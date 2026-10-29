import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from edd_evaluation import evaluate_system, render_results_markdown, run_evaluation  # noqa: E402


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fixtures():
    return (
        read_json(ROOT / "examples/gold_set_v1.json"),
        read_json(ROOT / "examples/mock_model_predictions.json"),
    )


def test_gold_set_schema_and_all_annotated_spans_are_valid():
    gold, _ = fixtures()
    schema = read_json(ROOT / "schema/gold_set.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(gold)
    for document in gold["documents"]:
        text = document["source"]["text"]
        for finding in document["gold_findings"]:
            assert text[finding["start_char"]:finding["end_char"]] == finding["quote"]
            if finding["statement_type"] == "source_claim":
                assert finding["statement"] == finding["quote"]
    assert any(not doc["gold_findings"] for doc in gold["documents"])
    assert any(doc["source"]["text"] == "" for doc in gold["documents"])


def test_edd006_candidate_shapes_validate_against_existing_output_schema():
    gold, model = fixtures()
    schema = read_json(ROOT.parent / "G4F-EDD-006/schema/extraction_result.schema.json")
    finding_schema = schema["properties"]["findings"]["items"]
    validator = Draft202012Validator(finding_schema)
    for candidates in model["predictions_by_document"].values():
        for candidate in candidates:
            validator.validate(candidate)


def test_baseline_and_optional_comparison_metrics_are_reproducible():
    gold, model = fixtures()
    first = run_evaluation(gold, model)
    second = run_evaluation(gold, model)
    assert first == second
    baseline, mock = first["results"]
    assert baseline["metrics"]["extraction_precision"] == 0.5
    assert baseline["metrics"]["extraction_recall"] == 1.0
    assert baseline["metrics"]["citation_correctness"] == 1.0
    assert baseline["metrics"]["unsupported_claim_rate"] == 0.5
    assert baseline["metrics"]["negative_case_abstention_rate"] == pytest.approx(1 / 3, abs=1e-6)
    assert baseline["metrics"]["positive_case_false_abstention_rate"] == 0.0
    assert mock["metrics"]["extraction_precision"] == pytest.approx(1 / 3, abs=1e-6)
    assert mock["metrics"]["extraction_recall"] == pytest.approx(1 / 3, abs=1e-6)
    assert mock["metrics"]["citation_correctness"] == 1.0
    assert mock["metrics"]["unsupported_claim_rate"] == pytest.approx(2 / 3, abs=1e-6)
    assert mock["metrics"]["positive_case_false_abstention_rate"] == pytest.approx(1 / 3, abs=1e-6)
    assert "small synthetic set" in " ".join(first["limitations"])
    assert "not a model run" in mock["system_name"]


def test_valid_quote_does_not_make_an_unsupported_claim_supported():
    gold, model = fixtures()
    result = run_evaluation(gold, model)["results"][1]
    negative_doc = next(item for item in result["per_document"] if item["document_id"] == "DOC-009-005")
    assert negative_doc["citation_correct"] == 1
    assert negative_doc["unsupported_claims"] == 1


def test_bad_citation_increases_unsupported_rate_and_unknown_document_fails():
    gold, model = fixtures()
    broken = json.loads(json.dumps(model))
    broken["predictions_by_document"]["DOC-009-001"][0]["evidence"]["end_char"] = 5
    result = evaluate_system(gold, broken["predictions_by_document"], system_name="broken fixture")
    assert result["metrics"]["citation_correctness"] < 1.0
    assert result["metrics"]["unsupported_claim_rate"] > 0
    with pytest.raises(ValueError, match="unknown document IDs"):
        evaluate_system(gold, {"DOC-UNKNOWN": []}, system_name="invalid")


def test_runner_rejects_non_synthetic_or_corrupted_gold():
    gold, _ = fixtures()
    with pytest.raises(ValueError, match="explicitly synthetic"):
        run_evaluation({**gold, "synthetic": False})
    corrupted = json.loads(json.dumps(gold))
    corrupted["documents"][0]["gold_findings"][0]["end_char"] += 1
    with pytest.raises(ValueError, match="quote/offset"):
        run_evaluation(corrupted)
    with pytest.raises(TypeError, match="gold_set must be an object"):
        run_evaluation([])


def test_rendered_results_include_all_requested_metrics_and_limitations():
    gold, model = fixtures()
    markdown = render_results_markdown(run_evaluation(gold, model))
    for label in ("Precision", "Recall", "Citation correctness", "Unsupported-claim rate", "Negative abstention", "False abstention", "Abstention precision", "Limitations"):
        assert label in markdown
    assert "not outputs from an actual language model" in markdown


def test_zero_prediction_and_zero_gold_denominators_are_defined_as_zero():
    gold = {
        "synthetic": True,
        "documents": [{
            "document_id": "DOC-EMPTY",
            "source": {"source_id": "SRC-EMPTY", "text": ""},
            "gold_findings": [],
        }],
    }
    result = evaluate_system(gold, {"DOC-EMPTY": []}, system_name="empty")
    metrics = result["metrics"]
    assert metrics["extraction_precision"] == 0.0
    assert metrics["extraction_recall"] == 0.0
    assert metrics["citation_correctness"] == 0.0
    assert metrics["unsupported_claim_rate"] == 0.0
    assert metrics["negative_case_abstention_rate"] == 1.0
    assert metrics["abstention_precision"] == 1.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
