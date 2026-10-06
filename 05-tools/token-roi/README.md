# tokenmeter

Drop-in LLM token metering. Call one function after every model response and the usage is emitted as
OpenTelemetry, following the [GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai),
so it lands in whatever observability backend you already run.

- **Never blocks your LLM path.** Emission is in-process; batching and export belong to the OTel SDK.
- **Never raises into your code.** `track()` catches everything and logs instead.
- **Never stores prompt or response text.** Text is counted, then discarded — it is not put on a
  span, a metric, or a log.
- **Works with agent SDKs.** Adapters and optional auto-instrumentation for the Claude Agent SDK,
  the OpenAI Agents SDK, and Google ADK.

## Install

```bash
pip install tokenmeter                    # core: pydantic + opentelemetry api/sdk
pip install "tokenmeter[otlp]"            # add OTLP exporters (only if tokenmeter bootstraps the SDK)
pip install "tokenmeter[tokenizers]"      # add tiktoken for exact OpenAI counts
```

## Quick start

If your application already configures OpenTelemetry, tokenmeter attaches to it — that is the
default, and there is nothing to wire up:

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
    environment="prod",
    app_version="1.4.2",
)

tokenmeter.track(
    prompt, response,
    model="claude-opus-5",
    provider="anthropic",
    metadata={"user_id": 42, "session_id": "s-9"},
    # optional but preferred — the provider's own numbers always win:
    input_tokens=1204, output_tokens=88,
    cache_read_tokens=6656, cache_write_tokens=0,
    duration_ms=1830.0,
)
```

If it does not, let tokenmeter build its own SDK and ship straight to a collector:

```python
from tokenmeter import OtelConfig

tokenmeter.init(
    otel=OtelConfig(configure_sdk=True, endpoint="http://localhost:4317",
                    service_name="checkout-api"),
    costs=[...],
)
```

`atrack`, `aflush`, and `ashutdown` are available for async codebases. `flush()` and `shutdown()`
drain the pipeline; `shutdown()` also runs at exit.

## What gets emitted

Per tracked call:

| Signal | What |
|---|---|
| Metric | `gen_ai.client.token.usage` (histogram, `{token}`) — one point with `gen_ai.token.type=input`, one with `output` |
| Metric | `gen_ai.client.token.cost` (counter, `{USD}`) — **non-standard**, omitted when the model has no configured price |
| Span | One `CLIENT` span named `chat claude-opus-5`, child of whatever span is active |
| Log | One record, `event_name = tokenmeter.token_usage` |

Span and log attributes:

| Attribute | Source |
|---|---|
| `gen_ai.provider.name` | your `provider`, mapped to the convention value (`vertex` → `gcp.vertex_ai`, …) |
| `gen_ai.operation.name` | `chat` / `embeddings` / `execute_tool`, from `call_type` |
| `gen_ai.request.model`, `gen_ai.response.model` | your `model` |
| `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | token counts |
| `gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.cache_write.input_tokens` | cache counts |
| `gen_ai.conversation.id` | `run_id`, or the ambient `run_context` |
| `gen_ai.agent.name` | `agent_name`, or the ambient `run_context` |
| `gen_ai.usage.cost`, `gen_ai.usage.cost.currency` | **non-standard** — the conventions define no cost attribute |
| `tokenmeter.token_source` | `provider` \| `tokenizer` \| `heuristic` — whether the counts are exact |
| `tokenmeter.environment`, `tokenmeter.app_version` | from `init()` |
| `tokenmeter.metadata.*` | your metadata, flattened; non-scalars are JSON-encoded |

**Metrics deliberately carry only provider, model, and operation.** Run ids, agent names, and
metadata would create a time series per value, so they ride spans and logs only — which means
per-run, per-agent and per-user cost can only be answered from spans, never from metrics.

`input_tokens` always means *tokens billed at the full input rate*. OpenAI and Google report cached
tokens inside the prompt count, so the adapters subtract them; Anthropic reports them separately, so
they are not. One cost formula then works across providers.

## Cost

Costs come from the `ModelCost` list you pass to `init()`. Cache rates default to Anthropic's
published multipliers of the input rate — 1.25× for writes, 0.10× for reads — and can be set
explicitly per model. An unpriced `(provider, model)` still emits full usage; it just carries no cost
attribute, and logs one warning naming the pair.

Cost is computed when the record is emitted, so changing a rate does not re-cost history. If that
matters, correct it in your backend.

## Persisting to a database

tokenmeter hands signals to OpenTelemetry and does not ship them anywhere itself. To keep usage in a
queryable store, put a collector between the app and a database:

```
app → tokenmeter → OTLP → otelcol-contrib → InfluxDB 3
```

[`deploy/`](deploy/) has a working stack — collector config, compose file, bootstrap steps and a
query catalogue — and [`docs/influxdb3-backend.md`](docs/influxdb3-backend.md) explains the schema.
The short version: the **span** is the system of record, because that is the only signal carrying
run ids, agent names, metadata and per-call cost.

## Agent SDKs

Parse a finished run explicitly:

```python
from tokenmeter.adapters import claude_agent, openai_agents, google_adk

claude_agent.track_result(result)          # per-model totals from a ResultMessage
openai_agents.track_run_result(result)     # one row per raw model response
google_adk.track_event(event)              # one row per ADK event
```

Or instrument once and forget:

```python
tokenmeter.instrument("claude_agent", "openai_agents", "google_adk")
```

| SDK | What auto-instrumentation hooks |
|---|---|
| Claude Agent SDK | `query` and `ClaudeSDKClient.receive_*`, recording each assistant message's usage |
| OpenAI Agents SDK | a trace processor over generation/response spans (needs the SDK's tracing on; use `openai_agents.run_hooks()` if it is off) |
| Google ADK | `Runner.run` / `Runner.run_async`, recording each event's `usage_metadata` |

Instrument **before** importing those names directly — a name already bound in your module keeps
pointing at the original. Do not combine `claude_agent.instrument()` with `track_result()` for the
same run: the first counts per call, the second counts per run, and together they double count.

Group a run's calls with `run_context`, which propagates through threads and asyncio tasks:

```python
from tokenmeter import run_context

with run_context(run_id="checkout-4711", agent_name="planner"):
    ...   # every call tracked in here shares gen_ai.conversation.id
```

## Token counting

Pass the provider's `usage` numbers whenever you have them. Without them, tokenmeter counts locally:
`tiktoken` for OpenAI, and a character heuristic elsewhere, since Anthropic and Google have no
offline tokenizer (their exact counts need a network call). `tokenmeter.token_source` records which
route was taken, so estimates can be filtered out of cost reporting.

## Conventions drift

The GenAI conventions are still `Development`. Two things to know:

- The cache-write attribute is `gen_ai.usage.cache_write.input_tokens` in the current registry, while
  some tooling still emits `gen_ai.usage.cache_creation.input_tokens`. Switch with
  `OtelConfig(cache_write_attribute=...)`.
- Cost attributes and the `tokenmeter.*` namespace are ours, not the spec's. They are namespaced so a
  strictly conformant backend ignores them rather than misreading them.

## Development

**pip is this project's package manager.** Dependencies are declared in `pyproject.toml`;
`requirements-dev.txt` is the one-command entry point that installs the package in editable mode
with every extra. No lock file is tracked — a library pins nothing, so that its host application
stays free to resolve its own versions.

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt                  # == pip install -e ".[dev,tokenizers,otlp]"
ruff check src tests && ruff format --check src tests && mypy && pytest
```

Tests use OpenTelemetry's in-memory exporters — no database, no collector, no network. To watch real
OTLP traffic instead, run a collector and init with `configure_sdk=True`:

```bash
docker run --rm -p 4317:4317 otel/opentelemetry-collector-contrib:0.161.0
```

Use the **contrib** distribution, not `otel/opentelemetry-collector` — the core image ships no
vendor exporters, so it cannot write to a database. For a full stack that persists usage to
InfluxDB 3, see [`deploy/`](deploy/).

Build and publish with the standard pip-ecosystem tools:

```bash
pip install build twine
python -m build          # sdist + wheel into dist/
twine upload dist/*
```

## Integrating tokenmeter with Claude Code

[`docs/claude-code-integration.md`](docs/claude-code-integration.md) is written for an agent working
inside a *client* application. Point Claude Code at it and it has everything needed to wire
tokenmeter in without reading this library's source.
