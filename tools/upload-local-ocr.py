#!/usr/bin/env python3
"""Upload a local file to S3 inbox and prepare (or auto-submit) an OCR Batch job.

Companion tool for submit-ocr-batch-job.py — designed for PowerShell users doing
POC runs.

- Takes a local PDF/image
- Uploads it (preserving original filename)
- Prints clean input_s3 / output_s3 values (flat output prefix by default)
- Prints a ready-to-copy PowerShell command
- --auto-submit (default: off) will launch the submit script for you

Defaults are POC-safe and will not collide with later automated pipelines:
  inbox  → poc-inbox/
  output → poc-processed/
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from _env import boto3_session, resolved_assume_role_arn

DEFAULT_INBOX_PREFIX = "poc-inbox/"
DEFAULT_OUTPUT_PREFIX = "poc-processed/"
ENV_BUCKET = "OCR_BUCKET"

def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("local_file", help="Local path to PDF or image")
    p.add_argument(
        "--bucket",
        help=f"S3 bucket name (falls back to ${ENV_BUCKET} environment variable)",
    )
    p.add_argument(
        "--inbox-prefix",
        default=DEFAULT_INBOX_PREFIX,
        help=f"Inbox prefix for the uploaded file (default: {DEFAULT_INBOX_PREFIX})",
    )
    p.add_argument(
        "--output-prefix",
        default=DEFAULT_OUTPUT_PREFIX,
        help=f"Output prefix for OCR artifacts (flat by default: {DEFAULT_OUTPUT_PREFIX})",
    )
    p.add_argument(
        "--assume-role",
        metavar="ARN",
        help="STS assume-role ARN (passed through to submit-ocr-batch-job.py)",
    )
    p.add_argument(
        "--auto-submit",
        action="store_true",
        default=False,
        help="Automatically run submit-ocr-batch-job.py after successful upload (default: off)",
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

    # Validate and expand local file
    local_path = Path(args.local_file).expanduser().resolve()
    if not local_path.is_file():
        print(f"Error: File not found: {local_path}", file=sys.stderr)
        return 1

    # Normalise prefixes (always end with /)
    inbox_prefix = args.inbox_prefix
    if not inbox_prefix.endswith("/"):
        inbox_prefix += "/"
    output_prefix = args.output_prefix
    if not output_prefix.endswith("/"):
        output_prefix += "/"

    # Build S3 keys/URIs
    filename = local_path.name
    input_key = f"{inbox_prefix}{filename}"
    input_s3 = f"s3://{bucket}/{input_key}"
    output_s3 = f"s3://{bucket}/{output_prefix}"

    # Create session (exactly the same pattern used by submit-ocr-batch-job.py)
    session = boto3_session(
        assume_role_arn=resolved_assume_role_arn(args.assume_role),
        role_session_name="submit-local-ocr",
    )

    # Upload
    s3 = session.client("s3")
    print(f"Uploading {filename} → {input_s3}")
    try:
        s3.upload_file(str(local_path), bucket, input_key)
        print("✓ Upload complete")
    except ClientError as e:
        print(f"Upload failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"Unexpected upload error: {e}", file=sys.stderr)
        return 1

    # Summary
    print("\n" + "=" * 70)
    print("OCR Batch Job Ready")
    print("=" * 70)
    print(f"Input  S3 URI : {input_s3}")
    print(f"Output prefix : {output_s3}")
    print()

    # PowerShell-ready multiline command (uses ` for line continuation)
    print("Copy-paste ready command (PowerShell):")
    print()
    print('python tools\\submit-ocr-batch-job.py `')
    print(f'  "{input_s3}" `')
    print(f'  "{output_s3}" `')
    if args.assume_role:
        print(f'  --assume-role "{args.assume_role}"')
    print()

    # Auto-submit if requested
    if args.auto_submit:
        print("=" * 70)
        print("Auto-submitting job now...")
        print("=" * 70)
        try:
            cmd = [
                sys.executable,
                str(Path(__file__).parent / "submit-ocr-batch-job.py"),
                input_s3,
                output_s3,
            ]
            if args.assume_role:
                cmd.extend(["--assume-role", args.assume_role])

            result = subprocess.run(cmd, check=True)
            return result.returncode
        except subprocess.CalledProcessError as e:
            return e.returncode
        except FileNotFoundError:
            print("Error: Could not locate submit-ocr-batch-job.py", file=sys.stderr)
            return 1

    print("Tip: add --auto-submit next time if you want to run the job immediately.")
    return 0

if __name__ == "__main__":
    sys.exit(main())