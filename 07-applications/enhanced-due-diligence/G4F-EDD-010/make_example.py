"""Write examples/audit_log.jsonl from a fictional review scenario.

All names, ids and evidence references are made up. The key below is a demo
value only; a real key would be random and live outside the repository.
"""

from pathlib import Path

from audit_trail import KEY_ENV, Actor, AuditLog

DEMO_KEY = b"demo-key-not-for-real-use-edd010"
OUT = Path(__file__).parent / "examples" / "audit_log.jsonl"

TIMES = [
    "2026-03-02T09:14:00+00:00",
    "2026-03-02T09:40:00+00:00",
    "2026-03-02T10:05:00+00:00",
    "2026-03-02T10:20:00+00:00",
    "2026-03-03T08:55:00+00:00",
    "2026-03-03T11:30:00+00:00",
    "2026-03-04T14:10:00+00:00",
    "2026-03-04T15:00:00+00:00",
    "2026-03-05T09:30:00+00:00",
    "2026-03-05T10:45:00+00:00",
    "2026-03-05T16:20:00+00:00",
    "2026-03-06T09:00:00+00:00",
    "2026-03-06T09:05:00+00:00",
]


def build(path: Path) -> AuditLog:
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    times = iter(TIMES)
    log = AuditLog(path, DEMO_KEY, clock=lambda: next(times), create=True)

    analyst = Actor("analyst-07", "analyst")
    reviewer = Actor("reviewer-02", "reviewer")
    senior = Actor("senior-01", "senior_reviewer")

    log.create(
        "F-001",
        analyst,
        {
            "title": "Ownership chain not fully disclosed",
            "summary": "Registry filing lists a holding entity with no named owner.",
            "risk_category": "beneficial_ownership",
            "confidence": "medium",
            "evidence_refs": ["EV-101"],
            "subject_name": "Corvane Ridge Trading Ltd",
        },
        refs=["case:CASE-0042", "evidence:EV-101"],
    )
    log.create(
        "F-002",
        analyst,
        {
            "title": "Adverse media mention",
            "summary": "Trade publication article mentions a payment dispute.",
            "risk_category": "adverse_media",
            "confidence": "low",
            "evidence_refs": ["EV-102"],
        },
        refs=["case:CASE-0042", "evidence:EV-102"],
    )
    log.edit(
        "F-001",
        analyst,
        {
            "evidence_refs": ["EV-101", "EV-103"],
            "analyst_notes": "Called registry helpdesk.",
        },
        reason="Added second registry extract",
        refs=["evidence:EV-103"],
    )
    log.submit("F-001", analyst)
    log.submit("F-002", analyst)
    log.reject(
        "F-002",
        reviewer,
        reason="Article is from 2019 and the dispute was settled; evidence is stale",
        refs=["evidence:EV-102"],
    )
    log.escalate(
        "F-001",
        reviewer,
        reason="Ownership gap needs a senior call before it goes into the report",
    )
    log.approve(
        "F-001",
        senior,
        reason="Gap is real and sourced; keep confidence at medium",
        refs=["evidence:EV-101", "evidence:EV-103"],
    )
    log.edit(
        "F-002",
        analyst,
        {
            "summary": "Settled 2019 payment dispute, kept for context.",
            "confidence": "low",
        },
        reason="Reworded after reviewer feedback",
    )
    log.submit("F-002", analyst)
    log.approve("F-002", reviewer, reason="Context note is fine as worded")
    log.close("F-001", reviewer, reason="Included in case report draft")
    log.close("F-002", reviewer, reason="Included in case report draft")
    return log


if __name__ == "__main__":
    log = build(OUT)
    print(f"wrote {len(log.events)} events to {OUT}")
    print(f"head: {log.head}")
    print(f"verify with {KEY_ENV}={DEMO_KEY.decode()} and --head {log.head}")
