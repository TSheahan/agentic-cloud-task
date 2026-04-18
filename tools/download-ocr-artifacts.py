#!/usr/bin/env python3
"""Download the three OCR artifacts from S3 given any source file reference.

Companion tool to upload-local-ocr.py and submit-ocr-batch-job.py for POC runs.

Accepts a **source file reference** (local path, full S3 URI, key, or filename).
It is slash-agnostic and trims any leading slash.

From the reference it extracts:
  - stem (filename without extension)
  - original basename (with extension)

Then reconstructs the three artifact locations under:
  s3://<bucket>/<output-prefix>/{stem}.md
  s3://<bucket>/<output-prefix>/{stem}.json
  s3://<bucket>/<output-prefix>/{original-basename}

Downloads all three files into the current working directory (or --output-dir).

Uses the same credential and env patterns as the rest of the toolchain.
"""

import argparse
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from _env import boto3_session, resolved_assume_role_arn

DEFAULT_OUTPUT_PREFIX = "poc-processed/"
ENV_BUCKET = "OCR_BUCKET"

def _parse_any_reference(ref: str) -> tuple[str | None, str]:
    """Return (bucket_from_uri or None, basename) — extremely permissive."""
    ref = ref.strip()
    if ref.startswith("s3://"):
        # Full S3 URI
        path = ref[5:]  # remove s3://
        if "/" in path:
            bucket, key = path.split("/", 1)
            return bucket, Path(key).name
        return path, ""  # malformed, but we'll handle later

    # Local path, key, or bare filename — strip leading slash and use basename
    if ref.startswith("/"):
        ref = ref[1:]
    return None, Path(ref).name

def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "source_reference",
        help="Source file reference — local path, s3:// URI, key, or filename only",
    )
    p.add_argument(
        "--bucket",
        help=f"S3 bucket (falls back to ${ENV_BUCKET} env var)",
    )
    p.add_argument(
        "--output-prefix",
        default=DEFAULT_OUTPUT_PREFIX,
        help=f"Output prefix where artifacts live (default: {DEFAULT_OUTPUT_PREFIX})",
    )
    p.add_argument(
        "--assume-role",
        metavar="ARN",
        help="STS assume-role ARN (passed through to credential session)",
    )
    p.add_argument(
        "--output-dir",
        default=".",
        help="Local directory to download into (default: current working directory)",
    )

    args = p.parse_args()

    # Resolve bucket
    bucket = args.bucket or os.environ.get(ENV_BUCKET)
    if not bucket:
        print(
            f"Error: --bucket was not supplied and ${ENV_BUCKET} environment variable is not set.",
            file=sys.stderr,
        )
        return 1

    # Extract stem and original name from any reference format
    _, basename = _parse_any_reference(args.source_reference)
    if not basename:
        print("Error: Could not determine filename from reference.", file=sys.stderr)
        return 1

    original_name = basename
    stem = Path(basename).stem

    # Normalise output prefix
    output_prefix = args.output_prefix
    if not output_prefix.endswith("/"):
        output_prefix += "/"

    # Build the three S3 keys
    md_key = f"{output_prefix}{stem}.md"
    json_key = f"{output_prefix}{stem}.json"
    orig_key = f"{output_prefix}{original_name}"

    md_uri = f"s3://{bucket}/{md_key}"
    json_uri = f"s3://{bucket}/{json_key}"
    orig_uri = f"s3://{bucket}/{orig_key}"

    # Session (same pattern as the other tools)
    session = boto3_session(
        assume_role_arn=resolved_assume_role_arn(args.assume_role),
        role_session_name="download-ocr-artifacts",
    )
    s3 = session.client("s3")

    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    files_to_download = [
        (md_key, f"{stem}.md"),
        (json_key, f"{stem}.json"),
        (orig_key, original_name),
    ]

    print(f"Downloading OCR artifacts for stem '{stem}' from {output_prefix}")
    print(f"Bucket: {bucket}   Output dir: {out_dir}\n")

    success_count = 0
    for s3_key, local_name in files_to_download:
        local_path = out_dir / local_name
        print(f"  → {local_name}")
        try:
            s3.download_file(bucket, s3_key, str(local_path))
            print(f"     saved → {local_path.name}")
            success_count += 1
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                print(f"     WARNING: not found in S3 ({s3_key})")
            else:
                print(f"     ERROR: {e}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"     Unexpected error: {e}", file=sys.stderr)

    print("\n" + "=" * 70)
    print(f"Download complete — {success_count}/3 files saved to {out_dir}")
    print("=" * 70)
    return 0 if success_count > 0 else 1

if __name__ == "__main__":
    sys.exit(main())