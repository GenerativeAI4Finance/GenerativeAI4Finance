import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import evaluate as cli
from make_synthetic import generate
from scenario_eval import metrics as m
from scenario_eval.contract import ContractError, join
from scenario_eval.report import DISCLAIMER, SINGLE_CLASS_REASON, evaluate, to_json, to_markdown


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
    for name, frame in (("predictions", preds), ("outcomes", outs)):
        frame.to_csv(tmp_path / f"{name}.csv", index=False, lineterminator="\n")
        shipped = (here / "examples" / f"{name}.csv").read_bytes()
        shipped = shipped.replace(b"\r\n", b"\n")
        assert (tmp_path / f"{name}.csv").read_bytes() == shipped


def test_cli_regenerates_committed_example_reports_byte_for_byte(tmp_path):
    here = Path(__file__).resolve().parents[1]
    preds, outs = generate(seed=7)
    for name, frame in (("predictions", preds), ("outcomes", outs)):
        frame.to_csv(tmp_path / f"{name}.csv", index=False, lineterminator="\n")
    output = tmp_path / "example_report"
    cli.main(
        [
            "--predictions",
            str(tmp_path / "predictions.csv"),
            "--outcomes",
            str(tmp_path / "outcomes.csv"),
            "--out",
            str(output),
        ]
    )
    for suffix in (".json", ".md"):
        generated = output.with_suffix(suffix).read_bytes()
        expected = (here / "reports" / f"example_report{suffix}").read_bytes()
        assert generated.endswith(b"\n") and b"\r" not in generated
        assert generated == expected.replace(b"\r\n", b"\n")


def test_cli_preserves_hashes_for_matching_input_basenames(tmp_path):
    preds, outs = generate(seed=7)
    pred_path = tmp_path / "predictions" / "data.csv"
    out_path = tmp_path / "outcomes" / "data.csv"
    pred_path.parent.mkdir()
    out_path.parent.mkdir()
    preds.to_csv(pred_path, index=False)
    outs.to_csv(out_path, index=False)
    report_path = tmp_path / "report"
    cli.main(
        [
            "--predictions",
            str(pred_path),
            "--outcomes",
            str(out_path),
            "--out",
            str(report_path),
            "--n-boot",
            "1",
        ]
    )
    inputs = json.loads(report_path.with_suffix(".json").read_text())["metadata"]["inputs"]
    assert inputs == {
        "predictions:data.csv": {"sha256": cli.sha256(pred_path)},
        "outcomes:data.csv": {"sha256": cli.sha256(out_path)},
    }
    assert inputs["predictions:data.csv"]["sha256"] != inputs["outcomes:data.csv"]["sha256"]
    markdown = report_path.with_suffix(".md").read_text()
    for name, info in inputs.items():
        assert f"`{name}` sha256 `{info['sha256']}`" in markdown


def test_cli_hashes_the_bytes_it_scores_when_inputs_are_replaced(tmp_path, monkeypatch):
    key = {"entity_id": ["a", "b"], "as_of": "2025-01-31", "horizon": 6, "scenario": "baseline"}
    preds = pd.DataFrame({**key, "p_event": [0.2, 0.8]})
    outs = pd.DataFrame({**key, "event": [0, 1]})
    pred_path, out_path = tmp_path / "p.csv", tmp_path / "o.csv"
    preds.to_csv(pred_path, index=False)
    outs.to_csv(out_path, index=False)
    original_hashes = {p.name: {"sha256": cli.sha256(p)} for p in (pred_path, out_path)}
    original_load = cli.load

    def replace_after_loading(*args):
        df = original_load(*args)
        preds.assign(p_event=[0.9, 0.1]).to_csv(pred_path, index=False)
        outs.assign(event=[1, 0]).to_csv(out_path, index=False)
        return df

    monkeypatch.setattr(cli, "load", replace_after_loading)
    output = tmp_path / "report"
    cli.main(
        [
            "--predictions",
            str(pred_path),
            "--outcomes",
            str(out_path),
            "--out",
            str(output),
            "--n-boot",
            "1",
        ]
    )
    report = json.loads(output.with_suffix(".json").read_text())
    assert report["metadata"]["inputs"] == original_hashes
    assert report["scenarios"]["baseline"]["binary"]["brier"] == pytest.approx(0.04)
    assert all(original_hashes[p.name]["sha256"] != cli.sha256(p) for p in (pred_path, out_path))


@pytest.mark.parametrize(
    "suffix", [".gz", ".bz2", ".xz", ".zip", ".tar", ".tar.gz", ".tar.bz2", ".tar.xz"]
)
def test_cli_compressed_inputs_preserve_inference_and_one_raw_snapshot(
    tmp_path, monkeypatch, suffix
):
    key = {"entity_id": ["a", "b"], "as_of": "2025-01-31", "horizon": 6, "scenario": "baseline"}
    preds = pd.DataFrame({**key, "p_event": [0.2, 0.8]})
    outs = pd.DataFrame({**key, "event": [0, 1]})
    paths = [tmp_path / f"{name}.csv{suffix}" for name in ("predictions", "outcomes")]
    for path, frame in zip(paths, (preds, outs)):
        frame.to_csv(path, index=False, lineterminator="\n", compression="infer")
    snapshots = {path: path.read_bytes() for path in paths}
    expected_inputs = {
        path.name: {"sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()}
        for path, raw in snapshots.items()
    }
    reads = dict.fromkeys(paths, 0)
    original_read_bytes = Path.read_bytes

    def replace_after_read(path):
        if path in reads:
            reads[path] += 1
            raw = original_read_bytes(path)
            path.write_bytes(b"producer replaced this input after its snapshot")
            return raw
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", replace_after_read)
    output = tmp_path / "report"
    cli.main(
        [
            "--predictions",
            str(paths[0]),
            "--outcomes",
            str(paths[1]),
            "--out",
            str(output),
            "--n-boot",
            "1",
        ]
    )
    report = json.loads(output.with_suffix(".json").read_text())
    assert report["metadata"]["inputs"] == expected_inputs
    assert report["scenarios"]["baseline"]["binary"]["brier"] == pytest.approx(0.04)
    assert (output.with_suffix(".md")).read_text().startswith("# Scenario")
    assert reads == dict.fromkeys(paths, 1)


def test_cli_preserves_six_bin_boundary_calibration(tmp_path):
    key = {"entity_id": ["a", "b"], "as_of": "2025-01-31", "horizon": 6, "scenario": "baseline"}
    preds = pd.DataFrame({**key, "p_event": [1 / 6, 0.1]})
    outs = pd.DataFrame({**key, "event": [1, 0]})
    pred_path, out_path = tmp_path / "p.csv", tmp_path / "o.csv"
    preds.to_csv(pred_path, index=False)
    outs.to_csv(out_path, index=False)
    output = tmp_path / "report"
    cli.main(
        [
            "--predictions",
            str(pred_path),
            "--outcomes",
            str(out_path),
            "--out",
            str(output),
            "--n-bins",
            "6",
            "--n-boot",
            "1",
        ]
    )
    binary = json.loads(output.with_suffix(".json").read_text())["scenarios"]["baseline"]["binary"]
    assert binary["ece_equal_width"] == pytest.approx(7 / 15)
    assert [r["n"] for r in binary["reliability_equal_width"]] == [1, 1, 0, 0, 0, 0]


@pytest.mark.parametrize("which,column", [("predictions", "p_event"), ("outcomes", "event")])
def test_cli_rejects_duplicate_csv_headers_without_writing(tmp_path, which, column):
    key = {"entity_id": ["a"], "as_of": "2025-01-31", "horizon": 6, "scenario": "baseline"}
    preds = pd.DataFrame({**key, "p_event": [0.2]})
    outs = pd.DataFrame({**key, "event": [0]})
    frame = preds if which == "predictions" else outs
    frame.insert(len(frame.columns), column, "conflicting", allow_duplicates=True)
    pred_path, out_path = tmp_path / "p.csv", tmp_path / "o.csv"
    preds.to_csv(pred_path, index=False)
    outs.to_csv(out_path, index=False)
    output = tmp_path / "result" / "report"
    with pytest.raises(ContractError, match="duplicate CSV"):
        cli.main(
            ["--predictions", str(pred_path), "--outcomes", str(out_path), "--out", str(output)]
        )
    assert not output.parent.exists()


def state_frame(n=240, seed=5, with_from=True):
    rng = np.random.default_rng(seed)
    states = ["current", "late", "default"]
    probs = rng.dirichlet([6, 2, 1], size=n)
    nxt = np.array([states[rng.choice(3, p=row)] for row in probs])
    even = np.arange(n) % 2 == 0
    preds = pd.DataFrame(
        {
            "entity_id": [f"e{i}" for i in range(n)],
            "as_of": "2025-01-31",
            "horizon": np.where(even, 6, 12),
            "scenario": np.where(even, "baseline", "stress"),
            "p_event": probs[:, 2],
            **{f"p_state_{s}": probs[:, i] for i, s in enumerate(states)},
        }
    )
    if with_from:
        preds["from_state"] = np.where(np.arange(n) % 3 == 0, "late", "current")
    outs = preds[["entity_id", "as_of", "horizon", "scenario"]].assign(
        event=(nxt == "default").astype(int), next_state=nxt
    )
    return join(preds, outs)


@pytest.fixture(scope="module")
def state_report():
    return evaluate(state_frame(), seed=0, n_boot=30)


def test_disclaimer_in_both_outputs(report):
    assert report["disclaimer"] == DISCLAIMER
    assert "not how it would perform on real borrowers" in DISCLAIMER
    assert DISCLAIMER in to_markdown(report)


def test_state_block_scores(state_report):
    st = state_report["scenarios"]["baseline"]["state_transition"]
    assert st["classes"] == ["current", "late", "default"]
    assert 0 <= st["brier"] <= 2
    assert st["log_loss"] > 0
    assert sum(st["observed_share"].values()) == pytest.approx(1)
    assert sum(st["mean_predicted_share"].values()) == pytest.approx(1)


def test_per_class_calibration_matches_one_vs_rest(state_report):
    df = state_frame()
    part = df[df["scenario"] == "baseline"]
    st = state_report["scenarios"]["baseline"]["state_transition"]
    assert [c["state"] for c in st["per_class"]] == ["current", "late", "default"]
    for c in st["per_class"]:
        y = (part["next_state"] == c["state"]).astype(int).to_numpy()
        p = part[f"p_state_{c['state']}"].to_numpy()
        assert c["n_observed"] == y.sum()
        assert c["brier"] == pytest.approx(m.brier(y, p), rel=1e-9)
        assert c["ece_equal_width"] == pytest.approx(m.ece(y, p), rel=1e-9)
        assert sum(r["n"] for r in c["reliability_equal_width"]) == len(part)


def test_from_state_breakdown(state_report):
    st = state_report["scenarios"]["stress"]["state_transition"]
    rows = {r["from_state"]: r for r in st["by_from_state"]}
    assert set(rows) == {"current", "late"}
    n_stress = state_report["metadata"]["n_per_scenario"]["stress"]
    assert sum(r["n"] for r in rows.values()) == n_stress
    assert "Next-state transition by from-state" in to_markdown(state_report)


def test_no_from_state_gives_no_breakdown():
    rep = evaluate(state_frame(with_from=False), seed=0, n_boot=10)
    assert rep["scenarios"]["baseline"]["state_transition"]["by_from_state"] is None
    assert "by from-state" not in to_markdown(rep)


def test_binary_only_input_has_no_state_block(example):
    binary = example[["entity_id", "as_of", "horizon", "scenario", "p_event", "event"]]
    rep = evaluate(binary, seed=0, n_boot=10)
    assert rep["scenarios"]["baseline"]["state_transition"] is None
    assert "Next-state" not in to_markdown(rep)


def test_by_horizon_rows(state_report):
    rows = state_report["scenarios"]["baseline"]["by_horizon"]
    assert [r["horizon"] for r in rows] == [6]
    assert rows[0]["n"] == state_report["metadata"]["n_per_scenario"]["baseline"]
    assert "## Binary event by horizon" in to_markdown(state_report)


def test_by_horizon_splits_a_mixed_scenario(example):
    mixed = example.copy()
    mixed.loc[mixed.index[::2], "horizon"] = 6
    rep = evaluate(mixed, seed=0, n_boot=10)
    for res in rep["scenarios"].values():
        assert [r["horizon"] for r in res["by_horizon"]] == [6, 12]
        assert sum(r["n"] for r in res["by_horizon"]) == res["binary"]["n"]


def test_small_sample_warnings_in_json_and_markdown(example):
    small = example[example["scenario"] == "baseline"].head(30).copy()
    small["event"] = 0
    small.loc[small.index[:2], "event"] = 1
    rep = evaluate(small, seed=0, n_boot=20)
    warnings = rep["scenarios"]["baseline"]["warnings"]
    assert any("below the minimum of 100 rows" in w for w in warnings)
    assert any("events = 2" in w for w in warnings)
    md = to_markdown(rep)
    assert "## Warnings" in md
    assert "below the minimum of 100 rows" in md


def test_no_warnings_for_the_shipped_example(report):
    assert all(res["warnings"] == [] for res in report["scenarios"].values())


def test_small_next_state_class_warning():
    df = state_frame()
    df.loc[df["scenario"] == "baseline", "next_state"] = "current"
    df["event"] = (df["next_state"] == "default").astype(int)
    rep = evaluate(df, seed=0, n_boot=10)
    assert any("next state 'late'" in w for w in rep["scenarios"]["baseline"]["warnings"])


def test_json_is_strict_and_rounded(report):
    text = to_json(report)
    assert "NaN" not in text and "Infinity" not in text
    json.loads(text)
    assert text.endswith("\n") and "\r" not in text


@pytest.mark.parametrize("bad", ["0", "-5", "101", "2.5", "abc", "True", ""])
def test_cli_rejects_bad_n_bins_without_writing(tmp_path, capsys, bad):
    preds, outs = generate(seed=7)
    preds.to_csv(tmp_path / "p.csv", index=False)
    outs.to_csv(tmp_path / "o.csv", index=False)
    args = ["--predictions", str(tmp_path / "p.csv"), "--outcomes", str(tmp_path / "o.csv")]
    with pytest.raises(SystemExit) as exc:
        cli.main([*args, "--out", str(tmp_path / "out" / "r"), "--n-bins", bad])
    assert exc.value.code == 2
    assert "n-bins" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("bad", [True, False, -1, 0, 101, 2.5, 10.0, "10", None])
def test_library_rejects_bad_n_bins(example, bad):
    with pytest.raises((TypeError, ValueError)):
        evaluate(example, n_bins=bad, n_boot=5)


def test_cli_rejects_invalid_input_without_writing(tmp_path):
    preds, outs = generate(seed=7)
    preds.loc[0, "as_of"] = "2025-02-30"
    preds.to_csv(tmp_path / "p.csv", index=False)
    outs.to_csv(tmp_path / "o.csv", index=False)
    argv = [
        "--predictions",
        str(tmp_path / "p.csv"),
        "--outcomes",
        str(tmp_path / "o.csv"),
        "--out",
        str(tmp_path / "out" / "r"),
    ]
    with pytest.raises(ContractError, match="as_of"):
        cli.main(argv)
    assert not (tmp_path / "out").exists()
