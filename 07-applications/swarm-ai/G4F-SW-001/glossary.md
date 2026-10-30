# Glossary

| Term | Meaning in this taxonomy |
| --- | --- |
| Agent | A software component that uses a model, tools, or both to perform a delegated task. |
| Agent lineage | Traceable record of which agent produced, transformed, or passed along a claim or action. |
| Correlated outputs | Outputs that are not independent confirmations because agents share models, prompts, sources, memory, or other influences. |
| Defensive signal | An observable event that justifies review; it is not by itself proof of an attack or malicious intent. |
| Evidence provenance | The origin and transformation history of a claim, including source identifiers, locations, timestamps, and agent handoffs. |
| False consensus | Apparent agreement that results from correlated outputs, repetition, aggregation choices, or missing dissent rather than independent corroboration. |
| Human review gate | A workflow control that requires an identified person to review evidence and explicitly approve a defined action or conclusion. |
| Indirect prompt injection | Instruction-like content embedded in data an agent retrieves or processes, rather than supplied as a direct instruction by the user. |
| Least privilege | Limiting an identity or agent to the minimum data and operations needed for its assigned task. |
| Monitor fragmentation | A condition where per-agent or per-step monitoring misses harmful end-to-end behavior because each monitor sees only part of a coordinated workflow. |
| Prompt injection | Untrusted input or retrieved content that attempts to alter an agent's intended task, policy, or behavior. |
| Shared memory | A store of messages, summaries, or other state that more than one agent can read or write. |
| Source laundering | Loss or obscuring of original source attribution as a claim is repeated or summarized, potentially making one source appear to be several. |
| Swarm / multi-agent workflow | A system in which multiple agents or agent-like components communicate, delegate tasks, share state, or jointly contribute to an output. |
| Tool misuse | An unintended or unauthorized tool action, including an action enabled by excessive permissions or inadequate authorization checks. |
