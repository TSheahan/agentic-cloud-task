# profiling/sara-wakeword/ — Wake Word Training

One-shot training run for a custom OpenWakeWord model ("hey Sara").
Layers on [aws-deep-learning-base](../aws-deep-learning-base/AGENTS.md).

## Characteristics

- **Instance type**: g4dn.xlarge (or .2xlarge if needed)
- **Runtime**: ~2-4 hours on g4dn
- **Dependencies**: Python 3.10-3.11, PyTorch + CUDA, OpenWakeWord (training
  mode), synthetic TTS data generation tools, tflite/ONNX export
- **AMI lifecycle**: one-shot — AMI discarded after training completes
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

### Scripts

| File | Role |
|------|------|
| [orchestrate.py](orchestrate.py) | Happy-path automation: launch AWS spot, upload config, train remotely, pull model back, tear down |
| [aws_train.sh](aws_train.sh) | Remote training script (runs on the AWS instance) |
| [smoke_test_model.py](smoke_test_model.py) | Local (Pi-side) validation: load ONNX, silent-frame check, optional live mic test |
| [generate_samples.py](generate_samples.py) | Local TTS sample generator using Cartesia/ElevenLabs/Deepgram backends |

### Session history

| File | Role |
|------|------|
| [2026-04-06_hudsons-bay-session-1.md](2026-04-06_hudsons-bay-session-1.md) | First session: pipeline built, IAM blockers resolved, spot quota blocked |
| [2026-04-06_hudsons-bay-session-2.md](2026-04-06_hudsons-bay-session-2.md) | Second session: runtime fix chain, teardown, proposal for declarative playbook approach |
