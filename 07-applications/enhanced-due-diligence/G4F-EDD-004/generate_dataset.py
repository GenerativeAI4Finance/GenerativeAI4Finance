#!/usr/bin/env python3
"""Generate deterministic, explicitly synthetic EDD training cases."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


DATASET_VERSION = "1.0.0"
DEFAULT_SEED = 20261022
SCENARIOS = (
    "normal",
    "ambiguous_entity_match",
    "incomplete_records",
    "conflicting_claims",
    "stale_evidence",
)
JURISDICTIONS = ("GB", "CA", "SG", "IN", "US")
RISK_BY_SCENARIO = {
    "normal": [],
    "ambiguous_entity_match": ["identity_verification"],
    "incomplete_records": ["ownership_opacity"],
    "conflicting_claims": ["ownership_opacity"],
    "stale_evidence": ["ownership_opacity"],
}


def _source(case_number: int, source_number: int, kind: str, description: str,
            checked_date: str, *, url: bool = True) -> dict:
    result = {
        "source_id": f"SRC-SYN-{case_number:03d}-{source_number:02d}",
        "source_type": kind,
        "description": f"SYNTHETIC FIXTURE: {description}",
        "checked_date": checked_date,
    }
    if url:
        result["url"] = (
            f"https://example.org/synthetic-edd/{case_number:03d}/"
            f"source-{source_number:02d}"
        )
    return result


def make_case(case_number: int, scenario: str, rng: random.Random) -> dict:
    jurisdiction = rng.choice(JURISDICTIONS)
    entity_id = f"ENT-SYN-{case_number:03d}"
    entity_name = f"Synthetic Meridian Entity {case_number:03d}"
    date_suffix = f"{case_number % 28 + 1:02d}"
    checked_date = f"2026-10-{date_suffix}"
    source_records = [
        _source(case_number, 1, "registry", "fictional entity register extract", checked_date),
        _source(case_number, 2, "internal_record", "fictional onboarding declaration showing a 60/40 ownership split", checked_date, url=False),
    ]

    directors = [
        {
            "person_id": f"PER-SYN-{case_number:03d}-01",
            "synthetic_name": f"Synthetic Person {case_number:03d}-A",
            "roles": ["director"],
            "jurisdiction": jurisdiction,
            "synthetic": True,
        },
        {
            "person_id": f"PER-SYN-{case_number:03d}-02",
            "synthetic_name": f"Synthetic Person {case_number:03d}-B",
            "roles": ["director", "shareholder"],
            "jurisdiction": jurisdiction,
            "synthetic": True,
        },
    ]
    shareholders = [
        {"owner_id": directors[1]["person_id"], "owner_type": "individual", "ownership_percent": 60},
        {"owner_id": directors[0]["person_id"], "owner_type": "individual", "ownership_percent": 40},
    ]
    subsidiaries = [{
        "entity_id": f"SUB-SYN-{case_number:03d}-01",
        "synthetic_name": f"Synthetic Meridian Subsidiary {case_number:03d}",
        "jurisdiction": rng.choice(JURISDICTIONS),
        "ownership_percent": 100,
        "synthetic": True,
    }]
    address = {
        "address_id": f"ADDR-SYN-{case_number:03d}-01",
        "address_line": f"{case_number + 1} Fictional Example Road, Sample District",
        "jurisdiction": jurisdiction,
        "synthetic": True,
    }
    risk_indicators = []
    findings = []
    review_status = "completed"
    confidence = 0.91

    if scenario == "ambiguous_entity_match":
        candidate = f"Synthetic Meridian Entity {case_number:03d}-A"
        risk_indicators.append({
            "indicator": "ambiguous_entity_match",
            "status": "unresolved",
            "detail": f"Synthetic candidate label {candidate} resembles the subject label; no real entity is implicated.",
        })
        findings.append({
            "finding_id": f"F-{case_number:03d}",
            "category": "identity_verification",
            "summary": "Synthetic training scenario: a label-only candidate cannot be resolved without additional distinguishing identifiers.",
            "severity": "medium",
            "disposition": "unresolved",
        })
        review_status, confidence = "escalated", 0.48
    elif scenario == "incomplete_records":
        shareholders[1]["ownership_percent"] = None
        risk_indicators.append({
            "indicator": "incomplete_ownership_record",
            "status": "incomplete",
            "detail": "A fictional ownership percentage is missing from the synthetic declaration.",
        })
        findings.append({
            "finding_id": f"F-{case_number:03d}",
            "category": "ownership_opacity",
            "summary": "Synthetic training scenario: the ownership chain is incomplete; additional evidence would be needed before a conclusion.",
            "severity": "medium",
            "disposition": "unresolved",
        })
        review_status, confidence = "escalated", 0.55
    elif scenario == "conflicting_claims":
        source_records.append(_source(
            case_number, 3, "other",
            "fictional ownership schedule claiming a 55/45 split, conflicting with the 60/40 onboarding declaration",
            checked_date,
        ))
        risk_indicators.append({
            "indicator": "conflicting_claims",
            "status": "disputed",
            "detail": "The synthetic onboarding declaration states 60/40 while a second synthetic schedule states 55/45; neither is treated as authoritative by this fixture.",
        })
        findings.append({
            "finding_id": f"F-{case_number:03d}",
            "category": "ownership_opacity",
            "summary": "Synthetic training scenario: source records conflict on ownership; preserve both claims and seek human reconciliation.",
            "severity": "high",
            "disposition": "unresolved",
        })
        review_status, confidence = "escalated", 0.4
    elif scenario == "stale_evidence":
        source_records[0]["checked_date"] = "2024-01-15"
        source_records[0]["description"] += " (stale synthetic snapshot)"
        risk_indicators.append({
            "indicator": "stale_evidence",
            "status": "outdated",
            "detail": "The synthetic registry snapshot predates the review and may not establish current status.",
        })
        findings.append({
            "finding_id": f"F-{case_number:03d}",
            "category": "adverse_media",
            "summary": "Synthetic training scenario: evidence is stale and cannot support a current-state conclusion without an updated check.",
            "severity": "low",
            "disposition": "unresolved",
        })
        review_status, confidence = "escalated", 0.52

    case_record = {
        "case_id": f"G4F-EDD-{400 + case_number:03d}",
        "subject_type": "company",
        "jurisdiction": jurisdiction,
        "review_date": "2026-10-22",
        "risk_categories": RISK_BY_SCENARIO[scenario],
        "source_records": source_records,
        "findings": findings,
        "confidence": confidence,
        "analyst_notes": f"SYNTHETIC TRAINING FIXTURE; scenario={scenario}; no real entity, person, source, or allegation is represented.",
        "review_status": review_status,
    }
    return {
        "case_record": case_record,
        "scenario": scenario,
        "subject_entity": {
            "entity_id": entity_id,
            "synthetic_name": entity_name,
            "entity_type": "company",
            "registration_id": f"SYN-REG-{case_number:06d}",
            "registration_jurisdiction": jurisdiction,
            "incorporation_date": f"202{case_number % 5}-0{case_number % 9 + 1}-15",
            "status": "active",
            "addresses": [address],
            "synthetic": True,
        },
        "directors": directors,
        "shareholders": shareholders,
        "subsidiaries": subsidiaries,
        "source_records": [
            {
                **record,
                "title": record["description"],
                "publisher": "Synthetic EDD Dataset Generator",
                "reference": record.get("url"),
                "publication_date": None,
                "access_date": record["checked_date"],
                "jurisdiction": jurisdiction,
                "evidence_status": (
                    "outdated" if scenario == "stale_evidence" and record["source_id"].endswith("01")
                    else "disputed" if scenario == "conflicting_claims" and record["source_id"].endswith("03")
                    else "available"
                ),
                "excerpt_or_summary": record["description"],
                "provenance_notes": "Generated fixture only; placeholder reference, not a real citation.",
            }
            for record in source_records
        ],
        "risk_indicators": risk_indicators,
        "synthetic": True,
    }


def generate_dataset(seed: int = DEFAULT_SEED, cases_per_scenario: int = 2) -> dict:
    if cases_per_scenario < 1:
        raise ValueError("cases_per_scenario must be at least 1")
    rng = random.Random(seed)
    cases = []
    number = 1
    for scenario in SCENARIOS:
        for _ in range(cases_per_scenario):
            cases.append(make_case(number, scenario, rng))
            number += 1
    return {
        "dataset_name": "GenerativeAI4Finance synthetic EDD cases",
        "dataset_version": DATASET_VERSION,
        "seed": seed,
        "synthetic": True,
        "generator": "generate_dataset.py",
        "case_count": len(cases),
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--cases-per-scenario", type=int, default=2)
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).parent / "data" / "edd_cases_v1.json",
    )
    args = parser.parse_args()
    dataset = generate_dataset(args.seed, args.cases_per_scenario)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(dataset, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {dataset['case_count']} synthetic cases to {args.output}")


if __name__ == "__main__":
    main()
