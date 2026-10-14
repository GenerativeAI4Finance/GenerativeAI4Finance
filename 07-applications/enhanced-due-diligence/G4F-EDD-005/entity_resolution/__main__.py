import argparse
import json
import sys

from .resolve import NO_MATCH, MatchConfig, load_records, resolve


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m entity_resolution",
        description="List candidate company record matches with the evidence behind each score.",
    )
    parser.add_argument("records", help="JSON file with a top-level 'records' list")
    parser.add_argument("--config", help="JSON file overriding MatchConfig fields")
    parser.add_argument(
        "--hide-no-match",
        action="store_true",
        help="only print pairs at or above needs_review",
    )
    parser.add_argument("--json", action="store_true", help="print results as JSON")
    args = parser.parse_args(argv)

    config = MatchConfig.from_file(args.config) if args.config else MatchConfig()
    results = resolve(load_records(args.records), config)
    if args.hide_no_match:
        results = [r for r in results if r.label != NO_MATCH]

    if args.json:
        json.dump([r.to_dict() for r in results], sys.stdout, indent=2)
        print()
        return 0

    print(
        f"thresholds: likely match >= {config.likely_match}, needs review >= {config.needs_review}"
    )
    print(
        "scores rank candidates for review; they do not establish that two records are the same company.\n"
    )
    for r in results:
        print(f"{r.left_id} <> {r.right_id}  score={r.score}  {r.label}  [{r.status}]")
        for note in r.evidence["notes"]:
            print(f"    - {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
