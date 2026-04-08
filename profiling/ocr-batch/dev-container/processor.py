"""AWS Batch OCR processor — Docling 2.x torch pipeline.

Downloads a PDF from S3, runs GPU-accelerated OCR via Docling + RapidOCR
(torch backend on CUDA), uploads Markdown + JSON + COMPLETED artifact.

Usage:
    python processor.py <input_s3_uri> <output_s3_prefix>

Example:
    python processor.py s3://bucket/inbox/doc.pdf s3://bucket/processed/doc/
"""

import json
import sys
import tempfile
from pathlib import Path

import boto3
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

s3 = boto3.client("s3")


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Split 's3://bucket/key/path' into ('bucket', 'key/path')."""
    path = uri.replace("s3://", "", 1)
    return path.split("/", 1)


def build_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        ocr_options=RapidOcrOptions(backend="torch", force_full_page_ocr=True),
        ocr_batch_size=16,
        accelerator_options=AcceleratorOptions(
            device=AcceleratorDevice.CUDA,
            num_threads=4,
        ),
    )
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        },
    )


def main():
    if len(sys.argv) < 3:
        print("Usage: processor.py <input_s3_uri> <output_s3_prefix>")
        sys.exit(1)

    input_uri = sys.argv[1]
    output_prefix = sys.argv[2]

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
        assert result.status.name == "SUCCESS", f"Conversion failed: {result.status}"

        md_path = Path(tmpdir) / f"{stem}.md"
        md_path.write_text(
            result.document.export_to_markdown(), encoding="utf-8"
        )

        # export_to_dict() -> dict; needs runtime verification on exact API
        json_path = Path(tmpdir) / f"{stem}.json"
        json_path.write_text(
            json.dumps(result.document.export_to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        s3.upload_file(str(md_path), bucket_out, f"{prefix_out}{stem}.md")
        s3.upload_file(str(json_path), bucket_out, f"{prefix_out}{stem}.json")

        artifact = Path(tmpdir) / "COMPLETED"
        artifact.touch()
        s3.upload_file(str(artifact), bucket_out, f"{prefix_out}COMPLETED")

    print(f"OCR complete -> {output_prefix}")


if __name__ == "__main__":
    main()
