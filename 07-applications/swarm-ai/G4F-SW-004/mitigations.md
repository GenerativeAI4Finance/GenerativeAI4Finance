# Mitigations and Interpretation

## Controls exercised by this prototype

- Treat source text as evidence data. Do not let text inside a document change
  system instructions, the case objective, or approval policy.
- Keep tools behind an explicit allowlist and enforce authorization in the
  workflow outside the model or agent's text output.
- Preserve source, scenario, and input identifiers alongside each finding.
- Check every quote and character range against the exact input text before
  including it in a report.
- Flag instruction-like content and retain it as untrusted content for review;
  do not execute, relay as authority, or obey it.
- Require human review for ambiguous or consequential outcomes. Agent agreement
  is not independent evidence and must not clear a case.
- Log each role's input/output and any tool call so a reviewer can reconstruct
  the run.

## Test containment

Fixtures contain only fictional names, synthetic status language, fake source
IDs, and harmless instruction-like requests. The runner has no provider,
network, external lookup, messaging, or real case-management integration. The
mock tool used by the baseline only creates a local trace event; these cases
do not request it. Tests inspect text and traces without evaluating or running
the embedded instructions.

## Limits

The harness evaluates the deterministic rule-based G4F-SW-003 roles. The
instruction detector uses configured phrases and cannot establish broad
prompt-injection resistance. It may miss unseen or paraphrased instructions,
and a phrase match is a signal, not proof of malicious intent. Passing results
are not evidence that an LLM provider, different prompt, different tool set,
or production deployment is safe.

For a future approved model adapter, preserve the same synthetic-only boundary,
disable external tools, record model/configuration identifiers, and evaluate
against additional independently authored fixtures. Do not send these fixtures
to an external endpoint unless that endpoint is explicitly approved for the
data and test.
