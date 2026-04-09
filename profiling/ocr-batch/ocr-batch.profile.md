# OCR Batch Processing — State Convergence Profile

GPU-accelerated OCR batch processing using **Docling** + **RapidOCR
`backend="paddle"`** (PaddlePaddle on GPU). This profile supports **two
convergence tracks** on the same generic host (typically **AWS Deep Learning
Base GPU AMI** + [base-gpu-node](../aws-deep-learning-base/base-gpu-node.profile.md)):

| Track | Purpose | Retained artifact |
|-------|---------|-------------------|
| **Host poke** | Interactive experimentation on the instance — import checks, [`poke-smoke-test.py`](container/poke-smoke-test.py), benchmarks — **without** requiring a container. | Native Python stack on the AMI (or long-lived instance). |
| **Container image** | Portable artifact for **AWS Batch** (or `docker run`): **self-contained image** with the full Python stack installed **inside** the image (`docker build` on the g4 host or CI). | **ECR image** (pin **digest** in job definitions). |

**You may converge one track or both.** Shared infrastructure (instance, WORKDIR,
transferred `container/` + test media) supports either; only the track you care
about needs its Apply steps and Audit checks.

**Architecture (current intent):** **Generic GPU AMI** on the host (drivers,
Docker, `nvidia-container-toolkit`). The **OCR application contract** for Batch
is the **container image** — including **Docling**, **RapidOCR**, **Paddle**, and
transitive deps (**Torch**, etc.) **in the image** when following the **fat
image** path. **Host poke** still uses **native `pip`** on the AMI for fast
iteration; that stack does not have to byte-match the image, but **pin
versions in repo** when you need reproducibility.

**Alternate (optional):** A **thin** image (`pip` glue only) + **narrow host
bind** of Paddle from the AMI (`/opt/ocr-paddle-bind`, `PYTHONPATH=/paddle`) —
see Apply §**Alternate — thin image + Paddle bind** and matching Audit notes.
Use when minimizing registry storage; operationally heavier than a fat image.

**Native Python for poke, not venv:** Host poke convergence assumes **system
`python3`** (or one declared `/opt/…` prefix) — not a long-lived `WORKDIR/venv`.

Layers on [aws-deep-learning-base](../aws-deep-learning-base/base-gpu-node.profile.md)
— must hold before this profile applies.

**Headless auth** (`agent`, `gh`): [headless-auth](../headless-auth/headless-auth.profile.md)
— user-interactive; defer until needed.

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

Container build artifacts: [`container/`](container/AGENTS.md) (Dockerfile,
processor.py, requirements.txt).

---

## Target State

### Shared infrastructure (both tracks)

Default **slug `ocr`**: EC2 Name **`cloud-task-ocr`**, SSH Host
**`cloud-task-ocr`**.

- **A running OCR batch instance is launched and tracked in `cloud-resources.md`.** Name **`cloud-task-ocr`**, `--tag` matches [`tools/launch-spot-instance.py`](../../tools/launch-spot-instance.py). Gitignored [**`cloud-resources.md`**](../../cloud-resources.md) **Nodes** row: Name, SSH Host, Instance ID, Public IP, Region, Type, Status, WORKDIR, Notes — current per [AGENTS.md](../../AGENTS.md). Market type is a launch-time parameter: **spot** (cost-sensitive batch work) or **on-demand** (AMI-bake builds, endurance guarantee).

- **SSH is profiled on the controlling machine.** **`Host cloud-task-ocr`**, **HostName** = instance public IP; User / IdentityFile per [dev-workstation](../local-dev-env/dev-workstation.profile.md). **`cloud-resources.md`** SSH (current) lists usable commands while running.

- **WORKDIR is `~/ocr-work`.** `/home/ubuntu/ocr-work` is the working directory on the instance — OCR files, run outputs, and container build context live under this root. WORKDIR is flat (not inside the project repo clone). Test media from [`test-media/`](test-media/) is present under `~/ocr-work/sample_scan/` when this profile’s transfer steps have been run.

- **Agent CLI and GitHub CLI are authenticated** per [headless-auth](../headless-auth/headless-auth.profile.md). User-interactive — defer until an on-instance session requires it.

- **GPU is accessible on the host.** `nvidia-smi` reports a GPU (e.g. Tesla T4 on `g4dn`).

### Track: Host poke (optional)

Converge this track when the goal is **interactive OCR on the instance** (scripts, agents, benchmarks) **without** relying on a container for execution.

- **AMI supports Docling + paddle via native Python and a clean install lineage.** **`paddlepaddle-gpu`**, **Docling**, and **`rapidocr-paddle`** are installed for **`python3` on `PATH`** (AMI bake owns exact pins). **`import paddle`** reports **≥1 CUDA device**; **`import docling`** succeeds; [`poke-smoke-test.py`](container/poke-smoke-test.py) converts a test image to markdown on GPU **without Docker**; scripts such as [`r3-paddle.py`](dev-benchmark/r3-paddle.py) can run end-to-end.

### Track: Container image (optional)

Converge this track when the goal is a **docker image** for **Batch** (or repeatable `docker run` on g4). **Fat image (default intent):** `docker build` installs dependencies **inside** the image (`requirements.txt` → `pip`); the **host AMI stays generic** — no application-specific native stack required on Batch workers beyond Docker + NVIDIA runtime.

- **`Dockerfile` uses a CUDA-capable base and installs from `requirements.txt`.** Typical pattern: `FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04`; system deps + `pip install -r requirements.txt` — **no** need to list every transitive in the Dockerfile if `pip` resolves them (Torch may arrive via **docling**).

- **`requirements.txt` lists direct glue pins** (`docling`, `rapidocr-paddle`, `boto3`, `pydantic`, …). It must **not** pin forbidden **direct** lines for stacks you are avoiding by design (e.g. duplicate `paddlepaddle-gpu` if Paddle is host-bound in a **thin** variant — see Alternate). **Transitive** installs (Torch, etc.) are expected for Docling when using a fat image.

- **`processor.py` implements Docling 2.x with RapidOCR paddle on CUDA and the three-output contract.** **S3 mode:** argv `<input_s3_uri> <output_s3_prefix>`. **Local mode:** `OCR_LOCAL_FILE` + `OCR_LOCAL_OUTPUT_DIR`. `RapidOcrOptions(backend="paddle", force_full_page_ocr=True)`, `AcceleratorOptions(device=CUDA)`, `format_options` for PDF and image. Outputs: `export_to_markdown()`, `export_to_dict()`, plus copy of input file.

- **Docker engine is available on the build/run host:** `docker --version` succeeds; **`nvidia-container-toolkit`** is installed so `docker run --gpus all` works.

- **Container image builds successfully** from `~/ocr-work/container/` and is suitable for push to ECR / use in Batch. **Registry storage cost** is usually modest versus compute; image size is an operational (pull time / disk) concern, not necessarily the primary cost driver.

- **Container smoke test passes** for the chosen variant: **fat** — `docker run` with `OCR_LOCAL_*` mounts, **no** host Paddle bind; **thin** — smoke uses **Apply** alternate mounts (`/opt/ocr-paddle-bind`, `PYTHONPATH=/paddle`). Three production artifacts under the output dir (test media under [`test-media/`](test-media/)).

---

## Apply

Sections are grouped by **shared** steps, **host poke**, **container image (fat)**, and **alternate thin+bind**. Execute only what matches your chosen track(s).

### Shared — launch, WORKDIR, transfer

#### 1. Launch instance (workstation)

Project `venv/`, `.env` loaded; AMI from `cloud-resources.md`; slug `ocr`.

**Spot** (batch work):
```bash
python tools/launch-spot-instance.py \
    --ami <ami-id-from-cloud-resources.md> \
    --instance-type g4dn.xlarge \
    --volume-gb 125 \
    --tag cloud-task-ocr \
    --instance-initiated-shutdown-behavior terminate
```

**On-demand** (AMI-bake / endurance):
```bash
python tools/launch-spot-instance.py \
    --ami <ami-id-from-cloud-resources.md> \
    --instance-type g4dn.xlarge \
    --volume-gb 125 \
    --tag cloud-task-ocr \
    --market-type on-demand \
    --instance-initiated-shutdown-behavior stop
```

Update `cloud-resources.md` (Nodes row, SSH section). Converge
[base-gpu-node](../aws-deep-learning-base/base-gpu-node.profile.md) if
needed.

#### 2. WORKDIR

```bash
mkdir -p ~/ocr-work
```

Set WORKDIR in `cloud-resources.md`.

#### 3. Transfer files to instance

```bash
rsync -avz profiling/ocr-batch/container/    cloud-task-ocr:~/ocr-work/container/
rsync -avz profiling/ocr-batch/test-media/   cloud-task-ocr:~/ocr-work/sample_scan/
rsync -avz profiling/ocr-batch/container/poke-smoke-test.py cloud-task-ocr:~/ocr-work/poke-smoke-test.py
```

*Windows workstation*: `rsync` is not available natively. Use `scp -r` but
pre-create the target directory (`ssh cloud-task-ocr "mkdir -p …"`) first,
and note that `scp -r dir/ host:dest/` nests the source directory name
inside `dest/` — flatten or adjust accordingly.

### Host poke — native Python stack

#### 4. AMI: native Python for poke (bake recipe)

Install **`paddlepaddle-gpu`**, **Docling**, and **`rapidocr-paddle`** with
the **system** interpreter — not into a venv.

```bash
sudo pip3 install paddlepaddle-gpu==2.6.2 -f https://www.paddlepaddle.org.cn/whl/linux/mkl/avx/stable.html
sudo pip3 install docling rapidocr-paddle
```

Fix RapidOCR models directory permissions for non-root model download:

```bash
sudo chmod -R 777 /usr/local/lib/python3.10/dist-packages/rapidocr/models
```

Confirmed working combination (2026-04-09 rebuild): `paddlepaddle-gpu`
**2.6.2**, `docling` **2.85.0**, `rapidocr-paddle` **1.4.5**, `torch`
**2.11.0** (transitive dep of docling), Python **3.10.12**, CUDA toolkit
**12.9**, driver **580.126.09**, Tesla T4.

Smoke:

```bash
python3 -c "import paddle; import docling; print('poke ok', paddle.__version__, paddle.device.cuda.device_count())"
```

End-to-end OCR smoke:

```bash
python3 ~/ocr-work/poke-smoke-test.py ~/ocr-work/sample_scan/service-invoice.jpg
```

### Shared — headless auth (deferred — user-interactive)

#### 5. Headless auth

Per [headless-auth](../headless-auth/headless-auth.profile.md): `agent`
prompt, `gh auth login`, `gh auth setup-git`. Defer until an on-instance
session requires it.

### Container image — Docker, build, run

#### 6. Ensure Docker availability

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

#### 7. Build container image

```bash
cd ~/ocr-work/container
docker build -t ocr-docling-gpu:latest .
```

#### 8. Push to ECR (stub — fill region, account, repo from your AWS layout)

After local validation, tag and push so Batch can reference **immutable digests**:

```bash
# Example only — replace ACCOUNT, REGION, REPO
# aws ecr get-login-password --region REGION | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.REGION.amazonaws.com
# docker tag ocr-docling-gpu:latest ACCOUNT.dkr.ecr.REGION.amazonaws.com/REPO:latest
# docker push ACCOUNT.dkr.ecr.REGION.amazonaws.com/REPO:latest
```

Record the pushed **digest** in Batch job definitions / runbooks (not only `:latest`).

#### 9. GPU sanity in container

```bash
docker run --rm --gpus all --entrypoint nvidia-smi ocr-docling-gpu:latest
```

#### 10. Container smoke — **fat image** (default)

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
come from the host (narrow bind). **Host poke** (Apply §4) must have populated
site-packages first.

#### A. Expose AMI Paddle to the container

After Apply §4, **`sudo pip3`** installs into **`/usr/local/lib/python3.10/dist-packages/`** on Ubuntu 22.04. The thin image has **`docling`** / **`rapidocr-paddle`** / transitives; **Paddle** may come from the host.

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

Run **Shared** checks for any convergence. Run **Host poke** checks only when
that track is in scope. Run **Container image** checks only when building or
validating the image. **N/A** is acceptable for skipped tracks.

Workstation checks: §1–§2. Instance (on `cloud-task-ocr`): §3 onward.

### Shared

#### 1. Instance tracked in `cloud-resources.md`

```bash
python tools/launch-spot-instance.py --tag cloud-task-ocr --check
```

Expected: `PASS: running instance i-… @ <ip> (tag=cloud-task-ocr)`

#### 2. SSH profiled

```bash
ssh -G cloud-task-ocr 2>/dev/null | grep -i '^hostname '
```

Expected: `hostname <public-ip>` matching `cloud-resources.md`.

#### 3. WORKDIR exists with test media (on-instance)

```bash
test -d ~/ocr-work && echo "PASS: WORKDIR" || echo "FAIL: WORKDIR"
ls ~/ocr-work/sample_scan/*.jpg >/dev/null 2>&1 && echo "PASS: test media" || echo "FAIL: test media"
```

Expected: two PASS lines.

#### 4. Auth (deferred — user-interactive)

```bash
gh --version >/dev/null 2>&1 && echo "PASS: gh" || echo "SKIP: gh not installed"
gh auth status >/dev/null 2>&1 && echo "PASS: gh auth" || echo "SKIP: gh auth"
```

SKIP is acceptable when auth is deferred.

#### 5. GPU accessible (on-instance)

```bash
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader && echo "PASS: GPU"
```

Expected: `Tesla T4, …` then `PASS: GPU`

### Host poke

#### 6. Poke stack — imports + OCR smoke (on-instance)

Use the system interpreter (not a venv):

```bash
python3 -c "import paddle; import docling; assert paddle.device.cuda.device_count() >= 1; print('PASS: poke imports')" 2>/dev/null || echo "FAIL: poke imports"
```

End-to-end OCR ([`poke-smoke-test.py`](container/poke-smoke-test.py)):

```bash
python3 ~/ocr-work/poke-smoke-test.py ~/ocr-work/sample_scan/service-invoice.jpg
```

Expected: `PASS: poke imports` and `PASS: poke smoke (…)`.

### Container image — repo contract (workstation or instance with repo)

#### 7. Dockerfile and base image

```bash
test -f profiling/ocr-batch/container/Dockerfile && echo "PASS" || echo "FAIL"
grep -q 'FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04' profiling/ocr-batch/container/Dockerfile && echo "PASS: FROM" || echo "FAIL"
! grep -qiE 'paddlepaddle-gpu' profiling/ocr-batch/container/Dockerfile && echo "PASS: no paddle in Dockerfile" || echo "FAIL"
```

Expected: three PASS lines. (Paddle may be transitive via `pip` in the image — the Dockerfile itself should not `pip install paddlepaddle-gpu` when using a **fat** image with docling; **thin** variant also avoids explicit Paddle in Dockerfile.)

#### 8. requirements.txt lists direct glue deps

```bash
grep -q 'docling' profiling/ocr-batch/container/requirements.txt && echo "PASS: docling" || echo "FAIL"
grep -q 'rapidocr-paddle' profiling/ocr-batch/container/requirements.txt && echo "PASS: rapidocr-paddle" || echo "FAIL"
grep -q 'boto3' profiling/ocr-batch/container/requirements.txt && echo "PASS: boto3" || echo "FAIL"
grep -q 'pydantic' profiling/ocr-batch/container/requirements.txt && echo "PASS: pydantic" || echo "FAIL"
grep -v '^#' profiling/ocr-batch/container/requirements.txt | grep -qE 'paddlepaddle-gpu' && echo "FAIL: explicit paddle wheel" || echo "PASS: no explicit paddle in requirements"
```

Expected: five PASS lines. (Torch may be **transitive** — do not require absence from `requirements.txt` unless using a thin strategy that forbids it.)

#### 9. processor.py uses Docling 2.x paddle API

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

### Container image — on-instance runtime

#### 10. Docker available on instance

```bash
docker --version && echo "PASS: docker" || echo "FAIL"
docker info 2>/dev/null | grep -q 'nvidia.com/gpu' && echo "PASS: nvidia CDI/runtime" || echo "FAIL"
```

Expected: two PASS lines.

#### 11. Image exists (after build)

```bash
docker images ocr-docling-gpu --format '{{.Repository}}:{{.Tag}}' | grep -q 'ocr-docling-gpu:latest' \
    && echo "PASS: image exists" || echo "FAIL"
```

#### 12. NVIDIA device in container

```bash
docker run --rm --gpus all --entrypoint nvidia-smi ocr-docling-gpu:latest \
    --query-gpu=name --format=csv,noheader && echo "PASS: nvidia-smi" || echo "FAIL"
```

#### 13. Container smoke — three artifacts (**fat** path)

After Apply §**10** (fat smoke), on-instance:

```bash
test -s ~/ocr-work/product/service-invoice.md && echo "PASS: markdown" || echo "FAIL"
test -s ~/ocr-work/product/service-invoice.json && echo "PASS: json" || echo "FAIL"
test -f ~/ocr-work/product/service-invoice.jpg && echo "PASS: original" || echo "FAIL"
```

Adjust basename to match `OCR_LOCAL_FILE`. Expected: three PASS lines.

#### 14. Paddle import in container (**thin** path only)

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

#### 15. Container smoke — three artifacts (**thin** path only)

After Apply §**Alternate B**, same file checks as §**13**. **N/A** for fat-only.

---

## Appendix A — Torch-first path (historical reference)

The original profiled default was **RapidOCR `backend="torch"`** with a
**venv** at `WORKDIR/venv` and **`onnxruntime-gpu` ≤1.22** for Docling
layout/table models. This path is superseded by the paddle + native-install
host poke and fat container tracks above; retained for reference only.

Key differences from the current target:

| Concern | Torch path (historical) | Paddle path (current) |
|---------|------------------------|----------------------|
| OCR backend | `RapidOcrOptions(backend="torch")` | `RapidOcrOptions(backend="paddle")` |
| Python env | `WORKDIR/venv` | System python (native pip) for poke |
| onnxruntime-gpu | Required, pinned ≤1.22 | Not required |
| Smoke test | PDF via torch pipeline | Image via [`poke-smoke-test.py`](container/poke-smoke-test.py) |

Torch install fragment (historical):

```bash
cd /home/ubuntu/ocr-work
python3 -m venv venv && source venv/bin/activate
pip install "docling[rapidocr]" "onnxruntime-gpu<1.23"
venv/bin/python -c "import torch; assert torch.cuda.is_available()"
```

**`onnxruntime-gpu` ≥1.23 note:** uses DRM-based device discovery that
fails on EC2 g4dn (`/sys/class/drm/card0/device/vendor` missing); pin to
≤1.22 if using this path.

---

## Appendix B — Historical benchmark matrix

Retained for timing/spacing experiments; not part of convergence.

| Round | Script | Notes |
|-------|--------|--------|
| 1 | [`dev-benchmark/r1-onnx.py`](dev-benchmark/r1-onnx.py) | ONNX RapidOCR; CUDA vs CPU Docling |
| 2 | [`dev-benchmark/r2-torch.py`](dev-benchmark/r2-torch.py) | Torch baseline (historical default) |
| 3 | [`dev-benchmark/r3-paddle.py`](dev-benchmark/r3-paddle.py) | Paddle |
| 4–6 | [`r4-onnx-spacing.py`](dev-benchmark/r4-onnx-spacing.py) … [`r6-paddle-spacing.py`](dev-benchmark/r6-paddle-spacing.py) | GPU-only, spacing params |
| 7 | [`dev-benchmark/r7-paddle-tuned.py`](dev-benchmark/r7-paddle-tuned.py) | Paddle tuned |

Spacing heuristics: [`ocr-spacing-assess.py`](dev-benchmark/ocr-spacing-assess.py).
Session note: [`2026-04-08_spacing-assess-latest-lot.md`](dev-benchmark/2026-04-08_spacing-assess-latest-lot.md).

---
