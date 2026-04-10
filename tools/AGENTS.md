# tools/ — Shared Operational Utilities

Reusable scripts invoked by profile Apply and Audit steps. Each tool
performs one atomic operation (launch an instance, ensure a security group,
tear down tagged resources) and is parameterised so multiple profiles can
share it.

## Conventions

- **`_env.py`** is the shared environment module. It loads `.env` on import
  and exports project root, AWS credential values, session helpers, and the
  user-scoped `ec2_client`. All tools import from it — no tool loads `.env`
  directly.

### AWS principals (`_env.py`)

Two layers matter for boto3:

| Principal | How | Typical permissions |
|-----------|-----|---------------------|
| **IAM user** (`.env` keys) | `boto3_session_user()`, or `ec2_client`, or `boto3_session(assume_role_arn=None)` | Often `sts:AssumeRole` to the orchestrator role + **AgenticCloud-Workstation-EC2-Lifecycle** (describe/start/stop project-tagged instances). Not Batch/ECR/full EC2-Core unless also granted on the user. |
| **Orchestrator role** (`agentic-cloud-task-orchestrator-role`) | `boto3_session(assume_role_arn=..., role_session_name="…")` | EC2-Core, ECR, Batch, S3, PassRole, CloudFormation read — see `cloud/cf-cloud-permission-roles.yaml`. |

**Default assume without repeating `--assume-role`:** set **`AGENTIC_ORCHESTRATOR_ROLE_ARN`** in `.env` to the role ARN. **`resolved_assume_role_arn(cli_value)`** returns `cli_value` if set, else that env var. Tools use it so CLI overrides env.

**Ad-hoc snippets:** for orchestrator APIs, use `boto3_session(assume_role_arn=resolved_assume_role_arn(None), role_session_name="cursor-snippet")` then `session.client("…")`. For user-only EC2 (e.g. tagged instance checks), `from _env import ec2_client` is enough. Assumed credentials **expire** (~1 h); do not cache a role-based client at module level for long runs.
- Tools are invoked from the project venv (`venv/`) established by the
  [local dev workstation profile](../profiling/local-dev-env/dev-workstation.profile.md).
- Each tool is self-documenting (`--help`).
- Tools that modify state support a `--check` or dry-run mode for Audit use.

## Contents

| File | Purpose |
|------|---------|
| [_env.py](_env.py) | Shared environment: loads `.env`, `PROJECT_ROOT`, `boto3_session` / `boto3_session_user` / `resolved_assume_role_arn`, user-scoped `ec2_client`, `detect_default_vpc(ec2=…)` |
| [launch-spot-instance.py](launch-spot-instance.py) | Ensure security group, launch EC2 instance (spot or on-demand), wait for running, return IP. Optional: guest shutdown stop vs terminate, `--persist-root-volume` (off by default: delete root EBS on instance terminate), spot interruption behavior. Write SSH config entry. |
| [teardown-instance.py](teardown-instance.py) | Terminate tagged instances, clean up security group and SSH config entry. |
| [create-ami.py](create-ami.py) | Create an AMI from a tagged running instance, wait for available. |
| [ensure-ecr-ocr-repo.py](ensure-ecr-ocr-repo.py) | Idempotent: ensure ECR `ocr-docling-gpu` exists with `Project=agentic-cloud-task`. Orchestrator role: `--assume-role` or `AGENTIC_ORCHESTRATOR_ROLE_ARN` if the user lacks `ecr:CreateRepository`. |
| [provision-ocr-batch.py](provision-ocr-batch.py) | Idempotent: ensure OCR GPU Batch compute env (scale-to-zero), job queue, and container job definition (`Ref::inputS3` / `Ref::outputS3`, `awslogs` log config). Subnets: CLI/env/default-VPC auto-detect; SG + IAM + log group from CLI, env, or **`--stack-name`** CF outputs. Orchestrator: `--assume-role` or `AGENTIC_ORCHESTRATOR_ROLE_ARN`. |
| [submit-ocr-batch-job.py](submit-ocr-batch-job.py) | Submit an OCR job to Batch and wait: on **SUCCEEDED** fetch + print `.md` from S3; on **FAILED** print reason + CloudWatch container logs. Positional args: `inputS3`, `outputS3`. Orchestrator: `--assume-role` or `AGENTIC_ORCHESTRATOR_ROLE_ARN`. |
