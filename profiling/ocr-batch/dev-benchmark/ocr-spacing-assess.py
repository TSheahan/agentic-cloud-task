#!/usr/bin/env python3
"""Heuristic spacing comparison for Docling OCR Markdown exports.

These metrics **do not** measure ground-truth spacing; they support **relative**
comparison across benchmark runs (same `sample_scan/` inputs).

Per file (body text, newlines stripped for ratios):
  - **camel**: ``[a-z][A-Z]`` — possible glued Latin words (also camelCase, headers).
  - **digit_letter**: ``[0-9][a-zA-Z]`` — noisy (units, odometer-style tokens).
  - **space_ratio**: (spaces + tabs) / non-newline characters.

Usage::

  # Single run (uses outputs/cuda if present, else outputs/cpu)
  python ocr-spacing-assess.py /path/to/run/dir

  # Label rows (e.g. benchmark id)
  python ocr-spacing-assess.py /path/to/run --label round7

  # All immediate subdirs of WORKDIR/runs that contain outputs/cuda
  export OCR_WORKDIR=/home/ubuntu/ocr-work
  python ocr-spacing-assess.py --discover

Output: JSON with per-file rows + mean aggregates, printed to stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _metrics(text: str) -> dict[str, float | int]:
    # Strip newlines for ratio so tables don't dominate line-break semantics
    flat = text.replace("\n", " ")
    n = len(flat)
    if n == 0:
        return {
            "camel": 0,
            "digit_letter": 0,
            "space_ratio": 0.0,
            "chars_nonl": 0,
        }
    spaces = sum(1 for c in flat if c in " \t")
    camel = len(re.findall(r"[a-z][A-Z]", flat))
    digit_letter = len(re.findall(r"[0-9][a-zA-Z]", flat))
    return {
        "camel": camel,
        "digit_letter": digit_letter,
        "space_ratio": round(spaces / n, 6),
        "chars_nonl": n,
    }


def _pick_out_dir(run_dir: Path) -> Path | None:
    cuda = run_dir / "outputs" / "cuda"
    cpu = run_dir / "outputs" / "cpu"
    if cuda.is_dir():
        return cuda
    if cpu.is_dir():
        return cpu
    return None


def assess_run(run_dir: Path, label: str | None = None) -> dict:
    run_dir = run_dir.resolve()
    out = _pick_out_dir(run_dir)
    if out is None:
        raise SystemExit(f"No outputs/cuda or outputs/cpu under {run_dir}")
    md_files = sorted(out.glob("*.md"))
    if not md_files:
        raise SystemExit(f"No .md under {out}")

    rows = []
    for p in md_files:
        text = p.read_text(encoding="utf-8", errors="replace")
        m = _metrics(text)
        rows.append({"file": p.name, **m})

    def mean(key: str) -> float:
        v = [r[key] for r in rows]
        return round(sum(v) / len(v), 6) if v else 0.0

    return {
        "label": label or run_dir.name,
        "run_dir": str(run_dir),
        "output_path": str(out),
        "rows": rows,
        "mean": {
            "camel": mean("camel"),
            "digit_letter": mean("digit_letter"),
            "space_ratio": mean("space_ratio"),
        },
    }


def discover_runs(runs_parent: Path) -> list[Path]:
    runs = []
    for child in sorted(runs_parent.iterdir()):
        if child.is_dir() and _pick_out_dir(child) is not None:
            runs.append(child)
    return runs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "run_dir",
        nargs="?",
        help="Benchmark run directory (contains outputs/cuda or outputs/cpu)",
    )
    ap.add_argument("--label", help="Short label for JSON output")
    ap.add_argument(
        "--discover",
        action="store_true",
        help="Use OCR_WORKDIR/runs (or --runs-root) and assess each subdir",
    )
    ap.add_argument(
        "--runs-root",
        type=Path,
        help="Parent of run dirs (default: $OCR_WORKDIR/runs)",
    )
    args = ap.parse_args()

    if args.discover:
        root = args.runs_root
        if root is None:
            import os

            wd = os.environ.get("OCR_WORKDIR", "/home/ubuntu/ocr-work")
            root = Path(wd) / "runs"
        if not root.is_dir():
            raise SystemExit(f"Not a directory: {root}")
        payload = []
        for rd in discover_runs(root):
            try:
                payload.append(assess_run(rd))
            except SystemExit as e:
                print(f"skip {rd}: {e}", file=sys.stderr)
        print(json.dumps({"runs": payload}, indent=2))
        return

    if not args.run_dir:
        ap.print_help()
        sys.exit(2)

    print(json.dumps(assess_run(Path(args.run_dir), args.label), indent=2))


if __name__ == "__main__":
    main()
