"""Project environment: credentials, paths, and AWS clients.

Loads ``.env`` (``python-dotenv``) and exposes region + long-lived keys.

**Two principals**

- **IAM user** (``AWS_ACCESS_KEY_ID_CLOUD`` / ``AWS_SECRET_ACCESS_KEY_CLOUD``): what
  ``boto3_session_user()`` and the module-level ``ec2_client`` use. Often scoped to
  ``sts:AssumeRole`` into the orchestrator role plus a narrow **workstation** EC2
  policy on ``AgenticOrchestratorGroup`` (see ``cloud/cf-cloud-permission-roles.yaml``).
- **Orchestrator role** (``agentic-cloud-task-orchestrator-role``): carries Batch,
  ECR, broad EC2-Core, S3, etc. Tools and snippets need a session built via
  :func:`boto3_session` with ``assume_role_arn`` set so API calls are evaluated
  against the role.

**Assume role without repeating ``--assume-role``**

Set ``AGENTIC_ORCHESTRATOR_ROLE_ARN`` in ``.env`` to the full role ARN. Tools merge:
``--assume-role`` (CLI) overrides the env var; if both are unset, calls use the
user session only.

**Snippet pattern (orchestrator permissions)**

    from _env import boto3_session, resolved_assume_role_arn

    session = boto3_session(
        assume_role_arn=resolved_assume_role_arn(None),
        role_session_name="my-check",
    )
    ec2 = session.client("ec2")

**Snippet pattern (user-only, e.g. tagged instance lifecycle)**

    from _env import ec2_client
    ec2_client.describe_instances(InstanceIds=["i-…"])

Assumed credentials expire (default ~1 h). Long-running jobs should refresh or use
the user/instance role, not a stale module-level client from an old assume.
"""

from __future__ import annotations

import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

AWS_ACCESS_KEY_ID_CLOUD = os.environ["AWS_ACCESS_KEY_ID_CLOUD"]
AWS_SECRET_ACCESS_KEY_CLOUD = os.environ["AWS_SECRET_ACCESS_KEY_CLOUD"]
AWS_DEFAULT_REGION = os.environ["AWS_DEFAULT_REGION"]

ENV_ORCHESTRATOR_ROLE_ARN = "AGENTIC_ORCHESTRATOR_ROLE_ARN"


def _user_session_kwargs() -> dict:
    return dict(
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID_CLOUD,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY_CLOUD,
    )


def boto3_session_user() -> boto3.Session:
    """Session using ``.env`` IAM user credentials only (no ``AssumeRole``)."""
    return boto3.Session(**_user_session_kwargs())


def resolved_assume_role_arn(cli_assume_role: str | None) -> str | None:
    """Role ARN for tools: ``--assume-role`` wins, else ``AGENTIC_ORCHESTRATOR_ROLE_ARN``."""
    if cli_assume_role:
        return cli_assume_role.strip() or None
    return (os.environ.get(ENV_ORCHESTRATOR_ROLE_ARN) or "").strip() or None


def boto3_session(
    *,
    assume_role_arn: str | None = None,
    role_session_name: str = "agentic-cloud-task",
) -> boto3.Session:
    """User session if ``assume_role_arn`` is falsy; else ``sts:AssumeRole`` then session.

    ``role_session_name`` is visible in CloudTrail (max 64 chars; truncated here).
    """
    base = _user_session_kwargs()
    if not assume_role_arn:
        return boto3.Session(**base)
    name = role_session_name[:64] if role_session_name else "agentic-cloud-task"
    sts = boto3.client("sts", **base)
    out = sts.assume_role(RoleArn=assume_role_arn, RoleSessionName=name)
    c = out["Credentials"]
    return boto3.Session(
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"],
    )


ec2_client = boto3.client("ec2", **_user_session_kwargs())


def detect_default_vpc(ec2=None) -> tuple[str, list[str]]:
    """Return (vpc_id, [subnet_ids]) for the account's default VPC.

    Raises SystemExit if no default VPC exists.
    """
    ec2 = ec2 or ec2_client
    vpcs = ec2.describe_vpcs(
        Filters=[{"Name": "is-default", "Values": ["true"]}]
    ).get("Vpcs", [])
    if not vpcs:
        raise SystemExit("error: no default VPC found in this region")
    vpc_id = vpcs[0]["VpcId"]
    subs = ec2.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    ).get("Subnets", [])
    if not subs:
        raise SystemExit(f"error: default VPC {vpc_id} has no subnets")
    subnet_ids = [s["SubnetId"] for s in subs]
    return vpc_id, subnet_ids
