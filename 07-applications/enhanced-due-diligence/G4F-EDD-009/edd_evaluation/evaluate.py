"""Reproducible small-sample metrics for EDD extraction candidates."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


EDD006_ROOT = Path(__file__).resolve().parents[2] / "G4F-EDD-006"
if str(EDD006_ROOT) not in sys.path:
    sys.path.insert(0, str(EDD006_ROOT))

from edd_extractor import SourceDocument, extract_findings  # noqa: E402


def _normalize(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    return " ".join(text.casefold().split())


def _prediction_key(prediction: Mapping[str, Any], fallback_source_id: str) -> tuple[str, str, str]:
    source_reference = prediction.get("source_reference", {})
    source_id = source_reference.get("source_id", fallback_source_id) if isinstance(source_reference, Mapping) else fallback_source_id
    return (
        str(source_id),
        _normalize(prediction.get("statement")),
        str(prediction.get("statement_type", "")),
    )


def _citation_is_correct(prediction: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    source_reference = prediction.get("source_reference")
    evidence = prediction.get("evidence")
    if not isinstance(source_reference, Mapping) or not isinstance(evidence, Mapping):
        return False
    if source_reference.get("source_id") != source.get("source_id"):
        return False
    quote = evidence.get("quote")
    start = evidence.get("start_char")
    end = evidence.get("end_char")
    text = source.get("text")
    if not isinstance(quote, str) or not quote or not isinstance(text, str):
        return False
    if isinstance(start, bool) or not isinstance(start, int) or isinstance(end, bool) or not isinstance(end, int):
        return False
    return 0 <= start < end <= len(text) and text[start:end] == quote


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _validate_gold_documents(gold_set: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if not isinstance(gold_set, Mapping):
        raise TypeError("gold_set must be an object.")
    docs = gold_set.get("documents")
    if not isinstance(docs, list) or not docs:
        raise ValueError("Gold set must include a non-empty documents array.")
    doc_ids: set[str] = set()
    gold_ids: set[str] = set()
    for doc in docs:
        if not isinstance(doc, Mapping):
            raise TypeError("Each gold document must be an object.")
        doc_id = doc.get("document_id")
        if not isinstance(doc_id, str) or not doc_id.strip() or doc_id in doc_ids:
            raise ValueError("Gold document IDs must be non-empty and unique.")
        doc_ids.add(doc_id)
        source = doc.get("source")
        if not isinstance(source, Mapping) or not isinstance(source.get("source_id"), str) or not isinstance(source.get("text"), str):
            raise ValueError(f"Document {doc_id} is missing a valid source_id or source text.")
        findings = doc.get("gold_findings")
        if not isinstance(findings, list):
            raise TypeError(f"Gold findings for {doc_id} must be an array.")
        for finding in findings:
            if not isinstance(finding, Mapping):
                raise TypeError(f"Gold findings for {doc_id} must contain objects.")
            gold_id = finding.get("gold_id")
            statement, quote = finding.get("statement"), finding.get("quote")
            start, end = finding.get("start_char"), finding.get("end_char")
            if not isinstance(gold_id, str) or not gold_id.strip() or gold_id in gold_ids:
                raise ValueError("Gold finding IDs must be non-empty and globally unique.")
            gold_ids.add(gold_id)
            if not isinstance(statement, str) or not statement.strip() or not isinstance(quote, str) or not quote:
                raise ValueError(f"Gold finding {gold_id} needs non-empty statement and quote text.")
            if isinstance(start, bool) or not isinstance(start, int) or isinstance(end, bool) or not isinstance(end, int):
                raise ValueError(f"Gold finding {gold_id} needs integer source offsets.")
            text = source["text"]
            if start < 0 or end <= start or end > len(text) or text[start:end] != quote:
                raise ValueError(f"Gold finding {gold_id} quote/offset does not match its source text.")
            if finding.get("statement_type") == "source_claim" and statement != quote:
                raise ValueError(f"Gold source_claim {gold_id} must preserve the exact quoted source text.")
    return docs


def evaluate_system(
    gold_set: Mapping[str, Any],
    outputs_by_document: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    system_name: str,
) -> dict[str, Any]:
    """Compare EDD-006-style candidate outputs against exact synthetic gold.

    Claim matching is deliberately conservative: source ID, normalized exact
    statement text, and statement_type must all match. Citation correctness is
    measured independently from claim matching.
    """
    docs = _validate_gold_documents(gold_set)
    if not isinstance(outputs_by_document, Mapping):
        raise TypeError("outputs_by_document must map document IDs to candidate arrays.")

    known_documents = {doc.get("document_id") for doc in docs}
    unknown_outputs = set(outputs_by_document) - known_documents
    if unknown_outputs:
        raise ValueError(f"Predictions reference unknown document IDs: {', '.join(sorted(unknown_outputs))}.")

    all_gold = 0
    true_positive = 0
    predicted_count = 0
    citation_correct = 0
    unsupported_count = 0
    positive_docs = 0
    negative_docs = 0
    false_abstentions = 0
    correct_negative_abstentions = 0
    abstained_docs = 0
    per_document: list[dict[str, Any]] = []

    for doc in docs:
        document_id = doc.get("document_id")
        source = doc.get("source")
        if not isinstance(source, Mapping):
            raise ValueError(f"Document {document_id} is missing its source object.")
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not isinstance(source.get("text"), str):
            raise ValueError(f"Document {document_id} source needs source_id and text.")
        gold_findings = doc.get("gold_findings", [])
        predictions = outputs_by_document.get(document_id, [])
        if not isinstance(gold_findings, list) or not isinstance(predictions, Sequence) or isinstance(predictions, (str, bytes)):
            raise TypeError(f"Gold findings and predictions for {document_id} must be arrays.")
        if any(not isinstance(item, Mapping) for item in gold_findings) or any(not isinstance(item, Mapping) for item in predictions):
            raise TypeError(f"Gold findings and predictions for {document_id} must contain objects.")

        gold_keys = Counter(
            (source_id, _normalize(item.get("statement")), str(item.get("statement_type", "")))
            for item in gold_findings
        )
        all_gold += len(gold_findings)
        is_positive = bool(gold_findings)
        positive_docs += int(is_positive)
        negative_docs += int(not is_positive)
        doc_tp = 0
        doc_citation = 0
        doc_unsupported = 0
        for prediction in predictions:
            predicted_count += 1
            key = _prediction_key(prediction, source_id)
            is_gold_match = gold_keys[key] > 0
            if is_gold_match:
                gold_keys[key] -= 1
                true_positive += 1
                doc_tp += 1
            citation_ok = _citation_is_correct(prediction, source)
            if citation_ok:
                citation_correct += 1
                doc_citation += 1
            if not is_gold_match or not citation_ok:
                unsupported_count += 1
                doc_unsupported += 1

        is_abstention = len(predictions) == 0
        abstained_docs += int(is_abstention)
        if is_abstention and is_positive:
            false_abstentions += 1
        if is_abstention and not is_positive:
            correct_negative_abstentions += 1
        per_document.append({
            "document_id": document_id,
            "gold_count": len(gold_findings),
            "prediction_count": len(predictions),
            "matched_claims": doc_tp,
            "citation_correct": doc_citation,
            "unsupported_claims": doc_unsupported,
            "abstained": is_abstention,
        })

    false_positive = predicted_count - true_positive
    false_negative = all_gold - true_positive
    precision = _ratio(true_positive, predicted_count)
    recall = _ratio(true_positive, all_gold)
    metrics = {
        "documents": len(docs),
        "gold_claims": all_gold,
        "predictions": predicted_count,
        "true_positive_claims": true_positive,
        "false_positive_claims": false_positive,
        "missed_gold_claims": false_negative,
        "extraction_precision": precision,
        "extraction_recall": recall,
        "extraction_f1": _ratio(2 * precision * recall, precision + recall),
        "citation_correctness": _ratio(citation_correct, predicted_count),
        "citation_correct_predictions": citation_correct,
        "unsupported_claim_rate": _ratio(unsupported_count, predicted_count),
        "unsupported_claims": unsupported_count,
        "negative_case_abstention_rate": _ratio(correct_negative_abstentions, negative_docs),
        "positive_case_false_abstention_rate": _ratio(false_abstentions, positive_docs),
        "abstention_precision": _ratio(correct_negative_abstentions, abstained_docs),
        "correct_negative_abstentions": correct_negative_abstentions,
        "negative_documents": negative_docs,
        "positive_documents": positive_docs,
        "abstained_documents": abstained_docs,
    }
    return {"system_name": system_name, "metrics": metrics, "per_document": per_document}


def run_evaluation(
    gold_set: Mapping[str, Any],
    model_predictions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run EDD-006's built-in rule baseline and optionally score model output."""
    if not isinstance(gold_set, Mapping):
        raise TypeError("gold_set must be an object.")
    if gold_set.get("synthetic") is not True:
        raise ValueError("This evaluator requires an explicitly synthetic gold set.")
    if model_predictions is not None and not isinstance(model_predictions, Mapping):
        raise TypeError("model_predictions must be an object.")
    documents = _validate_gold_documents(gold_set)
    if not any(doc.get("gold_findings") for doc in documents) or not any(not doc.get("gold_findings") for doc in documents):
        raise ValueError("Evaluation gold set must include both positive and negative documents.")

    baseline_outputs: dict[str, list[dict[str, Any]]] = {}
    for doc in documents:
        source_data = doc["source"]
        source = SourceDocument(
            source_id=source_data["source_id"],
            text=source_data["text"],
            title=source_data.get("title", ""),
            reference=source_data.get("reference"),
            url=source_data.get("url"),
            evidence_id=source_data.get("evidence_id"),
            claim_reference=source_data.get("claim_reference"),
            finding_reference=source_data.get("finding_reference"),
            source_type=source_data.get("source_type"),
        )
        result = extract_findings([source])
        baseline_outputs[doc["document_id"]] = result.to_dict()["findings"]

    results = [evaluate_system(gold_set, baseline_outputs, system_name="EDD-006 rule baseline")]
    if model_predictions is not None:
        predictions_by_doc = model_predictions.get("predictions_by_document", {})
        results.append(evaluate_system(
            gold_set,
            predictions_by_doc,
            system_name=str(model_predictions.get("system_name", "optional candidate system")),
        ))
    return {
        "evaluation_version": "1.0.0",
        "gold_set_version": gold_set.get("gold_set_version", "Not provided"),
        "dataset_version": gold_set.get("dataset_version", "Not provided"),
        "synthetic": True,
        "matching_rule": "Exact normalized statement + source_id + statement_type; one-to-one matching.",
        "citation_rule": "source_id must match the document and source_text[start_char:end_char] must equal the quote.",
        "results": results,
        "limitations": [
            "This small synthetic set is an engineering smoke test, not a representative sample or production-readiness evaluation.",
            "Exact-string matching does not measure semantic equivalence; paraphrases are not credited as extracted claims.",
            "A correct quote and offset do not prove that a claim is entailed by the passage.",
            "The optional bundled mock predictions are illustrative and are not outputs from an actual language model.",
        ],
    }


def render_results_markdown(results: Mapping[str, Any]) -> str:
    """Render compact reproducible metric results and limitations as Markdown."""
    columns = [
        ("System", "system_name"),
        ("Precision", "extraction_precision"),
        ("Recall", "extraction_recall"),
        ("Citation correctness", "citation_correctness"),
        ("Unsupported-claim rate", "unsupported_claim_rate"),
        ("Negative abstention", "negative_case_abstention_rate"),
        ("False abstention", "positive_case_false_abstention_rate"),
        ("Abstention precision", "abstention_precision"),
    ]
    lines = [
        "# G4F-EDD-009 Evaluation Results", "",
        f"- Evaluation version: {results.get('evaluation_version')}",
        f"- Gold-set version: {results.get('gold_set_version')}",
        f"- Dataset version: {results.get('dataset_version')}",
        "- Data: synthetic", "",
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for result in results.get("results", []):
        metric = result["metrics"]
        row = [result["system_name"]] + [f"{metric[key]:.3f}" for _, key in columns[1:]]
        lines.append("| " + " | ".join(row) + " |")
    lines.extend(["", "## Additional counts", ""])
    for result in results.get("results", []):
        metric = result["metrics"]
        matched_word = "claim" if metric["true_positive_claims"] == 1 else "claims"
        lines.append(
            f"- **{result['system_name']}:** {metric['true_positive_claims']} matched {matched_word}; "
            f"{metric['false_positive_claims']} extra claims; {metric['missed_gold_claims']} missed gold claims; "
            f"{metric['citation_correct_predictions']}/{metric['predictions']} citations structurally correct; "
            f"{metric['correct_negative_abstentions']}/{metric['negative_documents']} negative documents abstained."
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in results.get("limitations", []))
    lines.append("")
    return "\n".join(lines)
