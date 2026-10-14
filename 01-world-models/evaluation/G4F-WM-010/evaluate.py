"""Evaluate scenario predictions against held-out simulated outcomes.

    python evaluate.py --predictions examples/predictions.csv \
        --outcomes examples/outcomes.csv --out reports/example_report
"""

import argparse
import hashlib
import json
from pathlib import Path

from scenario_eval.contract import load
from scenario_eval.report import evaluate, to_markdown


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--outcomes", required=True)
    ap.add_argument("--out", required=True, help="output path without extension")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--n-bins", type=int, default=10)
    ap.add_argument("--pooled", action="store_true", help="also add a labelled pooled view")
    args = ap.parse_args(argv)

    df = load(args.predictions, args.outcomes)
    inputs = {
        Path(args.predictions).name: {"sha256": sha256(args.predictions)},
        Path(args.outcomes).name: {"sha256": sha256(args.outcomes)},
    }
    report = evaluate(
        df,
        seed=args.seed,
        n_boot=args.n_boot,
        n_bins=args.n_bins,
        pooled=args.pooled,
        inputs=inputs,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    out.with_suffix(".md").write_text(to_markdown(report))
    print(f"wrote {out.with_suffix('.json')} and {out.with_suffix('.md')}")


if __name__ == "__main__":
    main()
