"""Small fictional borrower panel used by the tests and the example.

This is not a realistic credit model. Each entity has a latent stress
random walk; the observed features are noisy views of it and the target
is whether stress crosses a threshold in the next `horizon_months`.
"""

import numpy as np
import pandas as pd

from panel import PanelSpec

FEATURES = ["utilisation", "days_past_due", "income_ratio"]


def make_panel(
    n_entities: int = 60,
    n_periods: int = 36,
    horizon_months: int = 3,
    seed: int = 0,
) -> tuple[pd.DataFrame, PanelSpec]:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2021-01-01", periods=n_periods, freq="MS")
    # Extra periods at the end so every row has a full outcome window.
    total = n_periods + horizon_months

    rows = []
    for i in range(n_entities):
        stress = np.cumsum(rng.normal(0, 0.35, total)) + rng.normal(0, 0.5)
        event = stress > 1.5
        for t in range(n_periods):
            s = stress[t]
            defaulted = bool(event[t + 1 : t + 1 + horizon_months].any())
            # Bureau data lands with a lag of a few days.
            lag = pd.Timedelta(days=int(rng.integers(1, 10)))
            util = np.clip(0.4 + 0.15 * s + rng.normal(0, 0.15), 0, 1.5)
            recovery = rng.uniform(0, 5000) if defaulted else 0.0
            rows.append(
                {
                    "entity_id": f"E{i:03d}",
                    "timestamp": dates[t],
                    "utilisation": float(util),
                    "days_past_due": float(max(0.0, 15 * s + rng.normal(0, 20))),
                    "income_ratio": float(1.0 - 0.1 * s + rng.normal(0, 0.2)),
                    "dpd_observed_at": dates[t] - lag,
                    "default_in_horizon": int(defaulted),
                    "recovery_amount": float(recovery),
                }
            )
    df = pd.DataFrame(rows)
    spec = PanelSpec(
        feature_cols=list(FEATURES),
        target_col="default_in_horizon",
        horizon=pd.DateOffset(months=horizon_months),
        post_outcome_cols=["recovery_amount"],
        observed_at={"days_past_due": "dpd_observed_at"},
    )
    return df, spec
