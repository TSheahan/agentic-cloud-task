"""Project environment: credentials, paths, and AWS clients.

Loads .env and constructs clients on import. Other tools/scripts use:

    from _env import PROJECT_ROOT, ec2_client
    from _env import AWS_ACCESS_KEY_ID_CLOUD  # if raw keys needed
"""

import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

AWS_ACCESS_KEY_ID_CLOUD = os.environ["AWS_ACCESS_KEY_ID_CLOUD"]
AWS_SECRET_ACCESS_KEY_CLOUD = os.environ["AWS_SECRET_ACCESS_KEY_CLOUD"]
AWS_DEFAULT_REGION = os.environ["AWS_DEFAULT_REGION"]

ec2_client = boto3.client(
    "ec2",
    region_name=AWS_DEFAULT_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID_CLOUD,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY_CLOUD,
)


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
