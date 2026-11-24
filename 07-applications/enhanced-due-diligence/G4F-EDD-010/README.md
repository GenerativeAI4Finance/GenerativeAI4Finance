# G4F-EDD-010: Human review and audit trail for EDD findings

This Python reference implementation records each finding event as one JSONL
line and rebuilds current or historical state by replaying the log. It uses the
standard library at runtime; tests require `pytest` and `jsonschema`.

## Setup and CLI

From the repository root, with Python 3.11 or newer:

```bash
cd 07-applications/enhanced-due-diligence/G4F-EDD-010
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests -q
python make_example.py

export EDD_AUDIT_KEY=demo-key-not-for-real-use-edd010
python audit_trail.py verify examples/audit_log.jsonl
python audit_trail.py verify examples/audit_log.jsonl --head 13:0613e7f0a074c11b25acea81550870fec9593cb46c3222052134724871bb5b88
python audit_trail.py state examples/audit_log.jsonl F-002 --as-of 2026-03-04T00:00:00+00:00
python audit_trail.py state examples/audit_log.jsonl F-001 --seq 4
```

The example key is public and for demonstration only. In PowerShell, replace
`source .venv/bin/activate` with `.\.venv\Scripts\Activate.ps1`, use `;` in
place of `&&`, and set the key with
`$env:EDD_AUDIT_KEY = 'demo-key-not-for-real-use-edd010'`. A real key must be
random, at least 32 bytes, and supplied by a secrets store. The CLI reads it from
`EDD_AUDIT_KEY`. Exit codes are 0 for success, 1 for an invalid or missing log
(or an empty log in `verify`), and 2 for bad arguments or a missing/short key.

`audit_trail.py` provides `verify LOG [--head SEQ:HASH]` and
`state LOG FINDING_ID [--as-of ISO_TIMESTAMP] [--seq N]`. A timestamp must
include a timezone; `--as-of` and `--seq` can be combined. Both CLI commands
verify the entire log before returning a selected historical state. In the
Python `replay(events, key, upto_seq=N)` sequence-only form, only the first N
positions are checked. With a time cutoff, replay also checks the first event
after the cutoff before stopping, but does not check later events. Use
`verify_events` or open `AuditLog` to verify every event.

`upto_seq` accepts `None` or an exact nonnegative integer; invalid values raise
`AuditError`. Zero selects no events. A cutoff beyond the head adds no sequence
restriction; any supplied time cutoff still applies. CLI `--seq` rejects negatives.

## Events and review rules

Files: `audit_trail.py` implements writing, verification, replay and the CLI;
`event_schema.json` defines an event; `make_example.py` regenerates the
fictional example in `examples/audit_log.jsonl`.

Events include a sequence number, finding and event type, pseudonymous actor
id and role, UTC timestamp, references, status transition, per-finding previous
event sequence, field changes, key id, and HMAC chain hashes. Timestamps are
normalized to UTC and cannot go backwards across the log. Reasons are required
for edits, decisions, escalation, and closure. References use `kind:id`, such
as `case:CASE-0042`.

The lifecycle is `created → draft → under_review`, followed by approval or
rejection; reviewers may escalate an under-review finding, after which only a
senior reviewer can approve or reject. A rejected finding may be edited back
to draft and resubmitted. Approved or rejected findings may be closed; closed
findings are final.

- Analysts create, edit, and submit. Reviewers and senior reviewers decide,
  escalate, and close.
- A person who created or edited a finding cannot approve, reject, escalate,
  or close it. The person who escalates cannot decide it.
- Edits are allowed only in draft or rejected status, must change a field, and
  record a reason. Refused actions raise `AuditError` and write nothing.
- Actor ids are normalized to lowercase and restricted to pseudonymous ids;
  roles are supplied by the caller, not authenticated by this library.

The finding fields are `title`, `summary`, `risk_category`, `confidence`,
`evidence_refs`, `subject_name`, and `analyst_notes`. Changes are field-level
diffs. Canonical JSON comparisons preserve type changes (`true` to `1`) while
ignoring object-key order. Input and returned state/events are copied.

## Integrity, replay, and checkpoints

Each event is HMAC-SHA256 chained to the previous event. Opening `AuditLog` and
both CLI commands check every line: JSON shape and duplicate keys, contiguous
sequence, previous hash, event HMAC, and whether the event obeys the review
rules and prior state. This detects edits, insertions, reordering, and middle
removals when the verifier has the key. It does not detect a valid shorter log
after tail removal, or a complete rewrite by someone with the key.

Store the latest `SEQ:HASH` head somewhere log writers cannot change, then
verify with `--head` or `expected_head=`. A checkpoint confirms that its event
remains unchanged; later appended events are allowed. Tail removal after the
latest checkpoint remains undetectable. The key can both write and verify, so
anyone who has it is trusted with both powers.

`AuditLog(path, key, create=True)` starts a log and refuses to overwrite an
existing file. An existing empty file can be opened for its first append, but
`verify` treats an empty log as failure. Missing or unreadable files fail.
Keep the path and lock file stable while writing. If a write is interrupted,
an incomplete final line makes reads and further appends fail. Preserve a copy,
remove only bytes after the last newline, verify against the latest external
head, then repeat the action only if still needed.

## Sensitive data and keys

`subject_name` and `analyst_notes` are stored as keyed digests, never clear
text. Each digest covers the finding id, field name, and value, so equal names
in different findings have different digests. Replay returns the digest, not
the original value; `matches_redacted(value, stored, key, finding_id=...,
field=...)` can check a candidate; malformed stored digests return `False`.
Anyone with the key can test guesses, so
these digests protect against readers without the key, not key holders. Other
free-text fields are stored as entered and may still contain sensitive data.

A 32-byte minimum secret derives separate chain and redaction keys plus a
short `key_id`; each event names its key id. Key rotation is not supported
within a log. To change keys, retain the old log's final head and start a new
log. Keep the key separate from the log and limit access to writers and trusted
verifiers.

## Filesystem, access, and retention

Appends use an exclusive adjacent `<log>.lock` (`fcntl` on Linux/macOS,
`msvcrt` on Windows), recheck the existing bytes and any newer events, then
write and `fsync`. Each append rereads the existing log to verify its
integrity (O(n)), so cumulative append cost grows with log size. Locking coordinates
`AuditLog` writers where supported; it does not coordinate other writers.
Symlink paths resolve to the
target for lock selection. Multiple hard links are refused because aliases
could use different locks. Keep the log and lock path stable; replacing them
while writing is outside the model. CLI readers do not lock and may observe a
torn final line during a write. Opening or refreshing `AuditLog` takes the
writer lock. The lock is released when a process exits, but
the empty lock file remains. Lock waiting defaults to 10 seconds.

Roles are trusted caller input; authentication and mapping pseudonymous ids to
people belong to the host application. In deployment, restrict writes to
append-only access, keep keys separately with tighter access, and copy heads
regularly to storage writers cannot alter. Retention is deployment-specific;
archive whole log segments with their heads rather than deleting lines.

This is a reference implementation, not a compliance claim or a tested real
case workload. File-lock behavior depends on the filesystem, timestamps depend
on writer clocks, and one `AuditLog` object should not be shared between
threads. The example log is wholly fictional; no root or applicable dataset
licence is declared. Maintainer guidance on an appropriate contribution and
dataset licence is requested.
