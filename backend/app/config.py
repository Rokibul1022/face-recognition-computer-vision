"""Application configuration.

All tunable knobs live here so they can be overridden with environment
variables instead of being hardcoded in the pipeline.
"""
from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no dependency). Real env vars always win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


BASE_DIR = Path(__file__).resolve().parent.parent
_load_dotenv(BASE_DIR / ".env")
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

# --- Agent pipeline ---------------------------------------------------------
# Local-first agent storage. When Supabase credentials are configured the code
# path is identical; only the Store backend swaps. See database/schema.sql for
# the drop-in Supabase/Postgres + pgvector schema.
DB_PATH = Path(os.getenv("FR_DB_PATH", BASE_DIR / "agent.db"))

# Long-term memory (FAISS index + metadata). Env-overridable so deployments can
# persist memory on a mounted volume (e.g. Render persistent disk).
MEMORY_INDEX_PATH = Path(os.getenv("FR_MEMORY_INDEX", BASE_DIR / "agent_memory.index"))
MEMORY_META_PATH = Path(os.getenv("FR_MEMORY_META", BASE_DIR / "agent_memory_meta.json"))

# Event queue size for the background agent worker; when full the CV push is
# dropped (logged) rather than blocking the ingestion endpoint.
EVENT_QUEUE_MAX = int(os.getenv("FR_EVENT_QUEUE_MAX", "1000"))

# Short-term memory TTL (seconds) for a "current incident" window per camera.
STM_TTL_SEC = int(os.getenv("FR_STM_TTL_SEC", "1800"))  # 30 min
# Dedupe window: same person_id on the same camera within N seconds collapses
# into the existing incident instead of spawning a new one.
EVENT_DEDUPE_SEC = int(os.getenv("FR_EVENT_DEDUPE_SEC", "60"))

# Severity classifier thresholds — the LLM only wakes up for ambiguous cases.
SEVERITY_LLM_AMBIGUOUS_MIN = float(os.getenv("FR_SEVERITY_LLM_MIN", "0.4"))
SEVERITY_LLM_AMBIGUOUS_MAX = float(os.getenv("FR_SEVERITY_LLM_MAX", "0.7"))

# Notification gating: severity >= WARNING AND confidence >= threshold notify.
NOTIFY_MIN_SEVERITY = int(os.getenv("FR_NOTIFY_MIN_SEVERITY", "2"))  # 0=INFO 1=WARNING 2=CRITICAL
NOTIFY_MIN_CONFIDENCE = float(os.getenv("FR_NOTIFY_MIN_CONFIDENCE", "0.7"))

# --- Optional LLM (reasoning / severity second pass / chat) ------------------
# All reasoning works deterministically with no key; setting an OpenAI-compatible
# key upgrades the Reasoning Agent, ambiguous severity cases, and chat.
LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("FR_LLM_MODEL", "gpt-4o-mini")

# Notification channels. Each is optional; un-configured channels log + no-op.
TELEGRAM_BOT_TOKEN = os.getenv("FR_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("FR_TELEGRAM_CHAT_ID", "")
SLACK_WEBHOOK_URL = os.getenv("FR_SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = os.getenv("FR_DISCORD_WEBHOOK_URL", "")
SMTP_HOST = os.getenv("FR_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("FR_SMTP_PORT", "587"))
SMTP_USER = os.getenv("FR_SMTP_USER", "")
SMTP_PASSWORD = os.getenv("FR_SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("FR_SMTP_FROM", "")
EMAIL_RECIPIENTS = [
    r.strip()
    for r in os.getenv("FR_EMAIL_RECIPIENTS", "").split(",")
    if r.strip()
]

# Agent worker: collects recent events for report generation.
REPORT_WINDOW_SEC = int(os.getenv("FR_REPORT_WINDOW_SEC", "86400"))  # 24h
