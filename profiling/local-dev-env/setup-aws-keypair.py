#!/usr/bin/env python3
"""Generate a project-global SSH keypair and import it to AWS.

Requires the project venv (boto3, python-dotenv) and .env with credentials.
Run from the project root after `pip install -r requirements.txt`.

Usage:
    python profiling/local-dev-env/setup-aws-keypair.py

Idempotent: skips keypair generation if .keys/cloud-task.pem already exists,
skips AWS import if the key pair already exists in the target region.
"""

import os
import subprocess
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KEYS_DIR = PROJECT_ROOT / ".keys"
KEY_NAME = "cloud-task"
PRIVATE_KEY = KEYS_DIR / f"{KEY_NAME}.pem"
PUBLIC_KEY = KEYS_DIR / f"{KEY_NAME}.pem.pub"

load_dotenv(PROJECT_ROOT / ".env", override=True)

REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-2")


def get_ec2_client():
    return boto3.client(
        "ec2",
        region_name=REGION,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID_CLOUD"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY_CLOUD"],
    )


def generate_keypair():
    if PRIVATE_KEY.exists():
        print(f"Keypair already exists: {PRIVATE_KEY}")
        return

    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating keypair: {PRIVATE_KEY}")
    subprocess.run(
        [
            "ssh-keygen", "-t", "rsa", "-b", "4096",
            "-f", str(PRIVATE_KEY),
            "-N", "",
            "-C", "agentic-cloud-task",
        ],
        check=True,
    )
    print(f"  Private key: {PRIVATE_KEY}")
    print(f"  Public key:  {PUBLIC_KEY}")


def import_to_aws(ec2):
    try:
        existing = ec2.describe_key_pairs(KeyNames=[KEY_NAME])
        if existing["KeyPairs"]:
            fp = existing["KeyPairs"][0].get("KeyFingerprint", "n/a")
            print(f"Key pair '{KEY_NAME}' already exists in AWS ({REGION}), fingerprint: {fp}")
            return
    except ec2.exceptions.ClientError as e:
        if "InvalidKeyPair.NotFound" not in str(e):
            raise

    pub_bytes = PUBLIC_KEY.read_bytes()
    resp = ec2.import_key_pair(
        KeyName=KEY_NAME,
        PublicKeyMaterial=pub_bytes,
        TagSpecifications=[{
            "ResourceType": "key-pair",
            "Tags": [{"Key": "Project", "Value": "agentic-cloud-task"}],
        }],
    )
    fp = resp.get("KeyFingerprint", "n/a")
    print(f"Imported '{KEY_NAME}' to AWS ({REGION}), fingerprint: {fp}")


def verify_identity(ec2):
    sts = boto3.client(
        "sts",
        region_name=REGION,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID_CLOUD"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY_CLOUD"],
    )
    identity = sts.get_caller_identity()
    print(f"AWS identity: {identity['Arn']}")


def print_ssh_config():
    block = f"""\
Host cloud-task-*
    User ubuntu
    IdentityFile {PRIVATE_KEY}
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null"""

    print()
    print("Add this block to ~/.ssh/config (if not already present):")
    print()
    print(block)
    print()


def main():
    print("--- agentic-cloud-task: keypair setup ---")
    print()

    ec2 = get_ec2_client()
    verify_identity(ec2)
    print()

    generate_keypair()
    print()

    import_to_aws(ec2)
    print()

    print_ssh_config()
    print("Done.")


if __name__ == "__main__":
    main()
