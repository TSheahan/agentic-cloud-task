"""Project environment: credentials, paths, and AWS client factories.

Loads .env on import. Other tools/scripts use:

    from _env import PROJECT_ROOT, ec2_client
    from _env import AWS_ACCESS_KEY_ID_CLOUD  # if raw keys needed
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

AWS_ACCESS_KEY_ID_CLOUD = os.environ["AWS_ACCESS_KEY_ID_CLOUD"]
AWS_SECRET_ACCESS_KEY_CLOUD = os.environ["AWS_SECRET_ACCESS_KEY_CLOUD"]
AWS_DEFAULT_REGION = os.environ["AWS_DEFAULT_REGION"]


def ec2_client():
    """Return a boto3 EC2 client configured from project credentials."""
    import boto3
    return boto3.client(
        "ec2",
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID_CLOUD,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY_CLOUD,
    )
