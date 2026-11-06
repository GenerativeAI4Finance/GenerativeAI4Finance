"""Score the bundled benchmark run and write JSON and Markdown reports."""

import argparse
import json
from pathlib import Path

from .metrics import PACKAGE_ROOT, render_markdown, score_benchmark_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute the G4F-SW-007 EDD benchmark scorecard.")
    parser.add_argument("--input", default=str(PACKAGE_ROOT / "examples" / "example_benchmark_run.json"))
    parser.add_argument("--json-output", default=str(PACKAGE_ROOT / "results" / "example_scorecard.json"))
    parser.add_argument("--markdown-output", default=str(PACKAGE_ROOT / "results" / "example_scorecard.md"))
    args = parser.parse_args()
    run = json.loads(Path(args.input).read_text(encoding="utf-8"))
    scorecard = score_benchmark_run(run)
    json_path, markdown_path = Path(args.json_output), Path(args.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(scorecard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(scorecard), encoding="utf-8")
    print(f"Wrote {json_path} and {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
