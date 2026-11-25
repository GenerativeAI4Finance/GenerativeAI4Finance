# Sources and references

Sources were checked on **25 November 2026**. These references provide general security and AI risk guidance; the financial workflow impacts and scenario mappings in the taxonomy are illustrative applications of that guidance, not claims of observed incidents.

| ID | Source | Used for |
|---|---|---|
| S1 | OWASP GenAI Security Project, [Top 10 for LLM Applications 2026](https://genai.owasp.org/top-10-for-llm-applications-2026/) | Prompt injection, sensitive information disclosure, excessive agency, unbounded consumption, misinformation, and security mitigations. The taxonomy summarizes these themes for financial workflow risk assessment. |
| S2 | National Institute of Standards and Technology (NIST), [Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile, NIST AI 600-1](https://doi.org/10.6028/NIST.AI.600-1), 2024 | Generative AI information security, direct and indirect prompt injection, information integrity, misinformation/disinformation, and downstream trust risks. |
| S3 | NIST, [Digital Identity Guidelines, SP 800-63-4](https://csrc.nist.gov/pubs/sp/800/63/4/final), July 2025 | Identity proofing, authentication, federation, authenticator lifecycle, and related assurance concepts. This is general guidance; organizations should apply standards appropriate to their jurisdiction and risk. |
| S4 | NIST, [Zero Trust Architecture, SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final), August 2020 | Per-resource access, authentication and authorization, continuous verification, and least privilege for users and services. |
| S5 | NIST, [Incident Response Recommendations and Considerations for Cybersecurity Risk Management, SP 800-61 Rev. 3](https://csrc.nist.gov/pubs/sp/800/61/r3/final), April 2025 | Preparing for, detecting, responding to, and recovering from cybersecurity incidents within risk management. |

## Citation notes

- The taxonomy's signals are practical defensive examples. They are not direct quotations, guaranteed indicators, or proof of malicious activity.
- Financial impacts are plausible scenarios for workflows such as lending, payment operations, fraud review, due diligence, investment research, and customer service. Their likelihood and severity require local assessment.
- OWASP's 2026 Top 10 is a living project resource; check its current version before citing it in a formal assessment.
- NIST publications are cross-sector guidance. They do not replace applicable law, regulator guidance, contractual commitments, or institutional policy.
