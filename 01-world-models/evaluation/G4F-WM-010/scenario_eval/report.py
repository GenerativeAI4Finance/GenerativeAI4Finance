"""Build the per-scenario report and render it as JSON-ready dict and Markdown."""

import numpy as np

from . import metrics as m
from .contract import SCENARIOS, STATE_PREFIX, state_columns

DISCLAIMER = (
    "Results are computed on simulated trajectories. They say how well the "
    "predictor matches the simulator, not how it would perform on real "
    "borrowers. Real-world validity needs validation on real outcome data."
)

SINGLE_CLASS_REASON = "only one outcome class present in this scenario"


def _binary_block(y, p, n_bins, n_boot, seed):
    auc = m.roc_auc(y, p)
    ap = m.average_precision(y, p)
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
        "murphy": m.murphy_decomposition(y, p, n_bins),
        "reliability_equal_width": m.reliability_table(y, p, n_bins, "width"),
        "reliability_equal_mass": m.reliability_table(y, p, n_bins, "mass"),
        "bootstrap_95": m.bootstrap(y, p, boot_fns, n_boot=n_boot, seed=seed),
    }


def _by_horizon(df):
    rows = []
    for h, g in df.groupby("horizon", sort=True):
        y, p = g["event"].to_numpy(), g["p_event"].to_numpy()
        rows.append(
            {
                "horizon": int(h),
                "n": len(g),
                "observed_rate": float(y.mean()),
                "mean_predicted": float(p.mean()),
                "brier": m.brier(y, p),
            }
        )
    return rows


def _state_block(df):
    cols = state_columns(df)
    if not cols:
        return None
    classes = [c[len(STATE_PREFIX) :] for c in cols]
    probs = df[cols].to_numpy(dtype=float)
    labels = df["next_state"].to_numpy()
    observed = {c: float(np.mean(labels == c)) for c in classes}
    predicted = {c: float(probs[:, i].mean()) for i, c in enumerate(classes)}
    return {
        "classes": classes,
        "brier": m.multiclass_brier(labels, probs, classes),
        "log_loss": m.multiclass_log_loss(labels, probs, classes),
        "accuracy": float(np.mean(np.asarray(classes)[probs.argmax(axis=1)] == labels)),
        "observed_share": observed,
        "mean_predicted_share": predicted,
    }


def _evaluate_slice(df, n_bins, n_boot, seed):
    y = df["event"].to_numpy()
    p = df["p_event"].to_numpy()
    return {
        "binary": _binary_block(y, p, n_bins, n_boot, seed),
        "by_horizon": _by_horizon(df),
        "state_transition": _state_block(df),
    }


def evaluate(df, *, seed=0, n_boot=500, n_bins=10, pooled=False, inputs=None):
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


def _fmt(x, digits=4):
    return "n/a" if x is None else f"{x:.{digits}f}"


def _fmt_ci(block, name):
    ci = block["bootstrap_95"][name]["ci"]
    return "" if ci is None else f" [{ci[0]:.4f}, {ci[1]:.4f}]"


def to_markdown(report):
    md = ["# Scenario prediction and calibration report (G4F-WM-010)", ""]
    meta = report["metadata"]
    md.append(
        f"Seed {meta['seed']}, {meta['n_bootstrap']} bootstrap resamples, "
        f"{meta['n_bins']} bins. 95% percentile intervals in brackets."
    )
    for name, info in meta["inputs"].items():
        md.append(f"- `{name}` sha256 `{info['sha256']}`")
    md += ["", f"> {report['disclaimer']}", "", "## Binary event, per scenario", ""]

    md.append(
        "| scenario | n | events | observed | mean pred | Brier | log loss "
        "| ROC AUC | PR AUC | ECE width | ECE mass |"
    )
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    slices = [(s, r) for s, r in report["scenarios"].items()]
    if "pooled_all_scenarios" in report:
        slices.append(("pooled (all, not headline)", report["pooled_all_scenarios"]))
    for name, res in slices:
        if res is None:
            md.append(f"| {name} | 0 | | | | | | | | | |")
            continue
        b = res["binary"]
        md.append(
            f"| {name} | {b['n']} | {b['events']} | {_fmt(b['observed_rate'])} "
            f"| {_fmt(b['mean_predicted'])} | {_fmt(b['brier'])}{_fmt_ci(b, 'brier')} "
            f"| {_fmt(b['log_loss'])} | {_fmt(b['roc_auc'])}{_fmt_ci(b, 'roc_auc')} "
            f"| {_fmt(b['pr_auc'])} | {_fmt(b['ece_equal_width'])}"
            f"{_fmt_ci(b, 'ece_equal_width')} | {_fmt(b['ece_equal_mass'])} |"
        )

    md += ["", "## Brier decomposition", ""]
    md.append("| scenario | Brier | reliability | resolution | uncertainty | within bin |")
    md.append("|---|---|---|---|---|---|")
    for name, res in slices:
        if res is None:
            continue
        d = res["binary"]["murphy"]
        md.append(
            f"| {name} | {_fmt(d['brier'])} | {_fmt(d['reliability'])} "
            f"| {_fmt(d['resolution'])} | {_fmt(d['uncertainty'])} | {_fmt(d['within_bin'])} |"
        )

    state_rows = [(n, r["state_transition"]) for n, r in slices if r and r["state_transition"]]
    if state_rows:
        md += ["", "## Next-state transition, per scenario", ""]
        md.append("| scenario | multi-class Brier | log loss | accuracy |")
        md.append("|---|---|---|---|")
        for name, st in state_rows:
            md.append(
                f"| {name} | {_fmt(st['brier'])} | {_fmt(st['log_loss'])} "
                f"| {_fmt(st['accuracy'])} |"
            )

    for name, res in report["scenarios"].items():
        if res is None:
            continue
        md += ["", f"## Reliability, {name} (equal-width bins)", ""]
        md.append("| bin | n | mean predicted | observed |")
        md.append("|---|---|---|---|")
        for r in res["binary"]["reliability_equal_width"]:
            md.append(
                f"| {r['lower']:.1f}-{r['upper']:.1f} | {r['n']} "
                f"| {_fmt(r['mean_predicted'])} | {_fmt(r['observed_rate'])} |"
            )
    return "\n".join(md) + "\n"
