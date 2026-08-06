"""FAISS gallery matcher.

Holds an `IndexFlatIP` over L2-normalized ArcFace embeddings (inner product
over normalized vectors == cosine similarity) plus a parallel list mapping
index position -> person_id. The whole index + metadata can be cached to disk
and rebuilt from the person repository.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from . import config
from .repository import PersonRepository

logger = logging.getLogger(__name__)


class GalleryMatcher:
    def __init__(
        self,
        index_path: Path | None = None,
        meta_path: Path | None = None,
    ) -> None:
        self.index_path = Path(index_path or config.GALLERY_INDEX_PATH)
        self.meta_path = Path(meta_path or config.GALLERY_META_PATH)
        self._index = None  # lazily built faiss.IndexFlatIP
        self._ids: list[str] = []  # index position -> person_id
        self._people: dict[str, dict] = {}  # person_id -> info dict

    # --- build / cache -----------------------------------------------------
    def build_from_repo(self, repo: PersonRepository, force: bool = False) -> int:
        """Enroll every person in the repository into the FAISS index."""
        import faiss

        if self._index is not None and not force:
            return len(self._ids)

        ids: list[str] = []
        vectors: list[np.ndarray] = []
        people: dict[str, dict] = {}
        for person_id in repo.person_ids():
            person = repo.get(person_id)
            if person is None:
                continue
            emb = repo.average_embedding(person_id)
            if emb is None:
                logger.warning("No face found in enrollment photos for %s; skipping.", person_id)
                continue
            ids.append(person_id)
            vectors.append(emb)
            people[person_id] = person.info

        dim = vectors[0].shape[0] if vectors else 512
        index = faiss.IndexFlatIP(dim)
        if vectors:
            index.add(np.stack(vectors).astype("float32"))

        self._index = index
        self._ids = ids
        self._people = people
        self.save()
        logger.info("Enrolled %d person(s) into gallery.", len(ids))
        return len(ids)

    def load(self) -> bool:
        """Load index + metadata from disk if present."""
        import faiss

        if not self.index_path.exists() or not self.meta_path.exists():
            return False
        try:
            self._index = faiss.read_index(str(self.index_path))
            meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            self._ids = meta["ids"]
            self._people = meta["people"]
            logger.info("Loaded gallery from disk: %d person(s).", len(self._ids))
            return True
        except Exception as exc:
            logger.warning("Failed to load cached gallery (%s); will rebuild.", exc)
            return False

    def save(self) -> None:
        import faiss

        if self._index is None:
            return
        faiss.write_index(self._index, str(self.index_path))
        self.meta_path.write_text(
            json.dumps({"ids": self._ids, "people": self._people}, indent=2),
            encoding="utf-8",
        )
        logger.debug("Gallery cached to disk.")

    # --- matching ----------------------------------------------------------
    @property
    def ids(self) -> list[str]:
        return list(self._ids)

    def is_ready(self) -> bool:
        return self._index is not None and len(self._ids) > 0

    def ensure(self, repo: PersonRepository) -> None:
        """Load from cache or build from the repo, whichever is available."""
        if self.is_ready():
            return
        if self.load():
            return
        self.build_from_repo(repo, force=True)

    def search(
        self,
        embedding: np.ndarray,
        threshold: float | None = None,
    ) -> tuple[str | None, float]:
        """Return (best person_id, cosine similarity). None if below threshold."""
        if not self.is_ready():
            return None, 0.0
        threshold = config.MATCH_THRESHOLD if threshold is None else threshold
        vec = np.ascontiguousarray(
            np.atleast_2d(embedding).astype("float32")
        )
        scores, idxs = self._index.search(vec, 1)
        score = float(scores[0][0])
        pos = int(idxs[0][0])
        if pos < 0 or score < threshold:
            return None, score
        return self._ids[pos], score

    def person_info(self, person_id: str) -> dict | None:
        return self._people.get(person_id)
