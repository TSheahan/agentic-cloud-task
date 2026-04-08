# OCR Batch Build Session 1 — Hand-off

**Date:** 2026-04-08
**Instance:** `cloud-task-ocr` — `i-08bad83e392dd6cb5` @ `3.106.240.196`
**Type:** g4dn.xlarge spot (ap-southeast-2)
**AMI:** `ami-06c90ff5b4e22cce6` (baked-core-gpu)
**WORKDIR:** `/home/ubuntu/ocr-work`

---

## What was done

### Infrastructure (converged)

1. **Profile skeleton created** — `ocr-batch.profile.md` patterned after
   `sara-wakeword/oww-training-env.profile.md`. Common Target State items
   filled; OCR-specific items populated with what we discovered.

2. **Spot instance launched** from baked-core-gpu AMI. Required
   `--instance-initiated-shutdown-behavior terminate` because one-time spot
   requests cannot combine `stop` shutdown with `terminate` interruption
   behavior. On-demand vCPU quota for G-family is 0 (increase requested
   2026-04-08 09:40 AEST — pending at session end).

3. **Base profile confirmed converged** — baked AMI includes apt fix, system
   packages (5/5), agent CLI, project repo clone, Python 3.10.12.

4. **WORKDIR + venv created** at `/home/ubuntu/ocr-work/venv` (Python 3.10.12).

5. **`cloud-resources.md` updated** — Nodes row and SSH commands for
   `cloud-task-ocr`.

### OCR stack (installed, not yet smoke-tested)

6. **`docling[rapidocr]` installed** — docling 2.85.0, rapidocr 3.7.0.
7. **`onnxruntime-gpu` installed** — 1.23.2. `CUDAExecutionProvider` confirmed
   available alongside TensorRT and CPU providers.
8. **GPU verified** — Tesla T4, driver 580.126.09, 15360 MiB VRAM.
9. **Docker present** — 29.3.1 (from DL AMI, not actively used).
10. **System deps verified** — `python3-dev`, `libsm6`, `libxext6` already
    installed from the baked AMI.
11. **Disk** — venv 5.8 GB, root volume 50% used (61 GB free of 121 GB).

### What was NOT done

- **No smoke test** — no PDF has been converted yet. The next step is to run
  a single document through Docling and confirm end-to-end operation.
- **Headless auth** — agent CLI and `gh` are installed but **not
  authenticated** on this instance. Run headless-auth if the on-device agent
  needs it.
- **No batch folder structure** — the transfer/inbox/outbox layout from the
  design brief is still a placeholder in Target State.
- **No AMI bake** — the instance is still running with the OCR stack installed
  but not yet validated. Bake after smoke test confirms the stack works.

---

## What to do next

This build follows an incremental **develop-a-step → back-fill-the-profile**
pattern. The user will specify the activity list for OCR-specific work. The
broad arc:

### Immediate next step

**Smoke test: convert a single PDF.**

1. Deposit a scanned PDF to the instance:
   ```bash
   scp /path/to/test.pdf cloud-task-ocr:/home/ubuntu/ocr-work/
   ```

2. Run a minimal Docling conversion on the instance:
   ```python
   from docling.document_converter import DocumentConverter
   from docling.datamodel.pipeline_options import (
       PdfPipelineOptions, RapidOcrOptions,
       AcceleratorOptions, AcceleratorDevice,
   )
   from docling.datamodel.base import InputFormat

   pipeline_options = PdfPipelineOptions(
       do_ocr=True,
       ocr_options=RapidOcrOptions(),
       accelerator_options=AcceleratorOptions(
           device=AcceleratorDevice.CUDA,
           num_threads=4,
       ),
   )
   converter = DocumentConverter(
       allowed_formats=[InputFormat.PDF],
       pipeline_options=pipeline_options,
   )
   result = converter.convert("/home/ubuntu/ocr-work/test.pdf")
   md = result.document.export_to_markdown()
   print(md[:2000])
   ```

3. Assess: did it use the GPU? How long did it take? Is the OCR quality
   acceptable?

4. Back-fill findings into the profile.

### Subsequent steps (user-directed)

- Define the batch folder structure (inbox → processing → outbox)
- Build the processing script (replaces the S3-oriented `processor.py`
  sample with SSH-deposition flow)
- Batch control: status yaml, flow control
- AMI bake once the stack is validated
- Client-side tooling: start/stop/status harness, sync script

---

## Research notes

### RapidOCR GPU acceleration

`rapidocr` (the onnxruntime variant installed by `docling[rapidocr]`) does
**not** effectively GPU-accelerate the OCR text extraction step itself. The
`use_gpu=True` parameter in `RapidOcrOptions` is a legacy flag. For GPU OCR,
`rapidocr_paddle` (PaddlePaddle backend) would be needed — this is a heavy
dependency (~2 GB, CUDA version coupling).

However, the **main GPU value** in this stack comes from Docling's own model
inference (layout analysis, table structure recognition) via
`onnxruntime-gpu` + `AcceleratorOptions(device=CUDA)`. The OCR text extraction
step is typically a smaller fraction of total runtime. Evaluate after the smoke
test whether CPU OCR throughput is acceptable before investing in PaddlePaddle
GPU.

### Spot launch constraints (ap-southeast-2)

- g4dn.xlarge spot capacity was exhausted for ~50 minutes during this session
  before becoming available.
- One-time spot requests: `instanceInitiatedShutdownBehavior: stop` is
  incompatible with `instanceInterruptionBehavior: terminate`. Use
  `--instance-initiated-shutdown-behavior terminate`.
- On-demand G-family vCPU quota is 0. Quota increase requested; approval
  pending.

---

## Files modified this session

| File | Change |
|------|--------|
| `profiling/ocr-batch/ocr-batch.profile.md` | Created — full skeleton with Target State, Apply, Audit |
| `profiling/ocr-batch/AGENTS.md` | Updated — added profile reference and contents table |
| `cloud-resources.md` | Updated — Nodes row and SSH commands for cloud-task-ocr |
| `profiling/ocr-batch/2026-04-08_build-session-1.md` | This file |

### Session 2 file changes

| File | Change |
|------|--------|
| `profiling/ocr-batch/ocr-batch.profile.md` | Smoke-test Target State; Apply §3b + API notes; Audit §7 imports; Audit §11; bake gated on smoke |
| `profiling/ocr-batch/2026-04-08_build-session-1.md` | Session 2 continuation appended |

---

## Session 2 continuation (same day, on-instance)

### Done

- **Docling smoke test passed.** Generated `test.pdf` on the instance (Pillow +
  `img2pdf` — `img2pdf` installed in venv for this test only). One-page image
  PDF with rendered Latin text.
- **Conversion:** `ConversionStatus.SUCCESS`. Sample export line (Markdown):
  `## OCR smoketest 2026-04-08` (expected minor OCR variance vs source string
  `"OCR smoke test 2026-04-08"`).
- **Timing (indicative):** ~39 s CPU time for first full run after cold start
  (includes first-time Hugging Face weight download + layout model load); ~67 s
  wall clock in that run. Repeat run ~12 s wall (same converter path; still
  logs layout weight load).
- **Imports / API:** Docling 2.x uses `InputFormat` from
  `docling.datamodel.base_models` (not `datamodel.base`). `DocumentConverter`
  takes PDF options via
  `format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=...)}`.
- **Profile back-fill:** `ocr-batch.profile.md` updated — Target State smoke
  item, Apply §3b, Audit §7 import fix, Audit §11 (slow smoke), bake gate tied
  to smoke success.

### Still open (unchanged from Session 1 unless noted)

- Headless auth for `agent` / `gh` if needed.
- Batch folder layout (inbox / processing / outbox) — still TBD.
- AMI bake after you are satisfied with stack validation.
- Optional: pin `img2pdf` in a small `requirements-smoke.txt` or document only
  (not installed by default).

### Suggested next steps

1. Decide **batch directory layout** and add concrete Target State + Apply for
   mkdir/rsync conventions.
2. **Processing script** skeleton that reads from inbox, writes to outbox, uses
   the `PdfFormatOption` pattern above.
3. **AMI bake** when ready.
