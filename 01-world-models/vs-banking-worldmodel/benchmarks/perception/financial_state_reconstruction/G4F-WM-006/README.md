# G4F-WM-006: Event-to-State Transition Dataset

This folder defines a deterministic synthetic format and generator for replayable
financial-state transitions. Each transition stores the state before an event,
the event and optional action, the resulting state, and its UTC timestamp.

## Contents

- `schema/event_state_transition.schema.json` — JSON Schema Draft 2020-12 for a transition record.
- `config/transition_scenarios.json` — seeded initial-state ranges and normal, stress, and recovery paths.
- `generator/transition_generator.py` — scenario replay, transition logic, JSON/CSV writer, and manifest writer.
- `data/sample/example_trajectories.json` — complete records with nested initial/result states.
- `data/sample/transitions.csv` — tabular form of the same transitions; state and event details are JSON-encoded columns.
- `data/sample/manifest.json` — dataset/generator version, seed, row/path/event counts, configuration and output hashes.
- `data_dictionary.md` — fields, rules, assumptions, and limitations.

## Generate or replay

From this folder:

```bash
python -m pip install -r requirements.txt
python -m generator.transition_generator
```

Use a different configuration or output directory with:

```bash
python -m generator.transition_generator --config config/transition_scenarios.json --output-dir data/sample
```

To replay a path in Python, load the JSON configuration and call
`generator.transition_generator.replay_scenario(config, scenario, initial_state)`.
The explicit initial state and ordered event configuration fully determine the
resulting transition sequence. The sample generator uses a fixed NumPy seed to
draw each scenario's starting values. A different seed changes those starting
values while preserving the configured event paths.

## Relationship to earlier World Models tasks

The record captures prediction-time state, event/action and timestamp concepts
from WM-001, uses fully fictional seeded scenario data consistent with WM-002
and WM-003, and follows the explicit state transition vocabulary in WM-004's
validation configuration. This folder is runnable independently; it does not
import or modify another task folder. All generated rows are marked synthetic.

This is a simulation and software fixture, not an empirical model, forecast,
credit decision, or claim about real borrowers or businesses.
