# Round 3 (RapidOCR paddle) — increment closeout

**Date:** 2026-04-08  
**Status:** **Closed** — Paddle stack installed, benchmark run completed, `SUMMARY.md` on instance, profile Apply §3e and Audit §14 added.

---

## Task

| Field | Value |
|-------|--------|
| **Intent** | Third OCR evaluation: **`RapidOcrOptions(backend="paddle")`** with `force_full_page_ocr`, `do_table_structure`, `ocr_batch_size` via env; same six `sample_scan/` JPEGs. |
| **Deliverables** | `paddlepaddle-gpu` + `rapidocr-paddle` in venv; timed sweep; `runs/2026-04-08_docling-paddle-round3-v1/`; profile + tooling updates. |
| **Install note** | Requested `paddlepaddle-gpu==2.6.2.post117` was **not** on the Paddle index; **`2.6.2`** installed. `paddle.utils.run_check()` OK on T4. |

---

## System state change

### Repository

- [`dev-benchmark/r3-paddle.py`](r3-paddle.py) (already present; exercised end-to-end).
- [`ocr-batch.profile.md`](../ocr-batch.profile.md) — round-3 Target State, Apply §3e, Audit §14.
- [`AGENTS.md`](../AGENTS.md) — tooling row finalized.

### Instance

- Pip packages: **`paddlepaddle-gpu` 2.6.2**, **`rapidocr-paddle` 1.4.5** (large wheel + RapidOCR paddle model files under `venv/.../rapidocr/models/`).
- Run directory: **`~/ocr-work/runs/2026-04-08_docling-paddle-round3-v1/`**.

---

## Result snapshot (aggregate)

CUDA sum **~22.3 s** · CPU sum **~192 s** · ratio **~8.6×** (Docling CPU forces paddle OCR to CPU, same pattern as round 2).
