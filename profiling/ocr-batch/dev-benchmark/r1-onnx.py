#!/usr/bin/env python3
"""Timed CUDA vs CPU Docling accelerator sweep for images under WORKDIR/sample_scan/.

Usage (on instance, venv active):
  export OCR_WORKDIR=/home/ubuntu/ocr-work
  python r1-onnx.py /path/to/run/dir

Writes timings.json, outputs/cuda/*.md, outputs/cpu/*.md under the run dir.
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


def make_converter(device: AcceleratorDevice) -> DocumentConverter:
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        ocr_options=RapidOcrOptions(),
        accelerator_options=AcceleratorOptions(
            device=device,
            num_threads=4,
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
    cpu_seconds: float | None = None
    cuda_status: str | None = None
    cpu_status: str | None = None


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python r1-onnx.py <run_directory>", file=sys.stderr)
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

    payload = {
        "sample_dir": str(sample_dir),
        "methodology": (
            "Two passes: CUDA accelerator then CPU accelerator. "
            "Each pass uses one DocumentConverter; first convert of files[0] is untimed "
            "(cold model load for that mode). Timed loop re-converts all files in order "
            "with the warm pipeline — first timed row is the second visit to files[0]."
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
