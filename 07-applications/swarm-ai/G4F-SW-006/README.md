# G4F-SW-006: Least-privilege tool permissions

A permission layer for the simulated EDD swarm. Each agent maps to one role; each role
explicitly grants tools and constrains their arguments. Unlisted calls are denied.
Decisions go to an audit logger, with argument values omitted unless a policy opts in.

The example uses synthetic agent, case, and source IDs. It needs no external services or
real data.

## Files and setup

- `policy.json`: agents, roles, tools, and argument rules.
- `permissions.py`: strict policy loading, `ToolGate`, audit logging, and redaction.
- `example.py`: allowed and denied calls with audit output.
- `tests/test_permissions.py`: pytest coverage.

Requires Python 3.12; pytest is the only dependency.

```sh
cd 07-applications/swarm-ai/G4F-SW-006
python -m venv .venv
# Activate the environment for your shell, then:
pip install -r requirements.txt
python -m pytest
python example.py
```

## Policy format

```json
{
  "version": 1,
  "agents": {"analyst-01": "evidence_analyst"},
  "roles": {
    "evidence_analyst": {
      "tools": {
        "read_evidence": {
          "args": {
            "case_id": {"pattern": "SYN-CASE-[0-9]{4}", "log_value": true}
          }
        },
        "list_sources": {}
      }
    }
  }
}
```

`agents` maps IDs to roles. A role can call only its listed tools; there are no
wildcards or inherited permissions. Under `args`, list every accepted argument: listed
arguments are required, and any extra argument is denied. Use `{}` for a tool with no
arguments.

Each argument needs one or more constraints:

- `pattern`: full regular-expression match on a string.
- `allowed`: non-empty exact values; types must match (`true` is not `1`).
- `min` / `max`: finite numeric bounds, with `min <= max`.
- `max_length`: non-negative integer limit for strings.

Arguments accept only plain strings, integers, floats, booleans, or null. Lists,
mappings, custom objects, and subclasses of these types are denied. Booleans are not
treated as integers for numeric bounds.

Policies must be plain JSON data with string object keys and finite numbers. Files are
limited to 1 MiB before UTF-8 decoding. File and programmatic policies also have limits
of 32 levels, 20,000 nodes, 65,536 characters per string, 1,048,576 total string
characters, and 14,000 bits per integer. These limits include unused fields; integer
bounds such as `10**400` remain valid. Runtime strings and integers use the same scalar
limits.

Patterns are limited to 2,048 characters and 64 unescaped opening parentheses. String
limits and `max_length` are checked before matching. These budgets reduce resource use
but do not prevent catastrophic backtracking in arbitrary Python regexes; use simple,
reviewed patterns for agent-controlled input.

The shipped policy defines `source_collector`, `entity_matcher`, `evidence_analyst`, and
`reviewer`. Only the reviewer can set a review status, and permitted statuses keep a
human involved or close with no finding; agents cannot approve a finding.

## Use the gate

```python
from permissions import ToolGate, load_policy

policy = load_policy("policy.json")
gate = ToolGate(policy, {"read_evidence": read_evidence})
analyst = gate.for_agent("analyst-01")  # give the handle to the agent
analyst.call("read_evidence", case_id="SYN-CASE-0007")
```

`AgentHandle.call` raises `PermissionDenied` when denied. `gate.check(agent_id, tool,
args)` returns a `Decision` without running the tool. Keep the gate with the
orchestrator and provide agents only their fixed-ID handles.

The gate fails closed: unexpected checker errors become denies. It checks a copied
argument mapping and passes that same copy to the tool. Loaded policy and tool mappings
are read-only snapshots. Invalid UTF-8 or JSON, duplicate keys, non-finite values,
unknown fields in roles, tools, or constraints, malformed constraints or patterns,
invalid role references, and unsupported versions raise `PolicyError` at load time. Diagnostics avoid file paths,
parser details, and raw credential-like names.

## Audit and redaction

The `g4f.permissions.audit` logger emits one JSON line per decision: allows at INFO and
denies at WARNING. It does not write to disk unless you configure a handler. By default,
arguments are logged by name and type, plus string length; values are omitted. Deny
reasons identify the failing argument without including its value.

Set `log_value: true` only for arguments with tight constraints. A value is included
only when it passes that argument's constraints, and it is still redacted when its name
or content resembles a credential. Common key formats, authorization strings, JWTs,
private keys, and credential-bearing URLs are detected after limited URL decoding and
Unicode normalization. Logged strings are truncated to 200 characters plus a length marker;
caller-controlled names are truncated to 64 characters plus a length marker. Detection changes only the log
representation; the tool receives the checked input.

Redaction is pattern based and cannot find every secret. Leave free text unlogged. Even
a tight allowlist or pattern does not make logging arbitrary values risk-free.

## Security limits

This is an in-process permission check, not a sandbox. Code in the same Python process
can call imported tools directly or inspect/modify objects. Real isolation requires
checking calls in a separate process or service. Agent identity is trusted from whoever
creates the handle; this module provides no authentication.

Rules apply to individual arguments, not combinations of arguments or changing state
such as rate limits and case assignment. The gate checks calls, not returned data. This
simulated reference implementation is not a certified or regulatory control.
