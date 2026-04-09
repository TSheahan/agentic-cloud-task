#!/usr/bin/env python3
"""Ensure ECR repository ocr-docling-gpu exists with Project=agentic-cloud-task.

Uses .env credentials (same as other tools). Idempotent: creates or verifies tag.

If CreateRepository is denied on the IAM user, pass the orchestrator role from
cloud/cf-cloud-permission-roles.yaml (``agentic-cloud-task-orchestrator-role``)
via ``--assume-role`` so calls run with the role that carries AgenticCloud-ECR.

Usage:
    python tools/ensure-ecr-ocr-repo.py
    python tools/ensure-ecr-ocr-repo.py --assume-role arn:aws:iam::ACCOUNT:role/agentic-cloud-task-orchestrator-role
"""

import argparse
import sys

import boto3
import botocore.exceptions

from _env import AWS_DEFAULT_REGION, AWS_ACCESS_KEY_ID_CLOUD, AWS_SECRET_ACCESS_KEY_CLOUD

REPO_NAME = "ocr-docling-gpu"
PROJECT_TAG = {"Key": "Project", "Value": "agentic-cloud-task"}
ORCHESTRATOR_ROLE_NAME = "agentic-cloud-task-orchestrator-role"


def _ecr_client(assume_role_arn: str | None):
    base = dict(
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID_CLOUD,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY_CLOUD,
    )
    if not assume_role_arn:
        return boto3.client("ecr", **base)
    sts = boto3.client("sts", **base)
    out = sts.assume_role(
        RoleArn=assume_role_arn,
        RoleSessionName="ensure-ecr-ocr-repo",
    )
    c = out["Credentials"]
    return boto3.client(
        "ecr",
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"],
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--assume-role",
        metavar="ARN",
        help=f"STS assume-role ARN (e.g. ...:role/{ORCHESTRATOR_ROLE_NAME}) before ECR calls",
    )
    args = p.parse_args()
    ecr = _ecr_client(args.assume_role)
    try:
        r = ecr.create_repository(
            repositoryName=REPO_NAME,
            imageScanningConfiguration={"scanOnPush": True},
            tags=[PROJECT_TAG],
        )
        repo = r["repository"]
        print("CREATED", repo["repositoryUri"])
        return 0
    except botocore.exceptions.ClientError as e:
        code = e.response["Error"]["Code"]
        if code != "RepositoryAlreadyExistsException":
            raise

    resp = ecr.describe_repositories(repositoryNames=[REPO_NAME])
    repo = resp["repositories"][0]
    print("EXISTS", repo["repositoryUri"])
    arn = repo["repositoryArn"]
    tags = ecr.list_tags_for_resource(resourceArn=arn)
    tm = {t["Key"]: t["Value"] for t in tags.get("tags", [])}
    if tm.get("Project") != PROJECT_TAG["Value"]:
        ecr.tag_resource(resourceArn=arn, tags=[PROJECT_TAG])
        print("Applied tag Project=", PROJECT_TAG["Value"], sep="")
    else:
        print("Tag OK: Project=", PROJECT_TAG["Value"], sep="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
