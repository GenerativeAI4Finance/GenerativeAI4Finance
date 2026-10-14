"""Append-only review and audit trail for EDD findings.

Every change to a finding is written as one JSON line. Each line carries the
hash of the line before it, so edits, deletions and reordering show up when the
log is verified. Current or past state is rebuilt by replaying the events.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1
GENESIS_HASH = "0" * 64

ROLES = {"analyst", "reviewer", "senior_reviewer"}
REVIEW_ROLES = {"reviewer", "senior_reviewer"}

FINDING_FIELDS = {
    "title",
    "summary",
    "risk_category",
    "confidence",
    "evidence_refs",
    "subject_name",
    "analyst_notes",
}
# These never go into the log in clear text. The log keeps a keyed digest so a
# value can be checked later by someone who holds the key.
SENSITIVE_FIELDS = {"subject_name", "analyst_notes"}

# (event_type, status before) -> status after
TRANSITIONS = {
    ("created", None): "draft",
    ("edited", "draft"): "draft",
    ("edited", "rejected"): "draft",
    ("submitted", "draft"): "under_review",
    ("approved", "under_review"): "approved",
    ("rejected", "under_review"): "rejected",
    ("escalated", "under_review"): "escalated",
    ("approved", "escalated"): "approved",
    ("rejected", "escalated"): "rejected",
    ("closed", "approved"): "closed",
    ("closed", "rejected"): "closed",
}

ALLOWED_ROLES = {
    "created": {"analyst"},
    "edited": {"analyst"},
    "submitted": {"analyst"},
    "approved": REVIEW_ROLES,
    "rejected": REVIEW_ROLES,
    "escalated": REVIEW_ROLES,
    "closed": REVIEW_ROLES,
}

DECISIONS = {"approved", "rejected", "escalated"}
REASON_REQUIRED = {"edited", "approved", "rejected", "escalated", "closed"}


class AuditError(Exception):
    """Raised when an event would break the review rules."""


class IntegrityError(Exception):
    """Raised when a stored log fails verification."""


@dataclass(frozen=True)
class Actor:
    id: str
    role: str

    def __post_init__(self):
        if self.role not in ROLES:
            raise AuditError(f"unknown role: {self.role}")


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def event_hash(event: dict) -> str:
    body = {k: v for k, v in event.items() if k != "hash"}
    return hashlib.sha256(canonical(body)).hexdigest()


def redact(value, key: bytes) -> dict:
    digest = hmac.new(key, canonical(value), hashlib.sha256).hexdigest()
    return {"redacted": True, "hmac_sha256": digest}


def matches_redacted(value, stored: dict, key: bytes) -> bool:
    return hmac.compare_digest(redact(value, key)["hmac_sha256"], stored["hmac_sha256"])


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_ts(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        raise AuditError(f"timestamp must include a timezone: {ts}")
    return dt


def verify_events(events: list[dict], expected_head: str | None = None) -> str:
    """Check the hash chain and sequence. Returns the head hash."""
    prev = GENESIS_HASH
    for i, event in enumerate(events, start=1):
        if event.get("seq") != i:
            raise IntegrityError(
                f"line {i}: expected seq {i}, found {event.get('seq')}"
            )
        if event.get("prev_hash") != prev:
            raise IntegrityError(f"line {i}: prev_hash does not match line {i - 1}")
        if event_hash(event) != event.get("hash"):
            raise IntegrityError(f"line {i}: content does not match its hash")
        prev = event["hash"]
    if expected_head is not None and prev != expected_head:
        raise IntegrityError(
            "head hash differs from the expected value (log truncated?)"
        )
    return prev


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise IntegrityError(f"line {n}: not valid JSON") from exc
    return events


def apply_event(states: dict, event: dict) -> None:
    fid = event["finding_id"]
    etype = event["event_type"]
    current = states.get(fid)
    before = current["status"] if current else None
    after = TRANSITIONS.get((etype, before))
    if after is None:
        raise AuditError(f"{fid}: cannot apply '{etype}' when status is {before}")

    if current is None:
        current = {
            "finding_id": fid,
            "status": None,
            "fields": {},
            "created_by": event["actor_id"],
            "authors": set(),
            "last_seq": None,
        }
        states[fid] = current

    for field, change in event.get("changes", {}).items():
        current["fields"][field] = change["to"]
    if etype in ("created", "edited"):
        current["authors"].add(event["actor_id"])
    current["status"] = after
    current["last_seq"] = event["seq"]


def replay(
    events: list[dict], as_of: str | None = None, upto_seq: int | None = None
) -> dict:
    """Rebuild finding state from events, optionally stopping at a time or seq."""
    cutoff = parse_ts(as_of) if as_of else None
    states: dict = {}
    for event in events:
        if upto_seq is not None and event["seq"] > upto_seq:
            break
        if cutoff is not None and parse_ts(event["timestamp"]) > cutoff:
            break
        apply_event(states, event)
    return states


class AuditLog:
    def __init__(self, path, redaction_key: bytes, clock=utc_now):
        if not redaction_key:
            raise AuditError("a redaction key is required")
        self.path = Path(path)
        self.key = redaction_key
        self.clock = clock
        self.events = read_events(self.path)
        self.head = verify_events(self.events)
        self.states = replay(self.events)

    def state(
        self, finding_id: str, as_of: str | None = None, upto_seq: int | None = None
    ):
        if as_of is None and upto_seq is None:
            states = self.states
        else:
            states = replay(self.events, as_of=as_of, upto_seq=upto_seq)
        return states.get(finding_id)

    def _clean(self, field, value):
        return redact(value, self.key) if field in SENSITIVE_FIELDS else value

    def _append(
        self, finding_id, event_type, actor, reason=None, refs=(), changes=None
    ):
        if event_type in REASON_REQUIRED and not (reason and reason.strip()):
            raise AuditError(f"'{event_type}' requires a reason")
        if actor.role not in ALLOWED_ROLES[event_type]:
            raise AuditError(f"role '{actor.role}' cannot perform '{event_type}'")

        current = self.states.get(finding_id)
        before = current["status"] if current else None
        if (event_type, before) not in TRANSITIONS:
            raise AuditError(
                f"{finding_id}: cannot apply '{event_type}' when status is {before}"
            )

        if event_type in DECISIONS and actor.id in current["authors"]:
            raise AuditError(f"{actor.id} worked on {finding_id} and cannot review it")
        if before == "escalated" and actor.role != "senior_reviewer":
            raise AuditError("only a senior_reviewer can decide an escalated finding")

        timestamp = self.clock()
        if self.events and parse_ts(timestamp) < parse_ts(self.events[-1]["timestamp"]):
            raise AuditError("timestamp is earlier than the last event")

        event = {
            "schema_version": SCHEMA_VERSION,
            "seq": len(self.events) + 1,
            "finding_id": finding_id,
            "event_type": event_type,
            "actor_id": actor.id,
            "actor_role": actor.role,
            "timestamp": timestamp,
            "reason": reason,
            "refs": list(refs),
            "status_before": before,
            "status_after": TRANSITIONS[(event_type, before)],
            "previous_event_seq": current["last_seq"] if current else None,
            "changes": changes or {},
            "prev_hash": self.head,
        }
        event["hash"] = event_hash(event)

        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
        self.events.append(event)
        self.head = event["hash"]
        apply_event(self.states, event)
        return event

    def create(self, finding_id, actor, fields, refs=(), reason=None):
        unknown = set(fields) - FINDING_FIELDS
        if unknown:
            raise AuditError(f"unknown fields: {sorted(unknown)}")
        changes = {
            f: {"from": None, "to": self._clean(f, v)} for f, v in fields.items()
        }
        return self._append(finding_id, "created", actor, reason, refs, changes)

    def edit(self, finding_id, actor, updates, reason, refs=()):
        unknown = set(updates) - FINDING_FIELDS
        if unknown:
            raise AuditError(f"unknown fields: {sorted(unknown)}")
        current = self.states.get(finding_id)
        old = current["fields"] if current else {}
        changes = {}
        for field, value in updates.items():
            new = self._clean(field, value)
            if old.get(field) != new:
                changes[field] = {"from": old.get(field), "to": new}
        if not changes:
            raise AuditError("edit does not change anything")
        return self._append(finding_id, "edited", actor, reason, refs, changes)

    def submit(self, finding_id, actor, reason=None):
        return self._append(finding_id, "submitted", actor, reason)

    def approve(self, finding_id, actor, reason, refs=()):
        return self._append(finding_id, "approved", actor, reason, refs)

    def reject(self, finding_id, actor, reason, refs=()):
        return self._append(finding_id, "rejected", actor, reason, refs)

    def escalate(self, finding_id, actor, reason, refs=()):
        return self._append(finding_id, "escalated", actor, reason, refs)

    def close(self, finding_id, actor, reason):
        return self._append(finding_id, "closed", actor, reason)


def _printable(state):
    if state is None:
        return None
    return {**state, "authors": sorted(state["authors"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify or replay an EDD audit log.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify")
    v.add_argument("log")
    v.add_argument("--head", help="expected head hash, if you stored one elsewhere")
    s = sub.add_parser("state")
    s.add_argument("log")
    s.add_argument("finding_id")
    s.add_argument("--as-of")
    s.add_argument("--seq", type=int)
    args = parser.parse_args(argv)

    events = read_events(Path(args.log))
    try:
        head = verify_events(events, args.head if args.cmd == "verify" else None)
    except IntegrityError as exc:
        print(f"FAILED: {exc}")
        return 1
    if args.cmd == "verify":
        print(f"OK: {len(events)} events, head {head}")
        return 0
    states = replay(events, as_of=args.as_of, upto_seq=args.seq)
    print(json.dumps(_printable(states.get(args.finding_id)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
