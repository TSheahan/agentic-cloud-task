# OCR Batch Processing — State Convergence Profile

GPU-accelerated OCR batch processing environment using **Docling** with
**RapidOCR** backend. Repeatable: instance is built once, baked into a custom
AMI, and relaunched from that image for subsequent runs (~90 s boot to working
state).

Layers on [aws-deep-learning-base](../aws-deep-learning-base/base-gpu-node.profile.md)
— that profile must hold before this one is applied.

**Headless auth (Cursor agent CLI, GitHub / git HTTPS)** on the node is defined in
[headless-auth](../headless-auth/headless-auth.profile.md). Apply it after SSH works
if the workflow needs `agent` or `gh` on the instance.

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

**Transfer pattern:** scanned documents are deposited to the instance via SSH
(rsync/scp). S3 and AWS Batch are out of scope for this build; the interface is
SSH-only.

---

## Target State

### Instance, SSH, auth, and cataloged WORKDIR

These items specialize the [base GPU node](../aws-deep-learning-base/base-gpu-node.profile.md) **Instance** and **SSH** Target State and [headless-auth](../headless-auth/headless-auth.profile.md) for OCR batch work. Default **slug** is **`ocr`**: EC2 **Name** tag and `~/.ssh/config` **Host** are **`cloud-task-ocr`** (pattern `cloud-task-<slug>` from the base profile).

- **A running OCR batch instance is launched and tracked in `cloud-resources.md`.** The instance is named **`cloud-task-ocr`**, matching `--tag` to [`tools/launch-spot-instance.py`](../../tools/launch-spot-instance.py). The gitignored [**`cloud-resources.md`**](../../cloud-resources.md) **Nodes** row for this instance records **Name**, **SSH Host**, **Instance ID**, **Public IP**, **Region**, **Type**, **Status**, **Notes**, and is kept current per root [AGENTS.md](../../AGENTS.md). Market type is **spot** (bulk OCR is interruptible and cost-sensitive); spot one-time requests require `--instance-initiated-shutdown-behavior terminate` (cannot use `stop` with spot interruption behavior `terminate`).

- **SSH is profiled for this instance on the controlling machine.** A per-instance **`Host`** entry exists in `~/.ssh/config` (default **`cloud-task-ocr`**), with **HostName** set to the instance public IP. **User**, **IdentityFile**, and `cloud-task-*` wildcard behavior follow the [local dev workstation profile](../local-dev-env/dev-workstation.profile.md). The **SSH (current)** section in **`cloud-resources.md`** lists usable commands for this host while it is **running** and the config entry matches.

- **Agent CLI and GitHub CLI are authenticated on the node** per [headless-auth](../headless-auth/headless-auth.profile.md): a trivial agent prompt completes without a login stall; **`gh --version`** succeeds; **`gh auth status`** exits 0; **`gh auth setup-git`** has been run so global git credential helper uses **`gh`** for HTTPS.

- **WORKDIR is named, recorded in `cloud-resources.md`, created on the instance, and uses durable storage by default.** The **Nodes** table **WORKDIR** column for this node's **SSH Host** contains the **absolute path** to the OCR working root (the same directory Apply uses for `mkdir` / `cd`). **Primary spec:** that path lives on **root EBS** (e.g. `/home/ubuntu/ocr-work`) so mutable state survives **stop → start** of the same instance; it is still subject to **terminate** and teardown policy.

### Working directory

- **WORKDIR is a flat directory on the instance, and is not inside the project repo clone.** At minimum, `venv/` is a direct child of WORKDIR. Mutable state (input queue, output results, processing scratch) lives only in WORKDIR. The cataloged path and storage class are defined in **Instance, SSH, auth, and cataloged WORKDIR** above.

### Python environment

- **A Python venv exists at `WORKDIR/venv`** (created from Python 3.10 identified by the base profile). pip, setuptools, and wheel are upgraded to current.

### OCR processing stack

- **Docling is installed with the RapidOCR extra.** `pip install "docling[rapidocr]"` in the venv. The following imports resolve without error:
  - `from docling.document_converter import DocumentConverter`
  - `from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions, AcceleratorOptions, AcceleratorDevice`
  - `from docling.datamodel.base import InputFormat`

- **`onnxruntime-gpu` is installed for CUDA-accelerated model inference.** Docling's layout analysis and table structure models use ONNX Runtime; `onnxruntime-gpu` provides `CUDAExecutionProvider` so these models run on the T4 GPU. `ort.get_available_providers()` includes `CUDAExecutionProvider`.

- **Docker is available on the instance.** Present from the DL AMI. Not required for the standalone proof-of-concept but available if needed.

### GPU verification

- **The T4 GPU is accessible and drivers are loaded.** `nvidia-smi` reports Tesla T4, ≥15 GB VRAM, and a functional driver. The `CUDAExecutionProvider` is listed by `onnxruntime`.

### Transfer and batch structure

_To be specified. Broad shape from the design brief:_

- **An input/output folder structure supports rsync-based batch flow.** _(placeholder — specific layout TBD: inbox, batch-in, batch-out, results. Documents are deposited via SSH, not S3.)_

### AMI bake readiness

- **The instance is bake-ready after initial build.** After the first full Apply cycle (common patterning + OCR stack install), the instance state is suitable for snapshotting into a custom AMI. Pre-bake secrets purge per [base-gpu-node](../aws-deep-learning-base/base-gpu-node.profile.md) Apply §5 is run before creating the image. The resulting AMI is recorded in `cloud-resources.md` and used for all subsequent launches.

---

## Apply

### 1. Launch instance (workstation)

On the **workstation**, with project **`venv/`** activated and **`.env`** loaded,
resolve the AMI from **`cloud-resources.md`**, then launch with slug **`ocr`**.

For **spot**, one-time requests require matching shutdown and interruption
behaviors — pass `--instance-initiated-shutdown-behavior terminate`:

```bash
python tools/launch-spot-instance.py \
    --ami <ami-id-from-cloud-resources.md> \
    --instance-type g4dn.xlarge \
    --volume-gb 125 \
    --tag cloud-task-ocr \
    --instance-initiated-shutdown-behavior terminate
```

If spot capacity is unavailable (`InsufficientInstanceCapacity`), retry after
a few minutes — g4dn spot in ap-southeast-2 can be temporarily exhausted.
On-demand requires a **Running On-Demand G and VT instances** vCPU quota > 0
(currently 0; quota increase pending as of 2026-04-08).

Update **`cloud-resources.md`** in the same session: add or refresh the **Nodes**
row. Leave **WORKDIR** as placeholder until §2 sets the path.

SSH to the node and converge **[aws-deep-learning-base](../aws-deep-learning-base/base-gpu-node.profile.md)**
if needed (baked AMI skips §2–4 of that profile). When the workflow needs
**Cursor agent CLI** or **`gh`** on the instance, run
**[headless-auth](../headless-auth/headless-auth.profile.md)** Apply / Audit.

### 2. Choose `WORKDIR` and create venv

```bash
WORKDIR=/home/ubuntu/ocr-work
mkdir -p "$WORKDIR"
cd "$WORKDIR"
PYTHON=$(command -v python3.11 || command -v python3.10)
$PYTHON -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

On the **workstation**, update **`cloud-resources.md`**: set the **WORKDIR** column
for this instance's **SSH Host** row to the absolute path.

### 3. Install OCR processing stack

```bash
cd /home/ubuntu/ocr-work
source venv/bin/activate

pip install "docling[rapidocr]"
pip install onnxruntime-gpu
```

`docling[rapidocr]` pulls in `docling` (2.85.0 at time of first install),
`rapidocr` (3.7.0), and their dependency trees. `onnxruntime-gpu` (1.23.2)
provides `CUDAExecutionProvider` for Docling's layout/table models.

Venv footprint after this step: ~5.8 GB. Disk usage ~50% of 125 GB root volume.

**Known noise:** `onnxruntime` emits a warning about
`/sys/class/drm/card0/device/vendor` — harmless; CUDA provider still loads.

### 4. Bake custom AMI

After the full build cycle, run the [base-gpu-node](../aws-deep-learning-base/base-gpu-node.profile.md) pre-bake secrets purge (Apply §5), then create the AMI:

```bash
python tools/create-ami.py --tag cloud-task-ocr --name ocr-batch-<date>
```

Record the new AMI in **`cloud-resources.md`**.

---

## Audit

Checks **1–2** run on the **workstation**. Checks **3–9** run **on the instance**
from **WORKDIR** (`/home/ubuntu/ocr-work`) with `venv` activated.

### 1. A running OCR batch instance is launched and tracked in `cloud-resources.md`

**Controlling machine** (project root, **`venv/`** active, **`.env`** loaded):

```bash
python tools/launch-spot-instance.py --tag cloud-task-ocr --check
```
Expected: `PASS: running instance i-... @ <ip> (tag=cloud-task-ocr)`

### 2. SSH is profiled for this instance on the controlling machine

**Controlling machine:**

```bash
ssh -G cloud-task-ocr 2>/dev/null | grep -i '^hostname '
```
Expected: `hostname <public-ip>` matching the instance's current address in **`cloud-resources.md`**.

### 3. Agent CLI and GitHub CLI are authenticated on the node

**On the instance:**

```bash
echo "reply ok" | agent -p 2>/dev/null \
    && echo "PASS: agent authenticated" \
    || echo "FAIL: agent not authenticated or not responding"
gh --version >/dev/null 2>&1 \
    && echo "PASS: gh installed" \
    || echo "FAIL: gh not found"
gh auth status >/dev/null 2>&1 \
    && echo "PASS: gh authenticated" \
    || echo "FAIL: gh not authenticated"
git config --global credential.helper 2>/dev/null | grep -q 'gh' \
    && echo "PASS: gh credential helper configured" \
    || echo "FAIL: gh credential helper not set"
```
Expected: four PASS lines.

### 4. WORKDIR is named, recorded in `cloud-resources.md`, created on the instance, and uses durable storage

**Catalog (workstation):** The **Nodes** row for **`cloud-task-ocr`** has a non-empty **WORKDIR** cell.

**On the instance:**

```bash
cd /home/ubuntu/ocr-work
test -d "$(pwd -P)" \
  && echo "PASS: WORKDIR exists at $(pwd -P)" \
  || echo "FAIL: WORKDIR missing or not a directory"
```
Expected: `PASS: WORKDIR exists at /home/ubuntu/ocr-work`

### 5. WORKDIR is a flat directory with venv, not inside the project repo clone

```bash
test -d venv \
  && case "$(pwd -P)" in */agentic-cloud-task|*/agentic-cloud-task/*)
       echo "FAIL: WORKDIR must not be inside the agentic-cloud-task repo path"
       ;;
     *)
       echo "PASS: WORKDIR layout and isolation OK"
       ;;
  esac
```
Expected: `PASS: WORKDIR layout and isolation OK`

### 6. A Python venv exists

```bash
[ -d venv ] && venv/bin/python --version 2>/dev/null \
    && echo "PASS: venv exists and python works" \
    || echo "FAIL: venv missing or broken"
```
Expected: `Python 3.10.12` then `PASS: venv exists and python works`

### 7. Docling is installed with the RapidOCR extra

```bash
venv/bin/python -c "
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions, AcceleratorOptions, AcceleratorDevice
from docling.datamodel.base import InputFormat
print('PASS: docling + RapidOCR imports OK')
"
```
Expected: `PASS: docling + RapidOCR imports OK`

### 8. `onnxruntime-gpu` is installed with CUDAExecutionProvider

```bash
venv/bin/python -c "
import onnxruntime as ort
providers = ort.get_available_providers()
assert 'CUDAExecutionProvider' in providers, f'FAIL: CUDA not in {providers}'
print(f'PASS: CUDAExecutionProvider available (providers={providers})')
"
```
Expected: `PASS: CUDAExecutionProvider available (providers=[..., 'CUDAExecutionProvider', ...])`

### 9. GPU is accessible

```bash
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null \
    && echo "PASS: GPU accessible" \
    || echo "FAIL: nvidia-smi failed"
```
Expected: `Tesla T4, <driver>, 15360 MiB` then `PASS: GPU accessible`

### 10. AMI bake readiness — instance is bake-ready

_Audit: pre-bake purge checks per base-gpu-node Audit §10, plus confirmation
that the OCR stack is installed and functional before snapshot._
