import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from edd_extractor import (  # noqa: E402
    CandidateFinding,
    SourceDocument,
    extract_findings,
    validate_candidates,
)


def load_json(relative_path):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def load_sources():
    return [SourceDocument(**item) for item in load_json("examples/input_sources.json")]


def test_default_extractor_returns_verbatim_claims_with_traceable_offsets():
    sources = load_sources()
    result = extract_findings(sources)
    assert result.status == "candidates_extracted"
    assert len(result.findings) == 3
    for finding in result.findings:
        source = next(item for item in sources if item.source_id == finding.source_reference["source_id"])
        start = finding.evidence["start_char"]
        end = finding.evidence["end_char"]
        assert source.text[start:end] == finding.evidence["quote"]
        assert finding.statement == finding.evidence["quote"]
        assert finding.statement_type == "source_claim"


def test_blank_or_missing_evidence_returns_insufficient_evidence():
    no_sources = extract_findings([])
    assert no_sources.status == "insufficient_evidence"
    empty = [SourceDocument(source_id="SRC-EMPTY", text="  \n")]
    result = extract_findings(empty)
    assert result.status == "insufficient_evidence"
    assert result.findings == []
    assert "Insufficient evidence" in result.message
    schema = load_json("schema/extraction_result.schema.json")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(no_sources.to_dict())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(result.to_dict())


def test_valid_provider_candidates_are_labeled_and_inferences_need_review():
    sources = load_sources()
    candidates = load_json("examples/provider_candidates_valid.json")
    result = validate_candidates(sources, candidates)
    assert result.status == "human_review_required"
    assert len(result.findings) == 4
    assert not result.rejected_candidates
    inference = next(item for item in result.findings if item.statement_type == "model_inference")
    unresolved = next(item for item in result.findings if item.statement_type == "unresolved")
    extracted_fact = next(item for item in result.findings if item.statement_type == "extracted_fact")
    assert inference.review_status == "requires_human_review"
    assert unresolved.review_status == "requires_human_review"
    assert extracted_fact.review_status == "requires_human_review"

    schema = load_json("schema/extraction_result.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(result.to_dict())


def test_unsupported_or_untraceable_provider_candidates_are_rejected():
    result = validate_candidates(
        load_sources(), load_json("examples/provider_candidates_invalid.json")
    )
    assert result.status == "insufficient_evidence"
    assert result.findings == []
    assert {item.code for item in result.rejected_candidates} == {
        "quote_mismatch", "unsupported_paraphrase", "unknown_source"
    }
    schema = load_json("schema/extraction_result.schema.json")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(result.to_dict())


def test_out_of_range_offsets_and_bad_statement_type_are_rejected():
    source = SourceDocument("SRC-1", "Synthetic source text.")
    bad_offset = CandidateFinding(
        "Synthetic source text.", "source_claim", "SRC-1",
        "Synthetic source text.", 0, 999,
    )
    bad_type = {
        "statement": "Synthetic source text.",
        "statement_type": "guess",
        "source_id": "SRC-1",
        "quote": "Synthetic source text.",
        "start_char": 0,
        "end_char": 22,
    }
    result = validate_candidates([source], [bad_offset, bad_type])
    assert result.status == "insufficient_evidence"
    assert [item.code for item in result.rejected_candidates] == ["invalid_location", "invalid_statement_type"]


def test_duplicate_source_ids_are_rejected_as_invalid_input():
    source = SourceDocument("SRC-1", "Synthetic source text.")
    try:
        validate_candidates([source, source], [])
    except ValueError as error:
        assert "unique" in str(error)
    else:
        raise AssertionError("duplicate source IDs should fail validation")


def test_edd001_source_record_adapter_preserves_case_schema_reference():
    case = load_json("../G4F-EDD-001/examples/case_low_risk.json")
    compact_record = case["source_records"][0]
    source = SourceDocument.from_edd001_record(
        compact_record,
        "SYNTHETIC FIXTURE: The supplied registry excerpt names Example Orchard Trading Ltd.",
    )
    result = extract_findings([source])
    assert result.status == "candidates_extracted"
    assert result.findings[0].source_reference["source_id"] == compact_record["source_id"]
    assert result.findings[0].source_reference["url"] == compact_record["url"]
    assert result.findings[0].source_reference["evidence_id"] is None


def test_edd002_evidence_adapter_carries_evidence_claim_and_finding_references():
    fixture = load_json("examples/edd002_evidence_input.json")
    evidence_schema_path = ROOT.parent / "G4F-EDD-002/schema.json"
    evidence_schema = json.loads(evidence_schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(evidence_schema, format_checker=FormatChecker()).validate(fixture["evidence_record"])

    source = SourceDocument.from_edd002_record(fixture["evidence_record"], fixture["source_text"])
    result = extract_findings([source])
    reference = result.findings[0].source_reference
    assert reference["source_id"] == fixture["evidence_record"]["evidence_id"]
    assert reference["evidence_id"] == fixture["evidence_record"]["evidence_id"]
    assert reference["claim_reference"] == fixture["evidence_record"]["claim_reference"]
    assert reference["finding_reference"] == fixture["evidence_record"]["finding_reference"]
    assert reference["source_type"] == fixture["evidence_record"]["source_type"]
    assert reference["url"] == fixture["evidence_record"]["url"]
    assert reference["reference"] == fixture["evidence_record"]["reference"]
