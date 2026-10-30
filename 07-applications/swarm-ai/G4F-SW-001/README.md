# G4F-SW-001: Swarm AI Threat and Capability Taxonomy

This folder defines a defensive taxonomy for reviewing simulated and deployed
multi-agent AI workflows used in financial research and operations. It separates
ordinary single-agent failures from failures amplified by communication,
delegation, shared memory, voting, or orchestration across agents.

## Contents

- [Threat and capability taxonomy](taxonomy.md) — definitions, assumptions,
  plausible financial impact, observable defensive signals, controls, and a
  safe test idea for each category.
- [Sources](sources.md) — public research and security guidance supporting the
  taxonomy.
- [Glossary](glossary.md) — terms used in this document.

## Scope and safe use

Examples are abstract and intended for authorized evaluation in isolated,
synthetic environments. They do not provide instructions for real-world abuse.
Impact statements are plausible scenarios, not claims that a particular
incident has occurred or that a particular system is vulnerable. Controls are
design suggestions, not a substitute for an organization's security policy,
legal obligations, or risk assessment.

The literature and platform designs are evolving. Source links were checked on
2026-10-30; recheck them before relying on this taxonomy for a formal assessment.
