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
- [container image](container-image.profile.md) — ECR image digest consumed
  by job definitions

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

---

## Target State

- **[`cloud/cf-batch-ocr.yaml`](../../cloud/cf-batch-ocr.yaml) is deployed** with `CAPABILITY_NAMED_IAM`. Parameters: **`VpcId`**, **`OcrS3BucketName`** (job role grants ListBucket + object read/write on that bucket). Outputs supply worker **security group ID** and **IAM ARNs** consumed by the provisioner (via env vars or CLI).

- **Subnet IDs for Batch workers** are chosen outside this template (same VPC as `VpcId`): typically **private subnets** with a path for the host to reach **ECR** (and S3 — public endpoints, NAT, or VPC endpoints per your VPC design). Record chosen subnets in **`cloud-resources.md`** if useful for the next operator.

- **Compute environment, job queue, and container job definition** exist in the project region. **Provisioning** is **idempotent** for CE and queue; **each provisioner run registers a new job definition revision**. Job container: **1 GPU**, **4 vCPU**, **16 GiB**, command **`Ref::inputS3`**, **`Ref::outputS3`** matching [`processor.py`](container/processor.py) S3 mode. **Image** pinned by digest in **`cloud-resources.md`** when possible.

---

## Apply

#### 1. Deploy IAM + worker security group (workstation)

One-time (or when changing bucket / VPC). From repo root, with credentials that can create IAM and EC2 security groups:

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

#### 2. Subnet IDs (workstation)

Set comma-separated worker subnets (must live in `VpcId`):

```bash
export AGENTIC_BATCH_OCR_WORKER_SUBNETS=subnet-aaa,subnet-bbb
```

#### 3. Provision compute environment, queue, job definition (workstation)

Project `venv/`, `.env` loaded. Use `--assume-role` if Batch APIs require the orchestrator role (same pattern as [`ensure-ecr-ocr-repo.py`](../../tools/ensure-ecr-ocr-repo.py)). Pass **`--image`** with the digest from `cloud-resources.md` when not using `:latest`.

```bash
python tools/provision-ocr-batch.py \
  --stack-name agentic-batch-ocr \
  --assume-role arn:aws:iam::ACCOUNT:role/agentic-cloud-task-orchestrator-role
```

With **`--stack-name`** (or **`AGENTIC_BATCH_OCR_CF_STACK_NAME`**), the provisioner reads **Outputs** from that stack for the worker security group and IAM ARNs; you still supply **subnets** (§**2** or **`AGENTIC_BATCH_OCR_WORKER_SUBNETS`**). The caller needs **`cloudformation:DescribeStacks`** on that stack (or keep using exported env vars instead). Optional: `--image`, `--assume-role`.

---

## Audit

_To be filled in during first execution against the target system._
