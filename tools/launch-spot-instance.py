#!/usr/bin/env python3
"""Launch an EC2 instance (spot or on-demand) and return its public IP.

Atomic steps:
  1. Ensure a security group exists (create-if-absent, SSH inbound).
  2. Request an instance with the given parameters.
  3. Wait for the instance to reach 'running'.
  4. Retrieve and print the public IP.
  5. Optionally write/update an SSH config Host entry.

Credentials are read from the project .env (AWS_ACCESS_KEY_ID_CLOUD,
AWS_SECRET_ACCESS_KEY_CLOUD, AWS_DEFAULT_REGION).

Usage:
    python tools/launch-spot-instance.py \\
        --ami <ami-id-from-cloud-resources-md> \\
        --instance-type g4dn.xlarge \\
        --volume-gb 40 \\
        --tag cloud-task-sara

    # Stop (not terminate) on guest shutdown; root EBS still deletes on terminate (default)
    python tools/launch-spot-instance.py \\
        --ami <ami-id> --tag cloud-task-sara \\
        --instance-initiated-shutdown-behavior stop

    # Optional: retain root EBS after instance termination (orphan volume until you delete it)
    python tools/launch-spot-instance.py \\
        --ami <ami-id> --tag cloud-task-sara --persist-root-volume

    # Check mode (Audit): report whether a matching instance is running
    python tools/launch-spot-instance.py --tag cloud-task-sara --check
"""

import argparse
import re
import sys
from pathlib import Path

from _env import ec2_client
from loguru import logger

DEFAULT_KEY_NAME = "cloud-task"
DEFAULT_SG_NAME = "cloud-task-sg"
DEFAULT_SPOT_MAX_PRICE = "0.50"
SSH_CONFIG_PATH = Path.home() / ".ssh" / "config"


# -- Security group --------------------------------------------------------

def ensure_security_group(ec2, sg_name: str) -> str:
    """Return the group ID of sg_name, creating it if absent."""
    resp = ec2.describe_security_groups(
        Filters=[{"Name": "group-name", "Values": [sg_name]}]
    )
    if resp["SecurityGroups"]:
        sg_id = resp["SecurityGroups"][0]["GroupId"]
        logger.info("Security group exists: {} ({})", sg_name, sg_id)
        return sg_id

    resp = ec2.create_security_group(
        GroupName=sg_name,
        Description="SSH access for agentic-cloud-task instances",
        TagSpecifications=[{
            "ResourceType": "security-group",
            "Tags": [{"Key": "Project", "Value": "agentic-cloud-task"}],
        }],
    )
    sg_id = resp["GroupId"]
    ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            "IpProtocol": "tcp",
            "FromPort": 22,
            "ToPort": 22,
            "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH"}],
        }],
    )
    logger.info("Security group created: {} ({})", sg_name, sg_id)
    return sg_id


# -- Instance launch -------------------------------------------------------

def launch_instance(
    ec2,
    ami: str,
    instance_type: str,
    volume_gb: int,
    tag: str,
    key_name: str,
    sg_id: str,
    spot_max_price: str,
    *,
    market_type: str,
    delete_root_on_termination: bool,
    instance_initiated_shutdown_behavior: str,
    spot_interruption_behavior: str,
) -> str:
    """Launch an EC2 instance. Returns instance ID."""
    bdm = [{
        "DeviceName": "/dev/sda1",
        "Ebs": {
            "VolumeSize": volume_gb,
            "VolumeType": "gp3",
            "DeleteOnTermination": delete_root_on_termination,
        },
    }]
    tags = [
        {
            "ResourceType": rt,
            "Tags": [
                {"Key": "Name", "Value": tag},
                {"Key": "Project", "Value": "agentic-cloud-task"},
            ],
        }
        for rt in ("instance", "volume", "network-interface")
    ]
    kwargs = {
        "ImageId": ami,
        "InstanceType": instance_type,
        "KeyName": key_name,
        "SecurityGroupIds": [sg_id],
        "MinCount": 1,
        "MaxCount": 1,
        "BlockDeviceMappings": bdm,
        "InstanceInitiatedShutdownBehavior": instance_initiated_shutdown_behavior,
        "TagSpecifications": tags,
    }
    if market_type == "spot":
        kwargs["InstanceMarketOptions"] = {
            "MarketType": "spot",
            "SpotOptions": {
                "MaxPrice": spot_max_price,
                "SpotInstanceType": "one-time",
                "InstanceInterruptionBehavior": spot_interruption_behavior,
            },
        }
    resp = ec2.run_instances(**kwargs)
    instance_id = resp["Instances"][0]["InstanceId"]
    logger.info("{} instance requested: {}", market_type.replace("-", " ").title(), instance_id)
    return instance_id


def wait_for_running(ec2, instance_id: str) -> str:
    """Wait until instance is running. Returns public IP."""
    logger.info("Waiting for instance {} to reach 'running'...", instance_id)
    waiter = ec2.get_waiter("instance_running")
    waiter.wait(
        InstanceIds=[instance_id],
        WaiterConfig={"Delay": 5, "MaxAttempts": 60},
    )
    resp = ec2.describe_instances(InstanceIds=[instance_id])
    ip = resp["Reservations"][0]["Instances"][0].get("PublicIpAddress")
    if not ip:
        raise RuntimeError(f"Instance {instance_id} has no public IP")
    logger.info("Instance running: {} @ {}", instance_id, ip)
    return ip


# -- SSH config ------------------------------------------------------------

def write_ssh_config_entry(host_alias: str, ip: str):
    """Add or update a Host entry in ~/.ssh/config."""
    SSH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SSH_CONFIG_PATH.exists():
        content = SSH_CONFIG_PATH.read_text()
    else:
        content = ""

    block_re = re.compile(
        rf"^Host {re.escape(host_alias)}\s*\n([ \t]+\S.*\n)*",
        re.MULTILINE,
    )
    new_block = f"Host {host_alias}\n    HostName {ip}\n"

    if block_re.search(content):
        content = block_re.sub(new_block, content)
        logger.info("Updated SSH config entry for {}", host_alias)
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        content += "\n" + new_block
        logger.info("Added SSH config entry for {}", host_alias)

    SSH_CONFIG_PATH.write_text(content)


# -- Check mode (Audit) ----------------------------------------------------

def check_instance(ec2, tag: str) -> bool:
    """Report whether a running instance with the given tag exists."""
    resp = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": [tag]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ])
    instances = [
        inst
        for res in resp["Reservations"]
        for inst in res["Instances"]
    ]
    if instances:
        inst = instances[0]
        ip = inst.get("PublicIpAddress", "no-public-ip")
        print(f"PASS: running instance {inst['InstanceId']} @ {ip} (tag={tag})")
        return True
    else:
        print(f"FAIL: no running instance with tag '{tag}'")
        return False


# -- CLI -------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Launch an EC2 instance, spot or on-demand (or check for one).",
    )
    p.add_argument("--ami", help="AMI ID to launch")
    p.add_argument("--instance-type", default="g4dn.xlarge")
    p.add_argument("--volume-gb", type=int, default=40)
    p.add_argument("--tag", required=True,
                   help="Name tag for the instance (e.g. cloud-task-sara)")
    p.add_argument("--key-name", default=DEFAULT_KEY_NAME)
    p.add_argument("--sg-name", default=DEFAULT_SG_NAME)
    p.add_argument(
        "--market-type",
        choices=("spot", "on-demand"),
        default="spot",
        help="Spot (default) or on-demand pricing.",
    )
    p.add_argument("--spot-max-price", default=DEFAULT_SPOT_MAX_PRICE,
                   help="Spot max price (spot market only).")
    p.add_argument(
        "--spot-interruption-behavior",
        choices=("terminate", "stop", "hibernate"),
        default="terminate",
        help="What AWS does on spot capacity reclaim (spot market only).",
    )
    p.add_argument(
        "--instance-initiated-shutdown-behavior",
        choices=("stop", "terminate"),
        default="stop",
        help="Guest-initiated shutdown: stop the instance (default) or terminate it.",
    )
    p.add_argument(
        "--persist-root-volume",
        action="store_true",
        help="EBS root volume is not deleted when the instance is terminated.",
    )
    p.add_argument("--ssh-host-alias",
                   help="SSH config Host alias (defaults to --tag value)")
    p.add_argument("--no-ssh-config", action="store_true",
                   help="Skip writing SSH config entry")
    p.add_argument("--check", action="store_true",
                   help="Audit mode: check if a matching instance is running")
    return p


def main():
    args = build_parser().parse_args()
    ec2 = ec2_client

    if args.check:
        ok = check_instance(ec2, args.tag)
        sys.exit(0 if ok else 1)

    if not args.ami:
        logger.error("--ami is required for launch (omit only with --check)")
        sys.exit(1)

    sg_id = ensure_security_group(ec2, args.sg_name)
    instance_id = launch_instance(
        ec2,
        ami=args.ami,
        instance_type=args.instance_type,
        volume_gb=args.volume_gb,
        tag=args.tag,
        key_name=args.key_name,
        sg_id=sg_id,
        spot_max_price=args.spot_max_price,
        market_type=args.market_type,
        delete_root_on_termination=not args.persist_root_volume,
        instance_initiated_shutdown_behavior=args.instance_initiated_shutdown_behavior,
        spot_interruption_behavior=args.spot_interruption_behavior,
    )
    ip = wait_for_running(ec2, instance_id)

    if not args.no_ssh_config:
        alias = args.ssh_host_alias or args.tag
        write_ssh_config_entry(alias, ip)

    print(f"instance_id={instance_id}")
    print(f"public_ip={ip}")


if __name__ == "__main__":
    main()
