#!/usr/bin/env python3
"""Orchestrate OWW training on AWS from the Pi.

Launches a g4dn.xlarge spot instance, uploads the training config,
runs aws_train.sh remotely, pulls back hey_sara.onnx, and tears
everything down. One command, one file back.

Usage:
    source ~/venv/bin/activate
    python ~/sara/hudsons-bay/orchestrate.py

    # Dry run (create infra, print SSH command, don't train):
    python ~/sara/hudsons-bay/orchestrate.py --dry-run

    # Teardown only (if a previous run left resources):
    python ~/sara/hudsons-bay/orchestrate.py --teardown-only

Credentials: AWS_ACCESS_KEY_ID_CLOUD, AWS_SECRET_ACCESS_KEY_CLOUD,
AWS_DEFAULT_REGION in project .env
"""

import argparse
import io
import os
import sys
import time
from pathlib import Path

import boto3
import paramiko
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REGION = os.environ["AWS_DEFAULT_REGION"]
AMI_ID = "ami-084f512b0521b5fb4"  # Deep Learning Base OSS Nvidia, Ubuntu 22.04, ap-southeast-2
INSTANCE_TYPE = "g4dn.xlarge"
VOLUME_SIZE_GB = 80
SPOT_MAX_PRICE = "0.50"  # safety cap; current spot ~$0.33
KEY_NAME = "sara-training-key"
SG_NAME = "sara-training-sg"
TAG_VALUE = "sara-hudsons-bay"

LOCAL_DIR = Path(__file__).resolve().parent
MODEL_OUTPUT = LOCAL_DIR / "model" / "hey_sara.onnx"
SSH_KEY_PATH = LOCAL_DIR / ".ssh_key.pem"

SSH_USER = "ubuntu"
SSH_TIMEOUT = 10
SSH_RETRIES = 30  # 30 × 10s = 5 min max wait for instance SSH

# Files to upload
UPLOAD_FILES = [
    "aws_train.sh",
    "hey_sara_model.yml",
]


def get_ec2_client():
    return boto3.client(
        "ec2",
        region_name=REGION,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID_CLOUD"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY_CLOUD"],
    )


def get_ec2_resource():
    return boto3.resource(
        "ec2",
        region_name=REGION,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID_CLOUD"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY_CLOUD"],
    )


# ---------------------------------------------------------------------------
# Infrastructure setup
# ---------------------------------------------------------------------------

def create_key_pair(ec2_client) -> str:
    """Create SSH key pair, save private key locally. Returns key name."""
    try:
        ec2_client.delete_key_pair(KeyName=KEY_NAME)
    except Exception:
        pass
    resp = ec2_client.create_key_pair(KeyName=KEY_NAME, KeyType="rsa", KeyFormat="pem")
    SSH_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SSH_KEY_PATH.write_text(resp["KeyMaterial"])
    SSH_KEY_PATH.chmod(0o600)
    logger.info("SSH key pair created: {}", KEY_NAME)
    return KEY_NAME


def create_security_group(ec2_client) -> str:
    """Create SG allowing SSH from anywhere. Returns group ID."""
    try:
        resp = ec2_client.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [SG_NAME]}]
        )
        if resp["SecurityGroups"]:
            sg_id = resp["SecurityGroups"][0]["GroupId"]
            logger.info("Security group exists: {} ({})", SG_NAME, sg_id)
            return sg_id
    except Exception:
        pass

    resp = ec2_client.create_security_group(
        GroupName=SG_NAME,
        Description="SSH access for sara wake word training",
    )
    sg_id = resp["GroupId"]
    ec2_client.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            "IpProtocol": "tcp",
            "FromPort": 22,
            "ToPort": 22,
            "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH"}],
        }],
    )
    logger.info("Security group created: {} ({})", SG_NAME, sg_id)
    return sg_id


def launch_spot_instance(ec2_client, sg_id: str) -> str:
    """Launch a spot instance. Returns instance ID."""
    resp = ec2_client.run_instances(
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_NAME,
        SecurityGroupIds=[sg_id],
        MinCount=1,
        MaxCount=1,
        InstanceMarketOptions={
            "MarketType": "spot",
            "SpotOptions": {
                "MaxPrice": SPOT_MAX_PRICE,
                "SpotInstanceType": "one-time",
                "InstanceInterruptionBehavior": "terminate",
            },
        },
        BlockDeviceMappings=[{
            "DeviceName": "/dev/sda1",
            "Ebs": {"VolumeSize": VOLUME_SIZE_GB, "VolumeType": "gp3", "DeleteOnTermination": True},
        }],
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": TAG_VALUE}, {"Key": "Project", "Value": "agentic-cloud-task"}],
        }],
    )
    instance_id = resp["Instances"][0]["InstanceId"]
    logger.info("Spot instance requested: {}", instance_id)
    return instance_id


def wait_for_instance(ec2_client, instance_id: str) -> str:
    """Wait for instance to be running. Returns public IP."""
    logger.info("Waiting for instance to enter 'running' state...")
    waiter = ec2_client.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 5, "MaxAttempts": 60})

    resp = ec2_client.describe_instances(InstanceIds=[instance_id])
    ip = resp["Reservations"][0]["Instances"][0].get("PublicIpAddress")
    if not ip:
        raise RuntimeError(f"Instance {instance_id} has no public IP")
    logger.info("Instance running: {} @ {}", instance_id, ip)
    return ip


# ---------------------------------------------------------------------------
# SSH operations
# ---------------------------------------------------------------------------

def wait_for_ssh(ip: str) -> paramiko.SSHClient:
    """Retry SSH connection until the instance is reachable."""
    key = paramiko.RSAKey.from_private_key(io.StringIO(SSH_KEY_PATH.read_text()))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    for attempt in range(1, SSH_RETRIES + 1):
        try:
            client.connect(ip, username=SSH_USER, pkey=key, timeout=SSH_TIMEOUT)
            logger.info("SSH connected (attempt {})", attempt)
            return client
        except Exception as e:
            if attempt == SSH_RETRIES:
                raise RuntimeError(f"SSH failed after {SSH_RETRIES} attempts: {e}")
            logger.debug("SSH attempt {}/{}: {}", attempt, SSH_RETRIES, e)
            time.sleep(10)
    raise RuntimeError("unreachable")


def upload_files(ssh: paramiko.SSHClient, files: list[str]):
    """Upload training files to ~/hudsons-bay/ on the instance."""
    sftp = ssh.open_sftp()
    try:
        try:
            sftp.mkdir("/home/ubuntu/hudsons-bay")
        except IOError:
            pass
        for fname in files:
            local = LOCAL_DIR / fname
            remote = f"/home/ubuntu/hudsons-bay/{fname}"
            logger.info("Uploading {} -> {}", local.name, remote)
            sftp.put(str(local), remote)
        sftp.chmod("/home/ubuntu/hudsons-bay/aws_train.sh", 0o755)
    finally:
        sftp.close()


def run_remote(ssh: paramiko.SSHClient, cmd: str, stream: bool = True) -> int:
    """Run command on instance, streaming stdout/stderr. Returns exit code."""
    logger.info("Remote: {}", cmd)
    _, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=None)
    if stream:
        for line in stdout:
            print(line, end="", flush=True)
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        err = stderr.read().decode()
        if err.strip():
            logger.error("stderr:\n{}", err)
    return exit_code


def download_model(ssh: paramiko.SSHClient):
    """Download hey_sara.onnx from the instance."""
    sftp = ssh.open_sftp()
    try:
        remote_path = "/home/ubuntu/hudsons-bay/hey_sara.onnx"
        MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading {} -> {}", remote_path, MODEL_OUTPUT)
        sftp.get(remote_path, str(MODEL_OUTPUT))
        size = MODEL_OUTPUT.stat().st_size
        logger.info("Downloaded hey_sara.onnx ({} bytes)", size)
    finally:
        sftp.close()


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------

def find_tagged_instances(ec2_client) -> list[str]:
    """Find any running/pending instances tagged with our project."""
    resp = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": [TAG_VALUE]},
            {"Name": "instance-state-name", "Values": ["running", "pending", "stopping", "stopped"]},
        ],
    )
    ids = []
    for res in resp["Reservations"]:
        for inst in res["Instances"]:
            ids.append(inst["InstanceId"])
    return ids


def teardown(ec2_client):
    """Terminate instances, delete SG and key pair."""
    instance_ids = find_tagged_instances(ec2_client)
    if instance_ids:
        logger.info("Terminating instances: {}", instance_ids)
        ec2_client.terminate_instances(InstanceIds=instance_ids)
        waiter = ec2_client.get_waiter("instance_terminated")
        waiter.wait(InstanceIds=instance_ids, WaiterConfig={"Delay": 5, "MaxAttempts": 60})
        logger.info("Instances terminated")
    else:
        logger.info("No tagged instances found")

    try:
        ec2_client.delete_key_pair(KeyName=KEY_NAME)
        logger.info("Key pair deleted: {}", KEY_NAME)
    except Exception:
        pass

    try:
        resp = ec2_client.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [SG_NAME]}]
        )
        for sg in resp["SecurityGroups"]:
            ec2_client.delete_security_group(GroupId=sg["GroupId"])
            logger.info("Security group deleted: {}", sg["GroupId"])
    except Exception as e:
        logger.debug("SG cleanup: {}", e)

    if SSH_KEY_PATH.exists():
        SSH_KEY_PATH.unlink()
        logger.debug("Local SSH key removed")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Orchestrate OWW training on AWS")
    p.add_argument("--dry-run", action="store_true",
                   help="Create infra and print SSH command, but don't train")
    p.add_argument("--teardown-only", action="store_true",
                   help="Just clean up any leftover AWS resources")
    args = p.parse_args()

    ec2_client = get_ec2_client()

    if args.teardown_only:
        teardown(ec2_client)
        return

    t_start = time.monotonic()
    instance_id = None

    try:
        # --- Setup ---
        create_key_pair(ec2_client)
        sg_id = create_security_group(ec2_client)
        instance_id = launch_spot_instance(ec2_client, sg_id)
        ip = wait_for_instance(ec2_client, instance_id)

        # --- Connect ---
        ssh = wait_for_ssh(ip)

        if args.dry_run:
            logger.info("Dry run — instance is live at {}. SSH with:", ip)
            print(f"\n  ssh -i {SSH_KEY_PATH} {SSH_USER}@{ip}\n")
            print("Run --teardown-only when done.")
            ssh.close()
            return

        try:
            # --- Upload ---
            upload_files(ssh, UPLOAD_FILES)

            # --- Train ---
            logger.info("Starting training (this will take 1-4 hours)...")
            exit_code = run_remote(ssh, "cd /home/ubuntu/hudsons-bay && ./aws_train.sh")

            if exit_code != 0:
                logger.error("Training failed with exit code {}", exit_code)
                logger.info("Instance still running at {} for debugging. "
                            "Run --teardown-only when done.", ip)
                ssh.close()
                return

            # --- Download ---
            download_model(ssh)
            ssh.close()

        except Exception:
            logger.exception("Error during training")
            logger.info("Instance still running at {} for debugging. "
                        "Run --teardown-only when done.", ip)
            return

        elapsed = time.monotonic() - t_start
        logger.info("Total wall time: {:.0f}m {:.0f}s", elapsed // 60, elapsed % 60)

    except Exception:
        logger.exception("Orchestration failed")
        if instance_id:
            logger.info("Attempting teardown of partial resources...")

    # --- Teardown ---
    logger.info("Tearing down AWS resources...")
    teardown(ec2_client)

    if MODEL_OUTPUT.exists():
        logger.info("SUCCESS: {} ({} bytes)", MODEL_OUTPUT, MODEL_OUTPUT.stat().st_size)
        logger.info("Next: python smoke_test_model.py {}", MODEL_OUTPUT)
    else:
        logger.error("Model file not found — training may have failed")


if __name__ == "__main__":
    main()
