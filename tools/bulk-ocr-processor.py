#!/usr/bin/env python3
"""Bulk OCR Processor for scanning-spirit-papers batch.

Unified, resumable replacement for the three POC scripts (upload-local-ocr.py,
submit-ocr-batch-job.py, download-ocr-artifacts.py).

Features:
  • Recursively discovers every *.jpg (preserves full folder tree)
  • Uploads to S3 under new namespace: scanning-spirit-papers/inbox/
  • Submits one AWS Batch job per file (preserves folder structure in output)
  • Monitors jobs with live status updates
  • Downloads .md + .json artifacts right next to each original .jpg
  • Idempotent + resumable via local .ocr_state.json
  • Windows/PowerShell first-class (backslashes OK, clear progress)

New namespace (clean separation from poc-*):
  Inbox  → scanning-spirit-papers/inbox/<full-relative-path>.jpg
  Output → scanning-spirit-papers/processed/<full-relative-path>.md + .json

Success = every .jpg has a sibling .md and .json in the same folder.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import boto3
from botocore.exceptions import ClientError

from _env import boto3_session, resolved_assume_role_arn

# === NEW NAMESPACE FOR THIS BATCH ===
DEFAULT_INBOX_PREFIX = "scanning-spirit-papers/inbox/"
DEFAULT_OUTPUT_PREFIX = "scanning-spirit-papers/processed/"
DEFAULT_QUEUE_NAME = "ocr-docling-gpu-queue"
DEFAULT_JOB_DEF_NAME = "ocr-docling-gpu"
DEFAULT_LOG_GROUP = "/agentic-cloud-task/ocr-batch"
STATE_FILENAME = ".ocr_state.json"
ENV_BUCKET = "OCR_BUCKET"

POLL_INTERVAL_S = 20
TERMINAL_STATES = {"SUCCEEDED", "FAILED"}

def get_relative_posix(jpg_path: Path, source_dir: Path) -> str:
    """Return relative path using / (S3 style)"""
    rel = jpg_path.relative_to(source_dir)
    return str(rel).replace(os.sep, "/")

def load_state(source_dir: Path) -> Dict[str, Dict]:
    state_file = source_dir / STATE_FILENAME
    if state_file.exists():
        try:
            with open(state_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: could not read state file ({e}) – starting fresh")
    return {}

def save_state(source_dir: Path, state: Dict[str, Dict]):
    state_file = source_dir / STATE_FILENAME
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Warning: could not save state file ({e})")

def find_jpg_files(source_dir: Path) -> List[Path]:
    jpgs = list(source_dir.rglob("*.jpg"))   # removed duplicate *.JPG (Windows case-insensitive FS caused doubles)
    print(f"Found {len(jpgs)} .jpg file(s) under {source_dir}")
    return sorted(jpgs)

def upload_file(s3_client, bucket: str, local_path: Path, s3_key: str) -> bool:
    try:
        s3_client.upload_file(str(local_path), bucket, s3_key)
        print(f"  ✓ Uploaded {local_path.name}")
        return True
    except Exception as e:
        print(f"  ✗ Upload failed {local_path.name}: {e}")
        return False

def submit_ocr_job(batch_client, queue: str, job_def: str,
                   input_s3: str, output_s3: str, stem: str) -> str | None:
    job_name = f"ocr-spirit-{stem.replace('.', '-')}"[:128]
    try:
        resp = batch_client.submit_job(
            jobName=job_name,
            jobQueue=queue,
            jobDefinition=job_def,
            parameters={"inputS3": input_s3, "outputS3": output_s3},
        )
        job_id = resp["jobId"]
        print(f"  → Submitted {job_name} (jobId: {job_id})")
        return job_id
    except Exception as e:
        print(f"  ✗ Submit failed: {e}")
        return None

def poll_job(batch_client, job_id: str) -> dict:
    """Return final job dict once terminal"""
    print(f"    Monitoring {job_id}...", end="", flush=True)
    while True:
        resp = batch_client.describe_jobs(jobs=[job_id])
        job = resp["jobs"][0]
        status = job["status"]
        print(f" → {status}", end="", flush=True)
        if status in TERMINAL_STATES:
            print()
            return job
        time.sleep(POLL_INTERVAL_S)

def download_artifacts(s3_client, bucket: str, output_prefix: str,
                       relative_posix: str, target_dir: Path) -> bool:
    stem = Path(relative_posix).stem
    rel_no_ext = relative_posix.rsplit('.', 1)[0]  # forward-slash form

    # Backslash fallback: earlier runs on Windows submitted jobs with
    # str(Path(...).parent) which produces backslash separators on Windows,
    # so processor.py wrote outputs to S3 keys containing literal backslashes.
    # Reconstruct that key variant so we can recover those objects.
    rel_dir_win = str(Path(relative_posix).parent)   # 'delivery\\emails' on Windows
    rel_no_ext_win = (
        f"{rel_dir_win}/{stem}"
        if rel_dir_win != "."
        else stem
    )

    success = True
    for ext in (".md", ".json"):
        s3_key = f"{output_prefix}{rel_no_ext}{ext}"
        local_path = target_dir / f"{stem}{ext}"
        try:
            s3_client.download_file(bucket, s3_key, str(local_path))
            print(f"    ↓ {local_path.name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                # Try the backslash-path variant produced by the Windows submit bug
                s3_key_win = f"{output_prefix}{rel_no_ext_win}{ext}"
                if s3_key_win != s3_key:
                    try:
                        s3_client.download_file(bucket, s3_key_win, str(local_path))
                        print(f"    ↓ {local_path.name}  (backslash key)")
                        continue  # success for this ext
                    except ClientError:
                        pass  # fall through to failure report below
                print(f"    ⚠  {stem}{ext} not found in S3")
                print(f"       (tried: s3://{bucket}/{s3_key})")
                if s3_key_win != s3_key:
                    print(f"       (tried: s3://{bucket}/{s3_key_win})")
                success = False
            else:
                print(f"    ✗ Download error {stem}{ext}: {e}")
                success = False
    return success

def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--source-dir",
        default=r"D:\scanning-spirit-papers",
        help="Root folder containing the scans (default: D:\\scanning-spirit-papers)",
    )
    p.add_argument("--bucket", help=f"S3 bucket (falls back to ${ENV_BUCKET})")
    p.add_argument(
        "--inbox-prefix",
        default=DEFAULT_INBOX_PREFIX,
        help=f"Inbox prefix (default: {DEFAULT_INBOX_PREFIX})",
    )
    p.add_argument(
        "--output-prefix",
        default=DEFAULT_OUTPUT_PREFIX,
        help=f"Output prefix (default: {DEFAULT_OUTPUT_PREFIX})",
    )
    p.add_argument("--assume-role", metavar="ARN", help="STS assume-role ARN")
    p.add_argument("--queue", default=DEFAULT_QUEUE_NAME)
    p.add_argument("--job-definition", default=DEFAULT_JOB_DEF_NAME)
    p.add_argument("--log-group", default=DEFAULT_LOG_GROUP)

    # Run modes (mutually exclusive)
    mode_group = p.add_mutually_exclusive_group()
    mode_group.add_argument("--full", action="store_true", help="Full pipeline (default)")
    mode_group.add_argument("--upload-only", action="store_true")
    mode_group.add_argument("--submit-only", action="store_true")
    mode_group.add_argument("--monitor-only", action="store_true")
    mode_group.add_argument("--download-only", action="store_true")

    p.add_argument("--force", action="store_true", help="Force re-upload / re-submit")
    p.add_argument("--max-concurrent", type=int, default=40, help="Max Batch jobs to submit at once (default raised for this batch)")

    args = p.parse_args()

    source_dir = Path(args.source_dir).expanduser().resolve()
    if not source_dir.is_dir():
        print(f"Error: Source directory not found: {source_dir}", file=sys.stderr)
        return 1

    bucket = args.bucket or os.environ.get(ENV_BUCKET)
    if not bucket:
        print(f"Error: --bucket not supplied and ${ENV_BUCKET} env var missing.", file=sys.stderr)
        return 1

    # Normalise prefixes
    inbox_prefix = args.inbox_prefix if args.inbox_prefix.endswith("/") else args.inbox_prefix + "/"
    output_prefix = args.output_prefix if args.output_prefix.endswith("/") else args.output_prefix + "/"

    # Session (same pattern as all your existing tools)
    session = boto3_session(
        assume_role_arn=resolved_assume_role_arn(args.assume_role),
        role_session_name="bulk-ocr-processor",
    )
    s3_client = session.client("s3")
    batch_client = session.client("batch")

    state = load_state(source_dir)
    jpg_files = find_jpg_files(source_dir)

    if not jpg_files:
        print("No .jpg files found – nothing to do.")
        return 0

    # Decide what to run
    mode = "full"
    if args.upload_only:
        mode = "upload"
    elif args.submit_only:
        mode = "submit"
    elif args.monitor_only:
        mode = "monitor"
    elif args.download_only:
        mode = "download"

    print(f"\n=== BULK OCR PROCESSOR – {mode.upper()} MODE ===\n")
    print(f"Source     : {source_dir}")
    print(f"Inbox      : {inbox_prefix}")
    print(f"Output     : {output_prefix}")
    print(f"State file : {STATE_FILENAME}\n")

    # ── PHASE 1: UPLOAD ─────────────────────────────────────────────────────
    if mode in ("full", "upload"):
        print("=== PHASE 1: UPLOAD ===")
        for jpg in jpg_files:
            rel_posix = get_relative_posix(jpg, source_dir)
            s3_key = f"{inbox_prefix}{rel_posix}"

            entry = state.get(rel_posix, {})
            if entry.get("status") == "uploaded" and not args.force:
                continue

            print(f"  {rel_posix}")
            if upload_file(s3_client, bucket, jpg, s3_key):
                state[rel_posix] = {
                    "status": "uploaded",
                    "uploaded_at": datetime.now(timezone.utc).isoformat(),
                    "local_path": str(jpg),
                }
                save_state(source_dir, state)

    # ── PHASE 2: SUBMIT ─────────────────────────────────────────────────────
    if mode in ("full", "submit"):
        print("\n=== PHASE 2: SUBMIT ===")
        submitted = 0
        for jpg in jpg_files:
            rel_posix = get_relative_posix(jpg, source_dir)
            entry = state.get(rel_posix, {})
            if entry.get("status") != "uploaded" and not args.force:
                continue
            if submitted >= args.max_concurrent:
                print("  Max concurrent jobs reached – stop submit for now.")
                break

            stem = Path(rel_posix).stem
            input_s3 = f"s3://{bucket}/{inbox_prefix}{rel_posix}"

            # Output prefix includes the exact folder structure for this file.
            # Use as_posix() to avoid Windows backslashes in the S3 key.
            rel_dir = Path(rel_posix).parent
            output_s3 = (
                f"s3://{bucket}/{output_prefix}{rel_dir.as_posix()}/"
                if rel_dir.as_posix() != "." else
                f"s3://{bucket}/{output_prefix}"
            )

            job_id = submit_ocr_job(batch_client, args.queue, args.job_definition,
                                    input_s3, output_s3, stem)
            if job_id:
                state[rel_posix] = {
                    "status": "submitted",
                    "job_id": job_id,
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                    "local_path": str(jpg),
                }
                save_state(source_dir, state)
                submitted += 1

    # ── PHASE 3: MONITOR ────────────────────────────────────────────────────
    if mode in ("full", "monitor"):
        print("\n=== PHASE 3: MONITOR ===")
        pending = [ (k, v["job_id"]) for k, v in state.items() if v.get("status") == "submitted" ]
        if not pending:
            print("  No jobs in 'submitted' state.")
        else:
            for rel_posix, job_id in pending:
                print(f"  {rel_posix}")
                job = poll_job(batch_client, job_id)
                status = job["status"]
                state[rel_posix]["status"] = status.lower()
                state[rel_posix]["finished_at"] = datetime.now(timezone.utc).isoformat()
                if status == "FAILED":
                    state[rel_posix]["failure_reason"] = job.get("statusReason", "unknown")
                save_state(source_dir, state)

    # ── PHASE 4: DOWNLOAD ───────────────────────────────────────────────────
    if mode in ("full", "download"):
        print("\n=== PHASE 4: DOWNLOAD ===")
        for jpg in jpg_files:
            rel_posix = get_relative_posix(jpg, source_dir)
            entry = state.get(rel_posix, {})
            if entry.get("status") not in ("succeeded", "downloaded"):
                continue

            # Self-healing: if state says "downloaded" but local artifacts are
            # absent (e.g. a prior run marked success on a 404), re-attempt.
            md_path = jpg.parent / f"{jpg.stem}.md"
            json_path = jpg.parent / f"{jpg.stem}.json"
            if entry.get("status") == "downloaded" and md_path.exists() and json_path.exists():
                continue

            print(f"  {rel_posix}")
            if download_artifacts(s3_client, bucket, output_prefix, rel_posix, jpg.parent):
                state[rel_posix]["status"] = "downloaded"
                state[rel_posix]["downloaded_at"] = datetime.now(timezone.utc).isoformat()
                save_state(source_dir, state)

    print(f"\n=== FINISHED ===\nState saved to {STATE_FILENAME} in source folder.")
    return 0

if __name__ == "__main__":
    sys.exit(main())