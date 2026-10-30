# Sources

Sources were accessed on 2026-10-30. The taxonomy uses them as background for
general risk categories and defensive principles. Experimental results are
scoped to the study's described setting and should not be generalized to all
multi-agent systems or financial applications.

| ID | Source | Supports |
| --- | --- | --- |
| S1 | OWASP Foundation, [OWASP Top 10 for Large Language Model Applications 2025](https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf) (2025). | Prompt injection, misinformation, and excessive agency as application risk categories; defensive framing. |
| S2 | National Institute of Standards and Technology, [Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile (NIST AI 600-1)](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) (July 2024). | Confabulation, erroneous or internally inconsistent outputs, and the risk of fabricated citations or overreliance. |
| S3 | MITRE ATT&CK, [Indirect Prompt Injection, T1698](https://attack.mitre.org/techniques/T1698/) (live technique page; version 1.0, created 2026-09-18, modified 2026-10-12). | Retrieved content can contain instructions that influence agent behavior; mitigations include independent authorization, network segmentation, and restricted permissions. |
| S4 | Tianjie Ju et al., [Flooding Spread of Manipulated Knowledge in LLM-Based Multi-Agent Communities](https://arxiv.org/abs/2407.07791) (arXiv:2407.07791, submitted 2024-07-10). | Experimental study of manipulated knowledge propagation in simulated multi-agent communities and retrieval settings. |
| S5 | Chenfei Yan et al., [When Truth Is Distributed: Misinformation Derails Collective Fact Recovery in LLM-Based Multi-Agent Systems](https://arxiv.org/abs/2608.03421) (arXiv:2608.03421, submitted 2026-08-04). | A controlled multi-agent study of misinformation and collective fact recovery; use as emerging research, not broad deployment evidence. |
| S6 | UK AI Security Institute, [Multi-Agent AI Control: Distributed Attacks Hamper Per-Instance Monitors](https://www.aisi.gov.uk/research/multi-agent-ai-control-distributed-attacks-hamper-per-instance-monitors) (research summary, accessed 2026-10-30). | Synthetic evaluation of distributed attacks and reduced effectiveness of per-instance monitors as coordination increases. |
| S7 | OWASP Foundation, [LLM06:2025 Excessive Agency](https://owasp.github.io/www-project-top-10-for-large-language-model-applications/2_0_vulns/LLM06_ExcessiveAgency.html) (2025). | Least functionality, least privilege, human confirmation, monitoring, and rate-limiting as damage-limiting controls. |

## Citation and interpretation notes

- The financial impacts in `taxonomy.md` are reasoned examples of how general
  AI and security failures could affect due diligence or operations; they are
  not directly measured findings from these sources.
- “Source laundering” and “review bypass” are taxonomy labels used here to
  organize provenance and workflow risks. They are not asserted to be official
  names for the cited sources' categories.
- Research papers report specific experimental setups. Their findings motivate
  defensive tests but do not establish prevalence, real-world intent, or a
  guaranteed outcome for a different deployment.
