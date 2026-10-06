# InfluxDB 3 bootstrap

One time, before the collector can write anything.

There is **no DDL**. InfluxDB is schema-on-write: the `spans` and
`gen_ai.client.token.*` tables, and every tag/field column in them, are created by
the first write. The only privileged steps are creating a token and a database.

## 1. Start InfluxDB alone

```bash
cd deploy
docker compose up -d influxdb3
```

## 2. Create an admin token

Printed **once**. Capture it.

```bash
docker compose exec influxdb3 influxdb3 create token --admin
export INFLUXDB3_AUTH_TOKEN='<the token>'
```

## 3. Create the database

On InfluxDB 3 this is what the collector's `bucket:` setting refers to.

**Retention is immutable in Core** — it is fixed at creation, and changing your mind
means creating a new database and migrating. 90 days is a reasonable starting point
for per-call span data.

```bash
docker compose exec influxdb3 \
  influxdb3 create database --retention-period 90d --token "$INFLUXDB3_AUTH_TOKEN" tokenmeter
```

HTTP equivalent, if you would rather not exec into the container:

```bash
curl -X POST localhost:8181/api/v3/configure/database \
  -H "Authorization: Bearer $INFLUXDB3_AUTH_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"db":"tokenmeter","retention_period":"90d"}'
```

## 4. Wire the collector

```bash
cp otelcol/.env.example otelcol/.env
# put the token in INFLUXDB3_TOKEN
docker compose up -d otelcol
curl -sf localhost:13133 && echo "collector healthy"
```

## Retention: one database or two?

`spans` is large and per-call; the metric tables are tiny and want to live forever.
One database means one retention period, so they cannot differ.

Start with the single 90-day database above. If the long-retention roll-up turns out
to matter, split into `tokenmeter` (90d, traces) and `tokenmeter_rollup` (infinite,
metrics) by declaring a second `influxdb` exporter that differs only in `bucket:`,
and pointing the metrics pipeline at it. Note Core's documented default cap of
5 databases.

Whichever you choose, write it down — Core will not let you change it later.
