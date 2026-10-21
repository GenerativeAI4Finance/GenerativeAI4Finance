"""Split the synthetic panel and print the leakage report as JSON.

python example.py --policy time_entity --seed 7
python example.py --policy entity --out report.json
"""

import argparse
from pathlib import Path

from leakage import run_checks, to_json
from splits import POLICIES, make_splits
from synthetic import make_panel


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", choices=POLICIES, default="time_entity")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--valid-start", default="2022-07-01")
    parser.add_argument("--test-start", default="2023-04-01")
    parser.add_argument("--out", type=Path, help="write the report here")
    args = parser.parse_args()

    df, spec = make_panel(seed=0)
    result = make_splits(
        df,
        spec,
        args.policy,
        valid_start=args.valid_start,
        test_start=args.test_start,
        seed=args.seed,
    )
    report = run_checks(df, result.labels, spec, result.manifest)
    text = to_json(report)
    if args.out:
        args.out.write_text(text + "\n")
    else:
        print(text)
    return 0 if report["all_applicable_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
