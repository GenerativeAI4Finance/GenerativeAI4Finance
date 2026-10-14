import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import make_example
from audit_trail import (
    SENSITIVE_FIELDS,
    Actor,
    AuditError,
    AuditLog,
    IntegrityError,
    main,
    matches_redacted,
    read_events,
    verify_events,
)

KEY = b"test-key"
ANALYST = Actor("analyst-1", "analyst")
ANALYST_2 = Actor("analyst-2", "analyst")
REVIEWER = Actor("reviewer-1", "reviewer")
SENIOR = Actor("senior-1", "senior_reviewer")


def ticking_clock():
    n = iter(range(10_000))
    return lambda: f"2026-01-01T00:{next(n):02d}:00+00:00"


@pytest.fixture
def log(tmp_path):
    return AuditLog(tmp_path / "audit.jsonl", KEY, clock=ticking_clock())


@pytest.fixture
def example(tmp_path):
    return make_example.build(tmp_path / "example.jsonl")


def new_finding(log, fid="F-1", actor=ANALYST):
    return log.create(
        fid,
        actor,
        {
            "title": "Registry gap",
            "confidence": "low",
            "subject_name": "Fictional Co Ltd",
        },
        refs=["evidence:EV-1"],
    )


def write_lines(path, events):
    path.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events))


# replay and reconstruction


def test_full_lifecycle_replays_to_closed(log):
    new_finding(log)
    log.edit("F-1", ANALYST, {"confidence": "medium"}, reason="second source")
    log.submit("F-1", ANALYST)
    log.approve("F-1", REVIEWER, reason="sourced")
    log.close("F-1", REVIEWER, reason="done")

    reopened = AuditLog(log.path, KEY)
    state = reopened.state("F-1")
    assert state["status"] == "closed"
    assert state["fields"]["confidence"] == "medium"
    assert state == log.state("F-1")


def test_state_at_earlier_seq(log):
    new_finding(log)
    log.edit("F-1", ANALYST, {"confidence": "medium"}, reason="r")
    log.edit("F-1", ANALYST, {"confidence": "high"}, reason="r")

    assert log.state("F-1", upto_seq=1)["fields"]["confidence"] == "low"
    assert log.state("F-1", upto_seq=2)["fields"]["confidence"] == "medium"
    assert log.state("F-1")["fields"]["confidence"] == "high"


def test_state_as_of_timestamp(example):
    before_review = example.state("F-002", as_of="2026-03-03T09:00:00+00:00")
    assert before_review["status"] == "under_review"
    assert before_review["fields"]["summary"].startswith("Trade publication")

    after_reject = example.state("F-002", as_of="2026-03-04T00:00:00+00:00")
    assert after_reject["status"] == "rejected"

    assert example.state("F-001", as_of="2026-03-01T00:00:00+00:00") is None
    assert example.state("F-002")["status"] == "closed"


def test_edit_records_only_changed_fields(log):
    new_finding(log)
    event = log.edit(
        "F-1", ANALYST, {"title": "Registry gap", "confidence": "high"}, reason="r"
    )
    assert event["changes"] == {"confidence": {"from": "low", "to": "high"}}
    assert event["previous_event_seq"] == 1


def test_noop_edit_is_rejected(log):
    new_finding(log)
    with pytest.raises(AuditError, match="does not change"):
        log.edit("F-1", ANALYST, {"confidence": "low"}, reason="r")


def test_unknown_field_is_rejected(log):
    with pytest.raises(AuditError, match="unknown fields"):
        log.create("F-1", ANALYST, {"passport_number": "X"})


# state machine


@pytest.mark.parametrize(
    "action",
    [
        lambda log: log.approve("F-1", REVIEWER, reason="r"),
        lambda log: log.close("F-1", REVIEWER, reason="r"),
        lambda log: log.escalate("F-1", REVIEWER, reason="r"),
    ],
)
def test_draft_cannot_skip_review(log, action):
    new_finding(log)
    with pytest.raises(AuditError, match="cannot apply"):
        action(log)


def test_closed_finding_is_final(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    log.reject("F-1", REVIEWER, reason="weak source")
    log.close("F-1", REVIEWER, reason="dropped")
    with pytest.raises(AuditError, match="cannot apply"):
        log.edit("F-1", ANALYST, {"confidence": "high"}, reason="r")


def test_cannot_edit_under_review(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    with pytest.raises(AuditError, match="cannot apply"):
        log.edit("F-1", ANALYST, {"confidence": "high"}, reason="r")


def test_rejected_finding_goes_back_to_draft_on_edit(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    log.reject("F-1", REVIEWER, reason="stale")
    event = log.edit("F-1", ANALYST, {"confidence": "medium"}, reason="fixed")
    assert event["status_after"] == "draft"


def test_cannot_create_twice(log):
    new_finding(log)
    with pytest.raises(AuditError, match="cannot apply"):
        new_finding(log)


def test_failed_action_writes_nothing(log):
    new_finding(log)
    size = log.path.stat().st_size
    with pytest.raises(AuditError):
        log.approve("F-1", REVIEWER, reason="r")
    assert log.path.stat().st_size == size
    assert len(log.events) == 1


# roles and separation of duties


def test_analyst_cannot_approve(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    with pytest.raises(AuditError, match="role 'analyst'"):
        log.approve("F-1", ANALYST_2, reason="r")


def test_reviewer_cannot_create_or_edit(log):
    with pytest.raises(AuditError, match="role 'reviewer'"):
        new_finding(log, actor=REVIEWER)


def test_author_cannot_review_own_finding(log):
    # same person holding a reviewer role still cannot decide on work they wrote
    new_finding(log)
    log.submit("F-1", ANALYST)
    same_person = Actor("analyst-1", "reviewer")
    with pytest.raises(AuditError, match="cannot review"):
        log.approve("F-1", same_person, reason="r")


def test_editor_cannot_review(log):
    new_finding(log)
    log.edit("F-1", ANALYST_2, {"confidence": "high"}, reason="r")
    log.submit("F-1", ANALYST)
    with pytest.raises(AuditError, match="cannot review"):
        log.reject("F-1", Actor("analyst-2", "senior_reviewer"), reason="r")


def test_escalated_needs_senior_reviewer(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    log.escalate("F-1", REVIEWER, reason="needs a second view")
    with pytest.raises(AuditError, match="senior_reviewer"):
        log.approve("F-1", Actor("reviewer-9", "reviewer"), reason="r")
    assert log.approve("F-1", SENIOR, reason="ok")["status_after"] == "approved"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_escalation_requires_reason(log, reason):
    new_finding(log)
    log.submit("F-1", ANALYST)
    with pytest.raises(AuditError, match="requires a reason"):
        log.escalate("F-1", REVIEWER, reason=reason)


def test_unknown_role_rejected():
    with pytest.raises(AuditError, match="unknown role"):
        Actor("x", "admin")


def test_timestamps_cannot_go_backwards(tmp_path):
    times = iter(["2026-01-02T00:00:00+00:00", "2026-01-01T00:00:00+00:00"])
    log = AuditLog(tmp_path / "a.jsonl", KEY, clock=lambda: next(times))
    new_finding(log)
    with pytest.raises(AuditError, match="earlier"):
        log.submit("F-1", ANALYST)


# tamper detection


def test_example_log_verifies(example):
    assert verify_events(read_events(example.path)) == example.head


def test_edited_line_is_detected(example):
    events = read_events(example.path)
    events[5]["reason"] = "looks fine"
    write_lines(example.path, events)
    with pytest.raises(IntegrityError, match="line 6: content"):
        AuditLog(example.path, KEY)


def test_edited_line_with_recomputed_hash_breaks_next_link(example):
    from audit_trail import event_hash

    events = read_events(example.path)
    events[5]["actor_role"] = "senior_reviewer"
    events[5]["hash"] = event_hash(events[5])
    write_lines(example.path, events)
    with pytest.raises(IntegrityError, match="line 7: prev_hash"):
        verify_events(read_events(example.path))


def test_removed_line_is_detected(example):
    events = read_events(example.path)
    del events[3]
    write_lines(example.path, events)
    with pytest.raises(IntegrityError, match="line 4"):
        verify_events(read_events(example.path))


def test_reordered_lines_are_detected(example):
    events = read_events(example.path)
    events[4], events[5] = events[5], events[4]
    write_lines(example.path, events)
    with pytest.raises(IntegrityError, match="line 5"):
        verify_events(read_events(example.path))


def test_truncated_tail_needs_external_head(example):
    events = read_events(example.path)[:-1]
    # the chain alone still looks fine after dropping the last line
    verify_events(events)
    with pytest.raises(IntegrityError, match="head hash"):
        verify_events(events, expected_head=example.head)


def test_garbage_line_is_detected(example):
    with example.path.open("a") as fh:
        fh.write("{not json\n")
    with pytest.raises(IntegrityError, match="not valid JSON"):
        read_events(example.path)


# redaction


def test_sensitive_values_never_hit_disk(log):
    new_finding(log)
    log.edit(
        "F-1",
        ANALYST,
        {"analyst_notes": "Spoke to Jane Example on 555-0100"},
        reason="r",
    )
    raw = log.path.read_text()
    assert "Fictional Co Ltd" not in raw
    assert "Jane Example" not in raw
    assert "555-0100" not in raw


def test_redacted_values_can_be_checked_with_key(log):
    new_finding(log)
    stored = log.state("F-1")["fields"]["subject_name"]
    assert stored["redacted"] is True
    assert matches_redacted("Fictional Co Ltd", stored, KEY)
    assert not matches_redacted("Other Co Ltd", stored, KEY)
    assert not matches_redacted("Fictional Co Ltd", stored, b"wrong-key")


def test_sensitive_edit_still_shows_that_it_changed(log):
    new_finding(log)
    event = log.edit(
        "F-1", ANALYST, {"subject_name": "Fictional Co Limited"}, reason="r"
    )
    change = event["changes"]["subject_name"]
    assert change["from"]["redacted"] and change["to"]["redacted"]
    assert change["from"] != change["to"]


def test_key_is_required(tmp_path):
    with pytest.raises(AuditError, match="redaction key"):
        AuditLog(tmp_path / "a.jsonl", b"")


# example file and schema


def test_committed_example_matches_generator(example):
    committed = HERE / "examples" / "audit_log.jsonl"
    assert committed.read_text() == example.path.read_text()


def test_example_events_match_schema(example):
    schema = json.loads((HERE / "event_schema.json").read_text())
    validator = Draft202012Validator(schema)
    redacted = Draft202012Validator({**schema["$defs"]["redacted"]})
    for event in read_events(example.path):
        validator.validate(event)
        for field, change in event["changes"].items():
            if field in SENSITIVE_FIELDS:
                for side in (change["from"], change["to"]):
                    if side is not None:
                        redacted.validate(side)


def test_cli(example, capsys):
    assert main(["verify", str(example.path)]) == 0
    assert "OK: 13 events" in capsys.readouterr().out
    assert main(["state", str(example.path), "F-001", "--seq", "4"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "under_review"
    assert main(["verify", str(example.path), "--head", "0" * 64]) == 1
