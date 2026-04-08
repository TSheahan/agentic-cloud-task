#!/usr/bin/env python3
"""Round 4: Default RapidOCR (ONNX) + Docling CUDA only; spacing fix on export.

Same inputs as round 1 (`WORKDIR/sample_scan/`). Differs from round 1 by:
  - No CPU accelerator pass (GPU timing only).
  - ``RapidOcrOptions(rapidocr_params={"Rec.use_space_char": True})`` (Docling passes
    through to RapidOCR; not a top-level RapidOcrOptions field in Docling 2.x).
  - Markdown written under `outputs/cuda/` is passed through :func:`ocr_spacing_fix.apply_spacing_fix`.

Round 1 used CUDA for Docling layout/table ONNX while RapidOCR detection/recognition
stayed on CPU (partial GPU). This round keeps that stack; only the comparison
methodology changes (no CPU sweep).

Usage (on instance, venv active):
  export OCR_WORKDIR=/home/ubuntu/ocr-work
  python r4-onnx-spacing.py /path/to/run/dir
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from docling.document_converter import DocumentConverter, ImageFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
)

_pkg = Path(__file__).resolve().parent
if _pkg.name == "dev-benchmark":
    _pkg = _pkg.parent
if str(_pkg) not in sys.path:
    sys.path.insert(0, str(_pkg))
from ocr_spacing_fix import SPACING_FIX_REVISION, apply_spacing_fix


def _workdir() -> Path:
    return Path(os.environ.get("OCR_WORKDIR", "/home/ubuntu/ocr-work"))


def _sample_dir() -> Path:
    return _workdir() / "sample_scan"


def make_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        ocr_options=RapidOcrOptions(
            rapidocr_params={"Rec.use_space_char": True},
        ),
        accelerator_options=AcceleratorOptions(
            device=AcceleratorDevice.CUDA,
            num_threads=int(os.environ.get("OCR_NUM_THREADS", "4")),
        ),
    )
    return DocumentConverter(
        allowed_formats=[InputFormat.IMAGE],
        format_options={
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
        },
    )


@dataclass
class Row:
    file: str
    bytes: int
    cuda_seconds: float | None = None
    cuda_status: str | None = None


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python r4-onnx-spacing.py <run_directory>",
            file=sys.stderr,
        )
        sys.exit(2)
    run_root = Path(sys.argv[1]).resolve()
    sample_dir = _sample_dir()
    out_cuda = run_root / "outputs" / "cuda"

    files = sorted(sample_dir.glob("*.jpg")) + sorted(sample_dir.glob("*.JPG"))
    if not files:
        raise SystemExit(f"No images under {sample_dir}")

    out_cuda.mkdir(parents=True, exist_ok=True)

    rows: list[Row] = []

    conv_cuda = make_converter()
    t_cold = time.perf_counter()
    conv_cuda.convert(str(files[0]))
    cold_cuda_sec = time.perf_counter() - t_cold

    for p in files:
        t0 = time.perf_counter()
        r = conv_cuda.convert(str(p))
        elapsed = time.perf_counter() - t0
        md = apply_spacing_fix(r.document.export_to_markdown())
        (out_cuda / f"{p.stem}.md").write_text(md, encoding="utf-8")
        rows.append(
            Row(
                file=p.name,
                bytes=p.stat().st_size,
                cuda_seconds=elapsed,
                cuda_status=r.status.value if r.status else None,
            )
        )

    total_cuda = sum(r.cuda_seconds or 0 for r in rows)

    try:
        from importlib.metadata import version

        dv = version("docling")
    except Exception:
        dv = None

    payload = {
        "benchmark_round": 4,
        "benchmark_series": "gpu-spacing",
        "cpu_pass": "skipped",
        "rapidocr_backend": "onnx",
        "spacing_fix_revision": SPACING_FIX_REVISION,
        "docling_version": dv,
        "sample_dir": str(sample_dir),
        "methodology": (
            "Round 4: Default RapidOCR (ONNX) + Docling accelerator CUDA only; "
            "rapidocr_params Rec.use_space_char=True. No CPU pass. Timed: convert() per file. "
            "Markdown: export_to_markdown() then apply_spacing_fix(); write outputs/cuda/*.md. "
            "Cold: untimed first convert on files[0]."
        ),
        "cold_load_untimed_seconds": {"cuda_first_file": round(cold_cuda_sec, 4)},
        "rows": [asdict(r) for r in rows],
        "totals": {"cuda_sum_s": round(total_cuda, 3)},
    }
    (run_root / "timings.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    print(json.dumps(payload["totals"], indent=2))


if __name__ == "__main__":
    main()
