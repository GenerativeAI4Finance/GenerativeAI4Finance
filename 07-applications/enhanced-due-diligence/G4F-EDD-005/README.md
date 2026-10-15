# G4F-EDD-005: Entity resolution for company records

This task compares company records from different sources and ranks candidate pairs for
analyst review. A score is evidence for prioritization, not proof that records describe
the same legal entity. Every result starts `unconfirmed`; a person makes the decision.

## Run it

From this directory:

```sh
python -m pip install -r requirements.txt
python -m pytest
python -m entity_resolution data/synthetic_companies.json --hide-no-match
```

Use `--json` for structured output, `--config config.json` to override thresholds or
weights, and omit `--hide-no-match` to see every candidate label. Invalid input prints
an `error:` message and exits with code 2. Input JSON is read as UTF-8; record strings
with unpaired surrogates are rejected safely. Text output escapes terminal controls;
JSON retains the structured values. Use a UTF-8 terminal for non-Latin text output.

A minimal Python API call:

```python
from entity_resolution import load_records, resolve

result = resolve(load_records("data/synthetic_companies.json"))
for pair in result.matches:
    print(pair.left_id, pair.right_id, pair.score, pair.label, pair.status)
```

`resolve` returns a `Resolution` with `matches` and `skipped_blocks`; each `MatchResult`
includes immutable evidence and status `unconfirmed`. `record_decision(result, reviewer,
accepted, note="")` creates a separate confirmed or rejected review record. It does not
mutate the match result.

## Input records

The JSON file has a top-level `records` array. Each object requires a unique `record_id`
and a `name` containing at least one letter or digit. Optional fields are `source`,
`aliases` (a list of strings), `registration_id`, `id_scheme`, `jurisdiction`, and
`city`. Unknown fields and invalid values are rejected.

`id_scheme` identifies the numbering system, for example `CIN` or `GB company number`.
IDs are compared only when both records have the same known jurisdiction. With matching
jurisdictions, different IDs are a conflict only when both records name the same scheme.
If either scheme is missing, differing IDs are unverified; if named schemes differ, or the
jurisdiction is unknown or different, the IDs are not comparable. Different named schemes
are not combined into one ID block.

Jurisdictions are uppercased; the aliases `UK` and `GBR` map to `GB` (along with a small
code table in `normalize.py`). Numeric-only IDs lose leading zeroes (`00445790` equals
`445790`); alphanumeric IDs retain them. Separators are removed, and placeholders such
as `N/A`, `NONE`, and `000` are treated as missing.

## Matching behavior

Names are casefolded, Latin accents are removed, `&` becomes `and`, punctuation
separates words, and a small table expands abbreviations and spelling variants. Trailing
legal forms are retained separately from the name core. Letters in other scripts remain
intact. A small placeholder table maps selected variants such as `Shree` and `Shri` to
`sri`; it is not a transliteration engine.

Candidates share either a registration ID with compatible jurisdiction/scheme or a
distinctive name token. Common tokens such as `trading` and `international` are excluded
from name blocking. Defaults limit name blocks to 50 records and registration ID blocks
to 1000. Oversized blocks are skipped and reported in `skipped_blocks` and CLI warnings;
pairs can still be generated through another shared block. Pairs with no shared blocking
key are not considered.

Default score signals are:

| Evidence | Score effect |
|---|---:|
| Name similarity (`rapidfuzz` token-sort ratio, best comparable name/alias) | 0–100 × 0.65 |
| Same registration ID, jurisdiction, and compatible scheme | +25 |
| Same jurisdiction | +10 |
| Different jurisdiction | −15 |
| Same city | +5 |
| Different legal-form families | −5 |

Scores are clipped to 0–100. A same-scheme ID conflict caps the score at 30. Without a
matching ID, the default cap is 79.9, so names and places alone cannot produce a likely
match. A matching ID keeps the score at least at the review threshold. Names from
different scripts are not compared by spelling: when no comparable alias exists, the
pair is placed between the review threshold and just below the likely-match threshold,
unless a same-scheme ID conflict vetoes it. Low normalization coverage also prevents a
likely-match score.

Default labels use full-precision scores: `likely match` at 80 or above, `needs review`
at 55 or above, and `no match` below 55. Name similarity and coverage retain full
precision for scoring; readable similarity notes round to one decimal. Displayed total
scores normally round to one decimal, with extra precision retained when rounding would
cross a label threshold or configured cap/floor.

For example, `REG-001` and `VEN-001` share a cleaned name, jurisdiction, and city but no
ID. Their score is capped at 79.9 and labeled `needs review`, not likely match.
`REG-004` and `REG-005` have the same cleaned name but different IDs in the same
jurisdiction and scheme, so their score is capped at 30. These records are candidates,
not confirmed entity links.

## Configuration

Pass a JSON object with any subset of `MatchConfig` fields:

```json
{"likely_match": 85, "needs_review": 60, "id_conflict_cap": 20}
```

The configuration rejects unknown keys, out-of-range values, and inconsistent
thresholds. `needs_review` must be below `likely_match`; by default `id_conflict_cap`
must be below `needs_review`. `allow_id_conflict_review` opts out of that restriction.
`no_id_cap`, if provided, must be at least `needs_review` and below `likely_match`.
`min_name_coverage` defaults to 0.5. The defaults were selected by hand against
synthetic examples, not tuned on labeled data.

## Data and limits

`data/synthetic_companies.json` contains fictional companies, IDs, and aliases;
jurisdiction codes and city names are real places used for realistic examples. It
contains no personal or customer data. The bundled records are wholly synthetic;
no root or applicable dataset licence is declared. Maintainer guidance on an
appropriate contribution and dataset licence is requested.

Blocking can miss a full rename or names that share no distinctive token, ID, or alias.
Oversized blocks are reported but not fully compared. Token-sort similarity ignores word
order and can rate unrelated names with the same words highly. The abbreviation,
legal-form, and variant tables are limited; there is no transliteration between scripts,
and Chinese or Japanese names are not split into words. Removing ID separators can make
differently formatted numbers equivalent. City comparison ignores case, accents, and
punctuation and does not parse addresses. Parent companies and subsidiaries can still
reach review. Passing tests on synthetic data does not establish accuracy on real
registry data.
