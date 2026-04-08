# Spacing heuristics — latest lot (rounds 4–7) + full benchmark matrix

**Date:** 2026-04-08  
**Tool:** [`ocr-spacing-assess.py`](ocr-spacing-assess.py) (`--discover` over `OCR_WORKDIR/runs`).  
**Inputs:** Same six `sample_scan/*.jpg` for every run; metrics computed on **`outputs/cuda/*.md`** (CUDA path).

## Metrics (automated, limited)

| Metric | Meaning |
|--------|---------|
| **camel** | Count of `[a-z][A-Z]` in flattened text — *lower often suggests fewer glued Latin tokens* (also false positives: real camelCase). |
| **digit_letter** | Count of `[0-9][a-zA-Z]` — noisy (units, table tokens). |
| **space_ratio** | Fraction of space/tab among non-newline characters — *higher* can mean more whitespace in prose (tables dilute). |

These do **not** replace visual review against source images.

## Mean aggregates (six files per run)

| Run | Round / note | mean camel | mean digit_letter | mean space_ratio |
|-----|----------------|------------|-------------------|------------------|
| `...gpu-eval-v1` | 1 ONNX | 17.333 | 9.167 | 0.2737 |
| `...torch-round2-v1` | 2 torch | 16.833 | 8.833 | 0.2794 |
| `...paddle-round3-v1` | 3 paddle | 17.333 | 9.167 | 0.2737 |
| `...onnx-round4-gpu-spacing-v1` | 4 ONNX + `Rec.use_space_char` | 17.333 | 9.167 | 0.2737 |
| `...torch-round5-gpu-spacing-v1` | 5 torch + spacing params | 16.833 | 8.833 | 0.2794 |
| `...paddle-round6-gpu-spacing-v1` | 6 paddle + `Rec.use_space_char` | 17.333 | 9.167 | 0.2737 |
| `...paddle-round7-tuned-v1` | **7 paddle tuned** (`text_score=0.6`, `Det.score_mode=slow`, …) | **16.833** | **9.333** | **0.2731** |

## Latest lot (rounds 4–7) — interpretation

- **Round 7 vs round 6 (same paddle GPU path, added tuning):** **camel** mean drops from **17.333 → 16.833** (same as torch cluster on this sample). **space_ratio** ticks down slightly (**0.2737 → 0.2731**). **digit_letter** rises **9.167 → 9.333** (mixed signal; often table-heavy).
- **Round 7 vs round 2/5 (torch):** **camel** matches torch (**16.833**). **space_ratio** remains lower than torch (**0.2731** vs **0.2794**).
- **ONNX/Paddle cluster (1, 3, 4, 6)** remains identical on these three metrics; **round 7** is the first paddle run in this matrix that **diverges** from that cluster on **camel** (aligned with torch) while staying in the same **space_ratio** band as other ONNX/Paddle runs (within ~0.0006).

## Reproduce

```bash
export OCR_WORKDIR=/home/ubuntu/ocr-work
python profiling/ocr-batch/ocr-spacing-assess.py --discover
python profiling/ocr-batch/ocr-spacing-assess.py "$OCR_WORKDIR/runs/2026-04-08_docling-paddle-round7-tuned-v1"
```
