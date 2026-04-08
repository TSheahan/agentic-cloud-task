### 1. Dockerfile (optimized for AWS Batch + g4dn T4 GPU)
Use the official NVIDIA CUDA runtime base (matches the drivers in the ECS GPU-optimized AMI). The container stays lightweight because the heavy GPU drivers live in your AMI.

```dockerfile
FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04

# System dependencies
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

# Copy and install Python deps (including Docling + RapidOCR Paddle backend)
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Your processor script
COPY processor.py .

# Batch will override the command with S3 input/output paths
ENTRYPOINT ["python3", "processor.py"]
```

**requirements.txt** (this is the minimal set that gives you Docling + GPU PaddleOCR):

```plain
docling>=2.0.0
rapidocr-paddle>=1.3.0
boto3
pydantic
```

(If you need extra Docling features like VLM models or formula recognition, add `docling[full]` or `docling[vlm]`.)

### 2. Processor Script (processor.py)
This is the exact script your Batch job will run. It:
- Downloads the input file from S3
- Runs Docling with GPU-accelerated RapidOCR (PaddleOCR models)
- Writes structured Markdown + JSON output
- Uploads results + a completion artifact back to S3
- Exits cleanly (Batch marks job `SUCCEEDED`)

```python
import sys
import boto3
import tempfile
from pathlib import Path
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    RapidOcrOptions,
    AcceleratorOptions,
    AcceleratorDevice,
)
from docling.datamodel.base import InputFormat

s3 = boto3.client("s3")

def main():
    if len(sys.argv) < 3:
        print("Usage: processor.py <input_s3_uri> <output_s3_prefix>")
        sys.exit(1)

    input_s3_uri = sys.argv[1]   # e.g. s3://my-bucket/incoming/file123.pdf
    output_prefix = sys.argv[2]  # e.g. s3://my-bucket/processed/file123/

    # Parse S3 URIs
    bucket_in, key_in = input_s3_uri.replace("s3://", "").split("/", 1)
    bucket_out = output_prefix.replace("s3://", "").split("/")[0]
    prefix_out = output_prefix.replace(f"s3://{bucket_out}/", "")

    with tempfile.TemporaryDirectory() as tmpdir:
        local_in = Path(tmpdir) / Path(key_in).name
        local_md = Path(tmpdir) / (Path(key_in).stem + ".md")
        local_json = Path(tmpdir) / (Path(key_in).stem + ".json")
        artifact = Path(tmpdir) / "COMPLETED"

        # Download input
        s3.download_file(bucket_in, key_in, str(local_in))

        # GPU-accelerated Docling + RapidOCR (PaddleOCR backend)
        pipeline_options = PdfPipelineOptions(
            do_ocr=True,
            ocr_options=RapidOcrOptions(
                use_gpu=True,                    # forces CUDA
                det_model_path=None,             # uses default Paddle models
                rec_model_path=None,
            ),
            accelerator_options=AcceleratorOptions(
                device=AcceleratorDevice.CUDA,
                num_threads=4,
            ),
        )

        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            pipeline_options=pipeline_options,
        )

        result = converter.convert(str(local_in))

        # Save outputs
        result.document.export_to_markdown(local_md)
        result.document.export_to_dict(local_json)   # or .export_to_json() if you prefer

        # Upload results
        s3.upload_file(str(local_md), bucket_out, f"{prefix_out}result.md")
        s3.upload_file(str(local_json), bucket_out, f"{prefix_out}result.json")

        # Completion artifact (your controller polls for this)
        artifact.touch()
        s3.upload_file(str(artifact), bucket_out, f"{prefix_out}COMPLETED")

    print(f"✅ OCR complete → {output_prefix}")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### 3. Build & Push the Container
```bash
# From your project directory (with Dockerfile + requirements.txt + processor.py)
aws ecr create-repository --repository-name ocr-docling-gpu --region <your-region> || true

docker build -t ocr-docling-gpu:latest .
docker tag ocr-docling-gpu:latest <your-account>.dkr.ecr.<region>.amazonaws.com/ocr-docling-gpu:latest

aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <your-account>.dkr.ecr.<region>.amazonaws.com
docker push <your-account>.dkr.ecr.<region>.amazonaws.com/ocr-docling-gpu:latest
```
