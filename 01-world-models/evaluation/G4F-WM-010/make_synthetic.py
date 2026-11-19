"""Write a small seeded synthetic example in the input contract format.

Every number here is made up. Outcomes at each horizon are sampled
independently, not as path-coherent absorbing trajectories. The stress scenario
raises the true default
rate but the "predictor" does not see the shift, so it under-predicts there.
That is the failure the report is meant to surface.

    python make_synthetic.py --seed 7 --entities-per-scenario 25 --out examples
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

AS_OF = ["2025-01-31", "2025-07-31"]
HORIZONS = [6, 12]
# (entities, true logit shift, shift the predictor assumes)
SCENARIOS = {
    "baseline": (300, 0.0, 0.0),
    "normal": (300, 0.3, 0.2),
    "stress": (200, 1.3, 0.2),
}


def sigmoid(z: float) -> float:
    return 1 / (1 + np.exp(-z))


def state_probs(x: float, horizon: int, shift: float) -> tuple[float, float, float]:
    """Probabilities of (current, delinquent, default) at the horizon."""
    p_default = sigmoid(-3.2 + 0.9 * x + 0.05 * horizon + shift)
    p_delinquent = (1 - p_default) * sigmoid(-2.0 + 0.6 * x + 0.5 * shift)
    return 1 - p_default - p_delinquent, p_delinquent, p_default


def generate(
    seed: int = 7, *, entities_per_scenario: int | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate the default panel, or an explicitly sized panel for each scenario."""
    if entities_per_scenario is not None and (
        isinstance(entities_per_scenario, bool)
        or not isinstance(entities_per_scenario, int)
        or entities_per_scenario < 1
    ):
        raise ValueError("entities_per_scenario must be a positive integer")
    rng = np.random.default_rng(seed)
    preds, outs = [], []
    for scenario, (n_entities, true_shift, model_shift) in SCENARIOS.items():
        if entities_per_scenario is not None:
            n_entities = entities_per_scenario
        for e in range(n_entities):
            entity = f"SYN-{e:04d}"
            for as_of in AS_OF:
                for h in HORIZONS:
                    x = rng.normal()
                    true = state_probs(x, h, true_shift)
                    # the predictor sees a noisy version of the risk score
                    x_hat = x + rng.normal(scale=0.3)
                    _, p_del, p_def = state_probs(x_hat, h, model_shift)
                    p_del, p_def = round(float(p_del), 6), round(float(p_def), 6)
                    state = rng.choice(["current", "delinquent", "default"], p=true)
                    key = {"entity_id": entity, "as_of": as_of, "horizon": h, "scenario": scenario}
                    preds.append(
                        {
                            **key,
                            "p_event": p_def,
                            "p_state_current": round(1 - p_del - p_def, 6),
                            "p_state_delinquent": p_del,
                            "p_state_default": p_def,
                        }
                    )
                    outs.append({**key, "event": int(state == "default"), "next_state": state})
    return pd.DataFrame(preds), pd.DataFrame(outs)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument(
        "--entities-per-scenario", type=int, help="override the default 300/300/200 entities"
    )
    ap.add_argument("--out", default="examples")
    args = ap.parse_args(argv)
    if args.entities_per_scenario is not None and args.entities_per_scenario < 1:
        ap.error("--entities-per-scenario must be a positive integer")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    preds, outs = generate(args.seed, entities_per_scenario=args.entities_per_scenario)
    # LF on every platform, so the files and their sha256 are the same everywhere
    preds.to_csv(out / "predictions.csv", index=False, lineterminator="\n")
    outs.to_csv(out / "outcomes.csv", index=False, lineterminator="\n")
    print(f"wrote {len(preds)} rows to {out}")


if __name__ == "__main__":
    main()
