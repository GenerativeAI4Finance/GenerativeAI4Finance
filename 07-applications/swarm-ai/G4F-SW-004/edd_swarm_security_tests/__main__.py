"""Run the local contamination and prompt-injection fixture suite."""

import argparse
import json
from pathlib import Path

from .evaluate import PACKAGE_ROOT, evaluate_suite, render_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local synthetic EDD prompt-injection checks.")
    parser.add_argument("--json-output", default=str(PACKAGE_ROOT / "results" / "results.json"))
    parser.add_argument("--markdown-output", default=str(PACKAGE_ROOT / "results" / "results.md"))
    args = parser.parse_args()
    result = evaluate_suite()
    json_path = Path(args.json_output)
    markdown_path = Path(args.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    print(f"Wrote {json_path} and {markdown_path}")
    return 0 if result["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
