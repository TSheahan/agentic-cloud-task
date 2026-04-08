# OCR Batch Container — State Convergence Profile

**Twofold goal**

1. **Interim poke** — SSH to the instance and exercise **Docling + RapidOCR paddle** on the **GPU** without crossing the container boundary (fast learning and debugging).
2. **Thin Docker image** — **Compose, build, and run** a **small** image (glue only) for **AWS Batch**, with **Paddle** supplied from the **AMI**, not baked into the image.

**Architecture:** **PaddlePaddle GPU** and the **native Python stack** used for poke live on the **custom AMI** (declarative bake). The container image carries only lightweight Python deps (`docling`, `rapidocr-paddle`, boto3, pydantic) — **no** `paddlepaddle-gpu`, **no** Torch/ONNX GPU wheels in the image.

**Native vs venv:** Convergence assumes **system (or single-prefix) Python** — e.g. `apt` / **`pip install` to system** or an **`/opt/...`** tree on `PATH` — **not** a long-lived **`WORKDIR/venv`** as the **source of truth**. An old torch-first venv under `~/ocr-work/venv` is **migration / interim** only; **after this Target State is checked in**, the **intended** path is **rebuild from a clean base AMI** and bake **native** installs so the disk is **not** carrying conflicting stacks.

Layering: [ocr-batch](../ocr-batch.profile.md) for **nodes, SSH, WORKDIR** catalog; [ocr-batch.profile.md](../ocr-batch.profile.md) **torch-first** path remains **reference** for bare-metal torch; **this profile** is **paddle + thin container** for Batch.

Follows the [state convergence pattern](../../../policies/state-convergence-pattern.md).

Superseded exploratory notes: [`01-starting-theory-of-container.md`](01-starting-theory-of-container.md).

---

## Target State

### Goal 1 — Interim poke (AMI, native Python)

- **AMI supports Docling + paddle poke via native Python and a clean bake lineage.** **`paddlepaddle-gpu`**, **Docling**, and **`rapidocr-paddle`** are installed for the **poke interpreter** (default **`python3`** on `PATH`, or one **declared** `/opt/...` path — AMI bake owns the matrix). **`import paddle`** reports **≥1 CUDA device**; **`import docling`** succeeds; scripts such as [`r3-paddle.py`](../dev-benchmark/r3-paddle.py) run **without Docker**. The golden image is **declarative from a known base** (e.g. DL Base GPU) plus **native** (`apt` / system `pip` / `--prefix`) installs — **not** by treating **`~/ocr-work/venv`** as the convergence source of truth. **After this profile is checked in, rebuild from a clean base AMI** before bake so the disk is not carrying conflicting torch/venv experiments. The thin **Dockerfile** still must **not** install `paddlepaddle-gpu`, Torch CUDA, or `onnxruntime-gpu`.

### Goal 2 — Thin Docker image (repo + runtime)

- **`Dockerfile` is minimal and uses the CUDA runtime base only.** `FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04`; system deps + `pip install -r requirements.txt` only — **no** Torch, **no** ONNX GPU, **no** Paddle wheels in the Dockerfile.

- **`requirements.txt` lists only lightweight Python glue:** `docling`, `rapidocr-paddle`, `boto3`, `pydantic` (and acceptable transitive deps). It must **not** list `paddlepaddle-gpu`, `onnxruntime-gpu`, or PyTorch.

- **`processor.py` implements Docling 2.x with RapidOCR paddle on CUDA and the three-output contract.** **S3 mode:** argv `<input_s3_uri> <output_s3_prefix>`. **Local mode:** `OCR_LOCAL_FILE` + **`OCR_LOCAL_OUTPUT_DIR`**. **`RapidOcrOptions(backend="paddle", force_full_page_ocr=True)`**, **`AcceleratorOptions(device=CUDA)`**, `format_options` for PDF and image. Outputs: **`export_to_markdown()`**, **`export_to_dict()`**, plus **copy of input file**.

- **Docker engine is available:** `docker --version` succeeds; **`nvidia-container-toolkit`** is installed so `docker run --gpus all` works.

- **Container image builds successfully** from `dev-container/`; production intent **&lt;150 MB compressed** when pushed (local size is a proxy until first publish).

- **Containerized runs can use Paddle on GPU** via **AMI → container** binding (bind-mounts / `PYTHONPATH` — paths in **AMI bake**). Without binding, `import paddle` inside the container fails even if `nvidia-smi` works.

- **Container smoke test passes** with `OCR_LOCAL_*` and Apply **§6** mounts: **three production artifacts** under the output dir (e.g. test media under [`test-media/`](../test-media/)).

---

## Apply

### 1. Source files (workstation)

Files live at `profiling/ocr-batch/dev-container/`: `Dockerfile`, `requirements.txt`, `processor.py` — **no** `paddlepaddle-gpu` in Dockerfile or `requirements.txt`.

### 2. Transfer to instance

```bash
rsync -avz profiling/ocr-batch/dev-container/ cloud-task-ocr:/home/ubuntu/ocr-work/dev-container/
```

### 3. AMI: native Python stack for poke (bake recipe)

Install **`paddlepaddle-gpu`**, **Docling**, and **`rapidocr-paddle`** with the **system** interpreter (or a **single `/opt/...` prefix** on `PATH`) per the AMI bake — **not** into `~/ocr-work/venv` as the long-term contract. Version/CUDA matrix lives in the bake profile.

Smoke on the baked instance:

```bash
python3 -c "import paddle; import docling; print('poke ok', paddle.__version__, paddle.device.cuda.device_count())"
```

Benchmark driver: [`dev-benchmark/r3-paddle.py`](../dev-benchmark/r3-paddle.py).

### 4. Ensure Docker availability

```bash
docker --version
dpkg -l | grep nvidia-container-toolkit
```

Install if missing (adapt for AMI Ubuntu version):

```bash
sudo apt-get update
sudo apt-get install -y docker.io nvidia-container-toolkit
sudo usermod -aG docker ubuntu
sudo systemctl restart docker
```

### 5. Build tiny image

```bash
cd /home/ubuntu/ocr-work/dev-container
docker build -t ocr-docling-gpu:latest .
```

### 6. Expose AMI Paddle to the container (runtime binding)

*Agentic — paths come from AMI bake.* Example pattern (adjust host paths after bake):

```bash
# Illustrative only — replace with paths from the AMI profile
docker run --rm --gpus all \
  -v /path/on/ami/to/paddle-packages:/paddle:ro \
  -e PYTHONPATH=/paddle \
  ...
```

Until mounts are fixed in the bake profile, full GPU paddle **inside** the container may not pass; **host-side** paddle (Apply §3) still validates the OCR stack.

### 7. GPU sanity in container (no Torch)

Use **`--entrypoint`** so arguments are not passed to `processor.py`:

```bash
docker run --rm --gpus all --entrypoint nvidia-smi ocr-docling-gpu:latest
```

Optional: `python3 -c "import paddle; print(paddle.device.cuda.device_count())"` **after** Apply §6 mount works.

### 8. Full smoke test (local env)

Mount repo test media and a writable product dir, set `OCR_LOCAL_FILE` / `OCR_LOCAL_OUTPUT_DIR`, plus **§6** Paddle mounts:

```bash
mkdir -p /home/ubuntu/ocr-work/product
docker run --rm --gpus all \
  -v /home/ubuntu:/host \
  # ... add Paddle bind mounts from §6 ...
  -e OCR_LOCAL_FILE=/host/agentic-cloud-task/profiling/ocr-batch/test-media/service-invoice.jpg \
  -e OCR_LOCAL_OUTPUT_DIR=/host/ocr-work/product \
  ocr-docling-gpu:latest
```

**S3 Batch path** — future Apply: IAM + bucket + `processor.py s3://… s3://…`.

---

## Audit

### 0. AMI poke stack — native `python3` (on-instance)

After bake / Apply §3 — use the **same** interpreter the AMI declares (usually **`python3`**, not `~/ocr-work/venv`):

```bash
python3 -c "import paddle; import docling; assert paddle.device.cuda.device_count() >= 1; print('PASS: poke stack')" 2>/dev/null || echo "FAIL: poke stack"
```

Expected: `PASS: poke stack`.

### 1. Dockerfile is minimal (no heavy ML wheels in build)

```bash
test -f profiling/ocr-batch/dev-container/Dockerfile && echo "PASS" || echo "FAIL"
grep -q 'FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04' profiling/ocr-batch/dev-container/Dockerfile && echo "PASS: FROM" || echo "FAIL"
! grep -qiE 'paddlepaddle-gpu|torch|onnxruntime' profiling/ocr-batch/dev-container/Dockerfile && echo "PASS: no heavy wheels in Dockerfile" || echo "FAIL"
```

Expected: three PASS lines.

### 2. requirements.txt is glue-only

```bash
grep -q 'docling' profiling/ocr-batch/dev-container/requirements.txt && echo "PASS: docling" || echo "FAIL"
grep -q 'rapidocr-paddle' profiling/ocr-batch/dev-container/requirements.txt && echo "PASS: rapidocr-paddle" || echo "FAIL"
grep -q 'boto3' profiling/ocr-batch/dev-container/requirements.txt && echo "PASS: boto3" || echo "FAIL"
grep -q 'pydantic' profiling/ocr-batch/dev-container/requirements.txt && echo "PASS: pydantic" || echo "FAIL"
grep -v '^#' profiling/ocr-batch/dev-container/requirements.txt | grep -qE 'paddlepaddle-gpu|torch|onnxruntime' && echo "FAIL: forbidden wheel" || echo "PASS: no forbidden wheels in deps"
```

Expected: five PASS lines.

### 3. processor.py uses Docling 2.x paddle API

```bash
grep -q 'format_options' profiling/ocr-batch/dev-container/processor.py && echo "PASS: format_options" || echo "FAIL"
grep -q 'backend="paddle"' profiling/ocr-batch/dev-container/processor.py && echo "PASS: paddle backend" || echo "FAIL"
grep -q 'OCR_LOCAL_FILE' profiling/ocr-batch/dev-container/processor.py && echo "PASS: OCR_LOCAL_FILE" || echo "FAIL"
grep -q 'OCR_LOCAL_OUTPUT_DIR' profiling/ocr-batch/dev-container/processor.py && echo "PASS: OCR_LOCAL_OUTPUT_DIR" || echo "FAIL"
grep -q 'export_to_dict' profiling/ocr-batch/dev-container/processor.py && echo "PASS: export_to_dict" || echo "FAIL"
grep -q 'ImageFormatOption' profiling/ocr-batch/dev-container/processor.py && echo "PASS: ImageFormatOption" || echo "FAIL"
grep -q 'shutil.copy2' profiling/ocr-batch/dev-container/processor.py && echo "PASS: original preserved" || echo "FAIL"
! grep -q 'pipeline_options=pipeline_options)$' profiling/ocr-batch/dev-container/processor.py && echo "PASS: no top-level pipeline_options" || echo "FAIL"
```

Expected: eight PASS lines.

### 4. Docker available on instance

```bash
docker --version && echo "PASS: docker" || echo "FAIL"
docker info 2>/dev/null | grep -q 'nvidia.com/gpu' && echo "PASS: nvidia CDI/runtime" || echo "FAIL"
```

Expected: two PASS lines.

### 5. Image exists (on-instance, after build)

```bash
docker images ocr-docling-gpu --format '{{.Repository}}:{{.Tag}}' | grep -q 'ocr-docling-gpu:latest' \
    && echo "PASS: image exists" || echo "FAIL"
```

### 6. NVIDIA device in container

```bash
docker run --rm --gpus all --entrypoint nvidia-smi ocr-docling-gpu:latest \
    --query-gpu=name --format=csv,noheader && echo "PASS: nvidia-smi" || echo "FAIL"
```

### 7. Container smoke (three artifacts; requires §6 Paddle binding when running in container)

On-instance, after a successful run to `OCR_LOCAL_OUTPUT_DIR`:

```bash
test -s /home/ubuntu/ocr-work/product/service-invoice.md && echo "PASS: markdown" || echo "FAIL"
test -s /home/ubuntu/ocr-work/product/service-invoice.json && echo "PASS: json" || echo "FAIL"
test -f /home/ubuntu/ocr-work/product/service-invoice.jpg && echo "PASS: original" || echo "FAIL"
```

Adjust basename to match `OCR_LOCAL_FILE`. Expected: three PASS lines.

---
