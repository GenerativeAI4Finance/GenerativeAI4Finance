"""Append-only review and audit trail for EDD findings.

Every change to a finding is written as one JSON line. Each line carries an
HMAC of its own content and the HMAC of the line before it, both under a key
that is kept outside the log. Reading a log runs every event back through the
same checks that were applied when it was written (roles, separation of duties,
reasons, timestamp order, status changes), so with the key an edited, removed,
reordered or forged line is caught. Lines removed from the end are only caught
against a head (seq and hash) stored somewhere else. Current or past state is
rebuilt by replaying the events.
"""

from __future__ import annotations

import argparse
import copy
import errno
import hashlib
import hmac
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

if os.name == "nt":
    import msvcrt
else:
    import fcntl

SCHEMA_VERSION = 1
GENESIS_HASH = "0" * 64
MIN_KEY_BYTES = 32
KEY_ENV = "EDD_AUDIT_KEY"

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
# Whoever created or edited a finding cannot take any of these steps on it.
INDEPENDENT = DECISIONS | {"closed"}
REASON_REQUIRED = {"edited", "approved", "rejected", "escalated", "closed"}

EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "seq",
        "finding_id",
        "event_type",
        "actor_id",
        "actor_role",
        "timestamp",
        "reason",
        "refs",
        "status_before",
        "status_after",
        "previous_event_seq",
        "changes",
        "key_id",
        "prev_hash",
        "hash",
    }
)

# Ids and references are kept to a narrow character set so that names, emails
# and free text do not end up in them by accident.
FINDING_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
ACTOR_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
REF = re.compile(r"[a-z][a-z0-9_]{0,31}:[A-Za-z0-9._:/#-]{1,128}")
HEX64 = re.compile(r"[0-9a-f]{64}")


class AuditError(Exception):
    """Raised when an event would break the review rules."""


class IntegrityError(Exception):
    """Raised when a stored log fails verification."""


@dataclass(frozen=True)
class Actor:
    """Who did something. ``id`` is a pseudonymous id such as ``analyst-07``.

    Ids are compared without regard to case, so they are stored in lower case.
    """

    id: str
    role: str

    def __post_init__(self):
        norm = self.id.strip().lower() if isinstance(self.id, str) else ""
        if not ACTOR_ID.fullmatch(norm):
            raise AuditError(
                "actor id must be a pseudonymous id such as analyst-07 (letters,"
                " digits, '.', '_' or '-'), not a name or email"
            )
        object.__setattr__(self, "id", norm)
        if self.role not in ROLES:
            raise AuditError(f"unknown role: {self.role}")


def _derive(key: bytes, purpose: str) -> bytes:
    return hmac.new(key, b"g4f-edd-010/" + purpose.encode(), hashlib.sha256).digest()


class Keys:
    """Keys derived from the one secret: one for the hash chain, one for the
    digests of sensitive fields, and a short id that names the key without
    revealing it."""

    def __init__(self, key: bytes):
        if not isinstance(key, bytes | bytearray):
            raise AuditError("the key must be bytes")
        if len(key) < MIN_KEY_BYTES:
            raise AuditError(f"the key must be at least {MIN_KEY_BYTES} bytes")
        key = bytes(key)
        self.chain = _derive(key, "chain")
        self.redaction = _derive(key, "redaction")
        self.key_id = _derive(key, "key-id").hex()[:16]

    def __repr__(self):
        return f"Keys(key_id={self.key_id!r})"


def _as_keys(key) -> Keys:
    return key if isinstance(key, Keys) else Keys(key)


class Head(NamedTuple):
    """Seq and hash of the last event. Kept outside the log, it shows whether
    lines were later removed from the end."""

    seq: int
    hash: str

    def __str__(self):
        return f"{self.seq}:{self.hash}"

    @classmethod
    def parse(cls, text: str) -> Head:
        m = isinstance(text, str) and re.fullmatch(r"([0-9]+):([0-9a-f]{64})", text)
        if not m:
            raise AuditError("a head looks like SEQ:HASH, e.g. 13:5f81...")
        return cls(int(m[1]), m[2])


def canonical(obj) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _mac(event: dict, keys: Keys) -> str:
    body = {k: v for k, v in event.items() if k != "hash"}
    return hmac.new(keys.chain, canonical(body), hashlib.sha256).hexdigest()


def event_hash(event: dict, key) -> str:
    """HMAC-SHA256 of an event, without its own hash, under the chain key."""
    return _mac(event, _as_keys(key))


def _digest(keys: Keys, finding_id: str, field: str, value) -> dict:
    """Keyed digest of a sensitive value, scoped to one finding and field."""
    scoped = canonical([finding_id, field, value])
    digest = hmac.new(keys.redaction, scoped, hashlib.sha256).hexdigest()
    return {"redacted": True, "hmac_sha256": digest}


def matches_redacted(value, stored: dict, key, *, finding_id: str, field: str) -> bool:
    """Check a value against the digest recorded for it. Needs the key."""
    expected = _digest(_as_keys(key), finding_id, field, value)["hmac_sha256"]
    return hmac.compare_digest(expected, stored["hmac_sha256"])


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_ts(ts) -> datetime:
    if not isinstance(ts, str):
        raise AuditError("timestamp must be a string")
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        raise AuditError(f"not an ISO 8601 timestamp: {ts}") from None
    if dt.tzinfo is None:
        raise AuditError(f"timestamp must include a timezone: {ts}")
    return dt


def to_utc(ts: str) -> str:
    """The form timestamps are stored in: ISO 8601 in UTC."""
    return parse_ts(ts).astimezone(UTC).isoformat()


class _Refused(ValueError):
    pass


def _no_duplicates(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise _Refused(f"duplicate key {k!r}")
        obj[k] = v
    return obj


def _no_constant(name):
    raise _Refused(f"{name} is not allowed")


def parse_lines(data: bytes, first_line: int = 1):
    """Yield (line number, event, size in bytes) for each line of a log.

    Each line must be one JSON object and end with a newline. Duplicate keys
    and NaN/Infinity are refused, so every JSON reader sees the same event.
    """
    end = data.rfind(b"\n") + 1
    pos, n = 0, first_line
    while pos < end:
        nl = data.index(b"\n", pos) + 1
        try:
            event = json.loads(
                data[pos:nl].decode("utf-8"),
                object_pairs_hook=_no_duplicates,
                parse_constant=_no_constant,
            )
        except _Refused as exc:
            raise IntegrityError(f"line {n}: {exc}") from None
        except ValueError:
            raise IntegrityError(f"line {n}: not valid JSON") from None
        if not isinstance(event, dict):
            raise IntegrityError(f"line {n}: not a JSON object")
        yield n, event, nl - pos
        pos, n = nl, n + 1
    if end < len(data):
        raise IntegrityError(
            f"line {n} is incomplete: the file does not end with a newline, which"
            " usually means a write was interrupted (see the README on recovery)"
        )


def read_events(path) -> list[dict]:
    """Read the events in a log file without checking them."""
    path = Path(path)
    if not path.exists():
        raise IntegrityError(f"{path} does not exist")
    return [event for _, event, _ in parse_lines(path.read_bytes())]


def _check_finding_id(fid) -> None:
    if not isinstance(fid, str) or not FINDING_ID.fullmatch(fid):
        raise AuditError(
            "finding_id must be 1 to 64 letters, digits, '.', '_', ':' or '-'"
        )


def _check_refs(refs) -> None:
    if not isinstance(refs, list) or not all(
        isinstance(r, str) and REF.fullmatch(r) for r in refs
    ):
        raise AuditError(
            "refs must be a list of record references such as case:CASE-0042"
        )


def _is_digest(value) -> bool:
    return (
        isinstance(value, dict)
        and value.keys() == {"redacted", "hmac_sha256"}
        and value["redacted"] is True
        and isinstance(value["hmac_sha256"], str)
        and HEX64.fullmatch(value["hmac_sha256"]) is not None
    )


def _check_changes(changes, etype: str, fields: dict) -> None:
    if not isinstance(changes, dict):
        raise AuditError("changes must be an object")
    if etype not in ("created", "edited"):
        if changes:
            raise AuditError(f"'{etype}' cannot change fields")
        return
    unknown = set(changes) - FINDING_FIELDS
    if unknown:
        raise AuditError(f"unknown fields: {sorted(unknown)}")
    if etype == "edited" and not changes:
        raise AuditError("edit does not change anything")
    for field, change in changes.items():
        if not isinstance(change, dict) or change.keys() != {"from", "to"}:
            raise AuditError(f"{field}: a change needs exactly 'from' and 'to'")
        if change["from"] != fields.get(field):
            raise AuditError(f"{field}: 'from' is not the value before this event")
        if change["to"] == change["from"]:
            raise AuditError(f"{field}: 'to' is the same as 'from'")
        if field in SENSITIVE_FIELDS and not (
            change["to"] is None or _is_digest(change["to"])
        ):
            raise AuditError(f"{field} must be a keyed digest, not clear text")


def _check_event(event, states: dict, prev: dict | None, keys: Keys):
    """Check one event against the log before it.

    Returns (finding_id, new state of that finding) and changes nothing. This
    is where every rule lives: it runs on each event before it is written and
    on each event read back from a file, so a stored log only verifies if
    every event in it could have been written through AuditLog.
    """
    if not isinstance(event, dict):
        raise AuditError("not a JSON object")
    if event.keys() != EVENT_FIELDS:
        missing = sorted(EVENT_FIELDS - event.keys())
        extra = sorted(event.keys() - EVENT_FIELDS)
        raise AuditError(f"wrong fields: missing {missing}, unexpected {extra}")

    # position in the chain, key and content
    seq = prev["seq"] + 1 if prev else 1
    if type(event["seq"]) is not int or event["seq"] != seq:
        raise AuditError(f"expected seq {seq}, found {event['seq']!r}")
    if event["prev_hash"] != (prev["hash"] if prev else GENESIS_HASH):
        raise AuditError(f"prev_hash does not match line {seq - 1}")
    if event["key_id"] != keys.key_id:
        raise AuditError(
            f"written with key id {event['key_id']!r} but the key given has id"
            f" {keys.key_id!r} (wrong key?)"
        )
    if not isinstance(event["hash"], str) or not hmac.compare_digest(
        event["hash"].encode(), _mac(event, keys).encode()
    ):
        raise AuditError("content does not match its hash")

    # who, why and when
    version = event["schema_version"]
    if type(version) is not int or version != SCHEMA_VERSION:
        raise AuditError(f"unsupported schema_version {version!r}")
    etype = event["event_type"]
    if not isinstance(etype, str) or etype not in ALLOWED_ROLES:
        raise AuditError(f"unknown event_type {etype!r}")
    fid = event["finding_id"]
    _check_finding_id(fid)
    actor = event["actor_id"]
    if not isinstance(actor, str) or not ACTOR_ID.fullmatch(actor):
        raise AuditError("actor_id is not a lower-case pseudonymous id")
    role = event["actor_role"]
    if not isinstance(role, str) or role not in ROLES:
        raise AuditError(f"unknown role: {role!r}")
    if role not in ALLOWED_ROLES[etype]:
        raise AuditError(f"role '{role}' cannot perform '{etype}'")
    reason = event["reason"]
    if reason is not None and not isinstance(reason, str):
        raise AuditError("reason must be text or null")
    if etype in REASON_REQUIRED and not (reason and reason.strip()):
        raise AuditError(f"'{etype}' requires a reason")
    _check_refs(event["refs"])
    ts = event["timestamp"]
    if to_utc(ts) != ts:
        raise AuditError(f"timestamp must be stored in UTC: {ts}")
    if prev and parse_ts(ts) < parse_ts(prev["timestamp"]):
        raise AuditError("timestamp is earlier than the last event")

    # status and links, which follow from the events before this one
    current = states.get(fid)
    before = current["status"] if current else None
    after = TRANSITIONS.get((etype, before))
    if after is None:
        raise AuditError(f"{fid}: cannot apply '{etype}' when status is {before}")
    if (event["status_before"], event["status_after"]) != (before, after):
        raise AuditError(
            f"status should go from {before} to {after}, not from"
            f" {event['status_before']!r} to {event['status_after']!r}"
        )
    last_seq = current["last_seq"] if current else None
    found = event["previous_event_seq"]
    if found != last_seq or isinstance(found, bool | float):
        raise AuditError(f"previous_event_seq should be {last_seq}, not {found!r}")

    # separation of duties
    if etype in INDEPENDENT and actor in current["authors"]:
        raise AuditError(f"{actor} worked on {fid} and cannot review it")
    if before == "escalated":
        if role != "senior_reviewer":
            raise AuditError("only a senior_reviewer can decide an escalated finding")
        if actor == current["escalated_by"]:
            raise AuditError(f"{actor} escalated {fid} and cannot also decide it")

    _check_changes(event["changes"], etype, current["fields"] if current else {})

    if current is None:
        new = {
            "finding_id": fid,
            "status": None,
            "fields": {},
            "created_by": actor,
            "authors": set(),
            "escalated_by": None,
            "last_seq": None,
        }
    else:
        new = copy.deepcopy(current)
    for field, change in event["changes"].items():
        if change["to"] is None:
            new["fields"].pop(field, None)
        else:
            new["fields"][field] = copy.deepcopy(change["to"])
    if etype in ("created", "edited"):
        new["authors"].add(actor)
    if etype == "escalated":
        new["escalated_by"] = actor
    new["status"] = after
    new["last_seq"] = event["seq"]
    return fid, new


def _checked(event, states, prev, keys, line):
    try:
        return _check_event(event, states, prev, keys)
    except AuditError as exc:
        raise IntegrityError(f"line {line}: {exc}") from exc


def _head_of(events: list[dict]) -> Head:
    if not events:
        return Head(0, GENESIS_HASH)
    return Head(events[-1]["seq"], events[-1]["hash"])


def _check_head(events: list[dict], expected) -> None:
    expected = expected if isinstance(expected, Head) else Head.parse(expected)
    if expected.seq > len(events):
        raise IntegrityError(
            f"log has {len(events)} events but the expected head is at seq"
            f" {expected.seq} (truncated?)"
        )
    actual = events[expected.seq - 1]["hash"] if expected.seq else GENESIS_HASH
    if actual != expected.hash:
        raise IntegrityError(
            f"event {expected.seq} does not match the expected head (rewritten?)"
        )


def _replay(events, keys: Keys, as_of=None, upto_seq=None) -> dict:
    cutoff = parse_ts(as_of) if as_of is not None else None
    states: dict = {}
    prev = None
    for line, event in enumerate(events, start=1):
        fid, new = _checked(event, states, prev, keys, line)
        if upto_seq is not None and event["seq"] > upto_seq:
            break
        if cutoff is not None and parse_ts(event["timestamp"]) > cutoff:
            break
        states[fid] = new
        prev = event
    return states


def replay(events, key, as_of=None, upto_seq=None) -> dict:
    """Rebuild finding state from events, optionally stopping at a time or seq.

    Every event up to the cutoff is checked exactly as when it was written.
    """
    return _replay(events, _as_keys(key), as_of, upto_seq)


def verify_events(events, key, expected_head=None) -> Head:
    """Check the chain, the key and every review rule. Returns the head.

    ``expected_head`` (a Head or "SEQ:HASH") must still be in the log
    unchanged; events added after it are fine.
    """
    _replay(events, _as_keys(key))
    if expected_head is not None:
        _check_head(events, expected_head)
    return _head_of(events)


@contextmanager
def exclusive_lock(path, timeout: float = 10.0):
    """Hold an exclusive lock on ``<path>.lock`` while the block runs.

    Uses fcntl.flock on POSIX and msvcrt.locking on Windows. The operating
    system drops the lock when the holder exits, so a crashed writer does not
    leave a stale lock behind. The empty .lock file itself stays.
    """
    path = Path(path)
    lock_path = path.with_name(path.name + ".lock")
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while not _try_lock(fd):
            if time.monotonic() >= deadline:
                raise AuditError(f"timed out waiting for {lock_path}")
            time.sleep(0.01)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)


if os.name == "nt":

    def _try_lock(fd: int) -> bool:
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EDEADLOCK):
                return False
            raise
        return True

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


def _copy_fields(fields) -> dict:
    """Check finding fields and copy them the way they will be stored."""
    if not isinstance(fields, dict):
        raise AuditError("fields must be a dict")
    unknown = set(map(str, fields)) - FINDING_FIELDS
    if unknown:
        raise AuditError(f"unknown fields: {sorted(unknown)}")
    try:
        return json.loads(json.dumps(fields, allow_nan=False))
    except (TypeError, ValueError):
        raise AuditError("field values must be plain JSON data") from None


class AuditLog:
    """An append-only audit log file.

    Any number of AuditLog objects, in one process or several, can append to
    the same file. Each append holds an exclusive lock (see exclusive_lock),
    reads and checks whatever other writers added since, writes its own line
    and fsyncs it. One object should not be shared between threads.
    """

    def __init__(
        self,
        path,
        key: bytes,
        *,
        clock=utc_now,
        create: bool = False,
        expected_head=None,
        lock_timeout: float = 10.0,
    ):
        self.path = Path(path)
        self._keys = _as_keys(key)
        self.clock = clock
        self.lock_timeout = lock_timeout
        self._events: list[dict] = []
        self._states: dict = {}
        self._size = 0
        if not create and not self.path.exists():
            raise IntegrityError(
                f"{self.path} does not exist (pass create=True to start a new log)"
            )
        with self._locked():
            if create:
                try:
                    self.path.open("xb").close()
                except FileExistsError:
                    raise AuditError(f"{self.path} already exists") from None
            self._refresh()
        if expected_head is not None:
            _check_head(self._events, expected_head)

    @property
    def events(self) -> list[dict]:
        """A copy of the events read or written so far."""
        return copy.deepcopy(self._events)

    @property
    def head(self) -> Head:
        return _head_of(self._events)

    @property
    def key_id(self) -> str:
        return self._keys.key_id

    def state(
        self, finding_id: str, as_of: str | None = None, upto_seq: int | None = None
    ):
        """A copy of a finding's state, now or at an earlier time or seq."""
        if as_of is None and upto_seq is None:
            return copy.deepcopy(self._states.get(finding_id))
        return _replay(self._events, self._keys, as_of, upto_seq).get(finding_id)

    def refresh(self) -> None:
        """Pick up events that other writers have appended."""
        with self._locked():
            self._refresh()

    def _locked(self):
        return exclusive_lock(self.path, self.lock_timeout)

    def _refresh(self) -> None:
        # Called with the lock held. Reads only what was added since last time.
        try:
            with self.path.open("rb") as fh:
                if os.fstat(fh.fileno()).st_size < self._size:
                    raise IntegrityError(
                        f"{self.path} is shorter than when it was last read"
                        " (truncated?)"
                    )
                fh.seek(self._size)
                data = fh.read()
        except FileNotFoundError:
            raise IntegrityError(f"{self.path} no longer exists") from None
        for line, event, size in parse_lines(data, len(self._events) + 1):
            prev = self._events[-1] if self._events else None
            fid, new = _checked(event, self._states, prev, self._keys, line)
            self._states[fid] = new
            self._events.append(event)
            self._size += size

    def _stored(self, finding_id, field, value):
        if value is None or field not in SENSITIVE_FIELDS:
            return value
        return _digest(self._keys, finding_id, field, value)

    def _append(
        self, finding_id, event_type, actor, reason=None, refs=(), updates=None
    ):
        if not isinstance(actor, Actor):
            raise AuditError("actor must be an Actor")
        _check_finding_id(finding_id)
        refs = list(refs) if isinstance(refs, list | tuple) else refs
        _check_refs(refs)

        with self._locked():
            self._refresh()
            current = self._states.get(finding_id)
            before = current["status"] if current else None
            old = current["fields"] if current else {}
            changes = {}
            for field, value in (updates or {}).items():
                new = self._stored(finding_id, field, value)
                if new != old.get(field):
                    changes[field] = {"from": old.get(field), "to": new}
            event = {
                "schema_version": SCHEMA_VERSION,
                "seq": len(self._events) + 1,
                "finding_id": finding_id,
                "event_type": event_type,
                "actor_id": actor.id,
                "actor_role": actor.role,
                "timestamp": to_utc(self.clock()),
                "reason": reason,
                "refs": refs,
                "status_before": before,
                "status_after": TRANSITIONS.get((event_type, before)),
                "previous_event_seq": current["last_seq"] if current else None,
                "changes": changes,
                "key_id": self._keys.key_id,
                "prev_hash": self.head.hash,
            }
            event["hash"] = _mac(event, self._keys)
            prev = self._events[-1] if self._events else None
            fid, new_state = _check_event(event, self._states, prev, self._keys)

            data = (json.dumps(event, sort_keys=True, allow_nan=False) + "\n").encode()
            with self.path.open("ab") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            self._size += len(data)
            self._events.append(event)
            self._states[fid] = new_state
        return copy.deepcopy(event)

    def create(self, finding_id, actor, fields, refs=(), reason=None):
        fields = _copy_fields(fields)
        return self._append(finding_id, "created", actor, reason, refs, fields)

    def edit(self, finding_id, actor, updates, reason, refs=()):
        updates = _copy_fields(updates)
        return self._append(finding_id, "edited", actor, reason, refs, updates)

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
    parser = argparse.ArgumentParser(
        description=f"Verify or replay an EDD audit log. The key is read from"
        f" the {KEY_ENV} environment variable. The log is read without taking"
        " the writers' lock."
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("log")
    common.add_argument(
        "--head", help="expected head as SEQ:HASH, kept somewhere other than the log"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify", parents=[common], help="check the whole log")
    s = sub.add_parser("state", parents=[common], help="show one finding's state")
    s.add_argument("finding_id")
    s.add_argument("--as-of", help="ISO 8601 time with a timezone")
    s.add_argument("--seq", type=int)
    args = parser.parse_args(argv)

    try:
        if not os.environ.get(KEY_ENV):
            raise AuditError(f"set {KEY_ENV} to the key the log was written with")
        keys = Keys(os.environ[KEY_ENV].encode())
        head = Head.parse(args.head) if args.head else None
        as_of = getattr(args, "as_of", None)
        if as_of is not None:
            parse_ts(as_of)
    except AuditError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        events = read_events(args.log)
        if args.cmd == "verify" and not events:
            raise IntegrityError(f"{args.log} has no events")
        found = verify_events(events, keys, head)
        if args.cmd == "state":
            states = _replay(events, keys, as_of=as_of, upto_seq=args.seq)
    except IntegrityError as exc:
        print(f"FAILED: {exc}")
        return 1
    except OSError as exc:
        print(f"FAILED: cannot read {args.log}: {exc.strerror}")
        return 1

    if args.cmd == "verify":
        print(f"OK: {len(events)} events, head {found}")
        if head is None:
            print("note: without --head, lines removed from the end would not show")
        return 0
    print(json.dumps(_printable(states.get(args.finding_id)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
