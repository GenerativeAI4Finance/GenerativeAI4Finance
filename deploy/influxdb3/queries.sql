-- tokenmeter analytics against InfluxDB 3.
--
-- Run with:  influxdb3 query --database tokenmeter --token "$INFLUXDB3_AUTH_TOKEN" '<sql>'
--   or POST /api/v3/query_sql, or any FlightSQL client.
-- InfluxQL is legacy and cannot express most of these. Use SQL.
--
-- Two mechanical rules, both consequences of how the exporter writes:
--   1. Every tokenmeter attribute key contains dots, so every identifier must
--      be double-quoted.
--   2. Tags come back as Dictionary(Int32, Utf8), so the numeric ones need a
--      CAST before aggregation. If a cast errors, wrap it:
--      CAST(arrow_cast("col", 'Utf8') AS DOUBLE)
--
-- `time` on a spans row is the span START: sink.py back-dates it by
-- duration_ms. A 30-second completion lands up to 30s before it finished.
-- Irrelevant at daily granularity, relevant at 1-minute.


-- 1. Spend and volume by model, last 7 days.
--    The IS NOT NULL guard excludes non-tokenmeter spans if this collector is
--    shared with other instrumentation.
SELECT "gen_ai.provider.name"                             AS provider,
       "gen_ai.request.model"                             AS model,
       COUNT(*)                                           AS calls,
       SUM(CAST("gen_ai.usage.input_tokens"  AS BIGINT))  AS input_tokens,
       SUM(CAST("gen_ai.usage.output_tokens" AS BIGINT))  AS output_tokens,
       SUM(CAST("gen_ai.usage.cost" AS DOUBLE))           AS cost_usd
FROM spans
WHERE time >= now() - INTERVAL '7 days'
  AND "gen_ai.request.model" IS NOT NULL
GROUP BY 1, 2
ORDER BY cost_usd DESC;


-- 2. Most expensive conversations (agent runs), last 24h.
--    This is the query the metrics can NEVER answer: metric_attributes()
--    deliberately omits conversation id to bound cardinality.
SELECT "gen_ai.conversation.id"                   AS conversation_id,
       MIN(time)                                  AS started_at,
       COUNT(*)                                   AS calls,
       COUNT(DISTINCT "gen_ai.request.model")     AS models_used,
       SUM(CAST("gen_ai.usage.cost" AS DOUBLE))   AS cost_usd,
       SUM(CAST("duration_nano" AS DOUBLE)) / 1e9 AS model_seconds
FROM spans
WHERE time >= now() - INTERVAL '24 hours'
  AND "gen_ai.conversation.id" IS NOT NULL
GROUP BY 1
ORDER BY cost_usd DESC
LIMIT 25;


-- 3. Daily spend by agent, last 30 days.
SELECT date_trunc('day', time)                  AS day,
       "gen_ai.agent.name"                      AS agent,
       COUNT(*)                                 AS calls,
       SUM(CAST("gen_ai.usage.cost" AS DOUBLE)) AS cost_usd
FROM spans
WHERE time >= now() - INTERVAL '30 days'
  AND "gen_ai.agent.name" IS NOT NULL
GROUP BY 1, 2
ORDER BY day, cost_usd DESC;


-- 4. Spend by user. Works only because tokenmeter.metadata.user_id is on the
--    span_dimensions allowlist -- unlisted metadata keys are inside the
--    `attributes` JSON blob and cannot be grouped.
SELECT "tokenmeter.metadata.user_id"            AS user_id,
       COUNT(*)                                 AS calls,
       SUM(CAST("gen_ai.usage.cost" AS DOUBLE)) AS cost_usd
FROM spans
WHERE time >= now() - INTERVAL '30 days'
  AND "tokenmeter.metadata.user_id" IS NOT NULL
GROUP BY 1
ORDER BY cost_usd DESC;


-- 5. Cache effectiveness by model.
--    input_tokens is the UNCACHED remainder billed at the full input rate, so
--    cache_read must be added back to recover the true prompt size.
SELECT "gen_ai.request.model"                                           AS model,
       SUM(CAST("gen_ai.usage.input_tokens" AS DOUBLE))                 AS fresh_input_tokens,
       SUM(CAST("gen_ai.usage.cache_read.input_tokens"  AS DOUBLE))     AS cache_read_tokens,
       SUM(CAST("gen_ai.usage.cache_write.input_tokens" AS DOUBLE))     AS cache_write_tokens,
       SUM(CAST("gen_ai.usage.cache_read.input_tokens" AS DOUBLE))
         / NULLIF(SUM(CAST("gen_ai.usage.cache_read.input_tokens" AS DOUBLE))
                + SUM(CAST("gen_ai.usage.input_tokens" AS DOUBLE)), 0)  AS cache_hit_ratio
FROM spans
WHERE time >= now() - INTERVAL '7 days'
  AND "gen_ai.request.model" IS NOT NULL
GROUP BY 1
ORDER BY cache_hit_ratio DESC;


-- 6. Trust check: how much reported spend rests on estimated token counts?
--    Anything other than 'provider' is an estimate. If `heuristic` carries real
--    money, those call sites are not passing the provider's usage numbers.
SELECT "tokenmeter.token_source"                AS token_source,
       COUNT(*)                                 AS calls,
       SUM(CAST("gen_ai.usage.cost" AS DOUBLE)) AS cost_usd
FROM spans
WHERE time >= now() - INTERVAL '7 days'
GROUP BY 1;


-- 7. Unpriced models: real usage reporting no cost at all because no ModelCost
--    is configured. PriceBook.cost_for returns None, so the tag is absent.
SELECT "gen_ai.provider.name"                            AS provider,
       "gen_ai.request.model"                            AS model,
       COUNT(*)                                          AS calls,
       SUM(CAST("gen_ai.usage.input_tokens"  AS BIGINT)) AS input_tokens,
       SUM(CAST("gen_ai.usage.output_tokens" AS BIGINT)) AS output_tokens
FROM spans
WHERE time >= now() - INTERVAL '7 days'
  AND "gen_ai.request.model" IS NOT NULL
  AND "gen_ai.usage.cost" IS NULL
GROUP BY 1, 2
ORDER BY calls DESC;


-- 8. Reconcile spans against the metric roll-up.
--    REQUIRES DELTA TEMPORALITY. With delta the cost Sum lands in a `gauge`
--    field; with cumulative it lands in `counter` and this silently returns
--    nothing. That empty result is the symptom, not a bug in the query.
--    Non-trivial drift means spans are being dropped somewhere.
SELECT s.model,
       s.cost_from_spans,
       m.cost_from_metrics,
       abs(s.cost_from_spans - m.cost_from_metrics) AS drift
FROM (
  SELECT "gen_ai.request.model" AS model,
         SUM(CAST("gen_ai.usage.cost" AS DOUBLE)) AS cost_from_spans
  FROM spans
  WHERE time >= now() - INTERVAL '1 day' AND "gen_ai.request.model" IS NOT NULL
  GROUP BY 1
) s
FULL OUTER JOIN (
  SELECT "gen_ai.request.model" AS model,
         SUM("gauge") AS cost_from_metrics
  FROM "gen_ai.client.token.cost"
  WHERE time >= now() - INTERVAL '1 day'
  GROUP BY 1
) m ON s.model = m.model
ORDER BY drift DESC;


-- 9. Long-retention roll-up: monthly spend from metrics alone. Survives the
--    `spans` retention period if you split the databases.
SELECT date_trunc('month', time) AS month,
       "gen_ai.request.model"    AS model,
       SUM("gauge")              AS cost_usd
FROM "gen_ai.client.token.cost"
WHERE time >= now() - INTERVAL '12 months'
GROUP BY 1, 2
ORDER BY month, cost_usd DESC;
