# OCR Batch Processing — State Convergence Profile

GPU-accelerated OCR batch processing using **Docling** + **RapidOCR `backend="torch"`** (PyTorch on GPU when Docling uses CUDA). This profile’s **Target State** is **torch-first**; ONNX and paddle are **reference-only** (see [Appendix A](#appendix-a--alternate-rapidocr-backends-reference)).

Repeatable: instance baked to a custom AMI, relaunched (~90 s boot to working state).

Layers on [aws-deep-learning-base](../aws-deep-learning-base/base-gpu-node.profile.md) — must hold before this profile applies.

**Headless auth** (`agent`, `gh`): [headless-auth](../headless-auth/headless-auth.profile.md).

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

**Transfer:** documents via SSH (rsync/scp); S3 / AWS Batch out of scope here.

---

## Target State

### Instance, SSH, auth, cataloged WORKDIR

Default **slug `ocr`**: EC2 Name **`cloud-task-ocr`**, `~/.ssh/config` Host **`cloud-task-ocr`**.

- **A running OCR batch instance is launched and tracked in `cloud-resources.md`.** Name **`cloud-task-ocr`**, `--tag` matches [`tools/launch-spot-instance.py`](../../tools/launch-spot-instance.py). Gitignored [**`cloud-resources.md`**](../../cloud-resources.md) **Nodes** row: **Name**, **SSH Host**, **Instance ID**, **Public IP**, **Region**, **Type**, **Status**, **Notes** — current per [AGENTS.md](../../AGENTS.md). **Spot** market; one-time requests use `--instance-initiated-shutdown-behavior terminate` (required with spot termination behavior).

- **SSH is profiled on the controlling machine.** **`Host cloud-task-ocr`**, **HostName** = instance public IP; **User** / **IdentityFile** per [dev-workstation](../local-dev-env/dev-workstation.profile.md). **`cloud-resources.md`** **SSH (current)** lists usable commands while running.

- **Agent CLI and GitHub CLI are authenticated** per [headless-auth](../headless-auth/headless-auth.profile.md): `agent` prompt completes; `gh --version`; `gh auth status` exits 0; `gh auth setup-git` for HTTPS.

- **WORKDIR is named in `cloud-resources.md`, exists on the instance, uses durable storage.** **Nodes.WORKDIR** = absolute OCR root (e.g. `/home/ubuntu/ocr-work` on root EBS); survives stop→start; terminate/teardown still applies.

### Working directory and Python

- **WORKDIR is flat, not inside the project repo clone; `venv/` is a direct child.** Mutable batch state lives only under WORKDIR.

- **A Python venv exists at `WORKDIR/venv`** (Python 3.10 per base profile). pip / setuptools / wheel current.

### OCR stack (profiled default: torch)

- **Docling with RapidOCR extra is installed.** Imports succeed:
  - `DocumentConverter`, `PdfFormatOption`, `ImageFormatOption`
  - `PdfPipelineOptions`, `RapidOcrOptions`, `AcceleratorOptions`, `AcceleratorDevice`
  - `InputFormat`

- **`onnxruntime-gpu` is installed.** Docling layout/table models use `CUDAExecutionProvider` on the T4.

- **The T4 GPU is accessible.** `nvidia-smi` shows Tesla T4, ≥15 GB VRAM, working driver.

- **The profiled OCR inference path is RapidOCR torch on CUDA.** In the venv: `import torch` and **`torch.cuda.is_available()`** is True. Docling pipeline uses **`RapidOcrOptions(backend="torch", force_full_page_ocr=True)`** on **`PdfPipelineOptions(do_ocr=True, do_table_structure=True, ocr_batch_size=…)`** with **`AcceleratorOptions(device=CUDA)`**, wired through **`PdfFormatOption` / `ImageFormatOption`** (Docling 2.x — no top-level `pipeline_options=` on `DocumentConverter`). RapidOCR runs on **GPU**; layout/table ONNX stays on **onnxruntime-gpu**.

- **PDF smoke conversion succeeds** using that torch pipeline: a test PDF under WORKDIR yields `success` and non-empty Markdown export.

### Evaluation baseline (torch)

- **A completed canonical torch benchmark capture exists under WORKDIR.** `sample_scan/` holds evaluation images; `runs/<run-id>/` contains `timings.json`, `SUMMARY.md`, `outputs/cuda/` and `outputs/cpu/`, `run_benchmark.py` matching [`dev-benchmark/r2-torch.py`](dev-benchmark/r2-torch.py) (CUDA vs CPU accelerator sweep with **torch** backend). Canonical id **`2026-04-08_docling-torch-round2-v1`** (or documented successor). *Purpose:* regression baseline aligned with the profiled default.

### Transfer and AMI

- **An rsync-oriented input/output layout exists** _(placeholder — inbox / batch-in / batch-out TBD)._

- **The instance is bake-ready** after Apply: OCR stack + smoke OK; pre-bake purge per [base-gpu-node](../aws-deep-learning-base/base-gpu-node.profile.md) Apply §5 before snapshot; AMI recorded in **`cloud-resources.md`**.

---

## Apply

### 1. Launch instance (workstation)

Project **`venv/`**, **`.env`** loaded; AMI from **`cloud-resources.md`**; slug **`ocr`**.

```bash
python tools/launch-spot-instance.py \
    --ami <ami-id-from-cloud-resources.md> \
    --instance-type g4dn.xlarge \
    --volume-gb 125 \
    --tag cloud-task-ocr \
    --instance-initiated-shutdown-behavior terminate
```

Update **`cloud-resources.md`** (Nodes row; WORKDIR placeholder until §2). Converge [base-gpu-node](../aws-deep-learning-base/base-gpu-node.profile.md) if needed. **[headless-auth](../headless-auth/headless-auth.profile.md)** if `agent` / `gh` required.

### 2. `WORKDIR` and venv

```bash
WORKDIR=/home/ubuntu/ocr-work
mkdir -p "$WORKDIR"
cd "$WORKDIR"
PYTHON=$(command -v python3.11 || command -v python3.10)
$PYTHON -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

Set **WORKDIR** in **`cloud-resources.md`**.

### 3. Install stack (Docling + ONNX GPU + PyTorch CUDA for torch OCR)

```bash
cd /home/ubuntu/ocr-work
source venv/bin/activate

pip install "docling[rapidocr]"
pip install onnxruntime-gpu
```

Verify **PyTorch sees CUDA** (profiled default):

```bash
venv/bin/python -c "import torch; assert torch.cuda.is_available(); print('torch', torch.__version__, 'cuda ok')"
```

If CUDA is false, install a **CUDA build** of PyTorch for the driver ([PyTorch install](https://pytorch.org/get-started/locally/)); DL AMI usually suffices.

**API note:** `DocumentConverter` uses `format_options={...}`, not top-level `pipeline_options=`. **Known noise:** onnxruntime may warn about `/sys/class/drm/...` — harmless if CUDA EP loads.

### 4. PDF smoke (torch — required before bake)

Deposit **`test.pdf`** under WORKDIR. Run:

```bash
cd /home/ubuntu/ocr-work
source venv/bin/activate
python << 'PY'
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions, RapidOcrOptions,
    AcceleratorOptions, AcceleratorDevice,
)
from docling.datamodel.base_models import InputFormat

pipeline_options = PdfPipelineOptions(
    do_ocr=True,
    do_table_structure=True,
    ocr_options=RapidOcrOptions(backend="torch", force_full_page_ocr=True),
    ocr_batch_size=16,
    accelerator_options=AcceleratorOptions(
        device=AcceleratorDevice.CUDA,
        num_threads=4,
    ),
)
converter = DocumentConverter(
    allowed_formats=[InputFormat.PDF],
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)},
)
result = converter.convert("/home/ubuntu/ocr-work/test.pdf")
assert result.status.name == "SUCCESS", result.status
print(result.document.export_to_markdown()[:500])
print("PASS: smoke conversion")
PY
```

### 5. Canonical torch evaluation capture (regression baseline)

On the **instance**, `sample_scan/` populated; run directory with [`dev-benchmark/r2-torch.py`](dev-benchmark/r2-torch.py):

```bash
export OCR_WORKDIR=/home/ubuntu/ocr-work
export OCR_BATCH_SIZE=16
RUN_ID=2026-04-08_docling-torch-round2-v1
mkdir -p "$OCR_WORKDIR/runs/$RUN_ID"
cp profiling/ocr-batch/dev-benchmark/r2-torch.py \
  "$OCR_WORKDIR/runs/$RUN_ID/run_benchmark.py"
source "$OCR_WORKDIR/venv/bin/activate"
python "$OCR_WORKDIR/runs/$RUN_ID/run_benchmark.py" "$OCR_WORKDIR/runs/$RUN_ID"
```

Author **`SUMMARY.md`** in the run directory.

### 6. Bake custom AMI

After smoke (§4) and [base-gpu-node](../aws-deep-learning-base/base-gpu-node.profile.md) pre-bake purge:

```bash
python tools/create-ami.py --tag cloud-task-ocr --name ocr-batch-<date>
```

Record AMI in **`cloud-resources.md`**.

---

## Audit

Workstation: **§1–2**. Instance (`/home/ubuntu/ocr-work`, `venv` active): **§3–13**.

### 1. Instance tracked in `cloud-resources.md`

```bash
python tools/launch-spot-instance.py --tag cloud-task-ocr --check
```
Expected: `PASS: running instance i-... @ <ip> (tag=cloud-task-ocr)`

### 2. SSH profiled

```bash
ssh -G cloud-task-ocr 2>/dev/null | grep -i '^hostname '
```
Expected: `hostname <public-ip>` matching **`cloud-resources.md`**.

### 3. Agent and `gh` authenticated

```bash
echo "reply ok" | agent -p 2>/dev/null && echo "PASS: agent" || echo "FAIL: agent"
gh --version >/dev/null 2>&1 && echo "PASS: gh" || echo "FAIL: gh"
gh auth status >/dev/null 2>&1 && echo "PASS: gh auth" || echo "FAIL: gh auth"
git config --global credential.helper 2>/dev/null | grep -q 'gh' && echo "PASS: gh cred" || echo "FAIL: gh cred"
```
Expected: four PASS lines.

### 4. WORKDIR cataloged and exists

**Workstation:** Nodes row for **`cloud-task-ocr`** has **WORKDIR** set.

**Instance:**

```bash
cd /home/ubuntu/ocr-work
test -d "$(pwd -P)" && echo "PASS: WORKDIR at $(pwd -P)" || echo "FAIL"
```
Expected: `PASS: WORKDIR at /home/ubuntu/ocr-work`

### 5. WORKDIR layout

```bash
test -d venv && case "$(pwd -P)" in */agentic-cloud-task|*/agentic-cloud-task/*) echo "FAIL: inside repo" ;; *) echo "PASS: layout OK" ;; esac
```
Expected: `PASS: layout OK`

### 6. Python venv

```bash
[ -d venv ] && venv/bin/python --version && echo "PASS: venv" || echo "FAIL"
```
Expected: `Python 3.10.x` then `PASS: venv`

### 7. Docling + RapidOCR imports

```bash
venv/bin/python -c "
from docling.document_converter import DocumentConverter, PdfFormatOption, ImageFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions, AcceleratorOptions, AcceleratorDevice
from docling.datamodel.base_models import InputFormat
print('PASS: imports')
"
```
Expected: `PASS: imports`

### 8. `onnxruntime-gpu` CUDA EP

```bash
venv/bin/python -c "
import onnxruntime as ort
assert 'CUDAExecutionProvider' in ort.get_available_providers()
print('PASS: CUDAExecutionProvider')
"
```
Expected: `PASS: CUDAExecutionProvider`

### 9. GPU accessible

```bash
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader && echo "PASS: GPU"
```
Expected: `Tesla T4, ...` then `PASS: GPU`

### 10. PyTorch CUDA + RapidOCR torch options

```bash
venv/bin/python -c "
import torch
assert torch.cuda.is_available()
from docling.datamodel.pipeline_options import RapidOcrOptions
RapidOcrOptions(backend='torch', force_full_page_ocr=True)
print('PASS: torch CUDA + RapidOcrOptions torch')
"
```
Expected: `PASS: torch CUDA + RapidOcrOptions torch`

### 11. PDF smoke (torch pipeline)

Requires `/home/ubuntu/ocr-work/test.pdf`.

```bash
cd /home/ubuntu/ocr-work
source venv/bin/activate
venv/bin/python -c "
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions, AcceleratorOptions, AcceleratorDevice
from docling.datamodel.base_models import InputFormat
po = PdfPipelineOptions(
    do_ocr=True, do_table_structure=True,
    ocr_options=RapidOcrOptions(backend='torch', force_full_page_ocr=True),
    ocr_batch_size=16,
    accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CUDA, num_threads=4),
)
cv = DocumentConverter(allowed_formats=[InputFormat.PDF], format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=po)})
r = cv.convert('/home/ubuntu/ocr-work/test.pdf')
assert r.status.value == 'success'
print('PASS: PDF smoke torch')
"
```
Expected: `PASS: PDF smoke torch`

### 12. Canonical torch evaluation capture

```bash
export OCR_WORKDIR=/home/ubuntu/ocr-work
RUN_ID=2026-04-08_docling-torch-round2-v1
RUN="$OCR_WORKDIR/runs/$RUN_ID"
test -d "$OCR_WORKDIR/sample_scan" && echo "PASS: sample_scan" || echo "FAIL: sample_scan"
test -f "$RUN/timings.json" && echo "PASS: timings.json" || echo "FAIL"
test -f "$RUN/SUMMARY.md" && echo "PASS: SUMMARY.md" || echo "FAIL"
test -d "$RUN/outputs/cuda" && test -d "$RUN/outputs/cpu" && echo "PASS: outputs" || echo "FAIL"
test -f "$RUN/run_benchmark.py" && echo "PASS: script" || echo "FAIL"
python3 -c "
import json, os
run = '$RUN'
with open(os.path.join(run, 'timings.json')) as f: d = json.load(f)
assert d.get('benchmark_round') == 2 and d.get('rapidocr_backend') == 'torch'
for r in d['rows']:
    assert r.get('cuda_status') == 'success' and r.get('cpu_status') == 'success'
assert d['totals'].get('ratio_cpu_per_cuda') is not None
print('PASS: torch capture shape')
"
```
Expected: lines ending with `PASS: torch capture shape`

### 13. AMI bake readiness

**Transfer layout:** Target State item is still placeholder — **no scripted audit** until inbox/batch paths are specified.

**AMI:** Pre-bake purge per [base-gpu-node](../aws-deep-learning-base/base-gpu-node.profile.md) Audit §10; confirm OCR stack + §11 smoke before snapshot.

---

## Appendix A — Alternate RapidOCR backends (reference)

Not part of the **profiled default**. Use only for comparison or legacy workflows.

| Backend | Notes |
|---------|--------|
| **ONNX** (implicit `RapidOcrOptions()`) | RapidOCR det/rec on **CPU**; Docling layout on **GPU** — partial GPU. Script: [`dev-benchmark/r1-onnx.py`](dev-benchmark/r1-onnx.py). |
| **paddle** | Requires `paddlepaddle-gpu`, `rapidocr-paddle`. Script: [`dev-benchmark/r3-paddle.py`](dev-benchmark/r3-paddle.py). Install fragment: [Appendix C.1](#c1-paddlepaddle--rapidocr-paddle). |

---

## Appendix B — Historical benchmark matrix (reference)

Superseded for **convergence** by the torch Target State above; retained for timing/spacing experiments.

| Round | Script | Notes |
|-------|--------|--------|
| 1 | [`dev-benchmark/r1-onnx.py`](dev-benchmark/r1-onnx.py) | ONNX RapidOCR; CUDA vs CPU Docling |
| 2 | [`dev-benchmark/r2-torch.py`](dev-benchmark/r2-torch.py) | **Canonical baseline** (profiled default) |
| 3 | [`dev-benchmark/r3-paddle.py`](dev-benchmark/r3-paddle.py) | Paddle |
| 4–6 | [`r4-onnx-spacing.py`](dev-benchmark/r4-onnx-spacing.py) … [`r6-paddle-spacing.py`](dev-benchmark/r6-paddle-spacing.py) | GPU-only, spacing params |
| 7 | [`r7-paddle-tuned.py`](dev-benchmark/r7-paddle-tuned.py) | Paddle tuned |

Spacing heuristics: [`ocr-spacing-assess.py`](ocr-spacing-assess.py). Session note: [`2026-04-08_spacing-assess-latest-lot.md`](2026-04-08_spacing-assess-latest-lot.md).

---

## Appendix C — Optional Apply fragments

### C.1 PaddlePaddle + rapidocr-paddle

```bash
cd /home/ubuntu/ocr-work
source venv/bin/activate
pip install paddlepaddle-gpu==2.6.2 -f https://www.paddlepaddle.org.cn/whl/linux/mkl/avx/stable.html
pip install rapidocr-paddle
python -c "import paddle; paddle.utils.run_check()"
```

Pick wheel matching CUDA/driver per [Paddle install](https://www.paddlepaddle.org.cn/install/quick).

### C.2 Round 1 (ONNX) evaluation capture

```bash
export OCR_WORKDIR=/home/ubuntu/ocr-work
RUN_ID=2026-04-08_docling-gpu-eval-v1
mkdir -p "$OCR_WORKDIR/runs/$RUN_ID"
cp profiling/ocr-batch/dev-benchmark/r1-onnx.py "$OCR_WORKDIR/runs/$RUN_ID/run_benchmark.py"
source "$OCR_WORKDIR/venv/bin/activate"
python "$OCR_WORKDIR/runs/$RUN_ID/run_benchmark.py" "$OCR_WORKDIR/runs/$RUN_ID"
```

### C.3 Rounds 4–7 GPU-spacing / tuned drivers

See filenames in [Appendix B](#appendix-b--historical-benchmark-matrix-reference); copy `ocr_spacing_fix.py` next to drivers when symlinks are not used.

---

## Appendix D — Optional Audit snippets (historical)

**Round 1 capture** (`2026-04-08_docling-gpu-eval-v1`): `timings.json` rows with `cuda_status`/`cpu_status`, `ratio_cpu_per_cuda`; `outputs/cuda` + `outputs/cpu`.

**Round 3 paddle** (`2026-04-08_docling-paddle-round3-v1`): `benchmark_round == 3`, `rapidocr_backend == "paddle"`.

Use only when validating legacy run directories; **not** required for torch profile convergence.
