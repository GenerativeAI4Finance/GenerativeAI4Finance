# G4F-SW-006: Least-privilege tool permissions for agents

A small permission layer for the simulated EDD swarm. Each agent is mapped to a
role, each role gets an explicit list of tools (and optional limits on the
arguments to those tools), and everything else is denied. Every decision, allow
or deny, goes to an audit log with secret-looking values redacted.

No external services and no real data. Agent names, case IDs and source IDs are
all synthetic.

## Files

- `policy.json`: the permission configuration (agents, roles, tools, argument limits)
- `permissions.py`: policy loader, enforcement (`ToolGate`), audit logging and redaction
- `example.py`: a few allowed and denied calls so you can see the log output
- `tests/test_permissions.py`: pytest suite

## Running it

Python 3.12, only dependency is pytest.

```
cd 07-applications/swarm-ai/G4F-SW-006
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
python example.py
```

## Policy format

```json
{
  "version": 1,
  "agents": { "analyst-01": "evidence_analyst" },
  "roles": {
    "evidence_analyst": {
      "tools": {
        "read_evidence": { "args": { "case_id": { "pattern": "SYN-CASE-[0-9]{4}" } } },
        "list_sources": {}
      }
    }
  }
}
```

- `agents` maps an agent ID to exactly one role.
- A role can only call the tools listed under it. There is no wildcard and no
  role inheritance on purpose, so reading one role tells you everything it can do.
- `args` lists every argument the tool accepts. Arguments not listed are
  rejected, and listed ones are required. A tool with no `args` accepts no
  arguments.
- Argument constraints: `pattern` (full regex match on a string), `allowed`
  (list of exact values), `min` / `max` (numbers, bools rejected, NaN and inf
  rejected), `max_length` (strings).

The shipped policy has four roles taken from G4F-SW-003: `source_collector`,
`entity_matcher`, `evidence_analyst` and `reviewer`. Only the reviewer can set a
review status, and even then only to values that keep a human in the loop or
close with no finding. There is no status that lets an agent approve a finding.

## Using it

```python
from permissions import ToolGate, load_policy

gate = ToolGate(load_policy("policy.json"), {"read_evidence": read_evidence, ...})
analyst = gate.for_agent("analyst-01")   # hand this to the agent, not the gate
analyst.call("read_evidence", case_id="SYN-CASE-0007")
```

`call` raises `PermissionDenied` on any deny. `gate.check(...)` returns a
`Decision` without running the tool if you only want the answer.

## Design choices

- **Deny by default.** A call is allowed only if the agent is known, its role
  exists, the tool is both registered with the gate and granted to the role,
  and the arguments pass every constraint. Anything else is a deny.
- **Fail closed.** Any exception raised while checking a call (odd argument
  types, a bug in a constraint) becomes a deny with reason
  `policy check error`. It never falls through to running the tool.
- **Strict loading.** Malformed policies are rejected at load time: unknown
  constraint keys, bad regexes, agents pointing at undefined roles, wrong
  version. A typo like `"regex"` instead of `"pattern"` would otherwise be
  silently ignored and make the policy looser than intended.
- **Immutable at runtime.** The loaded policy and the tool registry are
  read-only mappings, copied from their inputs. Changing the source dict or
  the tool dict after the gate is built has no effect. To change permissions
  you edit `policy.json` and build a new gate.
- **Identity comes from the orchestrator.** Agents get an `AgentHandle` with a
  fixed agent ID. The role is looked up from the policy, so passing
  `role="reviewer"` or similar in the arguments does nothing except get the
  call rejected for an unexpected argument.

## Audit log

Decisions are logged as one JSON object per line to the
`g4f.permissions.audit` logger (allows at INFO, denies at WARNING). Fields:
`event`, `decision`, `agent`, `role`, `tool`, `reason`, `args`.

Redaction rules:

- Any argument whose key looks like a credential (`token`, `secret`,
  `password`, `api_key`, `authorization`, `cookie`, `session`, ...) is replaced
  with `[REDACTED]`, at any nesting depth.
- Any string value that looks like a credential (bearer tokens, `sk-` style
  keys, AWS access key IDs, GitHub tokens, PEM private keys) is redacted.
- Long strings are cut at 200 characters, and non-JSON objects are logged as
  their type name only.
- Deny reasons name the failing argument but never include its value.

Wire the logger to whatever handler you use. Nothing is written to disk by
default.

## Security notes and limitations

- This is an in-process check. It stops an agent that goes through the gate,
  but it is not a sandbox. Python code running in the same process can import
  the tool functions directly or poke at private attributes. Real isolation
  needs the tools to run in a separate process or service that does this check
  itself.
- The agent ID is trusted. Whoever creates the `AgentHandle` decides who the
  agent is. There is no authentication here.
- Redaction is pattern based. It catches common credential formats and key
  names, not every possible secret. Don't rely on it as the only control for
  keeping secrets out of logs, and keep secrets out of tool arguments where
  possible.
- Constraints check one argument at a time. Rules that depend on several
  arguments together, or on state (rate limits, "only cases assigned to this
  agent"), are not covered.
- Only the call is checked, not what the tool returns. If a tool returns data
  the role should not see, that is the tool's problem.
- Passing these tests does not mean the setup meets any regulatory or security
  standard. It is a reference for the simulated swarm, not a certified control.
