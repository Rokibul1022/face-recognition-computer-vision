"""Short-term memory: in-process TTL cache for the active incident window.

Answers the "is this the same loitering event I saw 3 minutes ago?" question
the Reasoning Agent needs. Values expire after a configurable idle period.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from .. import config


class ShortTermMemory:
    """Thread-safe TTL key/value store with lazy expiration and pruning."""

    def __init__(self, ttl_sec: int | None = None) -> None:
        self._ttl = ttl_sec if ttl_sec is not None else config.STM_TTL_SEC
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def put(self, key: str, value: Any, ttl_sec: int | None = None) -> None:
        expires = time.monotonic() + (ttl_sec if ttl_sec is not None else self._ttl)
        with self._lock:
            self._data[key] = (expires, value)

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if expires < now:
                del self._data[key]
                return None
            return value

    def pop(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            item = self._data.pop(key, None)
            if item is None or item[0] < now:
                return None
            return item[1]

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def keys(self) -> list[str]:
        now = time.monotonic()
        with self._lock:
            return [k for k, (exp, _) in self._data.items() if exp >= now]

    def prune(self) -> int:
        """Drop expired entries; returns the number removed."""
        now = time.monotonic()
        removed = 0
        with self._lock:
            expired = [k for k, (exp, _) in self._data.items() if exp < now]
            for k in expired:
                del self._data[k]
                removed += 1
        return removed

    def size(self) -> int:
        return len(self.keys())

    # --- domain helpers ------------------------------------------------------
    def note_event(self, camera_id: str, identity: str, event_id: str) -> None:
        """Record that an event for this camera+identity just fired."""
        key = f"event:{camera_id}:{identity}"
        existing = self.get(key)
        recent: list[str] = list(existing or [])
        recent.append(event_id)
        self.put(key, recent[-10:])

    def recent_event_ids(self, camera_id: str, identity: str) -> list[str]:
        return list(self.get(f"event:{camera_id}:{identity}") or [])

    def note_seen(self, camera_id: str, identity: str, ttl_sec: int | None = None) -> None:
        now = time.monotonic()
        with self._lock:
            self._data[f"seen:{camera_id}:{identity}"] = (
                now + (ttl_sec if ttl_sec is not None else config.EVENT_DEDUPE_SEC),
                now,
            )

    def recently_seen(self, camera_id: str, identity: str) -> bool:
        return self.get(f"seen:{camera_id}:{identity}") is not None


# Module-level singleton shared across the pipeline.
default_short_term = ShortTermMemory()