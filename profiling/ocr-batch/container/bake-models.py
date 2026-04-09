"""
Build-time model bake script — run inside the container image during `docker build`.

Downloads/pre-populates into fixed paths so every container invocation (thousands
of AWS Batch cold starts) skips network I/O on startup:

  /app/docling-models/docling-project--docling-layout-heron/   (HF: layout model)
  /app/docling-models/docling-project--TableFormerV2/           (HF: table model)
  /usr/local/lib/python3.10/dist-packages/rapidocr/models/     (ModelScope: paddle OCR)

ENV DOCLING_ARTIFACTS_PATH=/app/docling-models must match in Dockerfile.
Exits non-zero on any failure so `docker build` aborts.
"""
import os
import sys
import pathlib
import tempfile

DOCLING_MODELS = "/app/docling-models"
os.environ["DOCLING_ARTIFACTS_PATH"] = DOCLING_MODELS
os.makedirs(DOCLING_MODELS, exist_ok=True)

artifacts = pathlib.Path(DOCLING_MODELS)

from docling.models.utils.hf_model_download import download_hf_model

# ---------------------------------------------------------------------------
# 1. Docling layout model
# ---------------------------------------------------------------------------
print("=== baking docling layout model (docling-project/docling-layout-heron) ===",
      flush=True)

LAYOUT_REPO = "docling-project/docling-layout-heron"
LAYOUT_DIR = artifacts / LAYOUT_REPO.replace("/", "--")
try:
    download_hf_model(repo_id=LAYOUT_REPO, local_dir=LAYOUT_DIR, revision="main")
except Exception as e:
    print(f"ERROR: layout model download failed: {e}", file=sys.stderr)
    sys.exit(1)

layout_files = list(LAYOUT_DIR.rglob("*"))
print(f"  {LAYOUT_DIR}: {len(layout_files)} paths", flush=True)
if len(layout_files) == 0:
    print("WARN: layout model directory is empty", file=sys.stderr)

# ---------------------------------------------------------------------------
# 2. Docling table model (default: docling_tableformer uses docling-project/docling-models)
#    TableStructureModel._model_repo_folder = "docling-project--docling-models"
# ---------------------------------------------------------------------------
print("=== baking docling table model (docling-project/docling-models@v2.3.0) ===",
      flush=True)

TABLE_REPO = "docling-project/docling-models"
TABLE_DIR = artifacts / TABLE_REPO.replace("/", "--")
try:
    download_hf_model(repo_id=TABLE_REPO, local_dir=TABLE_DIR, revision="v2.3.0")
except Exception as e:
    print(f"ERROR: table model download failed: {e}", file=sys.stderr)
    sys.exit(1)

table_files = list(TABLE_DIR.rglob("*"))
print(f"  {TABLE_DIR}: {len(table_files)} paths", flush=True)
if len(table_files) == 0:
    print("WARN: table model directory is empty", file=sys.stderr)

# ---------------------------------------------------------------------------
# 3. RapidOCR paddle models (det / cls / rec)
#    Uses rapidocr's own download utility — pure HTTP fetch, no GPU required.
# ---------------------------------------------------------------------------
print("=== baking rapidocr paddle models ===", flush=True)

import yaml

rapidocr_pkg = pathlib.Path("/usr/local/lib/python3.10/dist-packages/rapidocr")
default_cfg_path = rapidocr_pkg / "config.yaml"

with open(default_cfg_path) as fh:
    cfg = yaml.safe_load(fh)

for section in ("Det", "Cls", "Rec"):
    cfg[section]["engine_type"] = "paddle"

with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
    yaml.dump(cfg, tmp)
    tmp_cfg = tmp.name

try:
    from rapidocr.utils.download_models import download_models
    download_models(tmp_cfg)
except Exception as e:
    print(f"ERROR: rapidocr paddle model download failed: {e}", file=sys.stderr)
    sys.exit(1)
finally:
    os.unlink(tmp_cfg)

models_dir = rapidocr_pkg / "models"
paddle_files = [f for f in models_dir.rglob("*") if f.suffix in (".pdmodel", ".pdiparams")]
print(f"  rapidocr paddle models: {len(paddle_files)} files", flush=True)
if len(paddle_files) == 0:
    print("WARN: no rapidocr paddle model files found", file=sys.stderr)

print("=== bake complete ===", flush=True)
