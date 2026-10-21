
# G4F-EDD-003: EDD Review Checklist

| Checklist version | 1.0 |
|---|---|
| Checklist effective/review date | |

## 1. Purpose and Use

This jurisdiction-neutral checklist helps reviewers plan and document an Enhanced Due Diligence (EDD) review of an individual, company, organization, trust, or other relevant subject.

It defines what to verify, what evidence to record, which checks depend on jurisdiction, data access, or institutional policy, and when human review is required.

This checklist complements:

- **G4F-EDD-001:** EDD case data schema.
- **G4F-EDD-002:** Source and evidence record format.

The checklist supports consistent documentation. It is not a risk score, legal advice, an approval decision, or a substitute for applicable law and institutional procedures.

Do not collect more personal or confidential information than the review purpose and applicable rules permit.

## 2. Dependency Labels

- **Core:** A general evidence-handling or review check. The work still depends on the review scope and available evidence.
- **Jurisdiction-dependent:** Confirm local definitions, legal requirements, permitted sources, restrictions, and retention rules before performing or interpreting the check.
- **Data-dependent:** Perform only where relevant records or tools are lawfully available. Document access limitations and do not treat a failed search as a negative result.
- **Policy-dependent:** Follow the institution's approved procedures, thresholds, risk appetite, escalation paths, and handling requirements.

Multiple labels may apply to the same check. These labels identify dependencies; they do not independently authorize a search or create a legal obligation.

## 3. Review Header

Complete the following information for each review.

| Field | Reviewer entry |
|---|---|
| Case ID | |
| Subject type | `individual`, `company`, `organization`, `trust`, or `other` |
| Review purpose and scope | |
| Jurisdiction | Two-letter ISO 3166-1 alpha-2 country code in the EDD-001 case record |
| Reviewer reference | |
| Review date | YYYY-MM-DD |
| Checklist version | 1.0 |
| Applicable policy/procedure and version | |
| Data-access constraints or approved tools | |
| Review status | `pending`, `in_review`, `completed`, or `escalated` |

Use the case ID and review status defined by G4F-EDD-001. Do not use the checklist version or an evidence ID as the case ID.

### 3.1 Checklist Outcome Definitions

Use these outcomes for individual checks:

| Outcome | Meaning |
|---|---|
| `clear` | The check was completed within its documented scope and no relevant issue was identified. |
| `potential_match_issue` | A potential match, discrepancy, or other concern requires assessment. |
| `not_applicable` | The check does not apply; document the reason. |
| `unable_to_assess` | The check could not be completed sufficiently; document the reason and impact. |

These are checklist-specific outcomes. They are not values for the EDD-001 `review_status` field or the EDD-002 `evidence_status` field.

A clear result does not prove that no relevant issue exists.

## 4. Identity and Entity Resolution

**Objective:** Verify the identity or legal existence of the subject and distinguish it from similarly named people or entities.

### EDD-CHK-001 — Confirm identity or legal existence

**Dependencies:** Core; data-dependent; jurisdiction-dependent.

- Verify available identifying attributes using authoritative or otherwise suitable permitted sources.
- For individuals, consider permitted identifiers such as name, aliases, or other appropriate distinguishing attributes.
- For entities, consider legal name, registration number, registered status, formation jurisdiction, and other available identifiers.
- Record the identifiers checked, source references, retrieval date, discrepancies, and limitations.
- Minimize or mask sensitive identifiers in reviewer notes.

### EDD-CHK-002 — Search relevant name forms

**Dependencies:** Core; data-dependent; policy-dependent.

- Check relevant aliases, spelling variations, former names, trading names, and transliterations where appropriate.
- Record search terms, source or tool, date, and results.
- Note language or transliteration limitations and potential false positives.

### EDD-CHK-003 — Resolve candidate matches

**Dependencies:** Core; data-dependent; policy-dependent.

- Compare multiple distinguishing attributes rather than relying on name similarity alone.
- Record attributes supporting or contradicting a match, source references, and the rationale.
- Keep ambiguous results unresolved and escalate them according to applicable procedures.

### EDD-CHK-004 — Verify current status and identity continuity

**Dependencies:** Jurisdiction-dependent; data-dependent.

- Where relevant, check whether an entity is active, dissolved, renamed, merged, or otherwise changed.
- For individuals, verify relevant changes in identity status only where appropriate and lawfully accessible.
- Record the source's as-of date and any gap between the source date and review date.

## 5. Ownership, Control, and Beneficial Ownership

**Objective:** Understand relevant ownership layers, control relationships, and beneficial owners.

### EDD-CHK-005 — Map direct and indirect ownership

**Dependencies:** Core; data-dependent; jurisdiction-dependent.

- Identify relevant owners, ownership layers, percentages, or other interests.
- Record the source and as-of date for each material relationship.
- Document missing links and whether the ownership chain is independently corroborated.

### EDD-CHK-006 — Identify persons exercising control

**Dependencies:** Core; jurisdiction-dependent; data-dependent; policy-dependent.

- Examine relevant voting rights, appointment or removal rights, agreements, management roles, or other control mechanisms.
- Record the basis for identifying each controller and the evidence supporting the relationship.
- Distinguish verified control from assumptions or unresolved possibilities.

### EDD-CHK-007 — Identify beneficial owners

**Dependencies:** Jurisdiction-dependent; data-dependent; policy-dependent.

- Apply the relevant local definition, threshold, and institutional policy.
- Record the rule or policy version used, the basis for identification, supporting sources, and any exceptions or gaps.
- Do not assume a single global ownership threshold or treat missing information as proof that no beneficial owner exists.

### EDD-CHK-008 — Review trusts, nominees, and complex arrangements

**Dependencies:** Jurisdiction-dependent; data-dependent; policy-dependent.

- Where relevant, examine documented roles such as settlor, trustee, protector, beneficiaries or beneficiary class, nominee, and parties exercising effective control.
- Record the documentation reviewed and the roles or relationships that remain unknown.
- Follow applicable restrictions on access to and recording of trust or personal information.

### EDD-CHK-009 — Reconcile ownership information

**Dependencies:** Core; data-dependent.

- Compare declarations, registry data, corporate documents, and other permitted sources.
- Record conflicting figures, source dates, and how discrepancies were resolved or escalated.
- Identify material ownership information that remains unverified.

## 6. Sanctions Screening

**Objective:** Identify and appropriately assess potential matches against sanctions sources relevant to the review.

### EDD-CHK-010 — Identify applicable sanctions sources

**Dependencies:** Jurisdiction-dependent; data-dependent; policy-dependent.

- Identify the official sanctions lists or approved screening sources relevant under applicable law and institutional policy.
- Record source name, issuing authority or jurisdiction, list version or last-update information where available, and date checked.
- Document required sources that were inaccessible.

### EDD-CHK-011 — Screen the subject and relevant connected parties

**Dependencies:** Jurisdiction-dependent; data-dependent; policy-dependent.

- Check relevant names, aliases, and identifying attributes against the applicable sources.
- Record the parties and identifiers searched, date, tool or list, and result.
- Document search limitations, including transliteration issues and unavailable data.

### EDD-CHK-012 — Evaluate potential matches

**Dependencies:** Jurisdiction-dependent; data-dependent; policy-dependent.

- Compare available identifiers and contextual information with the listed party.
- Record matching and conflicting attributes, relevant source references, and the rationale.
- Distinguish a potential match from a confirmed identity match.
- Escalate unresolved matches according to approved procedures.

### EDD-CHK-013 — Assess ownership and control implications

**Dependencies:** Jurisdiction-dependent; data-dependent; policy-dependent.

- Where relevant, assess ownership or control relationships under the applicable legal framework and institutional policy.
- Record the rule or policy used and the evidence supporting the assessment.
- Escalate unresolved legal or policy interpretation.

### EDD-CHK-014 — Document screening limitations and disposition

**Dependencies:** Core; data-dependent; policy-dependent.

- Record unavailable lists, inaccessible tools, stale data, failed searches, or incomplete coverage.
- Document the reviewer’s assessment and outstanding follow-up.
- Do not treat a failed search or unavailable source as a no-match result.

## 7. Politically Exposed Person (PEP) Indicators

**Objective:** Identify relevant PEP indicators where required and assess them in context.

### EDD-CHK-015 — Determine whether PEP review applies

**Dependencies:** Jurisdiction-dependent; policy-dependent.

- Confirm the applicable definition, covered roles, relevant family or close-associate scope, and treatment of former public officials.
- Record the applicable rule or policy version.
- Document why the check is applicable or not applicable.

### EDD-CHK-016 — Assess a potential PEP match

**Dependencies:** Jurisdiction-dependent; data-dependent; policy-dependent.

- Verify the identity, relevant public role, jurisdiction, dates, status, and relationship basis using suitable sources.
- Record distinguishing attributes, source dates, and unresolved uncertainty.
- Do not infer PEP status from a name or title alone.

### EDD-CHK-017 — Document required follow-up

**Dependencies:** Jurisdiction-dependent; policy-dependent.

- Record additional review, approvals, or enhanced measures required by the applicable framework.
- Document the rationale and outstanding items.
- Avoid collecting unnecessary sensitive information.

PEP status alone is not evidence of misconduct.

## 8. Adverse Media

**Objective:** Identify and evaluate credible information relevant to financial crime, integrity, or other risks within the review scope.

### EDD-CHK-018 — Conduct scoped searches

**Dependencies:** Data-dependent; jurisdiction-dependent; policy-dependent.

- Search permitted, relevant sources using appropriate names, aliases, and identifiers.
- Record the search tool or source, search date, exact terms where permitted, language or regional limits, and scope.
- Follow applicable privacy and data-access restrictions.

### EDD-CHK-019 — Assess identity match and source quality

**Dependencies:** Core; data-dependent; policy-dependent.

- Distinguish the subject from namesakes using relevant identifying attributes.
- Record publisher, publication date, source type, relevant summary, and supporting evidence.
- Note whether an article is original reporting or repeats another source.
- Assess source credibility and attribution without assuming that publication establishes truth.

### EDD-CHK-020 — Assess allegations, context, and outcome

**Dependencies:** Data-dependent; jurisdiction-dependent; policy-dependent.

- Record the specific allegation or reported event and its source.
- Where verifiable, document whether the matter is alleged, investigated, charged, adjudicated, corrected, withdrawn, or otherwise resolved.
- Record dates, relevant outcomes, responses, and contrary evidence.
- Do not present allegations as established facts.

### EDD-CHK-021 — Assess relevance and recency

**Dependencies:** Core; policy-dependent.

- Explain why the information is relevant or not relevant to the review.
- Record whether the information remains current and whether subsequent developments were checked.
- Document uncertainty and limitations.

## 9. Litigation and Regulatory Actions

**Objective:** Identify relevant legal proceedings, regulatory actions, and official records within the review scope.

### EDD-CHK-022 — Search relevant official records

**Dependencies:** Jurisdiction-dependent; data-dependent; policy-dependent.

- Identify relevant court, insolvency, regulator, enforcement, or other official records.
- Record the authority, search date, identifiers, case or reference number, and source.
- Document coverage limitations and unavailable records.

### EDD-CHK-023 — Confirm the subject and procedural status

**Dependencies:** Jurisdiction-dependent; data-dependent.

- Confirm the subject's involvement and distinguish similarly named parties.
- Record the subject's role, nature of the proceeding, relevant dates, current status, and verified outcome.
- Distinguish allegations, investigations, charges, judgments, settlements, and enforcement actions.

### EDD-CHK-024 — Assess materiality and current effect

**Dependencies:** Jurisdiction-dependent; policy-dependent.

- Explain the relevance of the matter to the review purpose.
- Record any verified restrictions, obligations, unresolved questions, and required follow-up.
- Escalate legal interpretations outside the reviewer's authority or expertise.

A filing or allegation alone does not establish liability.

## 10. Related Entities and Connected Parties

**Objective:** Identify relevant relationships that may affect the subject's assessment.

### EDD-CHK-025 — Identify relevant relationships

**Dependencies:** Core; data-dependent; policy-dependent.

- Consider parent companies, subsidiaries, affiliates, directors, owners, controllers, and other parties relevant to the review.
- Record the relationship type, supporting source, and effective dates where available.
- Explain why the relationship is within scope.

### EDD-CHK-026 — Review connected parties where appropriate

**Dependencies:** Jurisdiction-dependent; data-dependent; policy-dependent.

- Screen or review relevant connected parties only where justified and permitted.
- Record the reason for inclusion, sources searched, and match rationale.
- Do not attribute an associated party's conduct to the subject without supporting evidence and an applicable basis.

### EDD-CHK-027 — Assess common-control or network indicators

**Dependencies:** Data-dependent; policy-dependent.

- Document specific ownership, management, control, or other material links.
- Separate verified relationships from hypotheses.
- Record missing links, conflicting records, and unresolved questions.

## 11. Geographic and Financial Crime Risk Indicators

**Objective:** Document relevant geographic and financial crime indicators without treating them as proof of wrongdoing.

### EDD-CHK-028 — Review geographic exposure

**Dependencies:** Jurisdiction-dependent; data-dependent; policy-dependent.

- Identify relevant jurisdictions associated with the subject or its activities.
- Assess materiality under the applicable legal framework and institutional policy.
- Record the source, nature of exposure, and assessment rationale.

### EDD-CHK-029 — Review relevant financial crime indicators

**Dependencies:** Data-dependent; policy-dependent.

- Examine documented indicators relevant to the review scope, where permitted information is available.
- Record the specific indicator, supporting evidence, source, and uncertainty.
- Distinguish verified facts from assumptions.

### EDD-CHK-030 — Document implications and follow-up

**Dependencies:** Core; policy-dependent.

- Explain how verified indicators affect the review, if at all.
- Record further verification or escalation required by applicable policy.
- Avoid unsupported conclusions based solely on geography, occupation, industry, or association.

## 12. Source Quality and Evidence Records

**Objective:** Ensure material findings are traceable to evidence and that source limitations are documented.

### EDD-CHK-031 — Capture traceable source details

**Dependencies:** Core.

For each material evidence item, record the fields required by G4F-EDD-002:

- `evidence_id`
- `claim_reference`
- `title`
- `publisher`
- `url`
- `reference`
- `publication_date`
- `access_date`
- `source_type`
- `source_classification`
- `jurisdiction`
- `excerpt_or_summary`
- `provenance_notes`
- `evidence_status`
- `limitations`

Use the schema's exact field names and allowed values. Include `null` where permitted and appropriate for unavailable optional source details, rather than inventing information.

### EDD-CHK-032 — Assess source authority and provenance

**Dependencies:** Core; policy-dependent.

- Record who created or published the source and how it was obtained.
- Assess whether the source directly supports the claim.
- Use the appropriate `source_type`, such as `official_record`, `regulatory_filing`, `news_article`, `research_report`, `user_document`, `website`, `database_record`, `other`, or `unknown`.
- Record one or more applicable `source_classification` values: `primary`, `secondary`, `user_provided`, or `generated`.
- Remember that classification alone does not establish reliability or authenticity.

### EDD-CHK-033 — Check freshness and completeness

**Dependencies:** Core; data-dependent.

- Record publication and actual access dates where available.
- Identify stale data, missing pages or fields, and incomplete source coverage.
- Document whether a newer source was sought and the impact of any gap.

### EDD-CHK-034 — Record unavailable, disputed, or outdated evidence

**Dependencies:** Core; data-dependent.

Use the EDD-002 `evidence_status` values exactly:

- `available`
- `unavailable`
- `disputed`
- `outdated`

For `unavailable` evidence, record at least one non-empty limitation explaining the gap.

For `disputed` or `outdated` evidence, record the relevant limitations. The schema requires a non-empty limitations array for these statuses.

Do not use checklist outcomes such as `clear` or `unable_to_assess` as evidence status values.

### EDD-CHK-035 — Preserve conflicting evidence and uncertainty

**Dependencies:** Core.

- Record conflicting sources and describe the specific disagreement.
- Preserve relevant contrary evidence and explain any provisional assessment.
- Distinguish source statements, analyst interpretation, and conclusions.
- Do not invent quotations, dates, citations, or source details.

### EDD-CHK-036 — Link evidence to claims and findings

**Dependencies:** Core.

- Assign each evidence record an ID matching the EDD-002 pattern, such as `EDD-EV-001`.
- Assign each evidence record a claim reference matching the required pattern, such as `CLAIM-001`.
- Record the claim or finding supported by each evidence item.
- Maintain a traceable mapping between claim references and case findings in reviewer notes or a separate claim register.
- Use EDD-001 finding IDs matching the pattern `F-001`, `F-002`, and so on.
- Do not add unsupported fields to the EDD-001 case schema.

**Important schema distinction:** EDD-001 does not define a dedicated claim ID property in its finding objects. EDD-002 requires `claim_reference`, so maintain the mapping separately or in permitted documentation. Do not assume that `claim_reference` is itself an EDD-001 field.

### EDD-CHK-037 — Record unavailable sources consistently

**Dependencies:** Core; data-dependent.

- Record the source or tool, attempted access date, known reason for unavailability, and impact on the review.
- If a source was not accessed, use `access_date: null` where appropriate under EDD-002.
- Record a limitation when `evidence_status` is `unavailable`.
- Do not mark a check clear solely because the source could not be accessed.

## 13. Mapping Checklist Results to EDD-001

Checklist results are not directly interchangeable with the case schema's risk categories, finding severity, disposition, confidence, or review status.

When a material issue is identified, record it in the case schema using its defined structure.

### 13.1 Allowed Case Risk Categories

Use only the following EDD-001 `risk_categories` values:

- `sanctions`
- `politically_exposed_person`
- `adverse_media`
- `ownership_opacity`
- `geographic_risk`
- `financial_crime`
- `identity_verification`
- `other`

Each risk category must be unique within the array.

### 13.2 Case Findings

Each EDD-001 finding requires:

- `finding_id`: a value such as `F-001`.
- `category`: one of the allowed risk categories.
- `summary`: a non-empty description of the finding.
- `severity`: `low`, `medium`, `high`, or `critical`.

The optional `disposition` field, when supplied, must use one of:

- `unresolved`
- `false_positive`
- `substantiated`
- `mitigated`

Use these values according to the evidence and applicable review procedures. Do not treat `potential_match_issue` as a valid disposition.

### 13.3 Confidence and Review Status

- `confidence` must be a number between `0` and `1`.
- Explain the basis for the overall confidence in `analyst_notes`.
- `review_status` must be `pending`, `in_review`, `completed`, or `escalated`.

Do not set a case to `completed` merely because every checklist row has an outcome. Required reviews, escalations, and approvals must be handled under applicable policy.

## 14. Escalation and Human-Review Triggers

Pause automated disposition and refer the issue to the designated human reviewer or escalation function when any of the following applies:

- Identity is ambiguous, a possible match cannot be resolved, or key identifiers conflict.
- A potential sanctions match requires further review or an authorized decision.
- Beneficial ownership or control cannot be established to the required standard.
- A PEP indicator may apply and the relevant definitions, relationships, or required measures remain unclear.
- Credible adverse information, litigation, or regulatory action is material, contested, or difficult to interpret.
- Related-party relationships create unresolved material concerns.
- Evidence is unavailable, stale, unauthenticated, incomplete, or contradictory in a way that may affect the outcome.
- Search coverage is inadequate because of jurisdiction, language, data access, licensing, or technical limitations.
- A privacy concern, prohibited data use, conflict of interest, or decision outside the reviewer's authority is identified.
- Applicable policy requires specialist review, additional approval, or escalation.

### 14.1 Escalation Record

| Field | Reviewer entry |
|---|---|
| Escalation reference | |
| Checklist ID | |
| Related case finding ID, if available | |
| Related claim and evidence references | |
| Issue summary | |
| Reason for escalation | |
| Assigned reviewer or team reference | |
| Referral date | |
| Outcome and rationale | |
| Outstanding actions | |
| Action owner and due date | |

Record the issue, supporting evidence references, unresolved question, referral date, outcome, and follow-up actions.

Follow the institution's approved procedures for urgent issues and any required restrictions. Do not independently authorize activity or make decisions outside the reviewer's authority.

## 15. Reviewer Notes and Close-Out

Use the following section to summarize the review and document unresolved fields.

| Reviewer note | Entry |
|---|---|
| Checks not completed and reason | |
| Evidence gaps, disputes, or stale sources | |
| Potential matches and resolution rationale | |
| Key findings and linked evidence IDs | |
| Claim-to-finding mapping reference | |
| Applicable policy decisions or approvals | |
| Escalation owner, date, and outcome | |
| Residual uncertainty and confidence rationale | |
| Reviewer recommendation | |
| Follow-up action, owner, and due date | |
| Reviewer sign-off and date | |

### 15.1 Final Review

- [ ] The subject and review scope are identified.
- [ ] The case ID and review date are recorded.
- [ ] Applicable checks have documented outcomes.
- [ ] Inapplicable checks include reasons.
- [ ] Checks that could not be assessed include limitations.
- [ ] Material findings are recorded using EDD-001-compatible fields and allowed values.
- [ ] Material evidence is recorded using EDD-002-compatible fields and allowed values.
- [ ] Claim references can be traced to documented claims and findings.
- [ ] Allegations are distinguished from verified facts and official outcomes.
- [ ] Material unresolved concerns have been escalated where required.
- [ ] Outstanding actions and approvals are documented.
- [ ] The case review status reflects the actual stage of review.
- [ ] The reviewer's rationale and limitations are recorded.

## 16. Scope and Limitations

This checklist is a general-purpose documentation aid for EDD reviews.

1. **Jurisdictional differences:** Applicable laws, sanctions regimes, PEP definitions, beneficial ownership requirements, and legal disclosure obligations vary by jurisdiction.
2. **Institutional policy:** Screening scope, risk classifications, escalation requirements, and approval processes must follow applicable institutional procedures.
3. **Data availability:** Registries, court records, screening databases, and publications may be incomplete, restricted, inaccessible, or outdated.
4. **Identity uncertainty:** Similar names and incomplete identifiers can produce false positives or false negatives.
5. **Source limitations:** Public reporting and third-party records may contain errors, disputed statements, or incomplete information.
6. **No guarantee of completeness:** The absence of identified concerns does not establish the absence of risk.
7. **No legal advice:** This checklist does not determine legal obligations, sanctions liability, or regulatory compliance.
8. **Human judgment:** Material findings and unresolved concerns require appropriate human assessment.
9. **Privacy and confidentiality:** Handle personal and confidential information according to applicable law and authorized procedures.
10. **No automated approval:** Completion of the checklist does not authorize a transaction, relationship, or other activity.
11. **Schema compatibility:** EDD-001 and EDD-002 define structured case and evidence fields. The checklist guides the review and does not replace schema validation.
12. **Version control:** Record the checklist version used and apply approved local supplements where required.

## 17. Relationship to Other G4F-EDD Deliverables

### G4F-EDD-001 — EDD Case Data Schema

Use the case schema to structure the review record, including:

- `case_id`
- `subject_type`
- `jurisdiction`
- `review_date`
- `risk_categories`
- `source_records`
- `findings`
- `confidence`
- `analyst_notes`
- `review_status`

The case schema's `source_records` use `source_id`, `source_type`, `description`, optional `url`, and `checked_date`.

Allowed `source_records.source_type` values are:

- `registry`
- `sanctions_list`
- `adverse_media`
- `internal_record`
- `identity_document`
- `other`

These case-level source records are distinct from the more detailed evidence records in EDD-002.

### G4F-EDD-002 — Source and Evidence Record Format

Use the evidence schema to document individual sources and their relationship to claims.

The evidence schema requires:

- `evidence_id`
- `claim_reference`
- `title`
- `publisher`
- `url`
- `reference`
- `publication_date`
- `access_date`
- `source_type`
- `source_classification`
- `jurisdiction`
- `excerpt_or_summary`
- `provenance_notes`
- `evidence_status`
- `limitations`

Use the exact allowed values and field types defined by the schema. Do not replace missing information with fabricated details.

Maintain the claim-to-finding mapping in separate documentation or reviewer notes because EDD-001 does not currently define a claim reference field.

## 18. Fictional Example of a Completed Checklist Item

This example is fictional and demonstrates documentation only. It does not describe a real person, company, sanctions listing, or investigation.

**Checklist ID:** `EDD-CHK-003`

**Check:** Resolve candidate identity matches.

**Case ID:** `G4F-EDD-003`

**Subject type:** `company`

**Claim reference:** `CLAIM-001`

**Evidence ID:** `EDD-EV-001`

**Finding ID:** `F-001`

**Verification objective:** Determine whether a fictional search result refers to the intended fictional company or a different entity with a similar name.

**Evidence reviewed:**

- Title: Fictional registry extract.
- Publisher: Fictional registry authority.
- URL: `null` because no URL is available in this fictional example.
- Reference: Fictional document reference.
- Publication date: `null` because the publication date is unknown.
- Access date: `2026-10-21`.
- Source type: `official_record`.
- Source classification: `primary`.
- Jurisdiction: Fictional jurisdiction.
- Evidence status: `available`.
- Limitations: The fictional record does not contain a matching registration number.

**Checklist outcome:** `unable_to_assess`

**Finding summary:** The available fictional record contains a similar company name but does not provide sufficient identifying information to confirm the match.

**Finding category:** `identity_verification`

**Finding severity:** `medium`

**Finding disposition:** `unresolved`

**Confidence:** Assess the overall case confidence separately; do not infer it from this checklist outcome alone.

**Escalation required:** If identity confirmation is necessary to complete the review, refer the unresolved match according to applicable procedures.

**Reviewer notes:** Obtain additional reliable identifying information or refer the issue for further review. Preserve the source limitation and do not conclude that the entities are identical.

**Schema note:** This is an illustrative mapping of checklist concepts to schema fields, not a complete case JSON object or complete evidence JSON object. A production record must include every field required by the relevant schema and use its permitted values.

## 19. Reviewer Note on Tailoring

Before using this checklist operationally, the institution's policy owner should approve the scope, sources, decision thresholds, escalation destinations, recordkeeping, and jurisdiction-specific requirements.

Reviewers should document the checklist version and any approved local supplement used.

---

**End of G4F-EDD-003 Review Checklist**
