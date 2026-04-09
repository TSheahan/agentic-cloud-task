# tools/ — Shared Operational Utilities

Reusable scripts invoked by profile Apply and Audit steps. Each tool
performs one atomic operation (launch an instance, ensure a security group,
tear down tagged resources) and is parameterised so multiple profiles can
share it.

## Conventions

- **`_env.py`** is the shared environment module. It loads `.env` on import
  and exports project root, AWS credential values, and client factories.
  All tools import from it — no tool loads `.env` or constructs AWS clients
  directly.
- Tools are invoked from the project venv (`venv/`) established by the
  [local dev workstation profile](../profiling/local-dev-env/dev-workstation.profile.md).
- Each tool is self-documenting (`--help`).
- Tools that modify state support a `--check` or dry-run mode for Audit use.

## Contents

| File | Purpose |
|------|---------|
| [_env.py](_env.py) | Shared environment: loads `.env`, exports `PROJECT_ROOT`, AWS credentials, `ec2_client` (ready-to-use boto3 EC2 client), `detect_default_vpc()` helper |
| [launch-spot-instance.py](launch-spot-instance.py) | Ensure security group, launch EC2 instance (spot or on-demand), wait for running, return IP. Optional: guest shutdown stop vs terminate, `--persist-root-volume` (off by default: delete root EBS on instance terminate), spot interruption behavior. Write SSH config entry. |
| [teardown-instance.py](teardown-instance.py) | Terminate tagged instances, clean up security group and SSH config entry. |
| [create-ami.py](create-ami.py) | Create an AMI from a tagged running instance, wait for available. |
| [ensure-ecr-ocr-repo.py](ensure-ecr-ocr-repo.py) | Idempotent: ensure ECR `ocr-docling-gpu` exists with `Project=agentic-cloud-task`. Use `--assume-role` with the orchestrator role ARN if the `.env` IAM user lacks `ecr:CreateRepository`. |
| [provision-ocr-batch.py](provision-ocr-batch.py) | Idempotent: ensure OCR GPU Batch compute env (scale-to-zero), job queue, and container job definition (`Ref::inputS3` / `Ref::outputS3`, `awslogs` log config). Subnets: CLI/env/default-VPC auto-detect; SG + IAM + log group from CLI, env, or **`--stack-name`** CF outputs. Optional `--assume-role`. |
| [submit-ocr-batch-job.py](submit-ocr-batch-job.py) | Submit an OCR job to Batch and wait: on **SUCCEEDED** fetch + print `.md` from S3; on **FAILED** print reason + CloudWatch container logs. Positional args: `inputS3`, `outputS3`. Optional `--assume-role`. |
