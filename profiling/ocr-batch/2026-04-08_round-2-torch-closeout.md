# Round 2 (RapidOCR torch) — increment closeout

**Date:** 2026-04-08  
**Status:** **Closed** — benchmark captured, profile updated, informal quality notes recorded in run `SUMMARY.md`.

---

## Task deposited (this increment)

| Field | Value |
|-------|--------|
| **Intent** | Second OCR evaluation round: Docling + **RapidOCR `backend="torch"`** (`force_full_page_ocr`, `do_table_structure`, `ocr_batch_size` via env), same six `sample_scan/` JPEGs as round 1. |
| **Deliverables** | Timed CUDA vs CPU sweep (`timings.json`), Markdown exports, human `SUMMARY.md` (methodology, cross-round caution, **output quality** notes), repo benchmark script, profile Target State + Apply §3d + Audit §13. |
| **Canonical run** | `2026-04-08_docling-torch-round2-v1` under `WORKDIR/runs/` on the OCR instance. |

---

## System state change

### Repository (durable, committed)

- [`dev-benchmark/r2-torch.py`](dev-benchmark/r2-torch.py) — round 2 benchmark driver.
- [`ocr-batch.profile.md`](ocr-batch.profile.md) — evaluation Target State item, Apply §3d, Audit §13; Docling 2.x wiring notes.
- [`AGENTS.md`](AGENTS.md) — tooling table row for round 2 script.

No change to `cloud-resources.md`, IAM, or launch tooling for this increment.

### Instance (`cloud-task-ocr` / `WORKDIR`, mutable)

- **New tree:** `~/ocr-work/runs/2026-04-08_docling-torch-round2-v1/` (`timings.json`, `SUMMARY.md`, `outputs/cuda/`, `outputs/cpu/`, `run_benchmark.py`).
- **Venv:** RapidOCR **torch** `.pth` weights cached under `venv/lib/python3.10/site-packages/rapidocr/models/` (downloaded on first torch run).
- **No** AMI bake, **no** replacement of base AMI in catalog for this step alone.

Reproducibility: re-run from repo script per profile Apply §3d; fresh nodes repeat model download unless weights are copied or baked.

---

## Interpretation anchor (for later readers)

Round 2 **CUDA pass** (~26 s for six images) vs **CPU pass** (~516 s) reflects **full GPU stack** (Docling CUDA + torch OCR on GPU) vs **full CPU stack** (Docling CPU + torch OCR on CPU) — not comparable to round 1’s ~1.5× ratio where ONNX RapidOCR stayed CPU in both passes. Subjective Markdown quality: round 2 **fewer** missed spaces than round 1; **some** remain.

---

## Next

Round 3+ can add a new `runs/<run-id>/` using the same layout; update profile canonical ids or treat audits as examples.
