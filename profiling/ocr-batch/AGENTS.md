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
| [ocr-batch.profile.md](ocr-batch.profile.md) | State convergence profile for the OCR batch environment (Target State / Apply / Audit) |

### Session history

| File | Role |
|------|------|
| [2026-04-08_build-session-1.md](2026-04-08_build-session-1.md) | First build session: instance launched, base converged, Docling + RapidOCR + onnxruntime-gpu installed. Hand-off for on-device continuation. |

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
