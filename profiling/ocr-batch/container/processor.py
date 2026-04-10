"""AWS Batch OCR processor — Docling 2.x + RapidOCR paddle on CUDA.

Production output contract (three artifacts): **Markdown**, **JSON** (from the
Docling document), and a **copy of the original input** (PDF or image). Upstream
match input may be discarded once these three exist under the output prefix.

**PaddlePaddle GPU** for **RapidOCR `backend="paddle"`** must be present in
the environment: **fat image** — installed in the container image (see
Dockerfile); **thin + bind** — from the host via `PYTHONPATH` (see ocr-batch
profile). This file does not embed install commands beyond normal imports.

S3 mode: download object → convert → upload `.md`, `.json`, and original
basename (same as input key).

Local mode: `OCR_LOCAL_FILE` + `OCR_LOCAL_OUTPUT_DIR` — write the same three
files locally (no S3).

Logging: optional env **`OCR_LOG_LEVEL`** (`DEBUG`, `INFO`, `WARNING`, `ERROR`,
`CRITICAL`; default **`WARNING`**) applied before Docling/RapidOCR import so
CloudWatch stays quiet unless you opt into verbose library logs.

Usage (S3):
    python processor.py <input_s3_uri> <output_s3_prefix>

Usage (local):
    export OCR_LOCAL_FILE=~/1.1.jpg
    export OCR_LOCAL_OUTPUT_DIR=~/ocr-work/product
    python processor.py

Example (S3):
    python processor.py s3://bucket/inbox/doc.pdf s3://bucket/processed/doc/
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Point docling to baked model dir so layout/table models load from disk without
# network calls. Set before docling imports so settings.artifacts_path picks it up.
# Not declared as ENV in Dockerfile — setting it there causes docling 2.85+ to
# KeyError on _default_models["paddle"] inside the rapidocr model resolver.
os.environ.setdefault("DOCLING_ARTIFACTS_PATH", "/app/docling-models")


def _configure_logging() -> None:
    """Apply root log level before third-party imports (default: WARNING)."""
    raw = os.environ.get("OCR_LOG_LEVEL", "WARNING").strip().upper()
    level = getattr(logging, raw, None)
    if not isinstance(level, int):
        level = logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
        force=True,
    )


_configure_logging()

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
)
from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Split 's3://bucket/key/path' into ('bucket', 'key/path')."""
    path = uri.replace("s3://", "", 1)
    return path.split("/", 1)


_RAPIDOCR_MODELS = Path(
    "/usr/local/lib/python3.10/dist-packages/rapidocr/models"
)

def build_converter() -> DocumentConverter:
    # Docling 2.85+ removed "paddle" from RapidOcrModel._default_models, so passing
    # det/cls/rec paths explicitly avoids a KeyError when artifacts_path is set.
    # Paths were pre-downloaded by bake-models.py at image build time.
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        ocr_options=RapidOcrOptions(
            backend="paddle",
            force_full_page_ocr=True,
            det_model_path=str(_RAPIDOCR_MODELS / "ch_PP-OCRv4_det_mobile"),
            cls_model_path=str(_RAPIDOCR_MODELS / "ch_ppocr_mobile_v2_0_cls_mobile"),
            rec_model_path=str(_RAPIDOCR_MODELS / "ch_PP-OCRv4_rec_mobile"),
            rec_keys_path=str(_RAPIDOCR_MODELS / "ppocr_keys_v1.txt"),
            font_path=str(_RAPIDOCR_MODELS / "ppocr_keys_v1.txt"),
        ),
        ocr_batch_size=16,
        accelerator_options=AcceleratorOptions(
            device=AcceleratorDevice.CUDA,
            num_threads=4,
        ),
    )
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
        },
    )


def _write_outputs(result, out_dir: Path, stem: str, source_path: Path) -> None:
    """Write `{stem}.md`, `{stem}.json`, and a copy of the original `source_path`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{stem}.md"
    md_path.write_text(result.document.export_to_markdown(), encoding="utf-8")
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(
        json.dumps(result.document.export_to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    dest_original = out_dir / source_path.name
    if source_path.resolve() != dest_original.resolve():
        shutil.copy2(source_path, dest_original)


def run_local(input_path: Path, output_dir: Path) -> None:
    input_path = input_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not input_path.is_file():
        raise SystemExit(f"Input file not found: {input_path}")

    converter = build_converter()
    result = converter.convert(str(input_path))
    if result.status.name != "SUCCESS":
        raise SystemExit(f"Conversion failed: {result.status}")

    stem = input_path.stem
    _write_outputs(result, output_dir, stem, input_path)
    print(
        f"OCR complete -> {output_dir} ({stem}.md, {stem}.json, {input_path.name})"
    )


def run_s3(input_uri: str, output_prefix: str) -> None:
    import boto3

    s3 = boto3.client("s3")
    bucket_in, key_in = parse_s3_uri(input_uri)
    bucket_out, prefix_out = parse_s3_uri(output_prefix)
    if not prefix_out.endswith("/"):
        prefix_out += "/"

    with tempfile.TemporaryDirectory() as tmpdir:
        local_in = Path(tmpdir) / Path(key_in).name
        stem = Path(key_in).stem

        s3.download_file(bucket_in, key_in, str(local_in))

        converter = build_converter()
        result = converter.convert(str(local_in))
        if result.status.name != "SUCCESS":
            raise SystemExit(f"Conversion failed: {result.status}")

        out_tmp = Path(tmpdir)
        _write_outputs(result, out_tmp, stem, local_in)

        orig_name = Path(key_in).name
        md_path = out_tmp / f"{stem}.md"
        json_path = out_tmp / f"{stem}.json"

        s3.upload_file(str(md_path), bucket_out, f"{prefix_out}{stem}.md")
        s3.upload_file(str(json_path), bucket_out, f"{prefix_out}{stem}.json")
        s3.upload_file(str(local_in), bucket_out, f"{prefix_out}{orig_name}")

    print(f"OCR complete -> {output_prefix}")


def main() -> None:
    local_file = os.environ.get("OCR_LOCAL_FILE")
    local_out = os.environ.get("OCR_LOCAL_OUTPUT_DIR")

    if local_file or local_out:
        if not local_file or not local_out:
            print(
                "Local mode requires both OCR_LOCAL_FILE and OCR_LOCAL_OUTPUT_DIR.",
                file=sys.stderr,
            )
            sys.exit(1)
        run_local(Path(local_file), Path(local_out))
        return

    if len(sys.argv) < 3:
        print(
            "S3 mode: python processor.py <input_s3_uri> <output_s3_prefix>\n"
            "Local mode: set OCR_LOCAL_FILE and OCR_LOCAL_OUTPUT_DIR",
            file=sys.stderr,
        )
        sys.exit(1)

    run_s3(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
