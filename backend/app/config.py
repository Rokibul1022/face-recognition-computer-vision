"""Application configuration.

All tunable knobs live here so they can be overridden with environment
variables instead of being hardcoded in the pipeline.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Paths ----------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("FR_DATA_DIR", BASE_DIR / "data"))
GALLERY_INDEX_PATH = Path(
    os.getenv("FR_GALLERY_INDEX", BASE_DIR / "gallery.index")
)
GALLERY_META_PATH = Path(
    os.getenv("FR_GALLERY_META", BASE_DIR / "gallery_meta.json")
)

# --- Model ----------------------------------------------------------------
MODEL_PACK = os.getenv("FR_MODEL_PACK", "buffalo_l")
# InsightFace models are downloaded into this directory on first use.
MODELS_DIR = Path(os.getenv("FR_MODELS_DIR", BASE_DIR / "models"))

# --- Detection ------------------------------------------------------------
DETECTOR_CONF_THRESHOLD = float(os.getenv("FR_DETECT_THRESHOLD", "0.5"))
DETECTOR_MAX_NUM = int(os.getenv("FR_DETECT_MAX_NUM", "10"))
# Keep aligned faces out of the equation for now; a single aligned crop per
# detected face is all the matcher needs.
FACE_SIZE = int(os.getenv("FR_FACE_SIZE", "112"))

# --- Matching -------------------------------------------------------------
# Cosine-similarity threshold. ArcFace embeddings are L2-normalized and scored
# with inner product, so this is the cosine similarity. Tune with
# `scripts/threshold_tuning.py`.
MATCH_THRESHOLD = float(os.getenv("FR_MATCH_THRESHOLD", "0.45"))

# --- Video ----------------------------------------------------------------
VIDEO_SAMPLE_EVERY = int(os.getenv("FR_VIDEO_SAMPLE_EVERY", "5"))  # every Nth frame

# --- WebSocket ------------------------------------------------------------
WS_MAX_QUEUE = int(os.getenv("FR_WS_MAX_QUEUE", "4"))  # drop old frames when backed up

# --- CORS -----------------------------------------------------------------
# "*" = allow any origin (fine for local dev/test). Restrict to explicit
# origins before deploying (FR_CORS_ORIGINS=http://localhost:5173).
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "FR_CORS_ORIGINS",
        "*",
    ).split(",")
    if o.strip()
]

# --- Misc -----------------------------------------------------------------
MAX_UPLOAD_MB = int(os.getenv("FR_MAX_UPLOAD_MB", "50"))
LOG_LEVEL = os.getenv("FR_LOG_LEVEL", "INFO").upper()

# Directory containing CUDA runtime DLLs (cublasLt64_12.dll, cudnn64_9.dll...).
# Set this when onnxruntime-gpu cannot find its CUDA libraries. If unset, the
# app attempts to locate a PyTorch CUDA install automatically.
CUDA_LIB_DIR = os.getenv("FR_CUDA_LIB_DIR", "")
