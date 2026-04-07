#!/usr/bin/env python3
"""Create an AMI from a tagged EC2 instance.

Atomic steps:
  1. Find a running instance by Name tag.
  2. Create an AMI with project tags.
  3. Wait for the AMI to become available.
  4. Print the AMI ID.

Credentials are read from the project .env (AWS_ACCESS_KEY_ID_CLOUD,
AWS_SECRET_ACCESS_KEY_CLOUD, AWS_DEFAULT_REGION).

Usage:
    python tools/create-ami.py --tag cloud-task-base --ami-name base-gpu-2026-04-07

    # Check mode (Audit): report whether an AMI with the given name exists
    python tools/create-ami.py --ami-name base-gpu-2026-04-07 --check
"""

import argparse
import sys
import time

from _env import ec2_client
from loguru import logger


def find_running_instance(ec2, tag: str) -> dict:
    """Return the first running instance with the given Name tag."""
    resp = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": [tag]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ])
    for res in resp["Reservations"]:
        for inst in res["Instances"]:
            return inst
    return None


def create_ami(ec2, instance_id: str, ami_name: str, description: str) -> str:
    """Create an AMI from an instance. Returns the image ID."""
    resp = ec2.create_image(
        InstanceId=instance_id,
        Name=ami_name,
        Description=description,
        TagSpecifications=[{
            "ResourceType": rt,
            "Tags": [
                {"Key": "Name", "Value": ami_name},
                {"Key": "Project", "Value": "agentic-cloud-task"},
            ],
        } for rt in ("image", "snapshot")],
    )
    image_id = resp["ImageId"]
    logger.info("AMI creation started: {} ({})", ami_name, image_id)
    return image_id


def wait_for_ami(ec2, image_id: str, poll_interval: int = 15, max_wait: int = 600):
    """Poll until the AMI reaches 'available' state."""
    logger.info("Waiting for AMI {} to become available...", image_id)
    elapsed = 0
    while elapsed < max_wait:
        resp = ec2.describe_images(ImageIds=[image_id])
        state = resp["Images"][0]["State"]
        if state == "available":
            logger.info("AMI available: {}", image_id)
            return
        if state == "failed":
            reason = resp["Images"][0].get("StateReason", {}).get("Message", "unknown")
            raise RuntimeError(f"AMI {image_id} failed: {reason}")
        logger.debug("AMI state: {} ({}s elapsed)", state, elapsed)
        time.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f"AMI {image_id} not available after {max_wait}s")


def check_ami(ec2, ami_name: str) -> bool:
    """Report whether an AMI with the given name exists."""
    resp = ec2.describe_images(
        Owners=["self"],
        Filters=[{"Name": "name", "Values": [ami_name]}],
    )
    if resp["Images"]:
        img = resp["Images"][0]
        print(f"PASS: AMI {img['ImageId']} ({ami_name}) state={img['State']}")
        return True
    else:
        print(f"FAIL: no AMI named '{ami_name}'")
        return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Create an AMI from a tagged EC2 instance (or check for one).",
    )
    p.add_argument("--tag",
                   help="Name tag of the source instance (e.g. cloud-task-base)")
    p.add_argument("--ami-name", required=True,
                   help="Name for the AMI (e.g. base-gpu-2026-04-07)")
    p.add_argument("--description", default="",
                   help="AMI description")
    p.add_argument("--check", action="store_true",
                   help="Audit mode: check if an AMI with the given name exists")
    return p


def main():
    args = build_parser().parse_args()
    ec2 = ec2_client

    if args.check:
        ok = check_ami(ec2, args.ami_name)
        sys.exit(0 if ok else 1)

    if not args.tag:
        logger.error("--tag is required for AMI creation (omit only with --check)")
        sys.exit(1)

    inst = find_running_instance(ec2, args.tag)
    if not inst:
        logger.error("No running instance with tag '{}'", args.tag)
        sys.exit(1)

    instance_id = inst["InstanceId"]
    logger.info("Source instance: {} (tag={})", instance_id, args.tag)

    description = args.description or f"Baked from {args.tag} ({instance_id})"
    image_id = create_ami(ec2, instance_id, args.ami_name, description)
    wait_for_ami(ec2, image_id)

    print(f"ami_id={image_id}")


if __name__ == "__main__":
    main()
