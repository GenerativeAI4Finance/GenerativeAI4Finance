# tokenmeter → InfluxDB 3

A working stack that persists tokenmeter usage data in a queryable database.

```
app → tokenmeter → OTLP (gRPC 4317) → otelcol-contrib → InfluxDB 3
```

Nothing here changes the tokenmeter library. It is configuration plus the `init()`
call the application makes. Background and schema reasoning live in
[`../docs/influxdb3-backend.md`](../docs/influxdb3-backend.md).

## Layout

| Path | What |
|---|---|
| `otelcol/config.yaml` | Collector pipelines and the InfluxDB exporter. `span_dimensions` is the schema. |
| `otelcol/.env.example` | Copy to `.env` (gitignored) and fill in the token |
| `docker-compose.yaml` | InfluxDB 3 Core + contrib collector |
| `influxdb3/bootstrap.md` | One-time token and database creation |
| `influxdb3/queries.sql` | The analytics queries |
| `examples/smoke_emit.py` | Emits one known record for end-to-end verification |

## Quick start

1. Follow [`influxdb3/bootstrap.md`](influxdb3/bootstrap.md) to create the admin
   token and the `tokenmeter` database, and to fill in `otelcol/.env`.
2. `docker compose up -d && curl -sf localhost:13133`
3. Emit a test record:
   ```bash
   OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta \
       python examples/smoke_emit.py
   ```
   It prints the cost the sink should have computed (`5.02750`).
4. Check the row landed, and that the metric field is named `gauge`:
   ```bash
   docker compose exec influxdb3 influxdb3 query \
     --database tokenmeter --token "$INFLUXDB3_AUTH_TOKEN" \
     'SELECT time, "gen_ai.request.model", "gen_ai.conversation.id",
             "tokenmeter.metadata.user_id",
             CAST("gen_ai.usage.cost" AS DOUBLE) AS cost_usd, "attributes"
      FROM spans ORDER BY time DESC LIMIT 5'
   ```

## Three things that will look like bugs

**The token counts and cost are tags, not fields.** Tagging numbers normally explodes
series count. Here the only alternative is an unqueryable JSON blob, and the exporter
already forces the unique `span_id` into the tag set — so the `spans` table is
*already* one series per row and these add zero new series. Do not "fix" this.

**`span_dimensions` is a one-way door.** An attribute not on that list is JSON-encoded
into a single `attributes` column and cannot be summed, filtered, or grouped. Adding
an entry later does **not** backfill existing rows. Treat changes as a migration.

**The cost metric's field name depends on temporality.** Delta writes a `gauge`
field; cumulative writes `counter`. Queries written against one return *empty*, not an
error, when the other is in force. Always set
`OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta` in the application.

## Adding a metadata key

`tokenmeter.metadata.*` keys are caller-defined, so the collector allowlists them one
at a time. `user_id` is already listed. To add another, append it to
`span_dimensions` in `otelcol/config.yaml` and restart the collector.

The rule: **a key earns a slot only when you can name the `GROUP BY` you want it
for.** Never allowlist a UUID or a free-text key — it becomes a permanent column that
cannot be removed, and unlisted keys are still retained inside `attributes` anyway.

## Schema ownership

There is no DDL anywhere in this stack, by design. InfluxDB is schema-on-write, so
tables and columns appear as the exporter writes them. The database itself is created
out of band by an operator (`influxdb3 create database`), and the application code
assumes it already exists.

Retention is attached to the database and is **immutable in Core** — see
`influxdb3/bootstrap.md` for the one-database vs two-database trade-off.

## Operational caveats

- **Collector down = data lost.** tokenmeter's batch processors drop on overflow and
  never block the LLM path. `file_storage` protects collector→InfluxDB across
  collector restarts; nothing protects an app exiting with unflushed batches, so call
  `flush()` before returning in short-lived processes. At-most-once, end to end.
- **Pin the collector image.** The attributes-as-JSON layout is an implementation
  detail of `otel2influx`, not a documented contract.
- **The token belongs only in `otelcol/.env`.** Not in the config, not in a URL, not
  in a compose `environment:` block — those show up in `docker inspect`.
