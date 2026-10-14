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


def fake_tools(calls):
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
    ]
    return {n: make(n) for n in names}


@pytest.fixture
def raw_policy():
    return json.loads(POLICY_PATH.read_text())


@pytest.fixture
def calls():
    return []


@pytest.fixture
def gate(calls):
    return ToolGate(load_policy(POLICY_PATH), fake_tools(calls))


def audit_records(caplog):
    return [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.name == "g4f.permissions.audit"
    ]


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
        assert gate.check(agent, "read_evidence", {"case_id": "SYN-CASE-0042"}).allowed


def test_agent_handle_calls_through_gate(gate, calls):
    handle = gate.for_agent("reviewer-01")
    handle.call(
        "set_review_status", case_id="SYN-CASE-0001", status="escalated_to_human"
    )
    assert calls[-1][0] == "set_review_status"


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


def test_tool_name_match_is_exact(gate):
    for name in ("Fetch_Source", "fetch_source ", "fetch_source\x00", ""):
        assert not gate.check(
            "collector-01", name, {"source_id": "SYN-SRC-0001"}
        ).allowed


def test_role_with_no_tools_gets_nothing(raw_policy, calls):
    raw_policy["roles"]["observer"] = {"tools": {}}
    raw_policy["agents"]["observer-01"] = "observer"
    gate = ToolGate(parse_policy(raw_policy), fake_tools(calls))
    assert not gate.check("observer-01", "list_sources").allowed


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
    assert d.role == "evidence_analyst"


def test_extra_arguments_rejected(gate):
    d = gate.check(
        "analyst-01",
        "read_evidence",
        {"case_id": "SYN-CASE-0001", "as_agent": "reviewer-01"},
    )
    assert not d.allowed and "unexpected arguments" in d.reason


def test_missing_arguments_rejected(gate):
    d = gate.check("reviewer-01", "set_review_status", {"case_id": "SYN-CASE-0001"})
    assert not d.allowed and "missing arguments: status" in d.reason


def test_policy_tool_is_not_callable(gate, calls):
    for agent in ("collector-01", "matcher-01", "analyst-01", "reviewer-01"):
        with pytest.raises(PermissionDenied):
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


def test_editing_source_dict_after_load_has_no_effect(raw_policy, calls):
    policy = parse_policy(raw_policy)
    raw_policy["agents"]["analyst-01"] = "reviewer"
    raw_policy["roles"]["evidence_analyst"]["tools"]["set_review_status"] = {}
    gate = ToolGate(policy, fake_tools(calls))
    assert not gate.check("analyst-01", "set_review_status", {}).allowed


def test_registering_tools_after_construction_has_no_effect(calls):
    tools = fake_tools(calls)
    gate = ToolGate(load_policy(POLICY_PATH), tools)
    tools["read_evidence"] = lambda **kw: "swapped"
    assert (
        gate.call("analyst-01", "read_evidence", {"case_id": "SYN-CASE-0001"})
        == "read_evidence ok"
    )


def test_agent_handle_cannot_change_identity(gate):
    handle = gate.for_agent("analyst-01")
    with pytest.raises(AttributeError):
        handle._agent_id = "reviewer-01"
    with pytest.raises(AttributeError):
        handle.agent_id = "reviewer-01"
    with pytest.raises(PermissionDenied):
        handle.call(
            "set_review_status", case_id="SYN-CASE-0001", status="closed_no_finding"
        )


# argument-level constraints


@pytest.mark.parametrize(
    "source_id",
    [
        "SYN-SRC-01",
        "SYN-SRC-00011",
        "REAL-SRC-0001",
        "SYN-SRC-0001\n",
        "../SYN-SRC-0001",
        1,
        None,
    ],
)
def test_pattern_is_full_match(gate, source_id):
    d = gate.check("collector-01", "fetch_source", {"source_id": source_id})
    assert not d.allowed and "does not match pattern" in d.reason


@pytest.mark.parametrize(
    "threshold", [0.49, 1.01, "0.9", True, float("nan"), float("inf"), None]
)
def test_numeric_bounds(gate, threshold):
    assert not gate.check(
        "matcher-01",
        "match_entities",
        {"case_id": "SYN-CASE-0001", "threshold": threshold},
    ).allowed


def test_numeric_bounds_inclusive(gate):
    for t in (0.5, 1, 1.0):
        assert gate.check(
            "matcher-01", "match_entities", {"case_id": "SYN-CASE-0001", "threshold": t}
        ).allowed


def test_allowed_values(gate):
    ok = {"case_id": "SYN-CASE-0001", "status": "escalated_to_human"}
    assert gate.check("reviewer-01", "set_review_status", ok).allowed
    bad = dict(ok, status="approved_final")
    assert not gate.check("reviewer-01", "set_review_status", bad).allowed


def test_max_length(gate):
    args = {"case_id": "SYN-CASE-0001", "note": "x" * 2001}
    assert not gate.check("analyst-01", "write_note", args).allowed
    args["note"] = "x" * 2000
    assert gate.check("analyst-01", "write_note", args).allowed


# fail closed


def test_non_mapping_args_denied(gate, calls):
    with pytest.raises(PermissionDenied, match="must be a mapping"):
        gate.call("collector-01", "list_sources", ["not", "a", "dict"])
    assert calls == []


def test_checker_exception_denies(gate, calls):
    class Weird:
        def __eq__(self, other):
            raise RuntimeError("boom")

        __hash__ = object.__hash__

    with pytest.raises(PermissionDenied, match="policy check error"):
        gate.call(
            "reviewer-01",
            "set_review_status",
            {"case_id": "SYN-CASE-0001", "status": Weird()},
        )
    assert calls == []


def test_unhashable_agent_id_denied(gate):
    assert not gate.check(["collector-01"], "list_sources").allowed


# policy loading


def test_shipped_policy_loads():
    policy = load_policy(POLICY_PATH)
    assert set(policy.agents.values()) <= set(policy.roles)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(version=2),
        lambda p: p.pop("roles"),
        lambda p: p["agents"].update({"ghost-01": "admin"}),
        lambda p: p["roles"]["reviewer"].pop("tools"),
        lambda p: p["roles"]["reviewer"]["tools"].update(read_evidence=["case_id"]),
        lambda p: p["roles"]["reviewer"]["tools"].update(read_evidence={"allow": True}),
        lambda p: p["roles"]["reviewer"]["tools"]["read_evidence"]["args"].update(
            case_id={"regex": ".*"}
        ),
        lambda p: p["roles"]["reviewer"]["tools"]["read_evidence"]["args"].update(
            case_id={}
        ),
        lambda p: p["roles"]["reviewer"]["tools"]["read_evidence"]["args"].update(
            case_id={"pattern": "("}
        ),
        lambda p: p["roles"]["entity_matcher"]["tools"]["match_entities"][
            "args"
        ].update(threshold={"min": "0"}),
        lambda p: p["roles"]["reviewer"]["tools"]["set_review_status"]["args"].update(
            status={"allowed": "x"}
        ),
    ],
)
def test_bad_policy_rejected(raw_policy, mutate):
    p = copy.deepcopy(raw_policy)
    mutate(p)
    with pytest.raises(PolicyError):
        parse_policy(p)


# audit log


def test_denials_are_logged(gate, caplog):
    caplog.set_level(logging.INFO, logger="g4f.permissions.audit")
    with pytest.raises(PermissionDenied):
        gate.call(
            "analyst-01",
            "set_review_status",
            {"case_id": "SYN-CASE-0001", "status": "closed_no_finding"},
        )
    (rec,) = audit_records(caplog)
    assert rec["decision"] == "deny"
    assert rec["agent"] == "analyst-01"
    assert rec["role"] == "evidence_analyst"
    assert rec["tool"] == "set_review_status"
    assert rec["reason"] == "tool not granted to role"
    assert caplog.records[0].levelno == logging.WARNING


def test_allows_are_logged(gate, caplog):
    caplog.set_level(logging.INFO, logger="g4f.permissions.audit")
    gate.call("collector-01", "list_sources")
    (rec,) = audit_records(caplog)
    assert rec["decision"] == "allow"


SECRETS = [
    "Bearer abc.def.ghi",
    "sk-test0000000000000000000000",
    "AKIAEXAMPLE000000000",
    "ghp_exampleexampleexampleexample00",
    "-----BEGIN RSA PRIVATE KEY-----\nMIIEfake\n-----END RSA PRIVATE KEY-----",
]


@pytest.mark.parametrize("secret", SECRETS)
def test_secret_values_redacted_in_log(gate, caplog, secret):
    caplog.set_level(logging.INFO, logger="g4f.permissions.audit")
    with pytest.raises(PermissionDenied):
        gate.call(
            "analyst-01",
            "write_note",
            {"case_id": "SYN-CASE-0001", "note": secret, "extra": 1},
        )
    text = caplog.text
    assert secret not in text
    assert "[REDACTED]" in text


def test_secret_keys_redacted_in_log(gate, caplog):
    caplog.set_level(logging.INFO, logger="g4f.permissions.audit")
    args = {
        "case_id": "SYN-CASE-0001",
        "api_key": "plain-looking-value-1",
        "headers": {"Authorization": "plain-looking-value-2"},
        "db_password": "plain-looking-value-3",
    }
    gate.check("analyst-01", "read_evidence", args)
    assert "plain-looking-value" not in caplog.text
    (rec,) = audit_records(caplog)
    assert rec["args"]["case_id"] == "SYN-CASE-0001"
    assert rec["args"]["headers"]["Authorization"] == "[REDACTED]"


def test_denial_reason_never_echoes_value(gate):
    d = gate.check(
        "collector-01", "fetch_source", {"source_id": "sk-test0000000000000000000000"}
    )
    assert "sk-" not in d.reason


def test_long_values_truncated_and_objects_not_dumped():
    out = redact({"note": "a" * 5000, "obj": object()})
    assert len(out["note"]) < 300
    assert out["obj"] == "<object>"
