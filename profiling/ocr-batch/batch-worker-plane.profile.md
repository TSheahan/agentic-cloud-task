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

- **Compute environment, job queue, and container job definition** exist in the project region. **Provisioning is idempotent** for all three resources. Job container: **1 GPU**, **3 vCPU**, **15360 MiB** (not the full g4dn.xlarge nominal 4 vCPU / 16 GiB — ECS/Batch host reserve otherwise yields `MISCONFIGURATION:JOB_RESOURCE_REQUIREMENT`), command **`Ref::inputS3`**, **`Ref::outputS3`** matching [`processor.py`](container/processor.py) S3 mode. **Image** referenced by **`:latest`** tag; submit jobs by **name only** (latest active revision).
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

Project `venv/`, `.env` loaded. Use `--assume-role` or set **`AGENTIC_ORCHESTRATOR_ROLE_ARN`** if Batch APIs require the orchestrator role (see [`tools/_env.py`](../../tools/_env.py) and [`tools/AGENTS.md`](../../tools/AGENTS.md)). Image defaults to `:latest`.

```bash
python tools/provision-ocr-batch.py \
  --stack-name agentic-batch-ocr \
  --assume-role arn:aws:iam::ACCOUNT:role/agentic-cloud-task-orchestrator-role
```

With **`--stack-name`** (or **`AGENTIC_BATCH_OCR_CF_STACK_NAME`**), the provisioner reads **Outputs** from that stack for the worker security group, IAM ARNs, and log group name. Subnets auto-detect from the default VPC unless overridden (§**2** or **`AGENTIC_BATCH_OCR_WORKER_SUBNETS`**). The caller needs **`cloudformation:DescribeStacks`** on that stack. Optional: `--image`, `--assume-role`.

---

## Audit

Derived from first smoke-test execution (2026-04-10). Steps 1--2 verified; steps 3--5 pending.

#### 1. CF stack deployed and outputs readable

```bash
# Orchestrator reads stack outputs (DescribeStacks)
python -c "
import sys
sys.path.insert(0, 'tools')
from _env import boto3_session, resolved_assume_role_arn
ROLE = 'arn:aws:iam::613737894147:role/agentic-cloud-task-orchestrator-role'
session = boto3_session(assume_role_arn=resolved_assume_role_arn(ROLE), role_session_name='audit-cfn')
cfn = session.client('cloudformation')
s = cfn.describe_stacks(StackName='agentic-batch-ocr')['Stacks'][0]
assert s['StackStatus'] == 'CREATE_COMPLETE'
for o in s['Outputs']: print(f\"{o['OutputKey']:30s} = {o['OutputValue']}\")
"
```

#### 2. Batch resources exist and are VALID

```bash
# CE status = VALID, queue exists, job def has active revision
python tools/provision-ocr-batch.py \
  --stack-name agentic-batch-ocr \
  --assume-role arn:aws:iam::ACCOUNT:role/agentic-cloud-task-orchestrator-role
# Idempotent — prints "exists" for each if already provisioned.
```

#### 3. Submit smoke job (pending)

_Run `tools/submit-ocr-batch-job.py` per brief step 4. Verify SUCCEEDED, `.md` output, 3 objects under output prefix._

#### 4. Batch SLR exists

Verify `AWSServiceRoleForBatch` exists in account (first-time Batch prerequisite).

---

## First-execution observations (2026-04-10)

Recorded during smoke test. Fold forward into Target State or Apply as warranted.

### Prerequisites not previously documented

1. **Batch service-linked role** (`AWSServiceRoleForBatch`) must exist before `CreateComputeEnvironment`. First-time Batch accounts need it created manually or via `iam:CreateServiceLinkedRole` for `batch.amazonaws.com`.
2. **Permission-roles stack** must grant `batch:TagResource` with `aws:RequestTag` condition for create-time tagging (tag-at-create chicken-and-egg).
3. **`iam:PassRole` to `ec2.amazonaws.com`** is needed in the Batch policy for the instance profile role (Batch passes it to EC2 at CE creation).
4. **`computeResources.tags`** (instance-level tags) triggers an additional IAM evaluation that the current orchestrator policy cannot satisfy. Removed from provisioner for now; CE-level tags (`tags` top-level) work. Revisit when the IAM interaction is understood.

### CF template fixes applied

- `AWSBatchServicePolicy` (nonexistent) changed to `AWSBatchServiceRole`.
- SG `GroupDescription` simplified to single-line ASCII (YAML `>` folding + em-dash caused EC2 rejection).

### Provisioner fixes applied

- `_session()` duplicate `region_name` kwarg fixed (both provisioner and submit tool).
- `computeEnvironmentOrder` kwarg renamed to `compute_env_order` (matched function signature).
- `computeResources.tags` removed (IAM denial; see prerequisite 4 above).

### Cleanup required

- Orphan probe CE `probe-no-crtags` in Batch (created during IAM debugging; needs console delete).
