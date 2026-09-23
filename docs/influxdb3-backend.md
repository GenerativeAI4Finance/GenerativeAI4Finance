# Persisting tokenmeter data in InfluxDB 3

tokenmeter emits OpenTelemetry and nothing else — it does not ship data anywhere
itself. This page describes the collector that does, and the schema you get.

```
app → tokenmeter → OTLP (gRPC 4317) → otelcol-contrib → InfluxDB 3
```

Everything here is configuration. No tokenmeter source change is involved, and no
schema is created from code: InfluxDB is schema-on-write, and the database itself is
created out of band (see [`deploy/influxdb3/bootstrap.md`](../deploy/influxdb3/bootstrap.md)).

---

## 1. The span is the system of record

tokenmeter splits its attributes by signal deliberately. **Metrics carry only four
labels** — `gen_ai.provider.name`, `gen_ai.operation.name`, `gen_ai.request.model`,
`gen_ai.response.model` — to bound time-series cardinality. Everything identifying
rides the **span**: token counts, cost, `gen_ai.conversation.id`,
`gen_ai.agent.name`, `tokenmeter.environment`, and `tokenmeter.metadata.*`.

So per-run, per-agent and per-user cost can only ever be answered from spans. The
metric tables are a cheap long-retention roll-up and a cross-check, not a source of
truth. (This is also why a metrics-only store such as Prometheus cannot back this
use case on its own.)

## 2. An attribute is either a tag or it is unqueryable

This is the single most important thing to understand about this backend.

For every span attribute, `otel2influx` does exactly one of two things:

- the attribute is named in the exporter's `span_dimensions` → it becomes a **tag**,
  i.e. its own column;
- it is not → it is collected with every other unlisted attribute, `json.Marshal`ed,
  and stored as **one string field named `attributes`**.

There is no per-attribute field. InfluxDB 3 SQL has no reliable JSON extraction, so
**anything missing from `span_dimensions` cannot be summed, filtered, or grouped.**

Two consequences that look wrong until you know this:

- **The token counts and cost are tags.** Orthodox line-protocol advice says never
  tag a number, because tags define series. But the alternative here is the
  unqueryable JSON blob, and `otel2influx` already forces `span_id` into the tag set
  — `span_id` is unique per row, so the `spans` table is *already* one series per
  row. Promoting the measures adds **zero** series, only dictionary-encoded Parquet
  columns. Do not "fix" this.
- **`span_dimensions` is an allowlist for `tokenmeter.metadata.*`, and that is a
  feature.** Metadata keys are caller-defined. A key earns a slot only when you can
  name the `GROUP BY` you want it for. Unlisted keys are still retained inside
  `attributes` — just not indexed.

The list is a **one-way door**: adding an entry later does not backfill existing
rows. Get it right before ingesting volume.

### Why InfluxDB 3 specifically

InfluxDB 1 and 2 kept an in-memory inverted index keyed by series, so unbounded tags
killed the database outright — `gen_ai.conversation.id` as a tag would have been
fatal. InfluxDB 3 stores Parquet queried by DataFusion and has no series index. Tags
are ordinary dictionary-encoded columns. What they still control is sort order
(hence Parquet row-group pruning) and the per-table column budget.

**Tag choice on v3 is a performance and storage decision, not a survival one.** On
v2 this schema would have been malpractice.

## 3. What the tables look like

### `spans` — one row per `track()` call

| kind | column |
|---|---|
| time | `time` — the span **start** (`record.timestamp − duration_ms`), not completion |
| tag | `trace_id`, `span_id` — forced by the exporter |
| tag | `service.name`, `tokenmeter.environment`, `tokenmeter.app_version` |
| tag | `gen_ai.provider.name`, `gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.response.model` |
| tag | `gen_ai.conversation.id`, `gen_ai.agent.name` |
| tag | `tokenmeter.token_source`, `gen_ai.usage.cost.currency` |
| tag | `tokenmeter.metadata.user_id` — allowlisted |
| tag | `gen_ai.usage.input_tokens`, `...output_tokens`, `...cache_read.input_tokens`, `...cache_write.input_tokens`, `gen_ai.usage.cost` |
| field | `span.name`, `span.kind`, `duration_nano`, `end_time_unix_nano` |
| field | `attributes` — JSON of every unlisted attribute |

Attributes tokenmeter omits when unset (`conversation.id`, `agent.name`,
`environment`, `app_version`, and `cost` for an unpriced model) simply produce no
tag, which reads as `NULL` in SQL. That is how the "unpriced models" query works.

### `gen_ai.client.token.usage` and `gen_ai.client.token.cost`

Tags are the resource attributes plus `otel.library.name`/`version`, the four metric
attributes, and (histogram only) `gen_ai.token.type`.

The histogram is of limited value: the SDK's default bucket bounds top out at
10 000, so most token counts fall into `+Inf`. Only its `count` and `sum` fields
mean much.

## 4. Temporality decides the metric field name

tokenmeter passes no temporality preference, so the SDK default — **cumulative** —
applies. In `otel2influx`, a monotonic cumulative Sum is written to a field called
`counter`; anything else goes to `gauge`.

- **Cumulative → `counter`**: a running total since process start. Getting "spend
  last week" means per-series last-minus-first with restart-reset detection. With
  multiple workers, restarts silently under-report. Unworkable.
- **Delta → `gauge`**: the increment for that interval. `SUM()` over any window is
  directly correct, and a dead worker simply stops contributing.

Set this in the application environment before `init()`:

```bash
export OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta
```

It only takes effect in **bootstrap mode** (in attach mode the host must not pass an
explicit `preferred_temporality`), and it is process-wide. The collector-side
fallback is the `cumulativetodelta` processor with `initial_value: keep` — the
default `auto` silently drops the first point of every new series.

**The presence of a `gauge` column is the acceptance test.** If `SUM("gauge")`
returns nothing, you are still on cumulative.

## 5. Wiring the application

```bash
pip install "tokenmeter[otlp]"    # or init raises ExporterUnavailableError
export OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta
```

```python
tokenmeter.init(
    otel=OtelConfig(
        configure_sdk=True,
        endpoint="http://otelcol:4317",
        service_name="checkout-api",
        emit_logs=False,
        export_interval_millis=60_000,
    ),
    costs=[...],
    environment="prod",
    app_version="1.4.2",
)
```

`emit_logs=False` is recommended: tokenmeter gives the span and the log *identical*
attributes, and the log's only differentiator — `event_name="tokenmeter.token_usage"`
— is discarded by the InfluxDB exporter. Exporting both doubles write volume for
nothing.

If the app already configures OpenTelemetry, leave `configure_sdk=False` and point
its own exporters at the collector. Two attach-mode caveats: the temporality
variable may be overridden by the host, and `OtelConfig.service_name` is **ignored**
(it is only read when tokenmeter builds the SDK), so the `service.name` tag comes
from the host's resource.

## 6. Querying

InfluxDB 3 speaks SQL via `/api/v3/query_sql`, FlightSQL, or `influxdb3 query`.
InfluxQL is legacy and cannot express most of these.

Two mechanical rules: every tokenmeter key contains dots so **every identifier needs
double-quoting**, and tags come back as `Dictionary(Int32, Utf8)` so **numeric tags
need `CAST`**.

The full catalogue is in [`deploy/influxdb3/queries.sql`](../deploy/influxdb3/queries.sql):
spend by model, most expensive conversations, daily spend by agent, spend by user,
cache effectiveness, the token-source trust check, unpriced models, a
span-vs-metric reconciliation, and a long-retention monthly roll-up.

## 7. Operational notes

- **Retention** is attached to the database and is **immutable in Core**. `spans`
  and the metric tables have opposite needs; see `bootstrap.md` for the one-database
  vs two-database trade-off.
- **Collector down = data lost.** tokenmeter's batch processors drop on overflow and
  never block the LLM path. The `file_storage` sending queue protects
  collector→InfluxDB across collector restarts; nothing protects an app that exits
  with unflushed batches, so call `flush()` before returning in serverless. This
  pipeline is at-most-once from app to collector.
- **Prompt and response text never reach InfluxDB** — tokenmeter discards it. Do not
  defeat this by putting text into `metadata`.
- **Precision**: cost is downcast from `Decimal` to `float` before it leaves the
  process, and non-scalar metadata is JSON-stringified.
- **Pin the collector image.** The attributes-as-JSON layout is an implementation
  detail of `otel2influx`, not a documented contract, and its own `docs/traces.md`
  describes an older layout.
