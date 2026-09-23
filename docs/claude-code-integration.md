# Integrating `tokenmeter` — a guide for Claude Code

**Audience: an AI coding agent working inside a client application that calls LLMs.** You do not need
to read tokenmeter's source. Everything required to wire it in correctly is on this page.

`tokenmeter` records what every LLM call in the host application cost — tokens in, tokens out, cache
hits, dollars — and emits it as OpenTelemetry following the
[GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai). It does
not ship data anywhere itself; it hands spans, metrics, and logs to the OTel pipeline the application
already has (or one it bootstraps for you). To persist that usage in a queryable database, see
[`influxdb3-backend.md`](influxdb3-backend.md) — a collector does the shipping, not this library.

Three guarantees that let you place calls freely:

| Guarantee | What it means for your edits |
|---|---|
| `track()` never raises | You do not need `try/except` around it. It returns `False` and logs on failure. |
| `track()` never blocks | Emission is in-process. Batching and network export belong to the OTel SDK. |
| Prompt/response text is never stored | Text passed in is counted, then discarded. It is not attached to any span, metric, or log. |

---

## 1. Decide whether to integrate at all

Integrate if the application makes LLM API calls and the user wants usage, cost, or per-tenant
attribution. **Do not** integrate as a "while I'm here" improvement — it adds a startup dependency
and a config surface. Ask first if the user has not requested it.

---

## 2. Install (pip)

tokenmeter is distributed on PyPI and installed with pip. Pick extras by what the app needs:

```bash
pip install tokenmeter                   # core: pydantic + opentelemetry api/sdk
pip install "tokenmeter[tokenizers]"     # + tiktoken — only if you count OpenAI text locally
pip install "tokenmeter[otlp]"           # + OTLP exporters — only if tokenmeter bootstraps the SDK
```

Add it to the client application's dependency declaration the same way its other deps are declared:

```toml
# pyproject.toml
dependencies = ["tokenmeter>=0.1"]
```

```
# requirements.txt
tokenmeter>=0.1
```

Requires Python ≥ 3.11.

---

## 3. Call `init()` exactly once, at startup

`init()` is process-wide. Call it before the first LLM call, in the application's startup path — not
at import time of a random module, and never inside a request handler.

```python
import tokenmeter
from tokenmeter import ModelCost

tokenmeter.init(
    costs=[
        ModelCost(provider="anthropic", model="claude-opus-5",
                  input_cost_per_1m=5, output_cost_per_1m=25),
        ModelCost(provider="openai", model="gpt-4o",
                  input_cost_per_1m=2.50, output_cost_per_1m=10),
    ],
    environment="prod",       # goes on every record as tokenmeter.environment
    app_version="1.4.2",      # goes on every record as tokenmeter.app_version
)
```

**Calling `init()` twice raises `AlreadyInitializedError`.** In codebases with reload, multiple
workers, or test fixtures, guard it:

```python
if not tokenmeter.is_initialized():
    tokenmeter.init(costs=COSTS, environment=ENV)
```

`shutdown()` is registered with `atexit`, so a normal process exit drains the pipeline for you.

### Does the app already configure OpenTelemetry?

Check for a call to `trace.set_tracer_provider(...)`, an `opentelemetry-instrument` entrypoint, or an
OTel vendor SDK (Datadog, Honeycomb, Grafana, New Relic).

* **Yes → do nothing.** Attach mode is the default. tokenmeter uses the app's providers and never
  shuts them down.
* **No → let tokenmeter bootstrap its own SDK** and export straight to a collector. This requires the
  `otlp` extra; without it you get `ExporterUnavailableError` naming the missing package.

```python
from tokenmeter import OtelConfig

tokenmeter.init(
    otel=OtelConfig(
        configure_sdk=True,
        endpoint="http://localhost:4317",
        protocol="grpc",                  # or "http/protobuf"
        service_name="checkout-api",
        headers={"x-api-key": "..."},     # if the collector needs auth
    ),
    costs=COSTS,
)
```

Bootstrapped providers are kept **local** to tokenmeter rather than installed globally, so they never
clobber a configuration the app adds later.

### Startup placement by application shape

```python
# FastAPI / Starlette — lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    tokenmeter.init(costs=COSTS, environment=settings.env, app_version=settings.version)
    yield
    await tokenmeter.ashutdown()

# Django — AppConfig.ready()
class CoreConfig(AppConfig):
    def ready(self):
        if not tokenmeter.is_initialized():
            tokenmeter.init(costs=COSTS, environment=settings.ENVIRONMENT)

# Celery worker — worker_process_init signal (each forked child needs its own)
@worker_process_init.connect
def _init_tokenmeter(**_):
    tokenmeter.init(costs=COSTS, environment=ENV)

# CLI / script / notebook — top of main()
def main() -> None:
    tokenmeter.init(costs=COSTS)
    ...
    tokenmeter.shutdown()

# AWS Lambda / serverless — init at module scope, FLUSH before returning.
# The container freezes after the handler returns; unflushed batches are lost.
tokenmeter.init(otel=OtelConfig(configure_sdk=True, endpoint=OTLP_URL), costs=COSTS)

def handler(event, context):
    result = do_work(event)
    tokenmeter.flush(timeout=2.0)
    return result
```

---

## 4. Record usage

Pick **one** of the three paths below per call site. Never combine two for the same call — that
double counts.

### Path A — raw provider SDK calls: `track()`

Call `track()` immediately after the model response returns. **Always pass the provider's own token
counts when the response carries them**; local counting is a fallback, and records which route was
taken in `tokenmeter.token_source` (`provider` | `tokenizer` | `heuristic`).

```python
tokenmeter.track(
    prompt, response_text,
    model="claude-opus-5",
    provider="anthropic",
    metadata={"user_id": 42, "session_id": "s-9"},
    input_tokens=1204, output_tokens=88,
    cache_read_tokens=6656, cache_write_tokens=0,
    duration_ms=1830.0,
)
```

`prompt` and `response` may be `None` when you pass explicit counts — text is only needed if
tokenmeter has to count it. Pass `None` rather than serialising a message list just to satisfy the
signature.

#### The one rule that is easy to get wrong

**`input_tokens` means *tokens billed at the full input rate* — cached tokens excluded.** Providers
disagree about this, so normalise at the call site:

| Provider | Response field | Mapping |
|---|---|---|
| **Anthropic** | `response.usage` | `input_tokens = usage.input_tokens` — already excludes cache. `cache_read_tokens = usage.cache_read_input_tokens`, `cache_write_tokens = usage.cache_creation_input_tokens` |
| **OpenAI** | `response.usage` | `input_tokens = usage.prompt_tokens - usage.prompt_tokens_details.cached_tokens` — the prompt count **includes** cached. `cache_read_tokens = ...cached_tokens`, `output_tokens = usage.completion_tokens` |
| **Google / Gemini** | `response.usage_metadata` | `input_tokens = prompt_token_count - cached_content_token_count`. `output_tokens = candidates_token_count + thoughts_token_count` (thinking bills as output). `cache_read_tokens = cached_content_token_count` |

Getting this wrong inflates cost by the full input rate on every cached token — typically the largest
error you can introduce. The agent-SDK adapters in Path B already handle it.

Concrete, per provider:

```python
# Anthropic
resp = client.messages.create(model="claude-opus-5", messages=msgs, max_tokens=1024)
u = resp.usage
tokenmeter.track(
    None, None, model="claude-opus-5", provider="anthropic",
    input_tokens=u.input_tokens,
    output_tokens=u.output_tokens,
    cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
    cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
    metadata={"user_id": user.id},
)

# OpenAI
resp = client.chat.completions.create(model="gpt-4o", messages=msgs)
u = resp.usage
cached = getattr(u.prompt_tokens_details, "cached_tokens", 0) or 0
tokenmeter.track(
    None, None, model="gpt-4o", provider="openai",
    input_tokens=u.prompt_tokens - cached,
    output_tokens=u.completion_tokens,
    cache_read_tokens=cached,
    metadata={"user_id": user.id},
)

# Google Gemini
resp = model.generate_content(prompt)
u = resp.usage_metadata
cached = getattr(u, "cached_content_token_count", 0) or 0
tokenmeter.track(
    None, None, model="gemini-2.5-pro", provider="google",
    input_tokens=u.prompt_token_count - cached,
    output_tokens=u.candidates_token_count + (getattr(u, "thoughts_token_count", 0) or 0),
    cache_read_tokens=cached,
)
```

**Streaming:** usage arrives on the final chunk (Anthropic `message_delta`, OpenAI's usage chunk when
`stream_options={"include_usage": True}`). Accumulate, then call `track()` once after the stream
closes. One call per model response, never per chunk.

Async code: `await tokenmeter.atrack(...)` — same signature.

### Path B — agent SDKs: adapters

If the app uses the Claude Agent SDK, the OpenAI Agents SDK, or Google ADK, use the adapter instead
of hand-mapping usage. Two granularities — **pick one per SDK**:

```python
# Auto: patch the SDK once at startup, right after init()
tokenmeter.instrument("claude_agent", "openai_agents", "google_adk")
```

```python
# Explicit: parse a finished run yourself
from tokenmeter.adapters import claude_agent, openai_agents, google_adk

claude_agent.track_result(result)        # per-model totals from a terminal ResultMessage
openai_agents.track_run_result(result)   # one row per raw model response in the run
google_adk.track_event(event)            # one row per ADK event
```

| SDK | `instrument()` patches | Notes |
|---|---|---|
| Claude Agent SDK | `query`, `ClaudeSDKClient.receive_messages`, `receive_response` | one row per assistant message |
| OpenAI Agents SDK | registers a trace processor over generation/response spans | needs the SDK's tracing **on** (the default); if it is off, pass `openai_agents.run_hooks()` to `Runner.run(hooks=...)` |
| Google ADK | `Runner.run`, `Runner.run_async` | one row per event carrying `usage_metadata` |

Two failure modes to avoid:

1. **Instrument before the SDK's names are imported by name.** `from claude_agent_sdk import query`
   binds `query` in that module; patching afterwards does not reach it. Call
   `tokenmeter.instrument(...)` at startup, before importing app modules that do this — or have them
   use `claude_agent_sdk.query(...)` via the module.
2. **Never combine `instrument()` with `track_result()` for the same run.** The first counts per
   call, the second counts per run. Together they double count.

`instrument()` with explicit names raises `AdapterUnavailableError` if that SDK is not installed, so
typos fail loudly. `instrument()` with **no** arguments instruments whatever happens to be installed
and silently skips the rest. `uninstrument(...)` reverses it.

### Path C — anything else: `record_sample()`

For a provider or framework with no adapter, normalise to a `UsageSample` yourself:

```python
from tokenmeter import UsageSample, TokenSource, CallType

tokenmeter.record_sample(UsageSample(
    provider="mistral",
    model="mistral-large",
    input_tokens=900,          # already net of cache — see the rule above
    output_tokens=120,
    cache_read_tokens=0,
    cache_write_tokens=0,
    token_source=TokenSource.PROVIDER,
    call_type=CallType.COMPLETION,
    duration_ms=412.0,
    run_id=None,               # falls back to the ambient run_context
    agent_name=None,
    metadata={"tenant": "acme"},
))
```

---

## 5. Group a run's calls with `run_context`

An agent run makes many model calls. Wrap the run so they share one `gen_ai.conversation.id`, instead
of threading a run id through every function:

```python
from tokenmeter import run_context

with run_context(run_id="checkout-4711", agent_name="planner"):
    ...  # every call tracked inside — including nested tasks — shares the id
```

Backed by `contextvars`, so it propagates into asyncio tasks and threads. Omit `run_id` and one is
generated. An explicit `run_id=`/`agent_name=` on `track()` wins over the ambient context.

---

## 6. Prices

Cost is only emitted for `(provider, model)` pairs configured in `init(costs=[...])`. An unpriced
pair still emits full token usage — it just carries no cost attribute, and logs **one** warning
naming the pair. Match is case-insensitive and whitespace-trimmed.

```python
ModelCost(
    provider="anthropic",
    model="claude-opus-5",
    input_cost_per_1m=5,             # USD per 1M tokens
    output_cost_per_1m=25,
    cache_write_cost_per_1m=6.25,    # optional — defaults to 1.25× input
    cache_read_cost_per_1m=0.50,     # optional — defaults to 0.10× input
)
```

Cache defaults follow Anthropic's published multipliers. **Set them explicitly for OpenAI and Google,
whose cached-token discounts differ.** Use `Decimal("2.50")` rather than a float for prices you care
about to the cent.

Cost is computed at emission time, so changing a rate does not re-cost history. Backfill corrections
in the observability backend, not here.

Keep the price list in the app's config (env, settings module, or a JSON/YAML file) so it can change
without a code deploy:

```python
COSTS = [ModelCost(**row) for row in json.loads(Path("model_costs.json").read_text())]
```

---

## 7. Metadata: what to attach, and what never to

Metadata is flattened onto spans and logs as `tokenmeter.metadata.<key>`. Accepts a `dict` or a
pydantic `BaseModel`. Non-scalar values are JSON-encoded rather than dropped.

**Attach** the dimensions the user will slice cost by: `user_id`, `tenant_id`, `session_id`,
`feature`, `request_id`, `plan_tier`.

**Never attach** prompt text, response text, message lists, tool arguments, API keys, PII, or
embedding vectors. tokenmeter deliberately discards the text you pass to `track()`; putting it back
in `metadata` defeats that and writes it to your logging backend.

**Metrics carry only `provider`, `model`, and `operation`** — never metadata, run ids, or agent names,
because each distinct value would create a new time series. Those ride spans and logs. So query
per-user cost from spans/logs, and aggregate cost from metrics.

---

## 8. What lands in the backend

| Signal | Name |
|---|---|
| Metric | `gen_ai.client.token.usage` — histogram, `{token}`; one point with `gen_ai.token.type=input`, one with `output` |
| Metric | `gen_ai.client.token.cost` — counter, `{USD}`; **non-standard**, omitted when the model has no configured price |
| Span | one `CLIENT` span named `chat <model>`, child of whatever span is active, back-dated by `duration_ms` |
| Log | one record, `event_name = tokenmeter.token_usage` |

Span and log attributes: `gen_ai.provider.name`, `gen_ai.operation.name`, `gen_ai.request.model`,
`gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.cache_write.input_tokens`,
`gen_ai.conversation.id`, `gen_ai.agent.name`, plus the non-standard `gen_ai.usage.cost`,
`gen_ai.usage.cost.currency`, `tokenmeter.token_source`, `tokenmeter.environment`,
`tokenmeter.app_version`, `tokenmeter.metadata.*`.

`provider` is mapped to the convention's well-known value: `azure_openai` → `azure.ai.openai`,
`bedrock` → `aws.bedrock`, `vertex` → `gcp.vertex_ai`, `google` → `gcp.gen_ai`, `gemini` →
`gcp.gemini`, `foundry` → `azure.ai.inference`. Unmapped providers pass through lowercased.

If the backend expects the older cache-write attribute name, switch it:
`OtelConfig(cache_write_attribute="gen_ai.usage.cache_creation.input_tokens")`.

### …and what lands in a database

If a collector is persisting this (see [`influxdb3-backend.md`](influxdb3-backend.md)), the mapping
is not one column per attribute. With the InfluxDB exporter, an attribute listed in the collector's
`span_dimensions` becomes its own column; every attribute *not* listed is JSON-encoded together into
a single `attributes` column and cannot be aggregated or grouped in SQL. Plan that list before
ingesting data — adding to it later does not backfill existing rows.

Two further notes for that path: `event_name` is dropped on the logs route, so the span is the
signal worth keeping (`emit_logs=False`); and metrics still carry only the four low-cardinality
attributes, so per-user and per-run cost must come from spans.

---

## 9. Verify the integration before reporting done

Do not claim the integration works because the code compiles. Prove a record is emitted, with an
in-memory exporter and no network:

```python
# test_tokenmeter_integration.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import tokenmeter
from tokenmeter import ModelCost


def test_llm_call_is_metered() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    tokenmeter.init(
        costs=[ModelCost(provider="anthropic", model="claude-opus-5",
                         input_cost_per_1m=5, output_cost_per_1m=25)],
        environment="test",
    )
    try:
        assert tokenmeter.track(
            None, None, model="claude-opus-5", provider="anthropic",
            input_tokens=1_000_000, output_tokens=0, metadata={"user_id": 1},
        )
    finally:
        tokenmeter.shutdown(timeout=1.0)

    span = exporter.get_finished_spans()[-1]
    assert span.name == "chat claude-opus-5"
    assert span.attributes["gen_ai.usage.input_tokens"] == 1_000_000
    assert span.attributes["gen_ai.usage.cost"] == 5.0          # 1M input tokens @ $5/1M
    assert span.attributes["tokenmeter.token_source"] == "provider"
    assert span.attributes["tokenmeter.metadata.user_id"] == 1
```

Then walk this checklist:

- [ ] `init()` runs exactly once, in the startup path, before the first LLM call.
- [ ] Every LLM call site the app owns is tracked — grep for `messages.create`,
      `chat.completions.create`, `generate_content`, `Runner.run`, `query(`.
- [ ] No call site is covered twice (adapter *and* manual `track()`).
- [ ] `input_tokens` excludes cached tokens for OpenAI and Google (§4).
- [ ] `tokenmeter.token_source` is `provider` on real traffic — `heuristic` means the provider's
      counts were not passed and the cost figures are estimates.
- [ ] Every model the app actually uses has a `ModelCost`; watch the logs for
      *"no configured cost for provider=… model=…"*.
- [ ] Serverless or short-lived processes call `flush()` before exit.
- [ ] No prompt, response, or PII in `metadata`.

---

## 10. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Log: *"init() has not been called; usage is not being recorded"* | `track()` ran before `init()`, once per process. Move `init()` earlier. |
| `AlreadyInitializedError` | `init()` called twice — reload, a second worker, or a test fixture. Guard with `is_initialized()`. |
| Log: *"no configured cost for provider=… model=…"* | That pair has no `ModelCost`. Usage is still recorded; add the price to get cost. |
| `ExporterUnavailableError` | `configure_sdk=True` without the exporters: `pip install "tokenmeter[otlp]"`. |
| `AdapterUnavailableError` | `instrument("…")` named an SDK that is not installed. Install it or drop the name. |
| `UnknownAdapterError` | Bad adapter name. Valid: `claude_agent`, `openai_agents`, `google_adk`. |
| `token_source` is `heuristic` | No counts passed and no offline tokenizer (Anthropic/Google have none). Pass the provider's `usage`. |
| `token_source` is `heuristic` for OpenAI | `pip install "tokenmeter[tokenizers]"` for exact tiktoken counts — or better, pass `usage`. |
| Nothing reaches the backend | Attach mode with no OTel configured in the app. Either configure OTel, or use `OtelConfig(configure_sdk=True, endpoint=...)`. |
| Everything double counted | An adapter *and* a manual `track()` on the same path, or `instrument()` plus `track_result()`. |
| Auto-instrumentation records nothing | The SDK name was imported directly before `instrument()` ran (§4 Path B). |
| Cost looks ~2× too high | Cached tokens counted at full input rate — see the `input_tokens` rule in §4. |
| Data lost in Lambda/CLI | Process exited before the batch exported. Call `flush()` (or `await aflush()`) before returning. |
| Rows never appear in the database | Check the collector's health endpoint, then its logs for a `Permanent error` from the exporter — usually a 401, because an empty token env var means no auth header is sent at all. Then check the app's endpoint, and whether `flush()` ran before exit. |
| Using the core collector image | `otel/opentelemetry-collector` ships no vendor exporters. Use `otel/opentelemetry-collector-contrib`. |
| Database has the span but no cost/token columns | Those attributes are not in the exporter's `span_dimensions`, so they sit inside the `attributes` JSON blob. Add them and restart — existing rows are **not** backfilled. |
| Cost metric sums to nothing | Metrics are still cumulative, so the field is named `counter`, not `gauge`. Set `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta` in the app before startup. |
| Cannot group spend by user | `tokenmeter.metadata.*` keys must be allowlisted in the collector to become columns, and metrics never carry them at all. |
| `service.name` is `unknown_service` | Attach mode ignores `OtelConfig.service_name` — it is only read when `configure_sdk=True`. Set `OTEL_SERVICE_NAME` or fix the host's resource. |

---

## 11. API reference

```python
tokenmeter.init(otel=None, costs=(), *, environment=None, app_version=None,
                chars_per_token=4.0, sink=None) -> TokenMeter
tokenmeter.track(prompt, response, model, provider, metadata=None, *,
                 input_tokens=None, output_tokens=None,
                 cache_read_tokens=0, cache_write_tokens=0,
                 call_type=CallType.COMPLETION, run_id=None, agent_name=None,
                 timestamp=None, duration_ms=None) -> bool
tokenmeter.record_sample(sample, *, timestamp=None) -> bool
tokenmeter.flush(timeout=30.0) -> bool
tokenmeter.shutdown(timeout=30.0) -> None
tokenmeter.instrument(*names) -> None        # "claude_agent" | "openai_agents" | "google_adk"
tokenmeter.uninstrument(*names) -> None
tokenmeter.is_initialized() -> bool
tokenmeter.get_client() -> TokenMeter        # raises NotInitializedError if init() has not run
tokenmeter.run_context(run_id=None, agent_name=None)            # context manager
tokenmeter.current_correlation() -> Correlation
```

Async equivalents: `atrack`, `arecord_sample`, `aflush`, `ashutdown`.

Config/data types: `OtelConfig`, `ModelCost`, `MeterConfig`, `UsageSample`, `TokenUsageRecord`,
`CostBreakdown`, `PriceBook`, `Correlation`.
Enums: `CallType` (`COMPLETION` → `chat`, `TOOL` → `execute_tool`, `EMBEDDING` → `embeddings`),
`TokenSource` (`PROVIDER`, `TOKENIZER`, `HEURISTIC`).
Errors: `TokenMeterError` (base), `NotInitializedError`, `AlreadyInitializedError`,
`AdapterUnavailableError`, `UnknownAdapterError`, `ExporterUnavailableError` — all raised from
configuration-time entry points only, never from `track()`.

For a database-backed collector, `emit_logs=False` is recommended: the span and the log carry
identical attributes, and the log's only distinguishing field, `event_name`, is discarded by the
InfluxDB exporter.

`OtelConfig` fields: `configure_sdk` (`False`), `endpoint`, `protocol` (`"grpc"` |
`"http/protobuf"`), `headers`, `service_name`, `resource_attributes`, `emit_metrics`, `emit_spans`,
`emit_logs` (all `True`), `export_interval_millis` (`60_000`), `cache_write_attribute`.

---

## 12. Rules of thumb

1. `init()` once, at startup, guarded by `is_initialized()` where reload is possible.
2. Always pass the provider's own `usage` numbers. Local counting is a fallback, not a plan.
3. `input_tokens` = tokens billed at the full input rate. Subtract cached tokens for OpenAI and
   Google; do not subtract for Anthropic.
4. One record per model response. Not per chunk, not per run *and* per call.
5. Metadata is for dimensions you will slice by — never for text or PII.
6. Price every model the app uses, or accept usage without cost.
7. Flush before a short-lived process exits.
8. Verify with an in-memory exporter before reporting the integration done.
