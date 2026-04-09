#!/usr/bin/env python3
"""Submit an OCR job to AWS Batch and wait for completion.

Submits a job to the provisioned Batch queue using the job definition by name
(latest active revision). The two required Ref:: parameters —
``inputS3`` and ``outputS3`` — are passed as overrides.

After submission the tool polls ``describe_jobs`` until the job reaches a
terminal state:

- **SUCCEEDED** — fetches and prints the output ``.md`` from S3.
- **FAILED** — prints ``statusReason`` and fetches the last N container log
  events from CloudWatch (using the log stream name reported by Batch).

Requires the same credentials / assumed role that can call
``batch:SubmitJob``, ``batch:DescribeJobs``, ``s3:GetObject``, and
``logs:GetLogEvents``.

Examples:
    python tools/submit-ocr-batch-job.py \\
        s3://bucket/inbox/doc.pdf s3://bucket/processed/doc/

    python tools/submit-ocr-batch-job.py \\
        s3://bucket/inbox/scan.jpg s3://bucket/processed/scan/ \\
        --assume-role arn:aws:iam::ACCOUNT:role/agentic-cloud-task-orchestrator-role

    python tools/submit-ocr-batch-job.py \\
        s3://bucket/inbox/doc.pdf s3://bucket/processed/doc/ \\
        --log-group /agentic-cloud-task/ocr-batch
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

from _env import AWS_DEFAULT_REGION, AWS_ACCESS_KEY_ID_CLOUD, AWS_SECRET_ACCESS_KEY_CLOUD

ORCHESTRATOR_ROLE_NAME = "agentic-cloud-task-orchestrator-role"
DEFAULT_QUEUE_NAME = "ocr-docling-gpu-queue"
DEFAULT_JOB_DEF_NAME = "ocr-docling-gpu"
DEFAULT_LOG_GROUP = "/agentic-cloud-task/ocr-batch"

ENV_LOG_GROUP = "AGENTIC_BATCH_OCR_LOG_GROUP"
ENV_CF_STACK = "AGENTIC_BATCH_OCR_CF_STACK_NAME"

POLL_INTERVAL_S = 15
TERMINAL_STATES = {"SUCCEEDED", "FAILED"}


def _session(assume_role_arn: str | None) -> boto3.Session:
    base = dict(
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID_CLOUD,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY_CLOUD,
    )
    if not assume_role_arn:
        return boto3.Session(region_name=AWS_DEFAULT_REGION, **base)
    sts = boto3.client("sts", **base)
    out = sts.assume_role(
        RoleArn=assume_role_arn,
        RoleSessionName="submit-ocr-batch-job",
    )
    c = out["Credentials"]
    return boto3.Session(
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"],
    )


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    path = uri.replace("s3://", "", 1)
    bucket, _, key = path.partition("/")
    return bucket, key


def _submit(batch, *, queue: str, job_def: str, input_s3: str, output_s3: str) -> str:
    stem = input_s3.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    job_name = f"ocr-{stem}"[:128]
    resp = batch.submit_job(
        jobName=job_name,
        jobQueue=queue,
        jobDefinition=job_def,
        parameters={"inputS3": input_s3, "outputS3": output_s3},
    )
    job_id = resp["jobId"]
    print(f"Submitted job {job_id} ({job_name})")
    return job_id


def _wait(batch, job_id: str) -> dict:
    prev_status = None
    while True:
        resp = batch.describe_jobs(jobs=[job_id])
        job = resp["jobs"][0]
        status = job["status"]
        if status != prev_status:
            reason = job.get("statusReason", "")
            suffix = f" — {reason}" if reason else ""
            print(f"  [{status}]{suffix}")
            prev_status = status
        if status in TERMINAL_STATES:
            return job
        time.sleep(POLL_INTERVAL_S)


def _fetch_md_from_s3(session: boto3.Session, output_s3: str, input_s3: str) -> None:
    """Download and print the .md output artifact."""
    bucket, prefix = _parse_s3_uri(output_s3)
    if not prefix.endswith("/"):
        prefix += "/"
    stem = input_s3.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    key = f"{prefix}{stem}.md"

    s3 = session.client("s3")
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as e:
        print(f"Warning: could not fetch s3://{bucket}/{key}: {e}", file=sys.stderr)
        return
    body = resp["Body"].read().decode("utf-8", errors="replace")
    print(f"\n{'=' * 60}")
    print(f"Output: s3://{bucket}/{key}")
    print(f"{'=' * 60}\n")
    print(body)


def _fetch_logs(session: boto3.Session, job: dict, log_group: str, tail: int) -> None:
    """Fetch the last `tail` log events for the job's container."""
    container = job.get("container", {})
    stream = container.get("logStreamName")
    if not stream:
        print("No log stream name available for this job.", file=sys.stderr)
        return

    logs = session.client("logs")
    try:
        resp = logs.get_log_events(
            logGroupName=log_group,
            logStreamName=stream,
            startFromHead=False,
            limit=tail,
        )
    except ClientError as e:
        print(f"Warning: could not fetch logs from {log_group}/{stream}: {e}", file=sys.stderr)
        return

    events = resp.get("events", [])
    if not events:
        print(f"(no log events in {log_group}/{stream})")
        return

    print(f"\n{'=' * 60}")
    print(f"Logs: {log_group}/{stream} (last {len(events)} events)")
    print(f"{'=' * 60}\n")
    for ev in events:
        print(ev.get("message", "").rstrip())


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("input_s3", help="S3 URI of input file (e.g. s3://bucket/inbox/doc.pdf)")
    p.add_argument("output_s3", help="S3 URI prefix for outputs (e.g. s3://bucket/processed/doc/)")
    p.add_argument(
        "--assume-role",
        metavar="ARN",
        help=f"STS assume-role ARN (e.g. ...:role/{ORCHESTRATOR_ROLE_NAME})",
    )
    p.add_argument("--queue", default=DEFAULT_QUEUE_NAME, help=f"Job queue name (default: {DEFAULT_QUEUE_NAME})")
    p.add_argument("--job-definition", default=DEFAULT_JOB_DEF_NAME, help=f"Job definition name (default: {DEFAULT_JOB_DEF_NAME})")
    p.add_argument(
        "--log-group",
        help=f"CloudWatch log group for failure diagnostics (or {ENV_LOG_GROUP}; default: {DEFAULT_LOG_GROUP})",
    )
    p.add_argument("--log-tail", type=int, default=50, help="Number of log events to fetch on failure (default: 50)")
    args = p.parse_args()

    session = _session(args.assume_role)
    batch = session.client("batch")

    job_id = _submit(
        batch,
        queue=args.queue,
        job_def=args.job_definition,
        input_s3=args.input_s3,
        output_s3=args.output_s3,
    )

    job = _wait(batch, job_id)
    status = job["status"]

    if status == "SUCCEEDED":
        _fetch_md_from_s3(session, args.output_s3, args.input_s3)
        return 0

    # FAILED
    reason = job.get("statusReason", "(no reason)")
    container = job.get("container", {})
    exit_code = container.get("exitCode")
    print(f"\nJob FAILED: {reason}", file=sys.stderr)
    if exit_code is not None:
        print(f"Container exit code: {exit_code}", file=sys.stderr)

    log_group = (
        (args.log_group or "").strip()
        or os.environ.get(ENV_LOG_GROUP, "").strip()
        or DEFAULT_LOG_GROUP
    )
    _fetch_logs(session, job, log_group, args.log_tail)
    return 1


if __name__ == "__main__":
    sys.exit(main())
