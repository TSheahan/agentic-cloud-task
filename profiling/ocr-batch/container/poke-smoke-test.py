#!/usr/bin/env python3
"""Poke smoke test: single-image Docling + RapidOCR paddle on CUDA.

Verifies the native poke stack produces real OCR output, not just that
imports succeed.  Exits 0 on PASS, 1 on FAIL.

Usage (on instance):
    python poke-smoke-test.py <image_path> [output_dir]

If output_dir is omitted, output is discarded after verification.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
)
from docling.document_converter import DocumentConverter, ImageFormatOption


def build_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        ocr_options=RapidOcrOptions(
            backend="paddle",
            force_full_page_ocr=True,
        ),
        accelerator_options=AcceleratorOptions(
            device=AcceleratorDevice.CUDA,
        ),
    )
    return DocumentConverter(
        allowed_formats=[InputFormat.IMAGE, InputFormat.PDF],
        format_options={
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
        },
    )


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python poke-smoke-test.py <image_path> [output_dir]",
            file=sys.stderr,
        )
        sys.exit(2)

    image_path = Path(sys.argv[1]).expanduser().resolve()
    if not image_path.is_file():
        print(f"FAIL: input not found: {image_path}")
        sys.exit(1)

    out_dir = (
        Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) >= 3 else None
    )

    try:
        converter = build_converter()
        t0 = time.perf_counter()
        result = converter.convert(str(image_path))
        elapsed = time.perf_counter() - t0

        if result.status.name != "SUCCESS":
            print(f"FAIL: conversion status {result.status}")
            sys.exit(1)

        md = result.document.export_to_markdown()
        if not md or len(md.strip()) < 10:
            print(f"FAIL: markdown output too short ({len(md)} chars)")
            sys.exit(1)

        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            md_path = out_dir / f"{image_path.stem}.md"
            md_path.write_text(md, encoding="utf-8")
            print(f"PASS: poke smoke ({elapsed:.1f}s, {len(md)} chars) -> {md_path}")
        else:
            print(f"PASS: poke smoke ({elapsed:.1f}s, {len(md)} chars)")

    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
