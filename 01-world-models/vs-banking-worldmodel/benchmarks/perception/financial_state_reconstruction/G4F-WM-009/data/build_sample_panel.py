"""Export the WM-008 synthetic panel as a frozen WM-009 sample input.

The WM-009 evaluator reads the checked-in CSV and does not need WM-008 at
runtime. Rebuilding the source panel imports WM-008's documented generator.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
WM008_DIR = TASK_DIR.parent / "G4F-WM-008"
OUTPUT_DIR = TASK_DIR / "data" / "sample"


def build() -> dict:
    if not WM008_DIR.is_dir():
        raise FileNotFoundError(f"WM-008 source generator is not available: {WM008_DIR}")
    sys.path.insert(0, str(WM008_DIR))
    try:
        from synthetic import make_panel

        frame, _ = make_panel(n_entities=60, n_periods=36, horizon_months=3, seed=0)
    finally:
        sys.path.pop(0)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "synthetic_panel.csv"
    frame.to_csv(csv_path, index=False, date_format="%Y-%m-%d", float_format="%.8f", lineterminator="\n")
    manifest = {
        "dataset_name": "G4F-WM-009-frozen-wm008-synthetic-panel",
        "dataset_version": "1.0.0",
        "source_task": "G4F-WM-008",
        "source_generator": "synthetic.make_panel",
        "source_seed": 0,
        "entity_count": int(frame["entity_id"].nunique()),
        "row_count": int(len(frame)),
        "period_count": int(frame["timestamp"].nunique()),
        "horizon_months": 3,
        "synthetic": True,
        "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
