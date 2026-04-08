# profiling/ocr-batch/ — Repeatable OCR Batch

Repeatable GPU-accelerated OCR processing task.
Layers on [aws-deep-learning-base](../aws-deep-learning-base/AGENTS.md).

## Characteristics

- **Instance type**: g4dn.xlarge (or appropriate GPU class)
- **AMI lifecycle**: build instance, convert to custom AMI, retain for reuse.
  Future launches boot from the custom AMI ready to work in ~90s.
- **Transfer pattern**: rsync in scripts + config → run OCR batch on GPU →
  rsync results out.
- **Capacity / cost:** bulk OCR is a good fit for **spot** (interruptible, cost-sensitive); long single-shot training (e.g. wake-word) often prefers **on-demand** and a separate **Running On-Demand G and VT instances** vCPU quota — see Service Quotas in the target region.

## Contents

### Profiles

| File | Role |
|------|------|
| [ocr-batch.profile.md](ocr-batch.profile.md) | State convergence profile (Target State / Apply / Audit): **torch-first** default; ONNX/paddle and historical benchmark material live in **appendices**. |

### Container development (`dev-container/`)

| Location | Role |
|----------|------|
| [dev-container/](dev-container/AGENTS.md) | Container packaging for AWS Batch: Dockerfile, processor.py, convergence profile. |

### Dev benchmarks (`sample_scan/` timing drivers)

| Location | Role |
|----------|------|
| [dev-benchmark/](dev-benchmark/AGENTS.md) | `r1-onnx.py` … `r7-paddle-tuned.py` — short names; canonical baseline **`r2-torch.py`**. |

### Utilities

| File | Role |
|------|------|
| [ocr_spacing_fix.py](ocr_spacing_fix.py) | Post-export spacing hook for spacing rounds (`apply_spacing_fix`, `SPACING_FIX_REVISION`). |
| [ocr-spacing-assess.py](ocr-spacing-assess.py) | Heuristic spacing comparison across run dirs; `--discover` scans `$OCR_WORKDIR/runs`. |

### Session history

| File | Role |
|------|------|
| [2026-04-08_build-session-1.md](2026-04-08_build-session-1.md) | Build + on-device continuation: stack installed; Docling 2.x PDF smoke test passed; profile back-filled (imports, `PdfFormatOption`, Audit §11). |
| [2026-04-08_ocr-batch-commit-report.md](2026-04-08_ocr-batch-commit-report.md) | **Commit snapshot:** torch default decision, headline timings, spacing heuristic summary, software pins; instance `WORKDIR` not retained past shutdown. |

### Increment closeouts

| File | Role |
|------|------|
| [2026-04-08_round-2-torch-closeout.md](2026-04-08_round-2-torch-closeout.md) | Round 2 closed: torch benchmark task, repo vs instance state delta, interpretation pointer. |
| [2026-04-08_round-3-paddle-closeout.md](2026-04-08_round-3-paddle-closeout.md) | Round 3 closed: Paddle + `rapidocr-paddle`, benchmark capture, install note for wheel version. |
| [2026-04-08_spacing-assess-latest-lot.md](2026-04-08_spacing-assess-latest-lot.md) | Spacing heuristic matrix for rounds 1–7 + latest-lot (4–7) notes; produced with `ocr-spacing-assess.py`. |

## User Design Brief

End state of this development will provide a cloud OCR appliance.

Interface:
- boto3
  - start/stop spot instance
  - ssh
    - inspection / troubleshoot
    - rsync

Client-side tooling:
- agent control harness
  - start / stop / status
- sync script
  - flow control - read status yaml from return folder, when inbox has files and server batch count is low, fill batch folder
  - enqueue: deposit to inbox - script queues to batch-in folder, cycles rsync
