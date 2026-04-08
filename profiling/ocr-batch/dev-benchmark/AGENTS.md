# profiling/ocr-batch/dev-benchmark/

Ad-hoc **Docling + RapidOCR** timing drivers for `WORKDIR/sample_scan/` evaluation. Not part of the profiled **Apply** path except where the parent [`ocr-batch.profile.md`](../ocr-batch.profile.md) references them (canonical baseline: **`r2-torch.py`**).

Parent: [profiling/ocr-batch/AGENTS.md](../AGENTS.md).

## Scripts

| File | Role |
|------|------|
| [r1-onnx.py](r1-onnx.py) | Round 1: CUDA vs CPU Docling sweep; default RapidOCR (ONNX on CPU). |
| [r2-torch.py](r2-torch.py) | Round 2: **`backend="torch"`** — profiled default **canonical** baseline. |
| [r3-paddle.py](r3-paddle.py) | Round 3: **`backend="paddle"`**. |
| [r4-onnx-spacing.py](r4-onnx-spacing.py) | Round 4: ONNX, GPU-only, `Rec.use_space_char` via `rapidocr_params`. |
| [r5-torch-spacing.py](r5-torch-spacing.py) | Round 5: torch, GPU-only, spacing params. |
| [r6-paddle-spacing.py](r6-paddle-spacing.py) | Round 6: paddle, GPU-only, spacing params. |
| [r7-paddle-tuned.py](r7-paddle-tuned.py) | Round 7: paddle tuned (`text_score`, `Det.score_mode`, …). |
| [ocr_spacing_fix.py](ocr_spacing_fix.py) | Post-export spacing hook imported by rounds 4–7. |
| [ocr-spacing-assess.py](ocr-spacing-assess.py) | Heuristic spacing comparison across run dirs; `--discover` scans `$OCR_WORKDIR/runs`. |

## Run (instance)

```bash
export OCR_WORKDIR=/home/ubuntu/ocr-work
source "$OCR_WORKDIR/venv/bin/activate"
python /path/to/repo/profiling/ocr-batch/dev-benchmark/r2-torch.py "$OCR_WORKDIR/runs/<run-id>"
```

Copy `r*.py` plus `ocr_spacing_fix.py` into a run directory if running without a repo checkout.
