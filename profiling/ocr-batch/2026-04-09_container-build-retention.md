# OCR fat container — build/debug retention (2026-04-09)

Session context: converge **Container image (fat)** on `cloud-task-ocr`; **Host poke** out of scope. Goal: `docker build` + fat smoke (`OCR_LOCAL_*`) producing three artifacts under `~/ocr-work/product/`.

This file is a **sequence log**: what broke, in order, what we inferred, and what we changed. It is not a polished runbook — it preserves trial-and-error signal for the next person or agent.

---

## 1. `paddle is not installed` (RapidOCR paddle backend)

**Observed:** Container run failed in RapidOCR with `ImportError: paddle is not installed` when using `backend="paddle"`.

**Learned:** The fat-image story ("Docling pulls Torch, etc.") does **not** reliably install **PaddlePaddle**. `rapidocr-paddle` expects a real `paddle` install for the paddle inference engine.

**Tried / fix:** Add explicit **`paddlepaddle-gpu==2.6.2`** (official wheel index) in the Dockerfile after `requirements.txt`, aligned with the stack pinned elsewhere in the profile for host poke.

**Profile gap:** Target text had implied transitivity; runtime showed Paddle must be **explicit** for this backend.

---

## 2. `Cannot load cudnn` / `cudnn_dso_handle should not be null` (first wave)

**Observed:** After Paddle was present, failure at OCR time: cuDNN could not load / handle null.

**Initial wrong hypotheses:**

- "Plain CUDA runtime image is missing cuDNN" → partially true, but not sufficient.
- "Use `*-cudnn-runtime`" → moved to **`nvidia/cuda:12.6.0-cudnn-runtime-ubuntu22.04`**, still failed — that image ships **cuDNN 9** (`libcudnn.so.9`), while the **Paddle 2.6.2** GPU wheel expects **cuDNN 8**-style loading.

**Tried:**

- Switch to **`nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04`** so **`libcudnn.so.8`** exists in the image.

**Still failed** after cuDNN8 base — same class of error at RapidOCR inference.

---

## 3. Paddle's hard-coded probe path for `libcudnn.so`

**Observed (from Paddle's own warning):** Paddle looks for **`/usr/local/cuda/lib64/libcudnn.so`**. On NVIDIA runtime images, cuDNN often lives under **`/usr/lib/x86_64-linux-gnu/`**, and **`/usr/local/cuda/lib64/`** may have **no** `libcudnn.so` at all.

**Learned:** This is not only "LD_LIBRARY_PATH shadowing"; the loader **first** tries a **fixed CUDA toolkit path**. Missing file there ⇒ failure even if `ldconfig` sees cuDNN elsewhere.

**Tried / fix:** **`RUN ln -sf`** from the real **`libcudnn.so.8`** into **`/usr/local/cuda/lib64/libcudnn.so`** (and `.8`).

**Minimal repro:** `python3 -c "import paddle; paddle.device.set_device('gpu:0'); paddle.randn(...)"` started working once symlinks + cuDNN8 base were correct.

---

## 4. `libcublas.so` not found (unversioned name)

**Observed:** Full Docling pipeline then failed with Paddle unable to open **`libcublas.so`** (unversioned). Image had **`libcublas.so.12`** / versioned names under `/usr/local/cuda/lib64/`, not **`libcublas.so`**.

**Learned:** Same pattern as cuDNN — Paddle's dynamic loader expects **unversioned** names in **`/usr/local/cuda/lib64/`**.

**Tried / fix:** Symlinks **`libcublas.so` → libcublas.so.12** and **`libcublasLt.so` → libcublasLt.so.12** in that directory.

---

## 5. Full fat smoke success

**Observed:** After the above, Apply §10-style run completed:

`OCR complete -> ... (service-invoice.md, service-invoice.json, service-invoice.jpg)`

**Audit:** `~/ocr-work/product/service-invoice.{md,json,jpg}` all present and non-empty where expected.

---

## 6. Model bake-in (follow-on session)

**Context:** The working container produced correct output but downloaded model weights on every cold start — visible in smoke output as `Initiating download: https://www.modelscope.cn/...`. With AWS Batch running thousands of fresh invocations, every start paying a network fetch is a latency and reliability problem.

**Goal:** Bake all model weights into the image layer so startup shows `File exists and is valid` with no downloads.

---

### 6a. Identifying what downloads and where it lands

**Three distinct model sets** download lazily at first use:

| Source | Models | Destination in container |
|--------|--------|--------------------------|
| ModelScope (rapidocr) | PP-OCRv4 det / cls / rec paddle `.pdmodel` + `.pdiparams` | `/usr/local/lib/python3.10/dist-packages/rapidocr/models/` |
| HuggingFace | `docling-project/docling-layout-heron` (layout) | `$DOCLING_ARTIFACTS_PATH/docling-project--docling-layout-heron/` |
| HuggingFace | `docling-project/docling-models@v2.3.0` (table — default TableFormer) | `$DOCLING_ARTIFACTS_PATH/docling-project--docling-models/` |

**Key finding:** docling's `resolve_model_artifacts_path()` checks `artifacts_path / repo_id.replace("/", "--")`. If that directory exists, it uses it; if `artifacts_path` is `None`, it calls HF `snapshot_download`. So `DOCLING_ARTIFACTS_PATH` pointing at a pre-populated directory is the intended bake mechanism.

**rapidocr** does not use docling's mechanism. It has its own `download_models(config_path)` utility which fetches from ModelScope by URL. No GPU is required — it's a pure HTTP fetch.

---

### 6b. Bake script approach

A `bake-models.py` runs as a Dockerfile `RUN` step, after pip installs are cached. Three calls:

1. `download_hf_model(repo_id="docling-project/docling-layout-heron", local_dir=artifacts / "docling-project--docling-layout-heron")` — layout model.
2. Same for `docling-project/docling-models@v2.3.0` — table model.
3. Write a temporary `config.yaml` with `engine_type: paddle` for Det/Cls/Rec, then call `rapidocr.utils.download_models.download_models(tmp_cfg)`.

**Lesson:** `RapidOCR()` (the main class) requires the paddle runtime to initialise — it fails at build time without a GPU. `download_models()` is a pure downloader that doesn't init the engine. **Always use the downloader, not the class init, for bake steps.**

---

### 6c. Identifying the correct default table model

**Wrong first guess:** Baked `docling-project/TableFormerV2` because that string appears in docling source. At runtime the table factory resolved to the **default** class `docling_tableformer` (not v2), which needs `docling-project/docling-models` with a `model_artifacts/tableformer/accurate/tm_config.json` layout — not `TableFormerV2`.

**Error:** `FileNotFoundError: /app/docling-models/accurate/tm_config.json`

**Lesson:** Always check `get_table_structure_factory()` to find the **default registered class**, then follow that class's `download_models()` to find the actual repo + revision. For docling 2.85: default is `TableStructureModel` → `docling-project/docling-models@v2.3.0`.

---

### 6d. Docling 2.85 `_default_models["paddle"]` KeyError

**Observed:** After baking models and setting `DOCLING_ARTIFACTS_PATH=/app/docling-models` (either as Dockerfile `ENV` or via `os.environ.setdefault`), the processor failed with:

```
KeyError: 'paddle'
```

inside `docling/models/stages/ocr/rapid_ocr_model.py`:

```python
/ self._default_models[backend_enum.value]["det_model_path"]["path"]
```

**Root cause:** In docling 2.85, `RapidOcrModel._default_models` has only `"onnxruntime"` and `"torch"` keys — `"paddle"` was dropped (rapidocr_paddle manages its own model files). When `artifacts_path` is non-None, the code tries to compute fallback paths for all five model options (`det`, `cls`, `rec`, `rec_keys`, `font`) via `None or artifacts_path / _default_models["paddle"][...]`. If any of the five `RapidOcrOptions` fields is `None`, Python evaluates the RHS — hitting the missing key.

**Failed incremental fixes:**
- Set `det_model_path`, `cls_model_path`, `rec_model_path` explicitly → still hit `rec_keys_path` lookup.
- Add `rec_keys_path` → still hit `font_path` lookup.
- Remove `ENV` from Dockerfile, set via `os.environ.setdefault` → same issue; `artifacts_path` is still set.

**Correct fix:** Provide **all five** path arguments to `RapidOcrOptions` as truthy strings pointing to baked files. This short-circuits every `None or artifacts_path / _default_models[...]` expression before it reaches the missing key. For `font_path`, there is no baked font — the keys file path is used as a dummy; rapidocr only warns about a mismatched font path, it does not abort.

```python
RapidOcrOptions(
    backend="paddle",
    det_model_path=str(RAPIDOCR_MODELS / "ch_PP-OCRv4_det_mobile"),
    cls_model_path=str(RAPIDOCR_MODELS / "ch_ppocr_mobile_v2_0_cls_mobile"),
    rec_model_path=str(RAPIDOCR_MODELS / "ch_PP-OCRv4_rec_mobile"),
    rec_keys_path=str(RAPIDOCR_MODELS / "ppocr_keys_v1.txt"),
    font_path=str(RAPIDOCR_MODELS / "ppocr_keys_v1.txt"),  # dummy; no font bundled
)
```

**Also:** `DOCLING_ARTIFACTS_PATH` must **not** be declared as a Dockerfile `ENV` directive — that would bake it into every container invocation permanently (including any future containers where you might not want it). Set it in `processor.py` via `os.environ.setdefault` before docling imports instead.

---

### 6e. Confirming bake success

Clean smoke run — all model lines show:

```
File exists and is valid: .../ch_PP-OCRv4_det_mobile/inference.pdmodel
File exists and is valid: .../ch_PP-OCRv4_det_mobile/inference.pdiparams
...
Loading weights: 100%|██████████| 770/770
OCR complete -> .../smoke-out (service-invoice.md, service-invoice.json, service-invoice.jpg)
```

No `Initiating download` lines. Baked image is ~400 MB larger than pre-bake.

---

## Side notes (not fully resolved as "design")

- **Mixed CUDA stacks:** Docling pulls **Torch** and **nvidia-* 13.x** wheels alongside a **CUDA 12.2** runtime base. It worked on this host but is architecturally "thick"; future work might pin Torch/CUDA or document the tradeoff.
- **LD_LIBRARY_PATH experiments:** Brief attempts to prepend `/usr/lib/...` in Python did **not** replace fixing **`/usr/local/cuda/lib64/`** symlinks — Paddle's error messages pointed at the toolkit path first.
- **ECR / digest:** Not part of this round; Apply §8 remains a stub for a later push.

---

## Files touched (repo)

- `profiling/ocr-batch/container/Dockerfile` — base image, `paddlepaddle-gpu` install, cuDNN/cuBLAS symlinks, bake step (`RUN python3 /tmp/bake-models.py`).
- `profiling/ocr-batch/container/bake-models.py` — new; build-time model downloader.
- `profiling/ocr-batch/container/requirements.txt` — comments (Paddle in Dockerfile for fat path).
- `profiling/ocr-batch/container/processor.py` — sets `DOCLING_ARTIFACTS_PATH` before imports; explicit paddle model paths; docstring clarification.
- `profiling/ocr-batch/ocr-batch.profile.md` — Target State updated: bake-in described, `_default_models` bug noted, smoke-clean criterion added.
- `profiling/ocr-batch/container/AGENTS.md` — `bake-models.py` entry added.

---

## One-line summary

**Fat OCR container needed:** explicit **Paddle GPU wheel**, **cuDNN8-compatible** base, **symlinks into `/usr/local/cuda/lib64/`**, and **all three model sets baked in** via `bake-models.py` — with all five explicit paddle model paths in `processor.py` to work around docling 2.85's missing `_default_models["paddle"]` key.
