# G4F-EDD-005: Entity resolution for company records

Compares company records from different sources (registry extract, vendor list, news mention and so on) and suggests which ones might refer to the same company. Every suggestion comes with a score and the evidence behind it. An analyst makes the final call.

A score here is a ranking aid. It is not proof that two records are the same legal entity.

## Layout

```
entity_resolution/
  normalize.py   name and identifier cleanup
  resolve.py     candidate generation, scoring, review decisions
  __main__.py    CLI
data/synthetic_companies.json   fictional sample records
tests/
```

## Running it

```
pip install -r requirements.txt
python -m entity_resolution data/synthetic_companies.json
python -m pytest
```

Useful flags: `--hide-no-match` to drop low scores, `--json` for machine-readable output, `--config my_config.json` to override thresholds or weights.

Sample output:

```
REG-001 <> VEN-001  score=80.0  likely match  [unconfirmed]
    - name similarity 100.0 ('quillon agro exports' vs 'quillon agro exports')
    - same jurisdiction (IN)
    - registration ID missing on at least one record
    - same city (Pune)
REG-004 <> REG-005  score=30.0  no match  [unconfirmed]
    - name similarity 100.0 ('northgate trading' vs 'northgate trading')
    - same jurisdiction (GB)
    - registration IDs conflict (SYN-GB-07731 vs SYN-GB-09914), score capped at 30.0
```

The second pair is the common-name case: identical names after cleanup, but two different registration numbers in the same registry, so it is not treated as a match.

## How it works

**1. Normalisation.** Names are ASCII-folded, lowercased, `&` becomes `and`, and punctuation is dropped (`P.V.T.` becomes `pvt`). A few abbreviations are expanded (`Mfg` to `manufacturing`, `Intl` to `international`). Trailing legal suffixes are stripped and kept separately, so `Pvt. Ltd.`, `Private Limited` and `Pte Ltd` all become the legal form `private limited` and don't affect the name comparison. Registration IDs are uppercased with separators removed.

Transliteration is handled by a small placeholder table (`Shree`/`Shri` to `sri`, `Laxmi` to `lakshmi`, and so on) in `normalize.py`. It is meant to be extended per jurisdiction, not treated as a real transliteration step.

**2. Candidate generation (blocking).** Records are only compared if they share a registration ID or a distinctive name token. Words that show up in lots of company names (`trading`, `exports`, `international`...) are not used as keys. Blocks bigger than `max_block_size` are skipped so one very common token doesn't blow up into every possible pair.

**3. Scoring.** For each candidate pair:

| Signal | Effect (defaults) |
|---|---|
| Name similarity (rapidfuzz `token_sort_ratio` on cleaned names, best of name and aliases) | 0 to 100, times `name_weight` 0.65 |
| Same registration ID, same jurisdiction | +25 |
| Same jurisdiction | +10 |
| Different jurisdiction | -15 |
| Same city | +5 |
| Legal forms from different families (e.g. limited vs LLP) | -5 |
| Different registration IDs, same jurisdiction | score capped at 30 |

The result is clipped to 0..100. IDs from different jurisdictions are not compared, since registries number independently. Each result lists which of these fired in `evidence.notes`, plus the name pair that gave the best similarity and whether an alias was involved.

**4. Labels.**

| Label | Default |
|---|---|
| likely match | score >= 80 |
| needs review | score >= 55 |
| no match | below 55 |

Every result starts as `unconfirmed`. `record_decision(result, reviewer, accepted, note)` builds a confirmed or rejected record with the reviewer's name and the score they were shown. The matcher never sets this itself.

## Configuration

All thresholds and weights live in `MatchConfig` in `resolve.py`. To change them, pass a JSON file with any subset of the fields:

```json
{"likely_match": 85, "needs_review": 60, "id_conflict_cap": 20}
```

`needs_review` has to be at or below `likely_match`. Keep `id_conflict_cap` under `needs_review` if conflicting IDs should always end up as "no match". The defaults were picked by hand against the sample data, not tuned on a labelled set, so treat them as a starting point.

## Data

`data/synthetic_companies.json` is made up for this task. The companies, registration numbers (`SYN-...`) and aliases are fictional. Jurisdiction codes and city names are real places, used only to make the records look realistic. No personal or customer data is included. Version 1.0, same licence as this repository.

## Limitations

- Blocking misses pairs that share no ID and no distinctive token, for example a company that was fully renamed, or one known only by an acronym that isn't listed as an alias.
- `token_sort_ratio` ignores word order, which helps with reordered names but can also score unrelated names with the same words highly.
- The abbreviation and transliteration tables are short and English/Indian-centric. Non-Latin scripts are not handled beyond accent folding.
- City comparison is exact string match. There is no address parsing.
- Group companies (parent and subsidiary with similar names) can score as "needs review". That is expected; they are related but not the same entity.
- Passing tests means the scoring behaves as described on synthetic data. It says nothing about accuracy on real registry data.
