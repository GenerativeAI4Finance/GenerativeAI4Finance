# Defensive financial AI incident taxonomy

## Assessment approach

These categories describe risk themes, not a claim that a system is vulnerable or that an actor intended harm. Financial impact depends on the workflow, data, tool permissions, control environment, and whether a human can review or reverse an action. The listed signals are triage indicators and must be interpreted with context.

Assess each scenario by: affected workflow and data; confidentiality, integrity, and availability; number of customers or records potentially affected; financial and operational consequences; action reversibility; duration; evidence confidence; and existing containment controls.

| ID | Theme | Applicable system scope |
|---|---|---|
| CY-01 | Prompt injection and untrusted context | User prompts, retrieved documents, emails, OCR, tool output, and memory |
| CY-02 | Tool misuse and excessive agency | AI workflows that read or write through tools, APIs, or agents |
| CY-03 | Identity and session abuse | Human, service, agent, and customer identities |
| CY-04 | Sensitive-data exposure and exfiltration | Retrieval, generation, logs, embeddings, and integrations |
| CY-05 | Coordinated misinformation and data-integrity failure | Research, due diligence, fraud, credit, and decision-support workflows |
| CY-06 | Denial of service and resource pressure | Model inference, retrieval, orchestration, and shared services |

## CY-01 — Prompt injection and untrusted context

**Definition.** Content supplied as evidence or retrieved context influences an AI system to disregard its intended task, trust boundary, or workflow policy. This can include direct user input or indirect instructions embedded in a document, tool response, or other input channel. [S1, S2]

**Plausible financial workflow impact.** A credit or due-diligence summary could omit a relevant adverse fact, misstate a source, or attempt an unauthorized handoff. In a workflow connected to tools, manipulated content could cause an inappropriate data lookup or action.

**Detection signals.** Unexpected task or output-format changes after ingestion of a particular source; repeated attempts to retrieve unrelated records; mismatch between source evidence and generated summary; tool calls not justified by the user request; or security controls triggering on a newly ingested document. These indicators do not establish intent.

**Mitigations.** Treat retrieved material and tool output as untrusted data; separate application policy from evidence; enforce authorization and tool permissions outside the model; constrain output schemas; require source-grounded claims; and use human review for consequential actions. Input filtering can help detect suspicious content but should not be the sole security boundary. [S1, S2]

**Safe defensive test.** In an isolated test instance, provide a fictional document containing inert instructions that conflict with the analysis task. Confirm that the system treats the text as evidence, preserves source references, and cannot invoke tools beyond a mocked read-only allowlist.

## CY-02 — Tool misuse and excessive agency

**Definition.** An AI component invokes an available tool or performs an action that is outside the user's authorization, workflow purpose, or approved action boundary. The risk can arise from ambiguous output, model error, untrusted input, or excessive permissions; tool misuse alone does not prove an attack. [S1]

**Plausible financial workflow impact.** An unauthorized or incorrectly scoped write could change a case status, create a payment instruction, place a hold, alter a customer record, or send confidential content to an external destination. Even read-only overreach can expose customer or counterparty data.

**Detection signals.** Tool access outside the assigned case or role; write-capable calls in a read-only workflow; repeated retries or action chains; mismatch between approved intent and tool arguments; actions without a human approval record; or calls attributed to a shared identity instead of a specific actor.

**Mitigations.** Default to read-only access; grant each user, service, or agent only task-specific permissions; enforce tool allowlists and argument validation in application code; require independent authorization and human confirmation for material or irreversible actions; limit call depth and rate; and keep tamper-evident actor-to-action logs. [S1, S5]

**Safe defensive test.** Use mocked tools and synthetic accounts. Verify that an agent assigned to read a case cannot modify it, access another case, initiate a payment, or bypass a required approval.

## CY-03 — Identity and session abuse

**Definition.** A human, service, agent, or customer identity or session is impersonated, misused, or granted access inconsistent with the verified identity and current authorization. Identity proofing, authentication, federation, and authenticator lifecycle are distinct control areas. [S3, S4]

**Plausible financial workflow impact.** An improperly authenticated actor could view or change onboarding records, customer profiles, credit files, fraud dispositions, or payment workflows. A compromised service identity can also enable access at machine speed and obscure the responsible user if accountability is weak.

**Detection signals.** Unusual device, location, session, or access pattern; authentication strength inconsistent with action sensitivity; unexpected privilege or consent changes; expired or long-lived credentials still in use; service identities used interactively; or actions that cannot be linked to a named user and task.

**Mitigations.** Use risk-appropriate identity proofing and strong authentication; re-evaluate authorization for sensitive actions; use unique service/agent identities and short-lived credentials; remove stale access; separate approval and execution duties; and audit identity lifecycle and federation changes. Apply institutional standards and applicable regulations. [S3, S4]

**Safe defensive test.** In a test tenant, simulate expired credentials, a disabled test identity, and an agent identity outside its assigned role. Confirm access is denied, the event is logged, and the incident path can identify the affected principal.

## CY-04 — Sensitive-data exposure and exfiltration

**Definition.** Confidential, regulated, privileged, or proprietary information is returned, transmitted, logged, retrieved, or otherwise made available to an unauthorized party or channel. AI-related exposure surfaces can include model responses, tool arguments, retrieved passages, logs, and derived artifacts. [S1, S2]

**Plausible financial workflow impact.** Customer identifiers, account or transaction details, KYC documents, credit records, credentials, confidential deal information, or internal risk analysis could be disclosed. Exposure may cause customer harm, operational response costs, regulatory reporting duties, or loss of market-sensitive information depending on context.

**Detection signals.** Retrieval outside the user's authorized scope; unusual volume or breadth of sensitive fields in responses; sensitive-data detection in output or telemetry; unexpected outbound destinations; secrets in prompts or logs; or repeated access patterns inconsistent with the user's case.

**Mitigations.** Authorize before retrieval and enforce document/field-level access controls; minimize data sent to models and tools; redact or block sensitive output where policy requires; restrict and scrub logs; control network egress; protect embeddings and derived stores; and maintain data-specific incident response and retention rules. [S1, S2, S5]

**Safe defensive test.** Populate a sandbox with synthetic customer records and canary values. Verify that an unauthorized role cannot retrieve them and that output, tool, and test logs do not expose the canary outside the authorized test boundary.

## CY-05 — Coordinated misinformation and data-integrity failure

**Definition.** False, stale, manipulated, or unsupported information is produced or amplified through AI outputs, shared retrieval, repeated summaries, or coordinated sources. Misinformation can be accidental; disinformation implies intent to deceive, which cannot be inferred from content repetition alone. NIST discusses risks from both misinformation and disinformation, including effects on information integrity and trust. [S2]

**Plausible financial workflow impact.** Unsupported claims could influence adverse-media review, borrower or counterparty risk summaries, fraud triage, investment research, customer communications, or operational escalation. Repeated copies of one claim may be mistaken for independent corroboration and affect a downstream human decision.

**Detection signals.** Multiple reports share the same underlying source or wording; source IDs or dates are missing; a claim becomes more certain without new evidence; contradictory evidence disappears in aggregation; stale information is presented as current; or generated facts cannot be traced to an original record.

**Mitigations.** Preserve provenance and source dates through every transformation; distinguish source claims, extracted facts, and model inferences; detect duplicates and source dependence; retain contradictions and uncertainty; require independent corroboration for material claims; and route unresolved or high-impact findings to a human reviewer. [S2]

**Safe defensive test.** Provide a sandbox workflow with fictional conflicting records, duplicate copies, and one stale source. Confirm the output preserves disagreement, source lineage, and uncertainty instead of presenting duplicated claims as independent evidence.

## CY-06 — Denial of service and resource pressure

**Definition.** Requests, retries, long-running inference, tool fan-out, or shared-resource contention consume more capacity or cost than the service can safely sustain. OWASP describes uncontrolled inference as a source of service disruption, increased cost, and service degradation. [S1]

**Plausible financial workflow impact.** A shared AI service may become unavailable or delayed during time-sensitive fraud, payment, customer-support, or screening operations. Usage-based inference can also create unexpected expense or consume capacity needed by other customers or critical workflows.

**Detection signals.** Request, token, latency, retry, concurrency, or tool-call rates depart from the approved baseline; queue depth or timeout rates rise; one tenant consumes disproportionate capacity; budget thresholds are crossed; or recurring workflows fail to terminate within expected limits.

**Mitigations.** Enforce per-user, per-tenant, and aggregate quotas; set request, output, time, and tool-call budgets; use bounded retries, queues, cancellation, and circuit breakers; reserve capacity for critical workflows; monitor cost and latency; and maintain a tested manual or degraded-service fallback. Include response and recovery in the incident plan. [S1, S5]

**Safe defensive test.** In a load-test environment with a fixed budget and synthetic traffic, verify that quotas and cancellation contain excess work, critical test traffic retains service, and operators receive actionable alerts without affecting production services.

## Cross-cutting incident handling

When signals suggest an incident, preserve relevant prompts, retrieved-source IDs, model and policy versions, identity and tool-call logs, and timestamps in accordance with retention policy. Limit access or disable the affected tool path when warranted, assess confidentiality/integrity/availability and business impact, and invoke the organization's incident-response process. Avoid deleting evidence during containment. NIST SP 800-61 Rev. 3 recommends integrating incident response into broader cybersecurity risk management. [S5]

## Source key

See [sources.md](sources.md) for full bibliographic details, supported themes, and access dates.
