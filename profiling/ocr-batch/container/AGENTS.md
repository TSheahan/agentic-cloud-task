# profiling/ocr-batch/container/ — Container Build Artifacts

Docker image artifacts for the OCR Batch processor. Referenced by the
companion profile [`container-image.profile.md`](../container-image.profile.md)
(Target State; Apply §2; Audit §1–§3).

Not a profile directory — the convergence profile lives at the parent level.

## Contents

| File | Role |
|------|------|
| [Dockerfile](Dockerfile) | CUDA + cuDNN8 base, `requirements.txt` + `paddlepaddle-gpu`, symlinks for Paddle's `/usr/local/cuda/lib64/` probes, bake step — see parent profile |
| [requirements.txt](requirements.txt) | Glue packages: `docling`, `rapidocr-paddle`, `boto3`, `pydantic` |
| [bake-models.py](bake-models.py) | Build-time model downloader: bakes docling layout (`docling-project/docling-layout-heron`), table (`docling-project/docling-models@v2.3.0`), and rapidocr paddle OCR models into the image layer; invoked by `RUN python3 /tmp/bake-models.py` in Dockerfile |
| [processor.py](processor.py) | S3 / local Docling 2.x RapidOCR paddle batch processor; three-output contract; sets `DOCLING_ARTIFACTS_PATH` before docling imports; passes explicit baked paddle model paths to sidestep docling 2.85+ `_default_models["paddle"]` lookup |
| [run-local-smoke.sh](run-local-smoke.sh) | `docker run` with `OCR_LOCAL_FILE` / `OCR_LOCAL_OUTPUT_DIR`; mounts repo at `/work`; default input `test-media/service-invoice.jpg` → `smoke-out/` (see [Audit §7](../container-image.profile.md)) |
| [poke-smoke-test.py](poke-smoke-test.py) | Single-image Docling + RapidOCR paddle CUDA smoke test; PASS/FAIL with timing |
| [01-starting-theory-of-container.md](01-starting-theory-of-container.md) | Pre-profile brain dump; superseded by the parent profile |
| [2026-04-09_container-dev-handoff.md](2026-04-09_container-dev-handoff.md) | Executing-agent handoff from the original build session |
