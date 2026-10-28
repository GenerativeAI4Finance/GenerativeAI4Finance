import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from edd_report import build_report_data, generate_report, render_markdown  # noqa: E402


def load_bundle():
    return json.loads((ROOT / "examples/report_input.json").read_text(encoding="utf-8"))


def test_example_has_linked_finding_and_withholds_unlinked_summary():
    bundle = load_bundle()
    report = build_report_data(bundle["case_record"], **{
        key: value for key, value in bundle.items() if key != "case_record"
    })
    assert report["report_version"] == "1.0.0"
    assert report["dataset_version"] == "1.0.0"
    assert report["generated_at"] == "2026-10-28T12:00:00Z"
    assert report["synthetic"] is True
    assert report["subject_summary"]["subject_name"] == "Example Orchard Trading Ltd."
    assert len(report["findings"]) == 1
    assert report["findings"][0]["finding_id"] == "F-801"
    assert {item["evidence_id"] for item in report["findings"][0]["evidence_records"]} == {"EDD-EV-801", "EDD-EV-802"}
    assert report["unlinked_findings"] == [{
        "finding_id": "F-802", "category": "adverse_media",
        "issue": "Only unavailable/generated evidence or a non-source-claim candidate is linked; summary withheld pending source support.",
    }]
    rendered = render_markdown(report)
    assert "Fictional unverified allegation deliberately has no source link" not in rendered
    assert "Model-generated/inferred candidate" in rendered
    assert "Exact cited passage" in rendered
    assert "No overall accusation, risk rating, or automatic final decision" in rendered
    assert "marked disputed" in rendered


def test_fixtures_validate_against_preceding_edd_schemas():
    bundle = load_bundle()
    base = ROOT.parent
    case_schema = json.loads((base / "G4F-EDD-001/schema.json").read_text(encoding="utf-8"))
    evidence_schema = json.loads((base / "G4F-EDD-002/schema.json").read_text(encoding="utf-8"))
    extraction_schema = json.loads((base / "G4F-EDD-006/schema/extraction_result.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(case_schema, format_checker=FormatChecker()).validate(bundle["case_record"])
    evidence_validator = Draft202012Validator(evidence_schema, format_checker=FormatChecker())
    for record in bundle["evidence_records"]:
        evidence_validator.validate(record)
    Draft202012Validator(extraction_schema, format_checker=FormatChecker()).validate(bundle["extraction_result"])


def test_unadopted_extractor_candidate_remains_separate_and_cited():
    bundle = load_bundle()
    report = build_report_data(bundle["case_record"], extraction_result=bundle["extraction_result"])
    assert [item["candidate_id"] for item in report["extractor_candidates"]] == ["CAND-0802"]
    rendered = render_markdown(report)
    assert "Source-claim candidate" in rendered
    assert "SYNTHETIC SOURCE: Separate example sentence." in rendered


def test_edd007_conflicts_stale_items_and_review_actions_are_reported_unresolved():
    bundle = load_bundle()
    report = build_report_data(
        bundle["case_record"], evidence_review=bundle["evidence_review"],
        unresolved_questions=["Confirm the ownership register date."],
    )
    assert any("conflicting ownership_percentage" in question for question in report["unresolved_questions"])
    assert any("Human-review the conflicting ownership_percentage" in action for action in report["recommended_actions"])
    assert "`unresolved_requires_human_review`" in render_markdown(report)


def test_missing_data_is_explicit_and_timestamp_must_include_timezone():
    report = build_report_data({"case_id": "G4F-EDD-999", "findings": []})
    rendered = render_markdown(report)
    assert "Scope\n\nNot provided" in rendered
    assert "Dataset version: Not provided" in rendered
    assert "Subject type: Not provided" in rendered
    assert "No source records provided." in rendered
    assert "No evidence-linked case findings were supplied." in rendered
    with pytest.raises(ValueError, match="include a timezone"):
        build_report_data({"case_id": "G4F-EDD-999"}, generated_at="2026-10-28T12:00:00")


def test_edd004_case_bundle_dataset_version_is_carried_forward():
    case_bundle = {"dataset_version": "3.2.1", "synthetic": True, "case_record": {"case_id": "G4F-EDD-888", "findings": []}}
    report = build_report_data(case_bundle, generated_at="2026-10-28T12:00:00Z")
    assert report["dataset_version"] == "3.2.1"
    assert report["synthetic"] is True


def test_full_edd004_dataset_selects_a_case_and_carries_subject_identity():
    dataset = {
        "dataset_version": "2.4.0", "synthetic": True,
        "cases": [{"case_record": {"case_id": "G4F-EDD-889", "subject_type": "company", "findings": []},
                   "subject_entity": {"entity_id": "SYN-ENTITY-889", "synthetic_name": "Synthetic Entity 889"},
                   "source_records": []}],
    }
    report = build_report_data(dataset, generated_at="2026-10-28T12:00:00Z")
    assert report["dataset_version"] == "2.4.0"
    assert report["subject_summary"]["subject_id"] == "SYN-ENTITY-889"
    assert report["subject_summary"]["subject_name"] == "Synthetic Entity 889"


def test_unavailable_edd002_source_does_not_support_a_substantive_finding():
    case = {"case_id": "G4F-EDD-776", "findings": [{"finding_id": "F-776", "category": "other", "summary": "Withhold", "severity": "low"}]}
    unavailable = [{"evidence_id": "EDD-EV-776", "claim_reference": "CLAIM-776", "finding_reference": "F-776", "evidence_status": "unavailable", "source_classification": ["primary"]}]
    report = build_report_data(case, evidence_records=unavailable)
    assert report["findings"] == []
    assert report["unlinked_findings"][0]["finding_id"] == "F-776"


def test_only_verbatim_source_claim_candidate_can_link_a_finding_without_edd002_record():
    case = {"case_id": "G4F-EDD-775", "findings": [{"finding_id": "F-775", "category": "other", "summary": "Source says active.", "severity": "low"}]}
    quote = "SYNTHETIC SOURCE: Entity status is active."
    inference = {
        "finding_id": "CAND-775", "statement": "The entity is probably active.",
        "statement_type": "model_inference", "review_status": "requires_human_review",
        "source_reference": {"source_id": "SRC-775", "finding_reference": "F-775"},
        "evidence": {"quote": quote, "start_char": 0, "end_char": len(quote)},
    }
    report = build_report_data(case, extraction_result={"findings": [inference]})
    assert report["findings"] == []

    source_claim = {**inference, "statement": quote, "statement_type": "source_claim", "review_status": "source_backed_candidate"}
    report = build_report_data(case, extraction_result={"findings": [source_claim]})
    assert report["findings"][0]["finding_id"] == "F-775"
    assert report["findings"][0]["extractor_candidates"][0]["evidence"]["quote"] == quote


def test_generated_only_source_does_not_support_case_finding():
    case = {"case_id": "G4F-EDD-777", "findings": [{"finding_id": "F-777", "category": "other", "summary": "Must be withheld", "severity": "low"}]}
    generated_evidence = [{"evidence_id": "EDD-EV-777", "claim_reference": "CLAIM-777", "finding_reference": "F-777", "source_classification": ["generated"], "evidence_status": "available"}]
    report = build_report_data(case, evidence_records=generated_evidence)
    assert report["findings"] == []
    assert report["unlinked_findings"][0]["finding_id"] == "F-777"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
