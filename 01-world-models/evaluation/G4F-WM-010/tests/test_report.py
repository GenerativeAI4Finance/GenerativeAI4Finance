import json
from pathlib import Path

import pytest

import evaluate as cli
from make_synthetic import generate
from scenario_eval.contract import join
from scenario_eval.report import SINGLE_CLASS_REASON, evaluate, to_markdown


@pytest.fixture(scope="module")
def example():
    preds, outs = generate(seed=7)
    return join(preds, outs)


@pytest.fixture(scope="module")
def report(example):
    return evaluate(example, seed=0, n_boot=100)


def test_each_scenario_reported_separately(report):
    assert set(report["scenarios"]) == {"baseline", "normal", "stress"}
    assert "pooled_all_scenarios" not in report
    n = report["metadata"]["n_per_scenario"]
    for name, res in report["scenarios"].items():
        assert res["binary"]["n"] == n[name]


def test_stress_miscalibration_shows_up(report):
    s = report["scenarios"]
    assert s["stress"]["binary"]["ece_equal_width"] > 5 * s["baseline"]["binary"]["ece_equal_width"]
    # the synthetic predictor under-predicts under stress
    assert s["stress"]["binary"]["calibration_in_the_large"] < -0.05
    stress_ci = s["stress"]["binary"]["bootstrap_95"]["ece_equal_width"]["ci"]
    base_ci = s["baseline"]["binary"]["bootstrap_95"]["ece_equal_width"]["ci"]
    assert stress_ci[0] > base_ci[1]


def test_pooled_view_is_opt_in_and_labelled(example):
    rep = evaluate(example, seed=0, n_boot=20, pooled=True)
    pooled = rep["pooled_all_scenarios"]
    assert "Not a headline number" in pooled["note"]
    assert pooled["binary"]["n"] == len(example)
    assert "pooled (all, not headline)" in to_markdown(rep)


def test_report_is_deterministic(example):
    a = evaluate(example, seed=3, n_boot=50)
    b = evaluate(example, seed=3, n_boot=50)
    assert json.dumps(a) == json.dumps(b)


def test_missing_scenario_and_single_class(example):
    part = example[example["scenario"] != "normal"].copy()
    part.loc[part["scenario"] == "baseline", "event"] = 0
    part.loc[part["scenario"] == "baseline", "next_state"] = "current"
    rep = evaluate(part, seed=0, n_boot=20)
    assert rep["scenarios"]["normal"] is None
    base = rep["scenarios"]["baseline"]["binary"]
    assert base["roc_auc"] is None
    assert base["roc_auc_null_reason"] == SINGLE_CLASS_REASON
    assert base["bootstrap_95"]["roc_auc"]["ci"] is None
    md = to_markdown(rep)
    assert "| normal | 0 |" in md


def test_cli_writes_json_and_markdown(tmp_path):
    preds, outs = generate(seed=7)
    preds.to_csv(tmp_path / "predictions.csv", index=False)
    outs.to_csv(tmp_path / "outcomes.csv", index=False)

    def run(name):
        cli.main(
            [
                "--predictions",
                str(tmp_path / "predictions.csv"),
                "--outcomes",
                str(tmp_path / "outcomes.csv"),
                "--out",
                str(tmp_path / "out" / name),
                "--n-boot",
                "20",
            ]
        )
        return (tmp_path / "out" / f"{name}.json").read_text()

    first = run("report")
    assert first == run("again")
    data = json.loads(first)
    assert len(data["metadata"]["inputs"]["predictions.csv"]["sha256"]) == 64
    assert (tmp_path / "out" / "report.md").read_text().startswith("# Scenario")


def test_shipped_example_matches_generator(tmp_path):
    here = Path(__file__).resolve().parents[1]
    preds, outs = generate(seed=7)
    preds.to_csv(tmp_path / "p.csv", index=False)
    outs.to_csv(tmp_path / "o.csv", index=False)
    assert (tmp_path / "p.csv").read_bytes() == (here / "examples" / "predictions.csv").read_bytes()
    assert (tmp_path / "o.csv").read_bytes() == (here / "examples" / "outcomes.csv").read_bytes()
