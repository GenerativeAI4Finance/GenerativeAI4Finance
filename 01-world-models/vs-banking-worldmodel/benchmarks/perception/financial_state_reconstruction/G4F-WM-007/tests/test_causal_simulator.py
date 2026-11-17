import json
import tempfile
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from simulator.causal_simulator import (
    DEFAULT_CONFIG,
    apply_intervention,
    generate_cohort,
    load_config,
    simulate,
    write_dataset,
)


def _arm(config, arm_id):
    return next(arm for arm in config["intervention_arms"] if arm["arm_id"] == arm_id)


def test_seeded_simulation_is_reproducible():
    config = load_config(DEFAULT_CONFIG)
    first = simulate(config)
    second = simulate(config)
    assert first == second


def test_observations_are_separate_and_held_fixed_across_interventions():
    config = load_config(DEFAULT_CONFIG)
    features, policies, records, _ = simulate(config)
    assert len(records) == len(features) * len(config["intervention_arms"])
    for entity_id in {record["entity_id"] for record in records}:
        entity_records = [record for record in records if record["entity_id"] == entity_id]
        assert len({json.dumps(record["observational_features"], sort_keys=True) for record in entity_records}) == 1
        assert len({record["simulation_context"]["shared_exogenous_shock"] for record in entity_records}) == 1
        assert {record["arm_id"] for record in entity_records} == {arm["arm_id"] for arm in config["intervention_arms"]}
    assert len(policies) == len(features)
    assert "interest_rate_pct" not in features[0]


def test_each_noncontrol_arm_changes_only_its_configured_policy_variable():
    config = load_config(DEFAULT_CONFIG)
    _, policies, _, = generate_cohort(config)
    baseline = policies[0]
    control = apply_intervention(baseline, _arm(config, "observed_policy"), config)
    expectations = {
        "rate_reduction_2pp": "interest_rate_pct",
        "term_extension_12m": "term_months",
        "limit_increase_20pct": "credit_limit_usd",
        "collections_delay_plus_15d": "collections_delay_days",
    }
    for arm_id, changed_key in expectations.items():
        intervened = apply_intervention(baseline, _arm(config, arm_id), config)
        changed = {key for key in control if control[key] != intervened[key]}
        assert changed == {changed_key}


def test_generated_outcomes_obey_bounds_and_arm_directions():
    config = load_config(DEFAULT_CONFIG)
    features, policies, records, _ = simulate(config)
    lookup = {(row["entity_id"], row["arm_id"]): row for row in records}
    for row in records:
        outcome = row["outcomes"]
        assert outcome["monthly_payment_usd"] >= 0
        assert 0 <= outcome["modeled_default_probability"] <= 1
        assert row["synthetic"] is True
        assert row["observational_features"]["monthly_income_usd"] > 0
    entity_id = features[0]["entity_id"]
    baseline = lookup[(entity_id, "observed_policy")]
    assert lookup[(entity_id, "rate_reduction_2pp")]["outcomes"]["monthly_payment_usd"] < baseline["outcomes"]["monthly_payment_usd"]
    assert lookup[(entity_id, "term_extension_12m")]["outcomes"]["monthly_payment_usd"] < baseline["outcomes"]["monthly_payment_usd"]
    assert lookup[(entity_id, "limit_increase_20pct")]["intervention"]["credit_limit_usd"] > policies[0]["credit_limit_usd"]
    assert lookup[(entity_id, "collections_delay_plus_15d")]["outcomes"]["modeled_default_probability"] > baseline["outcomes"]["modeled_default_probability"]


def test_manifest_and_outputs_are_reproducible():
    task_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix=".wm007-test-", dir=task_root) as temporary_root:
        tmp_path = Path(temporary_root)
        first_dir = tmp_path / "first"
        second_dir = tmp_path / "second"
        first = write_dataset(DEFAULT_CONFIG, first_dir)
        second = write_dataset(DEFAULT_CONFIG, second_dir)
        assert first["output_sha256"] == second["output_sha256"]
        assert first["potential_outcome_record_count"] == first["entity_count"] * first["intervention_arm_count"]
        assert json.loads((first_dir / "manifest.json").read_text(encoding="utf-8")) == first


def test_schema_and_config_are_valid_json():
    task_root = Path(__file__).resolve().parents[1]
    schema = json.loads((task_root / "schema" / "potential_outcome.schema.json").read_text(encoding="utf-8"))
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    assert schema["$schema"].endswith("2020-12/schema")
    assert config["intervention_arms"][0]["kind"] == "control"


def test_generated_potential_outcomes_validate_against_schema():
    task_root = Path(__file__).resolve().parents[1]
    schema = json.loads((task_root / "schema" / "potential_outcome.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    _, _, records, _ = simulate(load_config(DEFAULT_CONFIG))
    for record in records:
        validator.validate(record)
    invalid = dict(records[0])
    invalid.pop("outcomes")
    assert list(validator.iter_errors(invalid))


def test_duplicate_arm_id_is_rejected():
    config = load_config(DEFAULT_CONFIG)
    config["intervention_arms"].append(dict(config["intervention_arms"][0]))
    with pytest.raises(ValueError, match="unique"):
        from simulator.causal_simulator import load_config as _load

        # Validation is applied when loading a configuration file.
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            _load(path)
