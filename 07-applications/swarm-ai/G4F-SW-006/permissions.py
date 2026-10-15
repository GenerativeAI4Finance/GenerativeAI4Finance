"""Role-based tool permissions for simulated swarm agents.

Every tool call goes through ToolGate. Anything the policy does not explicitly
allow is denied, and every decision is written to the audit log. Argument
values stay out of the log unless the policy opts in for that argument.
"""

from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import unquote

audit_log = logging.getLogger("g4f.permissions.audit")

CONSTRAINT_KEYS = {"pattern", "allowed", "min", "max", "max_length"}
ARG_SPEC_KEYS = CONSTRAINT_KEYS | {"log_value"}
# Argument values must have exactly one of these types. Subclasses are
# rejected so the value that gets checked is the value the tool receives.
SCALAR_TYPES = (str, int, float, bool, type(None))

SECRET_KEY_RE = re.compile(
    r"secret|token|passw|pwd|api[_-]?key|access[_-]?key|auth|credential"
    r"|(?:private|signing|encryption|master)[_-]?key|cookie|session|jwt|dsn"
    r"|signature|bearer",
    re.IGNORECASE,
)
SECRET_VALUE_RES = [
    re.compile(r"\bbearer\s+\S+", re.IGNORECASE),
    re.compile(r"\bBasic\s+[A-Za-z0-9+/]{8,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    # credentials inside URLs: user:pass@host and ?api_key=...
    re.compile(r"://[^/\s:@]+:[^/\s@]+@"),
    re.compile(
        r"[?&](?:api[_-]?key|access[_-]?token|token|secret|password|sig|signature)=",
        re.IGNORECASE,
    ),
]
REDACTED = "[REDACTED]"
MAX_LOGGED_STR = 200
MAX_LABEL = 64
MAX_NAMES_IN_REASON = 5
MAX_LOGGED_ARGS = 20
MAX_POLICY_BYTES = 1024 * 1024
MAX_POLICY_DEPTH = 32
MAX_POLICY_NODES = 20_000
MAX_TEXT_LENGTH = 65_536
MAX_INTEGER_BITS = 14_000
MAX_PATTERN_LENGTH = 2048
MAX_PATTERN_DEPTH = 64


class PolicyError(ValueError):
    """The policy file is malformed. Raised at load time, never at call time."""


class PermissionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    role: str | None = None


@dataclass(frozen=True)
class Policy:
    agents: Mapping[str, str]
    # role -> tool -> arg name -> arg spec (constraints plus optional log_value)
    roles: Mapping[str, Mapping[str, Mapping[str, Mapping[str, Any]]]]

    def check(self, agent_id: str, tool: str, args: Mapping[str, Any]) -> Decision:
        role = self.agents.get(agent_id)
        if role is None:
            return Decision(False, "unknown agent")
        tools = self.roles.get(role)
        if tools is None:
            return Decision(False, "agent mapped to unknown role", role)
        spec = tools.get(tool)
        if spec is None:
            return Decision(False, "tool not granted to role", role)

        unexpected = sorted(set(args) - set(spec))
        if unexpected:
            # These names come from the caller, so only cleaned-up labels go
            # into the reason.
            return Decision(
                False, f"unexpected arguments: {_name_list(unexpected)}", role
            )
        missing = sorted(set(spec) - set(args))
        if missing:
            return Decision(False, f"missing arguments: {_name_list(missing)}", role)

        for name, arg_spec in spec.items():
            problem = _violation(args[name], arg_spec)
            if problem:
                # Only the arg name goes in the reason, never the value.
                return Decision(False, f"argument '{_label(name)}' {problem}", role)
        return Decision(True, "allowed", role)


def _violation(value: Any, c: Mapping[str, Any]) -> str | None:
    # Exact type comparisons throughout: bool is an int subclass, and True
    # should not pass as 1.
    if type(value) is str and len(value) > MAX_TEXT_LENGTH:
        return "exceeds string limit"
    if type(value) is int and value.bit_length() > MAX_INTEGER_BITS:
        return "exceeds integer limit"
    if "max_length" in c and (type(value) is not str or len(value) > c["max_length"]):
        return "exceeds max_length"
    if "allowed" in c and not any(
        type(value) is type(a) and value == a for a in c["allowed"]
    ):
        return "not in allowed values"
    if "pattern" in c and (type(value) is not str or not c["pattern"].fullmatch(value)):
        return "does not match pattern"
    if "min" in c or "max" in c:
        if type(value) not in (int, float):
            return "is not a number"
        if type(value) is float and not math.isfinite(value):
            return "is not a finite number"
        if "min" in c and value < c["min"]:
            return "below min"
        if "max" in c and value > c["max"]:
            return "above max"
    return None


def load_policy(path: str | Path) -> Policy:
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(MAX_POLICY_BYTES + 1)
    except OSError:
        # Paths and OS error text may contain credentials.
        raise PolicyError("cannot read policy file") from None
    if len(data) > MAX_POLICY_BYTES:
        raise PolicyError("policy exceeds byte limit")
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        raise PolicyError("policy is not valid UTF-8") from None
    _check_json_depth(text)
    try:
        raw = json.loads(
            text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_nan
        )
    except PolicyError:
        raise
    except (ValueError, RecursionError, OverflowError):
        raise PolicyError("policy is not valid JSON") from None
    return parse_policy(raw)


def _check_json_depth(text: str) -> None:
    """Bound nesting before the JSON decoder enters recursive parsing."""
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_POLICY_DEPTH:
                raise PolicyError("policy is not valid JSON: nesting limit exceeded")
        elif char in "]}":
            depth -= 1


def _check_policy_tree(raw: Any) -> None:
    """Validate plain, bounded data before formatting names or compiling regexes."""
    pending = [(raw, 0)]
    nodes = chars = 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if depth > MAX_POLICY_DEPTH or nodes > MAX_POLICY_NODES:
            raise PolicyError("policy exceeds structure limit")
        if type(value) in (dict, list):
            if len(value) > MAX_POLICY_NODES:
                raise PolicyError("policy exceeds structure limit")
            children = value.items() if type(value) is dict else enumerate(value)
            for key, child in children:
                if type(value) is dict:
                    if type(key) is not str:
                        raise PolicyError("policy object keys must be plain strings")
                    pending.append((key, depth + 1))
                pending.append((child, depth + 1))
            if len(pending) + nodes > MAX_POLICY_NODES:
                raise PolicyError("policy exceeds structure limit")
        elif type(value) is str:
            chars += len(value)
            if len(value) > MAX_TEXT_LENGTH or chars > MAX_POLICY_BYTES:
                raise PolicyError("policy exceeds string limit")
        elif type(value) is int:
            if value.bit_length() > MAX_INTEGER_BITS:
                raise PolicyError("policy exceeds integer limit")
        elif type(value) is float and not math.isfinite(value):
            raise PolicyError("policy numbers must be finite")
        elif type(value) not in SCALAR_TYPES:
            raise PolicyError("policy must contain only plain JSON data")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            # json would otherwise keep the last value without saying anything.
            raise PolicyError(f"duplicate key '{_label(key)}' in policy")
        out[key] = value
    return out


def _reject_nan(name: str) -> Any:
    raise PolicyError(f"'{name}' is not allowed in a policy file")


def parse_policy(raw: Any) -> Policy:
    _check_policy_tree(raw)
    if (
        not isinstance(raw, dict)
        or type(raw.get("version")) is not int
        or raw["version"] != 1
    ):
        raise PolicyError("policy must be an object with version 1")
    agents, roles = raw.get("agents"), raw.get("roles")
    if not isinstance(agents, dict) or not isinstance(roles, dict):
        raise PolicyError("policy needs 'agents' and 'roles' objects")

    frozen_roles = {}
    for role, body in roles.items():
        role_label = _label(role)
        if not isinstance(body, dict) or set(body) != {"tools"}:
            raise PolicyError(
                f"role '{role_label}' must be an object with only 'tools'"
            )
        if not isinstance(body["tools"], dict):
            raise PolicyError(f"role '{role_label}' needs a 'tools' object")
        tools = {}
        for tool, tool_spec in body["tools"].items():
            where = f"{role_label}.{_label(tool)}"
            if not isinstance(tool_spec, dict) or set(tool_spec) - {"args"}:
                raise PolicyError(
                    f"{where}: tool spec must be an object with only 'args'"
                    " (use {} for a tool that takes no arguments)"
                )
            arg_specs = tool_spec.get("args", {})
            if not isinstance(arg_specs, dict):
                raise PolicyError(f"{where}: 'args' must be an object")
            tools[tool] = MappingProxyType(
                {
                    name: _parse_arg_spec(f"{where}.{_label(name)}", c)
                    for name, c in arg_specs.items()
                }
            )
        frozen_roles[role] = MappingProxyType(tools)

    for agent, role in agents.items():
        if not isinstance(role, str) or role not in frozen_roles:
            raise PolicyError(
                f"agent '{_label(agent)}' refers to undefined role {_label(role)}"
            )

    return Policy(
        agents=MappingProxyType(dict(agents)), roles=MappingProxyType(frozen_roles)
    )


def _parse_arg_spec(where: str, c: Any) -> Mapping[str, Any]:
    if not isinstance(c, dict):
        raise PolicyError(f"{where}: argument spec must be an object")
    unknown = set(c) - ARG_SPEC_KEYS
    if unknown:
        # An unrecognised constraint would otherwise be silently ignored,
        # which would make the policy looser than its author intended.
        raise PolicyError(
            f"{where}: unknown constraint keys {_name_list(sorted(unknown))}"
        )
    if not set(c) & CONSTRAINT_KEYS:
        raise PolicyError(
            f"{where}: needs at least one of {', '.join(sorted(CONSTRAINT_KEYS))}"
        )
    out = dict(c)
    if "log_value" in out and type(out["log_value"]) is not bool:
        raise PolicyError(f"{where}: 'log_value' must be true or false")
    if "pattern" in out:
        if type(out["pattern"]) is not str:
            raise PolicyError(f"{where}: 'pattern' must be a string")
        _check_pattern_limits(out["pattern"], where)
        try:
            out["pattern"] = re.compile(out["pattern"])
        except (re.error, OverflowError, RecursionError):
            raise PolicyError(f"{where}: bad pattern") from None
    if "allowed" in out:
        values = out["allowed"]
        if not isinstance(values, list) or not values:
            raise PolicyError(f"{where}: 'allowed' must be a non-empty list")
        for v in values:
            if type(v) not in SCALAR_TYPES or (
                type(v) is float and not math.isfinite(v)
            ):
                raise PolicyError(
                    f"{where}: 'allowed' values must be strings, finite numbers,"
                    " booleans or null"
                )
        out["allowed"] = tuple(values)
    for key in ("min", "max"):
        if key not in out:
            continue
        value = out[key]
        if type(value) not in (int, float) or (
            type(value) is float and not math.isfinite(value)
        ):
            raise PolicyError(f"{where}: '{key}' must be a finite number")
    if "min" in out and "max" in out and out["min"] > out["max"]:
        raise PolicyError(f"{where}: 'min' is greater than 'max'")
    if "max_length" in out and (
        type(out["max_length"]) is not int or out["max_length"] < 0
    ):
        raise PolicyError(f"{where}: 'max_length' must be a non-negative integer")
    return MappingProxyType(out)


def _check_pattern_limits(pattern: str, where: str) -> None:
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise PolicyError(f"{where}: bad pattern (length limit exceeded)")
    groups = 0
    escaped = False
    for char in pattern:
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "(":
            # A conservative syntax budget also counts parentheses in classes
            # and comments, avoiding parser-specific ways to hide nesting.
            groups += 1
            if groups > MAX_PATTERN_DEPTH:
                raise PolicyError(f"{where}: bad pattern (parenthesis limit exceeded)")


def _secret_forms(text: str) -> list[str]:
    # Normalize only for detection. Never change the checked or executed input.
    if len(text) > MAX_TEXT_LENGTH:
        return []
    forms = [text]
    for _ in range(4):
        canonical = unicodedata.normalize("NFKC", forms[-1])
        canonical = "".join(c for c in canonical if c.isprintable())
        decoded = unquote(canonical, errors="replace")
        if decoded == forms[-1]:
            break
        forms.append(decoded)
    for form in tuple(forms):
        normalized = unicodedata.normalize("NFKC", form)
        forms.append("".join(c for c in normalized if c.isprintable() or c.isspace()))
        forms.append("".join(c for c in normalized if c.isprintable()))
    return forms


def _looks_secret(text: str) -> bool:
    return len(text) > MAX_TEXT_LENGTH or any(
        r.search(form) for form in _secret_forms(text) for r in SECRET_VALUE_RES
    )


def _label(text: Any, limit: int = MAX_LABEL) -> str:
    """Make a caller-supplied name safe to put in a reason or a log line."""
    if type(text) is not str:
        return f"<{_label(type(text).__name__, limit)}>"
    if _looks_secret(text):
        return REDACTED
    shown = "".join(c if c.isprintable() else "?" for c in text[:limit])
    return shown if len(text) <= limit else f"{shown}...[{len(text)} chars]"


def _name_list(names: list[str]) -> str:
    shown = ", ".join(_label(n) for n in names[:MAX_NAMES_IN_REASON])
    extra = len(names) - MAX_NAMES_IN_REASON
    return f"{shown} and {extra} more" if extra > 0 else shown


def redact(value: Any, key: str = "", _depth: int = 0) -> Any:
    """Return a log-safe version of a value.

    Secret-looking keys and values become [REDACTED], long strings are cut,
    non-finite floats become strings so the log stays valid JSON, and anything
    that isn't plain data is logged as its type name only.
    """
    if key and (
        len(key) > MAX_TEXT_LENGTH
        or any(SECRET_KEY_RE.search(form) for form in _secret_forms(key))
    ):
        return REDACTED
    if type(value) is str:
        if _looks_secret(value):
            return REDACTED
        if len(value) > MAX_LOGGED_STR:
            return value[:MAX_LOGGED_STR] + f"...[{len(value)} chars]"
        return value
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        return value if math.isfinite(value) else str(value)
    if _depth < 4 and isinstance(value, Mapping):
        return {
            _label(k): redact(v, k if type(k) is str else "", _depth + 1)
            for k, v in value.items()
        }
    if _depth < 4 and type(value) in (list, tuple):
        return [redact(v, "", _depth + 1) for v in value]
    return f"<{_label(type(value).__name__)}>"


def _describe(value: Any) -> dict[str, Any]:
    """What gets logged for an argument whose value is not logged."""
    out: dict[str, Any] = {"type": _label(type(value).__name__, 40)}
    if type(value) is str:
        out["len"] = len(value)
    return out


class ToolGate:
    __slots__ = ("_policy", "_tools")

    def __init__(self, policy: Policy, tools: Mapping[str, Callable[..., Any]]):
        object.__setattr__(self, "_policy", policy)
        object.__setattr__(self, "_tools", MappingProxyType(dict(tools)))

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("ToolGate is read-only; build a new gate instead")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("ToolGate is read-only; build a new gate instead")

    def check(
        self, agent_id: str, tool: str, args: Mapping[str, Any] | None = None
    ) -> Decision:
        return self._decide(agent_id, tool, args)[0]

    def call(
        self, agent_id: str, tool: str, args: Mapping[str, Any] | None = None
    ) -> Any:
        decision, checked = self._decide(agent_id, tool, args)
        if not decision.allowed:
            raise PermissionDenied(
                f"{_label(agent_id)} -> {_label(tool)}: {decision.reason}"
            )
        # Run the tool on the exact copy that was checked, not the caller's object.
        return self._tools[tool](**checked)

    def for_agent(self, agent_id: str) -> AgentHandle:
        return AgentHandle(self, agent_id)

    def _decide(
        self, agent_id: Any, tool: Any, args: Any
    ) -> tuple[Decision, dict[str, Any]]:
        snapshot: dict[str, Any] | None = None
        try:
            decision, snapshot = self._evaluate(agent_id, tool, args)
        except Exception as e:  # noqa: BLE001
            # Fail closed: a bug or odd input in the checker must never turn into an allow.
            decision = Decision(
                False, f"policy check error: {_label(type(e).__name__)}"
            )
        self._audit(agent_id, tool, args, snapshot, decision)
        return decision, snapshot if decision.allowed else {}

    def _evaluate(
        self, agent_id: Any, tool: Any, args: Any
    ) -> tuple[Decision, dict[str, Any] | None]:
        if type(agent_id) is not str or type(tool) is not str:
            return Decision(False, "agent id and tool name must be strings"), None
        if args is None:
            args = {}
        if not isinstance(args, Mapping):
            return Decision(False, "arguments must be a mapping"), None
        # Read the caller's mapping once. Everything after this works on the
        # copy, so a mapping that answers differently on a second read can't
        # get a different value past the check.
        snapshot = dict(args)
        if any(type(k) is not str for k in snapshot):
            return Decision(False, "argument names must be strings"), snapshot
        odd = sorted(k for k, v in snapshot.items() if type(v) not in SCALAR_TYPES)
        if odd:
            return (
                Decision(False, f"unsupported argument types: {_name_list(odd)}"),
                snapshot,
            )
        if tool not in self._tools:
            return Decision(False, "tool not registered"), snapshot
        return self._policy.check(agent_id, tool, snapshot), snapshot

    def _audit(
        self,
        agent_id: Any,
        tool: Any,
        args: Any,
        snapshot: dict[str, Any] | None,
        decision: Decision,
    ) -> None:
        base = {
            "event": "tool_call",
            "decision": "allow" if decision.allowed else "deny",
            "reason": decision.reason,
        }
        try:
            record = dict(
                base,
                agent=_label(agent_id),
                role=_label(decision.role) if decision.role is not None else None,
                tool=_label(tool),
                args=(
                    self._loggable_args(decision.role, tool, snapshot)
                    if snapshot is not None
                    else f"<{_label(type(args).__name__)}>"
                ),
            )
            line = json.dumps(record, sort_keys=True, allow_nan=False)
        except Exception:  # noqa: BLE001
            # Whatever the input, a decision always leaves an audit line.
            line = json.dumps(dict(base, args="<unloggable>"), sort_keys=True)
        level = logging.INFO if decision.allowed else logging.WARNING
        audit_log.log(level, line)

    def _loggable_args(
        self, role: str | None, tool: Any, snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        specs: Mapping[str, Mapping[str, Any]] = {}
        if role is not None and type(tool) is str:
            specs = self._policy.roles.get(role, {}).get(tool, {})
        out: dict[str, Any] = {}
        names = sorted(snapshot, key=str)
        for name in names[:MAX_LOGGED_ARGS]:
            value = snapshot[name]
            spec = specs.get(name) if type(name) is str else None
            # A value is logged only when the policy asks for it and the value
            # passed that argument's own constraints, so whatever reaches the
            # log already has the shape the policy expects.
            if (
                spec is not None
                and spec.get("log_value")
                and type(value) in SCALAR_TYPES
                and _violation(value, spec) is None
            ):
                out[_label(name)] = redact(value, name)
            else:
                out[_label(name)] = _describe(value)
        if len(names) > MAX_LOGGED_ARGS:
            out["..."] = f"{len(names) - MAX_LOGGED_ARGS} more arguments not shown"
        return out


class AgentHandle:
    """What an agent actually gets. The agent id is fixed by the orchestrator.

    The handle doesn't keep the gate as an attribute, so an agent can't reach
    `for_agent` or the policy through it. This is a convenience boundary, not a
    sandbox; see the security notes in the README.
    """

    __slots__ = ("_agent_id", "_call")

    def __init__(self, gate: ToolGate, agent_id: str):
        def call(tool: str, args: dict[str, Any]) -> Any:
            return gate.call(agent_id, tool, args)

        object.__setattr__(self, "_agent_id", agent_id)
        object.__setattr__(self, "_call", call)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("AgentHandle is read-only")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("AgentHandle is read-only")

    @property
    def agent_id(self) -> str:
        return self._agent_id

    def call(self, tool: str, /, **args: Any) -> Any:
        return self._call(tool, args)
