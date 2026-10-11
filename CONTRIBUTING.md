# GenerativeAI4Finance — Contributing Guide

Welcome to GenerativeAI4Finance! This repository brings together open-source work on financial AI datasets, evaluations, benchmarks, tools and reference implementations. Initial focus areas include Enhanced Due Diligence (EDD), Swarm AI risk in financial services, World Models for Finance, GNPA/credit risk, cyber resilience, developer infrastructure and regulatory intelligence.

**Contribution principle:** one focused task → implementation or research → tests/validation → documentation → one pull request.

## Open contribution tasks

Choose a task from the index below, then read its full specification in the relevant workstream further down this file. Difficulty and role are guides; you do not need to understand the entire repository to contribute.

| Task ID | Task | Difficulty | Suggested role |
|---|---|---|---|
| `G4F-EDD-001` | Define the EDD case data schema | Easy | Data / Backend Intern |
| `G4F-EDD-002` | Build a source and evidence record format | Easy | Research / Data Intern |
| `G4F-EDD-003` | Create an EDD review checklist | Easy | Financial Research Intern |
| `G4F-EDD-004` | Build a synthetic EDD case dataset | Medium | Data Engineer / Researcher |
| `G4F-EDD-005` | Implement entity resolution for company records | Medium | Python Engineer / Data Scientist |
| `G4F-EDD-006` | Build a source-backed finding extractor | Medium | NLP / LLM Engineer |
| `G4F-EDD-007` | Add contradiction and stale-evidence checks | Medium | Data / Backend Engineer |
| `G4F-EDD-008` | Generate an auditable EDD report | Medium | Backend / Reporting Engineer |
| `G4F-EDD-009` | Evaluate EDD extraction quality | Medium | Evaluation / Data Science Intern |
| `G4F-EDD-010` | Add EDD human-review and audit trail | Medium | Backend Engineer / Governance Researcher |
| `G4F-SW-001` | Define a Swarm AI threat and capability taxonomy | Easy | Cybersecurity / Research Intern |
| `G4F-SW-002` | Define the EDD swarm simulation scenario format | Easy | Python / QA Intern |
| `G4F-SW-003` | Build a multi-agent EDD baseline | Medium | Agent Engineer |
| `G4F-SW-004` | Test evidence contamination and prompt injection resistance | Medium | AI Security Engineer |
| `G4F-SW-005` | Measure coordination failure and correlated errors | Medium | Evaluation Engineer / Researcher |
| `G4F-SW-006` | Implement least-privilege tool permissions for agents | Medium | Backend / Security Engineer |
| `G4F-SW-007` | Create a Swarm AI + EDD benchmark scorecard | Medium | Benchmark / Research Engineer |
| `G4F-WM-001` | Define the financial event and state schema | Easy | Data Engineering Intern |
| `G4F-WM-002` | Create a synthetic borrower and loan-state generator | Medium | Data Scientist / Data Engineer |
| `G4F-WM-003` | Create synthetic macroeconomic and sector-event sequences | Medium | Research / Data Science Intern |
| `G4F-WM-004` | Build a temporal dataset validation suite | Medium | Data Quality Engineer |
| `G4F-WM-005` | Document dataset provenance, licensing and limitations | Easy | Research / Data Governance Intern |
| `G4F-WM-006` | Build an event-to-state transition dataset | Medium | Financial Modelling / Data Engineer |
| `G4F-WM-007` | Build causal intervention scenarios | Hard | Quantitative Researcher / World Model Researcher |
| `G4F-WM-008` | Create benchmark splits and leakage tests | Medium | ML Engineer / Data Engineer |
| `G4F-WM-009` | Build a baseline financial state predictor | Medium | ML Engineer |
| `G4F-WM-010` | Evaluate scenario prediction and calibration | Hard | ML Evaluation / Quantitative Researcher |
| `G4F-GNPA-001` | Define an early-warning prediction target | Medium | Credit Risk Researcher |
| `G4F-GNPA-002` | Generate synthetic credit-risk labels | Medium | Data Scientist |
| `G4F-GNPA-003` | Implement credit-risk benchmark metrics | Easy | Python / Evaluation Intern |
| `G4F-GNPA-004` | Add cost-sensitive risk evaluation | Medium | Credit Risk / Quantitative Researcher |
| `G4F-CYBER-001` | Create a defensive financial AI incident taxonomy | Easy | Cybersecurity Research Intern |
| `G4F-CYBER-002` | Build a controlled incident scenario schema | Easy | QA / Security Intern |
| `G4F-CYBER-003` | Implement an incident evidence bundle | Medium | Security / Backend Engineer |
| `G4F-DEV-001` | Add a local development setup guide | Easy | Developer Experience Intern |
| `G4F-DEV-002` | Add continuous integration for tests and linting | Medium | DevOps / Platform Engineer |
| `G4F-DEV-003` | Containerise a reference benchmark | Medium | System / DevOps Engineer |
| `G4F-DEV-004` | Build a benchmark run manifest | Easy | QA / Python Intern |
| `G4F-DEV-005` | Add a reproducible benchmark CLI | Hard | Python / Platform Engineer |
| `G4F-REG-001` | Create a regulatory source register | Easy | Regulatory Research Intern |
| `G4F-REG-002` | Build a regulatory document metadata extractor | Medium | Python / NLP Engineer |
| `G4F-REG-003` | Track regulatory changes with human verification | Medium | Data / Regulatory Technology Engineer |

## What contributors gain — by contributor profile

GenerativeAI4Finance welcomes contributors at different career stages. Choose a task that matches your experience and the time you can commit. The benefits below are opportunities, not guarantees; they depend on the work completed, review outcomes and project policy.

### For interns and students

- **Build real project experience:** work on clearly scoped tasks in financial AI, datasets, benchmarks, documentation or regulatory research.
- **Create a verifiable portfolio:** show reviewed pull requests, tests, research notes, schemas or sample datasets in your public GitHub profile.
- **Learn professional workflows:** practise Git branching, issue tracking, code review, testing, documentation and reproducible work.
- **Explore career paths:** gain exposure to AI engineering, data engineering, fintech, model evaluation, cybersecurity and financial research.
- **Get feedback:** use maintainer and peer review to improve your implementation and technical communication.

*Good starting points:* tasks marked **Easy** or **Good first task**, such as schemas, checklists, dataset cards, source registers and validation tests.

### For working professionals and engineers

- **Demonstrate applied expertise:** contribute reusable implementations, tests, data pipelines, evaluation tools or infrastructure.
- **Deepen skills in Financial AI:** work on EDD, credit-risk benchmarks, World Models for Finance, agent evaluation, AI security or regulatory intelligence.
- **Build a public technical track record:** link to the specific code, documentation and results you contributed.
- **Collaborate across disciplines:** work with researchers and practitioners in software, finance, risk, security and governance.
- **Practise open-source engineering:** improve modularity, maintainability, reproducibility and review-ready delivery.

*Good starting points:* medium-difficulty engineering tasks, benchmark components, evaluation suites, CI, reproducibility tooling and focused reference implementations.

### For researchers and data scientists

- **Turn ideas into reproducible artefacts:** contribute datasets, benchmark definitions, baselines, evaluation metrics and experiment reports.
- **Make assumptions explicit:** document methodology, limitations, data provenance and failure cases.
- **Compare approaches fairly:** help define repeatable tests and metrics for financial AI systems.
- **Increase research visibility:** make methods and results inspectable through public, version-controlled contributions.

*Good starting points:* synthetic data generation, temporal validation, causal-intervention scenarios, calibration, benchmark scorecards and EDD evaluation.

### For enterprise architects and technical leaders

- **Shape reference architectures:** contribute modular designs, interface contracts, data schemas, deployment patterns and reproducibility standards.
- **Apply architecture experience to meaningful problems:** help address auditability, least privilege, human review, data boundaries and integration across components.
- **Influence shared technical foundations:** propose designs that others can implement, test and build upon.
- **Demonstrate thought leadership through implementation:** contribute architecture decision records, diagrams, technical reviews and working reference designs—not just high-level opinions.

*Good starting points:* system design, agent permission models, benchmark architecture, containerisation, reproducible CLIs, data contracts and CI design.

### For banking, risk, compliance and regulatory professionals

- **Bring domain knowledge into practical tools:** help define credit-risk targets, EDD workflows, evidence standards, regulatory metadata and human-review requirements.
- **Improve relevance and reliability:** identify edge cases, misleading metrics, workflow constraints and assumptions engineers may overlook.
- **Make evaluations more meaningful:** contribute review checklists, test scenarios, acceptance criteria and documented limitations.
- **Help build reusable resources:** turn domain expertise into public schemas, guidance and benchmark specifications.

*Good starting points:* EDD checklists, GNPA target definitions, regulatory source registers, dataset cards and evaluation criteria. Do not submit confidential institutional information.

### For cybersecurity and AI safety professionals

- **Advance defensive evaluation:** help define threat taxonomies, controlled test scenarios, detection criteria and mitigation approaches.
- **Test system boundaries:** contribute permission checks, prompt-injection resistance tests, evidence integrity checks and incident artefacts.
- **Improve repeatability:** make security tests isolated, documented and safe to rerun.

*Good starting points:* defensive incident taxonomies, synthetic scenarios, least-privilege controls and benchmark scorecards. Work must remain within the project's defensive scope.

### For enterprises and technology teams

- **Collaborate on shared problems:** contribute generalisable tools, test cases, documentation or reference implementations relevant to financial AI.
- **Learn from open evaluation:** inspect documented methods, assumptions and limitations and compare them with your own requirements.
- **Support ecosystem development:** contribute engineering time, domain review or permitted synthetic/public examples that help improve shared resources.

Contributions must be authorised by the contributor's organisation where required. Do not submit proprietary code, confidential data, customer records or intellectual property without explicit permission. A contribution does not imply endorsement, certification or a production-ready solution.

### Recognition, bounties and opportunities

Contributors can build a public record of their work through merged pull requests and other accepted artefacts. Any acknowledgements, contributor listings, certificates, references, internships, employment or commercial opportunities are subject to project policy, availability and maintainer approval; none is guaranteed.

**Bounties are task-specific, not automatic.** A funded issue must state the amount, currency, eligibility, deliverables, review criteria and payment conditions. Do not assume payment unless a maintainer confirms the terms in writing before work begins. Unless explicitly agreed otherwise, contributions are unpaid.

The strongest contribution is one that solves a clearly defined problem, includes appropriate validation, documents its limitations and can be understood and reused by others.

## Start here: fork the repository first

1. **Fork the repository** to your own GitHub account using the **Fork** button on the repository page.
2. **Clone your fork** (replace `<your-username>` with your GitHub username):
   ```bash
   git clone https://github.com/<your-username>/GenerativeAI4Finance.git
   cd GenerativeAI4Finance
   ```
3. **Add the upstream repository** so you can sync with the main project:
   ```bash
   git remote add upstream https://github.com/GenerativeAI4Finance/GenerativeAI4Finance.git
   git remote -v
   ```
   If your fork uses a different repository name or URL, use the URL shown on your fork's GitHub page.
4. **Create a branch** for one task:
   ```bash
   git switch -c g4f-edd-001-case-schema
   ```
   Use a short, descriptive branch name; avoid working directly on `main`.
5. **Choose a task and open an issue.** Mention its task ID (for example, `G4F-EDD-001`), proposed approach, deliverables and acceptance criteria. Wait for maintainer feedback before substantial work.
6. **Make one focused change.** Follow the task's scope, add tests or validation, and update documentation and examples.
7. **Validate locally.** Run the relevant tests or checks and include the commands/results in your pull request. If the repository has no applicable test command yet, explain how you validated the change.
8. **Commit and push your branch** to your fork:
   ```bash
   git add <files-you-changed>
   git commit -m "Add EDD case schema"
   git push -u origin g4f-edd-001-case-schema
   ```
9. **Open a pull request** from your branch on your fork to the upstream repository's `main` branch. Link the issue, explain what changed, list tests/validation, and note limitations.

To sync your fork with upstream later:
```bash
git fetch upstream
git switch main
git merge upstream/main
git push origin main
```
If you have uncommitted changes, commit or stash them before syncing.

## Choose a task that fits your experience

- **Easy:** suitable for an intern or first-time contributor with basic programming or research skills.
- **Medium:** requires independent implementation, data handling, testing or domain research.
- **Hard:** requires system design, advanced modelling, specialist financial knowledge or integration across components.

Typical contributor profiles include interns/beginners, junior engineers or researchers, experienced engineers/researchers, and domain experts in banking, compliance, investigations, credit risk, cybersecurity or financial modelling.

## Issues, pull requests and review

- **Bug reports:** open an issue with a clear description, steps to reproduce, expected versus actual behaviour, and relevant environment details.
- **Feature proposals:** open an issue describing the use case, proposed scope and expected benefit.
- **Pull requests:** keep changes small and focused; link the agreed task or issue; include tests/validation, documentation and sample output where useful. Maintainers may request changes before merging.
- **Documentation contributions:** welcome, including tutorials, setup instructions, data dictionaries and explanations of limitations.

## Safety, data and research standards

- Use synthetic, public or properly licensed data. Do not commit customer data, personal data, confidential bank data, credentials, API keys or unlicensed datasets.
- Record data provenance, licence, version and limitations for every dataset or model evaluation.
- Distinguish verified facts, source claims, model inferences and unresolved questions. Do not fabricate citations or present unsupported model output as fact.
- Keep human review and uncertainty visible for consequential financial decisions. Passing tests does not establish regulatory compliance or certification.
- Keep cybersecurity scenarios controlled, isolated and focused on defensive evaluation. Do not target real people or institutions, bypass controls or execute real-world attacks.

# Workstream 1 --- Enhanced Due Diligence (EDD)

EDD is the first workstream. The goal is to build transparent,
reproducible tools that help analysts assemble and assess evidence about
a company or counterparty. The project is not intended to make
unsupported accusations or automatically declare a person or company
suspicious. Outputs must distinguish facts, source claims, model
inferences and unresolved questions.

## G4F-EDD-001 --- Define the EDD case data schema

-   **Difficulty:** Easy
-   **Role:** Data / Backend Intern
-   **Experience required:** Basic Python or JSON/YAML; familiarity with
    structured data is helpful.
-   **Scope of work:**
    -   Define a JSON Schema for an EDD case.
    -   Include case ID, subject type, jurisdiction, review date, risk
        categories, source records, findings, confidence, analyst notes
        and review status.
    -   Define required and optional fields and allowed values.
    -   Add two fictional example cases.
-   **Tools:** JSON Schema, Python, Git, GitHub.
-   **Deliverables:** Schema file, valid sample cases, validation tests
    and a short README.
-   **Acceptance criteria:** Examples validate; invalid values fail with
    clear messages; no real personal or confidential data is used.
-   **Good first task:** Yes.

## G4F-EDD-002 --- Build a source and evidence record format

-   **Difficulty:** Easy
-   **Role:** Research / Data Intern
-   **Experience required:** Careful research, Markdown, basic JSON or
    YAML.
-   **Scope of work:**
    -   Define a consistent record for each source used in an EDD
        review.
    -   Capture source title, publisher, URL or reference, publication
        date, access date, source type, jurisdiction, relevant excerpt
        or summary, and provenance notes.
    -   Record whether the source is primary, secondary, user-provided
        or generated.
    -   Document how to represent unavailable, disputed or outdated
        evidence.
-   **Tools:** Markdown, JSON/YAML, Git.
-   **Deliverables:** Evidence schema, five fictional or clearly
    labelled example records, documentation.
-   **Acceptance criteria:** Another analyst can identify where a claim
    came from and when it was checked; no fabricated citations.
-   **Good first task:** Yes.

## G4F-EDD-003 --- Create an EDD review checklist

-   **Difficulty:** Easy
-   **Role:** Financial Research Intern
-   **Experience required:** Desk research, clear writing; exposure to
    KYC/AML is helpful but not mandatory.
-   **Scope of work:**
    -   Draft a jurisdiction-neutral checklist covering identity and
        entity resolution, ownership and control, beneficial ownership,
        adverse media, sanctions screening, politically exposed person
        indicators where legally relevant, litigation/regulatory
        actions, related entities and source quality.
    -   Mark which checks depend on jurisdiction, data access or
        institutional policy.
    -   Include escalation and human-review triggers.
-   **Tools:** Markdown, GitHub.
-   **Deliverables:** Checklist, scope/limitations section and reviewer
    notes.
-   **Acceptance criteria:** Each item describes what to verify and what
    evidence to record; it does not present a checklist as legal advice
    or a substitute for applicable policy.
-   **Good first task:** Yes.

## G4F-EDD-004 --- Build a synthetic EDD case dataset

-   **Difficulty:** Medium
-   **Role:** Data Engineer / Researcher
-   **Experience required:** Python, CSV/JSON, basic data quality
    checks.
-   **Scope of work:**
    -   Generate fictional companies, directors, shareholders,
        subsidiaries, addresses, jurisdictions, source records and risk
        indicators.
    -   Include normal cases, ambiguous entity matches, incomplete
        records, conflicting claims and stale evidence.
    -   Add deterministic random seeds and dataset versioning.
    -   Ensure all entities and events are fictional and clearly marked
        synthetic.
-   **Tools:** Python, pandas, Faker or a comparable generator, pytest.
-   **Deliverables:** Generator script, versioned sample dataset, data
    dictionary and tests.
-   **Acceptance criteria:** Re-running with the same seed produces the
    same data; schema validation passes; no real people or real
    allegations are represented as facts.

## G4F-EDD-005 --- Implement entity resolution for company records

-   **Difficulty:** Medium
-   **Role:** Python Engineer / Data Scientist
-   **Experience required:** Python, string similarity, unit testing;
    SQL is useful.
-   **Scope of work:**
    -   Compare company names and identifiers across synthetic records.
    -   Handle punctuation, abbreviations, transliteration placeholders,
        aliases and common-name collisions.
    -   Return match scores and the evidence behind a match.
    -   Separate candidate generation from final human confirmation.
-   **Tools:** Python, pandas, rapidfuzz or equivalent, pytest.
-   **Deliverables:** Reusable module, tests, example notebook or CLI
    output.
-   **Acceptance criteria:** Includes both true-match and false-match
    tests; scores are not presented as proof of identity; thresholds are
    configurable and documented.

## G4F-EDD-006 --- Build a source-backed finding extractor

-   **Difficulty:** Medium
-   **Role:** NLP / LLM Engineer
-   **Experience required:** Python, APIs or local model inference,
    structured output validation.
-   **Scope of work:**
    -   Convert provided text into candidate findings with source
        references.
    -   Require every finding to point to a source record and supporting
        passage or location.
    -   Label statements as source claims, extracted facts, model
        inferences or unresolved items.
    -   Return "insufficient evidence" when the input does not support a
        conclusion.
-   **Tools:** Python, Pydantic or JSON Schema, an optional LLM provider
    behind a replaceable interface, pytest.
-   **Deliverables:** Extraction module, prompt or model configuration,
    test fixtures and failure cases.
-   **Acceptance criteria:** Invalid or unsupported findings are
    rejected or flagged; citations are traceable; provider credentials
    are never committed.

## G4F-EDD-007 --- Add contradiction and stale-evidence checks

-   **Difficulty:** Medium
-   **Role:** Data / Backend Engineer
-   **Experience required:** Python, date/time handling, rule-based
    logic.
-   **Scope of work:**
    -   Identify conflicting values across evidence records, such as
        different ownership percentages or inconsistent company status.
    -   Flag records beyond configurable freshness windows.
    -   Preserve both conflicting sources rather than silently selecting
        one.
-   **Tools:** Python, pandas, pytest.
-   **Deliverables:** Rules module, configurable thresholds, synthetic
    tests and documentation.
-   **Acceptance criteria:** Conflicts and stale records are visible in
    output; the system does not resolve material contradictions without
    a documented rule or human review.

## G4F-EDD-008 --- Generate an auditable EDD report

-   **Difficulty:** Medium
-   **Role:** Backend / Reporting Engineer
-   **Experience required:** Python, Markdown or HTML templating,
    structured data.
-   **Scope of work:**
    -   Generate a report containing scope, subject summary, findings,
        source references, unresolved questions, limitations and
        recommended review actions.
    -   Clearly distinguish evidence from model-generated summaries.
    -   Include report version, dataset version and generation
        timestamp.
-   **Tools:** Python, Jinja2 or equivalent, Markdown/HTML, pytest.
-   **Deliverables:** Report generator, fictional example report, tests.
-   **Acceptance criteria:** Every substantive finding links to
    evidence; missing data is shown explicitly; no unsupported overall
    accusation or automatic final decision is generated.

## G4F-EDD-009 --- Evaluate EDD extraction quality

-   **Difficulty:** Medium
-   **Role:** Evaluation / Data Science Intern
-   **Experience required:** Python or spreadsheet skills, careful
    annotation and basic statistics.
-   **Scope of work:**
    -   Create a small, manually reviewed gold set from synthetic
        documents.
    -   Define measures for extraction precision, recall, citation
        correctness, unsupported-claim rate and abstention quality.
    -   Compare a baseline rule-based system with an optional
        model-based system.
-   **Tools:** Python, pandas, scikit-learn or simple metric code,
    pytest.
-   **Deliverables:** Gold-set format, evaluation script, results table
    and limitations.
-   **Acceptance criteria:** Metrics are reproducible; the evaluation
    includes negative cases; results do not claim production readiness
    from a small sample.

## G4F-EDD-010 --- Add EDD human-review and audit trail

-   **Difficulty:** Medium
-   **Role:** Backend Engineer / Governance Researcher
-   **Experience required:** Python, event logging or workflow design.
-   **Scope of work:**
    -   Record finding creation, reviewer decision, edits, escalation
        and closure as append-only events.
    -   Capture actor role, timestamp, reason and references to changed
        records.
    -   Document access control and retention assumptions without
        implementing unsupported compliance claims.
-   **Tools:** Python, SQLite or JSONL for the reference implementation,
    pytest.
-   **Deliverables:** Event schema, minimal implementation, example
    audit log and tests.
-   **Acceptance criteria:** Changes are traceable; the previous state
    can be reconstructed from events; sensitive data is not written into
    logs unnecessarily.

------------------------------------------------------------------------

# Workstream 2 --- Swarm AI + EDD

This workstream explores how coordinated AI agents can affect financial
due diligence and investigation workflows. The initial benchmark should
use a controlled, defensive simulation with fictional entities,
synthetic documents and clearly defined agent permissions. Do not use
the project to target real people or institutions, bypass controls, or
execute real-world attacks.

## G4F-SW-001 --- Define a Swarm AI threat and capability taxonomy

-   **Difficulty:** Easy
-   **Role:** Cybersecurity / Research Intern
-   **Experience required:** Structured research and Markdown; security
    knowledge is helpful.
-   **Scope of work:**
    -   Categorise simulated behaviours such as parallel information
        gathering, conflicting claims, source laundering, coordinated
        misinformation, tool misuse, prompt injection and attempts to
        bypass review.
    -   For each category, document assumptions, possible financial
        impact, observable signals and defensive controls.
    -   Distinguish a single-agent failure from a coordinated
        multi-agent failure.
-   **Tools:** Markdown, Git, public research sources.
-   **Deliverables:** Taxonomy, source list and glossary.
-   **Acceptance criteria:** Each category has a clear definition and a
    defensive test idea; claims are sourced; no operational instructions
    for real-world abuse are included.
-   **Good first task:** Yes.

## G4F-SW-002 --- Define the EDD swarm simulation scenario format

-   **Difficulty:** Easy
-   **Role:** Python / QA Intern
-   **Experience required:** JSON/YAML, basic testing.
-   **Scope of work:**
    -   Define a schema for scenario ID, objective, agent roles, allowed
        tools, synthetic inputs, expected safe behaviour, prohibited
        actions, ground truth and evaluation metrics.
    -   Add scenarios for contradictory sources, duplicated evidence,
        untrusted document instructions and escalation to a human
        reviewer.
-   **Tools:** JSON Schema, YAML, Python, pytest.
-   **Deliverables:** Schema, three sample scenarios and validation
    tests.
-   **Acceptance criteria:** Scenarios are deterministic where possible,
    use fictional data, and define expected outcomes before execution.
-   **Good first task:** Yes.

## G4F-SW-003 --- Build a multi-agent EDD baseline

-   **Difficulty:** Medium
-   **Role:** Agent Engineer
-   **Experience required:** Python, APIs or model inference, structured
    data.
-   **Scope of work:**
    -   Implement separate simulated roles such as source collector,
        entity matcher, evidence analyst and reviewer.
    -   Use a fixed workflow and synthetic inputs before attempting
        dynamic agent coordination.
    -   Require the final result to include source references,
        uncertainty and unresolved issues.
-   **Tools:** Python, pytest, optional agent framework behind a
    replaceable interface.
-   **Deliverables:** Minimal runnable prototype, configuration and
    example output.
-   **Acceptance criteria:** Agent inputs/outputs are logged; the
    workflow can be rerun; the final report does not treat agent
    consensus as proof.

## G4F-SW-004 --- Test evidence contamination and prompt injection resistance

-   **Difficulty:** Medium
-   **Role:** AI Security Engineer
-   **Experience required:** Python, LLM evaluation or application
    security.
-   **Scope of work:**
    -   Create harmless synthetic documents containing embedded
        instructions that conflict with the EDD task.
    -   Test whether agents treat document content as untrusted evidence
        rather than system instructions.
    -   Measure whether the agent preserves citations and follows tool
        permissions.
-   **Tools:** Python, pytest, local or approved model endpoint.
-   **Deliverables:** Safe test fixtures, test harness, results and
    mitigations.
-   **Acceptance criteria:** Tests do not access external systems or
    execute embedded instructions; failures are reproducible;
    mitigations are documented.

## G4F-SW-005 --- Measure coordination failure and correlated errors

-   **Difficulty:** Medium
-   **Role:** Evaluation Engineer / Researcher
-   **Experience required:** Python, data analysis and metric design.
-   **Scope of work:**
    -   Compare a single-agent baseline with multiple-agent
        configurations on the same synthetic EDD cases.
    -   Measure unsupported claims, missed evidence, duplicate work,
        contradiction handling, latency and cost where available.
    -   Test whether agents independently repeat the same incorrect
        assumption.
-   **Tools:** Python, pandas, pytest, optional plotting library.
-   **Deliverables:** Experiment runner, metric definitions, results and
    analysis.
-   **Acceptance criteria:** Same cases are used across configurations;
    run settings and model versions are recorded; results include
    failures and uncertainty.

## G4F-SW-006 --- Implement least-privilege tool permissions for agents

-   **Difficulty:** Medium
-   **Role:** Backend / Security Engineer
-   **Experience required:** Python, access-control concepts, automated
    testing.
-   **Scope of work:**
    -   Define role-based tool permissions for each simulated agent.
    -   Deny unapproved tools by default and log denied actions.
    -   Add tests for attempted privilege escalation and cross-role
        access.
-   **Tools:** Python, pytest, optional policy library.
-   **Deliverables:** Permission configuration, enforcement layer, tests
    and security notes.
-   **Acceptance criteria:** Unauthorized actions fail closed; decisions
    are logged without leaking secrets; policy is configurable and
    documented.

## G4F-SW-007 --- Create a Swarm AI + EDD benchmark scorecard

-   **Difficulty:** Medium
-   **Role:** Benchmark / Research Engineer
-   **Experience required:** Python, metric design, familiarity with
    financial workflows.
-   **Scope of work:**
    -   Define metrics for evidence coverage, citation correctness,
        unsupported-claim rate, contradiction detection,
        human-escalation quality, policy violations, runtime and cost.
    -   Report each metric separately before considering any aggregate
        score.
    -   Define minimum evidence and run metadata required for
        reproducibility.
-   **Tools:** Python, JSON Schema, pandas, pytest.
-   **Deliverables:** Scorecard specification, metric implementation and
    example report.
-   **Acceptance criteria:** Metrics have precise definitions; missing
    values are not silently treated as zero; benchmark results can be
    independently reproduced.

------------------------------------------------------------------------

# Workstream 3 --- World Model for Finance: Dataset Creation

The goal is to build a benchmark-ready dataset representing how
financial states evolve over time and how actions or external events may
affect later outcomes. Initial data should be synthetic or licensed for
the intended use. A dataset must not imply causal relationships merely
because two variables move together.

## G4F-WM-001 --- Define the financial event and state schema

-   **Difficulty:** Easy
-   **Role:** Data Engineering Intern
-   **Experience required:** CSV/JSON, basic Python; financial domain
    knowledge is optional.
-   **Scope of work:**
    -   Define a time-stamped representation of an entity's financial
        state, events, actions, observations and outcomes.
    -   Include entity ID, timestamp, feature values, event type, action
        taken, observation source, target horizon and missingness
        indicators.
    -   Document which fields are observable at prediction time and
        which are future outcomes.
-   **Tools:** JSON Schema, Python, pandas.
-   **Deliverables:** Schema, data dictionary and sample rows.
-   **Acceptance criteria:** Schema prevents obvious target leakage by
    separating features available at time `t` from outcomes after time
    `t`; sample data is synthetic.
-   **Good first task:** Yes.

## G4F-WM-002 --- Create a synthetic borrower and loan-state generator

-   **Difficulty:** Medium
-   **Role:** Data Scientist / Data Engineer
-   **Experience required:** Python, pandas, probability distributions
    and testing.
-   **Scope of work:**
    -   Generate fictional borrowers, loans, repayment histories,
        cash-flow indicators and time-dependent states.
    -   Include normal repayment, liquidity stress, delinquency, cure
        and default paths.
    -   Record generation assumptions and use a fixed seed.
-   **Tools:** Python, pandas, NumPy, pytest.
-   **Deliverables:** Generator, configuration, data dictionary and
    sample dataset.
-   **Acceptance criteria:** Output is reproducible; constraints such as
    dates and balances are validated; no real borrower records are used.

## G4F-WM-003 --- Create synthetic macroeconomic and sector-event sequences

-   **Difficulty:** Medium
-   **Role:** Research / Data Science Intern
-   **Experience required:** Python or spreadsheet modelling,
    time-series basics.
-   **Scope of work:**
    -   Generate fictional interest-rate, commodity-price, demand and
        sector-shock sequences.
    -   Link selected shocks to synthetic borrower or business outcomes
        using explicit assumptions.
    -   Include baseline and stress scenarios.
-   **Tools:** Python, pandas, NumPy.
-   **Deliverables:** Generator, scenario definitions, documentation and
    tests.
-   **Acceptance criteria:** Each relationship is labelled as a
    simulation assumption; the dataset does not present synthetic
    patterns as empirical financial facts.

## G4F-WM-004 --- Build a temporal dataset validation suite

-   **Difficulty:** Medium
-   **Role:** Data Quality Engineer
-   **Experience required:** Python, pandas, unit testing.
-   **Scope of work:**
    -   Check duplicate keys, missing timestamps, impossible
        transitions, inconsistent units, invalid ranges and future-data
        leakage.
    -   Validate train/validation/test splits by time and entity.
    -   Generate a machine-readable quality report.
-   **Tools:** Python, pandas, pytest.
-   **Deliverables:** Validation module, fixtures for known failures,
    example report.
-   **Acceptance criteria:** Deliberately invalid samples trigger
    expected failures; time-based splits do not leak future records into
    training.

## G4F-WM-005 --- Document dataset provenance, licensing and limitations

-   **Difficulty:** Easy
-   **Role:** Research / Data Governance Intern
-   **Experience required:** Clear writing, research and attention to
    detail.
-   **Scope of work:**
    -   Create a dataset card with purpose, generation method, feature
        definitions, intended uses, exclusions, licensing, known
        limitations and version history.
    -   Distinguish synthetic, public, licensed and user-contributed
        data.
    -   Record source URLs and access dates where applicable.
-   **Tools:** Markdown, Git.
-   **Deliverables:** Dataset card template and one completed card.
-   **Acceptance criteria:** A reviewer can understand where the data
    came from, how it was generated and what conclusions it cannot
    support.
-   **Good first task:** Yes.

## G4F-WM-006 --- Build an event-to-state transition dataset

-   **Difficulty:** Medium
-   **Role:** Financial Modelling / Data Engineer
-   **Experience required:** Python, event-driven modelling, basic
    finance.
-   **Scope of work:**
    -   Represent transitions between financial states after events such
        as payment delays, liquidity shocks, rate changes or new credit
        exposure.
    -   Store initial state, event, optional action, resulting state and
        transition timestamp.
    -   Include normal, stress and recovery paths.
-   **Tools:** Python, pandas, NumPy, pytest.
-   **Deliverables:** Transition generator, schema and example
    trajectories.
-   **Acceptance criteria:** Transition logic is documented and
    testable; scenarios can be replayed; generated states obey defined
    constraints.

## G4F-WM-007 --- Build causal intervention scenarios

-   **Difficulty:** Hard
-   **Role:** Quantitative Researcher / World Model Researcher
-   **Experience required:** Causal inference, simulation or
    quantitative modelling.
-   **Scope of work:**
    -   Define controlled interventions such as changing repayment
        terms, credit limits, collections timing or interest rates in
        synthetic environments.
    -   Separate observational features from intervention variables and
        outcomes.
    -   Document assumptions, confounders and limits of interpretation.
-   **Tools:** Python, pandas, NumPy, suitable causal modelling
    libraries if needed.
-   **Deliverables:** Scenario specification, simulator, validation
    tests and research note.
-   **Acceptance criteria:** Intervention effects are traceable to
    explicit simulation rules; correlation is not described as
    causation; counterfactual assumptions are documented.

## G4F-WM-008 --- Create benchmark splits and leakage tests

-   **Difficulty:** Medium
-   **Role:** ML Engineer / Data Engineer
-   **Experience required:** Python, model evaluation, time-series or
    tabular data.
-   **Scope of work:**
    -   Define train, validation and test splits by time and entity.
    -   Prevent the same entity or near-duplicate trajectory from
        leaking across splits where prohibited by the benchmark design.
    -   Add checks for target leakage and post-outcome fields.
-   **Tools:** Python, pandas, scikit-learn, pytest.
-   **Deliverables:** Split generator, leakage tests and documentation.
-   **Acceptance criteria:** Splits are reproducible; leakage tests
    include known failure fixtures; split policy is explicitly
    documented.

## G4F-WM-009 --- Build a baseline financial state predictor

-   **Difficulty:** Medium
-   **Role:** ML Engineer
-   **Experience required:** Python, scikit-learn, pandas and model
    evaluation.
-   **Scope of work:**
    -   Train a simple baseline to predict a defined future state or
        outcome from information available at prediction time.
    -   Compare against a naive baseline.
    -   Report performance by time period and relevant synthetic
        subgroups.
-   **Tools:** Python, pandas, scikit-learn, pytest.
-   **Deliverables:** Training/evaluation script, baseline metrics,
    model card.
-   **Acceptance criteria:** Evaluation is reproducible; target and
    horizon are clearly defined; limitations and subgroup performance
    are reported.

## G4F-WM-010 --- Evaluate scenario prediction and calibration

-   **Difficulty:** Hard
-   **Role:** ML Evaluation / Quantitative Researcher
-   **Experience required:** Probabilistic forecasting, model
    evaluation, Python.
-   **Scope of work:**
    -   Evaluate predicted state transitions or risk probabilities
        against held-out simulated trajectories.
    -   Include calibration and error analysis where appropriate.
    -   Test baseline, normal and stress scenarios separately.
-   **Tools:** Python, pandas, scikit-learn or suitable statistical
    libraries.
-   **Deliverables:** Evaluation suite, metric definitions and
    reproducible report.
-   **Acceptance criteria:** Metrics match the prediction task; stress
    performance is reported separately; results do not imply real-world
    validity without real-world validation.

------------------------------------------------------------------------

# Workstream 4 --- GNPA / Credit Risk Benchmark

## G4F-GNPA-001 --- Define an early-warning prediction target

-   **Difficulty:** Medium
-   **Role:** Credit Risk Researcher
-   **Experience required:** Banking or credit-risk familiarity; ability
    to write precise specifications.
-   **Scope of work:**
    -   Define the prediction unit, observation date, target event,
        prediction horizon and eligible population.
    -   Distinguish delinquency, default, NPA and GNPA concepts where
        applicable.
    -   Document treatment of restructures, cures, write-offs and
        censored observations.
-   **Tools:** Markdown, Python optional.
-   **Deliverables:** Target specification, assumptions and example
    cases.
-   **Acceptance criteria:** Labels are unambiguous and time-bounded;
    jurisdiction and accounting/regulatory context are stated; edge
    cases are documented.

## G4F-GNPA-002 --- Generate synthetic credit-risk labels

-   **Difficulty:** Medium
-   **Role:** Data Scientist
-   **Experience required:** Python, pandas, basic credit-risk concepts.
-   **Scope of work:**
    -   Create fictional account histories with time-dependent
        delinquency and stress labels.
    -   Include class imbalance, cures and incomplete follow-up periods.
    -   Prevent labels from being inferred from information unavailable
        at the observation date.
-   **Tools:** Python, pandas, NumPy, pytest.
-   **Deliverables:** Dataset generator, label definitions, validation
    tests.
-   **Acceptance criteria:** Label-generation rules are transparent;
    leakage checks pass; all data is synthetic.

## G4F-GNPA-003 --- Implement credit-risk benchmark metrics

-   **Difficulty:** Easy
-   **Role:** Python / Evaluation Intern
-   **Experience required:** Python basics, classification metrics.
-   **Scope of work:**
    -   Implement precision, recall, F1, PR-AUC and confusion-matrix
        reporting.
    -   Add threshold-based recall and false-positive analysis.
    -   Document why accuracy alone can be misleading for rare events.
-   **Tools:** Python, scikit-learn, pytest.
-   **Deliverables:** Metrics module, unit tests and sample report.
-   **Acceptance criteria:** Results match trusted library calculations
    on known fixtures; threshold and positive-class definitions are
    explicit.
-   **Good first task:** Yes.

## G4F-GNPA-004 --- Add cost-sensitive risk evaluation

-   **Difficulty:** Medium
-   **Role:** Credit Risk / Quantitative Researcher
-   **Experience required:** Python, confusion-matrix metrics, ability
    to define business assumptions.
-   **Scope of work:**
    -   Allow users to specify the relative costs of missed stress cases
        and false alarms.
    -   Report performance across thresholds and cost assumptions.
    -   Avoid presenting one cost ratio as universally correct.
-   **Tools:** Python, pandas, pytest.
-   **Deliverables:** Configurable cost function, tests and worked
    synthetic example.
-   **Acceptance criteria:** Cost assumptions are visible; results can
    be recalculated; threshold selection is not silently hard-coded.

------------------------------------------------------------------------

# Workstream 5 --- AI-led Cyber Attacks and Financial Resilience

## G4F-CYBER-001 --- Create a defensive financial AI incident taxonomy

-   **Difficulty:** Easy
-   **Role:** Cybersecurity Research Intern
-   **Experience required:** Research, Markdown and source checking.
-   **Scope of work:**
    -   Categorise defensive test themes such as prompt injection, tool
        misuse, identity abuse, data exfiltration attempts, coordinated
        misinformation and denial-of-service pressure.
    -   Map each theme to potential financial workflow impact, detection
        signals and mitigations.
-   **Tools:** Markdown, Git.
-   **Deliverables:** Taxonomy and sourced references.
-   **Acceptance criteria:** Focuses on risk assessment and mitigation,
    not instructions to attack real systems.
-   **Good first task:** Yes.

## G4F-CYBER-002 --- Build a controlled incident scenario schema

-   **Difficulty:** Easy
-   **Role:** QA / Security Intern
-   **Experience required:** JSON/YAML, basic test design.
-   **Scope of work:**
    -   Define scenario fields for assets, simulated events, expected
        detections, safe response, severity, evidence and pass/fail
        conditions.
    -   Add harmless scenarios that run locally against a toy
        application.
-   **Tools:** JSON Schema, Python, pytest.
-   **Deliverables:** Schema, sample scenarios and validation tests.
-   **Acceptance criteria:** Scenarios are bounded, reproducible and do
    not connect to production systems.
-   **Good first task:** Yes.

## G4F-CYBER-003 --- Implement an incident evidence bundle

-   **Difficulty:** Medium
-   **Role:** Security / Backend Engineer
-   **Experience required:** Python, JSONL/logging, automated tests.
-   **Scope of work:**
    -   Package scenario ID, run configuration, timestamps, events,
        detections, response actions and hashes of generated artefacts.
    -   Exclude secrets and unnecessary personal data.
-   **Tools:** Python, JSON/JSONL, hashlib, pytest.
-   **Deliverables:** Evidence-bundle exporter, schema and example.
-   **Acceptance criteria:** Bundle can be validated independently;
    hashes are verified; limitations of the evidence are documented.

------------------------------------------------------------------------

# Workstream 6 --- Developer Infrastructure and Reproducibility

## G4F-DEV-001 --- Add a local development setup guide

-   **Difficulty:** Easy
-   **Role:** Developer Experience Intern
-   **Experience required:** Linux command line, Git and Python basics.
-   **Scope of work:**
    -   Document supported Python version, virtual environment setup,
        dependency installation, test commands and common errors.
    -   Keep setup local-first and avoid requiring cloud credentials.
-   **Tools:** Linux/macOS/Windows shell, Python, Git.
-   **Deliverables:** `CONTRIBUTING.md` or a focused setup guide.
-   **Acceptance criteria:** A new contributor can follow the steps from
    a clean checkout; commands are tested and accurate.
-   **Good first task:** Yes.

## G4F-DEV-002 --- Add continuous integration for tests and linting

-   **Difficulty:** Medium
-   **Role:** DevOps / Platform Engineer
-   **Experience required:** GitHub Actions, Linux shell, Python
    packaging.
-   **Scope of work:**
    -   Configure CI to install dependencies, run tests and execute
        selected lint/type checks.
    -   Pin or constrain dependencies and avoid storing credentials in
        workflows.
    -   Document how to reproduce CI failures locally.
-   **Tools:** GitHub Actions, Linux, Python, pytest, Ruff or
    equivalent.
-   **Deliverables:** Workflow file, configuration and documentation.
-   **Acceptance criteria:** CI runs on pull requests; failure status is
    visible; no secrets are required for basic tests.

## G4F-DEV-003 --- Containerise a reference benchmark

-   **Difficulty:** Medium
-   **Role:** System / DevOps Engineer
-   **Experience required:** Docker or Podman, Linux, environment
    configuration.
-   **Scope of work:**
    -   Create a container image for one selected benchmark runner.
    -   Add a non-root runtime where practical, a health or smoke test,
        and documented input/output mounts.
    -   Make the default run use synthetic data and no external
        credentials.
-   **Tools:** Docker/Podman, Linux, shell scripting, Python.
-   **Deliverables:** Containerfile/Dockerfile, run instructions and
    smoke tests.
-   **Acceptance criteria:** A clean local run succeeds using documented
    commands; image does not embed credentials; output is reproducible.
-   **Good first task for a systems intern:** With maintainer guidance.

## G4F-DEV-004 --- Build a benchmark run manifest

-   **Difficulty:** Easy
-   **Role:** QA / Python Intern
-   **Experience required:** JSON/YAML and basic scripting.
-   **Scope of work:**
    -   Record dataset version, benchmark version, model identifier,
        configuration, code revision, seed, environment and output
        artefact references.
    -   Validate that required fields are present before a run is marked
        reproducible.
-   **Tools:** Python, JSON Schema, Git.
-   **Deliverables:** Manifest schema, sample manifest and validation
    tests.
-   **Acceptance criteria:** Missing required metadata is reported
    clearly; secrets and raw sensitive inputs are excluded.
-   **Good first task:** Yes.

## G4F-DEV-005 --- Add a reproducible benchmark CLI

-   **Difficulty:** Hard
-   **Role:** Python / Platform Engineer
-   **Experience required:** Python packaging, CLI design, configuration
    management and testing.
-   **Scope of work:**
    -   Provide commands to validate a dataset, run a benchmark,
        evaluate results and export a run manifest.
    -   Keep model adapters and benchmark definitions modular.
    -   Return useful error messages and stable exit codes.
-   **Tools:** Python, Typer or argparse, pytest.
-   **Deliverables:** CLI package, tests, quick-start guide and example
    run.
-   **Acceptance criteria:** Commands work from a clean environment;
    invalid inputs fail safely; example execution produces documented
    artefacts.

------------------------------------------------------------------------

# Workstream 7 --- Regulatory Intelligence

## G4F-REG-001 --- Create a regulatory source register

-   **Difficulty:** Easy
-   **Role:** Regulatory Research Intern
-   **Experience required:** Desk research, citation discipline and
    Markdown.
-   **Scope of work:**
    -   Record regulator, jurisdiction, document title, publication
        date, effective date, status, source URL and last-checked date.
    -   Start with a clearly bounded jurisdiction or topic.
    -   Distinguish binding requirements from consultation papers,
        guidance, speeches and secondary commentary.
-   **Tools:** Markdown, CSV/JSON, Git.
-   **Deliverables:** Source register and update instructions.
-   **Acceptance criteria:** Each entry links to a verifiable source;
    status and dates are explicit; secondary summaries are labelled.
-   **Good first task:** Yes.

## G4F-REG-002 --- Build a regulatory document metadata extractor

-   **Difficulty:** Medium
-   **Role:** Python / NLP Engineer
-   **Experience required:** Python, HTML/PDF text processing and unit
    tests.
-   **Scope of work:**
    -   Extract candidate title, regulator, publication date, document
        type and URL from a small set of permitted public documents.
    -   Preserve the source URL and extraction confidence.
    -   Route uncertain results for human verification.
-   **Tools:** Python, requests only for approved public sources,
    BeautifulSoup and/or PDF text tools, pytest.
-   **Deliverables:** Extractor, fixture documents, tests and
    limitations.
-   **Acceptance criteria:** Extraction is tested on known fixtures;
    source metadata is not silently invented; site terms and access
    restrictions are respected.

## G4F-REG-003 --- Track regulatory changes with human verification

-   **Difficulty:** Medium
-   **Role:** Data / Regulatory Technology Engineer
-   **Experience required:** Python, text comparison, scheduled CI or
    automation concepts.
-   **Scope of work:**
    -   Compare versioned copies or metadata of permitted public
        regulatory documents.
    -   Produce a diff and a review queue rather than automatically
        declaring legal impact.
    -   Record checked date, document version and reviewer disposition.
-   **Tools:** Python, Git, difflib or equivalent, pytest.
-   **Deliverables:** Change-detection script, sample diff and operating
    guide.
-   **Acceptance criteria:** Changes are traceable to source versions;
    false positives are documented; a human verifies substantive
    implications.

------------------------------------------------------------------------

# Suggested starting sequence

The following sequence creates useful foundations before attempting a
large integrated system.

  -----------------------------------------------------------------------
  Order                   Task                    Why first
  ----------------------- ----------------------- -----------------------
  1                       `G4F-EDD-001` --- EDD   Establishes a shared
                          case schema             data contract

  2                       `G4F-EDD-002` ---       Makes findings
                          Evidence record format  traceable

  3                       `G4F-EDD-003` --- EDD   Defines the analyst
                          checklist               workflow

  4                       `G4F-EDD-004` ---       Enables safe
                          Synthetic EDD dataset   development and testing

  5                       `G4F-EDD-005` ---       Adds a useful core
                          Entity resolution       capability

  6                       `G4F-EDD-006` ---       Adds source-backed AI
                          Finding extractor       assistance

  7                       `G4F-SW-001` and        Define the swarm risk
                          `G4F-SW-002`            taxonomy and test
                                                  format

  8                       `G4F-SW-003` and        Build and test the
                          `G4F-SW-004`            controlled multi-agent
                                                  workflow

  9                       `G4F-WM-001` and        Establish temporal data
                          `G4F-WM-002`            structures and
                                                  synthetic financial
                                                  trajectories

  10                      `G4F-WM-004` and        Add data-quality and
                          `G4F-WM-008`            leakage controls before
                                                  modelling

  11                      `G4F-GNPA-001` and      Define a clear target
                          `G4F-GNPA-003`          and baseline metrics

  12                      `G4F-DEV-001` and       Make contributions
                          `G4F-DEV-004`           easier to reproduce
  -----------------------------------------------------------------------

## How to open a contribution issue

Copy this template into a GitHub issue.

``` markdown
## Task ID
G4F-EDD-001

## Objective
What will be built, and why is it needed?

## Proposed approach
Briefly describe the implementation plan.

## Deliverables
- [ ] Code, data schema or research artefact
- [ ] Tests or validation
- [ ] Documentation and example
- [ ] Data provenance and licence check, if applicable

## Acceptance criteria
List observable conditions that a reviewer can verify.

## Skills and environment
List the relevant language, libraries, OS, cloud or domain skills.

## Dependencies
List prerequisites or write `None`.

## Risks and assumptions
Identify data, security, legal or evaluation limitations.

## Maintainer agreement
Confirm scope with a maintainer before implementation.
```

## Pull request checklist

-   [ ] The change addresses one task or a tightly related set of tasks.
-   [ ] Tests or validation are included.
-   [ ] Documentation and examples are updated.
-   [ ] Dataset provenance and licence are recorded where applicable.
-   [ ] No credentials, customer data, personal data or confidential
    material are committed.
-   [ ] Benchmark outputs include enough metadata to reproduce the run.
-   [ ] Limitations and known failure cases are stated.

## Contribution and bounty policy

Tasks can be labelled `good first issue`, `intern`, `data`, `research`,
`python`, `security`, `world-model`, `benchmark` or `documentation`.

A task is **not automatically a paid bounty**. If a task has funding,
the issue should state the bounty amount, currency, eligibility,
deliverable, review criteria, payment conditions and who authorises
payment. Contributors should not begin work assuming payment unless the
maintainer has confirmed those terms in writing.

## Scope boundaries

-   Use synthetic or properly licensed data unless a task explicitly
    authorises another source and the data handling has been reviewed.
-   Do not commit API keys, credentials, private datasets or customer
    records.
-   Do not represent model output as a verified fact without supporting
    evidence.
-   Do not claim regulatory compliance or certification solely because
    tests pass.
-   Keep human review and uncertainty visible for consequential
    financial decisions.
-   Keep offensive-security scenarios isolated, controlled and focused
    on defensive evaluation.
