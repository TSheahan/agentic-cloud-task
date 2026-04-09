# AWS Batch Worker Plane — State Convergence Profile

Managed **GPU workers** for OCR batch processing on **AWS Batch**:
**g4dn**-class instances, scale-to-zero friendly defaults, **S3 in/out** only
in app code, **no SSH** on workers. A **single security group** from
[`cloud/cf-batch-ocr.yaml`](../../cloud/cf-batch-ocr.yaml) encodes that
intent: **no ingress**; **egress unrestricted** so image pull and AWS APIs
work without hand-maintained rules.

Layers on:
- [ocr-batch shared infrastructure](ocr-batch.profile.md) — instance, SSH,
  WORKDIR
- [container image](container-image.profile.md) — ECR image referenced by
  `:latest` tag in job definitions

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

---

## Target State

- **Default VPC ID and its public subnets are detected** at runtime via `ec2:DescribeVpcs` (`is-default=true`) and `ec2:DescribeSubnets`. A shared helper in `tools/_env.py` (or equivalent) exposes `detect_default_vpc() → (vpc_id, [subnet_ids])`. Both the CF stack deploy (`VpcId` parameter) and the provisioner (worker subnets) consume this as a fallback; explicit overrides (`AGENTIC_BATCH_OCR_WORKER_SUBNETS`, CLI `--vpc-id`) still win.

- **[`cloud/cf-batch-ocr.yaml`](../../cloud/cf-batch-ocr.yaml) is deployed** with `CAPABILITY_NAMED_IAM`. Parameters: **`VpcId`** (from detection or override), **`OcrS3BucketName`** (job role grants ListBucket + object read/write on that bucket). Outputs supply worker **security group ID**, **IAM ARNs**, **S3 bucket name**, and **log group name** consumed by the provisioner (via env vars or CLI).
  - Stack includes a **CloudWatch Logs log group** (`/agentic-cloud-task/ocr-batch`) with a short **retention policy** (cost control — retain for diagnostics, then drop).
  - Stack creates the **OCR data S3 bucket** (`OcrS3BucketName`).

- **Subnet IDs for Batch workers** default to the **detected default VPC public subnets**. The worker security group blocks all inbound, so a public IP creates no attack surface; outbound reaches ECR, S3, and CloudWatch via the VPC internet gateway with no NAT or endpoint cost. Revisit if compliance mandates no public IPs or the VPC gains existing private-subnet + NAT infrastructure.

- **Compute environment, job queue, and container job definition** exist in the project region. **Provisioning is idempotent** for all three resources. Job container: **1 GPU**, **4 vCPU**, **16 GiB**, command **`Ref::inputS3`**, **`Ref::outputS3`** matching [`processor.py`](container/processor.py) S3 mode. **Image** referenced by **`:latest`** tag; submit jobs by **name only** (latest active revision).
  - **On-demand EC2** (not Spot): cost difference is not a controlling concern; reliable availability reduces design load on the caller (no retry strategy, no fleet role, no interruption handling).
  - **`maxvCpus` = 4** (one g4dn.xlarge): single user, high paper backlog, low scan rate, interpretation in the loop — one worker disposes of the workload. `--max-vcpus` CLI flag exists if concurrency is needed later.
  - **Job definition registration is idempotent:** provisioner describes the latest active revision and compares image, resource requirements, command, parameters, and IAM role ARNs; registers a new revision only when config differs. Aligns with the `_ensure_*` pattern used for CE and queue.
  - **Job definition sets `logConfiguration`:** `awslogs` driver targeting the stack's log group, stream prefix `ocr`. Container stdout/stderr routes to the project log group, not the shared `/aws/batch/job` default.

- **Smoke-test submit tool** (`tools/submit-ocr-batch-job.py`) exists: submit-and-wait against the job queue by **name-only** job definition, with `inputS3` and `outputS3` parameter overrides. On **SUCCEEDED**: fetch and print the output `.md` from S3. On **FAILED**: print `statusReason` and fetch container logs from the project CloudWatch log group.

---

## Apply

#### 1. Deploy Batch OCR static stack (workstation)

One-time (or when changing bucket / VPC). `VpcId` can be auto-detected from the default VPC or supplied explicitly. From repo root, with credentials that can create IAM, EC2 security groups, S3, and CloudWatch Logs:

```bash
aws cloudformation deploy \
  --template-file cloud/cf-batch-ocr.yaml \
  --stack-name agentic-batch-ocr \
  --parameter-overrides VpcId=vpc-XXXXXXXX OcrS3BucketName=your-ocr-data-bucket \
  --capabilities CAPABILITY_NAMED_IAM
```

Copy **Outputs** into gitignored **`cloud-resources.md`** (see [example layout](../../cloud-resources.example.md)) and/or export for the next step:

- `WorkerSecurityGroupId` → `AGENTIC_BATCH_OCR_WORKER_SECURITY_GROUP_ID`
- `BatchServiceRoleArn` → `AGENTIC_BATCH_OCR_SERVICE_ROLE_ARN`
- `EcsExecutionRoleArn` → `AGENTIC_BATCH_OCR_EXECUTION_ROLE_ARN`
- `JobRoleArn` → `AGENTIC_BATCH_OCR_JOB_ROLE_ARN`
- `InstanceProfileArn` → `AGENTIC_BATCH_OCR_INSTANCE_PROFILE_ARN`
- `OcrS3BucketName` → `AGENTIC_BATCH_OCR_S3_BUCKET`
- `OcrBatchLogGroupName` → `AGENTIC_BATCH_OCR_LOG_GROUP`

#### 2. Subnet IDs (workstation — optional override)

The provisioner auto-detects default VPC public subnets when `AGENTIC_BATCH_OCR_WORKER_SUBNETS` is not set. To override:

```bash
export AGENTIC_BATCH_OCR_WORKER_SUBNETS=subnet-aaa,subnet-bbb
```

#### 3. Provision compute environment, queue, job definition (workstation)

Project `venv/`, `.env` loaded. Use `--assume-role` if Batch APIs require the orchestrator role (same pattern as [`ensure-ecr-ocr-repo.py`](../../tools/ensure-ecr-ocr-repo.py)). Image defaults to `:latest`.

```bash
python tools/provision-ocr-batch.py \
  --stack-name agentic-batch-ocr \
  --assume-role arn:aws:iam::ACCOUNT:role/agentic-cloud-task-orchestrator-role
```

With **`--stack-name`** (or **`AGENTIC_BATCH_OCR_CF_STACK_NAME`**), the provisioner reads **Outputs** from that stack for the worker security group, IAM ARNs, and log group name. Subnets auto-detect from the default VPC unless overridden (§**2** or **`AGENTIC_BATCH_OCR_WORKER_SUBNETS`**). The caller needs **`cloudformation:DescribeStacks`** on that stack. Optional: `--image`, `--assume-role`.

---

## Audit

_To be filled in during first execution against the target system._
