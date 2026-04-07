# profiling/sara-wakeword/ — Wake Word Training

One-shot training run for a custom OpenWakeWord model ("hey Sara").
Layers on [aws-deep-learning-base](../aws-deep-learning-base/AGENTS.md).

## Characteristics

- **Instance type**: g4dn.xlarge (or .2xlarge if needed)
- **Runtime**: ~2-4 hours on g4dn
- **Dependencies**: Python 3.10-3.11, PyTorch + CUDA, OpenWakeWord (training
  mode), **Cartesia** (or alternate) for pre-generated WAVs on the happy path;
  tflite/ONNX export
- **AMI lifecycle**: often one-shot; instances can be **stopped and restarted**
  (stop-on-shutdown, not terminate-on-shutdown) while root EBS still **deletes on
  terminate** — see [oww-training-env.profile.md](oww-training-env.profile.md) Target
  State (**Instance, SSH, auth, and cataloged WORKDIR** and Apply §1).
- **Transfer**: rsync trained model artifacts out on completion

## Contents

### Profiles

| File | Role |
|------|------|
| [oww-training-env.profile.md](oww-training-env.profile.md) | State convergence profile for the OWW training environment (Target State / Apply / Audit) |

### Reference

| File | Role |
|------|------|
| [domain-knowledge.md](domain-knowledge.md) | Durable domain knowledge: OWW architecture, sample strategy, dependency landscape, integration target |
| [hey_sara_model.yml](hey_sara_model.yml) | OWW training config (model name, phrases, sample counts, training params) |
| [oww_train_shim/](oww_train_shim/generate_samples.py) | Import shim so `train.py` can load without Piper when `--generate_clips` is omitted |
| [adversarial_phrases.example.txt](adversarial_phrases.example.txt) | Example phrase list for Cartesia negative clip generation (`--phrases-file`) |

### Scripts

| File | Role |
|------|------|
| [smoke_test_model.py](smoke_test_model.py) | Validation: load ONNX, silent-frame check, optional live mic test |
| [generate_samples.py](generate_samples.py) | Cartesia-first TTS WAV generator (ElevenLabs/Deepgram optional); use with oww-training-env profile |

### Deprecated (Hudson's Bay)

Historical automation and session logs — **not** the ongoing workflow:

| Location | Role |
|----------|------|
| [deprecated-hudsons-bay/AGENTS.md](deprecated-hudsons-bay/AGENTS.md) | Index: legacy `orchestrate.py`, `aws_train.sh`, 2026-04-06 session notes |
