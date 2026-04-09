# OCR Container Image — State Convergence Profile

Portable **Docker image** for **AWS Batch** (or `docker run` on g4):
**self-contained** fat image with the full Python stack installed inside
the image (`docker build` on the g4 host or CI).

Layers on [ocr-batch shared infrastructure](ocr-batch.profile.md) —
instance, SSH, WORKDIR, and test-media transfer must hold before this
profile applies.

**Architecture (current intent):** **Generic GPU AMI** on the host (drivers,
Docker, `nvidia-container-toolkit`). The **OCR application contract** for Batch
is the **container image** — including **Docling**, **RapidOCR**, **Paddle**, and
transitive deps (**Torch**, etc.) **in the image** when following the **fat
image** path.

**Alternate (optional):** A **thin** image (`pip` glue only) + **narrow host
bind** of Paddle from the AMI (`/opt/ocr-paddle-bind`, `PYTHONPATH=/paddle`) —
see Apply §**Alternate** and matching Audit notes. Use when minimizing registry
storage; operationally heavier than a fat image.

Container build artifacts: [`container/`](container/AGENTS.md) (Dockerfile,
processor.py, requirements.txt, bake-models.py).

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

---

## Target State

- **`Dockerfile` uses a CUDA + cuDNN8 runtime base and installs from `requirements.txt` plus Paddle for the fat path.** **Paddle's** published `paddlepaddle-gpu` wheels probe **`/usr/local/cuda/lib64/`** for **unversioned** names such as **`libcudnn.so`** and **`libcublas.so`**, while NVIDIA runtime images ship those libraries under **`/usr/lib/…`** or with **only versioned** SONAMEs (`libcublas.so.12`, etc.). The Dockerfile should **symlink** the expected names into `/usr/local/cuda/lib64/` (and use a **cuDNN 8** base — e.g. `nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04` — not cuDNN 9–only stacks for this wheel). Then: system deps + `pip install -r requirements.txt` + **`paddlepaddle-gpu`** from the official wheel index. Torch and much of Docling's stack may still arrive **transitively** via `pip`; **Paddle is not** reliably transitive from docling alone — the fat image must install it explicitly.

- **`requirements.txt` lists direct glue pins** (`docling`, `rapidocr-paddle`, `boto3`, `pydantic`, …). **`paddlepaddle-gpu` may live in the Dockerfile** (after `requirements.txt`) for the **fat** image rather than in `requirements.txt`, to keep one wheel-index line in the Dockerfile. For a **thin** variant, avoid duplicate Paddle in the image and use host bind (Alternate). **Transitive** installs (Torch, etc.) are expected for Docling when using a fat image.

- **`processor.py` implements Docling 2.x with RapidOCR paddle on CUDA and the three-output contract.** **S3 mode:** argv `<input_s3_uri> <output_s3_prefix>`. **Local mode:** `OCR_LOCAL_FILE` + `OCR_LOCAL_OUTPUT_DIR`. `RapidOcrOptions(backend="paddle", force_full_page_ocr=True)`, `AcceleratorOptions(device=CUDA)`, `format_options` for PDF and image. Outputs: `export_to_markdown()`, `export_to_dict()`, plus copy of input file. **Paddle OCR model paths** (`det`, `cls`, `rec`, `rec_keys`) are explicitly wired to baked paths in the image to prevent docling 2.85+'s `_default_models["paddle"]` lookup bug when `DOCLING_ARTIFACTS_PATH` is set.

- **All models are baked into the image at build time** via [`bake-models.py`](container/bake-models.py). No model downloads occur on container startup, which is essential for thousands of AWS Batch cold starts. Baked artifacts: **docling layout model** (`docling-project/docling-layout-heron` via HF → `/app/docling-models/`), **docling table model** (`docling-project/docling-models@v2.3.0` via HF → `/app/docling-models/`), **rapidocr paddle models** (det/cls/rec via ModelScope → `/usr/local/lib/python3.10/dist-packages/rapidocr/models/`). `DOCLING_ARTIFACTS_PATH=/app/docling-models` is set at runtime by `processor.py` (not as Dockerfile `ENV`) to avoid a version-specific path resolution bug in the OCR model factory.

- **Docker engine is available on the build/run host:** `docker --version` succeeds; **`nvidia-container-toolkit`** is installed so `docker run --gpus all` works.

- **Container image builds successfully** from `~/ocr-work/container/` and is suitable for push to ECR / use in Batch. **Registry storage cost** is usually modest versus compute; image size is an operational (pull time / disk) concern, not necessarily the primary cost driver.

- **Container smoke test passes** for the chosen variant: **fat** — `docker run` with `OCR_LOCAL_*` mounts, **no** host Paddle bind; **thin** — smoke uses **Apply** alternate mounts (`/opt/ocr-paddle-bind`, `PYTHONPATH=/paddle`). Three production artifacts under the output dir (test media under [`test-media/`](test-media/)). Smoke output shows `File exists and is valid` for all model paths — no network fetches.

- **IAM instance profile `ocr-ecr-push` is attached to `cloud-task-ocr` at launch.** The instance role carries `AmazonEC2ContainerRegistryPowerUser` (or equivalent write permissions: `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`). `aws sts get-caller-identity` on the instance succeeds without explicit credential configuration. The launching principal has `iam:PassRole` scoped to this profile ARN. Role + instance profile + permission boundary are defined in a CloudFormation template in `cloud/`.

- **ECR repository `ocr-docling-gpu` exists in the project region.** Created via `aws ecr create-repository` (idempotent; `|| true` on re-run). The repository URI is recorded in `cloud-resources.md`.

- **Container image is pushed to ECR and the digest is recorded.** Tagged as `<account>.dkr.ecr.<region>.amazonaws.com/ocr-docling-gpu:latest`; pushed with `docker push`. The **image digest** (not only `:latest`) is recorded in `cloud-resources.md` for use in Batch job definitions.

---

## Apply

#### 1. Ensure Docker availability

```bash
docker --version
dpkg -l | grep nvidia-container-toolkit
```

Install if missing:

```bash
sudo apt-get update
sudo apt-get install -y docker.io nvidia-container-toolkit
sudo usermod -aG docker ubuntu
sudo systemctl restart docker
```

#### 2. Build container image

```bash
cd ~/ocr-work/container
docker build -t ocr-docling-gpu:latest .
```

#### 3. Create ECR repository and push image

Prerequisites: IAM instance profile attached (Apply §3-pre below), or AWS credentials available in the environment. Run from the instance (role-based auth) or the workstation (env credentials).

**3-pre. IAM + ECR setup (workstation, one-time)**

Deploy the CloudFormation template from `cloud/` that creates the `ocr-ecr-push` role, instance profile, and `iam:PassRole` grant. Confirm the launching user's policy includes `iam:PassRole` on the profile ARN before the next instance launch. Update `tools/launch-spot-instance.py` to accept and pass `--iam-instance-profile`.

**3a. Create repository (idempotent):**

```bash
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
aws ecr create-repository --repository-name ocr-docling-gpu --region "$REGION" || true
```

Record the `repositoryUri` output in `cloud-resources.md`.

**3b. Authenticate Docker to ECR:**

```bash
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
```

**3c. Tag and push:**

```bash
REPO_URI="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/ocr-docling-gpu"
docker tag ocr-docling-gpu:latest "${REPO_URI}:latest"
docker push "${REPO_URI}:latest"
```

**3d. Record digest:**

```bash
docker inspect --format='{{index .RepoDigests 0}}' "${REPO_URI}:latest"
```

Paste the `sha256:…` digest into `cloud-resources.md` alongside the repository URI. Use the digest (not `:latest`) in Batch job definitions.

#### 4. GPU sanity in container

```bash
docker run --rm --gpus all --entrypoint nvidia-smi ocr-docling-gpu:latest
```

#### 5. Container smoke — **fat image** (default)

No host Paddle bind; stack comes from the image.

```bash
mkdir -p ~/ocr-work/product
docker run --rm --gpus all \
  -v /home/ubuntu:/host \
  -e OCR_LOCAL_FILE=/host/ocr-work/sample_scan/service-invoice.jpg \
  -e OCR_LOCAL_OUTPUT_DIR=/host/ocr-work/product \
  ocr-docling-gpu:latest
```

### Alternate — thin image + Paddle bind

Use when the image is built **without** full Paddle in the image and Paddle must
come from the host (narrow bind). **Host poke** ([ocr-batch Apply §4](ocr-batch.profile.md))
must have populated site-packages first.

#### A. Expose AMI Paddle to the container

After [ocr-batch Apply §4](ocr-batch.profile.md), **`sudo pip3`** installs into **`/usr/local/lib/python3.10/dist-packages/`** on Ubuntu 22.04. The thin image has **`docling`** / **`rapidocr-paddle`** / transitives; **Paddle** may come from the host.

**Why a narrow bind:** `PYTHONPATH` is **prepended**. Do **not** mount the full host `dist-packages` — it can shadow `docling` / Torch from the image.

Create **`/opt/ocr-paddle-bind`** with symlinks to **`paddle*`** top-level names under site-packages:

```bash
SITE=/usr/local/lib/python3.10/dist-packages
sudo mkdir -p /opt/ocr-paddle-bind
cd "$SITE" && for d in paddle*; do
  [ -e "$d" ] || continue
  sudo ln -sfn "$SITE/$d" "/opt/ocr-paddle-bind/$d"
done
```

**Quick sanity:**

```bash
docker run --rm --gpus all \
  -v /opt/ocr-paddle-bind:/paddle:ro \
  -e PYTHONPATH=/paddle \
  --entrypoint python3 ocr-docling-gpu:latest \
  -c "import paddle; assert paddle.device.cuda.device_count() >= 1; print('PASS: paddle in container', paddle.__version__)"
```

#### B. Container smoke — **thin** + bind

```bash
mkdir -p ~/ocr-work/product
docker run --rm --gpus all \
  -v /opt/ocr-paddle-bind:/paddle:ro \
  -e PYTHONPATH=/paddle \
  -v /home/ubuntu:/host \
  -e OCR_LOCAL_FILE=/host/ocr-work/sample_scan/service-invoice.jpg \
  -e OCR_LOCAL_OUTPUT_DIR=/host/ocr-work/product \
  ocr-docling-gpu:latest
```

---

## Audit

Repo contract checks (§1–§3): workstation or instance with repo. On-instance
runtime checks (§4 onward): on `cloud-task-ocr`. ECR/IAM checks (§8–§10):
require IAM instance profile attached.

### Repo contract

#### 1. Dockerfile and base image

```bash
test -f profiling/ocr-batch/container/Dockerfile && echo "PASS" || echo "FAIL"
grep -q 'FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04' profiling/ocr-batch/container/Dockerfile && echo "PASS: FROM (CUDA + cuDNN8 for Paddle)" || echo "FAIL"
grep -qiE 'paddlepaddle-gpu' profiling/ocr-batch/container/Dockerfile && echo "PASS: paddle in Dockerfile (fat)" || echo "FAIL"
```

Expected: three PASS lines. **Fat** default: explicit `paddlepaddle-gpu` install in the Dockerfile (or equivalent single `pip` layer). **Thin** variant: Dockerfile omits Paddle — use Audit §**11** and Apply **Alternate** instead; this check would be adapted for that track.

#### 2. requirements.txt lists direct glue deps

```bash
grep -q 'docling' profiling/ocr-batch/container/requirements.txt && echo "PASS: docling" || echo "FAIL"
grep -q 'rapidocr-paddle' profiling/ocr-batch/container/requirements.txt && echo "PASS: rapidocr-paddle" || echo "FAIL"
grep -q 'boto3' profiling/ocr-batch/container/requirements.txt && echo "PASS: boto3" || echo "FAIL"
grep -q 'pydantic' profiling/ocr-batch/container/requirements.txt && echo "PASS: pydantic" || echo "FAIL"
grep -v '^#' profiling/ocr-batch/container/requirements.txt | grep -qE 'paddlepaddle-gpu' && echo "SKIP or FAIL: paddle also in requirements (optional; fat uses Dockerfile)" || echo "PASS: paddle not duplicated in requirements"
```

Expected: five PASS lines from the `docling` … `pydantic` greps, plus the last line. **Fat** default installs Paddle in the **Dockerfile**, not necessarily in `requirements.txt`. (Torch may be **transitive**.)

#### 3. processor.py uses Docling 2.x paddle API

```bash
grep -q 'format_options' profiling/ocr-batch/container/processor.py && echo "PASS: format_options" || echo "FAIL"
grep -q 'backend="paddle"' profiling/ocr-batch/container/processor.py && echo "PASS: paddle backend" || echo "FAIL"
grep -q 'OCR_LOCAL_FILE' profiling/ocr-batch/container/processor.py && echo "PASS: OCR_LOCAL_FILE" || echo "FAIL"
grep -q 'OCR_LOCAL_OUTPUT_DIR' profiling/ocr-batch/container/processor.py && echo "PASS: OCR_LOCAL_OUTPUT_DIR" || echo "FAIL"
grep -q 'export_to_dict' profiling/ocr-batch/container/processor.py && echo "PASS: export_to_dict" || echo "FAIL"
grep -q 'ImageFormatOption' profiling/ocr-batch/container/processor.py && echo "PASS: ImageFormatOption" || echo "FAIL"
grep -q 'shutil.copy2' profiling/ocr-batch/container/processor.py && echo "PASS: original preserved" || echo "FAIL"
```

Expected: seven PASS lines.

### On-instance runtime

#### 4. Docker available on instance

```bash
docker --version && echo "PASS: docker" || echo "FAIL"
docker info 2>/dev/null | grep -q 'nvidia.com/gpu' && echo "PASS: nvidia CDI/runtime" || echo "FAIL"
```

Expected: two PASS lines.

#### 5. Image exists (after build)

```bash
docker images ocr-docling-gpu --format '{{.Repository}}:{{.Tag}}' | grep -q 'ocr-docling-gpu:latest' \
    && echo "PASS: image exists" || echo "FAIL"
```

#### 6. NVIDIA device in container

```bash
docker run --rm --gpus all --entrypoint nvidia-smi ocr-docling-gpu:latest \
    --query-gpu=name --format=csv,noheader && echo "PASS: nvidia-smi" || echo "FAIL"
```

#### 7. Container smoke — three artifacts (**fat** path)

After Apply §**5** (fat smoke), on-instance:

```bash
test -s ~/ocr-work/product/service-invoice.md && echo "PASS: markdown" || echo "FAIL"
test -s ~/ocr-work/product/service-invoice.json && echo "PASS: json" || echo "FAIL"
test -f ~/ocr-work/product/service-invoice.jpg && echo "PASS: original" || echo "FAIL"
```

Adjust basename to match `OCR_LOCAL_FILE`. Expected: three PASS lines.

**Repo-local helper (same contract, paths via `/work` mount):** with test media under [`test-media/`](test-media/) and the image built (`ocr-docling-gpu:latest`):

```bash
profiling/ocr-batch/container/run-local-smoke.sh
# optional: --input profiling/ocr-batch/test-media/water-bill.jpg --out-dir profiling/ocr-batch/smoke-out
```

Writes to `profiling/ocr-batch/smoke-out/` by default (gitignored). `--dry-run` prints the `docker run` command without executing.

#### 8. IAM instance profile attached (on-instance)

```bash
aws sts get-caller-identity --query 'Arn' --output text && echo "PASS: instance has IAM identity" || echo "FAIL: no credentials"
```

Expected: ARN containing the role name (e.g. `assumed-role/ocr-ecr-push/i-…`) and `PASS` line.

#### 9. ECR repository exists

```bash
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
aws ecr describe-repositories --repository-names ocr-docling-gpu --region "$REGION" \
  --query 'repositories[0].repositoryUri' --output text && echo "PASS: ECR repo exists" || echo "FAIL"
```

Expected: repository URI line and `PASS`.

#### 10. Image pushed to ECR (digest recorded)

```bash
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws ecr describe-images --repository-name ocr-docling-gpu --region "$REGION" \
  --image-ids imageTag=latest --query 'imageDetails[0].imageDigest' --output text \
  && echo "PASS: image in ECR" || echo "FAIL"
```

Expected: `sha256:…` digest and `PASS`. Cross-check digest against `cloud-resources.md`.

#### 11. Paddle import in container (**thin** path only)

When converging the **thin + bind** alternate: **`/opt/ocr-paddle-bind`** per Apply §**Alternate A**.

```bash
docker run --rm --gpus all \
  -v /opt/ocr-paddle-bind:/paddle:ro \
  -e PYTHONPATH=/paddle \
  --entrypoint python3 ocr-docling-gpu:latest \
  -c "import paddle; assert paddle.device.cuda.device_count() >= 1; print('PASS: paddle in container')" \
  && echo "PASS: paddle bind" || echo "FAIL: paddle bind"
```

**N/A** when only the **fat** image track is converged (Paddle is inside the image).

#### 12. Container smoke — three artifacts (**thin** path only)

After Apply §**Alternate B**, same file checks as §**7**. **N/A** for fat-only.
