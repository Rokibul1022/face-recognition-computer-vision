"""Flat-file person repository.

This module owns *where* enrolled people live on disk:
    data/{person_id}.png   -> the enrollment photo(s)
    data/{person_id}.json  -> {name, nid, age, address, number}

The rest of the pipeline (detector, matcher, service) talks to this class only
through the `PersonRepository` interface, so swapping flat files for Postgres
later is a one-file change.

NOTE: single-photo galleries are the main cause of false negatives. `add_images`
accepts multiple photos per person and averages their embeddings at enrollment
time — prefer at least 2–3 photos per person.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import config
from .detector import detect_faces

logger = logging.getLogger(__name__)

PERSON_META_FIELDS = ("name", "nid", "age", "address", "number")


@dataclass
class Person:
    person_id: str
    name: str
    nid: str
    age: int
    address: str
    number: str

    @property
    def info(self) -> dict:
        return {
            "name": self.name,
            "nid": self.nid,
            "age": self.age,
            "address": self.address,
            "number": self.number,
        }

    @classmethod
    def from_dict(cls, person_id: str, d: dict) -> "Person":
        return cls(
            person_id=person_id,
            name=str(d.get("name", person_id)),
            nid=str(d.get("nid", "")),
            age=int(d.get("age", 0) or 0),
            address=str(d.get("address", "")),
            number=str(d.get("number", "")),
        )


class PersonRepository:
    """Flat-file implementation of the person store."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = Path(data_dir or config.DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # --- discovery ---------------------------------------------------------
    def person_ids(self) -> list[str]:
        return sorted(
            p.stem
            for p in self.data_dir.glob("*.json")
            if not p.name.startswith(".")
        )

    def get(self, person_id: str) -> Person | None:
        meta_path = self.data_dir / f"{person_id}.json"
        if not meta_path.exists():
            return None
        try:
            d = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Unreadable metadata for %s: %s", person_id, exc)
            return None
        return Person.from_dict(person_id, d)

    def photo_paths(self, person_id: str) -> list[Path]:
        """All enrollment photos for a person (png/jpg/jpeg)."""
        return sorted(
            p
            for ext in (".png", ".jpg", ".jpeg")
            for p in self.data_dir.glob(f"{person_id}{ext}")
        )

    def save_photo(self, person_id: str, png_bytes: bytes) -> Path:
        """Persist an uploaded enrollment photo as data/{person_id}.png."""
        path = self.data_dir / f"{person_id}.png"
        path.write_bytes(png_bytes)
        return path

    def save_meta(self, person_id: str, info: dict) -> None:
        path = self.data_dir / f"{person_id}.json"
        path.write_text(
            json.dumps({k: info.get(k) for k in PERSON_META_FIELDS}, indent=2),
            encoding="utf-8",
        )

    # --- enrollment helpers ------------------------------------------------
    def average_embedding(self, person_id: str) -> np.ndarray | None:
        """Average the embeddings across all enrollment photos of a person.

        Averaging mitigates the classic single-photo false-negative problem:
        a photo is only a snapshot of one pose/lighting, while the gallery
        vector ideally represents the person in general.
        """
        embeddings: list[np.ndarray] = []
        for path in self.photo_paths(person_id):
            embeddings.extend(self._embeddings_from_file(path))
        if not embeddings:
            return None
        mean = np.mean(np.stack(embeddings), axis=0)
        norm = float(np.linalg.norm(mean))
        return mean / norm if norm > 0 else None

    def _embeddings_from_file(self, path: Path) -> list[np.ndarray]:
        import cv2

        frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if frame is None:
            logger.warning("Could not decode photo %s", path)
            return []
        faces = detect_faces(frame, embed=True)
        return [f.embedding for f in faces if f.embedding is not None]
