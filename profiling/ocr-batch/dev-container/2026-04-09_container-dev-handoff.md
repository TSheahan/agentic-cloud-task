# Container dev handoff — 2026-04-09

## Situation

The **cloud-task-ocr** instance is running and converged per
[ocr-batch.profile.md](../ocr-batch.profile.md) — bare-metal OCR stack
(Docling + RapidOCR torch on CUDA, onnxruntime-gpu, T4 GPU verified).
See [cloud-resources.md](../../../cloud-resources.md) for SSH host, IP,
WORKDIR (`/home/ubuntu/ocr-work`).

## Mission

Extend the instance to build and run a **containerized** OCR processor
for AWS Batch. Profile:
[dev-container.profile.md](dev-container.profile.md).

Experimental source files are in this directory: `Dockerfile`,
`requirements.txt`, `processor.py`. They need to be transferred to the
instance, built, and smoke-tested.

## What to watch for

The source files were derived from an **external Grok research dump**
([01-starting-theory-of-container.md](01-starting-theory-of-container.md))
cross-checked against the profiled state. Major API misalignments were
already corrected (paddle→torch, Docling 2.x `format_options`, import
paths). Two items still need **runtime verification on-instance**:

1. **`export_to_dict()`** in processor.py — only `export_to_markdown()`
   is profile-validated. Check the installed Docling version's actual API
   and fix if needed.
2. **CUDA base image version** (12.6.0) and **torch index** (cu124) in
   the Dockerfile — must be compatible with the host driver. Run
   `nvidia-smi` to confirm the driver's CUDA version and adjust if the
   container build or GPU test fails.

Docker and nvidia-container-toolkit availability on the DL AMI is also
unconfirmed — the profile's Apply §3 covers the install path if missing.

## Sequence

1. Confirm Docker + nvidia-container-toolkit are present (or install).
2. Transfer source files to instance (`rsync` per Apply §2).
3. Verify the two Grok-sourced unknowns above before building.
4. `docker build` and GPU smoke test.
5. Refine the profile with what you learn.
