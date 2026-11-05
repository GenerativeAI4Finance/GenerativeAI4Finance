"""CLI for running the synthetic coordination experiment."""

import argparse
import json
from pathlib import Path

from .runner import DEFAULT_CONFIG, PACKAGE_ROOT, load_json, render_markdown, run_experiment


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare single and multi-agent synthetic EDD baselines.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--json-output", default=str(PACKAGE_ROOT / "results" / "results.json"))
    parser.add_argument("--markdown-output", default=str(PACKAGE_ROOT / "results" / "results.md"))
    args = parser.parse_args()
    result = run_experiment(load_json(args.config))
    json_path, markdown_path = Path(args.json_output), Path(args.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    print(f"Wrote {json_path} and {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
