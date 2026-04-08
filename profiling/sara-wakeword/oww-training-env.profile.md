# OWW Training Environment — State Convergence Profile

OpenWakeWord training environment for the "hey Sara" custom wake word model.
Layers on [aws-deep-learning-base](../aws-deep-learning-base/base-gpu-node.profile.md)
— that profile must hold before this one is applied.

**Headless auth (Cursor agent CLI, GitHub / git HTTPS)** on the node is defined in
[headless-auth](../headless-auth/headless-auth.profile.md). Apply it after SSH works
if the workflow needs `agent` or `gh` on the instance.

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

**Happy path:** pre-generate positive and adversarial-negative WAVs with **Cartesia**
(preferred single cloud TTS) via [`generate_samples.py`](generate_samples.py) on a
machine with API keys, rsync them into the layout under `hey_sara_output/<model_name>/`,
then run **`openwakeword.train`** **without** `--generate_clips`. **Piper** (upstream
OWW’s built-in TTS path) is **deprecated** here — full steps live in **Appendix A
(deprecated Piper fallback)** only if an agent must re-enable Piper generation.

---

## Target State

### Instance, SSH, auth, and cataloged WORKDIR

These items specialize the [base GPU node](../aws-deep-learning-base/base-gpu-node.profile.md) **Instance** and **SSH** Target State and [headless-auth](../headless-auth/headless-auth.profile.md) for OWW training. Default **slug** is **`sara`**: EC2 **Name** tag and `~/.ssh/config` **Host** are **`cloud-task-sara`** (pattern `cloud-task-<slug>` from the base profile). Use a different slug only when you intentionally isolate multiple nodes and SSH hosts.

- **A running OWW training instance is launched and tracked in `cloud-resources.md`.** The instance is named with **`cloud-task-<slug>`** (default **`cloud-task-sara`**), matching `--tag` to [`tools/launch-spot-instance.py`](../../tools/launch-spot-instance.py). The gitignored [**`cloud-resources.md`**](../../cloud-resources.md) **Nodes** row for this instance records **Name**, **SSH Host**, **Instance ID**, **Public IP**, **Region**, **Type**, **Status**, **Notes**, and is kept current per root [AGENTS.md](../../AGENTS.md). Launch alignment (stop on guest shutdown, root volume delete on terminate, volume size, market type) is spelled out in Apply §1.

- **SSH is profiled for this instance on the controlling machine.** A per-instance **`Host`** entry exists in `~/.ssh/config` (default **`cloud-task-sara`**), with **HostName** set to the instance public IP. **User**, **IdentityFile**, and `cloud-task-*` wildcard behavior follow the [local dev workstation profile](../local-dev-env/dev-workstation.profile.md). The **SSH (current)** section in **`cloud-resources.md`** lists usable commands for this host while it is **running** and the config entry matches.

- **Agent CLI and GitHub CLI are authenticated on the node** per [headless-auth](../headless-auth/headless-auth.profile.md): a trivial agent prompt completes without a login stall; **`gh --version`** succeeds; **`gh auth status`** exits 0; **`gh auth setup-git`** has been run so global git credential helper uses **`gh`** for HTTPS.

- **WORKDIR is named, recorded in `cloud-resources.md`, created on the instance, and uses durable storage by default.** The **Nodes** table **WORKDIR** column for this node's **SSH Host** contains the **absolute path** to the OWW training root (the same directory Apply uses for `mkdir` / `cd`). **Primary spec:** that path lives on **root EBS** (e.g. `/home/ubuntu/oww-work`) so mutable state survives **stop → start** of the same instance; it is still subject to **terminate** and teardown policy. **Additionally, when instance-store NVMe is available** (e.g. DL AMI mount at `/opt/dlami/nvme`), WORKDIR may be placed under that mount for sequential I/O; record the **actual** absolute path in **`cloud-resources.md`** and treat the mount as **ephemeral** per AWS instance-store semantics—**rsync** irreplaceable artifacts to durable storage or off-node before terminate, and do not keep sole copies only on instance store.

### Working directory

- **WORKDIR is a flat directory on the instance with the core sibling paths, and is not inside the project repo clone.** At minimum, `hey_sara_model.yml`, `openwakeword/`, `venv/`, and **`oww_train_shim/`** (import shim for upstream `train.py`; see `hey_sara_model.yml` `piper_sample_generator_path`) are direct children of `WORKDIR`. Downloaded `.npy` files and the `hey_sara_output/` tree (including pre-synced WAV subdirs) appear as training proceeds. Copy `hey_sara_model.yml` and the shim tree from the repo; read this profile from the repo clone. Mutable state lives only in `WORKDIR`. The cataloged path and storage class are defined in **Instance, SSH, auth, and cataloged WORKDIR** above.

### Synthetic clips (Cartesia happy path)

- **Positive and adversarial-negative training WAVs are pre-placed** under `hey_sara_output/<model_name>/` in **`positive_train/`**, **`positive_test/`**, **`negative_train/`**, and **`negative_test/`** (defaults: `model_name` **`hey_sara`**, `output_dir` **`./hey_sara_output`** in `hey_sara_model.yml`). Each directory holds enough **`*.wav`** files for **`openwakeword.train`** to run **without** `--generate_clips` (upstream still imports `generate_samples` from `piper_sample_generator_path`; the shim **`./oww_train_shim`** satisfies that import and **must not** be invoked). **Preferred generator:** **Cartesia** — [`generate_samples.py`](generate_samples.py) with **`--backend cartesia`** (default). **One cloud provider** on the happy path; keep ElevenLabs/Deepgram as optional swaps in that script, not mixed targets in the same profile run.

- **Positive clip counts are ≥ 10,000 train / ≥ 2,000 test.** Phrase: **`hey Sara`** (see YAML `target_phrase`). Counts must meet or exceed **`n_samples: 10000`** / **`n_samples_val: 2000`** in `hey_sara_model.yml`. Pre-placing clips should match those totals so augmentation and training see a full set.

- **Positive clips are generated across ≥ 5 distinct Cartesia voices with varied prosody.** The generation set uses at least five different Cartesia voice IDs (not only "Allie") to ensure speaker diversity. Across the full clip set, generation varies speed (± 20%), pitch (± 10–20%), emphasis, and leading/trailing silence so the model generalises across speakers and speaking styles. The voice roster and variation parameters are documented in `generate_samples.py` or its invocation.

- **Adversarial-negative clips use an expanded phonetically-curated phrase set.** The adversarial phrase list in [`adversarial_phrases.example.txt`](adversarial_phrases.example.txt) and the `custom_negative_phrases` field in `hey_sara_model.yml` contain **≈ 20 phonetically confusable phrases** — names that rhyme with or share consonant/vowel structure with "sara" (e.g. "hey sarah", "hey tara", "hey Clara", "hey Kara", "hey Lara"), consonant and vowel shifts (e.g. "hey serra", "hey sora", "say sara"), and common mis-hearings (e.g. "hey sorry", "hey siri", "hey there", "say ra"). Phrases that **contain** the wake phrase in a longer utterance (e.g. "hey sara please", "sara come here") are **excluded** — in the deployment environment no one named Sara is present, so any utterance containing "hey sara" is a genuine activation.

- **Adversarial-negative clip counts match positive counts: ≥ 10,000 train / ≥ 2,000 test.** Generated with the same Cartesia multi-voice, varied-prosody approach as positives, driven by **`--phrases-file`**.

### Python environment

- **A Python venv exists** (created from the Python 3.10 or 3.11 identified by the base profile).
- **`openwakeword` is installed** in editable mode with the `[full]` extra, and **`import openwakeword.train`** (or another submodule) resolves to the real package — not only an empty top-level namespace. The working directory usually contains a git clone at `./openwakeword/`; on `sys.path`, a bare `import openwakeword` from the parent directory can bind to a namespace over that tree and omit `FEATURE_MODELS`, breaking `download_models()`. Use **`python -m openwakeword.train` from `WORKDIR`**, or `import openwakeword.train`, or **`cd openwakeword`** before ad-hoc scripts. Audits use submodule imports for this reason.
- **OpenWakeWord feature models are present** under `openwakeword/openwakeword/resources/models/` — at minimum `melspectrogram.onnx` and `embedding_model.onnx`. These are not in the git clone; fetch them with `openwakeword.utils.download_models()` (GitHub release assets). Training fails at “Computing openwakeword features” if they are missing.
- **NumPy is version 1.x** (`numpy<2`). PyTorch 1.13.1 and torchmetrics crash under NumPy 2.x. After **`pip install -e ".[full]"`**, keep **`pip install "numpy<2"`**; re-apply if any later `pip install` upgrades NumPy.
- **`huggingface_hub` is installed** (used for data downloads).

### Repositories

- **The `openwakeword` repository is cloned** from `https://github.com/dscripka/openWakeWord.git`. (The **`piper-sample-generator`** repo is **not** part of the happy path; see Appendix A if needed.)

### Training data

- **Training data files are present:**
  - `validation_set_features.npy` — from HuggingFace (`davidscripka/openwakeword_features`, filename `validation_set_features.npy`). Not `openwakeword_features.npy` (renamed upstream; 404).
  - `openwakeword_features_ACAV100M_2000_hrs_16bit.npy` — negative feature data from the same HF dataset. This is the dominant negative-class training signal (2,000 hours, ~5.6 M feature vectors), consumed directly during DNN training via `batch_n_per_class`.
  - `background_clips/` contains audio files used for **noise overlay during the augmentation step** (before feature extraction — distinct from the ACAV100M features used during DNN training). Representative ambient audio from the deployment environment (e.g. kitchen ambience, TV, household noise) is recommended over the minimal silence placeholder accepted in earlier iterations. Even a few minutes of real background audio materially improves the realism of augmented clips. A silence-only placeholder still permits training but skips effective noise augmentation.
  - `mit_rirs/` — MIT Room Impulse Responses (WAV files), sourced from the HuggingFace dataset `davidscripka/MIT_environmental_impulse_responses` (271 × 16 kHz WAVs). **RIRs are mandatory** — reverb augmentation is a standard part of the pipeline for producing far-field-realistic training features. Training proceeds without them but produces a weaker model; do not skip.

Optional: set `HF_TOKEN` when downloading from HuggingFace to improve rate limits (unauthenticated requests work but may be throttled).

### Training config

- **`hey_sara_model.yml` is present** in the working directory. All relative paths in the YAML (`./oww_train_shim`, `./validation_set_features.npy`, `./hey_sara_output`, etc.) resolve from the working directory.

- **Training parameters are calibrated for the 10k-sample data volume.** The YAML reflects:

  | Parameter | Value | Rationale |
  |-----------|-------|-----------|
  | `n_samples` | 10,000 | Scaled from 3,000; aligns with OWW community practice for service-ready models |
  | `n_samples_val` | 2,000 | Scaled from 500; matching |
  | `steps` | 50,000 | Scaled roughly linearly with data volume (was 25,000 at 3k samples) |
  | `augmentation_rounds` | 2 | Two rounds of noise/reverb/gain augmentation for richer feature diversity |
  | `batch_n_per_class` | ACAV=1024, adversarial=70, positive=70 | Adversarial/positive raised from 50 to prevent under-sampling the expanded dataset |
  | `model_type` | `dnn` | Unchanged — small footprint for edge deployment |
  | `layer_size` | 32 | Unchanged — 2 layers × 32 units |
  | `max_negative_weight` | 1,500 | Unchanged — class weighting, not data-volume dependent |
  | `target_false_positives_per_hour` | 0.5 | Unchanged — appropriate for single-user home/kitchen deployment (OWW community range: 0.2–0.5) |

### Post-training output

- **`hey_sara_output/hey_sara.onnx` exists** and is a valid ONNX model loadable by `openwakeword.model.Model`.

- **A custom verifier model is trained and co-located with the base ONNX model.** The verifier is a lightweight logistic regression (on the same Google speech embeddings) that fires only when the base model score exceeds its threshold. It requires minimal real-speaker data: **≥ 3 WAV clips** of the deployment user (Tim) saying "hey Sara" in deployment-like conditions, plus **~10 seconds** of the user's non-wakeword speech. The verifier is trained via `openwakeword.train_custom_verifier()` and produces a `.pkl` file (e.g. `hey_sara_verifier.pkl`). At inference, it is loaded alongside the base model via the `custom_verifier_models` parameter on `openwakeword.model.Model`. This dramatically reduces false positives for single-user home deployment at near-zero cost.

### Validation protocol

- **A threshold-determination protocol runs on the deployment target after training.** The base model and verifier are loaded on the Pi (or equivalent deployment hardware). A standardised test session of **15–30 minutes** records continuous ambient audio from the deployment environment while the operator delivers **controlled "hey Sara" utterances** at varied distances and volumes. The protocol produces a **FAR (false accept rate) vs. threshold curve** from which the deployment threshold is selected, targeting ≤ 0.5 false positives per hour with false rejection rate < 5%. The chosen threshold is recorded as **deployment metadata** (e.g. environment variable or config file in the consuming application) — it is a deployment parameter, not a training parameter, and does not belong in `hey_sara_model.yml`.

- **Smoke test passes on the deployment target.** [`smoke_test_model.py`](smoke_test_model.py) loads the ONNX model, feeds silent frames confirming zero scores, and optionally runs a live mic test. This is a necessary-but-not-sufficient gate; the threshold protocol above determines the production threshold.

### Iteration methodology

- **The training methodology supports up to two iterations, not open-ended refinement.** The first iteration uses the full synthetic pipeline (Cartesia multi-voice positives, expanded adversarial negatives, RIR-augmented features, ACAV100M background negatives). After deployment and the threshold-determination protocol, if the false-positive rate exceeds the target or false-rejection rate is unacceptable, a second iteration incorporates false-positive audio collected from the deployment environment as additional adversarial training data. The second iteration re-runs the training pipeline with the augmented dataset. If two iterations do not converge to acceptable performance, the methodology should be re-evaluated rather than continuing to iterate — likely causes would be insufficient voice diversity, an inadequate adversarial phrase set, or a fundamental deployment-environment mismatch.

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
    --volume-gb 128 \
    --tag cloud-task-sara \
    --instance-initiated-shutdown-behavior stop
```

Align with Target State: **stop** (not terminate) on guest OS shutdown (`--instance-initiated-shutdown-behavior stop`, tool default); **do not** pass **`--persist-root-volume`** (unless you document an exception in **`cloud-resources.md`**) so the root volume **deletes on instance termination**. **Disk headroom is fixed at launch:** choose **`--volume-gb`** at least **the AMI root snapshot size** (AWS rejects smaller values with `InvalidBlockDeviceMapping`; e.g. the current **`baked-core-gpu`** row in **`cloud-resources.md`** required **≥125** GiB in one bake). Then size up further so the root filesystem still has enough *free* space after the DL AMI baseline (see [base-gpu-node](../aws-deep-learning-base/base-gpu-node.profile.md) storage notes) for the large ACAV negative-features `.npy` (~17 GB), the venv, and training artifacts — **`80`** is a reasonable target only when the snapshot minimum allows it. Use **`--market-type on-demand`** to avoid spot reclaim mid-run, or **`--market-type spot`** for cost with appropriate **`--spot-interruption-behavior`**.

See **`python tools/launch-spot-instance.py --help`** for all flags (`--spot-interruption-behavior`,
`--ssh-host-alias`, `--no-ssh-config`, etc.).

Update **`cloud-resources.md`** in the same session (per root [AGENTS.md](../../AGENTS.md)):
add or refresh the **Nodes** row (**Name**, **SSH Host**, **Instance ID**, **Public IP**,
**Region**, **Type**, **Status**, **Notes**). Leave **WORKDIR** empty or placeholder until
Apply §2 sets the path; update **SSH (current)** with usable commands for the **Host**
that matches **`cloud-task-<slug>`** (default **`cloud-task-sara`**).

SSH to the node and converge **[aws-deep-learning-base](../aws-deep-learning-base/base-gpu-node.profile.md)**
if needed. When the workflow needs **Cursor agent CLI** or **`gh`** on the instance,
run **[headless-auth](../headless-auth/headless-auth.profile.md)** Apply / Audit
there.

---

Assumes the base GPU node profile already holds (apt fixed, system packages
installed, Python identified). Run the remaining commands **on the instance** from
the chosen **working directory** (`WORKDIR` below).

### 2. Choose `WORKDIR` and create venv

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
cp -r "$REPOROOT/profiling/sara-wakeword/oww_train_shim" .
PYTHON=${PYTHON:-$(command -v python3.11 || command -v python3.10)}
$PYTHON -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

On the **workstation**, update **`cloud-resources.md`**: set the **WORKDIR** column
for this instance's **SSH Host** row to the absolute path (`pwd -P` on the node
from this directory). If **`WORKDIR`** is under **`/opt/dlami/nvme`**, add a
**Notes** flag that training state is on **instance store** (ephemeral).

### 3. Clone `openwakeword`

```bash
[ -d openwakeword ] || git clone https://github.com/dscripka/openWakeWord.git openwakeword
```

### 4. Install OpenWakeWord and pin NumPy

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

### 6. Download training data from HuggingFace

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

### 7. Prepare background audio and RIRs

**RIRs (mandatory):** Download the MIT Room Impulse Responses from HuggingFace.
The dataset `davidscripka/MIT_environmental_impulse_responses` contains 271
WAV files at 16 kHz (~8 MB total).

```bash
mkdir -p mit_rirs
python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='davidscripka/MIT_environmental_impulse_responses',
    repo_type='dataset',
    local_dir='mit_rirs',
)
"
```

**Background clips (recommended upgrade):** Replace the silence placeholder
with representative ambient audio from the deployment environment. Even a
few minutes of kitchen ambience, TV audio, or household noise materially
improves augmentation realism. If real ambient audio is not available, a
silence placeholder still permits training but noise augmentation is
effectively a no-op.

```bash
mkdir -p background_clips
# Preferred: rsync real ambient recordings into background_clips/
# Fallback: generate a silence placeholder (noise augmentation will be ineffective)
[ "$(find background_clips -maxdepth 1 -type f 2>/dev/null | wc -l)" -ge 1 ] || \
    ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 60 -c:a pcm_s16le background_clips/silence.wav -y 2>/dev/null
```

### 8. Generate WAVs with Cartesia (workstation) and rsync to the instance

On a machine with **Cartesia** credentials (see `generate_samples.py` / forked_assistant
`tts` module and `.env`), from a checkout that includes **`profiling/sara-wakeword/`**:

Generation must use **≥ 5 distinct Cartesia voices** with varied prosody
(speed ± 20%, pitch ± 10–20%, emphasis, leading/trailing silence). See
Target State **Synthetic clips** for the full diversity requirement.

```bash
# Positives — counts must meet hey_sara_model.yml: n_samples=10000, n_samples_val=2000
python profiling/sara-wakeword/generate_samples.py --backend cartesia --count 10000 \
  -o /tmp/oww_pos_train
python profiling/sara-wakeword/generate_samples.py --backend cartesia --count 2000 \
  -o /tmp/oww_pos_test

# Adversarial negatives — expanded phrase list (~20 phrases)
python profiling/sara-wakeword/generate_samples.py --backend cartesia \
  --phrases-file profiling/sara-wakeword/adversarial_phrases.example.txt --count 500 \
  -o /tmp/oww_neg_train
python profiling/sara-wakeword/generate_samples.py --backend cartesia \
  --phrases-file profiling/sara-wakeword/adversarial_phrases.example.txt --count 100 \
  -o /tmp/oww_neg_test
```

Adjust **`--count`** so that after **`--phrases-file`** multiplication (samples **per phrase** × number of lines) you reach at least **`n_samples`** for train dirs and **`n_samples_val`** for test dirs (see Target State). The examples above are **illustrative** — scale **per phrase** until each of **`positive_train`**, **`negative_train`** has ≥ **`n_samples`** (10,000) WAVs and each of **`positive_test`**, **`negative_test`** has ≥ **`n_samples_val`** (2,000).

On the **instance**, create OWW’s expected layout and sync:

```bash
cd "$WORKDIR"
mkdir -p hey_sara_output/hey_sara/positive_train hey_sara_output/hey_sara/positive_test \
         hey_sara_output/hey_sara/negative_train hey_sara_output/hey_sara/negative_test
```

From the **workstation** (replace host and paths):

```bash
rsync -e ssh -av /tmp/oww_pos_train/ cloud-task-sara:$WORKDIR/hey_sara_output/hey_sara/positive_train/
rsync -e ssh -av /tmp/oww_pos_test/ cloud-task-sara:$WORKDIR/hey_sara_output/hey_sara/positive_test/
rsync -e ssh -av /tmp/oww_neg_train/ cloud-task-sara:$WORKDIR/hey_sara_output/hey_sara/negative_train/
rsync -e ssh -av /tmp/oww_neg_test/ cloud-task-sara:$WORKDIR/hey_sara_output/hey_sara/negative_test/
```

### 9. Training config

`hey_sara_model.yml` and **`oww_train_shim/`** should already be in **`WORKDIR`** from §2.

### 10. Run training (no `--generate_clips`)

**Critical: run from the working directory** (where `hey_sara_model.yml`
and all relative paths resolve), not from `openwakeword/`.

```bash
cd "$WORKDIR"
source venv/bin/activate
python -m openwakeword.train \
    --training_config hey_sara_model.yml \
    --augment_clips \
    --train_model
```

Do **not** pass **`--generate_clips`** on the happy path — that would invoke Piper’s
generator unless you switched YAML to **`piper_sample_generator_path: "./piper-sample-generator"`**
(Appendix A).

The correct CLI flag is `--training_config` (not `--config`).

**Re-runs:** To force re-augmentation, remove feature `*.npy` under **`hey_sara_output/hey_sara/`**
or pass upstream **`--overwrite`** with **`--augment_clips`** per OpenWakeWord docs.

Expected wall time: depends on clip counts and instance type.

### 11. Collect output

```bash
ls -la hey_sara_output/hey_sara.onnx
cp hey_sara_output/hey_sara.onnx .
```

Transfer the ONNX file back to the controlling machine via rsync/SFTP.

### 12. Train custom verifier (deployment target)

**Runs on the deployment target** (Pi or equivalent), not the training
instance. Requires the base ONNX model from §11 and a small number of
real recordings from the deployment user.

Record **≥ 3 WAV clips** of Tim saying "hey Sara" in deployment-like
conditions, plus **~10 seconds** of Tim's non-wakeword speech. Then:

```python
import openwakeword

openwakeword.train_custom_verifier(
    positive_reference_clips=["tim_hey_sara_1.wav", "tim_hey_sara_2.wav", "tim_hey_sara_3.wav"],
    negative_reference_clips=["tim_speech_1.wav", "tim_speech_2.wav"],
    output_path="./hey_sara_verifier.pkl",
    model_name="hey_sara.onnx",
)
```

The exact API may differ across OWW versions — verify against the installed
version's `docs/custom_verifier_models.md` or source. The executing agent
should confirm the function signature before running.

### 13. Validation protocol (deployment target)

**Runs on the deployment target** after the base model and verifier are
deployed. This step determines the production threshold.

1. Load the model with verifier:
   ```python
   oww = openwakeword.Model(
       wakeword_model_paths=["hey_sara.onnx"],
       custom_verifier_models={"hey_sara": "hey_sara_verifier.pkl"},
       custom_verifier_threshold=0.3,
   )
   ```
2. Run a **15–30 minute** ambient session with controlled "hey Sara"
   utterances at varied distances and volumes.
3. Log all scores; produce a FAR vs. threshold curve.
4. Select threshold targeting ≤ 0.5 FP/hour with FRR < 5%.
5. Record chosen threshold as deployment metadata (env var or config).

The smoke test ([`smoke_test_model.py`](smoke_test_model.py)) is a
necessary-but-not-sufficient pre-check; this protocol supersedes it for
threshold selection.

### Known non-blocking noise

- ONNX Runtime DRM vendor library warning — harmless.
- If `onnxruntime` is CPU-only, you may see that **`CUDAExecutionProvider` is not
  available** and a warning about GPU device discovery; feature extraction falls
  back to **CPU** unless you install **`onnxruntime-gpu`** matching your CUDA
  stack (optional; slower but valid).
- `torchvision` missing — only needed for figure generation, not training.
- `torchmetrics` may warn about `pkg_resources` / setuptools deprecation —
  harmless unless setuptools removal breaks a dependency; pin `setuptools<81`
  only if you need quiet logs.
- **`torch_audiomentations`** may emit `FutureWarning` about an `output_type`
  argument — upstream library noise, not a training failure.
- **`audiomentations`** may warn about `float64` samples being converted to
  `float32` — benign.

---

## Appendix A — Deprecated Piper fallback (not tracked in Target State)

**Status:** **Deprecated.** Lower-quality than the Cartesia happy path. No Target
State items and no Audits apply to this path — an agent must **re-derive** steps
from this appendix (and upstream `openwakeword` / `piper-sample-generator`) if
Piper is revived.

**When:** You want **`--generate_clips`** on the GPU node and accept Piper TTS
instead of pre-placed cloud WAVs.

**YAML:** In **`hey_sara_model.yml`**, set **`piper_sample_generator_path`** to
**`"./piper-sample-generator"`** (not **`./oww_train_shim`**). Remove or do not
copy **`oww_train_shim/`** into **WORKDIR**, or leave it unused.

**On the instance (sketch):**

```bash
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y libespeak-ng1
[ -d piper-sample-generator ] || git clone https://github.com/dscripka/piper-sample-generator.git piper-sample-generator
pip install -r piper-sample-generator/requirements.txt
pip install "numpy<2"
mkdir -p piper-sample-generator/models
wget -O piper-sample-generator/models/en-us-libritts-high.pt \
  'https://github.com/rhasspy/piper-sample-generator/releases/download/v1.0.0/en-us-libritts-high.pt'
```

Then run **`python -m openwakeword.train --training_config hey_sara_model.yml --generate_clips --augment_clips --train_model`**.

**Note:** `piper-sample-generator/requirements.txt` unpinned **`numpy`** may pull
NumPy 2.x — always re-pin **`numpy<2`**. **`webrtcvad`** / **`espeak_phonemizer`**
come from that requirements file.

---

## Audit

**Where to run:** Checks **1** (tool + **`cloud-resources.md`** row) and **2**
(**`ssh -G`**) use the **workstation**. Check **3** runs **on the instance**.
Check **4** uses the **catalog** on the workstation and a path test **on the
instance** (SSH session). Checks **5–15** assume a shell **cd**’d to **WORKDIR** on
the instance, using **`venv/bin/python`** where noted (or activate **`venv/`**
first). Checks **16–18** run on the **deployment target** (Pi or equivalent).

Do **not** rely on a bare `import openwakeword` as the only check — with a
sibling `./openwakeword` repo directory, it can resolve to a **namespace** that
does not expose the real package API. Prefer **`import openwakeword.train`** or
imports from **`openwakeword.model`** (see Target State, Python environment).

There is **one check per Target State item**, in the same order as the bold
items under Target State (from **Instance, SSH, auth, and cataloged WORKDIR**
through **Iteration methodology**). Each heading below names the item it
verifies. If you use a slug other than **`sara`**, substitute
**`cloud-task-<slug>`** in workstation commands.

**Optional sanity (not a Target State item):** before huge HuggingFace downloads,
run **`df -h .`** from **WORKDIR**. Low free space is usually a **launch-time**
mistake (**`--volume-gb`** too small for this workload); fix with a larger volume
on a new instance or EBS resize — do not treat a fixed gigabyte threshold as a
profile convergence item.

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
the operator uses on the instance (set in Apply §2).

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
  && test -d oww_train_shim \
  && test -f oww_train_shim/generate_samples.py \
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

### 6. Positive and adversarial-negative WAVs are pre-placed (Cartesia happy path)

**On the instance** from **WORKDIR**. Minimum WAV counts follow **`hey_sara_model.yml`**
(`n_samples` = 10000 train, `n_samples_val` = 2000 test per polarity); adjust the
thresholds below if you change the YAML.

```bash
BASE=hey_sara_output/hey_sara
MIN_TR=10000
MIN_TE=2000
n_pt=$(find "$BASE/positive_train" -maxdepth 1 -name '*.wav' 2>/dev/null | wc -l)
n_nt=$(find "$BASE/negative_train" -maxdepth 1 -name '*.wav' 2>/dev/null | wc -l)
n_pe=$(find "$BASE/positive_test" -maxdepth 1 -name '*.wav' 2>/dev/null | wc -l)
n_ne=$(find "$BASE/negative_test" -maxdepth 1 -name '*.wav' 2>/dev/null | wc -l)
if [ "$n_pt" -ge "$MIN_TR" ] && [ "$n_nt" -ge "$MIN_TR" ] \
   && [ "$n_pe" -ge "$MIN_TE" ] && [ "$n_ne" -ge "$MIN_TE" ]; then
  echo "PASS: clip dirs populated (pt=$n_pt nt=$n_nt pe=$n_pe ne=$n_ne)"
else
  echo "FAIL: need >=$MIN_TR train and >=$MIN_TE test WAVs per polarity (pt=$n_pt nt=$n_nt pe=$n_pe ne=$n_ne)"
fi
```
Expected: `PASS: clip dirs populated (...)`

### 7. A Python venv exists

```bash
[ -d venv ] && venv/bin/python --version 2>/dev/null \
    && echo "PASS: venv exists and python works" \
    || echo "FAIL: venv missing or broken"
```
Expected: `Python 3.x.x` on the first line, then `PASS: venv exists and python works`

### 8. `openwakeword` is installed (editable package reachable)

```bash
venv/bin/python -c "import openwakeword.train; print('PASS: openwakeword.train importable')"
```
Expected: `PASS: openwakeword.train importable`

### 9. OpenWakeWord feature models are present under `resources/models`

```bash
test -f openwakeword/openwakeword/resources/models/melspectrogram.onnx \
    && test -f openwakeword/openwakeword/resources/models/embedding_model.onnx \
    && echo "PASS: OWW feature ONNX models present" \
    || echo "FAIL: run download_models() from openwakeword/ repo dir (see Apply §5)"
```
Expected: `PASS: OWW feature ONNX models present`

### 10. NumPy is version 1.x

```bash
venv/bin/python -c "import numpy; v=int(numpy.__version__.split('.')[0]); print(f'numpy {numpy.__version__}'); assert v < 2, 'FAIL: numpy 2.x'"
```
Expected: `numpy 1.x.x`

### 11. `huggingface_hub` is installed

```bash
venv/bin/python -c "import huggingface_hub; print('PASS: huggingface_hub importable')"
```
Expected: `PASS: huggingface_hub importable`

### 12. The `openwakeword` repository is cloned

```bash
[ -d openwakeword ] \
    && echo "PASS: openwakeword repo present" \
    || echo "FAIL: openwakeword missing"
```
Expected: `PASS: openwakeword repo present`

### 13. Training data files are present

```bash
n_rirs=$(find mit_rirs -maxdepth 2 -name '*.wav' 2>/dev/null | wc -l)
[ -f validation_set_features.npy ] \
    && [ -f openwakeword_features_ACAV100M_2000_hrs_16bit.npy ] \
    && [ -d background_clips ] \
    && [ "$(find background_clips -maxdepth 1 -type f 2>/dev/null | wc -l)" -ge 1 ] \
    && [ "$n_rirs" -ge 1 ] \
    && echo "PASS: training data present (rirs=$n_rirs)" \
    || echo "FAIL: training data missing (npys, background_clips/, or mit_rirs/ empty)"
```
Expected: `PASS: training data present (rirs=271)` (or similar count).
RIRs are mandatory — see Target State **Training data**.

### 14. `hey_sara_model.yml` is present in the working directory

```bash
[ -f hey_sara_model.yml ] \
    && echo "PASS: training config present" \
    || echo "FAIL: training config missing"
```
Expected: `PASS: training config present`

### 15. `hey_sara_output/hey_sara.onnx` exists and loads as a valid model

```bash
venv/bin/python -c "
from openwakeword.model import Model
m = Model(wakeword_model_paths=['hey_sara_output/hey_sara.onnx'])
print(f'PASS: model loaded, keys={list(m.models.keys())}')
"
```
Expected: `PASS: model loaded, keys=['hey_sara']`

### 16. Custom verifier model exists

**Deployment target** (Pi or equivalent). Verifier `.pkl` file is co-located
with the base ONNX model and loadable by OWW.

```bash
python -c "
import openwakeword
m = openwakeword.Model(
    wakeword_model_paths=['hey_sara.onnx'],
    custom_verifier_models={'hey_sara': 'hey_sara_verifier.pkl'},
    custom_verifier_threshold=0.3,
)
print(f'PASS: model + verifier loaded, keys={list(m.models.keys())}')
"
```
Expected: `PASS: model + verifier loaded, keys=['hey_sara']`

The exact `Model()` parameters may differ across OWW versions. The
executing agent should verify the API against the installed version if
this check fails on a signature mismatch rather than a missing file.

### 17. Smoke test passes on the deployment target

**Deployment target:**

```bash
python smoke_test_model.py hey_sara.onnx
```
Expected: `Smoke test passed.`

### 18. Threshold-determination protocol and iteration methodology

**Stub — human-verified.** The operator confirms:

1. A threshold-determination session (15–30 min ambient + controlled
   utterances) has been run on the deployment target.
2. The chosen threshold is recorded as deployment metadata.
3. If this is iteration 2, false-positive audio from iteration 1 was
   incorporated as additional adversarial training data before retraining.
