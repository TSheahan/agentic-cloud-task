# OWW Training Environment — State Convergence Profile

OpenWakeWord training environment for the "hey Sara" custom wake word model.
Layers on [aws-deep-learning-base](../aws-deep-learning-base/base-gpu-node.md)
— that profile must hold before this one is applied.

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

---

## Target State

All paths below are relative to the working directory on the instance
(e.g. `/home/ubuntu/hudsons-bay`).

### Python environment

- A venv exists (created from the Python 3.10 or 3.11 identified by the
  base profile).
- `openwakeword` is installed in editable mode with the `[full]` extra.
- **NumPy is version 1.x** (`numpy<2`). PyTorch 1.13.1 and torchmetrics
  crash under NumPy 2.x. The pin must be applied *after* OWW install
  because `pip install -e ".[full]"` may pull NumPy 2.
- `huggingface_hub` is installed (used for data downloads).

### Repositories

- `openwakeword/` — clone of `https://github.com/dscripka/openWakeWord.git`
- `piper-sample-generator/` — clone of
  `https://github.com/dscripka/piper-sample-generator.git`

### Training data

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

### Training config

- `hey_sara_model.yml` is present in the working directory. All relative
  paths in the YAML (`./piper-sample-generator`, `./validation_set_features.npy`,
  `./hey_sara_output`, etc.) resolve from the working directory.

### Post-training output

- `hey_sara_output/hey_sara.onnx` exists and is a valid ONNX model loadable
  by `openwakeword.model.Model`.

---

## Apply

Assumes the base GPU node profile already holds (apt fixed, system packages
installed, Python identified).

### 1. Create venv

```bash
cd /home/ubuntu/hudsons-bay
$PYTHON -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

### 2. Clone repositories

```bash
[ -d openwakeword ] || git clone https://github.com/dscripka/openWakeWord.git openwakeword
[ -d piper-sample-generator ] || git clone https://github.com/dscripka/piper-sample-generator.git
```

### 3. Install OWW and pin NumPy

Order matters: install OWW first (pulls its deps including potentially
NumPy 2), then force the pin.

```bash
cd openwakeword
pip install -e ".[full]"
cd ..
pip install "numpy<2"
```

### 4. Download training data from HuggingFace

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

### 5. Prepare background audio and RIRs

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

### 6. Upload training config

Ensure `hey_sara_model.yml` is present in the working directory. If
using `orchestrate.py`, it handles the upload. Otherwise, rsync or
SFTP from the controlling machine.

### 7. Run training

**Critical: run from the working directory** (where `hey_sara_model.yml`
and all relative paths resolve), not from `openwakeword/`.

```bash
cd /home/ubuntu/hudsons-bay
python -m openwakeword.train \
    --training_config hey_sara_model.yml \
    --generate_clips \
    --augment_clips \
    --train_model
```

The correct CLI flag is `--training_config` (not `--config`).

Expected wall time: 1-4 hours depending on instance type and sample count.

### 8. Collect output

```bash
ls -la hey_sara_output/hey_sara.onnx
cp hey_sara_output/hey_sara.onnx .
```

Transfer the ONNX file back to the controlling machine via rsync/SFTP.

### Known non-blocking noise

- ONNX Runtime DRM vendor library warning — harmless.
- `torchvision` missing — only needed for figure generation, not training.

---

## Audit

```bash
# 1. OWW importable
python -c "import openwakeword; print('PASS: openwakeword importable')"
```
Expected: `PASS: openwakeword importable`

```bash
# 2. NumPy version < 2
python -c "import numpy; v=int(numpy.__version__.split('.')[0]); print(f'numpy {numpy.__version__}'); assert v < 2, 'FAIL: numpy 2.x'"
```
Expected: `numpy 1.x.x`

```bash
# 3. Repos present
[ -d openwakeword ] && [ -d piper-sample-generator ] \
    && echo "PASS: repos cloned" \
    || echo "FAIL: repos missing"
```
Expected: `PASS: repos cloned`

```bash
# 4. Training data files
[ -f validation_set_features.npy ] \
    && [ -f openwakeword_features_ACAV100M_2000_hrs_16bit.npy ] \
    && echo "PASS: training data present" \
    || echo "FAIL: training data missing"
```
Expected: `PASS: training data present`

```bash
# 5. Training config resolvable
[ -f hey_sara_model.yml ] \
    && echo "PASS: training config present" \
    || echo "FAIL: training config missing"
```
Expected: `PASS: training config present`

```bash
# 6. ONNX output exists and is loadable (post-training)
python -c "
from openwakeword.model import Model
m = Model(wakeword_model_paths=['hey_sara_output/hey_sara.onnx'])
print(f'PASS: model loaded, keys={list(m.models.keys())}')
"
```
Expected: `PASS: model loaded, keys=['hey_sara']`
