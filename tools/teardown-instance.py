#!/usr/bin/env python3
"""Terminate tagged EC2 instances and clean up associated resources.

Atomic steps:
  1. Find running/pending/stopped instances with the given Name tag.
  2. Terminate them and wait for termination.
  3. Delete the security group (retry on DependencyViolation).
  4. Optionally remove the SSH config Host entry.

Credentials are read from the project .env (AWS_ACCESS_KEY_ID_CLOUD,
AWS_SECRET_ACCESS_KEY_CLOUD, AWS_DEFAULT_REGION).

Usage:
    python tools/teardown-instance.py --tag cloud-task-sara

    # Check mode (Audit): report whether any matching instances exist
    python tools/teardown-instance.py --tag cloud-task-sara --check
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

import boto3
from dotenv import load_dotenv
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

DEFAULT_SG_NAME = "cloud-task-sg"
SSH_CONFIG_PATH = Path.home() / ".ssh" / "config"


def get_ec2_client():
    return boto3.client(
        "ec2",
        region_name=os.environ["AWS_DEFAULT_REGION"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID_CLOUD"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY_CLOUD"],
    )


def find_tagged_instances(ec2, tag: str) -> list[str]:
    """Find instances with the given Name tag that aren't already terminated."""
    resp = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": [tag]},
        {"Name": "instance-state-name",
         "Values": ["running", "pending", "stopping", "stopped"]},
    ])
    return [
        inst["InstanceId"]
        for res in resp["Reservations"]
        for inst in res["Instances"]
    ]


def terminate_instances(ec2, instance_ids: list[str]):
    """Terminate instances and wait."""
    if not instance_ids:
        logger.info("No instances to terminate")
        return
    logger.info("Terminating: {}", instance_ids)
    ec2.terminate_instances(InstanceIds=instance_ids)
    waiter = ec2.get_waiter("instance_terminated")
    waiter.wait(
        InstanceIds=instance_ids,
        WaiterConfig={"Delay": 5, "MaxAttempts": 60},
    )
    logger.info("Instances terminated")


def delete_security_group(ec2, sg_name: str, retries: int = 3):
    """Delete SG by name, retrying on DependencyViolation."""
    resp = ec2.describe_security_groups(
        Filters=[{"Name": "group-name", "Values": [sg_name]}]
    )
    for sg in resp["SecurityGroups"]:
        for attempt in range(1, retries + 1):
            try:
                ec2.delete_security_group(GroupId=sg["GroupId"])
                logger.info("Security group deleted: {} ({})",
                            sg_name, sg["GroupId"])
                return
            except ec2.exceptions.ClientError as e:
                if "DependencyViolation" in str(e) and attempt < retries:
                    logger.debug("SG in use, retry {}/{}...", attempt, retries)
                    time.sleep(10)
                else:
                    logger.warning("Could not delete SG {}: {}", sg_name, e)
                    return


def remove_ssh_config_entry(host_alias: str):
    """Remove a Host block from ~/.ssh/config."""
    if not SSH_CONFIG_PATH.exists():
        return
    content = SSH_CONFIG_PATH.read_text()
    block_re = re.compile(
        rf"^\n?Host {re.escape(host_alias)}\s*\n([ \t]+\S.*\n)*",
        re.MULTILINE,
    )
    new_content = block_re.sub("", content)
    if new_content != content:
        SSH_CONFIG_PATH.write_text(new_content)
        logger.info("Removed SSH config entry for {}", host_alias)


def check_no_instances(ec2, tag: str) -> bool:
    """Audit: confirm no running instances with the tag exist."""
    ids = find_tagged_instances(ec2, tag)
    if ids:
        print(f"FAIL: {len(ids)} instance(s) still active with tag '{tag}': "
              + ", ".join(ids))
        return False
    else:
        print(f"PASS: no active instances with tag '{tag}'")
        return True


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Terminate tagged EC2 instances and clean up.",
    )
    p.add_argument("--tag", required=True,
                   help="Name tag of instances to terminate")
    p.add_argument("--sg-name", default=DEFAULT_SG_NAME)
    p.add_argument("--keep-sg", action="store_true",
                   help="Don't delete the security group")
    p.add_argument("--ssh-host-alias",
                   help="SSH config Host alias to remove (defaults to --tag)")
    p.add_argument("--no-ssh-config", action="store_true",
                   help="Skip removing SSH config entry")
    p.add_argument("--check", action="store_true",
                   help="Audit mode: check that no matching instances exist")
    return p


def main():
    args = build_parser().parse_args()
    ec2 = get_ec2_client()

    if args.check:
        ok = check_no_instances(ec2, args.tag)
        sys.exit(0 if ok else 1)

    instance_ids = find_tagged_instances(ec2, args.tag)
    terminate_instances(ec2, instance_ids)

    if not args.keep_sg:
        delete_security_group(ec2, args.sg_name)

    if not args.no_ssh_config:
        alias = args.ssh_host_alias or args.tag
        remove_ssh_config_entry(alias)

    logger.info("Teardown complete for tag '{}'", args.tag)


if __name__ == "__main__":
    main()
