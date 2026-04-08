# OCR Batch Processing — State Convergence Profile

GPU-accelerated OCR batch processing using **Docling** + **RapidOCR
`backend="paddle"`** (PaddlePaddle on GPU). Covers the full workflow from
instance launch through **baked AMI** and **published thin container** for
AWS Batch.

**Architecture:** **PaddlePaddle GPU** and the native Python stack live on
the **custom AMI** (declarative bake). The container image carries only
lightweight Python deps (`docling`, `rapidocr-paddle`, `boto3`, `pydantic`)
— **no** `paddlepaddle-gpu`, **no** Torch/ONNX GPU wheels in the image.

**Native Python, not venv:** Convergence assumes **system Python** (or a
single `/opt/…` prefix on `PATH`) — **not** a long-lived `WORKDIR/venv`.
Rebuild from a clean base AMI and bake native installs so the disk carries
no conflicting stacks.

Layers on [aws-deep-learning-base](../aws-deep-learning-base/base-gpu-node.profile.md)
— must hold before this profile applies.

**Headless auth** (`agent`, `gh`): [headless-auth](../headless-auth/headless-auth.profile.md)
— user-interactive; defer until needed.

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

Container build artifacts: [`container/`](container/AGENTS.md) (Dockerfile,
processor.py, requirements.txt).

---

## Target State

### Infrastructure

Default **slug `ocr`**: EC2 Name **`cloud-task-ocr`**, SSH Host
**`cloud-task-ocr`**.

- **A running OCR batch instance is launched and tracked in `cloud-resources.md`.** Name **`cloud-task-ocr`**, `--tag` matches [`tools/launch-spot-instance.py`](../../tools/launch-spot-instance.py). Gitignored [**`cloud-resources.md`**](../../cloud-resources.md) **Nodes** row: Name, SSH Host, Instance ID, Public IP, Region, Type, Status, WORKDIR, Notes — current per [AGENTS.md](../../AGENTS.md). Market type is a launch-time parameter: **spot** (cost-sensitive batch work) or **on-demand** (AMI-bake builds, endurance guarantee).

- **SSH is profiled on the controlling machine.** **`Host cloud-task-ocr`**, **HostName** = instance public IP; User / IdentityFile per [dev-workstation](../local-dev-env/dev-workstation.profile.md). **`cloud-resources.md`** SSH (current) lists usable commands while running.

- **WORKDIR is `~/ocr-work`.** `/home/ubuntu/ocr-work` is the working directory on the instance — all OCR operations, transferred files, run outputs, and container artifacts live under this root. WORKDIR is flat (not inside the project repo clone). Test media from [`test-media/`](test-media/) is present under `~/ocr-work/sample_scan/`.

- **Agent CLI and GitHub CLI are authenticated** per [headless-auth](../headless-auth/headless-auth.profile.md). User-interactive — defer until an on-instance session requires it.

### AMI poke stack (native Python, paddle)

- **AMI supports Docling + paddle poke via native Python and a clean bake lineage.** **`paddlepaddle-gpu`**, **Docling**, and **`rapidocr-paddle`** are installed for the **poke interpreter** (default **`python3`** on `PATH`, or one declared `/opt/…` path — AMI bake owns the matrix). **`import paddle`** reports **≥1 CUDA device**; **`import docling`** succeeds; [`poke-smoke-test.py`](container/poke-smoke-test.py) converts a test image to markdown on GPU **without Docker**; scripts such as [`r3-paddle.py`](dev-benchmark/r3-paddle.py) run end-to-end. The golden image is declarative from a known base (e.g. DL Base GPU) plus native (`apt` / system `pip` / `--prefix`) installs. The thin Dockerfile must **not** install `paddlepaddle-gpu`, Torch CUDA, or `onnxruntime-gpu`.

### Thin container (repo + runtime)

- **`Dockerfile` is minimal and uses the CUDA runtime base only.** `FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04`; system deps + `pip install -r requirements.txt` only — **no** Torch, **no** ONNX GPU, **no** Paddle wheels in the Dockerfile.

- **`requirements.txt` lists only lightweight Python glue:** `docling`, `rapidocr-paddle`, `boto3`, `pydantic` (and acceptable transitive deps). It must **not** list `paddlepaddle-gpu`, `onnxruntime-gpu`, or PyTorch.

- **`processor.py` implements Docling 2.x with RapidOCR paddle on CUDA and the three-output contract.** **S3 mode:** argv `<input_s3_uri> <output_s3_prefix>`. **Local mode:** `OCR_LOCAL_FILE` + `OCR_LOCAL_OUTPUT_DIR`. `RapidOcrOptions(backend="paddle", force_full_page_ocr=True)`, `AcceleratorOptions(device=CUDA)`, `format_options` for PDF and image. Outputs: `export_to_markdown()`, `export_to_dict()`, plus copy of input file.

- **Docker engine is available:** `docker --version` succeeds; **`nvidia-container-toolkit`** is installed so `docker run --gpus all` works.

- **Container image builds successfully** from `container/`; production intent <150 MB compressed when pushed (local size is a proxy until first publish).

- **Containerized runs can use Paddle on GPU** via AMI → container binding (bind-mounts / `PYTHONPATH` — paths from AMI bake). Without binding, `import paddle` inside the container fails even if `nvidia-smi` works.

- **Container smoke test passes** with `OCR_LOCAL_*` and Apply §8 mounts: three production artifacts under the output dir (test media under [`test-media/`](test-media/)).

---

## Apply

### 1. Launch instance (workstation)

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

### 2. WORKDIR

```bash
mkdir -p ~/ocr-work
```

Set WORKDIR in `cloud-resources.md`.

### 3. Transfer files to instance

```bash
rsync -avz profiling/ocr-batch/container/    cloud-task-ocr:~/ocr-work/container/
rsync -avz profiling/ocr-batch/test-media/   cloud-task-ocr:~/ocr-work/sample_scan/
rsync -avz profiling/ocr-batch/container/poke-smoke-test.py cloud-task-ocr:~/ocr-work/poke-smoke-test.py
```

*Windows workstation*: `rsync` is not available natively. Use `scp -r` but
pre-create the target directory (`ssh cloud-task-ocr "mkdir -p …"`) first,
and note that `scp -r dir/ host:dest/` nests the source directory name
inside `dest/` — flatten or adjust accordingly.

### 4. AMI: native Python stack for poke (bake recipe)

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

### 5. Headless auth (deferred — user-interactive)

Per [headless-auth](../headless-auth/headless-auth.profile.md): `agent`
prompt, `gh auth login`, `gh auth setup-git`. Defer until an on-instance
session requires it.

### 6. Ensure Docker availability

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

### 7. Build container image

```bash
cd ~/ocr-work/container
docker build -t ocr-docling-gpu:latest .
```

### 8. Expose AMI Paddle to the container (runtime binding)

*Agentic — paths come from AMI bake.* Example pattern (adjust host paths
after bake):

```bash
docker run --rm --gpus all \
  -v /path/on/ami/to/paddle-packages:/paddle:ro \
  -e PYTHONPATH=/paddle \
  ...
```

Until mounts are fixed in the bake profile, full GPU paddle inside the
container may not pass; host-side paddle (Apply §4) still validates the OCR
stack.

### 9. GPU sanity in container

```bash
docker run --rm --gpus all --entrypoint nvidia-smi ocr-docling-gpu:latest
```

### 10. Container smoke test (local env)

Mount test media and a writable product dir, set `OCR_LOCAL_FILE` /
`OCR_LOCAL_OUTPUT_DIR`, plus §8 Paddle mounts:

```bash
mkdir -p ~/ocr-work/product
docker run --rm --gpus all \
  -v /home/ubuntu:/host \
  # ... add Paddle bind mounts from §8 ...
  -e OCR_LOCAL_FILE=/host/ocr-work/sample_scan/service-invoice.jpg \
  -e OCR_LOCAL_OUTPUT_DIR=/host/ocr-work/product \
  ocr-docling-gpu:latest
```

---

## Audit

Workstation checks: §1–§2. Instance (on `cloud-task-ocr`): §3 onward.

### 1. Instance tracked in `cloud-resources.md`

```bash
python tools/launch-spot-instance.py --tag cloud-task-ocr --check
```

Expected: `PASS: running instance i-… @ <ip> (tag=cloud-task-ocr)`

### 2. SSH profiled

```bash
ssh -G cloud-task-ocr 2>/dev/null | grep -i '^hostname '
```

Expected: `hostname <public-ip>` matching `cloud-resources.md`.

### 3. WORKDIR exists with test media (on-instance)

```bash
test -d ~/ocr-work && echo "PASS: WORKDIR" || echo "FAIL: WORKDIR"
ls ~/ocr-work/sample_scan/*.jpg >/dev/null 2>&1 && echo "PASS: test media" || echo "FAIL: test media"
```

Expected: two PASS lines.

### 4. Auth (deferred — user-interactive)

```bash
gh --version >/dev/null 2>&1 && echo "PASS: gh" || echo "SKIP: gh not installed"
gh auth status >/dev/null 2>&1 && echo "PASS: gh auth" || echo "SKIP: gh auth"
```

SKIP is acceptable when auth is deferred.

### 5. Poke stack — imports + OCR smoke (on-instance)

Use the system interpreter (not a venv):

```bash
python3 -c "import paddle; import docling; assert paddle.device.cuda.device_count() >= 1; print('PASS: poke imports')" 2>/dev/null || echo "FAIL: poke imports"
```

End-to-end OCR ([`poke-smoke-test.py`](container/poke-smoke-test.py)):

```bash
python3 ~/ocr-work/poke-smoke-test.py ~/ocr-work/sample_scan/service-invoice.jpg
```

Expected: `PASS: poke imports` and `PASS: poke smoke (…)`.

### 6. GPU accessible

```bash
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader && echo "PASS: GPU"
```

Expected: `Tesla T4, …` then `PASS: GPU`

### 7. Dockerfile is minimal

```bash
test -f profiling/ocr-batch/container/Dockerfile && echo "PASS" || echo "FAIL"
grep -q 'FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04' profiling/ocr-batch/container/Dockerfile && echo "PASS: FROM" || echo "FAIL"
! grep -qiE 'paddlepaddle-gpu|torch|onnxruntime' profiling/ocr-batch/container/Dockerfile && echo "PASS: no heavy wheels" || echo "FAIL"
```

Expected: three PASS lines.

### 8. requirements.txt is glue-only

```bash
grep -q 'docling' profiling/ocr-batch/container/requirements.txt && echo "PASS: docling" || echo "FAIL"
grep -q 'rapidocr-paddle' profiling/ocr-batch/container/requirements.txt && echo "PASS: rapidocr-paddle" || echo "FAIL"
grep -q 'boto3' profiling/ocr-batch/container/requirements.txt && echo "PASS: boto3" || echo "FAIL"
grep -q 'pydantic' profiling/ocr-batch/container/requirements.txt && echo "PASS: pydantic" || echo "FAIL"
grep -v '^#' profiling/ocr-batch/container/requirements.txt | grep -qE 'paddlepaddle-gpu|torch|onnxruntime' && echo "FAIL: forbidden wheel" || echo "PASS: no forbidden wheels"
```

Expected: five PASS lines.

### 9. processor.py uses Docling 2.x paddle API

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

### 10. Docker available on instance

```bash
docker --version && echo "PASS: docker" || echo "FAIL"
docker info 2>/dev/null | grep -q 'nvidia.com/gpu' && echo "PASS: nvidia CDI/runtime" || echo "FAIL"
```

Expected: two PASS lines.

### 11. Image exists (on-instance, after build)

```bash
docker images ocr-docling-gpu --format '{{.Repository}}:{{.Tag}}' | grep -q 'ocr-docling-gpu:latest' \
    && echo "PASS: image exists" || echo "FAIL"
```

### 12. NVIDIA device in container

```bash
docker run --rm --gpus all --entrypoint nvidia-smi ocr-docling-gpu:latest \
    --query-gpu=name --format=csv,noheader && echo "PASS: nvidia-smi" || echo "FAIL"
```

### 13. Container smoke (three artifacts)

Requires Apply §8 Paddle binding. On-instance after a successful run to
`OCR_LOCAL_OUTPUT_DIR`:

```bash
test -s ~/ocr-work/product/service-invoice.md && echo "PASS: markdown" || echo "FAIL"
test -s ~/ocr-work/product/service-invoice.json && echo "PASS: json" || echo "FAIL"
test -f ~/ocr-work/product/service-invoice.jpg && echo "PASS: original" || echo "FAIL"
```

Adjust basename to match `OCR_LOCAL_FILE`. Expected: three PASS lines.

---

## Appendix A — Torch-first path (historical reference)

The original profiled default was **RapidOCR `backend="torch"`** with a
**venv** at `WORKDIR/venv` and **`onnxruntime-gpu` ≤1.22** for Docling
layout/table models. This path is superseded by the paddle + native-install
Target State above; retained for reference only.

Key differences from the current target:

| Concern | Torch path (historical) | Paddle path (current) |
|---------|------------------------|----------------------|
| OCR backend | `RapidOcrOptions(backend="torch")` | `RapidOcrOptions(backend="paddle")` |
| Python env | `WORKDIR/venv` | System python (native pip) |
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
|-------|--------|-------|
| 1 | [`dev-benchmark/r1-onnx.py`](dev-benchmark/r1-onnx.py) | ONNX RapidOCR; CUDA vs CPU Docling |
| 2 | [`dev-benchmark/r2-torch.py`](dev-benchmark/r2-torch.py) | Torch baseline (historical default) |
| 3 | [`dev-benchmark/r3-paddle.py`](dev-benchmark/r3-paddle.py) | Paddle |
| 4–6 | [`r4-onnx-spacing.py`](dev-benchmark/r4-onnx-spacing.py) … [`r6-paddle-spacing.py`](dev-benchmark/r6-paddle-spacing.py) | GPU-only, spacing params |
| 7 | [`dev-benchmark/r7-paddle-tuned.py`](dev-benchmark/r7-paddle-tuned.py) | Paddle tuned |

Spacing heuristics: [`ocr-spacing-assess.py`](dev-benchmark/ocr-spacing-assess.py).
Session note: [`2026-04-08_spacing-assess-latest-lot.md`](dev-benchmark/2026-04-08_spacing-assess-latest-lot.md).

---
