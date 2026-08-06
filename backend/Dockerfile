# CPU-only default image. For GPU builds, base off an image that bundles the
# CUDA/cuDNN runtimes (e.g. nvidia/cuda:12.4.0-runtime-ubuntu22.04) and install
# onnxruntime-gpu (see requirements-gpu.txt) instead of onnxruntime.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# OpenCV/InsightFace need these shared libs on a slim base.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Model weights are downloaded on first run at runtime (see models/ in
# .dockerignore) — mounting a cache volume keeps them across container rebuilds.
COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

# The gallery is rebuilt on startup; point DATA_DIR at a mounted volume in prod.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
