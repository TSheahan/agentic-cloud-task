# profiling/ocr-batch/container/ — Container Build Artifacts

Docker image artifacts for the OCR Batch processor. Referenced by the
parent profile [`ocr-batch.profile.md`](../ocr-batch.profile.md) (Target
State → Thin container; Apply §7; Audit §7–§9).

Not a profile directory — the convergence profile lives at the parent level.

## Contents

| File | Role |
|------|------|
| [Dockerfile](Dockerfile) | NVIDIA CUDA 12.6 runtime base, Python 3.10, pip glue deps only — no heavy ML wheels |
| [requirements.txt](requirements.txt) | Glue packages: `docling`, `rapidocr-paddle`, `boto3`, `pydantic` |
| [processor.py](processor.py) | S3 / local Docling 2.x RapidOCR paddle batch processor; three-output contract |
| [poke-smoke-test.py](poke-smoke-test.py) | Single-image Docling + RapidOCR paddle CUDA smoke test; PASS/FAIL with timing |
| [01-starting-theory-of-container.md](01-starting-theory-of-container.md) | Pre-profile brain dump; superseded by the parent profile |
| [2026-04-09_container-dev-handoff.md](2026-04-09_container-dev-handoff.md) | Executing-agent handoff from the original build session |
