#!/usr/bin/env bash
# aws_train.sh — Hudson's Bay first-pass OWW training for hey_sara
#
# Run this on an AWS GPU instance (g4dn.xlarge or similar).
# Prerequisites: this script handles setup from a fresh Ubuntu + CUDA instance.
#
# Upload this entire hudsons-bay/ folder to the instance, then:
#   chmod +x aws_train.sh && ./aws_train.sh
#
# Output: hey_sara_output/hey_sara.onnx (copy back to Pi)
set -euo pipefail

echo "=== hey_sara OWW training — Hudson's Bay first pass ==="

# --- Fix DL AMI apt quirks ---
# The Deep Learning AMI ships duplicate NVIDIA CUDA sources and a wildcard
# apt pin (Priority: 600) that covers ALL packages. This breaks dependency
# resolution for anything with a deep dep tree (e.g. ffmpeg).
# Fix: remove the duplicate source, and scope the pin to NVIDIA packages only.
if [ -f /etc/apt/sources.list.d/archive_uri-https_developer_download_nvidia_com_compute_cuda_repos_ubuntu2204_x86_64_-jammy.list ]; then
    sudo rm /etc/apt/sources.list.d/archive_uri-https_developer_download_nvidia_com_compute_cuda_repos_ubuntu2204_x86_64_-jammy.list
    echo "Removed duplicate NVIDIA apt source"
fi
for f in /etc/apt/preferences.d/*; do
    if grep -q 'Pin: release l=NVIDIA CUDA' "$f" && grep -q 'Package: \*' "$f"; then
        sudo sed -i 's/^Package: \*$/Package: cuda* libnv* libnccl* libcub* nvidia* tensorrt*/' "$f"
        echo "Scoped NVIDIA apt pin in $f to NVIDIA packages only"
    fi
done

# --- System deps ---
sudo apt-get update -qq
# DL AMI minimal Python lacks ensurepip; venv creation fails without this
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git ffmpeg libsndfile1 python3-venv

# --- Python environment ---
# OWW training requires Python 3.10 or 3.11 (PyTorch 1.13.1 compat)
if ! command -v python3.11 &> /dev/null && ! command -v python3.10 &> /dev/null; then
    echo "ERROR: Need Python 3.10 or 3.11. Install with deadsnakes PPA or use a suitable AMI."
    exit 1
fi
PYTHON=$(command -v python3.11 || command -v python3.10)
echo "Using: $PYTHON ($($PYTHON --version))"

$PYTHON -m venv venv
source venv/bin/activate

pip install --upgrade pip setuptools wheel

# --- Clone OWW and piper-sample-generator ---
if [ ! -d "openwakeword" ]; then
    git clone https://github.com/dscripka/openWakeWord.git openwakeword
fi

if [ ! -d "piper-sample-generator" ]; then
    git clone https://github.com/dscripka/piper-sample-generator.git
fi

# --- Install OWW training deps ---
cd openwakeword
pip install -e ".[full]"
cd ..
# PyTorch 1.13 + torchmetrics wheels expect NumPy 1.x; pip may pull NumPy 2.x otherwise
pip install "numpy<2"

# --- Download training data ---
# False-positive validation features (~185 MB on HF; filename is validation_set_features.npy)
if [ ! -f "validation_set_features.npy" ]; then
    echo "Downloading false-positive validation features..."
    pip install huggingface_hub
    python -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='davidscripka/openwakeword_features',
    filename='validation_set_features.npy',
    repo_type='dataset',
    local_dir='.',
)
"
fi

# Negative feature data (ACAV100M sample)
if [ ! -f "openwakeword_features_ACAV100M_2000_hrs_16bit.npy" ]; then
    echo "Downloading ACAV100M negative features..."
    python -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='davidscripka/openwakeword_features',
    filename='openwakeword_features_ACAV100M_2000_hrs_16bit.npy',
    repo_type='dataset',
    local_dir='.',
)
"
fi

# MIT Room Impulse Responses
if [ ! -d "mit_rirs" ]; then
    echo "Downloading MIT RIRs..."
    mkdir -p mit_rirs
    # OWW expects WAV files in this dir; the training notebook downloads them
    # from a specific source. For Hudson's Bay, we skip RIRs if download fails.
    echo "WARNING: MIT RIR download not automated yet — training will proceed without RIRs"
fi

# Background audio clips
if [ ! -d "background_clips" ]; then
    echo "Creating minimal background clips dir..."
    mkdir -p background_clips
    # Generate 60s of silence as minimal placeholder
    ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 60 -c:a pcm_s16le background_clips/silence.wav -y 2>/dev/null
fi

# --- Inject any Cartesia/ElevenLabs samples from Pi ---
# If samples/ dir exists (uploaded from Pi), copy WAVs into positive training data
if [ -d "samples" ] && [ "$(ls -A samples/ 2>/dev/null)" ]; then
    echo "Found pre-generated TTS samples — will be available for future integration"
fi

# --- Run training ---
# Stay in hudsons-bay root: hey_sara_model.yml paths (piper-sample-generator, *.npy, clips) are relative to cwd.
echo ""
echo "=== Starting OWW training pipeline ==="
echo ""

python -m openwakeword.train \
    --training_config hey_sara_model.yml \
    --generate_clips \
    --augment_clips \
    --train_model

echo ""
echo "=== Training complete ==="

# --- Collect output ---
# output_dir in yaml is ./hey_sara_output; ONNX is <output_dir>/<model_name>.onnx
if [ -f "hey_sara_output/hey_sara.onnx" ]; then
    cp hey_sara_output/hey_sara.onnx .
    echo "SUCCESS: hey_sara.onnx ready ($(wc -c < hey_sara.onnx) bytes)"
    echo "Copy this file back to Pi: scp hey_sara.onnx voice@<pi-ip>:~/sara/hudsons-bay/model/"
else
    echo "ERROR: hey_sara.onnx not found in output dir"
    echo "Check hey_sara_output/ for partial results"
    ls -la hey_sara_output/ 2>/dev/null || true
fi
