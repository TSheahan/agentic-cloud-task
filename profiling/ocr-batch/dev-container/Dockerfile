FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# PyTorch with CUDA — install before docling so rapidocr-torch finds it.
# Index URL must match the CUDA major.minor in the base image; cu124 is
# backward-compatible with the 12.6 runtime but verify at build time.
RUN pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu124

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY processor.py .

ENTRYPOINT ["python3", "processor.py"]
