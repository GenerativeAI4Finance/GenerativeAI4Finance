# G4F-SW-006: Least-privilege tool permissions for agents

A small permission layer for the simulated EDD swarm. Each agent is mapped to a
role, each role gets an explicit list of tools (and limits on the arguments to
those tools), and everything else is denied. Every decision, allow or deny, goes
to an audit log. Argument values stay out of that log unless the policy says a
particular argument is safe to record.

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
        "read_evidence": {
          "args": { "case_id": { "pattern": "SYN-CASE-[0-9]{4}", "log_value": true } }
        },
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
  rejected, and listed ones are required. A tool that takes no arguments is
  written as `{}`.
- Each argument needs at least one constraint:
  - `pattern`: full regex match on a string
  - `allowed`: non-empty list of exact values. Types must match too, so `true`
    does not pass for `1` and `1.0` does not pass for `1`.
  - `min` / `max`: finite numbers, with `min` no greater than `max`. Bools,
    NaN and infinity are rejected as values.
  - `max_length`: non-negative integer, for strings
- `log_value: true` on an argument lets its value appear in the audit log (see
  below). Leave it off for anything free text.
- Argument values must be plain strings, integers, floats, booleans or null.
  Lists, dicts, other objects and subclasses of the plain types are denied.

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
`Decision` without running the tool if you only want the answer. Keep the gate
with the orchestrator and give each agent only its handle.

## Design choices

- **Deny by default.** A call is allowed only if the agent is known, its role
  exists, the tool is both registered with the gate and granted to the role,
  and the arguments pass every constraint. Anything else is a deny.
- **Fail closed.** Any exception raised while checking a call becomes a deny
  with a reason starting with `policy check error`, followed by a cleaned and
  redacted exception type name. It never falls through to running the tool.
- **The checked value is the value the tool gets.** The gate copies the
  arguments once, checks that copy, and runs the tool with the same copy.
  Only exact plain types are accepted, so a mapping or string subclass can't
  show one value to the check and another to the tool.
- **Strict loading.** Malformed policies are rejected at load time with
  `PolicyError`: invalid JSON, duplicate keys, `NaN` or `Infinity`, unknown
  constraint keys, arguments with no constraint, bad regexes, `min` above
  `max`, negative or fractional `max_length`, `null` tool specs, unknown keys
  in a role, agents pointing at undefined roles, and any version other than
  the integer `1`. A typo like `"regex"` instead of `"pattern"` would
  otherwise be silently ignored and make the policy looser than intended.
- **Immutable at runtime.** The loaded policy and the tool registry are
  read-only mappings, copied from their inputs, and the gate's attributes
  can't be reassigned. Changing the source dict or the tool dict after the
  gate is built has no effect. To change permissions you edit `policy.json`
  and build a new gate.
- **Identity comes from the orchestrator.** Agents get an `AgentHandle` with a
  fixed agent ID. The handle doesn't hold the gate as an attribute, so the
  agent can't call `for_agent` to become someone else. The role is looked up
  from the policy, so passing `role="reviewer"` or similar in the arguments
  only gets the call rejected for an unexpected argument.

## Audit log

Decisions are logged as one JSON object per line to the
`g4f.permissions.audit` logger (allows at INFO, denies at WARNING). Fields:
`event`, `decision`, `agent`, `role`, `tool`, `reason`, `args`. Every
decision writes a line, including calls that fail in odd ways.

What `args` contains:

- By default only each argument's name and type, plus the length for
  strings, e.g. `"note": {"type": "str", "len": 412}`. Values are not logged.
- An argument marked `log_value: true` in the policy has its value logged,
  but only if the value passed that argument's own constraints. A `case_id`
  that matches `SYN-CASE-[0-9]{4}` is logged as is. Something else sent in
  that slot is logged as type and length only.
- Logged values still go through redaction as a second layer: secret-looking
  argument names such as `password`, `api_key` and `Authorization` cause the
  value to become `[REDACTED]` even with `log_value: true`. Strings that
  look like credentials (bearer and basic auth regardless of scheme case,
  `sk-` and Stripe keys, AWS,
  GitHub, Slack and Google keys, JWTs, PEM private keys, URLs with a password
  or a key in the query string) become `[REDACTED]`, and long strings are cut
  at 200 characters.
- Names chosen by the caller (unexpected argument names, tool names) are cut
  to 64 characters, non-printable characters are replaced with `?`, and names
  that look like credentials are redacted. The same applies to caller-controlled
  type names, deny reasons and `PermissionDenied` messages. At most 20 arguments
  are listed per line.

Deny reasons name the failing argument but never include its value.

Wire the logger to whatever handler you use. Nothing is written to disk by
default.

## Security notes and limitations

- This is an in-process check. It stops an agent that goes through its
  handle, but it is not a sandbox. Python code running in the same process
  can import the tool functions directly, use `object.__setattr__` on the
  gate, or dig the gate out of the handle's closure. Real isolation needs the
  tools to run in a separate process or service that does this check itself.
- The agent ID is trusted. Whoever creates the `AgentHandle` decides who the
  agent is. There is no authentication here.
- Keeping values out of the log is the main control for secrets. Redaction
  only applies to values a policy author chose to log, and it is pattern
  based, so it catches common credential formats and key names, not every
  possible secret. Only set `log_value` on arguments with a tight `pattern`
  or `allowed` list.
- Arguments are limited to plain scalar values. A tool that needs structured
  input would need a new constraint type rather than a looser check.
- Constraints check one argument at a time. Rules that depend on several
  arguments together, or on state (rate limits, "only cases assigned to this
  agent"), are not covered.
- Only the call is checked, not what the tool returns. If a tool returns data
  the role should not see, that is the tool's problem.
- Passing these tests does not mean the setup meets any regulatory or security
  standard. It is a reference for the simulated swarm, not a certified control.
