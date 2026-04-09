# OCR Batch Processing — State Convergence Profile

GPU-accelerated OCR batch processing using **Docling** + **RapidOCR
`backend="paddle"`** (PaddlePaddle on GPU). This profile owns **shared
infrastructure** and the optional **host poke** track. Two companion profiles
cover the container and Batch worker planes:

| Track | Profile | Purpose |
|-------|---------|---------|
| **Shared infrastructure** | _(this file)_ | Instance, SSH, WORKDIR, test media transfer |
| **Host poke** | _(this file)_ | Interactive experimentation on the instance — no container |
| **Container image** | [container-image.profile.md](container-image.profile.md) | Portable Docker image → ECR (fat default; thin alternate) |
| **AWS Batch worker plane** | [batch-worker-plane.profile.md](batch-worker-plane.profile.md) | Managed GPU workers, S3 in/out, scale-to-zero |

**You may converge any subset of tracks.** Shared infrastructure supports all
downstream tracks. Container image layers on shared; Batch worker plane layers
on both shared and container image.

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

### Shared infrastructure

Default **slug `ocr`**: EC2 Name **`cloud-task-ocr`**, SSH Host
**`cloud-task-ocr`**.

- **A running OCR batch instance is launched and tracked in `cloud-resources.md`.** Name **`cloud-task-ocr`**, `--tag` matches [`tools/launch-spot-instance.py`](../../tools/launch-spot-instance.py). Gitignored [**`cloud-resources.md`**](../../cloud-resources.md) **Nodes** row: Name, SSH Host, Instance ID, Public IP, Region, Type, Status, WORKDIR, Notes — current per [AGENTS.md](../../AGENTS.md). Market type is a launch-time parameter: **spot** (cost-sensitive batch work) or **on-demand** (AMI-bake builds, endurance guarantee).

- **SSH is profiled on the controlling machine.** **`Host cloud-task-ocr`**, **HostName** = instance public IP; User / IdentityFile per [dev-workstation](../local-dev-env/dev-workstation.profile.md). **`cloud-resources.md`** SSH (current) lists usable commands while running.

- **WORKDIR is `~/ocr-work`.** `/home/ubuntu/ocr-work` is the working directory on the instance — OCR files, run outputs, and container build context live under this root. WORKDIR is flat (not inside the project repo clone). Test media from [`test-media/`](test-media/) is present under `~/ocr-work/sample_scan/` when this profile's transfer steps have been run.

- **Agent CLI and GitHub CLI are authenticated** per [headless-auth](../headless-auth/headless-auth.profile.md). User-interactive — defer until an on-instance session requires it.

- **GPU is accessible on the host.** `nvidia-smi` reports a GPU (e.g. Tesla T4 on `g4dn`).

### Track: Host poke (optional)

Converge this track when the goal is **interactive OCR on the instance** (scripts, agents, benchmarks) **without** relying on a container for execution.

- **AMI supports Docling + paddle via native Python and a clean install lineage.** **`paddlepaddle-gpu`**, **Docling**, and **`rapidocr-paddle`** are installed for **`python3` on `PATH`** (AMI bake owns exact pins). **`import paddle`** reports **≥1 CUDA device**; **`import docling`** succeeds; [`poke-smoke-test.py`](container/poke-smoke-test.py) converts a test image to markdown on GPU **without Docker**; scripts such as [`r3-paddle.py`](dev-benchmark/r3-paddle.py) can run end-to-end.

---

## Apply

Sections cover **shared** infrastructure and **host poke**. Container image and
Batch worker plane steps are in their companion profiles.

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

---

## Audit

Run **Shared** checks for any convergence. Run **Host poke** checks only when
that track is in scope. Container image and Batch worker plane checks are in
their companion profiles.

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

---

## Appendix A — Torch-first path (historical reference)

The original profiled default was **RapidOCR `backend="torch"`** with a
**venv** at `WORKDIR/venv` and **`onnxruntime-gpu` ≤1.22** for Docling
layout/table models. This path is superseded by the paddle + native-install
host poke track (this file) and fat container track
([container-image.profile.md](container-image.profile.md)); retained for
reference only.

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
