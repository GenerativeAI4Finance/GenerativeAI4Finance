# G4F-CYBER-001: Defensive financial AI incident taxonomy

This task documents security incident themes for AI-enabled financial workflows. It organizes each theme by plausible workflow impact, observable signals, mitigations, and a safe defensive test idea.

## Contents

- [Defensive taxonomy](taxonomy.md)
- [Sources](sources.md)

## Scope and relationship to other work

The taxonomy is cross-workflow: it applies to systems supporting lending, payments, fraud operations, KYC/AML review, investment research, treasury, and customer service. Impacts are illustrative scenarios, not assertions that a specific financial institution or product has experienced an incident.

[G4F-SW-001](../../swarm-ai/G4F-SW-001/README.md) covers failures specific to multi-agent workflows in greater depth. This taxonomy additionally covers broader identity, data disclosure, and availability risks that can affect single-agent and non-agentic AI systems.

## Safe use and limitations

Use the test ideas only with systems you own or are authorized to assess, using synthetic inputs and inert or mocked tools. The document intentionally describes defensive observables and safeguards rather than steps for attacking real systems. A signal is a lead for investigation, not proof of malicious intent or a confirmed incident. Apply institutional policy, legal requirements, and the organization's incident-response process.

References were checked on 25 November 2026. Recheck source versions before using this taxonomy for a formal risk assessment.
