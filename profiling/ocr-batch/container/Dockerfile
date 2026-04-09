# CUDA runtime base + pip from requirements.txt. Host poke may use native Paddle; fat image carries deps via pip.
# Paddle's published GPU wheels expect libcudnn.so.8; *-cudnn*-runtime images that ship only
# cuDNN 9 (e.g. some 12.6 tags) break at inference with "cudnn_dso_handle should not be null".
FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Paddle's loader probes /usr/local/cuda/lib64/ for unversioned names; runtime
# images often ship only versioned SONAMEs.
RUN ln -sf /usr/lib/x86_64-linux-gnu/libcudnn.so.8 /usr/local/cuda/lib64/libcudnn.so \
    && ln -sf /usr/lib/x86_64-linux-gnu/libcudnn.so.8 /usr/local/cuda/lib64/libcudnn.so.8 \
    && ln -sf /usr/local/cuda/lib64/libcublas.so.12 /usr/local/cuda/lib64/libcublas.so \
    && ln -sf /usr/local/cuda/lib64/libcublasLt.so.12 /usr/local/cuda/lib64/libcublasLt.so

WORKDIR /app

RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt \
    && pip3 install --no-cache-dir \
        paddlepaddle-gpu==2.6.2 \
        -f https://www.paddlepaddle.org.cn/whl/linux/mkl/avx/stable.html

# Bake docling layout/table models and rapidocr paddle model weights at build time.
# Avoids per-invocation downloads in Batch (thousands of cold starts).
# Docling models land in /app/docling-models/ (subdirs: repo_id with / -> --).
# RapidOCR paddle models land inside the rapidocr package models/ dir.
# DOCLING_ARTIFACTS_PATH is set by bake-models.py at build time and by processor.py
# at runtime — not declared as ENV to avoid polluting the rapidocr OCR model resolver
# in docling 2.85+ which KeyErrors on _default_models["paddle"] when artifacts_path is set.
COPY bake-models.py /tmp/bake-models.py
RUN python3 /tmp/bake-models.py && rm /tmp/bake-models.py

COPY processor.py .

ENTRYPOINT ["python3", "processor.py"]
