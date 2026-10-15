import argparse
import json
import sys
import unicodedata

from .resolve import NO_MATCH, MatchConfig, load_records, resolve


def _terminal_text(text: str) -> str:
    """Keep supplied text on one line without executing terminal controls."""
    return "".join(
        char.encode("unicode_escape").decode("ascii")
        if unicodedata.category(char) in {"Cc", "Cs", "Zl", "Zp"}
        else char
        for char in text
    )


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        super().error(_terminal_text(message))


def main(argv=None) -> int:
    parser = _ArgumentParser(
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

    # Names can be in any script; do not depend on the console code page.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        config = MatchConfig.from_file(args.config) if args.config else MatchConfig()
        resolution = resolve(load_records(args.records), config)
    except (ValueError, OSError) as exc:
        print(f"error: {_terminal_text(str(exc))}", file=sys.stderr)
        return 2
    results = resolution.matches
    if args.hide_no_match:
        results = [r for r in results if r.label != NO_MATCH]

    if args.json:
        output = resolution.to_dict()
        output["matches"] = [r.to_dict() for r in results]
        json.dump(output, sys.stdout, indent=2)
        print()
        return 0

    print(
        f"thresholds: likely match >= {config.likely_match}, needs review >= {config.needs_review}"
    )
    print(
        "scores rank candidates for review; they do not establish that two records are the same company.\n"
    )
    for r in results:
        print(
            _terminal_text(
                f"{r.left_id} <> {r.right_id}  score={r.score}  {r.label}  [{r.status}]"
            )
        )
        for note in r.evidence["notes"]:
            print(f"    - {_terminal_text(note)}")
    if resolution.skipped_blocks:
        print(
            f"\nwarning: {len(resolution.skipped_blocks)} block(s) were too large and "
            "were not fully compared:"
        )
        for block in resolution.skipped_blocks:
            print(f"    - {_terminal_text(block.describe())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
