# OCR Batch Container — State Convergence Profile

Containerized OCR processor for **AWS Batch**. Wraps the torch-first
Docling + RapidOCR pipeline from
[ocr-batch.profile.md](../ocr-batch.profile.md) into a Docker image that
receives a PDF via S3, converts it, and uploads structured output.

Prerequisite: the OCR instance is launched and the bare-metal OCR stack is
converged per [ocr-batch.profile.md](../ocr-batch.profile.md) — Docker is
built on-instance before pushing to ECR.

Follows the [state convergence pattern](../../../policies/state-convergence-pattern.md).

Starting theory: [`01-starting-theory-of-container.md`](01-starting-theory-of-container.md)
(pre-profile brain dump; superseded by this profile for convergence purposes).

---

## Target State

### Container source artifacts (repo-committed)

- **`Dockerfile` exists and is aligned with the torch-first OCR profile.**
  Base image: `nvidia/cuda:12.6.0-runtime-ubuntu22.04`. Installs Python
  3.10, system deps, PyTorch (CUDA, from PyTorch index), then
  `requirements.txt`. Copies `processor.py`. Entrypoint:
  `python3 processor.py`.

- **`requirements.txt` lists the torch-first dependency set.**
  `docling[rapidocr]>=2.0.0`, `onnxruntime-gpu<=1.22`, `boto3`,
  `pydantic`. No paddle dependencies. Torch installed separately in
  Dockerfile for CUDA index URL control.

- **`processor.py` implements the S3-to-S3 Docling 2.x torch pipeline.**
  S3 download → Docling conversion → S3 upload (`.md`, `.json`,
  `COMPLETED` artifact). Uses `format_options=` (not top-level
  `pipeline_options=`), `RapidOcrOptions(backend="torch",
  force_full_page_ocr=True)`, `AcceleratorOptions(device=CUDA)`. Import
  path: `docling.datamodel.base_models.InputFormat`.

### Instance runtime (on cloud-task-ocr)

- **Docker engine is available on the OCR instance.** `docker --version`
  succeeds; `nvidia-container-toolkit` is installed so the `--gpus` flag
  works with the T4.

- **Container image builds successfully.** `docker build -t
  ocr-docling-gpu:latest .` exits 0 from the dev-container directory on
  the instance.

- **Container has GPU access.** `docker run --rm --gpus all
  ocr-docling-gpu:latest` can see the T4 via `nvidia-smi` and
  `torch.cuda.is_available()` returns True.

- **Container smoke test passes.** Running processor.py inside the
  container against a test PDF produces `SUCCESS` status and non-empty
  Markdown output.

---

## Apply

### 1. Create container source files (workstation)

Corrected from [`01-starting-theory-of-container.md`](01-starting-theory-of-container.md)
to align with the profiled torch-first default. Key corrections from the
theory:

- **requirements.txt:** `docling[rapidocr]` replaces `rapidocr-paddle`;
  `onnxruntime-gpu<=1.22` added (EC2 g4dn DRM pin).
- **processor.py:** `format_options={...}` replaces top-level
  `pipeline_options=`; `RapidOcrOptions(backend="torch")` replaces
  `use_gpu=True` / paddle; import from `base_models` not `base`;
  `export_to_markdown()` returns string (not a file-writer).
- **Dockerfile:** torch installed from PyTorch CUDA index before
  `requirements.txt`; no `rapidocr-paddle` in the image.

Files committed at `profiling/ocr-batch/dev-container/`:
`Dockerfile`, `requirements.txt`, `processor.py`.

### 2. Transfer to instance

```bash
rsync -avz profiling/ocr-batch/dev-container/ cloud-task-ocr:/home/ubuntu/ocr-work/dev-container/
```

### 3. Ensure Docker availability

*Stub — runtime-dependent.* The AWS DL Base GPU AMI may or may not include
Docker and the NVIDIA container toolkit. Check first:

```bash
docker --version
dpkg -l | grep nvidia-container-toolkit
```

If missing, install (on-instance):

```bash
sudo apt-get update
sudo apt-get install -y docker.io nvidia-container-toolkit
sudo usermod -aG docker ubuntu
sudo systemctl restart docker
# re-login for group change
```

Exact package names may vary with the AMI's Ubuntu version; adapt at
runtime.

### 4. Build image

```bash
cd /home/ubuntu/ocr-work/dev-container
docker build -t ocr-docling-gpu:latest .
```

Build time is significant (PyTorch download + docling deps). Watch for:
- CUDA version mismatch between the container base image (12.6) and the
  torch wheel index (`cu124`). If torch reports no CUDA at runtime, the
  index URL in the Dockerfile may need updating.
- `onnxruntime-gpu` version conflicts with the torch install.

### 5. GPU smoke test

```bash
docker run --rm --gpus all ocr-docling-gpu:latest \
    python3 -c "import torch; assert torch.cuda.is_available(); print('GPU OK')"
```

### 6. Full smoke test

*Stub — depends on S3 test bucket or a local-path mode added to
processor.py.* Minimal approach: volume-mount a test PDF and run a local
conversion. Full S3 test requires bucket + IAM role configuration (future
Apply step — AWS Batch infrastructure).

---

## Audit

### 1. Dockerfile exists and is torch-aligned

```bash
test -f profiling/ocr-batch/dev-container/Dockerfile && echo "PASS" || echo "FAIL"
grep -q 'whl/cu' profiling/ocr-batch/dev-container/Dockerfile && echo "PASS: torch CUDA index" || echo "FAIL"
! grep -q paddle profiling/ocr-batch/dev-container/Dockerfile && echo "PASS: no paddle" || echo "FAIL"
```

Expected: three PASS lines.

### 2. requirements.txt is torch-first

```bash
grep -q 'docling\[rapidocr\]' profiling/ocr-batch/dev-container/requirements.txt && echo "PASS: docling[rapidocr]" || echo "FAIL"
grep -q 'onnxruntime-gpu' profiling/ocr-batch/dev-container/requirements.txt && echo "PASS: onnxruntime-gpu" || echo "FAIL"
! grep -q paddle profiling/ocr-batch/dev-container/requirements.txt && echo "PASS: no paddle" || echo "FAIL"
```

Expected: three PASS lines.

### 3. processor.py uses Docling 2.x torch API

```bash
grep -q 'format_options' profiling/ocr-batch/dev-container/processor.py && echo "PASS: format_options" || echo "FAIL"
grep -q 'backend="torch"' profiling/ocr-batch/dev-container/processor.py && echo "PASS: torch backend" || echo "FAIL"
grep -q 'base_models' profiling/ocr-batch/dev-container/processor.py && echo "PASS: base_models import" || echo "FAIL"
! grep -q 'pipeline_options=pipeline_options)$' profiling/ocr-batch/dev-container/processor.py && echo "PASS: no top-level pipeline_options" || echo "FAIL"
```

Expected: four PASS lines.

### 4. Docker available on instance

*Stub — run on-instance (ssh cloud-task-ocr).*

```bash
docker --version && echo "PASS: docker" || echo "FAIL"
docker info 2>/dev/null | grep -q 'Runtimes.*nvidia' && echo "PASS: nvidia runtime" || echo "FAIL"
```

Expected: two PASS lines. If Docker is not yet installed, this check
identifies the gap for Apply §3.

### 5. Image builds

*Stub — run on-instance after Apply §4.* Presence of the built image:

```bash
docker images ocr-docling-gpu --format '{{.Repository}}:{{.Tag}}' | grep -q 'ocr-docling-gpu:latest' \
    && echo "PASS: image exists" || echo "FAIL"
```

### 6. GPU access inside container

*Stub — run on-instance after build.*

```bash
docker run --rm --gpus all ocr-docling-gpu:latest \
    python3 -c "import torch; assert torch.cuda.is_available(); print('PASS: GPU')"
```

Expected: `PASS: GPU`.

### 7. Container smoke test

*Stub — depends on S3 bucket or local-path mode.* Not yet auditable;
requires Apply §6 infrastructure or a local-only test harness in
processor.py.

---
