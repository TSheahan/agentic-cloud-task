#!/usr/bin/env python3
"""Round 7: RapidOCR paddle + tuned detection/recognition + Docling CUDA only.

Tuned to match this intent (Docling 2.x wiring differs from a flat snippet):

  - ``backend="paddle"``, ``force_full_page_ocr=True``
  - Space handling: ``rapidocr_params["Rec.use_space_char"] = True`` (RapidOCR;
    not a top-level ``RapidOcrOptions`` field)
  - ``text_score=0.6`` on ``RapidOcrOptions`` (maps to ``Global.text_score``)
  - ``ocr_batch_size``: on ``PdfPipelineOptions`` here (default 16 via ``OCR_BATCH_SIZE``)
  - ``det_db_score_mode="slow"`` (Paddle name) → RapidOCR ``Det.score_mode="slow"``

Same inputs / layout as rounds 4–6: ``WORKDIR/sample_scan/``, ``outputs/cuda/*.md``,
GPU-only timing, ``apply_spacing_fix`` on export.

Usage (on instance, venv active, Paddle stack installed):
  export OCR_WORKDIR=/home/ubuntu/ocr-work
  export OCR_BATCH_SIZE=16   # optional; default 16
  python r7-paddle-tuned.py /path/to/run/dir
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


def _ocr_batch_size() -> int:
    return int(os.environ.get("OCR_BATCH_SIZE", "16"))


def make_converter() -> DocumentConverter:
    ocr = RapidOcrOptions(
        backend="paddle",
        force_full_page_ocr=True,
        text_score=0.6,
        rapidocr_params={
            "Rec.use_space_char": True,
            "Det.score_mode": "slow",
        },
    )
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        ocr_options=ocr,
        ocr_batch_size=_ocr_batch_size(),
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


def _paddle_meta() -> dict:
    try:
        import paddle

        ver = getattr(paddle, "__version__", None)
        cuda = None
        try:
            cuda = paddle.device.is_compiled_with_cuda()
        except Exception:
            pass
        return {"paddle_version": ver, "paddle_compiled_with_cuda": cuda}
    except Exception as e:
        return {"paddle_import_error": str(e)}


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python r7-paddle-tuned.py <run_directory>",
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
        "benchmark_round": 7,
        "benchmark_series": "gpu-spacing",
        "cpu_pass": "skipped",
        "rapidocr_backend": "paddle",
        "spacing_fix_revision": SPACING_FIX_REVISION,
        "docling_version": dv,
        "ocr_batch_size": _ocr_batch_size(),
        "rapidocr_tuning": {
            "text_score": 0.6,
            "rec_use_space_char": True,
            "det_score_mode": "slow",
            "note": "Paddle det_db_score_mode maps to RapidOCR Det.score_mode",
        },
        "paddle": _paddle_meta(),
        "sample_dir": str(sample_dir),
        "methodology": (
            "Round 7: Paddle + text_score=0.6, Rec.use_space_char, Det.score_mode=slow, "
            "ocr_batch_size from OCR_BATCH_SIZE (default 16); CUDA only; export + apply_spacing_fix."
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
