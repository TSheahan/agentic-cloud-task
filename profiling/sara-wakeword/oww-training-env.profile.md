# OWW Training Environment — State Convergence Profile

OpenWakeWord training environment for the "hey Sara" custom wake word model.
Layers on [aws-deep-learning-base](../aws-deep-learning-base/base-gpu-node.profile.md)
— that profile must hold before this one is applied.

**Headless auth (Cursor agent CLI, GitHub / git HTTPS)** on the node is defined in
[headless-auth](../headless-auth/headless-auth.profile.md). Apply it after SSH works
if the workflow needs `agent` or `gh` on the instance.

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

---

## Target State

### Instance, SSH, auth, and cataloged WORKDIR

These items specialize the [base GPU node](../aws-deep-learning-base/base-gpu-node.profile.md) **Instance** and **SSH** Target State and [headless-auth](../headless-auth/headless-auth.profile.md) for OWW training. Default **slug** is **`sara`**: EC2 **Name** tag and `~/.ssh/config` **Host** are **`cloud-task-sara`** (pattern `cloud-task-<slug>` from the base profile). Use a different slug only when you intentionally isolate multiple nodes and SSH hosts.

- **A running OWW training instance is launched and tracked in `cloud-resources.md`.** The instance is named with **`cloud-task-<slug>`** (default **`cloud-task-sara`**), matching `--tag` to [`tools/launch-spot-instance.py`](../../tools/launch-spot-instance.py). The gitignored [**`cloud-resources.md`**](../../cloud-resources.md) **Nodes** row for this instance records **Name**, **SSH Host**, **Instance ID**, **Public IP**, **Region**, **Type**, **Status**, **Notes**, and is kept current per root [AGENTS.md](../../AGENTS.md). Launch alignment (stop on guest shutdown, root volume delete on terminate, volume size, market type) is spelled out in Apply §1.

- **SSH is profiled for this instance on the controlling machine.** A per-instance **`Host`** entry exists in `~/.ssh/config` (default **`cloud-task-sara`**), with **HostName** set to the instance public IP. **User**, **IdentityFile**, and `cloud-task-*` wildcard behavior follow the [local dev workstation profile](../local-dev-env/dev-workstation.profile.md). The **SSH (current)** section in **`cloud-resources.md`** lists usable commands for this host while it is **running** and the config entry matches.

- **Agent CLI and GitHub CLI are authenticated on the node** per [headless-auth](../headless-auth/headless-auth.profile.md): a trivial agent prompt completes without a login stall; **`gh --version`** succeeds; **`gh auth status`** exits 0; **`gh auth setup-git`** has been run so global git credential helper uses **`gh`** for HTTPS.

- **WORKDIR is named, recorded in `cloud-resources.md`, created on the instance, and uses durable storage by default.** The **Nodes** table **WORKDIR** column for this node's **SSH Host** contains the **absolute path** to the OWW training root (the same directory Apply uses for `mkdir` / `cd`). **Primary spec:** that path lives on **root EBS** (e.g. `/home/ubuntu/oww-work`) so mutable state survives **stop → start** of the same instance; it is still subject to **terminate** and teardown policy. **Additionally, when instance-store NVMe is available** (e.g. DL AMI mount at `/opt/dlami/nvme`), WORKDIR may be placed under that mount for sequential I/O; record the **actual** absolute path in **`cloud-resources.md`** and treat the mount as **ephemeral** per AWS instance-store semantics—**rsync** irreplaceable artifacts to durable storage or off-node before terminate, and do not keep sole copies only on instance store.

### Working directory and capacity

- **WORKDIR is a flat directory on the instance with the core sibling paths, and is not inside the project repo clone.** At minimum, `hey_sara_model.yml`, `openwakeword/`, `piper-sample-generator/`, and `venv/` are direct children of `WORKDIR`. Downloaded `.npy` files and `hey_sara_output/` appear in the same directory as downloads and training complete (see Training data and Post-training items). Copy `hey_sara_model.yml` into `WORKDIR` at setup; read this profile from the repo clone. The repo clone is read-only context (profiles, config YAML); mutable state lives only in `WORKDIR`. The cataloged path and storage class are defined in **Instance, SSH, auth, and cataloged WORKDIR** above.
- **At least ~25 GB free space** is available on the filesystem that contains `WORKDIR` before large downloads and training (the ACAV negative-features `.npy` alone is ~17 GB; venv, Piper checkpoint, and artifacts add more).

### System (clip generation)

- **System package `libespeak-ng1` is installed.** The Python package `espeak-phonemizer` loads `libespeak-ng.so.1` via ctypes; without the distro library, `--generate_clips` fails at phonemization even when the Piper `.pt` model is present.

### Python environment

- **A Python venv exists** (created from the Python 3.10 or 3.11 identified by the base profile).
- **`openwakeword` is installed** in editable mode with the `[full]` extra, and **`import openwakeword.train`** (or another submodule) resolves to the real package — not only an empty top-level namespace. The working directory usually contains a git clone at `./openwakeword/`; on `sys.path`, a bare `import openwakeword` from the parent directory can bind to a namespace over that tree and omit `FEATURE_MODELS`, breaking `download_models()`. Use **`python -m openwakeword.train` from `WORKDIR`**, or `import openwakeword.train`, or **`cd openwakeword`** before ad-hoc scripts. Audits use submodule imports for this reason.
- **OpenWakeWord feature models are present** under `openwakeword/openwakeword/resources/models/` — at minimum `melspectrogram.onnx` and `embedding_model.onnx`. These are not in the git clone; fetch them with `openwakeword.utils.download_models()` (GitHub release assets). Training fails at “Computing openwakeword features” if they are missing.
- **NumPy is version 1.x** (`numpy<2`). PyTorch 1.13.1 and torchmetrics crash under NumPy 2.x. Re-apply `pip install "numpy<2"` after `pip install -r piper-sample-generator/requirements.txt` — that file lists unpinned `numpy`, and pip may upgrade NumPy to 2.x.
- **`huggingface_hub` is installed** (used for data downloads).

### Piper clip generation

- **Piper sample generation is provisioned for `--generate_clips`:**
  - Python: `webrtcvad` and `espeak_phonemizer` (from PyPI as `espeak-phonemizer`) — satisfied by `pip install -r piper-sample-generator/requirements.txt` in the training venv, with **`numpy<2` re-applied afterward**.
  - Voice model: `piper-sample-generator/models/en-us-libritts-high.pt` and companion `en-us-libritts-high.pt.json`. The `.pt` is gitignored upstream; download from the [rhasspy Piper sample-generator release](https://github.com/rhasspy/piper-sample-generator/releases/download/v1.0.0/en-us-libritts-high.pt) (see `piper-sample-generator/README.md`).

### Repositories

- **Required repositories are cloned:**
  - `openwakeword/` — from `https://github.com/dscripka/openWakeWord.git`
  - `piper-sample-generator/` — from `https://github.com/dscripka/piper-sample-generator.git`

### Training data

- **Training data files are present:**
  - `validation_set_features.npy` — from HuggingFace (`davidscripka/openwakeword_features`, filename `validation_set_features.npy`). Not `openwakeword_features.npy` (renamed upstream; 404).
  - `openwakeword_features_ACAV100M_2000_hrs_16bit.npy` — negative feature data from the same HF dataset.
  - `background_clips/` contains at least one audio file (e.g. a minimal 60s silence WAV) for false-positive training.
  - `mit_rirs/` — MIT Room Impulse Responses (WAV files). Optional for a first pass; training proceeds without RIRs but reverb augmentation is skipped.

Optional: set `HF_TOKEN` when downloading from HuggingFace to improve rate limits (unauthenticated requests work but may be throttled).

### Training config

- **`hey_sara_model.yml` is present** in the working directory. All relative paths in the YAML (`./piper-sample-generator`, `./validation_set_features.npy`, `./hey_sara_output`, etc.) resolve from the working directory.

### Post-training output

- **`hey_sara_output/hey_sara.onnx` exists** and is a valid ONNX model loadable by `openwakeword.model.Model`.

---

## Apply

### 1. Launch instance (workstation) and headless auth (node)

On the **workstation**, with project **`venv/`** activated and **`.env`** loaded,
resolve the AMI from **`cloud-resources.md`**, then launch. Default **slug** is
**`sara`**: pass **`--tag cloud-task-sara`** so the EC2 **Name** tag and SSH
**Host** follow the `cloud-task-<slug>` pattern from
[base-gpu-node](../aws-deep-learning-base/base-gpu-node.profile.md) (use another
slug only when isolating multiple nodes).

```bash
# From project root, after:  venv\Scripts\activate   (Windows)
# or:  source venv/bin/activate   (Linux/macOS)
python tools/launch-spot-instance.py \
    --ami <ami-id-from-cloud-resources.md> \
    --instance-type g4dn.xlarge \
    --volume-gb 80 \
    --tag cloud-task-sara \
    --instance-initiated-shutdown-behavior stop
```

Align with Target State: **stop** (not terminate) on guest OS shutdown (`--instance-initiated-shutdown-behavior stop`, tool default); **do not** pass **`--persist-root-volume`** (unless you document an exception in **`cloud-resources.md`**) so the root volume **deletes on instance termination**; size **`--volume-gb`** for the ~25 GB+ headroom item in Target State. Use **`--market-type on-demand`** to avoid spot reclaim mid-run, or **`--market-type spot`** for cost with appropriate **`--spot-interruption-behavior`**.

See **`python tools/launch-spot-instance.py --help`** for all flags (`--spot-interruption-behavior`,
`--ssh-host-alias`, `--no-ssh-config`, etc.).

Update **`cloud-resources.md`** in the same session (per root [AGENTS.md](../../AGENTS.md)):
add or refresh the **Nodes** row (**Name**, **SSH Host**, **Instance ID**, **Public IP**,
**Region**, **Type**, **Status**, **Notes**). Leave **WORKDIR** empty or placeholder until
Apply §3 sets the path; update **SSH (current)** with usable commands for the **Host**
that matches **`cloud-task-<slug>`** (default **`cloud-task-sara`**).

SSH to the node and converge **[aws-deep-learning-base](../aws-deep-learning-base/base-gpu-node.profile.md)**
if needed. When the workflow needs **Cursor agent CLI** or **`gh`** on the instance,
run **[headless-auth](../headless-auth/headless-auth.profile.md)** Apply / Audit
there.

---

Assumes the base GPU node profile already holds (apt fixed, system packages
installed, Python identified). Run the remaining commands **on the instance** from
the chosen **working directory** (`WORKDIR` below).

### 2. System library for Piper phonemization

Not included in the default base GPU package set; install on the instance if missing:

```bash
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y libespeak-ng1
```

### 3. Choose `WORKDIR` and create venv

**Default (Target State):** use **durable root EBS** — not instance-store NVMe —
unless you explicitly accept ephemeral storage for speed. Set **`REPOROOT`** to the
clone of this repo on the instance (default layout below).

```bash
REPOROOT=/home/ubuntu/agentic-cloud-task
# Primary: durable path on root EBS (survives stop/start of this instance).
WORKDIR=/home/ubuntu/oww-work
# Optional: for heavy sequential I/O on huge .npy files, set WORKDIR under
# instance-store NVMe instead (ephemeral per AWS — record path + warning in
# cloud-resources.md Notes), e.g. after confirming `mountpoint -q /opt/dlami/nvme`:
#   WORKDIR=/opt/dlami/nvme/sara-wakeword
mkdir -p "$WORKDIR"
cd "$WORKDIR"
cp "$REPOROOT/profiling/sara-wakeword/hey_sara_model.yml" .
PYTHON=${PYTHON:-$(command -v python3.11 || command -v python3.10)}
$PYTHON -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

On the **workstation**, update **`cloud-resources.md`**: set the **WORKDIR** column
for this instance's **SSH Host** row to the absolute path (`pwd -P` on the node
from this directory). If **`WORKDIR`** is under **`/opt/dlami/nvme`**, add a
**Notes** flag that training state is on **instance store** (ephemeral).

### 4. Clone repositories

```bash
[ -d openwakeword ] || git clone https://github.com/dscripka/openWakeWord.git openwakeword
[ -d piper-sample-generator ] || git clone https://github.com/dscripka/piper-sample-generator.git piper-sample-generator
```

### 5. Install OpenWakeWord and first NumPy pin

```bash
cd openwakeword
pip install -e ".[full]"
cd ..
pip install "numpy<2"
```

### 6. Download OpenWakeWord feature models (not in git)

The clone does not include `resources/models/*.onnx` / `*.tflite`. Install the
release assets into the package tree (editable install writes under
`openwakeword/openwakeword/resources/models/`).

Run **`python -c "…download_models()"` from inside the `openwakeword/` repo
directory** (not the parent working directory): if the parent folder is also named
`openwakeword`, a bare `import openwakeword` from the parent can resolve to a
broken namespace package and `download_models()` will fail.

```bash
cd "$WORKDIR"/openwakeword
source ../venv/bin/activate
python -c "from openwakeword.utils import download_models; download_models()"
cd "$WORKDIR"
```

This also downloads bundled wakeword checkpoints and VAD weights; only the
melspectrogram and embedding ONNX files are required for training feature
extraction, but pulling the full set matches upstream defaults.

### 7. Piper Python dependencies, then re-pin NumPy

`piper-sample-generator/requirements.txt` includes unpinned `numpy`; installing it
may upgrade NumPy to 2.x. Always re-apply the pin after.

```bash
pip install -r piper-sample-generator/requirements.txt
pip install "numpy<2"
```

After this, `pip check` may still report conflicts (e.g. `numpy-minmax` /
`numpy-rms` prefer NumPy ≥2). Training has run successfully with **NumPy 1.x**
re-pinned; treat resolver noise as expected unless imports or training fail.

### 8. Download Piper voice model (not in git)

```bash
mkdir -p piper-sample-generator/models
wget -O piper-sample-generator/models/en-us-libritts-high.pt \
  'https://github.com/rhasspy/piper-sample-generator/releases/download/v1.0.0/en-us-libritts-high.pt'
# Companion JSON is usually present in the clone; if missing, obtain from the same release tree.
```

### 9. Download training data from HuggingFace

```bash
pip install huggingface_hub

python -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='davidscripka/openwakeword_features',
    filename='validation_set_features.npy',
    repo_type='dataset',
    local_dir='.',
)
"

python -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='davidscripka/openwakeword_features',
    filename='openwakeword_features_ACAV100M_2000_hrs_16bit.npy',
    repo_type='dataset',
    local_dir='.',
)
"
```

If HuggingFace rate-limits or 404s on a filename, check the dataset page
for renames. This has happened before (the original filename
`openwakeword_features.npy` was renamed to `validation_set_features.npy`).

### 10. Prepare background audio and RIRs

```bash
# Minimal background placeholder (sufficient for first pass)
mkdir -p background_clips
[ -f background_clips/silence.wav ] || \
    ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 60 -c:a pcm_s16le background_clips/silence.wav -y 2>/dev/null

# MIT RIRs — skip on first pass if download is not automated
mkdir -p mit_rirs
```

For production-quality training, source proper background audio and the
MIT RIR dataset. The training pipeline degrades gracefully without RIRs
(skips reverb augmentation) and with minimal background audio.

### 11. Training config

`hey_sara_model.yml` should already be in **`WORKDIR`** from §3. If not, copy from
**`$REPOROOT/profiling/sara-wakeword/hey_sara_model.yml`** or rsync from the
workstation.

### 12. Run training

**Critical: run from the working directory** (where `hey_sara_model.yml`
and all relative paths resolve), not from `openwakeword/`.

```bash
cd "$WORKDIR"
source venv/bin/activate
python -m openwakeword.train \
    --training_config hey_sara_model.yml \
    --generate_clips \
    --augment_clips \
    --train_model
```

The correct CLI flag is `--training_config` (not `--config`).

**Re-runs:** If clip subdirectories already contain files from a previous run, the
trainer may **skip** some clip-generation steps and continue (watch logs for
“Skipping generation…”). To force regeneration, clear those directories first.

**Re-running with `--generate_clips`:** The pipeline may log that it is skipping
negative (or other) clip batches when enough WAVs already exist in the configured
output directories — not necessarily a full regeneration. For a clean clip pass,
remove the relevant clip output directories first (see OpenWakeWord `train.py` /
config for paths), accepting longer wall time.

Expected wall time: 1-4 hours depending on instance type and sample count.

### 13. Collect output

```bash
ls -la hey_sara_output/hey_sara.onnx
cp hey_sara_output/hey_sara.onnx .
```

Transfer the ONNX file back to the controlling machine via rsync/SFTP.

### Known non-blocking noise

- ONNX Runtime DRM vendor library warning — harmless.
- If `onnxruntime` is CPU-only, you may see that **`CUDAExecutionProvider` is not
  available** and a warning about GPU device discovery; feature extraction falls
  back to **CPU** unless you install **`onnxruntime-gpu`** matching your CUDA
  stack (optional; slower but valid).
- `torchvision` missing — only needed for figure generation, not training.
- `torchmetrics` / `webrtcvad` may warn about `pkg_resources` / setuptools
  deprecation — harmless unless setuptools removal breaks a dependency; pin
  `setuptools<81` only if you need quiet logs.
- **`torch_audiomentations`** may emit `FutureWarning` about an `output_type`
  argument — upstream library noise, not a training failure.
- **`audiomentations`** may warn about `float64` samples being converted to
  `float32` — benign.

---

## Audit

**Where to run:** Checks **1** (tool + **`cloud-resources.md`** row) and **2**
(**`ssh -G`**) use the **workstation**. Check **3** runs **on the instance**.
Check **4** uses the **catalog** on the workstation and a path test **on the
instance** (SSH session). Checks **5–17** assume a shell **cd**’d to **WORKDIR** on
the instance, using **`venv/bin/python`** where noted (or activate **`venv/`**
first).

Do **not** rely on a bare `import openwakeword` as the only check — with a
sibling `./openwakeword` repo directory, it can resolve to a **namespace** that
does not expose the real package API. Prefer **`import openwakeword.train`** or
imports from **`openwakeword.model`** (see Target State, Python environment).

There is **one check per Target State item**, in the same order as the bold
items under Target State (from **Instance, SSH, auth, and cataloged WORKDIR**
through **Post-training output**). Each heading below names the item it verifies.
If you use a slug other than **`sara`**, substitute **`cloud-task-<slug>`** in
workstation commands.

### 1. A running OWW training instance is launched and tracked in `cloud-resources.md`

**Controlling machine** (project root, **`venv/`** active, **`.env`** loaded):

```bash
python tools/launch-spot-instance.py --tag cloud-task-sara --check
```
Expected: `PASS: running instance i-... @ <ip> (tag=cloud-task-sara)` (exact
wording from the tool).

**Catalog (executor on workstation):** Open gitignored **`cloud-resources.md`**.
Confirm a **Nodes** row exists for this instance whose **Name** and **SSH Host**
match **`cloud-task-sara`** (or your **`cloud-task-<slug>`**) and whose
**Instance ID** / **Public IP** match the running instance from the check above.

### 2. SSH is profiled for this instance on the controlling machine

**Controlling machine:**

```bash
ssh -G cloud-task-sara 2>/dev/null | grep -i '^hostname '
```
Expected: a line `hostname <public-ip>` where **`<public-ip>`** matches the
instance’s current address in **`cloud-resources.md`**. If **`Host`** differs
from **`cloud-task-sara`**, substitute that **Host** in the command.

### 3. Agent CLI and GitHub CLI are authenticated on the node

**On the instance** (compound check; matches [headless-auth](../headless-auth/headless-auth.profile.md) audits):

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
Expected: four lines containing **`PASS: agent authenticated`**, **`PASS: gh installed`**, **`PASS: gh authenticated`**, and **`PASS: gh credential helper configured`**.

### 4. WORKDIR is named, recorded in `cloud-resources.md`, created on the instance, and uses durable storage by default

**Catalog (workstation):** The **Nodes** row for **`cloud-task-sara`** (or your
**`cloud-task-<slug>`**) has a non-empty **WORKDIR** cell with the **absolute path**
the operator uses on the instance (set in Apply §3).

**On the instance**, with **`WORKDIR_PATH`** set to that cataloged path (or after
`cd` to **WORKDIR** so **`$(pwd -P)`** is correct):

```bash
WORKDIR_PATH=$(pwd -P)
test -n "$WORKDIR_PATH" && test -d "$WORKDIR_PATH" \
  && echo "PASS: WORKDIR exists at $WORKDIR_PATH" \
  || echo "FAIL: WORKDIR missing or not a directory"
case "$WORKDIR_PATH" in
  /opt/dlami/nvme/*)
    echo "NOTE: WORKDIR is under instance-store NVMe (ephemeral); confirm cloud-resources.md Notes"
    ;;
  *)
    echo "NOTE: WORKDIR not under /opt/dlami/nvme (default durable root-EBS-style layout)"
    ;;
esac
```
Expected: `PASS: WORKDIR exists at /...` and either **NOTE** line. If WORKDIR is
on NVMe, **Notes** in **`cloud-resources.md`** should call out instance store.

### 5. WORKDIR is a flat directory with the core sibling paths, and is not inside the project repo clone

```bash
test -f hey_sara_model.yml \
  && test -d openwakeword \
  && test -d piper-sample-generator \
  && test -d venv \
  && case "$(pwd -P)" in */agentic-cloud-task|*/agentic-cloud-task/*)
       echo "FAIL: WORKDIR must not be inside the agentic-cloud-task repo path"
       exit 1
       ;;
     *)
       echo "PASS: WORKDIR layout and isolation OK"
       ;;
   esac
```
Expected: `PASS: WORKDIR layout and isolation OK`

### 6. At least ~25 GB free space on the filesystem containing WORKDIR

```bash
AVAIL=$(df -BG --output=avail . 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -n "$AVAIL" ] && [ "$AVAIL" -ge 25 ] 2>/dev/null; then
  echo "PASS: >=25G avail on WORKDIR filesystem ($AVAIL G)"
else
  echo "FAIL: need ~25GB+ free on filesystem containing WORKDIR (avail=${AVAIL:-unknown})"
fi
```
Expected: `PASS: >=25G avail on WORKDIR filesystem (... G)`

### 7. System package `libespeak-ng1` is installed

```bash
dpkg -l libespeak-ng1 2>/dev/null | grep -q '^ii' \
    && echo "PASS: libespeak-ng1 installed" \
    || echo "FAIL: libespeak-ng1 missing"
```
Expected: `PASS: libespeak-ng1 installed`

### 8. A Python venv exists

```bash
[ -d venv ] && venv/bin/python --version 2>/dev/null \
    && echo "PASS: venv exists and python works" \
    || echo "FAIL: venv missing or broken"
```
Expected: `Python 3.x.x` on the first line, then `PASS: venv exists and python works`

### 9. `openwakeword` is installed (editable package reachable)

```bash
venv/bin/python -c "import openwakeword.train; print('PASS: openwakeword.train importable')"
```
Expected: `PASS: openwakeword.train importable`

### 10. OpenWakeWord feature models are present under `resources/models`

```bash
test -f openwakeword/openwakeword/resources/models/melspectrogram.onnx \
    && test -f openwakeword/openwakeword/resources/models/embedding_model.onnx \
    && echo "PASS: OWW feature ONNX models present" \
    || echo "FAIL: run download_models() from openwakeword/ repo dir (see Apply §6)"
```
Expected: `PASS: OWW feature ONNX models present`

### 11. NumPy is version 1.x

```bash
venv/bin/python -c "import numpy; v=int(numpy.__version__.split('.')[0]); print(f'numpy {numpy.__version__}'); assert v < 2, 'FAIL: numpy 2.x'"
```
Expected: `numpy 1.x.x`

### 12. `huggingface_hub` is installed

```bash
venv/bin/python -c "import huggingface_hub; print('PASS: huggingface_hub importable')"
```
Expected: `PASS: huggingface_hub importable`

### 13. Piper sample generation is provisioned for `--generate_clips`

```bash
test -f piper-sample-generator/models/en-us-libritts-high.pt \
    && test -f piper-sample-generator/models/en-us-libritts-high.pt.json \
    && venv/bin/python -c "import webrtcvad; from espeak_phonemizer import Phonemizer; Phonemizer('en-us'); print('PASS: Piper deps and model files OK')" \
    || echo "FAIL: Piper model or Python deps"
```
Expected: `PASS: Piper deps and model files OK`

### 14. Required repositories are cloned

```bash
[ -d openwakeword ] && [ -d piper-sample-generator ] \
    && echo "PASS: repos cloned" \
    || echo "FAIL: repos missing"
```
Expected: `PASS: repos cloned`

### 15. Training data files are present

```bash
[ -f validation_set_features.npy ] \
    && [ -f openwakeword_features_ACAV100M_2000_hrs_16bit.npy ] \
    && [ -d background_clips ] \
    && [ "$(find background_clips -maxdepth 1 -type f 2>/dev/null | wc -l)" -ge 1 ] \
    && echo "PASS: training data present" \
    || echo "FAIL: training data missing (npys, background_clips/, or empty background_clips)"
```
Expected: `PASS: training data present`

### 16. `hey_sara_model.yml` is present in the working directory

```bash
[ -f hey_sara_model.yml ] \
    && echo "PASS: training config present" \
    || echo "FAIL: training config missing"
```
Expected: `PASS: training config present`

### 17. `hey_sara_output/hey_sara.onnx` exists and loads as a valid model

```bash
venv/bin/python -c "
from openwakeword.model import Model
m = Model(wakeword_model_paths=['hey_sara_output/hey_sara.onnx'])
print(f'PASS: model loaded, keys={list(m.models.keys())}')
"
```
Expected: `PASS: model loaded, keys=['hey_sara']`
