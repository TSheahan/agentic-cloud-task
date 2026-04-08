# OCR batch — commit snapshot (ephemeral instance)

**Time bound:** 2026-04-08. **Audience:** project commit; operators after the **`cloud-task-ocr`** build instance is gone.

**Context:** The working **`WORKDIR`** on the instance (e.g. `~/ocr-work`, `runs/`, `sample_scan/`, `venv/`) is **not** retained past shutdown. This file **does** retain **decisions, versions, and headline metrics** that matter for the repo.

---

## What endures in git (durable)

| Artifact | Role |
|----------|------|
| [`ocr-batch.profile.md`](../ocr-batch.profile.md) | **Torch-first** Target State / Apply / Audit; ONNX, paddle, and legacy benchmark steps in **appendices**. |
| Benchmark drivers + [`ocr-spacing-assess.py`](ocr-spacing-assess.py), [`ocr_spacing_fix.py`](ocr_spacing_fix.py) | Reproducible evaluation and spacing heuristics. |
| [`2026-04-08_spacing-assess-latest-lot.md`](2026-04-08_spacing-assess-latest-lot.md) | Full heuristic matrix table (rounds 1–7 on the six-image set). |
| This report | Session snapshot: decisions + timing table + software pins. |

**Not durable:** per-run Markdown under `WORKDIR/runs/*/outputs/`, local `timings.json` copies on disk only, scratch PDFs—unless someone **rsyncs** them elsewhere before teardown.

---

## Decision (profiled default)

**RapidOCR `backend="torch"`** (PyTorch on GPU with Docling `AcceleratorDevice.CUDA`) is the **profiled default** for OCR batch. **Evidence:** on the canonical six JPEG evaluation set, torch produced **better prose word spacing** than default ONNX (RapidOCR on CPU + Docling CUDA) and than paddle on aggregate readability; automated spacing metrics were **weak discriminators** but aligned with that read (see spacing-assess note below). **Canonical regression baseline:** round-2 torch capture, run id **`2026-04-08_docling-torch-round2-v1`**, script [`dev-benchmark/r2-torch.py`](r2-torch.py).

ONNX and paddle remain **reference** backends ([`ocr-batch.profile.md` Appendix A](../ocr-batch.profile.md#appendix-a--alternate-rapidocr-backends-reference)).

---

## Headline timing metrics (six images, `sample_scan/`)

GPU-only passes where applicable; **same machine** (g4dn / T4 class, Docling 2.85.x stack as installed during session). **Cold** first-file load excluded from row sums where the driver reports `cuda_sum_s` over timed loop only.

| Label | Script / run | `cuda_sum_s` (approx.) | Notes |
|-------|----------------|------------------------|--------|
| Round 4 ONNX + spacing params | [`dev-benchmark/r4-onnx-spacing.py`](r4-onnx-spacing.py) | **~48** | Partial GPU (RapidOCR ONNX on CPU). |
| Round 5 torch + spacing | [`dev-benchmark/r5-torch-spacing.py`](r5-torch-spacing.py) | **~25.7** | Full GPU OCR stack. |
| Round 6 paddle + spacing | [`dev-benchmark/r6-paddle-spacing.py`](r6-paddle-spacing.py) | **~22.0** | |
| Round 7 paddle tuned | [`dev-benchmark/r7-paddle-tuned.py`](r7-paddle-tuned.py) | **~21.7** | `text_score=0.6`, `Det.score_mode=slow`, `Rec.use_space_char` via `rapidocr_params`. |

**Earlier CUDA vs CPU sweep (round 2 torch, six images):** CUDA total **~26 s**, CPU total **~516 s** (full CPU stack); see [`2026-04-08_round-2-torch-closeout.md`](2026-04-08_round-2-torch-closeout.md).

Interpretation: **torch** sits between **paddle** (fastest here) and **ONNX** (slowest on this set) for **wall time**; **default choice remains torch** for **spacing/readability**, not raw minimum seconds.

---

## Spacing heuristics (automated, limited)

Aggregates over six exported `outputs/cuda/*.md` files (see [`2026-04-08_spacing-assess-latest-lot.md`](2026-04-08_spacing-assess-latest-lot.md)):

- **Torch (rounds 2 / 5):** mean **camel** `[a-z][A-Z]` **16.833**, mean **space_ratio** **~0.279** — best **space_ratio** in the matrix.
- **ONNX/paddle cluster (1, 3, 4, 6):** mean **camel** **17.333**, **space_ratio** **~0.274** (round **7** paddle tuned: **camel 16.833**, **space_ratio ~0.273**).
- **`Rec.use_space_char`** via Docling `rapidocr_params` did **not** change exported text vs baseline on these files for matching backends; tuning (round 7) moved paddle **camel** toward the torch cluster without a clear “spacing win” story in bulk metrics.

**Takeaway:** metrics support **torch as default** for qualitative spacing; **do not** over-trust global ratios for QA.

---

## Software pins (instance session)

Recorded at benchmark time where available:

| Component | Version / note |
|-----------|----------------|
| Docling | 2.85.0 |
| rapidocr | 3.7.0 (via `docling[rapidocr]`) |
| onnxruntime-gpu | 1.23.2 |
| Paddle (round 7 only) | paddlepaddle-gpu **2.6.2**, rapidocr-paddle **1.4.5** |
| Python venv | 3.10.x |

---

## Next operator

1. Converge [`ocr-batch.profile.md`](../ocr-batch.profile.md) Apply / Audit on a **fresh** node from AMI or bootstrap.  
2. Recreate **`WORKDIR`**, **`sample_scan/`**, and the **canonical torch run** if regression baselines are required.  
3. Use **`ocr-spacing-assess.py --discover`** after runs to compare heuristics.

---

## Related

- [Round 2 closeout](2026-04-08_round-2-torch-closeout.md) · [Round 3 closeout](2026-04-08_round-3-paddle-closeout.md)  
- [Spacing assess detail](2026-04-08_spacing-assess-latest-lot.md)  
- [Build session 1](2026-04-08_build-session-1.md)
