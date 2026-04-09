# profiling/ocr-batch/ — Repeatable OCR Batch

Repeatable GPU-accelerated OCR processing task.
Layers on [aws-deep-learning-base](../aws-deep-learning-base/AGENTS.md).

## Characteristics

- **Instance type**: g4dn.xlarge (or appropriate GPU class)
- **AMI lifecycle**: build instance, convert to custom AMI, retain for reuse.
  Future launches boot from the custom AMI ready to work in ~90s.
- **Transfer pattern**: rsync in scripts + config → run OCR batch on GPU →
  rsync results out.
- **Capacity / cost:** bulk OCR is a good fit for **spot** (interruptible,
  cost-sensitive); AMI-bake and endurance sessions use **on-demand** — see
  Service Quotas for the target region.

## Contents

### Profile

| File | Role |
|------|------|
| [ocr-batch.profile.md](ocr-batch.profile.md) | Unified convergence profile: shared infra; **optional** tracks for **host poke** vs **container image** (fat default for Batch; thin+Paddle-bind alternate). Torch path in appendix (historical). |

### Container artifacts (`container/`)

| Location | Role |
|----------|------|
| [container/](container/AGENTS.md) | Dockerfile, processor.py, requirements.txt — build context for the OCR container image (fat or thin strategy per profile). |

### Dev benchmarks

| Location | Role |
|----------|------|
| [dev-benchmark/](dev-benchmark/AGENTS.md) | `r1-onnx.py` … `r7-paddle-tuned.py` — timing drivers; historical baseline `r2-torch.py`. |

### Utilities

| File | Role |
|------|------|
| [container/run-local-smoke.sh](container/run-local-smoke.sh) | Container fat smoke: `docker run` + `OCR_LOCAL_*`, repo mounted at `/work`; defaults to `test-media/service-invoice.jpg` → `smoke-out/`. [Audit §13](ocr-batch.profile.md). |
| [poke-smoke-test.py](container/poke-smoke-test.py) | Single-image Docling + RapidOCR paddle CUDA smoke test; PASS/FAIL with timing. Used by [Audit §5](ocr-batch.profile.md). |
| [ocr_spacing_fix.py](dev-benchmark/ocr_spacing_fix.py) | Post-export spacing hook for spacing rounds (`apply_spacing_fix`, `SPACING_FIX_REVISION`). |
| [ocr-spacing-assess.py](dev-benchmark/ocr-spacing-assess.py) | Heuristic spacing comparison across run dirs; `--discover` scans `$OCR_WORKDIR/runs`. |

### Session history

| File | Role |
|------|------|
| [2026-04-08_build-session-1.md](dev-benchmark/2026-04-08_build-session-1.md) | Build + on-device continuation: stack installed; Docling 2.x PDF smoke test passed; profile back-filled. |
| [2026-04-08_ocr-batch-commit-report.md](dev-benchmark/2026-04-08_ocr-batch-commit-report.md) | Commit snapshot: torch default decision, headline timings, spacing heuristic summary, software pins. |
| [2026-04-09_container-build-retention.md](2026-04-09_container-build-retention.md) | Container image build/debug sequence log: Paddle install, cuDNN8 base, symlinks, model bake-in, `_default_models["paddle"]` workaround. |

### Increment closeouts

| File | Role |
|------|------|
| [2026-04-08_round-2-torch-closeout.md](dev-benchmark/2026-04-08_round-2-torch-closeout.md) | Round 2 closed: torch benchmark task, repo vs instance state delta. |
| [2026-04-08_round-3-paddle-closeout.md](dev-benchmark/2026-04-08_round-3-paddle-closeout.md) | Round 3 closed: Paddle + `rapidocr-paddle`, benchmark capture, install note. |
| [2026-04-08_spacing-assess-latest-lot.md](dev-benchmark/2026-04-08_spacing-assess-latest-lot.md) | Spacing heuristic matrix for rounds 1–7. |

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
