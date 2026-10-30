# Swarm AI Threat and Capability Taxonomy

## How to read this taxonomy

“Swarm” means a workflow in which multiple agents or agent-like components
exchange findings, delegate subtasks, use shared state, or jointly produce an
answer. The term does not imply that agents are autonomous, malicious, or even
based on different models. A coordinated failure may arise from shared faulty
instructions, correlated model behavior, contaminated shared data, or deliberate
coordination; behavior alone does not prove intent.

The financial impacts below are plausible examples (such as an incorrect due
diligence conclusion, payment hold, compliance escalation, or disclosure of
confidential information). They are not evidence of actual incidents. Signals
are investigation leads, not proof. Defensive tests should run only against
owned systems with synthetic data and inert tools.

| ID | Category | Individual failure or coordination dimension |
| --- | --- | --- |
| SW-01 | Parallel information gathering | A capability that can create a single-agent access issue; coordination can multiply load and combine access across agents. |
| SW-02 | Conflicting claims and false consensus | Individual agents may disagree or confabulate; aggregation can suppress disagreement or create unwarranted consensus. |
| SW-03 | Source laundering and provenance loss | One agent may misattribute evidence; repeated agent-to-agent summaries can obscure the original source and make repetition look like corroboration. |
| SW-04 | Coordinated misinformation and manipulated knowledge | One erroneous claim can be amplified by interacting agents, shared memory, or common retrieval. |
| SW-05 | Tool misuse and excessive agency | One agent can misuse an over-permissioned tool; delegation can distribute actions and obscure the actor or authorization chain. |
| SW-06 | Direct or indirect prompt injection | A single agent may follow hostile instructions; shared content or messages can propagate instruction influence to other agents. |
| SW-07 | Review bypass and monitor fragmentation | One agent may evade a local check; splitting a workflow among agents can leave no reviewer with the complete action or evidence trail. |

## SW-01 — Parallel information gathering

**Definition.** Agents search or retrieve information concurrently to cover a
larger scope or reduce latency. This is often a legitimate capability. Risk
arises when concurrency exceeds access, rate, confidentiality, or source-quality
boundaries, or when independent retrieval results are merged without provenance.

**Assumptions.** Agents have access to one or more search, database, document,
or internal retrieval tools. Parallel work may use distinct identities or a
shared service account.

**Possible financial impact.** Excessive requests may raise service costs,
trigger data-provider limits, or slow time-sensitive screening. Broad or
unnecessary access could expose customer, counterparty, or internal research
data. Incomplete retrieval could lead to a missed adverse-media item or an
unsupported diligence conclusion.

**Observable signals.** Sudden concurrency or query-volume increases; repeated
or near-duplicate queries; agents accessing records outside their assigned
scope; unusually broad result sets; missing source IDs in merged results; or
retrieval traffic that lacks an attributable agent and user request.

**Defensive controls.** Apply per-agent identity and least privilege; enforce
central rate and scope limits; propagate the user's authorization to each
subtask; log query, identity, source, and task lineage; deduplicate results while
preserving source references; cap fan-out and stop on budget exhaustion.

**Single-agent versus coordinated failure.** A single agent can over-query or
retrieve outside scope. Multiple agents can multiply request volume, combine
privileges, or make individually reasonable searches exceed aggregate limits.
Count and authorize the workflow at the orchestrator as well as at each tool.

**Defensive test idea.** In a sandbox with synthetic documents and a mock search
service, fan out a bounded query to several agents and then exceed a configured
aggregate request budget. Verify that the service rejects or queues excess work,
records every agent and source, and does not return documents outside the
synthetic allowlist.

## SW-02 — Conflicting claims and false consensus

**Definition.** Agents produce inconsistent claims, or an aggregation step
turns differing or weakly supported claims into a single confident answer.
Consensus is a workflow outcome, not independent verification.

**Assumptions.** Agents may receive different source subsets, use different
prompts or models, or share the same model and evidence. An aggregator, vote,
or orchestrator resolves their outputs.

**Possible financial impact.** Conflicting ownership, status, identity, or risk
information could be reconciled incorrectly, leading to a misdirected review,
an inaccurate report, or an inappropriate decision to proceed, pause, or
escalate.

**Observable signals.** Material values differ across agent outputs; confidence
increases despite no new evidence; a vote has no source-level rationale; the
final answer omits minority findings; or agents cite the same underlying source
as if they were independent confirmations.

**Defensive controls.** Preserve each claim with source and agent lineage;
compare material fields explicitly; report unresolved disagreement; distinguish
independent sources from repeated copies; require a documented rule or human
review before resolving material contradictions. Do not treat majority vote as
proof of factual correctness.

**Single-agent versus coordinated failure.** A single model can contradict
itself or confidently state an unsupported value. A multi-agent setup can
amplify shared errors, create apparent consensus from correlated outputs, or
discard a valid dissenting result during aggregation. An ensemble is not
automatically more reliable than its inputs.

**Defensive test idea.** Give two sandbox agents different synthetic records
with incompatible ownership percentages and a third a stale record. Verify
that the report retains all values, source dates, and the conflict status and
does not silently select a majority value.

## SW-03 — Source laundering and provenance loss

**Definition.** A statement is repeated or summarized by downstream agents
until its original source, uncertainty, or status as an inference is lost. The
repetition can make one unsupported claim appear independently corroborated.

**Assumptions.** Agents exchange summaries, store shared notes, or use retrieval
from prior conversations. Source references are not mandatory or are not
validated end to end.

**Possible financial impact.** A diligence report may cite an intermediary
summary instead of the originating record, mistake copied claims for multiple
sources, or carry an outdated or unverified allegation into a risk assessment.

**Observable signals.** References point only to another agent's summary;
multiple purported sources resolve to the same original document; quotation or
location is missing; attribution changes across handoffs; uncertainty language
disappears; or the source date and source type are absent.

**Defensive controls.** Require source-record identifiers and exact evidence
locations for each material finding; preserve a provenance graph through every
handoff; label quotations, source claims, extracted facts, inferences, and
unresolved items separately; deduplicate by underlying source; reject claims
whose provenance cannot be resolved to an allowed record.

**Single-agent versus coordinated failure.** A single agent can invent or
misstate a citation. Coordination adds repeated-summary hops that can hide
where a claim originated and can create false corroboration. Track evidence
lineage across the workflow, not just the last agent's citation.

**Defensive test idea.** Seed a synthetic shared memory with a clearly labeled
unverified claim, ask multiple agents to summarize it, and inspect the final
record. Pass only if the claim remains labeled unverified, links to the original
seed item, and is not counted as multiple independent sources.

## SW-04 — Coordinated misinformation and manipulated knowledge

**Definition.** False or misleading content is intentionally introduced or
accidentally propagated through agent messages, shared memory, or retrieval,
affecting a collective conclusion. The taxonomy covers the observable system
behavior and does not infer malicious intent from disagreement alone.

**Assumptions.** Agents consume one another's outputs or can write to a shared
knowledge store. Information may be stale, wrong, adversarial, or merely
misunderstood.

**Possible financial impact.** A fabricated or distorted entity relationship,
sanctions match, adverse-media summary, or transaction fact could affect an
analyst's prioritization or a downstream review. Repetition may make a false
claim appear corroborated and damage trust or create avoidable operational
costs.

**Observable signals.** A claim spreads across agents without new evidence;
many outputs share unusual identical phrasing; source-independent verification
fails; a claim persists in memory after correction; or consensus tracks message
volume rather than evidence quality.

**Defensive controls.** Gate writes to shared memory; attach source and freshness
metadata; independently verify material claims against primary records; detect
duplicate provenance; retain correction history; isolate untrusted agent
outputs; require human review for material adverse conclusions. Use a separate
verification path rather than asking the same communicating group to validate
itself.

**Single-agent versus coordinated failure.** One agent may confabulate or
misread a source. In a group, one bad claim can spread, be reinforced by
correlated agents, or persist in shared retrieval. Published research describes
experimental settings where manipulated information propagates; this does not
establish rates or outcomes for financial deployments [S4, S5].

**Defensive test idea.** In a fully synthetic graph of agents and records,
introduce one seeded false company-status claim in a message that is explicitly
not an authoritative source. Verify that the claim is not promoted to a fact,
source-independent verification is requested, and downstream reports retain
the uncertainty and lineage.

## SW-05 — Tool misuse and excessive agency

**Definition.** An agent uses an available tool for an unintended, unauthorized,
or overly consequential action, or has more tool capability, permission, or
autonomy than its task requires. A tool call is an action requiring controls,
not merely text generation.

**Assumptions.** Agents can read or write records, query services, send
communications, or trigger workflow actions. Some actions may have financial,
privacy, or compliance consequences.

**Possible financial impact.** An unauthorized write, external message, or
workflow change could expose confidential information, corrupt a diligence
record, cause payment or onboarding delays, or trigger an incorrect operational
action.

**Observable signals.** Tool call does not match the assigned task; permission
scope is broader than the requested function; actions lack user approval or
policy authorization; repeated retries; a tool call is based on untrusted
retrieved text; or the logs do not identify the requesting agent and approving
principal.

**Defensive controls.** Use narrow, task-specific tool interfaces and
least-privilege identities; separate read and write permissions; authorize
consequential actions outside the model; use human confirmation for sensitive
steps; validate arguments against schemas and policy; apply rate limits,
idempotency, and audit logs; make read-only mode the default where possible.

**Single-agent versus coordinated failure.** A single agent can misuse a
permitted capability. Multiple agents can distribute a sequence across roles,
pass along untrusted instructions, or make ownership of an action ambiguous.
Bind every action to a user task, agent identity, source context, and external
authorization decision.

**Defensive test idea.** In a mock-tool environment, request a read-only
research task while the mock tool exposes a separate write operation. Verify
that the agent cannot invoke the write operation and that any simulated
consequential action requires an authorization token issued by the test harness.

## SW-06 — Direct or indirect prompt injection

**Definition.** Untrusted user input or retrieved content contains instructions
that attempt to override the system's task, policies, or tool boundaries.
Indirect injection arrives through content the agent is asked to process, such
as a document or web result. Prompt injection is a risk category; the presence
of suspicious text alone does not establish successful compromise.

**Assumptions.** Agents read external or user-controlled text and may also have
tools or access to other agents. Instructions and data can be mixed in the same
context.

**Possible financial impact.** An agent could omit adverse evidence, expose
confidential information, produce a misleading report, or propose an
unauthorized action. The realized impact depends on tool permissions and
independent controls.

**Observable signals.** Output deviates from the assigned task after processing
untrusted content; retrieved content is treated as higher-priority instruction;
tool requests are not supported by the user's task; agents pass suspicious
instructions to peers; or source text is quoted as policy rather than evidence.

**Defensive controls.** Treat retrieved content as data, not authorization;
separate instruction channels from evidence; enforce tool authorization outside
the model; minimize permissions and accessible data; validate actions against
the original task; preserve logs; test both direct and indirect injection with
inert synthetic strings. No single text filter should be treated as a complete
defense.

**Single-agent versus coordinated failure.** A single agent may follow an
injected instruction. In a swarm, one agent can relay malicious text or an
instruction-like paraphrase to peers, while each agent's local monitor sees
only a fragment. MITRE ATT&CK describes indirect prompt injection through
content retrieved by agents and emphasizes independent authorization controls
[S3].

**Defensive test idea.** Put an inert instruction-like marker in a synthetic
document, alongside valid facts. Ask a sandboxed agent team to summarize the
facts. Verify that the marker is treated only as document content, does not
change tool permissions or task scope, and remains traceable in the evidence
record.

## SW-07 — Review bypass and monitor fragmentation

**Definition.** An agent or workflow produces a consequential result without
the required human or policy review, or distributes work so that a reviewer or
monitor sees only a harmless-looking fragment rather than the complete chain.
This includes premature finalization, missing escalation, and attempts to
present a generated conclusion as already approved.

**Assumptions.** A workflow has review or escalation requirements, but agents
can hand off work, summarize results, or interact with separate monitoring
components.

**Possible financial impact.** An unsupported finding or unresolved conflict
could enter a final diligence report, change a case's priority, or influence an
onboarding or transaction decision without an accountable reviewer.

**Observable signals.** Final state has no reviewer identity or decision;
approval is inferred from agent consensus; handoff history is incomplete;
escalation flags disappear; material edits occur after review; or local monitors
record compliant substeps while the end-to-end action violates workflow policy.

**Defensive controls.** Enforce review gates in the workflow engine rather than
prompts; require explicit reviewer identity, decision, and timestamp; make
approval invalidated by material post-review changes; preserve end-to-end
traces; monitor aggregate action and information flow across agents; allow
reviewers to inspect original evidence and disagreements; fail closed when
required review metadata is absent.

**Single-agent versus coordinated failure.** One agent may omit or mislabel an
escalation. Coordination can fragment the task so that each local step appears
acceptable while the complete action is not. A UK AI Security Institute study
reports this monitor-fragmentation concern in a synthetic multi-agent control
setting; it is evidence for testing end-to-end monitoring, not a universal
claim about all systems [S6].

**Defensive test idea.** Use a synthetic case with a required human review
state. Have mock agents split research, summarization, and report preparation.
Verify the final report cannot enter an approved state unless a designated
reviewer explicitly approves the complete evidence-linked case, and that any
post-approval change resets the review state.

## Review note

For each test, record the system version, agent roles, model/configuration,
synthetic inputs, tools available, expected control, observed trace, outcome,
and any unresolved limitations. Do not infer hostile intent solely from an
unexpected output; record observable behavior and investigate its cause.
