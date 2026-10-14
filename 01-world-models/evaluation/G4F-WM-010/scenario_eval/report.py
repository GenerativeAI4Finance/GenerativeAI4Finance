"""Build the per-scenario report and render it as JSON and Markdown."""

import json

import numpy as np
import pandas as pd

from . import metrics as m
from .contract import SCENARIOS, STATE_PREFIX, state_columns

DISCLAIMER = (
    "Results are computed on simulated trajectories. They say how well the "
    "predictor matches the simulator, not how it would perform on real "
    "borrowers. Real-world validity needs validation on real outcome data."
)

SINGLE_CLASS_REASON = "only one outcome class present in this scenario"

# Below these sizes the numbers are too noisy to read on their own, so the
# scenario gets a warning in both the JSON and the Markdown.
MIN_ROWS = 100
MIN_EVENTS = 10  # also used for non-events and for each next state

# Floats in the JSON are rounded to this many significant digits, so last-bit
# differences between maths libraries (np.log, for one) cannot change the file.
JSON_DIGITS = 10

ECE_INTERVAL_NOTE = (
    "ECE adds up absolute gaps, so sampling noise tends to push it up, and every bootstrap "
    "resample adds a second round of noise on top. The resampled values therefore sit above "
    "the point value, and for a well calibrated scenario the point value can fall below its "
    "own interval. That says the gap is within noise, not that the interval is wrong. The "
    "debiased reliability in the next table removes the noise term directly."
)

DECOMPOSITION_NOTE = (
    "Brier = reliability - resolution + uncertainty + within bin. Reliability is the squared "
    "calibration error. The debiased version subtracts each bin's binomial sampling variance "
    "(Kumar, Liang and Ma 2019) and is not part of the sum; a value near or below 0 means the "
    "remaining calibration gap is within sampling noise."
)


def _mce_bin_n(rows):
    """Row count of the bin that sets the MCE (the larger bin on a tie)."""
    return max((abs(r["observed_rate"] - r["mean_predicted"]), r["n"]) for r in rows if r["n"])[1]


def _binary_block(y, p, n_bins, n_boot, seed):
    auc = m.roc_auc(y, p)
    ap = m.average_precision(y, p)
    width = m.reliability_table(y, p, n_bins, "width")
    boot_fns = {
        "brier": m.brier,
        "log_loss": m.log_loss,
        "roc_auc": m.roc_auc,
        "pr_auc": m.average_precision,
        "ece_equal_width": lambda yy, pp: m.ece(yy, pp, n_bins, "width"),
    }
    return {
        "n": len(y),
        "events": int(y.sum()),
        "observed_rate": float(y.mean()),
        "mean_predicted": float(p.mean()),
        # positive means the model over-predicts on average
        "calibration_in_the_large": float(p.mean() - y.mean()),
        "brier": m.brier(y, p),
        "log_loss": m.log_loss(y, p),
        "roc_auc": auc,
        "roc_auc_null_reason": None if auc is not None else SINGLE_CLASS_REASON,
        "pr_auc": ap,
        "pr_auc_null_reason": None if ap is not None else SINGLE_CLASS_REASON,
        "ece_equal_width": m.ece(y, p, n_bins, "width"),
        "ece_equal_mass": m.ece(y, p, n_bins, "mass"),
        "mce_equal_width": m.mce(y, p, n_bins, "width"),
        "mce_equal_width_bin_n": _mce_bin_n(width),
        "mce_equal_mass": m.mce(y, p, n_bins, "mass"),
        "murphy": m.murphy_decomposition(y, p, n_bins),
        "reliability_debiased": m.reliability_debiased(y, p, n_bins),
        "reliability_equal_width": width,
        "reliability_equal_mass": m.reliability_table(y, p, n_bins, "mass"),
        "bootstrap_95": m.bootstrap(y, p, boot_fns, n_boot=n_boot, seed=seed),
    }


def _by_horizon(df, n_bins):
    rows = []
    for h, g in df.groupby("horizon", sort=True):
        y, p = g["event"].to_numpy(), g["p_event"].to_numpy()
        rows.append(
            {
                "horizon": int(h),
                "n": len(g),
                "events": int(y.sum()),
                "observed_rate": float(y.mean()),
                "mean_predicted": float(p.mean()),
                "brier": m.brier(y, p),
                "ece_equal_width": m.ece(y, p, n_bins, "width"),
            }
        )
    return rows


def _state_scores(labels, probs, classes):
    return {
        "brier": m.multiclass_brier(labels, probs, classes),
        "log_loss": m.multiclass_log_loss(labels, probs, classes),
        "accuracy": float(np.mean(np.asarray(classes)[probs.argmax(axis=1)] == labels)),
        "observed_share": {c: float(np.mean(labels == c)) for c in classes},
        "mean_predicted_share": {c: float(probs[:, i].mean()) for i, c in enumerate(classes)},
    }


def _one_vs_rest(state, y, p, n_bins):
    """Calibration of one next-state probability column against 1[next_state == state]."""
    width = m.reliability_table(y, p, n_bins, "width")
    return {
        "state": state,
        "n_observed": int(y.sum()),
        "observed_share": float(y.mean()),
        "mean_predicted": float(p.mean()),
        "brier": m.brier(y, p),
        "ece_equal_width": m.ece(y, p, n_bins, "width"),
        "mce_equal_width": m.mce(y, p, n_bins, "width"),
        "mce_equal_width_bin_n": _mce_bin_n(width),
        "reliability_equal_width": width,
    }


def _state_block(df, n_bins):
    cols = state_columns(df)
    if not cols:
        return None
    classes = [c[len(STATE_PREFIX) :] for c in cols]
    probs = df[cols].to_numpy(dtype=float)
    labels = df["next_state"].to_numpy()
    block = {"classes": classes, **_state_scores(labels, probs, classes)}
    block["per_class"] = [
        _one_vs_rest(c, (labels == c).astype(int), probs[:, i], n_bins)
        for i, c in enumerate(classes)
    ]
    block["by_from_state"] = None
    if "from_state" in df.columns:
        block["by_from_state"] = [
            {
                "from_state": str(s),
                "n": len(g),
                **_state_scores(g["next_state"].to_numpy(), g[cols].to_numpy(dtype=float), classes),
            }
            for s, g in df.groupby("from_state", sort=True)
        ]
    return block


def _warnings(binary, state):
    out = []
    n, events = binary["n"], binary["events"]
    if n < MIN_ROWS:
        out.append(f"n = {n} is below the minimum of {MIN_ROWS} rows: every metric is unstable")
    for label, count in (("events", events), ("non-events", n - events)):
        if count < MIN_EVENTS:
            out.append(
                f"{label} = {count} is below the minimum of {MIN_EVENTS}: "
                "ROC AUC, PR AUC and the calibration metrics are unstable"
            )
    flat = [k for k, v in binary["bootstrap_95"].items() if v["ci_null_reason"] == m.ZERO_WIDTH]
    if flat:
        out.append(
            f"bootstrap intervals for {', '.join(flat)} have zero width, so they are null "
            "in the JSON and not shown"
        )
    for c in state["per_class"] if state else []:
        if c["n_observed"] < MIN_EVENTS:
            out.append(
                f"next state '{c['state']}' has {c['n_observed']} observations, below the "
                f"minimum of {MIN_EVENTS}: its one-vs-rest calibration is unstable"
            )
    return out


def _evaluate_slice(df, n_bins, n_boot, seed):
    y = df["event"].to_numpy()
    p = df["p_event"].to_numpy()
    binary = _binary_block(y, p, n_bins, n_boot, seed)
    state = _state_block(df, n_bins)
    return {
        "warnings": _warnings(binary, state),
        "binary": binary,
        "by_horizon": _by_horizon(df, n_bins),
        "state_transition": state,
    }


def evaluate(
    df: pd.DataFrame,
    *,
    seed: int = 0,
    n_boot: int = 500,
    n_bins: int = 10,
    pooled: bool = False,
    inputs: dict | None = None,
) -> dict:
    seed = m.check_int("seed", seed, 0)
    n_boot = m.check_int("n_boot", n_boot, 1)
    n_bins = m.check_n_bins(n_bins)
    scenarios = {}
    for i, name in enumerate(SCENARIOS):
        part = df[df["scenario"] == name]
        if len(part) == 0:
            scenarios[name] = None
            continue
        # separate but fixed bootstrap stream per scenario
        scenarios[name] = _evaluate_slice(part, n_bins, n_boot, seed + i)

    report = {
        "metadata": {
            "task": "G4F-WM-010",
            "seed": seed,
            "n_bootstrap": n_boot,
            "n_bins": n_bins,
            "log_loss_clip": m.LOG_LOSS_EPS,
            "small_sample_minimums": {"rows": MIN_ROWS, "events": MIN_EVENTS},
            "inputs": inputs or {},
            "n_per_scenario": {s: int((df["scenario"] == s).sum()) for s in SCENARIOS},
            "numpy_version": np.__version__,
        },
        "disclaimer": DISCLAIMER,
        "scenarios": scenarios,
    }
    if pooled:
        report["pooled_all_scenarios"] = {
            "note": "Pooled over baseline, normal and stress. Not a headline number: "
            "it mixes regimes and can hide stress miscalibration.",
            **_evaluate_slice(df, n_bins, n_boot, seed + len(SCENARIOS)),
        }
    return report


def _round(x):
    if isinstance(x, float):
        return float(f"{x:.{JSON_DIGITS}g}")
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v) for v in x]
    return x


def to_json(report: dict) -> str:
    """The report as JSON text, floats rounded to JSON_DIGITS significant digits."""
    return json.dumps(_round(report), indent=2, allow_nan=False) + "\n"


def _fmt(x, digits=4):
    return "n/a" if x is None else f"{x:.{digits}f}"


def _fmt_ci(block, name):
    # zero-width intervals are already None in the report, see metrics.bootstrap
    ci = block["bootstrap_95"][name]["ci"]
    return "" if ci is None else f" [{ci[0]:.4f}, {ci[1]:.4f}]"


def _fmt_mce(block):
    return f"{_fmt(block['mce_equal_width'])} (n={block['mce_equal_width_bin_n']})"


def _fmt_bin(row, n_bins):
    digits = 1 if 10 % n_bins == 0 else 2 if 100 % n_bins == 0 else 3
    return f"{row['lower']:.{digits}f}-{row['upper']:.{digits}f}"


def _label(name, res):
    return f"{name} (see warnings)" if res["warnings"] else name


def to_markdown(report: dict) -> str:
    md = ["# Scenario prediction and calibration report (G4F-WM-010)", ""]
    meta = report["metadata"]
    mins = meta["small_sample_minimums"]
    md.append(
        f"Seed {meta['seed']}, {meta['n_bootstrap']} bootstrap resamples, "
        f"{meta['n_bins']} bins. 95% percentile intervals in brackets."
    )
    for name, info in meta["inputs"].items():
        md.append(f"- `{name}` sha256 `{info['sha256']}`")
    md += ["", f"> {report['disclaimer']}", ""]

    slices = list(report["scenarios"].items())
    if "pooled_all_scenarios" in report:
        slices.append(("pooled (all, not headline)", report["pooled_all_scenarios"]))
    present = [(name, res) for name, res in slices if res is not None]

    md += ["## Warnings", ""]
    warned = [(name, res["warnings"]) for name, res in present if res["warnings"]]
    for name, warnings in warned:
        md += [f"- {name}: {w}" for w in warnings]
    if not warned:
        md.append(
            f"None. No scenario is below {mins['rows']} rows, {mins['events']} events, "
            f"{mins['events']} non-events or {mins['events']} observations of any next state."
        )

    md += ["", "## Binary event, per scenario", ""]
    md.append(
        "| scenario | n | events | observed | mean pred | Brier | log loss | ROC AUC | PR AUC |"
    )
    md.append("|---|---|---|---|---|---|---|---|---|")
    for name, res in slices:
        if res is None:
            md.append(f"| {name} | 0 | | | | | | | |")
            continue
        b = res["binary"]
        md.append(
            f"| {_label(name, res)} | {b['n']} | {b['events']} | {_fmt(b['observed_rate'])} "
            f"| {_fmt(b['mean_predicted'])} | {_fmt(b['brier'])}{_fmt_ci(b, 'brier')} "
            f"| {_fmt(b['log_loss'])} | {_fmt(b['roc_auc'])}{_fmt_ci(b, 'roc_auc')} "
            f"| {_fmt(b['pr_auc'])} |"
        )

    md += ["", "## Calibration, per scenario", ""]
    md.append(
        "Mean pred minus observed is calibration in the large (negative means the model "
        "under-predicts). The bin count next to MCE width is the size of the bin that sets it."
    )
    md += ["", "| scenario | mean pred - observed | ECE width | ECE mass | MCE width | MCE mass |"]
    md.append("|---|---|---|---|---|---|")
    below = []
    for name, res in present:
        b = res["binary"]
        ci = b["bootstrap_95"]["ece_equal_width"]["ci"]
        if ci is not None and not ci[0] <= b["ece_equal_width"] <= ci[1]:
            below.append(name)
        md.append(
            f"| {_label(name, res)} | {_fmt(b['calibration_in_the_large'])} "
            f"| {_fmt(b['ece_equal_width'])}{_fmt_ci(b, 'ece_equal_width')} "
            f"| {_fmt(b['ece_equal_mass'])} | {_fmt_mce(b)} | {_fmt(b['mce_equal_mass'])} |"
        )
    note = ECE_INTERVAL_NOTE
    if below:
        note += f" Here the point value is outside its interval for: {', '.join(below)}."
    md += ["", note]

    md += ["", "## Brier decomposition (equal-width bins)", ""]
    md.append(
        "| scenario | Brier | reliability | reliability debiased | resolution "
        "| uncertainty | within bin |"
    )
    md.append("|---|---|---|---|---|---|---|")
    for name, res in present:
        d = res["binary"]["murphy"]
        md.append(
            f"| {_label(name, res)} | {_fmt(d['brier'])} | {_fmt(d['reliability'])} "
            f"| {_fmt(res['binary']['reliability_debiased'])} | {_fmt(d['resolution'])} "
            f"| {_fmt(d['uncertainty'])} | {_fmt(d['within_bin'])} |"
        )
    md += ["", DECOMPOSITION_NOTE]

    md += ["", "## Binary event by horizon", ""]
    md.append("| scenario | horizon | n | events | observed | mean pred | Brier | ECE width |")
    md.append("|---|---|---|---|---|---|---|---|")
    for name, res in present:
        for h in res["by_horizon"]:
            md.append(
                f"| {name} | {h['horizon']} | {h['n']} | {h['events']} "
                f"| {_fmt(h['observed_rate'])} | {_fmt(h['mean_predicted'])} "
                f"| {_fmt(h['brier'])} | {_fmt(h['ece_equal_width'])} |"
            )

    state_rows = [(name, res["state_transition"]) for name, res in present]
    state_rows = [(name, st) for name, st in state_rows if st]
    if state_rows:
        md += ["", "## Next-state transition, per scenario", ""]
        md.append("| scenario | multi-class Brier | log loss | accuracy |")
        md.append("|---|---|---|---|")
        for name, st in state_rows:
            md.append(
                f"| {name} | {_fmt(st['brier'])} | {_fmt(st['log_loss'])} "
                f"| {_fmt(st['accuracy'])} |"
            )

        md += ["", "## Next-state calibration by class (one-vs-rest)", ""]
        md.append(
            "| scenario | next state | observed n | observed share | mean pred | Brier "
            "| ECE width | MCE width |"
        )
        md.append("|---|---|---|---|---|---|---|---|")
        for name, st in state_rows:
            for c in st["per_class"]:
                md.append(
                    f"| {name} | {c['state']} | {c['n_observed']} "
                    f"| {_fmt(c['observed_share'])} | {_fmt(c['mean_predicted'])} "
                    f"| {_fmt(c['brier'])} | {_fmt(c['ece_equal_width'])} | {_fmt_mce(c)} |"
                )

        from_rows = [(name, st["by_from_state"]) for name, st in state_rows if st["by_from_state"]]
        if from_rows:
            md += ["", "## Next-state transition by from-state", ""]
            md.append("| scenario | from state | n | multi-class Brier | log loss | accuracy |")
            md.append("|---|---|---|---|---|---|")
            for name, rows in from_rows:
                for r in rows:
                    md.append(
                        f"| {name} | {r['from_state']} | {r['n']} | {_fmt(r['brier'])} "
                        f"| {_fmt(r['log_loss'])} | {_fmt(r['accuracy'])} |"
                    )

    for name, res in report["scenarios"].items():
        if res is None:
            continue
        md += ["", f"## Reliability, {name} (equal-width bins)", ""]
        md.append("| bin | n | mean predicted | observed |")
        md.append("|---|---|---|---|")
        for r in res["binary"]["reliability_equal_width"]:
            md.append(
                f"| {_fmt_bin(r, meta['n_bins'])} | {r['n']} "
                f"| {_fmt(r['mean_predicted'])} | {_fmt(r['observed_rate'])} |"
            )
    return "\n".join(md) + "\n"
