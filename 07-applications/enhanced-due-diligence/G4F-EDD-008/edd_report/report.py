"""Build evidence-linked EDD reports without making final risk decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping, Sequence


REPORT_VERSION = "1.0.0"
_MISSING = "Not provided"


def _text(value: Any) -> str:
    if value is None or value == "":
        return _MISSING
    if isinstance(value, (dict, list)):
        return str(value)
    return str(value)


def _markdown(value: Any) -> str:
    """Escape untrusted input for safe, readable Markdown text/table cells."""
    return (escape(_text(value), quote=False)
            .replace("\\", "\\\\")
            .replace("|", "\\|")
            .replace("`", "\\`")
            .replace("*", "\\*")
            .replace("_", "\\_")
            .replace("[", "\\[")
            .replace("]", "\\]"))


def _code(value: Any) -> str:
    """Render a literal Markdown code span without escaping identifier underscores."""
    text = _text(value).replace("`", "\\`")
    return f"`{text}`"


def _sequence(value: Any, name: str) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a list of objects.")
    if any(not isinstance(item, Mapping) for item in value):
        raise TypeError(f"Every item in {name} must be an object.")
    return list(value)


def _timestamp(generated_at: str | None) -> str:
    if generated_at is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if not isinstance(generated_at, str):
        raise TypeError("generated_at must be an ISO-8601 timestamp string.")
    try:
        parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("generated_at must be an ISO-8601 timestamp with timezone.") from error
    if parsed.tzinfo is None:
        raise ValueError("generated_at must include a timezone.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _source_label(record: Mapping[str, Any]) -> str:
    return str(record.get("evidence_id") or record.get("source_id") or "Source ID not provided")


def _evidence_reference(record: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve relevant citation/provenance values from EDD-001/002 records."""
    if "evidence_id" in record:
        return {
            "evidence_id": record.get("evidence_id"),
            "claim_reference": record.get("claim_reference"),
            "finding_reference": record.get("finding_reference"),
            "title": record.get("title"),
            "publisher": record.get("publisher"),
            "url": record.get("url"),
            "reference": record.get("reference"),
            "publication_date": record.get("publication_date"),
            "access_date": record.get("access_date"),
            "source_type": record.get("source_type"),
            "source_classification": record.get("source_classification"),
            "jurisdiction": record.get("jurisdiction"),
            "evidence_status": record.get("evidence_status"),
            "excerpt_or_summary": record.get("excerpt_or_summary"),
            "provenance_notes": record.get("provenance_notes"),
            "limitations": record.get("limitations", []),
        }
    return {
        "source_id": record.get("source_id"),
        "title": record.get("description") or record.get("title"),
        "source_type": record.get("source_type"),
        "publisher": record.get("publisher"),
        "url": record.get("url"),
        "checked_date": record.get("checked_date"),
        "reference": record.get("reference"),
        "publication_date": record.get("publication_date"),
        "access_date": record.get("access_date"),
        "source_classification": record.get("source_classification"),
        "jurisdiction": record.get("jurisdiction"),
        "evidence_status": record.get("evidence_status"),
        "excerpt_or_summary": record.get("excerpt_or_summary"),
        "provenance_notes": record.get("provenance_notes"),
        "limitations": record.get("limitations", []),
    }


def build_report_data(
    case_record: Mapping[str, Any] | Mapping[str, Any],
    *,
    evidence_records: Sequence[Mapping[str, Any]] | None = None,
    source_records: Sequence[Mapping[str, Any]] | None = None,
    extraction_result: Mapping[str, Any] | None = None,
    evidence_review: Mapping[str, Any] | None = None,
    subject_entity: Mapping[str, Any] | None = None,
    scope: str | None = None,
    unresolved_questions: Sequence[str] | None = None,
    limitations: Sequence[str] | None = None,
    recommended_actions: Sequence[str] | None = None,
    dataset_version: str | None = None,
    synthetic: bool | None = None,
    dataset_case_index: int = 0,
    report_version: str = REPORT_VERSION,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Create normalized report data from EDD-001 plus EDD-002/006/007 inputs.

    `case_record` may be an EDD-001 case object or an EDD-004 case bundle that
    contains `case_record`. A case finding is included as a substantive finding
    only when an EDD-002 record or EDD-006 candidate explicitly points to its
    `finding_id`; otherwise its summary is withheld and listed as unlinked.
    """
    if not isinstance(case_record, Mapping):
        raise TypeError("case_record must be an object.")
    dataset_bundle = case_record
    dataset_case: Mapping[str, Any] = {}
    if isinstance(case_record.get("cases"), Sequence) and not isinstance(case_record.get("cases"), (str, bytes)):
        cases = case_record["cases"]
        if isinstance(dataset_case_index, bool) or not isinstance(dataset_case_index, int) or not 0 <= dataset_case_index < len(cases):
            raise IndexError("dataset_case_index is outside the dataset cases array.")
        dataset_case = cases[dataset_case_index]
        if not isinstance(dataset_case, Mapping) or not isinstance(dataset_case.get("case_record"), Mapping):
            raise ValueError("Selected EDD-004 dataset item must contain an EDD-001 case_record.")
        case_record = dataset_case["case_record"]
        if dataset_version is None:
            dataset_version = dataset_bundle.get("dataset_version")
        if source_records is None:
            source_records = dataset_case.get("source_records", case_record.get("source_records", []))
    if isinstance(case_record.get("case_record"), Mapping):
        dataset_case = case_record
        case_record = case_record["case_record"]
        if source_records is None:
            source_records = dataset_case.get("source_records", case_record.get("source_records", []))
        if dataset_version is None:
            dataset_version = dataset_bundle.get("dataset_version")
    if not isinstance(case_record, Mapping):
        raise TypeError("case_record must contain an EDD-001 case object.")
    if subject_entity is not None and not isinstance(subject_entity, Mapping):
        raise TypeError("subject_entity must be an object.")
    subject_entity = subject_entity or dataset_case.get("subject_entity", {})
    if not isinstance(report_version, str) or not report_version.strip():
        raise ValueError("report_version must be a non-empty string.")

    evidence = _sequence(evidence_records, "evidence_records")
    sources = _sequence(source_records if source_records is not None else case_record.get("source_records", []), "source_records")
    findings_in = _sequence(case_record.get("findings", []), "case_record.findings")
    questions = list(unresolved_questions or [])
    limits = list(limitations or [])
    actions = list(recommended_actions or [])
    if any(not isinstance(item, str) or not item.strip() for item in questions + limits + actions):
        raise ValueError("Questions, limitations, and recommended actions must be non-empty strings.")

    candidates = []
    if extraction_result is not None:
        if not isinstance(extraction_result, Mapping):
            raise TypeError("extraction_result must be an object.")
        candidates = _sequence(extraction_result.get("findings", []), "extraction_result.findings")
    candidate_links: dict[str, list[dict[str, Any]]] = {}
    independent_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        src = candidate.get("source_reference")
        quote = candidate.get("evidence")
        if not isinstance(src, Mapping) or not any(
            isinstance(src.get(key), str) and src[key].strip() for key in ("source_id", "evidence_id")
        ) or not isinstance(quote, Mapping) or not isinstance(quote.get("quote"), str) or not quote.get("quote"):
            # An untraceable extractor result is not rendered as a substantive statement.
            continue
        start, end = quote.get("start_char"), quote.get("end_char")
        if (isinstance(start, bool) or not isinstance(start, int) or isinstance(end, bool)
                or not isinstance(end, int) or start < 0 or end <= start
                or end - start != len(quote["quote"])):
            continue
        entry = {
            "candidate_id": candidate.get("finding_id"),
            "statement": candidate.get("statement"),
            "statement_type": candidate.get("statement_type"),
            "review_status": candidate.get("review_status"),
            "source_reference": dict(src),
            "evidence": dict(quote),
        }
        linked_id = src.get("finding_reference")
        if isinstance(linked_id, str) and linked_id:
            candidate_links.setdefault(linked_id, []).append(entry)
        else:
            independent_candidates.append(entry)

    linked_findings: list[dict[str, Any]] = []
    unlinked_findings: list[dict[str, Any]] = []
    for finding in findings_in:
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or not finding_id:
            raise ValueError("Every case finding needs a non-empty finding_id.")
        linked_evidence = [record for record in evidence if record.get("finding_reference") == finding_id]
        linked_candidates = candidate_links.get(finding_id, [])
        usable_evidence = [
            record for record in linked_evidence
            if "generated" not in (record.get("source_classification") or [])
            and record.get("evidence_status") != "unavailable"
        ]
        has_source_passage = any(
            candidate.get("statement_type") == "source_claim"
            and candidate.get("statement") == candidate.get("evidence", {}).get("quote")
            and candidate.get("review_status") == "source_backed_candidate"
            for candidate in linked_candidates
        )
        if not usable_evidence and not has_source_passage:
            if linked_evidence or linked_candidates:
                issue = "Only unavailable/generated evidence or a non-source-claim candidate is linked; summary withheld pending source support."
                question = f"Does a source passage directly support case finding {finding_id}?"
                action = f"Substantiate case finding {finding_id} using reviewable source evidence; model output alone is not sufficient."
            else:
                issue = "No non-generated evidence record or cited passage is linked; summary withheld."
                question = f"Provide or confirm a source reference for case finding {finding_id}."
                action = f"Link and review source evidence for case finding {finding_id} before relying on it."
            unlinked_findings.append({
                "finding_id": finding_id,
                "category": finding.get("category"),
                "issue": issue,
            })
            questions.append(question)
            actions.append(action)
            continue
        linked_findings.append({
            "finding_id": finding_id,
            "category": finding.get("category"),
            "summary": finding.get("summary"),
            "severity": finding.get("severity"),
            "disposition": finding.get("disposition"),
            "evidence_records": [_evidence_reference(record) for record in linked_evidence],
            "extractor_candidates": linked_candidates,
            "evidence_note": "Case-record summary is reproduced as supplied and is not an independent verification.",
        })

    if not sources and not evidence:
        limits.append("No source or evidence records were provided to the report generator.")
    if extraction_result and extraction_result.get("status") == "insufficient_evidence":
        limits.append("EDD-006 returned insufficient_evidence for the supplied extraction input.")
    if candidates:
        limits.append("Extractor quotes and offsets are reproduced from EDD-006 output; this report does not revalidate them against the original source text.")

    status_issues: list[dict[str, Any]] = []
    if evidence_review is not None:
        if not isinstance(evidence_review, Mapping):
            raise TypeError("evidence_review must be an object.")
        status_issues.extend(_sequence(evidence_review.get("conflicts", []), "evidence_review.conflicts"))
        status_issues.extend(_sequence(evidence_review.get("stale_evidence", []), "evidence_review.stale_evidence"))
        status_issues.extend(_sequence(evidence_review.get("evidence_status_issues", []), "evidence_review.evidence_status_issues"))
        for conflict in evidence_review.get("conflicts", []):
            questions.append(f"Resolve the conflicting {conflict.get('attribute', 'value')} observations for {conflict.get('subject_id', 'the subject')}.")
            actions.append(f"Human-review the conflicting {conflict.get('attribute', 'value')} observations; preserve all sources until resolved.")
        for stale_item in evidence_review.get("stale_evidence", []):
            observation = stale_item.get("observation", {})
            actions.append(f"Refresh or confirm evidence for observation {observation.get('observation_id', 'ID not provided')}.")

    for record in evidence:
        status = record.get("evidence_status")
        if status in {"unavailable", "disputed", "outdated"}:
            questions.append(f"Review evidence record {_source_label(record)} marked {status}.")
            if status == "unavailable":
                actions.append(f"Obtain and inspect evidence record {_source_label(record)} before relying on its contents.")
            else:
                actions.append(f"Resolve or qualify evidence record {_source_label(record)} marked {status}.")
        for caveat in record.get("limitations", []) or []:
            if isinstance(caveat, str) and caveat.strip():
                limits.append(f"{_source_label(record)}: {caveat}")

    # Keep first occurrence while retaining order for a stable report.
    questions = list(dict.fromkeys(questions))
    limits = list(dict.fromkeys(limits))
    actions = list(dict.fromkeys(actions))
    subject_summary = {
        "subject_type": case_record.get("subject_type"),
        "subject_name": (case_record.get("subject_name") or case_record.get("subject_name_display")
                         or subject_entity.get("synthetic_name")),
        "subject_id": (case_record.get("subject_id")
                       or subject_entity.get("entity_id")),
        "jurisdiction": case_record.get("jurisdiction"),
        "review_date": case_record.get("review_date"),
        "case_review_status": case_record.get("review_status"),
        "risk_categories": case_record.get("risk_categories"),
        "case_confidence": case_record.get("confidence"),
    }
    return {
        "report_version": report_version,
        "dataset_version": dataset_version,
        "generated_at": _timestamp(generated_at),
        "synthetic": bool(dataset_bundle.get("synthetic", False) if synthetic is None else synthetic),
        "case_id": case_record.get("case_id"),
        "scope": scope,
        "subject_summary": subject_summary,
        "findings": linked_findings,
        "unlinked_findings": unlinked_findings,
        "source_records": [_evidence_reference(record) for record in sources],
        "evidence_records": [_evidence_reference(record) for record in evidence],
        "extractor_candidates": independent_candidates,
        "unresolved_questions": questions,
        "limitations": limits,
        "recommended_actions": actions,
        "evidence_review_items": status_issues,
    }


def _list(values: Sequence[Any], empty_text: str) -> str:
    if not values:
        return f"- {empty_text}\n"
    return "".join(f"- {_markdown(item)}\n" for item in values)


def _render_reference(record: Mapping[str, Any]) -> str:
    ident = record.get("evidence_id") or record.get("source_id") or "ID not provided"
    title = record.get("title") or "Title not provided"
    classification = record.get("source_classification")
    classification_text = f"; classification: {_markdown(classification)}" if classification else ""
    return (f"**{_markdown(ident)}** — {_markdown(title)}; "
            f"type: {_markdown(record.get('source_type'))}; "
            f"status: {_markdown(record.get('evidence_status'))}; "
            f"checked/accessed: {_markdown(record.get('access_date') or record.get('checked_date'))}; "
            f"URL/reference: {_markdown(record.get('url') or record.get('reference'))}{classification_text}")


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render report data as Markdown, with source quotes clearly attributed."""
    lines = [
        f"# EDD Review Report — {_markdown(report.get('case_id'))}", "",
        "> This report organizes supplied review data. It does not make a final risk, compliance, onboarding, or enforcement decision.", "",
        "## Report metadata", "",
        f"- Report version: {_markdown(report.get('report_version'))}",
        f"- Dataset version: {_markdown(report.get('dataset_version'))}",
        f"- Generated at (UTC): {_markdown(report.get('generated_at'))}",
        f"- Synthetic dataset: {'Yes' if report.get('synthetic') else 'Not marked synthetic'}", "",
        "## Scope", "", _markdown(report.get("scope")), "",
        "## Subject summary", "",
    ]
    for label, key in (("Subject type", "subject_type"), ("Subject name", "subject_name"),
                       ("Subject ID", "subject_id"), ("Jurisdiction", "jurisdiction"),
                       ("Review date", "review_date"), ("Case review status (from input)", "case_review_status")):
        lines.append(f"- {label}: {_markdown(report['subject_summary'].get(key))}")
    categories = report["subject_summary"].get("risk_categories")
    lines.append(f"- Risk categories recorded in case file: {_markdown(categories)}")
    lines.append(f"- Case confidence (input value; not recalculated): {_markdown(report['subject_summary'].get('case_confidence'))}")
    lines.extend(["", "## Findings", ""])
    findings = report.get("findings", [])
    if not findings:
        lines.append("No evidence-linked case findings were supplied.")
    for finding in findings:
        lines.extend([
            f"### {_markdown(finding.get('finding_id'))} — {_markdown(finding.get('category'))}", "",
            f"- Summary from case record: {_markdown(finding.get('summary'))}",
            f"- Severity from case record: {_markdown(finding.get('severity'))}",
            f"- Disposition from case record: {_markdown(finding.get('disposition'))}",
            f"- Evidence note: {_markdown(finding.get('evidence_note'))}",
            "- Linked evidence:",
        ])
        refs = finding.get("evidence_records", [])
        if refs:
            lines.extend(f"  - {_render_reference(ref)}" for ref in refs)
            for ref in refs:
                if ref.get("excerpt_or_summary"):
                    lines.append(f"    - Source-record excerpt/summary (as recorded): {_markdown(ref.get('excerpt_or_summary'))}")
                classifications = ref.get("source_classification") or []
                if "generated" in classifications:
                    lines.append("    - Classification includes `generated`; not independent source evidence.")
        for candidate in finding.get("extractor_candidates", []):
            candidate_type = candidate.get("statement_type")
            candidate_label = (
                "Model-generated/inferred candidate"
                if candidate_type in {"model_inference", "extracted_fact", "unresolved"}
                else "Source-claim candidate"
            )
            lines.extend([
                f"- {candidate_label} ({_markdown(candidate.get('statement_type'))}; {_markdown(candidate.get('review_status'))}): {_markdown(candidate.get('statement'))}",
                f"  - Source reference: {_markdown(candidate.get('source_reference'))}",
                f"  - Supporting source passage: {_markdown(candidate.get('evidence', {}).get('quote'))}",
                f"  - Passage offsets: {candidate.get('evidence', {}).get('start_char', _MISSING)}–{candidate.get('evidence', {}).get('end_char', _MISSING)}",
            ])
        lines.append("")

    lines.extend(["## Findings without an evidence link", ""])
    if report.get("unlinked_findings"):
        lines.append("These case finding summaries are withheld because qualifying source evidence was not available:")
        for item in report["unlinked_findings"]:
            lines.append(f"- {_markdown(item.get('finding_id'))} ({_markdown(item.get('category'))}): {_markdown(item.get('issue'))}")
    else:
        lines.append("None.")
    lines.extend(["", "## Extractor outputs not adopted as case findings", ""])
    if report.get("extractor_candidates"):
        lines.append("These are candidate outputs, not approved case findings:")
        for candidate in report["extractor_candidates"]:
            stype = candidate.get("statement_type")
            label = "Model-generated/inferred candidate" if stype in {"model_inference", "extracted_fact", "unresolved"} else "Source-claim candidate"
            lines.extend([
                f"- **{label}** ({_markdown(candidate.get('candidate_id'))}; type: {_markdown(stype)}; review: {_markdown(candidate.get('review_status'))}): {_markdown(candidate.get('statement'))}",
                f"  - Source: {_markdown(candidate.get('source_reference'))}",
                f"  - Exact cited passage: {_markdown(candidate.get('evidence', {}).get('quote'))}",
                f"  - Passage offsets: {candidate.get('evidence', {}).get('start_char', _MISSING)}–{candidate.get('evidence', {}).get('end_char', _MISSING)}",
            ])
    else:
        lines.append("None provided.")
    lines.extend(["", "## Source references", ""])
    refs = report.get("evidence_records", []) + report.get("source_records", [])
    if refs:
        for ref in refs:
            lines.append(f"- {_render_reference(ref)}")
            if ref.get("excerpt_or_summary"):
                lines.append(f"  - Excerpt/summary (as recorded): {_markdown(ref.get('excerpt_or_summary'))}")
            if ref.get("provenance_notes"):
                lines.append(f"  - Provenance: {_markdown(ref.get('provenance_notes'))}")
    else:
        lines.append("No source records provided.")
    lines.extend(["", "## Contradiction and freshness checks", ""])
    review_items = report.get("evidence_review_items", [])
    if not review_items:
        lines.append("No EDD-007 review output supplied.")
    for item in review_items:
        if "attribute" in item and "values" in item:
            lines.append(
                f"- **Unresolved conflict** for {_markdown(item.get('subject_id'))}, "
                f"attribute {_markdown(item.get('attribute'))}; resolution: "
                f"{_code(item.get('resolution') or 'unresolved_requires_human_review')}."
            )
            for value_group in item.get("values", []):
                lines.append(f"  - Value: {_markdown(value_group.get('normalized_value', value_group.get('value')))}")
                for observation in value_group.get("observations", []):
                    lines.append(
                        f"    - Observation {_markdown(observation.get('observation_id'))}: "
                        f"{_markdown(observation.get('value'))}; source reference: "
                        f"{_markdown(observation.get('source_reference'))}"
                    )
        elif "reason" in item:
            observation = item.get("observation", {})
            lines.append(
                f"- **Stale or undated evidence** for observation "
                f"{_markdown(observation.get('observation_id'))}: "
                f"{_markdown(item.get('reason'))}; age: {_markdown(item.get('age_days'))} days; "
                f"maximum: {_markdown(item.get('max_age_days'))} days; source: "
                f"{_markdown(observation.get('source_reference'))}"
            )
        else:
            lines.append(
                f"- **Evidence status issue**: {_markdown(item.get('issue'))}; source: "
                f"{_markdown(item.get('observation', {}).get('source_reference'))}"
            )
    lines.extend(["", "## Unresolved questions", "", _list(report.get("unresolved_questions", []), "None provided; this does not mean all questions were resolved.").rstrip(), "",
                  "## Limitations", "", _list(report.get("limitations", []), "No additional limitations supplied; assess source quality and completeness independently.").rstrip(), "",
                  "## Recommended review actions", "", _list(report.get("recommended_actions", []), "No review actions supplied.").rstrip(), "",
                  "## Decision boundary", "", "No overall accusation, risk rating, or automatic final decision is generated by this report.", ""])
    return "\n".join(lines)


def generate_report(case_record: Mapping[str, Any], **kwargs: Any) -> str:
    """Convenience function returning a rendered Markdown report."""
    return render_markdown(build_report_data(case_record, **kwargs))
