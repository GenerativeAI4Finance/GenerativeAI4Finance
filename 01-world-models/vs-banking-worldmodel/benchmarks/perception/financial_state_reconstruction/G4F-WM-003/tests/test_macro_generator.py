import hashlib
import json
from pathlib import Path
import tempfile

import pandas.testing as pdt
import pytest

from generator.macro_generator import generate_dataset, validate_dataset, write_dataset


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "scenarios.json"


def test_generation_is_seeded_and_reproducible():
    first = generate_dataset(CONFIG)
    second = generate_dataset(CONFIG)
    for name in first:
        pdt.assert_frame_equal(first[name], second[name])
    validate_dataset(first, CONFIG)


def test_stress_path_applies_configured_macro_and_sector_shocks():
    data = generate_dataset(CONFIG)
    macro = data["macro_sequences"]
    shock_start = 8
    baseline = macro[(macro["scenario"] == "baseline") & (macro["sector"] == "manufacturing")].sort_values("month_index")
    stress = macro[(macro["scenario"] == "stress") & (macro["sector"] == "manufacturing")].sort_values("month_index")
    assert (stress.loc[stress["month_index"] < shock_start, "policy_rate_pct"].to_numpy() == baseline.loc[baseline["month_index"] < shock_start, "policy_rate_pct"].to_numpy()).all()
    assert (stress.loc[stress["month_index"] >= shock_start, "policy_rate_pct"].to_numpy() > baseline.loc[baseline["month_index"] >= shock_start, "policy_rate_pct"].to_numpy()).all()
    assert (stress.loc[stress["month_index"] >= shock_start, "commodity_price_index"].to_numpy() > baseline.loc[baseline["month_index"] >= shock_start, "commodity_price_index"].to_numpy()).all()
    assert (stress.loc[stress["month_index"] >= shock_start, "sector_demand_index"].to_numpy() < baseline.loc[baseline["month_index"] >= shock_start, "sector_demand_index"].to_numpy()).all()


def test_outcomes_are_linked_to_both_scenarios_and_labelled_assumptions():
    data = generate_dataset(CONFIG)
    outcomes = data["business_outcomes"]
    assert set(outcomes["business_id"]) == set(data["businesses"]["business_id"])
    assert set(outcomes["scenario"]) == {"baseline", "stress"}
    assert (outcomes["relationship_type"] == "simulation_assumption").all()
    baseline = outcomes[outcomes["scenario"] == "baseline"].set_index(["business_id", "date"])
    stress = outcomes[outcomes["scenario"] == "stress"].set_index(["business_id", "date"])
    assert (baseline["cashflow_change_vs_baseline_index"] == 0).all()
    assert (stress["cashflow_change_vs_baseline_index"] != 0).any()
    assert not baseline["cashflow_stress_flag"].any()
    assert stress["cashflow_stress_flag"].any()


def test_invalid_shock_start_is_rejected():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["scenarios"]["stress"]["shock_start_month_index"] = config["periods"]
    with pytest.raises(ValueError, match="inside the sequence"):
        generate_dataset(config)


def test_writer_manifest_hashes_and_csv_bytes_are_reproducible():
    data = generate_dataset(CONFIG)
    with tempfile.TemporaryDirectory(prefix="g4f-wm003-test-", dir=ROOT / "data") as temp_dir:
        output = write_dataset(data, temp_dir, CONFIG)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["seed"] == 20261111
        assert manifest["synthetic"] is True
        first_bytes = {file.name: file.read_bytes() for file in output.iterdir()}
        for filename, digest in manifest["output_sha256"].items():
            assert hashlib.sha256((output / filename).read_bytes()).hexdigest() == digest
        write_dataset(generate_dataset(CONFIG), output, CONFIG)
        assert first_bytes == {file.name: file.read_bytes() for file in output.iterdir()}
