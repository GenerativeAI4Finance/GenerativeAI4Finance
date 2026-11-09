# G4F-WM-001: Financial Event and State Schema

This folder defines a time-stamped, synthetic record format for financial
entity states, events, actions, observations, and later outcomes. It is
self-contained and uses JSON Schema Draft 2020-12.

## Files

- `schema/financial_event.schema.json` — input schema. Prediction-time
  features and post-prediction outcomes are separate, closed objects.
- `data_dictionary.md` — field definitions, timing rules, and missingness.
- `examples/synthetic_records.json` — three fictional records, including an
  explicitly missing feature.
- `tests/test_schema.py` — validates examples and checks structural leakage
  guards.
- `requirements.txt` — validator and test dependencies.

## Leakage boundary

`prediction_time_utc` is the point at which the record is scored. Values under
`features_at_t` are observations available by that time. Realized events and
labels belong only under `outcomes_after_t`; they are not model inputs. Outcome
timestamps must be later than the prediction time and no later than the end of
the declared target horizon. JSON Schema closes the feature and outcome
objects so a target field cannot be added to the feature block unnoticed.
Cross-field timestamp ordering must also be checked by a consuming pipeline;
JSON Schema alone cannot compare two date-time values.

All sample entities and values are fictional. The examples are format
illustrations, not financial advice, credit decisions, or claims about real
persons or companies.

## Validate the examples

From this directory, run:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```
