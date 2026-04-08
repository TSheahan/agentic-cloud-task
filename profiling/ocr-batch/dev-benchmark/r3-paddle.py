#!/usr/bin/env python3
"""Round 3: RapidOCR `backend="paddle"` (PaddleOCR) + Docling CUDA vs CPU accelerator sweep.

Same inputs as rounds 1–2 (`WORKDIR/sample_scan/`). Differs by:
  - `RapidOcrOptions(backend="paddle", force_full_page_ocr=True)`
  - `PdfPipelineOptions(do_table_structure=True, ocr_batch_size=...)`

Docling 2.x: `force_full_page_ocr` belongs on `RapidOcrOptions`, not on `PdfPipelineOptions`.
Use `ImageFormatOption` + `DocumentConverter(format_options=...)`, not `pipeline_options=` on the converter.

Usage (on instance, venv active, Paddle stack installed per profile):
  export OCR_WORKDIR=/home/ubuntu/ocr-work
  export OCR_BATCH_SIZE=16   # optional
  python r3-paddle.py /path/to/run/dir

Requires PaddlePaddle + GPU setup compatible with RapidOCR paddle backend (see Apply §3e when added).
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


def _workdir() -> Path:
    return Path(os.environ.get("OCR_WORKDIR", "/home/ubuntu/ocr-work"))


def _sample_dir() -> Path:
    return _workdir() / "sample_scan"


def _ocr_batch_size() -> int:
    return int(os.environ.get("OCR_BATCH_SIZE", "16"))


def make_pipeline_options(device: AcceleratorDevice) -> PdfPipelineOptions:
    ocr = RapidOcrOptions(
        backend="paddle",
        force_full_page_ocr=True,
    )
    return PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        ocr_options=ocr,
        ocr_batch_size=_ocr_batch_size(),
        accelerator_options=AcceleratorOptions(
            device=device,
            num_threads=int(os.environ.get("OCR_NUM_THREADS", "4")),
        ),
    )


def make_converter(device: AcceleratorDevice) -> DocumentConverter:
    pipeline_options = make_pipeline_options(device)
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
    cpu_seconds: float | None = None
    cuda_status: str | None = None
    cpu_status: str | None = None


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
            "Usage: python r3-paddle.py <run_directory>",
            file=sys.stderr,
        )
        sys.exit(2)
    run_root = Path(sys.argv[1]).resolve()
    sample_dir = _sample_dir()
    out_cuda = run_root / "outputs" / "cuda"
    out_cpu = run_root / "outputs" / "cpu"

    files = sorted(sample_dir.glob("*.jpg")) + sorted(sample_dir.glob("*.JPG"))
    if not files:
        raise SystemExit(f"No images under {sample_dir}")

    out_cuda.mkdir(parents=True, exist_ok=True)
    out_cpu.mkdir(parents=True, exist_ok=True)

    rows: list[Row] = []

    conv_cuda = make_converter(AcceleratorDevice.CUDA)
    t_cold = time.perf_counter()
    conv_cuda.convert(str(files[0]))
    cold_cuda_sec = time.perf_counter() - t_cold

    for p in files:
        t0 = time.perf_counter()
        r = conv_cuda.convert(str(p))
        elapsed = time.perf_counter() - t0
        md = r.document.export_to_markdown()
        (out_cuda / f"{p.stem}.md").write_text(md, encoding="utf-8")
        rows.append(
            Row(
                file=p.name,
                bytes=p.stat().st_size,
                cuda_seconds=elapsed,
                cuda_status=r.status.value if r.status else None,
            )
        )

    conv_cpu = make_converter(AcceleratorDevice.CPU)
    t_cold_cpu = time.perf_counter()
    conv_cpu.convert(str(files[0]))
    cold_cpu_sec = time.perf_counter() - t_cold_cpu

    by_name = {r.file: r for r in rows}
    for p in files:
        t0 = time.perf_counter()
        r = conv_cpu.convert(str(p))
        elapsed = time.perf_counter() - t0
        md = r.document.export_to_markdown()
        (out_cpu / f"{p.stem}.md").write_text(md, encoding="utf-8")
        by_name[p.name].cpu_seconds = elapsed
        by_name[p.name].cpu_status = r.status.value if r.status else None

    total_cuda = sum(r.cuda_seconds or 0 for r in rows)
    total_cpu = sum(r.cpu_seconds or 0 for r in rows)

    per_doc_ratios = []
    for r in rows:
        if r.cuda_seconds and r.cpu_seconds and r.cuda_seconds > 0:
            per_doc_ratios.append(r.cpu_seconds / r.cuda_seconds)

    try:
        from importlib.metadata import version

        dv = version("docling")
    except Exception:
        dv = None

    payload = {
        "benchmark_round": 3,
        "rapidocr_backend": "paddle",
        "docling_version": dv,
        "ocr_batch_size": _ocr_batch_size(),
        "paddle": _paddle_meta(),
        "sample_dir": str(sample_dir),
        "methodology": (
            "Round 3: RapidOCR paddle backend (PaddleOCR) + full-page OCR + "
            "table structure; Docling accelerator CUDA vs CPU for layout/table ONNX. "
            "Same cold/warm pattern as rounds 1–2."
        ),
        "cold_load_untimed_seconds": {
            "cuda_first_file": round(cold_cuda_sec, 4),
            "cpu_first_file": round(cold_cpu_sec, 4),
        },
        "rows": [asdict(r) for r in rows],
        "totals": {
            "cuda_sum_s": round(total_cuda, 3),
            "cpu_sum_s": round(total_cpu, 3),
            "ratio_cpu_per_cuda": round(total_cpu / total_cuda, 3) if total_cuda else None,
            "mean_doc_ratio_cpu_per_cuda": round(
                sum(per_doc_ratios) / len(per_doc_ratios), 3
            )
            if per_doc_ratios
            else None,
        },
    }
    (run_root / "timings.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    print(json.dumps(payload["totals"], indent=2))


if __name__ == "__main__":
    main()
