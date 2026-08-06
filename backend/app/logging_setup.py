"""Structured logging: JSON-ish lines with a request id and stage timings."""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from . import config

# Request-scoped correlation id, set by middleware for each HTTP/WS request.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class StructFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "message": record.getMessage(),
        }
        extra = getattr(record, "data", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructFormatter())
    root.addHandler(handler)
    root.setLevel(config.LOG_LEVEL)
    # Quiet the noisy insightface/onnxruntime model prints.
    logging.getLogger("insightface").setLevel(logging.WARNING)
    logging.getLogger("onnxruntime").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)
