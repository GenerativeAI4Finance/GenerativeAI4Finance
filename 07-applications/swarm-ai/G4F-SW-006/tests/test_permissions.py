import copy
import json
import logging
from pathlib import Path

import pytest

from permissions import (
    PermissionDenied,
    PolicyError,
    ToolGate,
    load_policy,
    parse_policy,
    redact,
)

POLICY_PATH = Path(__file__).resolve().parent.parent / "policy.json"


def fake_tools(calls, extra=()):
    def make(name):
        def tool(**kwargs):
            calls.append((name, kwargs))
            return f"{name} ok"

        return tool

    names = [
        "fetch_source",
        "list_sources",
        "read_evidence",
        "match_entities",
        "write_note",
        "set_review_status",
        # registered but granted to nobody in the policy
        "update_policy",
        "export_case_bundle",
        *extra,
    ]
    return {n: make(n) for n in names}


def one_tool_gate(calls, arg_specs, tool="t"):
    """A gate with one agent ('a-01'), one role and one tool."""
    policy = parse_policy(
        {
            "version": 1,
            "agents": {"a-01": "r"},
            "roles": {"r": {"tools": {tool: {"args": arg_specs}}}},
        }
    )
    return ToolGate(policy, fake_tools(calls, extra=[tool]))


@pytest.fixture
def raw_policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def calls():
    return []


@pytest.fixture
def gate(calls):
    return ToolGate(load_policy(POLICY_PATH), fake_tools(calls))


def strict_json(line):
    def reject(name):
        raise ValueError(f"{name} in audit line")

    return json.loads(line, parse_constant=reject)


def audit_records(caplog):
    return [
        strict_json(r.getMessage())
        for r in caplog.records
        if r.name == "g4f.permissions.audit"
    ]


@pytest.fixture
def audit(caplog):
    caplog.set_level(logging.INFO, logger="g4f.permissions.audit")
    return caplog


# allowed paths


def test_role_can_use_its_own_tool(gate, calls):
    assert (
        gate.call("collector-01", "fetch_source", {"source_id": "SYN-SRC-0001"})
        == "fetch_source ok"
    )
    assert calls == [("fetch_source", {"source_id": "SYN-SRC-0001"})]


def test_tool_with_no_args(gate):
    assert gate.call("collector-01", "list_sources") == "list_sources ok"


def test_shared_tool_allowed_for_each_granted_role(gate):
    for agent in ("matcher-01", "analyst-01", "reviewer-01"):
        d = gate.check(agent, "read_evidence", {"case_id": "SYN-CASE-0042"})
        assert d.allowed and d.reason == "allowed"


def test_agent_handle_calls_through_gate(gate, calls):
    handle = gate.for_agent("reviewer-01")
    handle.call(
        "set_review_status", case_id="SYN-CASE-0001", status="escalated_to_human"
    )
    assert calls == [
        (
            "set_review_status",
            {"case_id": "SYN-CASE-0001", "status": "escalated_to_human"},
        )
    ]


def test_agent_handle_passes_an_argument_named_tool(calls):
    gate = one_tool_gate(calls, {"tool": {"allowed": ["hammer"]}}, tool="use")
    gate.for_agent("a-01").call("use", tool="hammer")
    assert calls == [("use", {"tool": "hammer"})]


# default deny


def test_unknown_agent_denied(gate, calls):
    with pytest.raises(PermissionDenied, match="unknown agent"):
        gate.call("intruder-99", "list_sources")
    assert calls == []


def test_unknown_tool_denied(gate):
    d = gate.check("collector-01", "delete_everything")
    assert not d.allowed and d.reason == "tool not registered"


def test_registered_tool_not_in_any_role_denied(gate, calls):
    with pytest.raises(PermissionDenied, match="tool not granted"):
        gate.call("reviewer-01", "export_case_bundle")
    assert calls == []


def test_tool_name_match_is_exact(calls):
    # The near-miss names are registered with the gate, so the denial has to
    # come from the policy lookup, not from "tool not registered".
    names = ["Fetch_Source", "fetch_source ", "fetch_source\x00", "ｆetch_source", ""]
    gate = ToolGate(load_policy(POLICY_PATH), fake_tools(calls, extra=names))
    for name in names:
        d = gate.check("collector-01", name, {"source_id": "SYN-SRC-0001"})
        assert not d.allowed
        assert d.reason == "tool not granted to role"
    assert calls == []


def test_agent_id_match_is_exact(gate):
    for agent in ("Collector-01", "collector-01 ", "collector-0１"):
        d = gate.check(agent, "list_sources")
        assert not d.allowed and d.reason == "unknown agent"


def test_role_with_no_tools_gets_nothing(raw_policy, calls):
    raw_policy["roles"]["observer"] = {"tools": {}}
    raw_policy["agents"]["observer-01"] = "observer"
    gate = ToolGate(parse_policy(raw_policy), fake_tools(calls))
    assert (
        gate.check("observer-01", "list_sources").reason == "tool not granted to role"
    )


def test_policy_allows_but_tool_not_registered(calls):
    tools = fake_tools(calls)
    del tools["list_sources"]
    gate = ToolGate(load_policy(POLICY_PATH), tools)
    assert gate.check("collector-01", "list_sources").reason == "tool not registered"


# cross-role access and escalation attempts


@pytest.mark.parametrize(
    "agent,tool,args",
    [
        ("collector-01", "read_evidence", {"case_id": "SYN-CASE-0001"}),
        ("matcher-01", "fetch_source", {"source_id": "SYN-SRC-0001"}),
        (
            "analyst-01",
            "set_review_status",
            {"case_id": "SYN-CASE-0001", "status": "closed_no_finding"},
        ),
        (
            "reviewer-01",
            "write_note",
            {"case_id": "SYN-CASE-0001", "note": "looks fine"},
        ),
        (
            "collector-01",
            "match_entities",
            {"case_id": "SYN-CASE-0001", "threshold": 0.9},
        ),
    ],
)
def test_cross_role_access_denied(gate, calls, agent, tool, args):
    with pytest.raises(PermissionDenied, match="tool not granted"):
        gate.call(agent, tool, args)
    assert calls == []


def test_claiming_a_role_in_arguments_does_not_help(gate):
    d = gate.check(
        "analyst-01",
        "set_review_status",
        {"case_id": "SYN-CASE-0001", "status": "closed_no_finding", "role": "reviewer"},
    )
    assert not d.allowed
    assert d.reason == "tool not granted to role"
    assert d.role == "evidence_analyst"


def test_extra_arguments_rejected(gate):
    d = gate.check(
        "analyst-01",
        "read_evidence",
        {"case_id": "SYN-CASE-0001", "as_agent": "reviewer-01"},
    )
    assert not d.allowed and d.reason == "unexpected arguments: as_agent"


def test_missing_arguments_rejected(gate):
    d = gate.check("reviewer-01", "set_review_status", {"case_id": "SYN-CASE-0001"})
    assert not d.allowed and d.reason == "missing arguments: status"


def test_policy_tool_is_not_callable(gate, calls):
    for agent in ("collector-01", "matcher-01", "analyst-01", "reviewer-01"):
        with pytest.raises(PermissionDenied, match="tool not granted"):
            gate.call(
                agent, "update_policy", {"role": "reviewer", "add_tool": "write_note"}
            )
    assert calls == []


def test_policy_cannot_be_mutated_at_runtime(gate):
    policy = gate._policy
    with pytest.raises(TypeError):
        policy.agents["analyst-01"] = "reviewer"
    with pytest.raises(TypeError):
        policy.roles["evidence_analyst"]["set_review_status"] = {}
    with pytest.raises(TypeError):
        policy.roles["evidence_analyst"]["write_note"]["note"]["max_length"] = 10**9
    with pytest.raises(AttributeError):
        policy.agents = {}


def test_gate_attributes_cannot_be_reassigned(gate):
    other = parse_policy(
        {
            "version": 1,
            "agents": {"analyst-01": "god"},
            "roles": {"god": {"tools": {"set_review_status": {}}}},
        }
    )
    with pytest.raises(AttributeError):
        gate._policy = other
    with pytest.raises(AttributeError):
        gate._tools = {}
    with pytest.raises(AttributeError):
        del gate._policy
    assert gate.check("analyst-01", "set_review_status").reason == (
        "tool not granted to role"
    )


def test_editing_source_dict_after_load_has_no_effect(raw_policy, calls):
    policy = parse_policy(raw_policy)
    raw_policy["agents"]["analyst-01"] = "reviewer"
    raw_policy["roles"]["evidence_analyst"]["tools"]["set_review_status"] = {
        "args": {"case_id": {"pattern": ".*"}, "status": {"pattern": ".*"}}
    }
    raw_policy["roles"]["evidence_analyst"]["tools"]["write_note"]["args"]["note"][
        "max_length"
    ] = 10**9
    gate = ToolGate(policy, fake_tools(calls))
    args = {"case_id": "SYN-CASE-0001", "status": "closed_no_finding"}
    d = gate.check("analyst-01", "set_review_status", args)
    assert not d.allowed
    assert d.role == "evidence_analyst"
    assert d.reason == "tool not granted to role"
    note = {"case_id": "SYN-CASE-0001", "note": "x" * 2001}
    assert gate.check("analyst-01", "write_note", note).reason == (
        "argument 'note' exceeds max_length"
    )


def test_registering_tools_after_construction_has_no_effect(calls):
    tools = fake_tools(calls)
    gate = ToolGate(load_policy(POLICY_PATH), tools)
    tools["read_evidence"] = lambda **kw: "swapped"
    assert (
        gate.call("analyst-01", "read_evidence", {"case_id": "SYN-CASE-0001"})
        == "read_evidence ok"
    )


def test_agent_handle_is_read_only_and_does_not_expose_the_gate(gate, calls):
    # This covers the ordinary ways an agent might try to change who it is.
    # It is not a sandbox: see the security notes in the README.
    handle = gate.for_agent("analyst-01")
    with pytest.raises(AttributeError):
        handle._agent_id = "reviewer-01"
    with pytest.raises(AttributeError):
        handle.agent_id = "reviewer-01"
    with pytest.raises(AttributeError):
        del handle._agent_id
    assert not hasattr(handle, "_gate")
    assert not hasattr(handle, "for_agent")
    with pytest.raises(PermissionDenied, match="tool not granted"):
        handle.call(
            "set_review_status", case_id="SYN-CASE-0001", status="closed_no_finding"
        )
    assert calls == []


def test_overwriting_handle_slot_does_not_change_who_calls(gate, calls):
    handle = gate.for_agent("analyst-01")
    object.__setattr__(handle, "_agent_id", "reviewer-01")
    with pytest.raises(PermissionDenied, match="analyst-01 -> set_review_status"):
        handle.call(
            "set_review_status", case_id="SYN-CASE-0001", status="closed_no_finding"
        )
    assert calls == []


# argument-level constraints


@pytest.mark.parametrize(
    "source_id",
    [
        "SYN-SRC-01",
        "SYN-SRC-00011",
        "REAL-SRC-0001",
        "SYN-SRC-0001\n",
        "../SYN-SRC-0001",
        "SYN-SRC-٠٠٠١",
        1,
        None,
    ],
)
def test_pattern_is_full_match(gate, source_id):
    d = gate.check("collector-01", "fetch_source", {"source_id": source_id})
    assert not d.allowed and d.reason == "argument 'source_id' does not match pattern"


@pytest.mark.parametrize(
    "threshold,reason",
    [
        (0.49, "below min"),
        (1.01, "above max"),
        ("0.9", "is not a number"),
        (True, "is not a number"),
        (None, "is not a number"),
        (float("nan"), "is not a finite number"),
        (float("inf"), "is not a finite number"),
    ],
)
def test_numeric_bounds(gate, threshold, reason):
    d = gate.check(
        "matcher-01",
        "match_entities",
        {"case_id": "SYN-CASE-0001", "threshold": threshold},
    )
    assert not d.allowed and d.reason == f"argument 'threshold' {reason}"


def test_numeric_bounds_inclusive(gate):
    for t in (0.5, 1, 1.0):
        assert gate.check(
            "matcher-01", "match_entities", {"case_id": "SYN-CASE-0001", "threshold": t}
        ).allowed


def test_allowed_values(gate):
    ok = {"case_id": "SYN-CASE-0001", "status": "escalated_to_human"}
    assert gate.check("reviewer-01", "set_review_status", ok).allowed
    bad = dict(ok, status="approved_final")
    d = gate.check("reviewer-01", "set_review_status", bad)
    assert not d.allowed and d.reason == "argument 'status' not in allowed values"


def test_allowed_values_compare_types_exactly(calls):
    gate = one_tool_gate(calls, {"n": {"allowed": [1, "1", None]}})
    for ok in (1, "1", None):
        assert gate.check("a-01", "t", {"n": ok}).allowed
    for bad in (True, 1.0, "01"):
        assert not gate.check("a-01", "t", {"n": bad}).allowed


def test_max_length(gate):
    args = {"case_id": "SYN-CASE-0001", "note": "x" * 2001}
    d = gate.check("analyst-01", "write_note", args)
    assert not d.allowed and d.reason == "argument 'note' exceeds max_length"
    args["note"] = "x" * 2000
    assert gate.check("analyst-01", "write_note", args).allowed


# the value that is checked is the value the tool gets


def test_tool_receives_the_checked_copy_not_the_callers_mapping(gate, calls):
    class Shifty(dict):
        """Answers one value on the first read and another after that."""

        reads = 0

        def __getitem__(self, key):
            Shifty.reads += 1
            return "SYN-SRC-0001" if Shifty.reads == 1 else "../../secrets/prod.env"

    args = Shifty(source_id="SYN-SRC-0001")
    gate.call("collector-01", "fetch_source", args)
    assert calls == [("fetch_source", {"source_id": "SYN-SRC-0001"})]


@pytest.mark.parametrize(
    "value",
    [
        type("Sneaky", (str,), {"__eq__": lambda s, o: True, "__hash__": str.__hash__})(
            "approved_final"
        ),
        type("Fmt", (str,), {"__format__": lambda s, spec: "/data/../../etc/passwd"})(
            "SYN-CASE-0001"
        ),
        type("Num", (float,), {})(0.9),
        ["SYN-CASE-0001"],
        {"nested": "SYN-CASE-0001"},
        object(),
    ],
)
def test_subclasses_and_containers_are_rejected(gate, calls, value):
    d = gate.check(
        "reviewer-01",
        "set_review_status",
        {"case_id": "SYN-CASE-0001", "status": value},
    )
    assert not d.allowed and d.reason == "unsupported argument types: status"
    with pytest.raises(PermissionDenied):
        gate.call(
            "reviewer-01",
            "set_review_status",
            {"case_id": "SYN-CASE-0001", "status": value},
        )
    assert calls == []


def test_non_string_argument_names_rejected(gate):
    d = gate.check("collector-01", "fetch_source", {1: "SYN-SRC-0001"})
    assert not d.allowed and d.reason == "argument names must be strings"


# fail closed


def test_non_mapping_args_denied(gate, calls):
    with pytest.raises(PermissionDenied, match="must be a mapping"):
        gate.call("collector-01", "list_sources", ["not", "a", "dict"])
    assert calls == []


def test_checker_exception_denies(calls, audit):
    class BrokenPolicy:
        def check(self, agent_id, tool, args):
            raise RuntimeError("boom")

    gate = ToolGate(BrokenPolicy(), fake_tools(calls))
    with pytest.raises(PermissionDenied, match="policy check error: RuntimeError"):
        gate.call("collector-01", "list_sources")
    assert calls == []
    (rec,) = audit_records(audit)
    assert rec["decision"] == "deny"


def test_mapping_that_fails_to_copy_denies(gate, calls):
    class Broken(dict):
        def keys(self):
            raise RuntimeError("boom")

        def __iter__(self):
            raise RuntimeError("boom")

    with pytest.raises(PermissionDenied, match="policy check error"):
        gate.call("collector-01", "list_sources", Broken())
    assert calls == []


def test_unhashable_agent_id_denied(gate):
    d = gate.check(["collector-01"], "list_sources")
    assert not d.allowed and d.reason == "agent id and tool name must be strings"


# policy loading


def test_shipped_policy_loads():
    policy = load_policy(POLICY_PATH)
    assert set(policy.agents.values()) <= set(policy.roles)


def _args(p, role, tool):
    return p["roles"][role]["tools"][tool]["args"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(version=2),
        lambda p: p.update(version=True),
        lambda p: p.update(version=1.0),
        lambda p: p.pop("roles"),
        lambda p: p["agents"].update({"ghost-01": "admin"}),
        lambda p: p["agents"].update({"ghost-01": ["reviewer"]}),
        lambda p: p["roles"]["reviewer"].pop("tools"),
        lambda p: p["roles"]["reviewer"].update(inherits="evidence_analyst"),
        lambda p: p["roles"]["reviewer"]["tools"].update(read_evidence=["case_id"]),
        lambda p: p["roles"]["reviewer"]["tools"].update(read_evidence={"allow": True}),
        lambda p: p["roles"]["reviewer"]["tools"].update(read_evidence=None),
        lambda p: _args(p, "reviewer", "read_evidence").update(case_id={"regex": ".*"}),
        lambda p: _args(p, "reviewer", "read_evidence").update(case_id={}),
        lambda p: _args(p, "reviewer", "read_evidence").update(
            case_id={"log_value": True}
        ),
        lambda p: _args(p, "reviewer", "read_evidence").update(
            case_id={"pattern": ".*", "log_value": "yes"}
        ),
        lambda p: _args(p, "reviewer", "read_evidence").update(
            case_id={"pattern": "("}
        ),
        lambda p: _args(p, "reviewer", "read_evidence").update(case_id={"pattern": 5}),
        lambda p: _args(p, "entity_matcher", "match_entities").update(
            threshold={"min": "0"}
        ),
        lambda p: _args(p, "entity_matcher", "match_entities").update(
            threshold={"max": float("nan")}
        ),
        lambda p: _args(p, "entity_matcher", "match_entities").update(
            threshold={"min": float("-inf")}
        ),
        lambda p: _args(p, "entity_matcher", "match_entities").update(
            threshold={"min": True}
        ),
        lambda p: _args(p, "entity_matcher", "match_entities").update(
            threshold={"min": 1, "max": 0}
        ),
        lambda p: _args(p, "evidence_analyst", "write_note").update(
            note={"max_length": float("nan")}
        ),
        lambda p: _args(p, "evidence_analyst", "write_note").update(
            note={"max_length": -1}
        ),
        lambda p: _args(p, "evidence_analyst", "write_note").update(
            note={"max_length": 10.5}
        ),
        lambda p: _args(p, "reviewer", "set_review_status").update(
            status={"allowed": "x"}
        ),
        lambda p: _args(p, "reviewer", "set_review_status").update(
            status={"allowed": []}
        ),
        lambda p: _args(p, "reviewer", "set_review_status").update(
            status={"allowed": [["x"]]}
        ),
        lambda p: _args(p, "reviewer", "set_review_status").update(
            status={"allowed": [float("nan")]}
        ),
    ],
)
def test_bad_policy_rejected(raw_policy, mutate):
    p = copy.deepcopy(raw_policy)
    mutate(p)
    with pytest.raises(PolicyError):
        parse_policy(p)


def _policy_text(agents='{"a": "r"}', constraint='{"max": 1}'):
    return (
        f'{{"version": 1, "agents": {agents}, "roles": {{"r": {{"tools": '
        f'{{"t": {{"args": {{"x": {constraint}}}}}}}}}}}}}'
    )


@pytest.mark.parametrize(
    "text",
    [
        "{not json",
        "[]",
        '{"version": 1, "version": 1, "agents": {}, "roles": {}}',
        _policy_text(agents='{"a": "r", "a": "admin"}'),
        _policy_text(constraint='{"max": NaN}'),
        _policy_text(constraint='{"max_length": Infinity}'),
        _policy_text(constraint='{"min": -Infinity}'),
    ],
)
def test_bad_policy_file_rejected(tmp_path, text):
    path = tmp_path / "policy.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(path)


def test_policy_text_helper_is_valid_when_clean(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(_policy_text(), encoding="utf-8")
    assert load_policy(path).roles["r"]["t"]["x"]["max"] == 1


def test_missing_policy_file_rejected(tmp_path):
    with pytest.raises(PolicyError, match="cannot read policy file"):
        load_policy(tmp_path / "nope.json")


# audit log


def test_denials_are_logged(gate, audit):
    with pytest.raises(PermissionDenied):
        gate.call(
            "analyst-01",
            "set_review_status",
            {"case_id": "SYN-CASE-0001", "status": "closed_no_finding"},
        )
    (rec,) = audit_records(audit)
    assert rec["decision"] == "deny"
    assert rec["agent"] == "analyst-01"
    assert rec["role"] == "evidence_analyst"
    assert rec["tool"] == "set_review_status"
    assert rec["reason"] == "tool not granted to role"
    assert audit.records[0].levelno == logging.WARNING


def test_allows_are_logged(gate, audit):
    gate.call("collector-01", "list_sources")
    (rec,) = audit_records(audit)
    assert rec["decision"] == "allow"
    assert rec["args"] == {}
    assert audit.records[0].levelno == logging.INFO


def test_argument_values_are_not_logged_by_default(gate, audit):
    note = "Director has a second passport, see attachment."
    gate.call("analyst-01", "write_note", {"case_id": "SYN-CASE-0001", "note": note})
    (rec,) = audit_records(audit)
    assert note not in audit.text
    assert rec["args"]["note"] == {"type": "str", "len": len(note)}
    # case_id opts in to value logging in policy.json
    assert rec["args"]["case_id"] == "SYN-CASE-0001"


def test_opted_in_value_is_logged_only_when_it_passes_its_constraint(gate, audit):
    leaked = "sk_live_0000000000000000000000"
    gate.check("analyst-01", "read_evidence", {"case_id": leaked})
    (rec,) = audit_records(audit)
    assert leaked not in audit.text
    assert rec["args"]["case_id"] == {"type": "str", "len": len(leaked)}


def test_unexpected_argument_values_are_never_logged(gate, audit):
    args = {
        "case_id": "SYN-CASE-0001",
        "api_key": "plain-looking-value-1",
        "pwd": "plain-looking-value-2",
        "dsn": "postgres://user:hunter2@db/prod",
    }
    gate.check("analyst-01", "read_evidence", args)
    assert "plain-looking-value" not in audit.text
    assert "hunter2" not in audit.text
    (rec,) = audit_records(audit)
    assert rec["args"]["api_key"] == {"type": "str", "len": 21}


SECRETS = [
    "Bearer abc.def.ghi",
    "Basic dXNlcjpodW50ZXIy",
    "sk-test0000000000000000000000",
    "sk_live_00000000000000000000",
    "rk_test_00000000000000000000",
    "AKIAEXAMPLE000000000",
    "ghp_exampleexampleexampleexample00",
    "github_pat_11AAAAAAA0000000000000000000",
    "xoxb-0000000000-0000000000000",
    "AIzaSyA0000000000000000000000000000000",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl",
    "-----BEGIN RSA PRIVATE KEY-----\nMIIEfake\n-----END RSA PRIVATE KEY-----",
    "https://user:hunter2@example.test/path",
    "https://example.test/feed?api_key=abc123",
]


@pytest.mark.parametrize("secret", SECRETS)
def test_secret_values_redacted_even_when_value_logging_is_on(calls, audit, secret):
    gate = one_tool_gate(calls, {"text": {"pattern": "(?s).*", "log_value": True}})
    gate.call("a-01", "t", {"text": secret})
    (rec,) = audit_records(audit)
    assert secret not in audit.text
    assert rec["args"]["text"] == "[REDACTED]"


@pytest.mark.parametrize("key", ["api_key", "pwd", "access_key", "jwt", "dsn", "auth"])
def test_secret_keys_redacted(key):
    assert redact({key: "plain-looking-value"}) == {key: "[REDACTED]"}


def test_denial_reason_never_echoes_value(gate):
    d = gate.check(
        "collector-01", "fetch_source", {"source_id": "sk-test0000000000000000000000"}
    )
    assert "sk-" not in d.reason


def test_caller_supplied_names_are_cleaned_in_reason_and_log(gate, audit):
    long_name = "x" * 5000
    secret_name = "sk_live_00000000000000000000"
    d = gate.check(
        "analyst-01",
        "read_evidence",
        {"case_id": "SYN-CASE-0001", long_name: 1, secret_name: 2},
    )
    assert not d.allowed
    assert len(d.reason) < 300
    assert secret_name not in d.reason
    assert secret_name not in audit.text
    assert long_name not in audit.text


def test_reason_lists_a_bounded_number_of_names(gate):
    args = {"case_id": "SYN-CASE-0001", **{f"extra{i:02}": i for i in range(30)}}
    d = gate.check("analyst-01", "read_evidence", args)
    assert d.reason.endswith("and 25 more")


def test_tool_name_with_newlines_is_cleaned(gate, audit):
    tool = "list_sources\nINFO forged audit line"
    with pytest.raises(PermissionDenied) as exc:
        gate.call("collector-01", tool)
    assert "\n" not in str(exc.value)
    assert all("\n" not in r.getMessage() for r in audit.records)


def test_audit_line_written_for_self_referencing_tool_name(gate, audit):
    tool = []
    tool.append(tool)
    assert not gate.check("collector-01", tool).allowed
    (rec,) = audit_records(audit)
    assert rec["decision"] == "deny"


def test_nan_argument_keeps_audit_line_valid_json(calls, audit):
    gate = one_tool_gate(calls, {"x": {"allowed": [1.0], "log_value": True}})
    assert not gate.check("a-01", "t", {"x": float("nan")}).allowed
    (rec,) = audit_records(audit)
    assert rec["args"]["x"] == {"type": "float"}


def test_many_arguments_are_summarised_in_log(gate, audit):
    args = {f"a{i:03}": i for i in range(100)}
    gate.check("analyst-01", "read_evidence", args)
    (rec,) = audit_records(audit)
    assert len(rec["args"]) == 21
    assert rec["args"]["..."] == "80 more arguments not shown"


def test_redact_truncates_and_does_not_dump_objects():
    out = redact({"note": "a" * 5000, "obj": object()})
    assert len(out["note"]) < 300
    assert out["obj"] == "<object>"


def test_redact_handles_cycles_and_non_finite_floats():
    loop = []
    loop.append(loop)
    json.dumps(redact({"loop": loop, "x": float("inf")}), allow_nan=False)
