# Dataset Card: [dataset name]

> Complete this card for each dataset release. Replace bracketed prompts and
> explicitly explain any `Unknown`, `Not applicable`, or unavailable field.
> Do not infer licensing or provenance from a file's location alone.

## Identification

- **Dataset name:** [name]
- **Dataset version:** [semantic version or repository revision]
- **Release date:** [YYYY-MM-DD]
- **Maintainer / contact:** [team or role; avoid personal details unless appropriate]
- **Related project / task:** [project and task IDs]
- **Files and formats:** [paths, file types, approximate sizes or row counts]
- **Schema / data dictionary:** [path or URL]

## Purpose and scope

- **Purpose:** [why the dataset was created]
- **Intended uses:** [supported research, testing, teaching, or demonstration uses]
- **Out-of-scope uses and exclusions:** [decisions or claims the data must not support]
- **Population and unit of analysis:** [who/what each row represents and dataset grain]
- **Time coverage and jurisdictions:** [dates, geography, or explicitly none]

## Composition and fields

| Table/file | Grain | Main fields | Records / size | Missingness notes |
| --- | --- | --- | --- | --- |
| [file] | [unit represented] | [key fields] | [count] | [known missingness] |

- **Feature definitions:** [link to data dictionary]
- **Sensitive or personal data:** [present / absent / unknown, with explanation]
- **Synthetic markers:** [how synthetic rows and values are identified]

## Provenance and generation

For each input, source, or component dataset, record its category and origin.
Use one or more categories: **synthetic**, **public**, **licensed**, or
**user-contributed**. State whether the component is directly included,
transformed, or only used to define a schema or method.

| Component / input | Category | Origin or generator | Transformation / use | Source URL or repository reference | Access date (YYYY-MM-DD) |
| --- | --- | --- | --- | --- | --- |
| [name] | [category] | [who/what created it] | [how used] | [URL or path; explain if none] | [date or N/A + reason] |

- **Generation method and assumptions:** [algorithms, sampling, simulation assumptions]
- **Randomness / reproducibility:** [seed, configuration, runtime dependencies]
- **Ground truth:** [how labels or expected outcomes were defined; or none]
- **Known transformations:** [cleaning, filtering, normalization, joins]
- **Provenance gaps:** [unknown origin, missing metadata, or unavailable source]

## Licensing and access

- **Dataset license:** [exact license and scope, or `Unknown` with follow-up]
- **Code / generator license:** [license, if different]
- **Third-party terms:** [licenses, attribution, redistribution limits, or none identified]
- **Access and redistribution:** [public/private, restrictions, and where obtained]
- **License evidence:** [license file/URL and access date]

Do not assume that a repository's code license automatically grants rights to
third-party data. For synthetic data, identify the license governing the
generated files and separately record the generator's license.

## Quality, limitations, and risks

- **Known quality checks:** [validation, tests, manual review, metrics]
- **Known limitations and representational gaps:** [small sample, simplified logic, omitted populations]
- **Bias or fairness considerations:** [what is known and untested]
- **Potential misuse or invalid conclusions:** [what users must not infer]
- **Data freshness / staleness:** [as-of date, refresh cadence, or not applicable]
- **Unresolved issues:** [open provenance, licensing, quality, or scope questions]

## Recommended citation and use notes

[How to refer to the dataset, cite its version, and report synthetic or assumed values.]

## Version history

| Version | Date | Changes | Provenance / license impact |
| --- | --- | --- | --- |
| [x.y.z] | [YYYY-MM-DD] | [summary] | [none or describe] |
