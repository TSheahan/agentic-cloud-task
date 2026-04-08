# Updated Target State — Draft

Replacement for the `## Target State` section of
`profiling/sara-wakeword/oww-training-env.profile.md`.

Incorporates all accepted methodology mutations from the review cycle.
Sections marked **(unchanged)** are carried forward verbatim from the
current profile. Sections marked **(revised)** contain mutations.
New sections are marked **(new)**.

When this draft is accepted, Apply and Audit sections must be re-derived
to match.

---

## Target State

### Instance, SSH, auth, and cataloged WORKDIR

**(unchanged)**

These items specialize the [base GPU node](../aws-deep-learning-base/base-gpu-node.profile.md) **Instance** and **SSH** Target State and [headless-auth](../headless-auth/headless-auth.profile.md) for OWW training. Default **slug** is **`sara`**: EC2 **Name** tag and `~/.ssh/config` **Host** are **`cloud-task-sara`** (pattern `cloud-task-<slug>` from the base profile). Use a different slug only when you intentionally isolate multiple nodes and SSH hosts.

- **A running OWW training instance is launched and tracked in `cloud-resources.md`.** The instance is named with **`cloud-task-<slug>`** (default **`cloud-task-sara`**), matching `--tag` to [`tools/launch-spot-instance.py`](../../tools/launch-spot-instance.py). The gitignored [**`cloud-resources.md`**](../../cloud-resources.md) **Nodes** row for this instance records **Name**, **SSH Host**, **Instance ID**, **Public IP**, **Region**, **Type**, **Status**, **Notes**, and is kept current per root [AGENTS.md](../../AGENTS.md). Launch alignment (stop on guest shutdown, root volume delete on terminate, volume size, market type) is spelled out in Apply §1.

- **SSH is profiled for this instance on the controlling machine.** A per-instance **`Host`** entry exists in `~/.ssh/config` (default **`cloud-task-sara`**), with **HostName** set to the instance public IP. **User**, **IdentityFile**, and `cloud-task-*` wildcard behavior follow the [local dev workstation profile](../local-dev-env/dev-workstation.profile.md). The **SSH (current)** section in **`cloud-resources.md`** lists usable commands for this host while it is **running** and the config entry matches.

- **Agent CLI and GitHub CLI are authenticated on the node** per [headless-auth](../headless-auth/headless-auth.profile.md): a trivial agent prompt completes without a login stall; **`gh --version`** succeeds; **`gh auth status`** exits 0; **`gh auth setup-git`** has been run so global git credential helper uses **`gh`** for HTTPS.

- **WORKDIR is named, recorded in `cloud-resources.md`, created on the instance, and uses durable storage by default.** The **Nodes** table **WORKDIR** column for this node's **SSH Host** contains the **absolute path** to the OWW training root (the same directory Apply uses for `mkdir` / `cd`). **Primary spec:** that path lives on **root EBS** (e.g. `/home/ubuntu/oww-work`) so mutable state survives **stop → start** of the same instance; it is still subject to **terminate** and teardown policy. **Additionally, when instance-store NVMe is available** (e.g. DL AMI mount at `/opt/dlami/nvme`), WORKDIR may be placed under that mount for sequential I/O; record the **actual** absolute path in **`cloud-resources.md`** and treat the mount as **ephemeral** per AWS instance-store semantics—**rsync** irreplaceable artifacts to durable storage or off-node before terminate, and do not keep sole copies only on instance store.

### Working directory

**(unchanged)**

- **WORKDIR is a flat directory on the instance with the core sibling paths, and is not inside the project repo clone.** At minimum, `hey_sara_model.yml`, `openwakeword/`, `venv/`, and **`oww_train_shim/`** (import shim for upstream `train.py`; see `hey_sara_model.yml` `piper_sample_generator_path`) are direct children of `WORKDIR`. Downloaded `.npy` files and the `hey_sara_output/` tree (including pre-synced WAV subdirs) appear as training proceeds. Copy `hey_sara_model.yml` and the shim tree from the repo; read this profile from the repo clone. Mutable state lives only in `WORKDIR`. The cataloged path and storage class are defined in **Instance, SSH, auth, and cataloged WORKDIR** above.

### Synthetic clips (Cartesia happy path)

**(revised — sample counts, voice diversity, adversarial phrase set)**

- **Positive and adversarial-negative training WAVs are pre-placed** under `hey_sara_output/<model_name>/` in **`positive_train/`**, **`positive_test/`**, **`negative_train/`**, and **`negative_test/`** (defaults: `model_name` **`hey_sara`**, `output_dir` **`./hey_sara_output`** in `hey_sara_model.yml`). Each directory holds enough **`*.wav`** files for **`openwakeword.train`** to run **without** `--generate_clips` (upstream still imports `generate_samples` from `piper_sample_generator_path`; the shim **`./oww_train_shim`** satisfies that import and **must not** be invoked). **Preferred generator:** **Cartesia** — [`generate_samples.py`](generate_samples.py) with **`--backend cartesia`** (default). **One cloud provider** on the happy path; keep ElevenLabs/Deepgram as optional swaps in that script, not mixed targets in the same profile run.

- **Positive clip counts are ≥ 10,000 train / ≥ 2,000 test.** Phrase: **`hey Sara`** (see YAML `target_phrase`). Counts must meet or exceed **`n_samples: 10000`** / **`n_samples_val: 2000`** in `hey_sara_model.yml`. Pre-placing clips should match those totals so augmentation and training see a full set.

- **Positive clips are generated across ≥ 5 distinct Cartesia voices with varied prosody.** The generation set uses at least five different Cartesia voice IDs (not only "Allie") to ensure speaker diversity. Across the full clip set, generation varies speed (± 20%), pitch (± 10–20%), emphasis, and leading/trailing silence so the model generalises across speakers and speaking styles. The voice roster and variation parameters are documented in `generate_samples.py` or its invocation.

- **Adversarial-negative clips use an expanded phonetically-curated phrase set.** The adversarial phrase list in [`adversarial_phrases.example.txt`](adversarial_phrases.example.txt) and the `custom_negative_phrases` field in `hey_sara_model.yml` contain **≈ 20 phonetically confusable phrases** — names that rhyme with or share consonant/vowel structure with "sara" (e.g. "hey sarah", "hey tara", "hey Clara", "hey Kara", "hey Lara"), consonant and vowel shifts (e.g. "hey serra", "hey sora", "say sara"), and common mis-hearings (e.g. "hey sorry", "hey siri", "hey there", "say ra"). Phrases that **contain** the wake phrase in a longer utterance (e.g. "hey sara please", "sara come here") are **excluded** — in the deployment environment no one named Sara is present, so any utterance containing "hey sara" is a genuine activation.

- **Adversarial-negative clip counts match positive counts: ≥ 10,000 train / ≥ 2,000 test.** Generated with the same Cartesia multi-voice, varied-prosody approach as positives, driven by **`--phrases-file`**.

### Python environment

**(unchanged)**

- **A Python venv exists** (created from the Python 3.10 or 3.11 identified by the base profile).
- **`openwakeword` is installed** in editable mode with the `[full]` extra, and **`import openwakeword.train`** (or another submodule) resolves to the real package — not only an empty top-level namespace. The working directory usually contains a git clone at `./openwakeword/`; on `sys.path`, a bare `import openwakeword` from the parent directory can bind to a namespace over that tree and omit `FEATURE_MODELS`, breaking `download_models()`. Use **`python -m openwakeword.train` from `WORKDIR`**, or `import openwakeword.train`, or **`cd openwakeword`** before ad-hoc scripts. Audits use submodule imports for this reason.
- **OpenWakeWord feature models are present** under `openwakeword/openwakeword/resources/models/` — at minimum `melspectrogram.onnx` and `embedding_model.onnx`. These are not in the git clone; fetch them with `openwakeword.utils.download_models()` (GitHub release assets). Training fails at "Computing openwakeword features" if they are missing.
- **NumPy is version 1.x** (`numpy<2`). PyTorch 1.13.1 and torchmetrics crash under NumPy 2.x. After **`pip install -e ".[full]"`**, keep **`pip install "numpy<2"`**; re-apply if any later `pip install` upgrades NumPy.
- **`huggingface_hub` is installed** (used for data downloads).

### Repositories

**(unchanged)**

- **The `openwakeword` repository is cloned** from `https://github.com/dscripka/openWakeWord.git`. (The **`piper-sample-generator`** repo is **not** part of the happy path; see Appendix A if needed.)

### Training data

**(revised — RIRs mandatory, background_clips upgraded)**

- **Training data files are present:**
  - `validation_set_features.npy` — from HuggingFace (`davidscripka/openwakeword_features`, filename `validation_set_features.npy`). Not `openwakeword_features.npy` (renamed upstream; 404).
  - `openwakeword_features_ACAV100M_2000_hrs_16bit.npy` — negative feature data from the same HF dataset. This is the dominant negative-class training signal (2,000 hours, ~5.6 M feature vectors), consumed directly during DNN training via `batch_n_per_class`.
  - `background_clips/` contains audio files used for **noise overlay during the augmentation step** (before feature extraction — distinct from the ACAV100M features used during DNN training). Representative ambient audio from the deployment environment (e.g. kitchen ambience, TV, household noise) is recommended over the minimal silence placeholder accepted in earlier iterations. Even a few minutes of real background audio materially improves the realism of augmented clips. A silence-only placeholder still permits training but skips effective noise augmentation.
  - `mit_rirs/` — MIT Room Impulse Responses (WAV files), sourced from the HuggingFace dataset `davidscripka/MIT_environmental_impulse_responses` (271 × 16 kHz WAVs). **RIRs are mandatory** — reverb augmentation is a standard part of the pipeline for producing far-field-realistic training features. Training proceeds without them but produces a weaker model; do not skip.

Optional: set `HF_TOKEN` when downloading from HuggingFace to improve rate limits (unauthenticated requests work but may be throttled).

### Training config

**(revised — steps, batch sizes, augmentation rounds)**

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

**(revised — adds verifier model)**

- **`hey_sara_output/hey_sara.onnx` exists** and is a valid ONNX model loadable by `openwakeword.model.Model`.

- **A custom verifier model is trained and co-located with the base ONNX model.** The verifier is a lightweight logistic regression (on the same Google speech embeddings) that fires only when the base model score exceeds its threshold. It requires minimal real-speaker data: **≥ 3 WAV clips** of the deployment user (Tim) saying "hey Sara" in deployment-like conditions, plus **~10 seconds** of the user's non-wakeword speech. The verifier is trained via `openwakeword.train_custom_verifier()` and produces a `.pkl` file (e.g. `hey_sara_verifier.pkl`). At inference, it is loaded alongside the base model via the `custom_verifier_models` parameter on `openwakeword.model.Model`. This dramatically reduces false positives for single-user home deployment at near-zero cost.

### Validation protocol

**(new)**

- **A threshold-determination protocol runs on the deployment target after training.** The base model and verifier are loaded on the Pi (or equivalent deployment hardware). A standardised test session of **15–30 minutes** records continuous ambient audio from the deployment environment while the operator delivers **controlled "hey Sara" utterances** at varied distances and volumes. The protocol produces a **FAR (false accept rate) vs. threshold curve** from which the deployment threshold is selected, targeting ≤ 0.5 false positives per hour with false rejection rate < 5%. The chosen threshold is recorded as **deployment metadata** (e.g. environment variable or config file in the consuming application) — it is a deployment parameter, not a training parameter, and does not belong in `hey_sara_model.yml`.

- **Smoke test passes on the deployment target.** [`smoke_test_model.py`](smoke_test_model.py) loads the ONNX model, feeds silent frames confirming zero scores, and optionally runs a live mic test. This is a necessary-but-not-sufficient gate; the threshold protocol above determines the production threshold.

### Iteration methodology

**(new)**

- **The training methodology supports up to two iterations, not open-ended refinement.** The first iteration uses the full synthetic pipeline (Cartesia multi-voice positives, expanded adversarial negatives, RIR-augmented features, ACAV100M background negatives). After deployment and the threshold-determination protocol, if the false-positive rate exceeds the target or false-rejection rate is unacceptable, a second iteration incorporates false-positive audio collected from the deployment environment as additional adversarial training data. The second iteration re-runs the training pipeline with the augmented dataset. If two iterations do not converge to acceptable performance, the methodology should be re-evaluated rather than continuing to iterate — likely causes would be insufficient voice diversity, an inadequate adversarial phrase set, or a fundamental deployment-environment mismatch.

---

## Change log (relative to previous Target State)

Summarises what changed and why. Remove this section when the draft is
applied to the profile.

| Area | Change | Source |
|------|--------|--------|
| Sample counts | 3k/500 → 10k/2k | OWW community practice; highest-leverage change for service-ready quality |
| Adversarial phrases | 6 → ~20 curated | Phonetic-similarity expansion; exclude wake-phrase-containing utterances (deployment context: no one named Sara present) |
| Voice diversity | "Allie" primary → ≥5 voices | Speaker diversity is the dominant generalisation factor in OWW's frozen-embedding pipeline |
| RIR sourcing | Optional → mandatory | HF dataset `davidscripka/MIT_environmental_impulse_responses` makes this zero-friction |
| background_clips | Silence accepted → ambient recommended | Silence = no effective noise augmentation; distinct from ACAV100M (feature-level, not augmentation-level) |
| augmentation_rounds | 1 → 2 | Standard for production-quality OWW training |
| steps | 25k → 50k | Linear scaling with data volume |
| batch_n_per_class adv/pos | 50 → 70 | Prevents under-sampling expanded dataset |
| Custom verifier | Not used → standard step | Lightweight logistic regression on ~3 real clips; near-zero cost, high FP reduction for single-user deployment |
| Validation protocol | New section | FAR/FRR curve on deployment hardware; threshold as deployment metadata |
| Iteration methodology | New section | 2-iteration cap; prevents open-ended refinement |
| target_FP/hr | 0.5 (confirmed) | Validated against OWW community norms (0.2–0.5); no change needed |

**Deferred to future work (not in this Target State):**
- Tier 2 real voice corpus (200–500 recorded clips for training mix) — separate work item
- Voice cloning via Cartesia — requires recorded material
- Supplemental background audio beyond minimal ambient — nice-to-have, not gating
