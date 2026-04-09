#!/usr/bin/env bash
# Run the OCR container in local mode (OCR_LOCAL_FILE + OCR_LOCAL_OUTPUT_DIR).
# Mounts the git repo at /work inside the container so paths are stable for Audit.
#
# Usage (from anywhere):
#   ./profiling/ocr-batch/container/run-local-smoke.sh
#   ./profiling/ocr-batch/container/run-local-smoke.sh --input profiling/ocr-batch/test-media/water-bill.jpg
#
# Requires: Docker, nvidia-container-toolkit, GPU; image ocr-docling-gpu:latest (docker build).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# container/ -> ocr-batch -> profiling -> repo root
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

IMAGE="${OCR_IMAGE:-ocr-docling-gpu:latest}"
INPUT_REL="${OCR_INPUT_REL:-profiling/ocr-batch/test-media/service-invoice.jpg}"
OUT_REL="${OCR_OUT_REL:-profiling/ocr-batch/smoke-out}"

usage() {
  cat <<EOF
Run OCR container local mode: mount repo at /work, set OCR_LOCAL_FILE and OCR_LOCAL_OUTPUT_DIR.

Usage: $(basename "$0") [options]

Options:
  --image NAME     Docker image (default: ocr-docling-gpu:latest, or \$OCR_IMAGE)
  --input REL      Path under repo to input image (default: $INPUT_REL)
  --out-dir REL    Path under repo for outputs (default: $OUT_REL)
  --dry-run        Print docker command and exit (no input file required)
  -h, --help       This help
EOF
}

DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) IMAGE="$2"; shift 2 ;;
    --input) INPUT_REL="$2"; shift 2 ;;
    --out-dir) OUT_REL="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

INPUT_HOST="$REPO_ROOT/$INPUT_REL"
OUT_HOST="$REPO_ROOT/$OUT_REL"

if [[ "$DRY_RUN" -eq 0 ]]; then
  if [[ ! -f "$INPUT_HOST" ]]; then
    echo "FAIL: input not found: $INPUT_HOST" >&2
    echo "Add media under profiling/ocr-batch/test-media/ (see ocr-batch.profile.md Apply — transfer test-media) or pass --input." >&2
    exit 1
  fi
  mkdir -p "$OUT_HOST"
fi

# Paths as seen inside the container (single mount of repo root)
OCR_LOCAL_FILE="/work/$INPUT_REL"
OCR_LOCAL_OUTPUT_DIR="/work/$OUT_REL"

cmd=(docker run --rm --gpus all
  -v "$REPO_ROOT:/work"
  -e "OCR_LOCAL_FILE=$OCR_LOCAL_FILE"
  -e "OCR_LOCAL_OUTPUT_DIR=$OCR_LOCAL_OUTPUT_DIR"
  "$IMAGE")

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '%q ' "${cmd[@]}"
  echo
  exit 0
fi

echo "Repo mount: $REPO_ROOT -> /work"
echo "OCR_LOCAL_FILE=$OCR_LOCAL_FILE"
echo "OCR_LOCAL_OUTPUT_DIR=$OCR_LOCAL_OUTPUT_DIR"
echo "Image: $IMAGE"
"${cmd[@]}"

stem="$(basename "$INPUT_HOST")"
stem="${stem%.*}"
echo "---"
echo "Check outputs (basename follows input stem: $stem):"
echo "  $OUT_HOST/${stem}.md"
echo "  $OUT_HOST/${stem}.json"
echo "  $OUT_HOST/${stem}.jpg (or original extension copied)"
