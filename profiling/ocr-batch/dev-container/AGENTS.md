# profiling/ocr-batch/dev-container/ — Container Development

Container packaging of the torch-first OCR pipeline for AWS Batch.
Layers on [ocr-batch](../AGENTS.md) (instance must be converged first).

## Contents

| File | Role |
|------|------|
| [dev-container.profile.md](dev-container.profile.md) | State convergence profile: container artifacts, build, GPU smoke test |
| [01-starting-theory-of-container.md](01-starting-theory-of-container.md) | Pre-profile brain dump (Dockerfile + processor + ECR push); superseded by the profile for convergence |
| [Dockerfile](Dockerfile) | NVIDIA CUDA runtime base, Python 3.10, torch CUDA, docling stack |
| [requirements.txt](requirements.txt) | Python deps for the container (torch-first, no paddle) |
| [processor.py](processor.py) | S3→Docling 2.x RapidOCR paddle→S3 batch processor; three-output contract; local env via `OCR_LOCAL_*` |
| [2026-04-09_container-dev-handoff.md](2026-04-09_container-dev-handoff.md) | Executing-agent handoff: situation, mission, Grok-sourced unknowns, sequence |
