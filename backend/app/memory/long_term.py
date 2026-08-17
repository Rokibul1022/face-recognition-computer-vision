"""Long-term memory: FAISS vector store over event descriptions.

Emulates the pgvector `event_embeddings` table locally. Without pulling in a
text-embedding model we use a deterministic hashed character n-gram embedder
over a configurable dim (default 256); identical text maps to identical vectors
so "has this pattern appeared before?" retrievals are stable across restarts.
Swap `TextEmbedder` for a real embedding model (or pgvector) without touching
the search API.
"""
from __future__ import annotations

import hashlib
import logging
import math
import threading
from pathlib import Path

import numpy as np

from .. import config

logger = logging.getLogger(__name__)

_DEFAULT_DIM = 256


def _hash_vec(text: str, dim: int) -> np.ndarray:
    """Deterministic dense unit vector from sliding character n-grams."""
    vec = np.zeros(dim, dtype="float32")
    t = text.lower()
    grams = [t[i : i + 3] for i in range(max(len(t) - 2, 1))]
    for g in grams:
        h = int(hashlib.md5(g.encode("utf-8")).hexdigest()[:8], 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


class TextEmbedder:
    """Minimal deterministic embedder used for long-term memory retrieval."""

    def __init__(self, dim: int = _DEFAULT_DIM) -> None:
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        return _hash_vec(text, self.dim)


class LongTermMemory:
    """FAISS IndexFlatIP (cosine over L2-normalized vectors) + metadata list.

    Persisted to disk like the gallery matcher so history survives restarts.
    """

    def __init__(
        self,
        index_path: Path | None = None,
        meta_path: Path | None = None,
        embedder: TextEmbedder | None = None,
        max_entries: int | None = None,
    ) -> None:
        self.index_path = Path(index_path or config.MEMORY_INDEX_PATH)
        self.meta_path = Path(meta_path or config.MEMORY_META_PATH)
        self.embedder = embedder or TextEmbedder()
        self.max_entries = int(max_entries or config.MEMORY_MAX_ENTRIES)
        self._index = None
        self._meta: list[dict] = []  # position -> {"event_id", "description", ...}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        try:
            import faiss

            if self.index_path.exists() and self.meta_path.exists():
                import json

                self._index = faiss.read_index(str(self.index_path))
                self._meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
                logger.info("Loaded long-term memory: %d entries.", len(self._meta))
        except Exception as exc:
            logger.warning("Could not load long-term memory (%s); starting empty.", exc)
            self._index = None
            self._meta = []

    def _ensure_index(self) -> None:
        if self._index is None:
            import faiss

            self._index = faiss.IndexFlatIP(self.embedder.dim)

    def _save(self) -> None:
        try:
            import faiss
            import json

            if self._index is None:
                return
            faiss.write_index(self._index, str(self.index_path))
            self.meta_path.write_text(
                json.dumps(self._meta, indent=2), encoding="utf-8"
            )
        except Exception:
            pass  # memory is a cache; failure to persist is non-fatal

    def add(self, description: str, event_id: str, **extra: object) -> None:
        vec = np.atleast_2d(self.embedder.embed(description)).astype("float32")
        with self._lock:
            self._ensure_index()
            self._index.add(vec)
            self._meta.append({"event_id": event_id, "description": description, **extra})
            self._trim()
            self._save()

    def _trim(self) -> None:
        """Drop the oldest entries when the cap is exceeded (ring buffer)."""
        import faiss

        overflow = len(self._meta) - self.max_entries
        if overflow <= 0:
            return
        self._meta = self._meta[overflow:]
        # Rebuild the index from the remaining tail; cheaper and simpler than
        # renumbering IDs on the raw FAISS index.
        vecs = np.vstack(
            [self.embedder.embed(m["description"]) for m in self._meta]
        ).astype("float32")
        index = faiss.IndexFlatIP(self.embedder.dim)
        if len(vecs):
            index.add(vecs)
        self._index = index
        logger.info("Trimmed long-term memory to %d entries.", len(self._meta))

    def search(self, description: str, k: int = 5) -> list[dict]:
        """Top-k similar stored events with similarity scores."""
        with self._lock:
            if self._index is None or self._index.ntotal == 0:
                return []
            vec = np.atleast_2d(self.embedder.embed(description)).astype("float32")
            k = min(k, self._index.ntotal)
            scores, idxs = self._index.search(vec, k)
            results = []
            for i, pos in enumerate(idxs[0]):
                if pos < 0 or pos >= len(self._meta):
                    continue
                item = dict(self._meta[int(pos)])
                item["similarity"] = round(float(cosine_from_ip(scores[0][i])), 4)
                results.append(item)
            return results

    def size(self) -> int:
        return len(self._meta)

    def all(self) -> list[dict]:
        return list(self._meta)


def cosine_from_ip(ip: float) -> float:
    """Score used is raw inner product on normalized vectors ~ cosine."""
    return max(-1.0, min(1.0, float(ip)))


# Module-level singleton.
default_long_term = LongTermMemory()