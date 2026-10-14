import itertools
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import make_example
from audit_trail import (
    GENESIS_HASH,
    KEY_ENV,
    MIN_KEY_BYTES,
    REASON_REQUIRED,
    Actor,
    AuditError,
    AuditLog,
    Head,
    IntegrityError,
    event_hash,
    exclusive_lock,
    main,
    matches_redacted,
    read_events,
    replay,
    verify_events,
)

KEY = b"test-key-for-the-audit-trail-tests"
DEMO_KEY = make_example.DEMO_KEY
ANALYST = Actor("analyst-1", "analyst")
ANALYST_2 = Actor("analyst-2", "analyst")
REVIEWER = Actor("reviewer-1", "reviewer")
SENIOR = Actor("senior-1", "senior_reviewer")
SENIOR_2 = Actor("senior-2", "senior_reviewer")
SCHEMA = Draft202012Validator(
    json.loads((HERE / "event_schema.json").read_text(encoding="utf-8"))
)


def ticking_clock(start="2026-01-01T00:00:00+00:00"):
    t0 = datetime.fromisoformat(start)
    n = itertools.count()
    return lambda: (t0 + timedelta(minutes=next(n))).isoformat()


@pytest.fixture
def log(tmp_path):
    return AuditLog(tmp_path / "audit.jsonl", KEY, clock=ticking_clock(), create=True)


@pytest.fixture
def example(tmp_path):
    return make_example.build(tmp_path / "example.jsonl")


@pytest.fixture
def cli_key(monkeypatch):
    monkeypatch.setenv(KEY_ENV, DEMO_KEY.decode())


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
    text = "".join(json.dumps(e, sort_keys=True) + "\n" for e in events)
    path.write_bytes(text.encode())


def resign(events, key, start=0):
    """Recompute hashes from ``start`` on, as someone holding ``key`` could."""
    prev = events[start - 1]["hash"] if start else GENESIS_HASH
    for event in events[start:]:
        event["prev_hash"] = prev
        event["hash"] = event_hash(event, key)
        prev = event["hash"]
    return events


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


def test_cannot_close_twice(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    log.approve("F-1", REVIEWER, reason="ok")
    log.close("F-1", REVIEWER, reason="done")
    with pytest.raises(AuditError, match="cannot apply 'closed' when status is closed"):
        log.close("F-1", REVIEWER, reason="again")


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
    with pytest.raises(AuditError, match="role 'reviewer' cannot perform 'created'"):
        new_finding(log, actor=REVIEWER)
    new_finding(log)
    with pytest.raises(AuditError, match="role 'reviewer' cannot perform 'edited'"):
        log.edit("F-1", REVIEWER, {"confidence": "high"}, reason="r")


def test_author_cannot_review_own_finding(log):
    # same person holding a reviewer role still cannot decide on work they wrote
    new_finding(log)
    log.submit("F-1", ANALYST)
    same_person = Actor("analyst-1", "reviewer")
    with pytest.raises(AuditError, match="cannot review"):
        log.approve("F-1", same_person, reason="r")


def test_author_cannot_close_own_finding(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    log.reject("F-1", REVIEWER, reason="weak")
    with pytest.raises(AuditError, match="cannot review"):
        log.close("F-1", Actor("analyst-1", "reviewer"), reason="drop it")


def test_editor_cannot_review(log):
    new_finding(log)
    log.edit("F-1", ANALYST_2, {"confidence": "high"}, reason="r")
    log.submit("F-1", ANALYST)
    with pytest.raises(AuditError, match="cannot review"):
        log.reject("F-1", Actor("analyst-2", "senior_reviewer"), reason="r")


def test_actor_ids_are_compared_without_case(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    variant = Actor(" Analyst-1 ", "reviewer")
    assert variant.id == "analyst-1"
    with pytest.raises(AuditError, match="cannot review"):
        log.approve("F-1", variant, reason="r")


@pytest.mark.parametrize("actor_id", ["", "Jane Doe", "jane@example.com", None])
def test_actor_id_must_be_pseudonymous(actor_id):
    with pytest.raises(AuditError, match="pseudonymous id"):
        Actor(actor_id, "analyst")


def test_escalated_needs_senior_reviewer(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    log.escalate("F-1", REVIEWER, reason="needs a second view")
    with pytest.raises(AuditError, match="senior_reviewer"):
        log.approve("F-1", Actor("reviewer-9", "reviewer"), reason="r")
    assert log.approve("F-1", SENIOR, reason="ok")["status_after"] == "approved"


def test_escalator_cannot_decide(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    log.escalate("F-1", SENIOR, reason="needs a second view")
    with pytest.raises(AuditError, match="escalated F-1 and cannot also decide"):
        log.approve("F-1", SENIOR, reason="agree with myself")
    assert log.approve("F-1", SENIOR_2, reason="ok")["status_after"] == "approved"


def _draft(log):
    new_finding(log)


def _under_review(log):
    new_finding(log)
    log.submit("F-1", ANALYST)


def _approved(log):
    _under_review(log)
    log.approve("F-1", REVIEWER, reason="ok")


REASON_CASES = {
    "edited": (
        _draft,
        lambda log, r: log.edit("F-1", ANALYST, {"confidence": "high"}, reason=r),
    ),
    "approved": (_under_review, lambda log, r: log.approve("F-1", REVIEWER, r)),
    "rejected": (_under_review, lambda log, r: log.reject("F-1", REVIEWER, r)),
    "escalated": (_under_review, lambda log, r: log.escalate("F-1", REVIEWER, r)),
    "closed": (_approved, lambda log, r: log.close("F-1", REVIEWER, r)),
}


@pytest.mark.parametrize("event_type", sorted(REASON_REQUIRED))
@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reason_is_required(log, event_type, reason):
    setup, action = REASON_CASES[event_type]
    setup(log)
    with pytest.raises(AuditError, match=f"'{event_type}' requires a reason"):
        action(log, reason)


def test_unknown_role_rejected():
    with pytest.raises(AuditError, match="unknown role"):
        Actor("x", "admin")


# timestamps


def test_timestamps_cannot_go_backwards(tmp_path):
    times = iter(["2026-01-02T00:00:00+00:00", "2026-01-01T00:00:00+00:00"])
    log = AuditLog(tmp_path / "a.jsonl", KEY, clock=lambda: next(times), create=True)
    new_finding(log)
    with pytest.raises(AuditError, match="earlier"):
        log.submit("F-1", ANALYST)


def test_timestamps_are_stored_in_utc_and_compared_as_instants(tmp_path):
    times = iter(
        [
            "2026-03-02T09:00:00+00:00",
            "2026-03-02T10:30:00+01:00",  # 09:30 UTC
            "2026-03-02T09:45:00Z",  # later, although "09:45" sorts before "10:30"
        ]
    )
    log = AuditLog(tmp_path / "a.jsonl", KEY, clock=lambda: next(times), create=True)
    new_finding(log)
    assert log.submit("F-1", ANALYST)["timestamp"] == "2026-03-02T09:30:00+00:00"
    assert (
        log.approve("F-1", REVIEWER, "ok")["timestamp"] == "2026-03-02T09:45:00+00:00"
    )

    assert log.state("F-1", as_of="2026-03-02T10:20:00+01:00")["status"] == "draft"
    assert (
        log.state("F-1", as_of="2026-03-02T05:40:00-04:00")["status"] == "under_review"
    )
    assert log.state("F-1", as_of="2026-03-02T09:45:00+00:00")["status"] == "approved"


@pytest.mark.parametrize(
    "bad, message",
    [("2026-03-02T09:00:00", "timezone"), ("yesterday", "ISO 8601")],
)
def test_clock_must_give_a_timezone(tmp_path, bad, message):
    log = AuditLog(tmp_path / "a.jsonl", KEY, clock=lambda: bad, create=True)
    with pytest.raises(AuditError, match=message):
        new_finding(log)
    assert log.path.read_bytes() == b""


def test_as_of_needs_a_timezone(log):
    new_finding(log)
    with pytest.raises(AuditError, match="timezone"):
        log.state("F-1", as_of="2026-01-01")


# keyed chain: tampering and forged events


def test_example_log_verifies(example):
    assert verify_events(read_events(example.path), DEMO_KEY) == example.head


def test_every_event_names_the_key(example):
    assert {e["key_id"] for e in example.events} == {example.key_id}


def test_edited_line_is_detected(example):
    events = read_events(example.path)
    events[5]["reason"] = "looks fine"
    write_lines(example.path, events)
    with pytest.raises(IntegrityError, match="line 6: content does not match"):
        AuditLog(example.path, DEMO_KEY)


def test_rehashing_without_the_key_is_detected(example):
    events = read_events(example.path)
    events[5]["event_type"] = "approved"
    events[5]["reason"] = "Looks fine to me"
    resign(events, b"someone else's key, at least 32 bytes", start=5)
    write_lines(example.path, events)
    with pytest.raises(IntegrityError, match="line 6: content does not match"):
        verify_events(read_events(example.path), DEMO_KEY)


def test_edited_line_with_recomputed_hash_breaks_next_link(example):
    events = read_events(example.path)
    events[5]["reason"] = "Looks fine to me"
    events[5]["hash"] = event_hash(events[5], DEMO_KEY)
    write_lines(example.path, events)
    with pytest.raises(IntegrityError, match="line 7: prev_hash"):
        verify_events(read_events(example.path), DEMO_KEY)


def test_rewrite_by_key_holder_needs_external_head(example):
    events = read_events(example.path)
    events[5]["reason"] = "Looks fine to me"
    resign(events, DEMO_KEY, start=5)
    write_lines(example.path, events)
    # a consistent rewrite by someone with the key passes on its own...
    AuditLog(example.path, DEMO_KEY)
    # ...but not against a head that was stored elsewhere
    with pytest.raises(IntegrityError, match="does not match the expected head"):
        AuditLog(example.path, DEMO_KEY, expected_head=example.head)


def test_removed_line_is_detected(example):
    events = read_events(example.path)
    del events[3]
    write_lines(example.path, events)
    with pytest.raises(IntegrityError, match="line 4"):
        verify_events(read_events(example.path), DEMO_KEY)


def test_reordered_lines_are_detected(example):
    events = read_events(example.path)
    events[4], events[5] = events[5], events[4]
    write_lines(example.path, events)
    with pytest.raises(IntegrityError, match="line 5"):
        verify_events(read_events(example.path), DEMO_KEY)


FORGERIES = [
    ({"actor_id": "analyst-1"}, "cannot review"),
    ({"reason": None}, "requires a reason"),
    ({"timestamp": "2020-01-01T00:00:00+00:00"}, "earlier"),
    ({"timestamp": "2026-01-01T03:00:00+02:00"}, "stored in UTC"),
    ({"status_before": "garbage"}, "status should go"),
    ({"status_after": "closed"}, "status should go"),
    ({"previous_event_seq": 999}, "previous_event_seq"),
    ({"actor_role": "admin"}, "unknown role"),
    ({"actor_role": "analyst"}, "role 'analyst' cannot"),
    ({"event_type": "closed"}, "cannot apply 'closed'"),
    ({"changes": {"title": {"from": "Registry gap", "to": "x"}}}, "cannot change"),
    ({"finding_id": ""}, "finding_id"),
    ({"refs": "case:CASE-1"}, "refs"),
    ({"seq": 3.0}, "expected seq"),
    ({"note": "extra"}, "unexpected"),
]


@pytest.mark.parametrize("forged, message", FORGERIES)
def test_forged_event_fails_the_write_checks(log, forged, message):
    # someone with the key appends an event that the API would have refused
    new_finding(log)
    log.submit("F-1", ANALYST)
    log.approve("F-1", REVIEWER, reason="ok")
    events = read_events(log.path)
    events[-1].update(forged)
    resign(events, KEY, start=2)
    write_lines(log.path, events)
    with pytest.raises(IntegrityError, match=f"line 3: .*{message}"):
        AuditLog(log.path, KEY)


def test_replay_runs_the_same_checks(log):
    _approved(log)
    events = log.events
    events[-1]["actor_id"] = "analyst-1"
    resign(events, KEY, start=2)
    with pytest.raises(IntegrityError, match="line 3: analyst-1 worked on F-1"):
        replay(events, KEY)


def test_clear_text_sensitive_value_is_refused_on_read(log):
    new_finding(log)
    log.edit("F-1", ANALYST, {"subject_name": "Fictional Co Limited"}, reason="r")
    events = read_events(log.path)
    events[1]["changes"]["subject_name"]["to"] = "Fictional Co Limited"
    resign(events, KEY, start=1)
    write_lines(log.path, events)
    with pytest.raises(IntegrityError, match="line 2: subject_name must be a keyed"):
        AuditLog(log.path, KEY)


def test_change_must_start_from_the_previous_value(log):
    new_finding(log)
    log.edit("F-1", ANALYST, {"confidence": "high"}, reason="r")
    events = read_events(log.path)
    events[1]["changes"]["confidence"]["from"] = "medium"
    resign(events, KEY, start=1)
    write_lines(log.path, events)
    with pytest.raises(IntegrityError, match="line 2: confidence: 'from' is not"):
        AuditLog(log.path, KEY)


# opening, expected head and truncation


def test_missing_log_is_an_error_unless_created(tmp_path):
    path = tmp_path / "audit.jsonl"
    with pytest.raises(IntegrityError, match="does not exist"):
        AuditLog(path, KEY)
    assert list(tmp_path.iterdir()) == []
    AuditLog(path, KEY, create=True)
    assert AuditLog(path, KEY).events == []
    with pytest.raises(AuditError, match="already exists"):
        AuditLog(path, KEY, create=True)


def test_truncated_tail_needs_external_head(example):
    events = read_events(example.path)[:-1]
    # the chain alone still looks fine after dropping the last line
    verify_events(events, DEMO_KEY)
    with pytest.raises(IntegrityError, match="truncated"):
        verify_events(events, DEMO_KEY, expected_head=example.head)


def test_expected_head_on_open(example):
    head = example.head
    AuditLog(example.path, DEMO_KEY, expected_head=head)
    AuditLog(example.path, DEMO_KEY, expected_head=str(head))
    # an older checkpoint still passes: events after it are allowed
    AuditLog(example.path, DEMO_KEY, expected_head=Head(5, example.events[4]["hash"]))

    write_lines(example.path, read_events(example.path)[:7])
    AuditLog(example.path, DEMO_KEY)
    with pytest.raises(IntegrityError, match="7 events but the expected head is at"):
        AuditLog(example.path, DEMO_KEY, expected_head=head)


@pytest.mark.parametrize(
    "text", ["", "13", "13:abc", "x:" + "0" * 64, "-1:" + "0" * 64]
)
def test_head_must_be_seq_and_hash(text):
    with pytest.raises(AuditError, match="SEQ:HASH"):
        Head.parse(text)


def test_writer_notices_log_shortened_under_it(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    data = log.path.read_bytes()
    log.path.write_bytes(data[: data.index(b"\n") + 1])
    with pytest.raises(IntegrityError, match="shorter"):
        log.approve("F-1", REVIEWER, reason="ok")


# copies in and out


def test_state_is_a_copy(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    state = log.state("F-1")
    state["status"] = "draft"
    state["authors"].clear()
    state["fields"]["confidence"] = "high"

    assert log.state("F-1")["status"] == "under_review"
    with pytest.raises(AuditError, match="cannot apply"):
        log.edit("F-1", ANALYST, {"title": "rewritten"}, reason="r")
    with pytest.raises(AuditError, match="cannot review"):
        log.approve("F-1", Actor("analyst-1", "reviewer"), reason="r")


def test_caller_data_is_copied_in(log):
    evidence = ["EV-1"]
    refs = ["evidence:EV-1"]
    log.create("F-1", ANALYST, {"title": "t", "evidence_refs": evidence}, refs=refs)
    evidence.append("EV-2")
    refs.append("evidence:EV-2")

    assert log.state("F-1")["fields"]["evidence_refs"] == ["EV-1"]
    assert log.events[0]["refs"] == ["evidence:EV-1"]
    log.edit("F-1", ANALYST, {"evidence_refs": evidence}, reason="added EV-2")
    assert AuditLog(log.path, KEY).state("F-1") == log.state("F-1")


def test_historical_state_and_events_are_copies(log):
    new_finding(log)
    log.submit("F-1", ANALYST)
    old = log.state("F-1", upto_seq=1)
    old["authors"].clear()
    old["fields"]["title"] = "changed"
    log.events[0]["actor_id"] = "someone-else"
    log.state("F-1")["authors"].clear()

    assert log.state("F-1", upto_seq=1)["authors"] == {"analyst-1"}
    assert log.state("F-1", upto_seq=1)["fields"]["title"] == "Registry gap"
    same_person = Actor("analyst-1", "reviewer")
    with pytest.raises(AuditError, match="cannot review"):
        log.approve("F-1", same_person, reason="r")
    with pytest.raises(AuditError, match="cannot review"):
        AuditLog(log.path, KEY).approve("F-1", same_person, reason="r")


def test_returned_events_are_copies(log):
    event = new_finding(log)
    event["changes"]["title"]["to"] = "tampered in memory"
    log.events[0]["seq"] = 99
    assert log.state("F-1", upto_seq=1)["fields"]["title"] == "Registry gap"
    verify_events(log.events, KEY)


# several writers, locking and interrupted writes


def test_two_writers_share_one_chain(tmp_path):
    clock = ticking_clock()
    w1 = AuditLog(tmp_path / "a.jsonl", KEY, clock=clock, create=True)
    w2 = AuditLog(tmp_path / "a.jsonl", KEY, clock=clock)
    new_finding(w1, "F-1")
    new_finding(w2, "F-2")  # w2 had not seen F-1 yet
    w1.submit("F-2", ANALYST)  # w1 had not seen F-2 yet

    assert [e["seq"] for e in read_events(w1.path)] == [1, 2, 3]
    assert w2.state("F-2")["status"] == "draft"
    w2.refresh()
    assert w2.state("F-2")["status"] == "under_review"
    assert AuditLog(w1.path, KEY).head == w1.head == w2.head


CHILD = """
import sys
sys.path.insert(0, sys.argv[1])
from audit_trail import Actor, AuditLog
log = AuditLog(sys.argv[2], sys.argv[3].encode(), clock=lambda: "2026-01-01T00:00:00Z")
for i in range(5):
    log.create(f"F-{sys.argv[4]}-{i}", Actor("analyst-1", "analyst"), {"title": "t"})
"""


def test_writers_in_separate_processes(tmp_path):
    path = tmp_path / "audit.jsonl"
    AuditLog(path, KEY, create=True)
    args = [str(HERE), str(path), KEY.decode()]
    procs = [
        subprocess.Popen([sys.executable, "-B", "-c", CHILD, *args, str(k)])
        for k in range(3)
    ]
    assert [p.wait(timeout=120) for p in procs] == [0, 0, 0]
    events = AuditLog(path, KEY).events
    assert len(events) == 15
    assert len({e["finding_id"] for e in events}) == 15


def test_append_waits_for_the_lock(log):
    log.lock_timeout = 0.2
    with exclusive_lock(log.path), pytest.raises(AuditError, match="timed out"):
        new_finding(log)
    assert log.path.read_bytes() == b""
    new_finding(log)


def test_append_is_fsynced(log, monkeypatch):
    calls = []
    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(fd) or real_fsync(fd))
    new_finding(log)
    assert len(calls) == 1


def test_missing_final_newline_is_refused(example):
    example.path.write_bytes(example.path.read_bytes().rstrip(b"\n"))
    with pytest.raises(IntegrityError, match="line 13 is incomplete"):
        AuditLog(example.path, DEMO_KEY)


def test_torn_last_line_is_refused(example):
    data = example.path.read_bytes()
    example.path.write_bytes(data[:-200])
    with pytest.raises(IntegrityError, match="line 13 is incomplete"):
        AuditLog(example.path, DEMO_KEY)


def test_writer_does_not_append_after_a_torn_line(log):
    new_finding(log)
    with log.path.open("ab") as fh:
        fh.write(b'{"seq": 2, "half')  # another writer stopped mid-line
    size = log.path.stat().st_size
    with pytest.raises(IntegrityError, match="line 2 is incomplete"):
        log.submit("F-1", ANALYST)
    assert log.path.stat().st_size == size


# parsing


@pytest.mark.parametrize(
    "line, message",
    [
        (b"{not json\n", "not valid JSON"),
        (b"\n", "not valid JSON"),
        (b"null\n", "not a JSON object"),
        (b"[1, 2]\n", "not a JSON object"),
        (b"5\n", "not a JSON object"),
        (b'{"seq": NaN}\n', "NaN is not allowed"),
    ],
)
def test_bad_lines_are_refused(example, line, message):
    with example.path.open("ab") as fh:
        fh.write(line)
    with pytest.raises(IntegrityError, match=f"line 14: {message}"):
        read_events(example.path)


def test_duplicate_keys_are_refused(example, cli_key, capsys):
    lines = example.path.read_bytes().split(b"\n")
    # a reader that keeps the first value would see an approval here
    lines[5] = lines[5].replace(
        b'{"actor_id"', b'{"event_type": "approved", "actor_id"'
    )
    example.path.write_bytes(b"\n".join(lines))
    with pytest.raises(IntegrityError, match="line 6: duplicate key 'event_type'"):
        read_events(example.path)
    assert main(["verify", str(example.path)]) == 1
    assert "duplicate key" in capsys.readouterr().out


# keys and redaction


@pytest.mark.parametrize(
    "key",
    [b"", b"x", b"x" * (MIN_KEY_BYTES - 1), "a str key that is long enough to use"],
)
def test_weak_or_non_bytes_keys_are_refused(tmp_path, key):
    with pytest.raises(AuditError, match="key must"):
        AuditLog(tmp_path / "a.jsonl", key, create=True)
    assert list(tmp_path.iterdir()) == []


def test_wrong_key_is_reported(example):
    with pytest.raises(
        IntegrityError, match=r"line 1: written with key id .*wrong key"
    ):
        AuditLog(example.path, KEY)


def test_sensitive_values_never_hit_disk(log):
    new_finding(log)
    log.edit(
        "F-1",
        ANALYST,
        {"analyst_notes": "Spoke to Jane Example on 555-0100"},
        reason="r",
    )
    raw = log.path.read_text(encoding="utf-8")
    assert "Fictional Co Ltd" not in raw
    assert "Jane Example" not in raw
    assert "555-0100" not in raw


def test_redacted_values_can_be_checked_with_key(log):
    new_finding(log)
    stored = log.state("F-1")["fields"]["subject_name"]
    assert stored["redacted"] is True
    scope = {"finding_id": "F-1", "field": "subject_name"}
    assert matches_redacted("Fictional Co Ltd", stored, KEY, **scope)
    assert not matches_redacted("Other Co Ltd", stored, KEY, **scope)
    other_key = b"another-key-that-is-32-bytes-long"
    assert not matches_redacted("Fictional Co Ltd", stored, other_key, **scope)
    scope["finding_id"] = "F-2"
    assert not matches_redacted("Fictional Co Ltd", stored, KEY, **scope)


def test_same_subject_in_two_findings_gives_different_digests(log):
    new_finding(log, "F-1")
    new_finding(log, "F-2")
    first = log.state("F-1")["fields"]["subject_name"]
    second = log.state("F-2")["fields"]["subject_name"]
    assert first != second


def test_sensitive_edit_still_shows_that_it_changed(log):
    new_finding(log)
    event = log.edit(
        "F-1", ANALYST, {"subject_name": "Fictional Co Limited"}, reason="r"
    )
    change = event["changes"]["subject_name"]
    assert change["from"]["redacted"] and change["to"]["redacted"]
    assert change["from"] != change["to"]


def test_sensitive_field_can_be_cleared(log):
    new_finding(log)
    event = log.edit("F-1", ANALYST, {"subject_name": None}, reason="wrong entity")
    assert event["changes"]["subject_name"]["to"] is None
    assert "subject_name" not in log.state("F-1")["fields"]
    assert AuditLog(log.path, KEY).state("F-1") == log.state("F-1")


# input checks


@pytest.mark.parametrize(
    "call, message",
    [
        (lambda log: log.create("", ANALYST, {"title": "t"}), "finding_id"),
        (lambda log: log.create("F 1", ANALYST, {"title": "t"}), "finding_id"),
        (lambda log: log.create("F-1", ANALYST, {}, refs="case:CASE-1"), "refs"),
        (lambda log: log.create("F-1", ANALYST, {}, refs=["person:Jane Q"]), "refs"),
        (lambda log: log.create("F-1", ANALYST, {"title": object()}), "plain JSON"),
        (lambda log: log.create("F-1", ANALYST, {"title": float("nan")}), "plain JSON"),
        (lambda log: log.create("F-1", ANALYST, ["title"]), "must be a dict"),
        (lambda log: log.create("F-1", ANALYST, {}, reason=42), "reason"),
        (lambda log: log.create("F-1", "analyst-1", {}), "must be an Actor"),
    ],
)
def test_bad_input_is_refused(log, call, message):
    with pytest.raises(AuditError, match=message):
        call(log)
    assert log.path.read_bytes() == b""


# example file and schema


def test_committed_example_matches_generator(example):
    committed = HERE / "examples" / "audit_log.jsonl"
    assert committed.read_text(encoding="utf-8") == example.path.read_text(
        encoding="utf-8"
    )


def test_readme_shows_the_example_head(example):
    assert str(example.head) in (HERE / "README.md").read_text(encoding="utf-8")


def test_example_events_match_schema(example):
    for event in read_events(example.path):
        SCHEMA.validate(event)


def test_written_events_match_schema(log):
    new_finding(log)
    log.edit("F-1", ANALYST, {"analyst_notes": "n", "subject_name": None}, "r")
    log.submit("F-1", ANALYST)
    log.escalate("F-1", REVIEWER, "second view")
    log.reject("F-1", SENIOR, "weak")
    log.close("F-1", REVIEWER, "dropped")
    for event in log.events:
        SCHEMA.validate(event)


SCHEMA_VIOLATIONS = {
    "clear-text subject_name": lambda e: e["changes"]["subject_name"].update(to="Jo"),
    "unknown changed field": lambda e: e["changes"].update(
        passport_no={"from": None, "to": "X123"}
    ),
    "unknown top-level field": lambda e: e.update(note="x"),
    "missing key_id": lambda e: e.pop("key_id"),
    "empty finding_id": lambda e: e.update(finding_id=""),
    "email as actor_id": lambda e: e.update(actor_id="jane@example.com"),
    "timestamp without timezone": lambda e: e.update(timestamp="2026-03-02T09:14:00"),
    "timestamp not a date": lambda e: e.update(timestamp="not a date"),
    "refs as a string": lambda e: e.update(refs="case:CASE-1"),
    "approval without reason": lambda e: e.update(
        event_type="approved", actor_role="reviewer", reason=None, changes={}
    ),
    "approval by an analyst": lambda e: e.update(
        event_type="approved", reason="ok", changes={}
    ),
    "submission with changes": lambda e: e.update(event_type="submitted"),
}


@pytest.mark.parametrize(
    "mutate", [pytest.param(f, id=name) for name, f in SCHEMA_VIOLATIONS.items()]
)
def test_schema_rejects(example, mutate):
    event = read_events(example.path)[0]
    SCHEMA.validate(event)
    mutate(event)
    assert not SCHEMA.is_valid(event)


# command line


def test_cli(example, cli_key, capsys):
    assert main(["verify", str(example.path)]) == 0
    assert f"OK: 13 events, head {example.head}" in capsys.readouterr().out
    assert main(["verify", str(example.path), "--head", str(example.head)]) == 0
    capsys.readouterr()
    assert main(["state", str(example.path), "F-001", "--seq", "4"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "under_review"
    assert main(["verify", str(example.path), "--head", "13:" + "0" * 64]) == 1


@pytest.mark.parametrize(
    "line, message",
    [
        (b"{not json\n", "not valid JSON"),
        (b"[1, 2]\n", "not a JSON object"),
        (b"null\n", "not a JSON object"),
    ],
)
def test_cli_reports_bad_lines(example, cli_key, capsys, line, message):
    with example.path.open("ab") as fh:
        fh.write(line)
    assert main(["verify", str(example.path)]) == 1
    assert f"FAILED: line 14: {message}" in capsys.readouterr().out


def test_cli_missing_or_empty_log_fails(tmp_path, cli_key, capsys):
    path = tmp_path / "audit.jsonl"
    assert main(["verify", str(path)]) == 1
    assert "does not exist" in capsys.readouterr().out
    path.write_bytes(b"")
    assert main(["verify", str(path)]) == 1
    assert "has no events" in capsys.readouterr().out


def test_cli_unreadable_log_fails(tmp_path, cli_key, capsys, monkeypatch):
    assert main(["verify", str(tmp_path)]) == 1  # a directory
    assert "FAILED" in capsys.readouterr().out
    path = tmp_path / "audit.jsonl"
    path.write_bytes(b"{}\n")

    def deny(self):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_bytes", deny)
    assert main(["verify", str(path)]) == 1
    assert "cannot read" in capsys.readouterr().out


def test_empty_existing_log_is_a_valid_empty_log(tmp_path, cli_key, capsys):
    path = tmp_path / "audit.jsonl"
    path.write_bytes(b"")
    log = AuditLog(path, KEY, clock=ticking_clock())
    assert log.events == [] and log.head == Head(0, GENESIS_HASH)
    new_finding(log)
    assert AuditLog(path, KEY).head.seq == 1
    path.write_bytes(b"")
    assert main(["state", str(path), "F-1"]) == 0
    assert capsys.readouterr().out.strip() == "null"


def test_cli_truncated_log_fails_against_head(example, cli_key, capsys):
    write_lines(example.path, read_events(example.path)[:7])
    assert main(["verify", str(example.path), "--head", str(example.head)]) == 1
    assert "truncated" in capsys.readouterr().out


@pytest.mark.parametrize(
    "args, message",
    [
        (["--as-of", "2026-03-04"], "timezone"),
        (["--as-of", "yesterday"], "ISO 8601"),
        (["--head", "13"], "SEQ:HASH"),
    ],
)
def test_cli_bad_arguments(example, cli_key, capsys, args, message):
    assert main(["state", str(example.path), "F-002", *args]) == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize("value", [None, "too-short"])
def test_cli_needs_a_usable_key(example, monkeypatch, capsys, value):
    if value is None:
        monkeypatch.delenv(KEY_ENV, raising=False)
    else:
        monkeypatch.setenv(KEY_ENV, value)
    assert main(["verify", str(example.path)]) == 2
    assert "key" in capsys.readouterr().err


def test_cli_reports_rule_violations(example, cli_key, capsys):
    events = read_events(example.path)
    events[12]["event_type"] = "edited"
    resign(events, DEMO_KEY, start=12)
    write_lines(example.path, events)
    assert main(["state", str(example.path), "F-002"]) == 1
    assert "FAILED: line 13: role 'reviewer' cannot" in capsys.readouterr().out
