# OWW Training Environment — State Convergence Profile

OpenWakeWord training environment for the "hey Sara" custom wake word model.
Layers on [aws-deep-learning-base](../aws-deep-learning-base/base-gpu-node.profile.md)
— that profile must hold before this one is applied.

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

---

## Target State

Use a **single flat working directory** on the instance where `hey_sara_model.yml`,
`openwakeword/`, `piper-sample-generator/`, downloaded `.npy` files, `venv/`, and
`hey_sara_output/` all live as siblings.

**`WORKDIR` must be outside the project repo clone.** The repo is read-only context
(profiles, config YAML); all mutable state (venv, clones, downloads, training
output) goes in `WORKDIR`. Copy `hey_sara_model.yml` into `WORKDIR` at setup; read
the profile from the repo.

**Ephemeral NVMe storage:** g4dn instances expose fast instance-store NVMe,
pre-mounted by the DL AMI at **`/opt/dlami/nvme`** (ext4, `rw,noatime`). Use this
for `WORKDIR` — e.g. `/opt/dlami/nvme/sara-wakeword`. Benefits: ~125 GB available,
higher sequential throughput than gp3 (good for 17 GB `.npy` reads and heavy clip
I/O), and naturally ephemeral so no cleanup needed before termination. **Confirm the
mount exists on boot** (`df -h /opt/dlami/nvme`); if absent, fall back to a path on
the root volume outside the repo (e.g. `/home/ubuntu/oww-work`).

> **TODO (next run):** The Apply steps below still show an in-repo `WORKDIR` default
> from the first execution. Update snippets to default to `/opt/dlami/nvme/sara-wakeword`,
> add a step that confirms the mount and copies `hey_sara_model.yml` from the repo,
> and verify the full flow end-to-end on ephemeral storage before considering this
> profile converged.

**Disk:** allow roughly **25 GB+** free before starting: the ACAV negative-features
`.npy` alone is ~17 GB; the venv, Piper voice checkpoint, and training artifacts
add more. The NVMe instance store easily covers this.

**Python import path:** The working directory usually contains a git clone at
`./openwakeword/` (repo root). On `sys.path`, the name **`openwakeword` can bind
to a namespace package over that directory** instead of the real install, so a
bare `import openwakeword` may succeed but **omit** `FEATURE_MODELS` and break
`download_models()` if run from the parent directory. **`python -m openwakeword.train`
from `WORKDIR` resolves the installed package correctly.** For ad-hoc Python,
`import openwakeword.train` or run scripts with **`cd openwakeword`** (inner repo)
first. Audits below use submodule imports for this reason.

### System (clip generation)

- **System package `libespeak-ng1` is installed.** The Python package
  `espeak-phonemizer` loads `libespeak-ng.so.1` via ctypes; without the distro
  library, `--generate_clips` fails at phonemization even when the Piper `.pt`
  model is present.

### Python environment

- **A Python venv exists** (created from the Python 3.10 or 3.11 identified
  by the base profile).
- **`openwakeword` is installed** in editable mode with the `[full]` extra, and
  **`import openwakeword.train`** (or another submodule) resolves to the real
  package — not only an empty top-level namespace (see layout note above).
- **OpenWakeWord feature models are present** under
  `openwakeword/openwakeword/resources/models/` — at minimum `melspectrogram.onnx`
  and `embedding_model.onnx`. These are **not** in the git clone; fetch them with
  `openwakeword.utils.download_models()` (GitHub release assets). Training fails
  at “Computing openwakeword features” if they are missing.
- **NumPy is version 1.x** (`numpy<2`). PyTorch 1.13.1 and torchmetrics
  crash under NumPy 2.x. Re-apply `pip install "numpy<2"` **after**
  `pip install -r piper-sample-generator/requirements.txt` — that requirements
  file lists unpinned `numpy`, and pip may upgrade NumPy to 2.x.
- **`huggingface_hub` is installed** (used for data downloads).

### Piper clip generation

- **Piper sample generation is provisioned for `--generate_clips`:**
  - Python: `webrtcvad` and `espeak_phonemizer` (from PyPI as `espeak-phonemizer`)
    — satisfied by `pip install -r piper-sample-generator/requirements.txt` in
    the training venv, with **`numpy<2` re-applied afterward**.
  - Voice model: `piper-sample-generator/models/en-us-libritts-high.pt` and
    companion `en-us-libritts-high.pt.json`. The `.pt` is gitignored upstream;
    download from the [rhasspy Piper sample-generator release](https://github.com/rhasspy/piper-sample-generator/releases/download/v1.0.0/en-us-libritts-high.pt)
    (see `piper-sample-generator/README.md`).

### Repositories

- **Required repositories are cloned:**
  - `openwakeword/` — from `https://github.com/dscripka/openWakeWord.git`
  - `piper-sample-generator/` — from
    `https://github.com/dscripka/piper-sample-generator.git`

### Training data

- **Training data files are present:**
  - `validation_set_features.npy` — false-positive validation features from
    HuggingFace (`davidscripka/openwakeword_features`, filename
    `validation_set_features.npy`). **Not** `openwakeword_features.npy` —
    that filename was renamed upstream and returns 404.
  - `openwakeword_features_ACAV100M_2000_hrs_16bit.npy` — negative feature
    data from the same HF dataset.
  - `mit_rirs/` — MIT Room Impulse Responses (WAV files). Optional for a
    first pass; training proceeds without RIRs but reverb augmentation is
    skipped.
  - `background_clips/` — background audio for false-positive training. A
    minimal placeholder (60s silence WAV) is sufficient for a first pass.

Optional: set **`HF_TOKEN`** in the environment when downloading from HuggingFace
to improve rate limits (unauthenticated requests work but may be throttled).

### Training config

- **`hey_sara_model.yml` is present** in the working directory. All relative
  paths in the YAML (`./piper-sample-generator`, `./validation_set_features.npy`,
  `./hey_sara_output`, etc.) resolve from the working directory.

### Post-training output

- **`hey_sara_output/hey_sara.onnx` exists** and is a valid ONNX model
  loadable by `openwakeword.model.Model`.

### Re-runs and partial state

- **Re-running `train.py` with `--generate_clips`:** The pipeline may **log that
  it is skipping** negative (or other) clip batches when **enough WAVs already
  exist** in the configured output directories — not necessarily a full
  regeneration. For a **clean** clip pass, remove the relevant clip output
  directories first (see OpenWakeWord `train.py` / config for paths), accepting
  the cost of longer wall time.

---

## Apply

Assumes the base GPU node profile already holds (apt fixed, system packages
installed, Python identified). Run all commands from the chosen **working directory**
(`WORKDIR` below — adjust to match your layout).

### 1. System library for Piper phonemization

Not included in the default base GPU package set; install on the instance if missing:

```bash
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y libespeak-ng1
```

### 2. Create venv

```bash
WORKDIR=/home/ubuntu/agentic-cloud-task/profiling/sara-wakeword
cd "$WORKDIR"
PYTHON=${PYTHON:-$(command -v python3.11 || command -v python3.10)}
$PYTHON -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

### 3. Clone repositories

```bash
[ -d openwakeword ] || git clone https://github.com/dscripka/openWakeWord.git openwakeword
[ -d piper-sample-generator ] || git clone https://github.com/dscripka/piper-sample-generator.git piper-sample-generator
```

### 4. Install OpenWakeWord and first NumPy pin

```bash
cd openwakeword
pip install -e ".[full]"
cd ..
pip install "numpy<2"
```

### 5. Download OpenWakeWord feature models (not in git)

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

### 6. Piper Python dependencies, then re-pin NumPy

`piper-sample-generator/requirements.txt` includes unpinned `numpy`; installing it
may upgrade NumPy to 2.x. Always re-apply the pin after.

```bash
pip install -r piper-sample-generator/requirements.txt
pip install "numpy<2"
```

After this, `pip check` may still report conflicts (e.g. `numpy-minmax` /
`numpy-rms` prefer NumPy ≥2). Training has run successfully with **NumPy 1.x**
re-pinned; treat resolver noise as expected unless imports or training fail.

### 7. Download Piper voice model (not in git)

```bash
mkdir -p piper-sample-generator/models
wget -O piper-sample-generator/models/en-us-libritts-high.pt \
  'https://github.com/rhasspy/piper-sample-generator/releases/download/v1.0.0/en-us-libritts-high.pt'
# Companion JSON is usually present in the clone; if missing, obtain from the same release tree.
```

### 8. Download training data from HuggingFace

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

### 9. Prepare background audio and RIRs

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

### 10. Training config

Ensure `hey_sara_model.yml` is present in the working directory (in-repo under
`profiling/sara-wakeword/` when using this project layout). If using
`orchestrate.py`, it handles the upload. Otherwise, rsync or SFTP from the
controlling machine.

### 11. Run training

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

Expected wall time: 1-4 hours depending on instance type and sample count.

### 12. Collect output

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

Run from the **working directory**, using **`venv/bin/python`** so checks do not
depend on an activated shell (or `source venv/bin/activate` first and use `python`).

Do **not** rely on a bare `import openwakeword` as the only check — with a
sibling `./openwakeword` repo directory, it can resolve to a **namespace** that
does not expose the real package API. Prefer **`import openwakeword.train`** or
imports from **`openwakeword.model`** (see Target State, Python import path).

### 1. A Python venv exists

```bash
[ -d venv ] && venv/bin/python --version 2>/dev/null \
    && echo "PASS: venv exists and python works" \
    || echo "FAIL: venv missing or broken"
```
Expected: `Python 3.x.x` followed by `PASS: venv exists and python works`

### 2. `openwakeword` is installed (editable package reachable)

```bash
venv/bin/python -c "import openwakeword.train; print('PASS: openwakeword.train importable')"
```
Expected: `PASS: openwakeword.train importable`

### 3. NumPy is version 1.x

```bash
venv/bin/python -c "import numpy; v=int(numpy.__version__.split('.')[0]); print(f'numpy {numpy.__version__}'); assert v < 2, 'FAIL: numpy 2.x'"
```
Expected: `numpy 1.x.x`

### 4. `huggingface_hub` is installed

```bash
venv/bin/python -c "import huggingface_hub; print('PASS: huggingface_hub importable')"
```
Expected: `PASS: huggingface_hub importable`

### 5. Required repositories are cloned

```bash
[ -d openwakeword ] && [ -d piper-sample-generator ] \
    && echo "PASS: repos cloned" \
    || echo "FAIL: repos missing"
```
Expected: `PASS: repos cloned`

### 6. OpenWakeWord `resources/models` assets (feature extraction)

```bash
test -f openwakeword/openwakeword/resources/models/melspectrogram.onnx \
    && test -f openwakeword/openwakeword/resources/models/embedding_model.onnx \
    && echo "PASS: OWW feature ONNX models present" \
    || echo "FAIL: run download_models() from openwakeword/ repo dir (see Apply §5)"
```
Expected: `PASS: OWW feature ONNX models present`

### 7. System package `libespeak-ng1` is installed

```bash
dpkg -l libespeak-ng1 2>/dev/null | grep -q '^ii' \
    && echo "PASS: libespeak-ng1 installed" \
    || echo "FAIL: libespeak-ng1 missing"
```
Expected: `PASS: libespeak-ng1 installed`

### 8. Piper sample generation is provisioned

```bash
test -f piper-sample-generator/models/en-us-libritts-high.pt \
    && test -f piper-sample-generator/models/en-us-libritts-high.pt.json \
    && venv/bin/python -c "import webrtcvad; from espeak_phonemizer import Phonemizer; Phonemizer('en-us'); print('PASS: Piper deps and model files OK')" \
    || echo "FAIL: Piper model or Python deps"
```
Expected: `PASS: Piper deps and model files OK`

### 9. Training data files are present

```bash
[ -f validation_set_features.npy ] \
    && [ -f openwakeword_features_ACAV100M_2000_hrs_16bit.npy ] \
    && echo "PASS: training data present" \
    || echo "FAIL: training data missing"
```
Expected: `PASS: training data present`

### 10. `hey_sara_model.yml` is present

```bash
[ -f hey_sara_model.yml ] \
    && echo "PASS: training config present" \
    || echo "FAIL: training config missing"
```
Expected: `PASS: training config present`

### 11. `hey_sara_output/hey_sara.onnx` exists

```bash
venv/bin/python -c "
from openwakeword.model import Model
m = Model(wakeword_model_paths=['hey_sara_output/hey_sara.onnx'])
print(f'PASS: model loaded, keys={list(m.models.keys())}')
"
```
Expected: `PASS: model loaded, keys=['hey_sara']`
