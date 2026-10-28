"""Command-line entry point for the EDD Markdown report generator."""

import argparse
import json
from pathlib import Path

from .report import generate_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an auditable Markdown EDD review report.")
    parser.add_argument("--input", required=True, help="JSON report bundle")
    parser.add_argument("--output", help="Output Markdown path; defaults to stdout")
    args = parser.parse_args()
    bundle = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(bundle, dict) or "case_record" not in bundle:
        parser.error("input JSON must be an object containing case_record")
    case_record = bundle.pop("case_record")
    report = generate_report(case_record, **bundle)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
