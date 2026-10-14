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
- `timestamp` (ISO 8601 with timezone, must not go backwards)
- `reason`: required for edits, decisions, escalation and closure
- `refs`: references to related records, e.g. `case:CASE-0042`, `evidence:EV-101`
- `status_before` / `status_after`
- `previous_event_seq`: the last event for the same finding, so you can walk a finding's history
- `changes`: field-level diff, `{"field": {"from": old, "to": new}}`, only for fields that actually changed
- `prev_hash` / `hash`: SHA-256 hash chain over the canonical JSON of each event

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

Rules enforced on write:

- Only analysts create, edit and submit. Only reviewers and senior reviewers
  approve, reject, escalate and close.
- Anyone who created or edited a finding cannot approve, reject or escalate it,
  even if they also hold a reviewer role.
- An escalated finding can only be decided by a `senior_reviewer`.
- Edits are only allowed in `draft` or `rejected`. Closed is final.
- An edit that changes nothing is refused.

A refused action raises `AuditError` and writes nothing.

## Sensitive fields

`subject_name` and `analyst_notes` are never written to the log in clear text.
The log stores an HMAC-SHA256 of the value instead:

```json
{"redacted": true, "hmac_sha256": "0c13882e..."}
```

The key is passed in when the log is opened and is not stored in the log. With
the key you can check whether a given value matches what was recorded
(`matches_redacted`), and an edit still shows that the field changed. Without
the key the digest tells you nothing useful. A keyed hash is used rather than a
plain one because names are easy to guess and a plain hash could be reversed
by trying candidates.

This means replay gives back digests for these two fields, not the original
values. The values themselves belong in the case store, not the audit log.

## How to run

```bash
cd 07-applications/enhanced-due-diligence/G4F-EDD-010
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m pytest tests -q
python make_example.py                     # regenerate the example log
python audit_trail.py verify examples/audit_log.jsonl
python audit_trail.py state examples/audit_log.jsonl F-002 --as-of 2026-03-04T00:00:00+00:00
python audit_trail.py state examples/audit_log.jsonl F-001 --seq 4
```

Python 3.11 or newer.

## Verification

`verify` checks that `seq` runs 1, 2, 3, ... with no gaps, that each line's
`prev_hash` equals the previous line's `hash`, and that each line's content
still matches its own hash. That catches an edited line, a removed line and
reordered lines. The tests cover each case.

Dropping lines from the end of the file still leaves a valid chain. To catch
that you need to keep the latest head hash somewhere else (a ticketing system,
a separate store, a signed checkpoint) and pass it with `--head`.

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
- The redaction key is held separately from the log, with tighter access.
- Retention period is not set here. It depends on the institution and the
  jurisdiction and should be decided by whoever runs it. Deleting old events
  breaks the chain, so retention would need to be handled by archiving whole
  log segments with their head hash, not by removing lines.

## Limitations

- Single writer only. There is no locking, so two processes appending at once
  can corrupt the chain.
- The hash chain shows tampering but does not prevent it. Someone with write
  access can rewrite the whole file and recompute every hash. An external head
  hash or signing would be needed to stop that.
- Free text in `reason` and non-sensitive fields is written as given. The code
  cannot tell if an analyst pastes a personal detail into a reason, so that
  still relies on guidance and review.
- Timestamps come from the writer's clock and are only checked to be in order.
- No reopen step after closing, and no delegation or four-eyes on closure.
- Example data is fictional. Nothing here has been tested against a real case
  workload.
