# G4F-EDD-005: Entity resolution for company records

Compares company records from different sources (registry extract, vendor list, news mention and so on) and suggests which ones might refer to the same company. Every suggestion comes with a score and the evidence behind it. An analyst makes the final call.

A score here is a ranking aid. It is not proof that two records are the same legal entity.

## Layout

```
entity_resolution/
  normalize.py   name, identifier, jurisdiction and city cleanup
  resolve.py     validation, candidate generation, scoring, review decisions
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

Useful flags: `--hide-no-match` to drop low scores, `--json` for machine-readable output, `--config my_config.json` to override thresholds or weights. Bad input (a missing name, an unknown field, a misspelt config key) stops the run with an `error:` line and exit code 2 instead of a traceback. Files are read as UTF-8, and the CLI writes UTF-8 whatever the console code page is.

Sample output of `python -m entity_resolution data/synthetic_companies.json --hide-no-match`:

```
thresholds: likely match >= 80.0, needs review >= 55.0
scores rank candidates for review; they do not establish that two records are the same company.

REG-002 <> VEN-002  score=100.0  likely match  [unconfirmed]
    - name similarity 100.0 ('sri vaibhav lakshmi textiles' vs 'sri vaibhav lakshmi textiles')
    - same jurisdiction (IN)
    - registration ID matches (SYN-IN-100877)
    - same city (Surat)
REG-003 <> VEN-003  score=100.0  likely match  [unconfirmed]
    - name similarity 100.0 ('zbl research' vs 'zbl research')
    - best name match uses an alias: 'ZBL Research' / 'ZBL Research'
    - same jurisdiction (US)
    - registration ID matches (SYN-US-55120)
    - same city (Austin)
REG-006 <> VEN-006  score=100.0  likely match  [unconfirmed]
    - name similarity 100.0 ('orvane manufacturing international' vs 'orvane manufacturing international')
    - same jurisdiction (GB)
    - registration ID matches (SYN-GB-04410)
REG-001 <> VEN-001  score=79.9  needs review  [unconfirmed]
    - name similarity 100.0 ('quillon agro exports' vs 'quillon agro exports')
    - same jurisdiction (IN)
    - registration ID missing on at least one record
    - same city (Pune)
    - no matching registration ID, so the score is capped at 79.9 and cannot be a likely match
VEN-005 <> NEWS-002  score=75.0  needs review  [unconfirmed]
    - name similarity 100.0 ('marlowe finch logistics' vs 'marlowe finch logistics')
    - same jurisdiction (US)
    - registration ID missing on at least one record
REG-001 <> NEWS-001  score=58.8  needs review  [unconfirmed]
    - name similarity 75.0 ('quillon agro exports' vs 'quillon agro')
    - same jurisdiction (IN)
    - registration ID missing on at least one record
VEN-001 <> NEWS-001  score=58.8  needs review  [unconfirmed]
    - name similarity 75.0 ('quillon agro exports' vs 'quillon agro')
    - same jurisdiction (IN)
    - registration ID missing on at least one record
REG-007 <> VEN-008  score=55.0  needs review  [unconfirmed]
    - names are in different scripts (Cyrillic vs Latin): 'Северный Ветер Трейдинг ООО' vs 'Severnyi Veter Trading OOO' cannot be scored by spelling, so the pair goes to human review
    - same jurisdiction (RU)
    - registration ID matches (SYN-RU-30112)
    - same city (Moscow)
REG-008 <> VEN-009  score=55.0  needs review  [unconfirmed]
    - name similarity 21.4 ('ashgrove dairy' vs 'pelham widgets')
    - same jurisdiction (GB)
    - registration ID matches (SYN-GB-21500)
    - same city (York)
    - registration ID matches but the names differ (similarity 21.4); this may be a renamed company, or a wrong ID, so it needs review
```

The vetoed common-name case only shows up without `--hide-no-match`. The names are identical after cleanup, but the two records carry different numbers from the same registry (they are labelled with the same `id_scheme`), so it is not treated as a match:

```
REG-004 <> REG-005  score=30.0  no match  [unconfirmed]
    - name similarity 100.0 ('northgate trading' vs 'northgate trading')
    - same jurisdiction (GB)
    - registration IDs conflict (SYN-GB-07731 vs SYN-GB-09914, same scheme), score capped at 30.0
```

Things to notice in the sample run:

- `REG-001 <> VEN-001` has the same name, jurisdiction and city but no shared registration ID, so it stops at 79.9 and goes to review. Without an identifier, names and places alone are not enough for a likely match.
- `REG-007 <> VEN-008` is a Cyrillic name against its Latin spelling. They cannot be compared by spelling, so the pair is flagged and sent to review, not scored 0 and not scored high.
- `REG-008 <> VEN-009` has the same registration ID but completely different names. A matching ID never drops below review, and the note says it may be a rename.

## Records

Records are JSON objects. Unknown fields are rejected so a typo like `"country"` is not silently ignored.

| Field | Notes |
|---|---|
| `record_id` | required, unique string |
| `name` | required string with at least one letter or digit |
| `source` | optional string |
| `aliases` | optional list of strings (a single string is rejected, not split into letters) |
| `registration_id` | optional string |
| `id_scheme` | optional label for which registry or numbering scheme `registration_id` comes from, for example `"CIN"` or `"GB company number"` |
| `jurisdiction` | optional code such as `GB` (`UK` and `GBR` are read as `GB`; case and padding are ignored) |
| `city` | optional string |

## How it works

**1. Normalisation.** Names are casefolded and accents are removed from Latin letters. `&` becomes `and`, apostrophes are dropped (`Int'l` becomes `intl`, then `international`) and dots inside an initialism are dropped (`P.V.T.` becomes `pvt`) while a dot between words splits them (`Pvt.Ltd.` is `pvt ltd`). Letters with no accent form are folded too (`ß`, `ø`, `ł`, `æ`). A few abbreviations are expanded (`Mfg` to `manufacturing`, `Intl` to `international`). Trailing legal suffixes are stripped and kept separately, so `Pvt. Ltd.`, `Private Limited`, `Pte Ltd` and `Pty Ltd` all become the legal form `private limited` and don't affect the name comparison. The list also covers `AG`, `SA`, `BV`, `NV`, `SpA`, `Srl`, `Sarl` and `A/S`.

Letters in other scripts (Cyrillic, Greek, Arabic, Han and so on) are kept and casefolded, not dropped. The script of each name is recorded, along with how much of the name survived cleanup.

Registration IDs are uppercased with separators removed. IDs made only of digits also lose leading zeros, so `00445790` equals `445790`. Placeholders such as `N/A` or `000` count as missing. Jurisdictions are canonical upper-case codes with a short alias table, and cities are compared ignoring case, accents and punctuation.

Transliteration of Latin spellings is handled by a small placeholder table (`Shree`/`Shri` to `sri`, `Laxmi` to `lakshmi`, and so on) in `normalize.py`. It is meant to be extended per jurisdiction, not treated as a real transliteration step. Nothing converts between scripts.

**2. Candidate generation (blocking).** Records are only compared if they share a registration ID or a distinctive name token. These are two kinds of block with separate limits:

- ID blocks group records with the same ID within a jurisdiction (the key includes the jurisdiction, so the same number in two countries does not pair up). IDs are strong evidence, so `max_id_block_size` is high (1000).
- Name-token blocks group records sharing a distinctive word. Words that show up in lots of company names (`trading`, `exports`, `international`...) are not used as keys. Blocks bigger than `max_block_size` (50) are not compared, so one very common token doesn't blow up into every possible pair.

A skipped block is never silent. `generate_candidates` and `resolve` return the skipped blocks (kind, key, size, limit, pairs not compared), the CLI prints a warning listing them, and `--json` includes a `skipped_blocks` list. Pairs in a skipped block are still found if they share some other block, for example an ID.

**3. Scoring.** For each candidate pair:

| Signal | Effect (defaults) |
|---|---|
| Name similarity (rapidfuzz `token_sort_ratio` on cleaned names, best of name and aliases) | 0 to 100, times `name_weight` 0.65 |
| Same registration ID, same jurisdiction, compatible scheme | +25 |
| Same jurisdiction | +10 |
| Different jurisdiction | -15 |
| Same city | +5 |
| Legal forms from different families (e.g. limited vs LLP) | -5 |

Then these rules apply:

| Rule | Effect (defaults) |
|---|---|
| Different registration IDs from the same scheme and jurisdiction | score capped at 30 (`id_conflict_cap`) |
| No matching registration ID | score capped at 79.9, just under `likely_match` (`no_id_cap`) |
| Names in different scripts, or much of a name lost in cleanup | pair is routed to review: score kept between `needs_review` and just under `likely_match` |
| Matching registration ID | score at least `needs_review`, with a note when the names differ (possible rename) |

The result is clipped to 0..100. IDs are only compared when both records have the same jurisdiction, and a conflict needs both records to name the same `id_scheme`. If the scheme is not given on both, two different IDs might be different kinds of number (a company number and a tax number), so the evidence says `unverified`, the pair stays below a likely match, and it is not vetoed. IDs with different schemes are not compared at all. Each result lists which of these fired in `evidence.notes`, plus the name pair that gave the best similarity and whether an alias was involved.

Names in different scripts are compared only against variants in the same script, which an alias can supply. If no variant pair shares a script, `evidence.cross_script` is true and `evidence.name.score` is null.

**4. Labels.**

| Label | Default |
|---|---|
| likely match | score >= 80 |
| needs review | score >= 55 |
| no match | below 55 |

Where a call is doubtful, the pair goes to a person rather than being decided by the code: unlabelled ID differences, cross-script names and renamed companies all end up in "needs review".

**5. Review decisions.** A `MatchResult` is immutable and always reports its status as `unconfirmed`. The matcher never confirms anything. `record_decision(result, reviewer, accepted, note)` returns a separate record with `confirmed` or `rejected`, the reviewer's name (blank names are rejected) and the score and label the reviewer was shown. It does not change the result; storing the decision is up to the caller.

## Configuration

All thresholds and weights live in `MatchConfig` in `resolve.py`. To change them, pass a JSON file with any subset of the fields:

```json
{"likely_match": 85, "needs_review": 60, "id_conflict_cap": 20}
```

The config is checked when it is loaded: unknown keys are rejected (with a "did you mean" hint), values must be numbers in range, and the relationships have to make sense:

- `needs_review` must be below `likely_match`.
- `id_conflict_cap` must be below `needs_review`, so an ID conflict always ends as "no match". Set `allow_id_conflict_review` to true to opt out and let conflicting pairs reach review.
- `no_id_cap` is optional. Left out, it is just under `likely_match`, so a likely match always needs a matching ID. If set it must be at least `needs_review` and below `likely_match`.
- `min_name_coverage` (default 0.5) is the share of a name's characters that has to survive cleanup before the name is trusted for a likely match.

The defaults were picked by hand against the sample data, not tuned on a labelled set, so treat them as a starting point.

## Data

`data/synthetic_companies.json` is made up for this task. The companies, registration numbers (`SYN-...`) and aliases are fictional. Jurisdiction codes and city names are real places, used only to make the records look realistic. No personal or customer data is included. Version 1.0, same licence as this repository.

## Why not pandas

The task lists pandas as a tool. It is not used here. The input is a short JSON list, pairs are scored one at a time with rapidfuzz, and the output is a list of small result objects, so the standard library covers it and adding pandas would only be an extra dependency.

## Limitations

- Blocking misses pairs that share no ID and no distinctive token, for example a company that was fully renamed, or one known only by an acronym that isn't listed as an alias. A Cyrillic name and its Latin spelling are only paired if they share an ID, an alias, or a token.
- Blocks over the size limit are reported but not compared. A pair whose only shared keys sit in skipped blocks is missed, and the warning is how you find out.
- `token_sort_ratio` ignores word order, which helps with reordered names but can also score unrelated names with the same words highly ("Bank of Ohio" and "Ohio Bank" both clean to the same words).
- The abbreviation, legal form and transliteration tables are short and English/Indian/European centric. Non-Latin scripts are compared as text only: there is no transliteration between scripts, and Chinese or Japanese names are not split into words, so a whole run of characters is one token.
- Without a matching ID a pair can never be a likely match, so true matches that lack IDs always need a person to look at them.
- Removing separators from IDs means `12-3456` and `123-456` look the same.
- City comparison ignores case, accents and punctuation. There is no address parsing.
- Group companies (parent and subsidiary with similar names) can score as "needs review". That is expected; they are related but not the same entity.
- Passing tests means the scoring behaves as described on synthetic data. It says nothing about accuracy on real registry data.
