"""Evaluate scenario predictions against held-out simulated outcomes.

    python evaluate.py --predictions examples/predictions.csv \
        --outcomes examples/outcomes.csv --out reports/example_report
"""

import argparse
import hashlib
from io import BytesIO
from pathlib import Path

from scenario_eval.contract import load
from scenario_eval.metrics import MAX_BINS
from scenario_eval.report import evaluate, to_json, to_markdown


def sha256(path: str | Path) -> str:
    """sha256 of the file with CRLF read as LF, so a CRLF copy hashes the same."""
    return _sha256_bytes(Path(path).read_bytes())


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _int_arg(lo, hi=None):
    def parse(text):
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"expected an integer, got {text!r}") from None
        if value < lo or (hi is not None and value > hi):
            bounds = f"between {lo} and {hi}" if hi is not None else f"at least {lo}"
            raise argparse.ArgumentTypeError(f"must be {bounds}, got {value}")
        return value

    return parse


def output_paths(out: str | Path) -> tuple[Path, Path]:
    """<out>.json and <out>.md. A trailing .json or .md on out is dropped; any
    other dot is kept, so run.v2 gives run.v2.json rather than run.json."""
    out = Path(out)
    if out.suffix in (".json", ".md"):
        out = out.with_suffix("")
    return out.with_name(out.name + ".json"), out.with_name(out.name + ".md")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--outcomes", required=True)
    ap.add_argument("--out", required=True, help="output path without extension")
    ap.add_argument("--seed", type=_int_arg(0), default=0)
    ap.add_argument("--n-boot", type=_int_arg(1), default=500)
    ap.add_argument(
        "--n-bins", type=_int_arg(1, MAX_BINS), default=10, help=f"1 to {MAX_BINS}, default 10"
    )
    ap.add_argument("--pooled", action="store_true", help="also add a labelled pooled view")
    args = ap.parse_args(argv)

    # Parse and hash the same snapshots even if a producer replaces an input
    # after it has been read. Reopening for the hashes can misidentify the run.
    prediction_bytes = Path(args.predictions).read_bytes()
    outcome_bytes = Path(args.outcomes).read_bytes()
    df = load(BytesIO(prediction_bytes), BytesIO(outcome_bytes))
    prediction_name, outcome_name = Path(args.predictions).name, Path(args.outcomes).name
    if prediction_name == outcome_name:
        prediction_name = f"predictions:{prediction_name}"
        outcome_name = f"outcomes:{outcome_name}"
    inputs = {
        prediction_name: {"sha256": _sha256_bytes(prediction_bytes)},
        outcome_name: {"sha256": _sha256_bytes(outcome_bytes)},
    }
    report = evaluate(
        df,
        seed=args.seed,
        n_boot=args.n_boot,
        n_bins=args.n_bins,
        pooled=args.pooled,
        inputs=inputs,
    )
    json_path, md_path = output_paths(args.out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    # LF on every platform, so the files are byte-identical everywhere
    json_path.write_text(to_json(report), encoding="utf-8", newline="\n")
    md_path.write_text(to_markdown(report), encoding="utf-8", newline="\n")
    print(f"wrote {json_path} and {md_path}")


if __name__ == "__main__":
    main()
