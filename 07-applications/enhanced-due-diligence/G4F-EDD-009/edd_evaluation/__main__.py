"""Run the gold-set evaluation from JSON files."""

import argparse
import json
from pathlib import Path

from .evaluate import render_results_markdown, run_evaluation


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Evaluate EDD-006 extraction outputs against a synthetic gold set.")
    parser.add_argument("--gold-set", default=str(root / "examples/gold_set_v1.json"))
    parser.add_argument("--model-predictions", default=str(root / "examples/mock_model_predictions.json"), help="Optional EDD-006-style prediction bundle")
    parser.add_argument("--baseline-only", action="store_true", help="Skip optional prediction comparison")
    parser.add_argument("--json-output", default=str(root / "results/results.json"))
    parser.add_argument("--markdown-output", default=str(root / "results/results.md"))
    args = parser.parse_args()

    gold = json.loads(Path(args.gold_set).read_text(encoding="utf-8"))
    model = None if args.baseline_only or not args.model_predictions else json.loads(Path(args.model_predictions).read_text(encoding="utf-8"))
    results = run_evaluation(gold, model)
    json_path, markdown_path = Path(args.json_output), Path(args.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_results_markdown(results), encoding="utf-8")
    print(f"Wrote {json_path} and {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
