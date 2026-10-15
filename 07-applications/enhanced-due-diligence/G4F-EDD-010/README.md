# G4F-EDD-010: Human review and audit trail for EDD findings

A small reference implementation of an append-only audit trail for EDD
findings. Every step a finding goes through (created, edited, submitted,
approved, rejected, escalated, closed) is written as one line of JSON. The
current state of a finding, or its state at any earlier point, is rebuilt by
replaying those lines.

It uses only the Python standard library. `pytest` and `jsonschema` are needed
for the tests.

## Files

- `audit_trail.py`: the log, the review rules, replay and verification, plus a small CLI.
- `event_schema.json`: JSON Schema for one event (one line of the log).
- `make_example.py`: writes `examples/audit_log.jsonl` from a fictional scenario.
- `examples/audit_log.jsonl`: example log with two findings on one made-up case.
- `tests/test_audit_trail.py`: tests.

## Event model

Each event has:

- `seq`: position in the log, starting at 1
- `finding_id`, `event_type`
- `actor_id` and `actor_role` (`analyst`, `reviewer`, `senior_reviewer`)
- `timestamp` (ISO 8601, stored in UTC, must not go backwards)
- `reason`: required for edits, decisions, escalation and closure
- `refs`: references to related records in the form `kind:id`, e.g. `case:CASE-0042`, `evidence:EV-101`
- `status_before` / `status_after`
- `previous_event_seq`: the last event for the same finding, so you can walk a finding's history
- `changes`: field-level diff, `{"field": {"from": old, "to": new}}`, only for fields that actually changed
- `key_id`: names the key the log was written with (see Keys)
- `prev_hash` / `hash`: HMAC-SHA256 chain over the canonical JSON of each event

Actor ids are pseudonymous (`analyst-07`): letters, digits, `.`, `_` and `-`,
so a name with spaces or an email address is refused. They are compared without
regard to case and stored in lower case, so `Analyst-07` and `analyst-07` are
the same person.

The finding record itself is kept minimal (`title`, `summary`,
`risk_category`, `confidence`, `evidence_refs`, `subject_name`,
`analyst_notes`). It is not tied to the G4F-EDD-001 case schema yet and can be
aligned with it once that lands.

## Status flow

```
created -> draft --submit--> under_review --approve--> approved --close--> closed
                                  |        --reject---> rejected --close--> closed
                                  |                        |
                                  |                      edit -> draft (resubmit)
                                  +--escalate--> escalated --approve/reject (senior only)
```

Rules:

- Only analysts create, edit and submit. Only reviewers and senior reviewers
  approve, reject, escalate and close.
- Anyone who created or edited a finding cannot approve, reject, escalate or
  close it, even if they also hold a reviewer role.
- An escalated finding can only be decided by a `senior_reviewer`, and not by
  the one who escalated it. Escalating asks for a second view, so the same
  person deciding it would defeat the point.
- Edits are only allowed in `draft` or `rejected`. Closed is final.
- An edit that changes nothing is refused.

A refused action raises `AuditError` and writes nothing. Data passed in is
copied, and `events`, returned events and `state()` hand out copies, so
changing them in the caller cannot alter the log or the rules applied to it.

The same checks run again on every event when a log is read. They live in one
function, so a log only verifies if each of its events could have been written
through `AuditLog`. That includes the fields that follow from earlier events:
`status_before`, `status_after`, `previous_event_seq` and the `from` side of
each change must match what the events before it give.

## Sensitive fields

`subject_name` and `analyst_notes` are never written to the log in clear text.
The log stores an HMAC-SHA256 of the value instead:

```json
{"redacted": true, "hmac_sha256": "97b8d754..."}
```

The digest covers the finding id and the field name as well as the value. The
same name in two findings therefore gives two unrelated digests, and the log
does not show that two findings are about the same subject. Within one finding
the digest still shows that the value changed, and whether it went back to an
earlier value. Setting a sensitive field to `None` is recorded as `null`.

With the key you can check whether a given value matches what was recorded
(`matches_redacted(value, stored, key, finding_id=..., field=...)`). Anyone
who holds the key can test guesses the same way, so the digests only protect
names from people without the key. A keyed hash is used rather than a plain one
because names are easy to guess and a plain hash could be checked by anyone
trying candidates.

Replay gives back digests for these two fields, not the original values. The
values themselves belong in the case store, not the audit log.

## Keys

A log is opened with one secret key of at least 32 bytes. Two keys are derived
from it with HMAC-SHA256, one for the hash chain and one for the digests above,
and a third derivation gives a short `key_id` that is written into every event.
Opening a log with a different key fails on line 1 with "wrong key?" rather
than treating every digest as changed.

Anyone with the key can verify the log, but can also write events that verify
and test guesses against the digests. The key belongs with the writing service
and whoever is trusted to verify, not with every reader. There is no key
rotation inside one log; to change keys, keep the old log's final head and
start a new log.

## How to run

```bash
cd 07-applications/enhanced-due-diligence/G4F-EDD-010
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m pytest tests -q
python make_example.py                     # regenerate the example log

export EDD_AUDIT_KEY=demo-key-not-for-real-use-edd010   # demo key from make_example.py
python audit_trail.py verify examples/audit_log.jsonl
python audit_trail.py verify examples/audit_log.jsonl --head 13:0613e7f0a074c11b25acea81550870fec9593cb46c3222052134724871bb5b88
python audit_trail.py state examples/audit_log.jsonl F-002 --as-of 2026-03-04T00:00:00+00:00
python audit_trail.py state examples/audit_log.jsonl F-001 --seq 4
```

The CLI reads the key from `EDD_AUDIT_KEY`. A real key should be random and
come from a secrets store. Exit codes are 0 when the log verifies, 1 when it
does not or the file is missing (and for `verify`, when it is empty) and 2 for
bad arguments or a missing or short key.

Python 3.11 or newer.

## Verification

Opening a log with `AuditLog`, and both CLI commands, check every line: it must
be one JSON object with no duplicate keys, `seq` runs 1, 2, 3, ... with no
gaps, each line's `prev_hash` equals the previous line's `hash`, each line's
`hash` is the HMAC of its content under the log key, and the event passes the
rules above given the events before it. Without the key, nobody can edit,
insert, reorder or remove a line in the middle, or append one, and still have
the log verify. An event appended by someone with the key still has to pass the
rules. The tests cover each case.

Two things the log cannot show by itself:

- Lines removed from the end leave a shorter log that is still valid.
- Someone with the key and write access can rewrite the file and recompute
  every hash.

To catch both, keep the latest head (`SEQ:HASH`, printed by `verify` and
available as `AuditLog.head`) somewhere the writers cannot change (a ticketing
system, a separate store, a signed checkpoint) and pass it with `--head` or
`expected_head=`. The check passes if that event is still in the log
unchanged; events added after it are fine. Anything removed after the last
stored head cannot be detected.

A missing file is an error. A new log is started with
`AuditLog(path, key, create=True)`, which refuses to overwrite an existing file.
An existing empty file is a valid log with no events: `AuditLog` opens it and
the first append becomes event 1. `verify` reports it as a failure, because a
log that should hold history and holds none is more likely damaged than new.
A path that is a directory, or a file that cannot be read, also makes the CLI
exit with 1.

## Several writers and interrupted writes

Each append takes an exclusive lock on a `<log>.lock` file next to the log
(`fcntl.flock` on Linux and macOS, `msvcrt.locking` on Windows), checks that
the previously read bytes are unchanged, reads anything other writers have
appended since, checks the new event against that, writes it and calls `fsync`
before returning. Several `AuditLog` objects, in one process or in several,
can append to the same file without forking the chain when they share this
lock. Symlink paths resolve to the target before choosing the lock. Writers
refuse files with multiple hard links, including links added after opening,
because hard-link aliases could otherwise choose different sidecar locks.
Checking the existing prefix reads it again on each refresh or append, so
the read cost grows with the log size.
The operating system drops the lock when a writer exits or dies, so there is no
stale lock to clean up; the empty `.lock` file stays. Waiting for the lock
gives up after `lock_timeout` seconds (10 by default) with an `AuditError`.

An `AuditLog` object only sees other writers' events when it next appends or
when `refresh()` is called. One object should not be shared between threads.

The CLI only reads and does not take the lock, so it also works on a read-only
copy. If it runs while a write is in progress it can report the last line as
incomplete; running it again after the write gives the real answer.

### Recovering from an interrupted write

If a writer dies partway through a write, the file can end without a newline.
Opening the log then fails with "line N is incomplete" and nothing more is
appended. The interrupted append never returned to its caller. To recover,
keep a copy of the file, remove the partial last line (everything after the
last newline), verify the result against the latest stored head, and redo the
action if it is still needed.

## Access control and retention assumptions

These are assumptions for the reference implementation, not a statement that
it meets any regulation or standard.

- Roles come from the caller. The code checks that the role is allowed to do
  the action, but it does not authenticate anyone. In a real deployment the
  role would come from an identity provider.
- Actor ids are pseudonymous (`analyst-07`). Mapping ids to people is kept
  outside the log.
- Writers can only append. Readers can verify and replay. Nobody should be able
  to rewrite the file, which in practice means storage that enforces this
  (write-once storage, restricted file permissions or a database with no
  update or delete grants).
- The key is held separately from the log, with tighter access. Since the key
  is needed to verify, whoever verifies is trusted not to write.
- Heads are copied regularly to a store the writers cannot change.
- Retention period is not set here. It depends on the institution and the
  jurisdiction and should be decided by whoever runs it. Deleting old events
  breaks the chain, so retention would need to be handled by archiving whole
  log segments with their head, not by removing lines.

## Limitations

- The lock only coordinates writers that go through `AuditLog`, and it relies
  on file locks working on the storage, which some network file systems do not
  guarantee. Keep the log path and its lock file stable: replacing either file
  or adding aliases while a write is in progress is outside this coordination
  model. Writers require a filesystem that reports hard-link counts.
- The hash chain shows tampering but does not prevent it, and verifying needs
  the same secret as writing. Public-key signatures would separate the two but
  need a library outside the standard library.
- Free text in `reason`, `title`, `summary` and the other non-sensitive fields
  is written as given. The code cannot tell if an analyst pastes a personal
  detail there, so that still relies on guidance and review.
- Timestamps come from the writer's clock and are only checked to be in order.
  With writers on different machines, clock skew can make an append fail as
  earlier than the last event.
- No reopen step after closing, no delegation, and no four-eyes on closure
  (one reviewer closes, as long as they did not work on the finding).
- Example data is fictional. Nothing here has been tested against a real case
  workload.
