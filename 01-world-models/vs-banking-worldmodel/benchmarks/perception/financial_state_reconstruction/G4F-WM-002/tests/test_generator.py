import json
import hashlib
from pathlib import Path
import tempfile

import pandas as pd
import pandas.testing as pdt
import pytest

from generator.borrower_generator import generate_dataset, validate_dataset, write_dataset


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "generator.json"


def test_generation_is_reproducible_and_valid():
    first = generate_dataset(CONFIG)
    second = generate_dataset(CONFIG)
    for name in first:
        pdt.assert_frame_equal(first[name], second[name])
    validate_dataset(first, CONFIG)


def test_configured_paths_and_cure_default_progression_are_present():
    dataset = generate_dataset(CONFIG)
    loans = dataset["loans"]
    states = dataset["monthly_states"]
    assert set(loans["scenario_path"]) == {"normal_repayment", "liquidity_stress", "delinquency", "cure", "default"}
    cure_id = loans.loc[loans["scenario_path"] == "cure", "loan_id"].iloc[0]
    cure_states = states.loc[states["loan_id"] == cure_id].sort_values("month_index")
    assert "cured" in set(cure_states["financial_state"])
    cure_repayments = dataset["repayment_history"].loc[dataset["repayment_history"]["loan_id"] == cure_id]
    assert "paid_late" in set(cure_repayments["payment_status"])
    default_id = loans.loc[loans["scenario_path"] == "default", "loan_id"].iloc[0]
    default_states = states.loc[states["loan_id"] == default_id].sort_values("month_index")
    assert default_states.iloc[-1]["financial_state"] == "default"
    assert default_states.iloc[-1]["days_past_due"] >= 90


def test_cash_flow_and_balance_constraints():
    dataset = generate_dataset(CONFIG)
    states = dataset["monthly_states"]
    assert (states["net_cash_flow_usd"] == (states["monthly_income_usd"] - states["monthly_expenses_usd"]).round(2)).all()
    assert (states["outstanding_balance_usd"] >= 0).all()
    assert (states["days_past_due"] >= 0).all()
    stressed = states[states["financial_state"] == "liquidity_stress"]
    assert not stressed.empty
    assert (stressed["net_cash_flow_usd"] < 0).all()
    validate_dataset(dataset, CONFIG)


def test_invalid_scenario_month_index_is_rejected():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["assumptions"]["cure_month_index"] = config["observation_months"]
    with pytest.raises(ValueError, match="month indices"):
        generate_dataset(config)


def test_writer_manifest_records_seed_hash_and_counts():
    dataset = generate_dataset(CONFIG)
    with tempfile.TemporaryDirectory(prefix="g4f-wm002-test-", dir=ROOT / "data") as temp_dir:
        output = write_dataset(dataset, temp_dir, CONFIG)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["seed"] == 20261110
        assert manifest["generator_version"] == "1.0.0"
        assert manifest["synthetic"] is True
        assert manifest["row_counts"]["borrowers"] == len(dataset["borrowers"])
        assert manifest["scenario_counts"] == {"cure": 3, "default": 3, "delinquency": 3, "liquidity_stress": 3, "normal_repayment": 4}
        reread = pd.read_csv(output / "monthly_states.csv")
        assert len(reread) == len(dataset["monthly_states"])
        first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
        for filename, digest in manifest["output_sha256"].items():
            assert hashlib.sha256((output / filename).read_bytes()).hexdigest() == digest
        write_dataset(generate_dataset(CONFIG), output, CONFIG)
        assert first_bytes == {path.name: path.read_bytes() for path in output.iterdir()}
