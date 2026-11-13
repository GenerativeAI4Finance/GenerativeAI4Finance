# Dataset Card: Financial State Reconstruction Synthetic Benchmark Materials

## Identification

- **Dataset name:** Financial State Reconstruction Synthetic Benchmark Materials
- **Dataset version:** 1.0.0 (WM-001–WM-004 examples and fixtures as currently checked in)
- **Release date:** 2026-11-13
- **Maintainer / contact:** GenerativeAI4Finance World Models benchmark contributors
- **Related project / task:** `01-world-models/vs-banking-worldmodel/benchmarks/perception/financial_state_reconstruction`; G4F-WM-001 through G4F-WM-005
- **Files and formats:** JSON schema and example records (WM-001); JSON configuration and CSV synthetic tables (WM-002 and WM-003); JSON validation fixtures and a JSON quality report (WM-004).
- **Schema / data dictionary:** See the per-task `README.md` and `data_dictionary.md` files listed below.

## Purpose and scope

- **Purpose:** Provide small, reproducible, fictional materials to develop and test financial-state schemas, synthetic borrower/loan generation, macro/sector scenario generation, and temporal data validation.
- **Intended uses:** Software development, schema and pipeline examples, unit tests, controlled demonstrations, and educational exercises about temporal records and leakage checks.
- **Out-of-scope uses and exclusions:** Credit underwriting, borrower or company assessment, forecasting, model calibration, real-world macroeconomic inference, regulatory reporting, and any decision about a real person or organization.
- **Population and unit of analysis:** No real population is sampled. WM-001 has example entity/state records; WM-002 has synthetic borrower, loan, month-state, and repayment rows; WM-003 has synthetic business, scenario/month/sector, event, and modeled outcome rows; WM-004 contains generic validator fixtures rather than an observational dataset.
- **Time coverage and jurisdictions:** Simulated/example dates are specified in each task configuration and fixture. They do not represent observed periods or jurisdictions; no jurisdiction-specific data is included.

## Composition and fields

| Component | Grain | Main fields | Records / size | Missingness notes |
| --- | --- | --- | --- | --- |
| WM-001 `examples/synthetic_records.json` | Example financial entity-state/event record | Prediction timestamp, features at time t, later outcomes, source/observation metadata | Three example records | One example explicitly demonstrates a missing feature; see its data dictionary. |
| WM-002 `data/sample/*.csv` | Borrower, loan, loan-month state, or installment | Synthetic IDs, income, principal, rate, cash flow, state, payment status | 16 borrowers, 16 loans, 96 monthly states, 96 repayment rows | Payment dates can be null for missed payments; generator rules define the semantics. |
| WM-003 `data/sample/*.csv` | Business, scenario/month/sector, event, or modeled business outcome | Synthetic rates and indices, scenario labels, modeled cash flow and stress flags | 8 businesses, 192 macro sequence rows, 4 sector events, 384 business outcomes | No source-observation missingness is modeled; values are generated from assumptions. |
| WM-004 `fixtures/*.json` and `reports/example_quality_report.json` | Generic temporal record, split assignment, or validation result | IDs, timestamps, state, feature availability, outcomes, split labels, diagnostics | One valid and one intentionally invalid fixture plus example report | Invalid fixture deliberately contains missing/invalid fields to exercise checks. |

- **Feature definitions:** See [WM-001 data dictionary](../G4F-WM-001/data_dictionary.md), [WM-002 data dictionary](../G4F-WM-002/data_dictionary.md), [WM-003 data dictionary](../G4F-WM-003/data_dictionary.md), and [WM-004 data dictionary](../G4F-WM-004/data_dictionary.md).
- **Sensitive or personal data:** None intended or included. Identifiers and labels are explicitly synthetic; region codes are fictional and have no geographic mapping.
- **Synthetic markers:** WM-001 examples and WM-002/WM-003 generated rows are identified as synthetic in their documentation and data fields. WM-004 fixtures declare their synthetic status in the dataset document.

## Provenance and generation

The reviewed materials contain no public source dataset, licensed source dataset, or user-contributed records. WM-001 describes a record format and fictional examples; WM-002 and WM-003 use deterministic code and configuration to generate fictional values; WM-004 uses deliberately constructed fixtures to demonstrate validator behavior. The task documentation and code paths below were inspected on **2026-11-13**. No external source URLs or external data access dates apply.

| Component / input | Category | Origin or generator | Transformation / use | Source URL or repository reference | Access date (YYYY-MM-DD) |
| --- | --- | --- | --- | --- | --- |
| WM-001 record schema and examples | Synthetic | Hand-authored schema and fictional examples | Defines time-stamped state/event structure and illustrates missingness and leakage boundaries | `G4F-WM-001/schema/financial_event.schema.json`; `G4F-WM-001/examples/synthetic_records.json`; `G4F-WM-001/README.md` | 2026-11-13 |
| WM-002 borrower and loan sample | Synthetic | `G4F-WM-002/generator/borrower_generator.py` and `config/generator.json`; seed `20261110` | Generates 16 fictional borrower/loan paths and six monthly snapshots; configuration and output hashes are in `data/sample/manifest.json` | `G4F-WM-002/` | 2026-11-13 |
| WM-003 macro and sector sample | Synthetic | `G4F-WM-003/generator/macro_generator.py` and `config/scenarios.json`; seed `20261111` | Simulates baseline/stress paths with explicitly assumed relationships; manifest records versions and hashes | `G4F-WM-003/` | 2026-11-13 |
| WM-004 validation fixtures and report | Synthetic | Hand-authored fixture records, rules, and validator output | Provides a passing fixture and deliberately failing fixture for structural and temporal checks | `G4F-WM-004/fixtures/`; `G4F-WM-004/config/validation_rules.json`; `G4F-WM-004/reports/example_quality_report.json` | 2026-11-13 |
| Public or licensed data | Not present | No public or licensed dataset was identified in the reviewed components | None | Not applicable; no external data source is used | Not applicable |
| User-contributed records | Not present | No user-contributed records are used | None | Not applicable | Not applicable |

- **Generation method and assumptions:** WM-002 uses configured ranges, fixed scenario-path counts, and modeled repayment/state rules. WM-003 uses a seeded random walk and configured sector sensitivities and shock formulas. WM-001 examples and WM-004 fixtures are illustrative records. See each component's README and data dictionary for details.
- **Randomness / reproducibility:** WM-002 and WM-003 manifests record fixed seeds, generator and dataset versions, runtime versions, configuration hashes, row/scenario counts, and output hashes. Identical output is expected for the same seed, configuration, and runtime versions. WM-001 and WM-004 examples are static checked-in files.
- **Ground truth:** No empirical ground truth. WM-002 scenario labels and WM-003 outcomes are constructed by configured rules/formulas. WM-004 expected pass/fail behavior is defined by its fixtures and validation rules.
- **Known transformations:** Generated output is serialized to CSV with documented stable ordering/formatting. WM-004 report diagnostics are produced by applying configured structural validation rules to the fixtures. No third-party observational records are joined or transformed.
- **Provenance gaps:** The files do not provide an individual author or timestamp for every manually authored fictional value. This does not change their stated synthetic status; future releases should record generator/configuration revisions and any new sources.

## Licensing and access

- **Dataset license:** The repository root contains an Apache License 2.0 license. The checked-in synthetic files are part of this repository and are intended to follow that repository license, subject to any applicable notices or later file-specific terms. Review the root [`LICENSE`](../../../../../../LICENSE) and repository notices before redistribution.
- **Code / generator license:** Apache License 2.0 as stated by the repository root license, subject to applicable notices.
- **Third-party terms:** No third-party data or data-provider terms were identified in the reviewed WM-001–WM-004 materials. Reassess if external sources or dependencies that carry data terms are added.
- **Access and redistribution:** Files are checked into the repository. Repository-level access and license terms apply; no separate data access service is required.
- **License evidence:** Repository root `LICENSE` (Apache License 2.0), inspected 2026-11-13. No separate file-specific data license was found in the reviewed task folders.

## Quality, limitations, and risks

- **Known quality checks:** WM-001 has schema/example tests; WM-002 and WM-003 have deterministic generator and constraint tests; WM-004 includes valid/invalid fixtures and tests for configured validation rules. The WM-002/003 manifests provide hashes and row counts. These checks confirm implementation behavior against the authored specifications, not real-world validity.
- **Known limitations and representational gaps:** Samples are small and intentionally simplified. WM-002 omits many servicing details, and its scenario counts are test quotas rather than population frequencies. WM-003 sensitivity coefficients, stress magnitudes, and thresholds are illustrative assumptions rather than estimated parameters. WM-001 demonstrates format constraints only. WM-004 checks configured metadata and structural rules but cannot establish semantic correctness or prove a feature has no hidden future information.
- **Bias or fairness considerations:** No real population is represented, so the data cannot establish fairness, representativeness, or disparate impact. Synthetic distributions can still encode arbitrary choices from configuration; review those assumptions before using the data to compare system behavior.
- **Potential misuse or invalid conclusions:** Do not interpret any row, scenario, risk flag, state label, or modeled outcome as an allegation or observation about a real borrower/business, a probability estimate, a causal relationship, a forecast, or evidence of model performance on real data.
- **Data freshness / staleness:** Not applicable to observed facts because there are none. Reproducibility metadata reflects the checked-in generator/configuration state and runtime versions at the recorded sample generation.
- **Unresolved issues:** Confirm file-level licensing expectations if repository policy changes or if external/public/licensed/user-contributed material is added. Keep manifests and cards synchronized when generators, seeds, assumptions, or samples change.

## Recommended citation and use notes

Refer to the component task and dataset version, for example: “G4F-WM-002 synthetic borrower/loan sample, dataset version 1.0.0, seed 20261110.” State explicitly that values are synthetic and assumptions are not empirically calibrated. Cite repository paths and commit/revision when documenting a particular use.

## Version history

| Version | Date | Changes | Provenance / license impact |
| --- | --- | --- | --- |
| 1.0.0 | 2026-11-13 | Initial completed card for the WM-001–WM-004 materials; documents sources, generation, licensing, intended use, and limits. | Records only synthetic/internal materials; repository root Apache License 2.0 noted; no third-party or user-contributed data identified. |
