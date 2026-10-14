"""Role-based tool permissions for simulated swarm agents.

Every tool call goes through ToolGate. Anything the policy does not explicitly
allow is denied, and every decision is written to the audit log with
secret-looking arguments redacted.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

audit_log = logging.getLogger("g4f.permissions.audit")

CONSTRAINT_KEYS = {"pattern", "allowed", "min", "max", "max_length"}

SECRET_KEY_RE = re.compile(
    r"secret|token|passw|api[_-]?key|auth|credential|private[_-]?key|cookie|session",
    re.IGNORECASE,
)
SECRET_VALUE_RES = [
    re.compile(r"bearer\s+\S+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
REDACTED = "[REDACTED]"
MAX_LOGGED_STR = 200


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
    # role -> tool -> arg name -> constraint
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
            return Decision(
                False, f"unexpected arguments: {', '.join(unexpected)}", role
            )
        missing = sorted(set(spec) - set(args))
        if missing:
            return Decision(False, f"missing arguments: {', '.join(missing)}", role)

        for name, constraint in spec.items():
            problem = _violation(args[name], constraint)
            if problem:
                # Only the arg name goes in the reason, never the value.
                return Decision(False, f"argument '{name}' {problem}", role)
        return Decision(True, "allowed", role)


def _violation(value: Any, c: Mapping[str, Any]) -> str | None:
    if "allowed" in c and value not in c["allowed"]:
        return "not in allowed values"
    if "pattern" in c and (
        not isinstance(value, str) or not c["pattern"].fullmatch(value)
    ):
        return "does not match pattern"
    if "max_length" in c and (
        not isinstance(value, str) or len(value) > c["max_length"]
    ):
        return "exceeds max_length"
    if "min" in c or "max" in c:
        # bool is an int subclass; True should not pass as 1.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "is not a number"
        if not math.isfinite(value):
            return "is not a finite number"
        if "min" in c and value < c["min"]:
            return "below min"
        if "max" in c and value > c["max"]:
            return "above max"
    return None


def load_policy(path: str | Path) -> Policy:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return parse_policy(raw)


def parse_policy(raw: Any) -> Policy:
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise PolicyError("policy must be an object with version 1")
    agents, roles = raw.get("agents"), raw.get("roles")
    if not isinstance(agents, dict) or not isinstance(roles, dict):
        raise PolicyError("policy needs 'agents' and 'roles' objects")

    frozen_roles = {}
    for role, body in roles.items():
        if not isinstance(body, dict) or not isinstance(body.get("tools"), dict):
            raise PolicyError(f"role '{role}' needs a 'tools' object")
        tools = {}
        for tool, tool_spec in body["tools"].items():
            tool_spec = {} if tool_spec is None else tool_spec
            if not isinstance(tool_spec, dict) or set(tool_spec) - {"args"}:
                raise PolicyError(
                    f"{role}.{tool}: tool spec must be an object with only 'args'"
                )
            arg_specs = tool_spec.get("args", {})
            if not isinstance(arg_specs, dict):
                raise PolicyError(f"{role}.{tool}: 'args' must be an object")
            tools[tool] = MappingProxyType(
                {
                    name: _parse_constraint(f"{role}.{tool}.{name}", c)
                    for name, c in arg_specs.items()
                }
            )
        frozen_roles[role] = MappingProxyType(tools)

    for agent, role in agents.items():
        if role not in frozen_roles:
            raise PolicyError(f"agent '{agent}' refers to undefined role '{role}'")

    return Policy(
        agents=MappingProxyType(dict(agents)), roles=MappingProxyType(frozen_roles)
    )


def _parse_constraint(where: str, c: Any) -> Mapping[str, Any]:
    if not isinstance(c, dict) or not c:
        raise PolicyError(f"{where}: constraint must be a non-empty object")
    unknown = set(c) - CONSTRAINT_KEYS
    if unknown:
        # An unrecognised constraint would otherwise be silently ignored,
        # which would make the policy looser than its author intended.
        raise PolicyError(f"{where}: unknown constraint keys {sorted(unknown)}")
    out = dict(c)
    if "pattern" in out:
        try:
            out["pattern"] = re.compile(out["pattern"])
        except (re.error, TypeError) as e:
            raise PolicyError(f"{where}: bad pattern ({e})") from None
    if "allowed" in out:
        if not isinstance(out["allowed"], list):
            raise PolicyError(f"{where}: 'allowed' must be a list")
        out["allowed"] = tuple(out["allowed"])
    for key in ("min", "max", "max_length"):
        if key in out and (
            isinstance(out[key], bool) or not isinstance(out[key], (int, float))
        ):
            raise PolicyError(f"{where}: '{key}' must be a number")
    return MappingProxyType(out)


def redact(value: Any, key: str = "") -> Any:
    if key and SECRET_KEY_RE.search(key):
        return REDACTED
    if isinstance(value, str):
        if any(r.search(value) for r in SECRET_VALUE_RES):
            return REDACTED
        if len(value) > MAX_LOGGED_STR:
            return value[:MAX_LOGGED_STR] + f"...[{len(value)} chars]"
        return value
    if isinstance(value, Mapping):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return f"<{type(value).__name__}>"


class ToolGate:
    def __init__(self, policy: Policy, tools: Mapping[str, Callable[..., Any]]):
        self._policy = policy
        self._tools = MappingProxyType(dict(tools))

    def check(
        self, agent_id: str, tool: str, args: Mapping[str, Any] | None = None
    ) -> Decision:
        args = {} if args is None else args
        try:
            if not isinstance(args, Mapping):
                decision = Decision(False, "arguments must be a mapping")
            elif tool not in self._tools:
                decision = Decision(False, "tool not registered")
            else:
                decision = self._policy.check(agent_id, tool, args)
        except Exception as e:  # noqa: BLE001
            # Fail closed: a bug or odd input in the checker must never turn into an allow.
            decision = Decision(False, f"policy check error: {type(e).__name__}")
        self._audit(agent_id, tool, args, decision)
        return decision

    def call(
        self, agent_id: str, tool: str, args: Mapping[str, Any] | None = None
    ) -> Any:
        decision = self.check(agent_id, tool, args)
        if not decision.allowed:
            raise PermissionDenied(f"{agent_id} -> {tool}: {decision.reason}")
        return self._tools[tool](**(args or {}))

    def for_agent(self, agent_id: str) -> AgentHandle:
        return AgentHandle(self, agent_id)

    def _audit(self, agent_id: str, tool: str, args: Any, decision: Decision) -> None:
        try:
            logged_args = (
                redact(args)
                if isinstance(args, Mapping)
                else f"<{type(args).__name__}>"
            )
        except Exception:  # noqa: BLE001
            logged_args = "<unloggable>"
        record = {
            "event": "tool_call",
            "decision": "allow" if decision.allowed else "deny",
            "agent": redact(agent_id),
            "role": decision.role,
            "tool": redact(tool),
            "reason": decision.reason,
            "args": logged_args,
        }
        level = logging.INFO if decision.allowed else logging.WARNING
        audit_log.log(level, json.dumps(record, sort_keys=True, default=str))


class AgentHandle:
    """What an agent actually gets. The agent id is fixed by the orchestrator."""

    __slots__ = ("_agent_id", "_gate")

    def __init__(self, gate: ToolGate, agent_id: str):
        object.__setattr__(self, "_gate", gate)
        object.__setattr__(self, "_agent_id", agent_id)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("AgentHandle is read-only")

    @property
    def agent_id(self) -> str:
        return self._agent_id

    def call(self, tool: str, **args: Any) -> Any:
        return self._gate.call(self._agent_id, tool, args)
