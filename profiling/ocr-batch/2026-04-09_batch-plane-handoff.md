# OCR AWS Batch plane — handoff (2026-04-09)

Time-bound snapshot of **design choices**, **what CloudFormation owns**, **baked-in provisioner defaults**, and a **path to full instantiation** (runnable Batch jobs end-to-end). Authoritative living detail remains in [`ocr-batch.profile.md`](ocr-batch.profile.md), [`cloud/cf-batch-ocr.yaml`](../../cloud/cf-batch-ocr.yaml), and [`tools/provision-ocr-batch.py`](../../tools/provision-ocr-batch.py).

---

## 1. Decided (explicit product / ops intent)

| Element | Decision | Notes |
|--------|----------|--------|
| **Worker role** | Batch EC2 workers are **not SSH targets** | No interactive admin on job hosts; tear-down is cheap. |
| **Ingress** | **None** on the worker security group | Matches "lock inbound down entirely" once basics exist. |
| **Egress** | **All traffic** to `0.0.0.0/0` (`IpProtocol: -1`) | Simplicity over curated endpoint lists; covers ECR, S3, CloudWatch Logs, STS, etc. |
| **Application I/O** | **S3 only** at the app layer | [`processor.py`](container/processor.py) S3 mode: `<input_s3_uri>` + `<output_s3_prefix>`. |
| **Split: CF vs script** | **Low-churn** = template; **faster iteration** = Python | CE, queue, job definition stay out of `cf-batch-ocr.yaml` so job-def churn does not imply stack updates. |
| **Orchestrator credentials** | **Assume role** pattern matches ECR tooling | `.env` user may lack Batch/CF; `agentic-cloud-task-orchestrator-role` carries API rights. |
| **Stack-driven deps** | **`DescribeStacks`** supplies SG + five ARNs + log group + S3 bucket | Optional `--stack-name` / `AGENTIC_BATCH_OCR_CF_STACK_NAME`; precedence: CLI > env > stack output. |
| **Subnets** | **Auto-detect default VPC** or operator-supplied (not in Batch OCR stack) | `detect_default_vpc()` in `_env.py`; CLI/env override still wins. |
| **S3 scope for job role** | **Single bucket** parameter on stack | `OcrS3BucketName`: ListBucket + object RW under that bucket only (no prefix-level IAM in template). |
| **Batch API caller** | **`cloudformation:DescribeStacks`** added for orchestrator | [`cf-cloud-permission-roles.yaml`](../../cloud/cf-cloud-permission-roles.yaml) — `AgenticCloud-CloudFormationReadPolicy`; stack update required for `--stack-name` path. |
| **ECR image** | **Fat** GPU container, digest pinned for prod | `cloud-resources.md` holds URI + digest; Batch job defs should prefer `@sha256:…`. |
| **Tagging** | **`Project=agentic-cloud-task`** on Batch-created resources | CE tags, CE computeResource instance tags, queue tags, job definition tags (provisioner). |

---

## 2. Disposed to template (`cloud/cf-batch-ocr.yaml`)

These are **created once** (or rarely), exported as **Outputs**, and consumed by the provisioner via **env** or **`--stack-name`**.

| Element | In template | Role |
|---------|-------------|------|
| Worker **security group** | `BatchOcrWorkerSecurityGroup` | VPC + no ingress + open egress (see §1). |
| **Batch service role** | `BatchOcrServiceRole` + `AWSBatchServicePolicy` | `batch.amazonaws.com` manages compute. |
| **ECS task execution role** | `BatchOcrEcsExecutionRole` + `AmazonECSTaskExecutionRolePolicy` | ECR pull, log driver. |
| **Job role** | `BatchOcrJobRole` + inline `OcrS3DataAccess` | In-container S3 for one bucket. |
| **Instance role + profile** | `BatchOcrInstanceRole` + `AmazonEC2ContainerServiceforEC2Role` + `BatchOcrInstanceProfile` | Host identity for Batch-launched EC2. |
| **Parameters** | `VpcId`, `OcrS3BucketName`, `ProjectTagValue` | Bucket must exist; VPC must match subnet choice later. |
| **Named IAM** | Fixed `RoleName` / `InstanceProfileName` under `agentic-cloud-task-batch-ocr-*` | Predictable ARNs; deploy needs `CAPABILITY_NAMED_IAM`. |

**Not** in this template: subnets, compute environment, job queue, job definition, ECR repo, data buckets' creation.

---

## 3. Baked into `tools/provision-ocr-batch.py` (defaults & behavior)

Treat these as **implicit decisions** unless overridden via CLI.

### 3.1 Naming

| Constant | Value |
|----------|--------|
| Compute environment | `ocr-docling-gpu-ce` |
| Job queue | `ocr-docling-gpu-queue` |
| Job definition name | `ocr-docling-gpu` |
| ECR repo name (for default image URI only) | `ocr-docling-gpu` |

### 3.2 Compute environment (when created)

| Field | Baked value | Override |
|-------|-------------|----------|
| `type` | `MANAGED` | — |
| `state` | `ENABLED` | — |
| Compute resource `type` | `EC2` or `SPOT` if `--spot` | `--spot`, `--spot-fleet-role-arn` |
| `minvCpus` | `0` | `--min-vcpus` |
| `desiredvCpus` | `0` | `--desired-vcpus` |
| `maxvCpus` | `4` | `--max-vcpus` (default caps at **one g4dn.xlarge**) |
| `instanceTypes` | `g4dn.xlarge` | `--instance-types` (comma list) |
| `allocationStrategy` | `BEST_FIT_PROGRESSIVE` (EC2) / `SPOT_CAPACITY_OPTIMIZED` (Spot) | tied to `--spot` |
| Instance **tags** (on launched workers) | `Project=agentic-cloud-task` | code `_batch_tags()` |
| CE **tags** | same | — |

### 3.3 Job queue (when created)

| Field | Baked value |
|-------|-------------|
| `state` | `ENABLED` |
| `priority` | `1` |
| `computeEnvironmentOrder` | single entry: `order: 1`, `computeEnvironment` = CE **ARN** from describe/create |
| `tags` | `Project=agentic-cloud-task` |

### 3.4 Job definition (idempotent — skips if config unchanged)

| Field | Baked value |
|-------|-------------|
| `type` | `container` |
| `platformCapabilities` | `["EC2"]` (GPU on EC2, not Fargate) |
| `parameters` | `inputS3`, `outputS3` with **placeholder** defaults (`s3://your-bucket/...`) |
| `image` | CLI `--image` or **default** `{account}.dkr.ecr.{AWS_DEFAULT_REGION}.amazonaws.com/ocr-docling-gpu:latest` |
| `resourceRequirements` | GPU `1`, VCPU `4`, MEMORY `16384` (MiB) |
| `command` | `["Ref::inputS3", "Ref::outputS3"]` (appends to image `ENTRYPOINT` → `processor.py` argv) |
| `tags` | `Project=agentic-cloud-task` |

**Now also set:** `logConfiguration` (`awslogs` driver, project log group, stream prefix `ocr`) — wired from `--log-group` / env / stack output.

**Not set in code:** `ulimits`, `environment`, `secrets`, `linuxParameters` (e.g. extra devices), retry strategy, timeout, job attempts.

### 3.5 Idempotency & failure modes

- **CE**: if name exists and status is `CREATING` / `UPDATING` / `DELETING` / `VALID` → reuse ARN; `INVALID` / `DELETED` / unknown → exit with error (no in-place CE update).
- **Queue**: exists → reuse; else create.
- **Job definition**: `_ensure_job_definition` — describes latest active revision, compares image / resources / command / parameters / IAM ARNs / logConfiguration; registers new revision only when config differs.
- **Subnets**: CLI > env > `detect_default_vpc()` auto-detect from default VPC.
- **Region / credentials**: `AWS_DEFAULT_REGION` and cloud keys from [`_env.py`](../../tools/_env.py) / `.env`; optional STS `assume-role`.

### 3.6 Environment variable names (contract)

`AGENTIC_BATCH_OCR_WORKER_SUBNETS`, `AGENTIC_BATCH_OCR_WORKER_SECURITY_GROUP_ID`, `AGENTIC_BATCH_OCR_INSTANCE_PROFILE_ARN`, `AGENTIC_BATCH_OCR_SERVICE_ROLE_ARN`, `AGENTIC_BATCH_OCR_EXECUTION_ROLE_ARN`, `AGENTIC_BATCH_OCR_JOB_ROLE_ARN`, `AGENTIC_BATCH_OCR_S3_BUCKET`, `AGENTIC_BATCH_OCR_LOG_GROUP`, `AGENTIC_BATCH_OCR_CF_STACK_NAME`.

---

## 4. Open / not yet decided (or not automated)

| Topic | Status |
|-------|--------|
| ~~**Submit job** path~~ | **Done** — [`tools/submit-ocr-batch-job.py`](../../tools/submit-ocr-batch-job.py): submit-and-wait, fetch `.md` on success or CloudWatch logs on failure. |
| ~~**Logging**~~ | **Done** — job def sets `logConfiguration` (`awslogs`, project log group, prefix `ocr`). |
| **Multi-bucket or prefix-scoped IAM** | Template is **one bucket**; cross-account or least-prefix S3 policy is future work. |
| **Spot** | `--spot` exists; Spot fleet IAM and quota validation not scripted. |
| **Service quotas / SLRs** | GPU vCPU limits and first-run Batch/Spot SLRs in region — manual or separate check. |
| **CE update** | Changing instance type, max vCPU, or subnets on an existing CE may require console/API update rules; script does not `UpdateComputeEnvironment`. |
| ~~**Audit**~~ | **Done (2026-04-10)** — `batch-worker-plane.profile.md` Audit §§1–4 + first-execution observations back-filled from smoke. |
| **Image scanning / lifecycle** | ECR scan on push was set in `ensure-ecr-ocr-repo.py`; Batch-specific lifecycle policies not in scope here. |

---

## 5. Development plan → full Batch instantiation

Ordered path from **current repo state** to **one successful OCR job in Batch**:

1. **IAM permission stack** — Deploy/update [`cf-cloud-permission-roles.yaml`](../../cloud/cf-cloud-permission-roles.yaml) so orchestrator has **Batch**, **ECR**, **S3**, **PassRole**, **`DescribeStacks`**, etc.
2. **Data plane bucket** — Create (or designate) **one** S3 bucket for OCR input/output; align with `OcrS3BucketName`.
3. **Batch OCR static stack** — Deploy [`cf-batch-ocr.yaml`](../../cloud/cf-batch-ocr.yaml) with correct **`VpcId`** and bucket name; record Outputs in **`cloud-resources.md`**.
4. **Network** — Subnets auto-detect from default VPC; override with `AGENTIC_BATCH_OCR_WORKER_SUBNETS` if needed.
5. **ECR image** — Ensure image is built, pushed, digest in `cloud-resources.md`; use **`--image …@sha256:…`** on provisioner when registering job def.
6. **Run provisioner** — `python tools/provision-ocr-batch.py --stack-name … [--assume-role …] [--image …@sha256:…]`; if CE is new, **wait for VALID** and re-run if queue create raced.
7. **Submit test job** — `python tools/submit-ocr-batch-job.py s3://bucket/inbox/doc.pdf s3://bucket/processed/doc/ [--assume-role …]`
8. **Verify** — Tool prints `.md` on success or CloudWatch logs on failure; add **Audit** steps to the profile for repeatability.
9. **Hardening (optional)** — Job timeout; retry strategy; Spot path; `UpdateComputeEnvironment` workflow or doc; multi-bucket IAM if needed.

---

## 6. Quick reference links

| Artifact | Path |
|----------|------|
| Profile (Target State / Apply) | [`batch-worker-plane.profile.md`](batch-worker-plane.profile.md) |
| Batch static CFN | [`cloud/cf-batch-ocr.yaml`](../../cloud/cf-batch-ocr.yaml) |
| Account IAM CFN | [`cloud/cf-cloud-permission-roles.yaml`](../../cloud/cf-cloud-permission-roles.yaml) |
| Provisioner | [`tools/provision-ocr-batch.py`](../../tools/provision-ocr-batch.py) |
| Submit tool | [`tools/submit-ocr-batch-job.py`](../../tools/submit-ocr-batch-job.py) |
| ECR repo helper | [`tools/ensure-ecr-ocr-repo.py`](../../tools/ensure-ecr-ocr-repo.py) |
| Catalog layout (example) | [`cloud-resources.example.md`](../../cloud-resources.example.md) |

---

## 7. Smoke completion (2026-04-10)

- **Batch job** reached **SUCCEEDED**; **three** objects under the chosen `processed/…` prefix (`.md`, `.json`, original basename).
- **Profile** [`batch-worker-plane.profile.md`](batch-worker-plane.profile.md): **Audit** intro + §3 submit checkpoint + **First-execution observations** (resource limits, `SameFileError`, submit UTF-8, `OCR_LOG_LEVEL`) updated for the next agent.
- **Gitignored catalog:** refresh root **`cloud-resources.md`** with current stack outputs / job def revision / ECR digest if you track operational pins there.
- **Working tree:** review uncommitted **`cloud/cf-cloud-permission-roles.yaml`** (adds `ecr:DescribeRepositories` on the orchestrator policy) and **`profiling/ocr-batch/container/processor.py`** (`OCR_LOG_LEVEL`); **`cloud/Untitled`** stray file removed if it reappears.
