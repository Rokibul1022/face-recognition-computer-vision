# Edge CV container: runs the capture → detect → recognize → POST /events loop.
# Reuses the backend Python package (mounted/a copy) for the detector + matcher.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Backend deps contain insightface + faiss + opencv; edge-cv reuses them.
COPY backend/requirements.txt /srv/backend/requirements.txt
RUN pip install --no-cache-dir -r /srv/backend/requirements.txt

COPY backend/app /srv/backend/app
COPY backend/scripts /srv/backend/scripts
COPY edge-cv /srv/edge-cv

WORKDIR /srv/edge-cv
CMD ["python", "main.py", \
     "--source", "${EDGE_SOURCE:-0}", \
     "--backend", "${EDGE_BACKEND:-http://backend:8000}", \
     "--camera-id", "${EDGE_CAMERA_ID:-gate-1}", \
     "--sample-every", "${EDGE_SAMPLE_EVERY:-10}", \
     "--fps", "${EDGE_FPS:-1}"]