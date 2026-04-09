#!/usr/bin/env python3
"""Provision a minimal AWS Batch stack for OCR (GPU, scale-to-zero).

Creates (idempotent where possible):
  - Managed EC2 compute environment: minvCpus=0, desiredvCpus=0, maxvCpus caps workers
  - Job queue bound to that environment
  - Container job definition: ECR image, 1 GPU / 4 vCPU / 16 GiB, S3 argv via Ref:: parameters

**Slow-moving IAM + worker security group** live in CloudFormation
[`cloud/cf-batch-ocr.yaml`](../cloud/cf-batch-ocr.yaml) (deploy with ``CAPABILITY_NAMED_IAM``).

**Dependency resolution** for security group + IAM ARNs (not subnets): **CLI flags** beat **environment
variables**, which beat **stack outputs** when you pass ``--stack-name`` (or
``AGENTIC_BATCH_OCR_CF_STACK_NAME``). That reads ``DescribeStacks`` and maps
``WorkerSecurityGroupId``, ``BatchServiceRoleArn``, ``EcsExecutionRoleArn``, ``JobRoleArn``,
``InstanceProfileArn``. You can still export those outputs as env vars instead if you prefer.

**Networking / security posture (default intent):** Batch workers are **not** SSH hosts. **No inbound**
on the worker security group from this template; **egress is open** so the host can reach **ECR**,
**S3**, and other AWS APIs without designing a per-endpoint matrix. **Application data** is only **S3**
in ``processor.py``; instances are ephemeral. **Subnets** are still a parameter (VPC layout): use the
same private subnets you would use for internal workers; ensure a route to the internet or VPC
endpoints so **image pull** succeeds.

**Environment variables** (optional defaults for flags of the same meaning):

- ``AGENTIC_BATCH_OCR_WORKER_SUBNETS`` — comma-separated subnet IDs
- ``AGENTIC_BATCH_OCR_WORKER_SECURITY_GROUP_ID`` — single SG (from ``cf-batch-ocr`` output)
- ``AGENTIC_BATCH_OCR_INSTANCE_PROFILE_ARN``
- ``AGENTIC_BATCH_OCR_SERVICE_ROLE_ARN`` (Batch service role)
- ``AGENTIC_BATCH_OCR_EXECUTION_ROLE_ARN`` (ECS task execution)
- ``AGENTIC_BATCH_OCR_JOB_ROLE_ARN`` (S3 in-container)

If ``batch:*`` / ``ecr:*`` are only on the orchestrator role, pass ``--assume-role`` (same pattern as
``ensure-ecr-ocr-repo.py``). Using ``--stack-name`` additionally requires
``cloudformation:DescribeStacks`` on that stack (or keep using copied env vars and omit ``--stack-name``).

Examples:
    # After deploying cloud/cf-batch-ocr.yaml (simplest: pull outputs from the stack):
    python tools/provision-ocr-batch.py --stack-name agentic-batch-ocr --subnets subnet-aaa,subnet-bbb

    # Or export stack outputs into env vars, then:
    python tools/provision-ocr-batch.py --subnets subnet-aaa,subnet-bbb

    python tools/provision-ocr-batch.py \\
        --subnets subnet-aaa,subnet-bbb \\
        --security-group-ids sg-ccc \\
        --instance-profile-arn arn:aws:iam::ACCOUNT:instance-profile/... \\
        --batch-service-role-arn arn:aws:iam::ACCOUNT:role/... \\
        --execution-role-arn arn:aws:iam::ACCOUNT:role/... \\
        --job-role-arn arn:aws:iam::ACCOUNT:role/...

    python tools/provision-ocr-batch.py ... --image ACCOUNT.dkr.ecr.REGION.amazonaws.com/ocr-docling-gpu@sha256:...
"""

from __future__ import annotations

import argparse
import os
import sys

import boto3
from botocore.exceptions import ClientError

from _env import AWS_DEFAULT_REGION, AWS_ACCESS_KEY_ID_CLOUD, AWS_SECRET_ACCESS_KEY_CLOUD

PROJECT_TAG_KEY = "Project"
PROJECT_TAG_VALUE = "agentic-cloud-task"
ORCHESTRATOR_ROLE_NAME = "agentic-cloud-task-orchestrator-role"

ENV_WORKER_SUBNETS = "AGENTIC_BATCH_OCR_WORKER_SUBNETS"
ENV_WORKER_SG = "AGENTIC_BATCH_OCR_WORKER_SECURITY_GROUP_ID"
ENV_INSTANCE_PROFILE = "AGENTIC_BATCH_OCR_INSTANCE_PROFILE_ARN"
ENV_SERVICE_ROLE = "AGENTIC_BATCH_OCR_SERVICE_ROLE_ARN"
ENV_EXECUTION_ROLE = "AGENTIC_BATCH_OCR_EXECUTION_ROLE_ARN"
ENV_JOB_ROLE = "AGENTIC_BATCH_OCR_JOB_ROLE_ARN"
ENV_CF_STACK = "AGENTIC_BATCH_OCR_CF_STACK_NAME"

# Must match Output keys in cloud/cf-batch-ocr.yaml
OUT_WORKER_SG = "WorkerSecurityGroupId"
OUT_BATCH_SERVICE = "BatchServiceRoleArn"
OUT_ECS_EXEC = "EcsExecutionRoleArn"
OUT_JOB = "JobRoleArn"
OUT_INSTANCE_PROFILE = "InstanceProfileArn"

DEFAULT_CE_NAME = "ocr-docling-gpu-ce"
DEFAULT_QUEUE_NAME = "ocr-docling-gpu-queue"
DEFAULT_JOB_DEF_NAME = "ocr-docling-gpu"
DEFAULT_REPO = "ocr-docling-gpu"


def _session(assume_role_arn: str | None):
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
        RoleSessionName="provision-ocr-batch",
    )
    c = out["Credentials"]
    return boto3.Session(
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"],
    )


def _batch_tags() -> dict[str, str]:
    return {PROJECT_TAG_KEY: PROJECT_TAG_VALUE}


def _from_cli_or_env(cli: str | None, env_key: str, flag: str) -> str:
    v = (cli or "").strip() or os.environ.get(env_key, "").strip()
    if not v:
        sys.exit(f"error: pass {flag} or set environment variable {env_key}")
    return v


def _resolve_from_stack_or_env(
    cli: str | None,
    env_key: str,
    flag: str,
    *,
    stack_outputs: dict[str, str] | None,
    output_key: str,
) -> str:
    if (cli or "").strip():
        return (cli or "").strip()
    e = os.environ.get(env_key, "").strip()
    if e:
        return e
    if stack_outputs:
        v = (stack_outputs.get(output_key) or "").strip()
        if v:
            return v
    sys.exit(
        f"error: pass {flag}, set {env_key}, or use --stack-name / {ENV_CF_STACK} "
        f"(CloudFormation output {output_key!r})"
    )


def _load_cf_stack_outputs(session: boto3.Session, stack_name: str) -> dict[str, str]:
    cfn = session.client("cloudformation")
    try:
        resp = cfn.describe_stacks(StackName=stack_name)
    except ClientError as e:
        sys.exit(f"error: DescribeStacks({stack_name!r}) failed: {e}")
    stacks = resp.get("Stacks") or []
    if not stacks:
        sys.exit(f"error: no CloudFormation stack named {stack_name!r}")
    outs = stacks[0].get("Outputs") or []
    return {o["OutputKey"]: o["OutputValue"] for o in outs}


def _ensure_compute_env(
    batch,
    *,
    name: str,
    service_role_arn: str,
    instance_profile_arn: str,
    subnets: list[str],
    security_group_ids: list[str],
    instance_types: list[str],
    min_vcpus: int,
    max_vcpus: int,
    desired_vcpus: int,
    use_spot: bool,
    spot_fleet_role_arn: str | None,
) -> str:
    resp = batch.describe_compute_environments(computeEnvironments=[name])
    envs = resp.get("computeEnvironments", [])
    if envs:
        st = envs[0].get("status")
        if st == "INVALID":
            sys.exit(
                f"error: compute environment {name!r} is INVALID; fix or delete it in AWS, then re-run"
            )
        if st == "DELETED":
            sys.exit(
                f"error: compute environment {name!r} is DELETED; wait for teardown or use a new --compute-env-name"
            )
        if st in ("CREATING", "UPDATING", "DELETING", "VALID"):
            arn = envs[0]["computeEnvironmentArn"]
            print("Compute environment exists:", arn, f"({st})")
            return arn
        sys.exit(f"error: compute environment {name!r} has unexpected status {st!r}")

    resources: dict = {
        "type": "SPOT" if use_spot else "EC2",
        "minvCpus": min_vcpus,
        "maxvCpus": max_vcpus,
        "desiredvCpus": desired_vcpus,
        "instanceTypes": instance_types,
        "subnets": subnets,
        "securityGroupIds": security_group_ids,
        "instanceRole": instance_profile_arn,
        "tags": _batch_tags(),
    }
    if use_spot:
        if not spot_fleet_role_arn:
            sys.exit("error: --spot requires --spot-fleet-role-arn")
        resources["spotIamFleetRole"] = spot_fleet_role_arn
        resources["allocationStrategy"] = "SPOT_CAPACITY_OPTIMIZED"
    else:
        resources["allocationStrategy"] = "BEST_FIT_PROGRESSIVE"

    batch.create_compute_environment(
        computeEnvironmentName=name,
        type="MANAGED",
        state="ENABLED",
        computeResources=resources,
        serviceRole=service_role_arn,
        tags=_batch_tags(),
    )
    arn = batch.describe_compute_environments(computeEnvironments=[name])[
        "computeEnvironments"
    ][0]["computeEnvironmentArn"]
    print("Created compute environment:", arn)
    return arn


def _ensure_job_queue(batch, *, name: str, compute_env_order: list[dict]) -> str:
    resp = batch.describe_job_queues(jobQueues=[name])
    queues = resp.get("jobQueues", [])
    if queues:
        arn = queues[0]["jobQueueArn"]
        print("Job queue exists:", arn)
        return arn

    batch.create_job_queue(
        jobQueueName=name,
        state="ENABLED",
        priority=1,
        computeEnvironmentOrder=compute_env_order,
        tags=_batch_tags(),
    )
    arn = batch.describe_job_queues(jobQueues=[name])["jobQueues"][0]["jobQueueArn"]
    print("Created job queue:", arn)
    return arn


def _register_job_definition(
    batch,
    *,
    name: str,
    image: str,
    job_role_arn: str,
    execution_role_arn: str,
) -> str:
    resp = batch.register_job_definition(
        jobDefinitionName=name,
        type="container",
        platformCapabilities=["EC2"],
        parameters={
            "inputS3": "s3://your-bucket/path/to/input.pdf",
            "outputS3": "s3://your-bucket/path/to/output/prefix/",
        },
        containerProperties={
            "image": image,
            "resourceRequirements": [
                {"type": "GPU", "value": "1"},
                {"type": "VCPU", "value": "4"},
                {"type": "MEMORY", "value": "16384"},
            ],
            "jobRoleArn": job_role_arn,
            "executionRoleArn": execution_role_arn,
            "command": ["Ref::inputS3", "Ref::outputS3"],
        },
        tags=_batch_tags(),
    )
    rev = resp["revision"]
    arn = resp["jobDefinitionArn"]
    print("Registered job definition:", arn, "(revision", str(rev) + ")")
    return arn


def _default_image(session: boto3.Session) -> str:
    sts = session.client("sts")
    account = sts.get_caller_identity()["Account"]
    return (
        f"{account}.dkr.ecr.{AWS_DEFAULT_REGION}.amazonaws.com/"
        f"{DEFAULT_REPO}:latest"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--assume-role",
        metavar="ARN",
        help=f"STS assume-role ARN (e.g. ...:role/{ORCHESTRATOR_ROLE_NAME})",
    )
    p.add_argument("--compute-env-name", default=DEFAULT_CE_NAME)
    p.add_argument("--queue-name", default=DEFAULT_QUEUE_NAME)
    p.add_argument("--job-definition-name", default=DEFAULT_JOB_DEF_NAME)
    p.add_argument(
        "--stack-name",
        metavar="NAME",
        help=f"cf-batch-ocr stack: read SG + IAM ARNs from Outputs (or {ENV_CF_STACK})",
    )
    p.add_argument(
        "--subnets",
        help=f"Comma-separated subnet IDs (or {ENV_WORKER_SUBNETS})",
    )
    p.add_argument(
        "--security-group-ids",
        help=f"Comma-separated security group IDs (or {ENV_WORKER_SG}; else stack output {OUT_WORKER_SG})",
    )
    p.add_argument(
        "--instance-profile-arn",
        help=f"Instance profile ARN (or {ENV_INSTANCE_PROFILE}; else {OUT_INSTANCE_PROFILE})",
    )
    p.add_argument(
        "--batch-service-role-arn",
        help=f"Batch service role ARN (or {ENV_SERVICE_ROLE}; else {OUT_BATCH_SERVICE})",
    )
    p.add_argument(
        "--execution-role-arn",
        help=f"ECS task execution role ARN (or {ENV_EXECUTION_ROLE}; else {OUT_ECS_EXEC})",
    )
    p.add_argument(
        "--job-role-arn",
        help=f"Job role ARN for processor.py S3 access (or {ENV_JOB_ROLE}; else {OUT_JOB})",
    )
    p.add_argument(
        "--image",
        help="ECR image URI (default: <account>.dkr.ecr.<region>.amazonaws.com/ocr-docling-gpu:latest)",
    )
    p.add_argument(
        "--min-vcpus",
        type=int,
        default=0,
        help="Minimum vCPUs (0 = scale to zero when idle)",
    )
    p.add_argument(
        "--max-vcpus",
        type=int,
        default=4,
        help="Maximum vCPUs (4 = one g4dn.xlarge)",
    )
    p.add_argument(
        "--desired-vcpus",
        type=int,
        default=0,
        help="Desired vCPUs at steady state (keep 0 for idle)",
    )
    p.add_argument(
        "--instance-types",
        default="g4dn.xlarge",
        help="Comma-separated instance types",
    )
    p.add_argument(
        "--spot",
        action="store_true",
        help="Use SPOT instead of on-demand EC2 (requires --spot-fleet-role-arn)",
    )
    p.add_argument(
        "--spot-fleet-role-arn",
        help="IAM role for Spot Fleet (required with --spot)",
    )
    args = p.parse_args()

    if args.min_vcpus < 0 or args.desired_vcpus < 0 or args.max_vcpus < 1:
        sys.exit("error: invalid vCPU bounds")
    if args.desired_vcpus > args.max_vcpus or args.min_vcpus > args.max_vcpus:
        sys.exit("error: min/desired vCPUs must not exceed max_vcpus")

    subnets_raw = _from_cli_or_env(args.subnets, ENV_WORKER_SUBNETS, "--subnets")

    session = _session(args.assume_role)
    stack_name = (args.stack_name or "").strip() or os.environ.get(ENV_CF_STACK, "").strip()
    stack_outputs = _load_cf_stack_outputs(session, stack_name) if stack_name else None
    if stack_outputs:
        print("Using CloudFormation outputs from stack:", stack_name)

    sg_raw = _resolve_from_stack_or_env(
        args.security_group_ids,
        ENV_WORKER_SG,
        "--security-group-ids",
        stack_outputs=stack_outputs,
        output_key=OUT_WORKER_SG,
    )
    instance_profile_arn = _resolve_from_stack_or_env(
        args.instance_profile_arn,
        ENV_INSTANCE_PROFILE,
        "--instance-profile-arn",
        stack_outputs=stack_outputs,
        output_key=OUT_INSTANCE_PROFILE,
    )
    batch_service_role_arn = _resolve_from_stack_or_env(
        args.batch_service_role_arn,
        ENV_SERVICE_ROLE,
        "--batch-service-role-arn",
        stack_outputs=stack_outputs,
        output_key=OUT_BATCH_SERVICE,
    )
    execution_role_arn = _resolve_from_stack_or_env(
        args.execution_role_arn,
        ENV_EXECUTION_ROLE,
        "--execution-role-arn",
        stack_outputs=stack_outputs,
        output_key=OUT_ECS_EXEC,
    )
    job_role_arn = _resolve_from_stack_or_env(
        args.job_role_arn,
        ENV_JOB_ROLE,
        "--job-role-arn",
        stack_outputs=stack_outputs,
        output_key=OUT_JOB,
    )
    batch = session.client("batch")
    image = args.image or _default_image(session)
    subnets = [s.strip() for s in subnets_raw.split(",") if s.strip()]
    sgs = [s.strip() for s in sg_raw.split(",") if s.strip()]
    inst_types = [s.strip() for s in args.instance_types.split(",") if s.strip()]

    ce_arn = _ensure_compute_env(
        batch,
        name=args.compute_env_name,
        service_role_arn=batch_service_role_arn,
        instance_profile_arn=instance_profile_arn,
        subnets=subnets,
        security_group_ids=sgs,
        instance_types=inst_types,
        min_vcpus=args.min_vcpus,
        max_vcpus=args.max_vcpus,
        desired_vcpus=args.desired_vcpus,
        use_spot=args.spot,
        spot_fleet_role_arn=args.spot_fleet_role_arn,
    )

    _ensure_job_queue(
        batch,
        name=args.queue_name,
        computeEnvironmentOrder=[
            {"order": 1, "computeEnvironment": ce_arn},
        ],
    )

    _register_job_definition(
        batch,
        name=args.job_definition_name,
        image=image,
        job_role_arn=job_role_arn,
        execution_role_arn=execution_role_arn,
    )

    print("Done. Submit jobs with jobQueue=", args.queue_name, "jobDefinition=", args.job_definition_name, sep="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
