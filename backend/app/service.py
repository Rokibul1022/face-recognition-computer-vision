"""Recognition service: ties the detector + matcher together per request."""
from __future__ import annotations

import logging
import time

import numpy as np

from .detector import DetectedFace, detect_faces
from .matcher import GalleryMatcher
from .models import FaceResult, MatchInfo
from .repository import PersonRepository

logger = logging.getLogger(__name__)


def _face_to_result(face: DetectedFace, matcher: GalleryMatcher) -> FaceResult:
    if face.embedding is None:
        return FaceResult(bbox=face.bbox, landmarks=face.landmarks)

    person_id, score = matcher.search(face.embedding)
    result = FaceResult(
        bbox=face.bbox,
        landmarks=face.landmarks,
        score=round(score, 4),
        matched=person_id is not None,
    )
    if person_id is not None:
        info = matcher.person_info(person_id) or {}
        result.match = MatchInfo(
            person_id=person_id, score=round(score, 4), info=info
        )
    return result


class RecognitionService:
    def __init__(self, repo: PersonRepository, matcher: GalleryMatcher) -> None:
        self.repo = repo
        self.matcher = matcher

    def ensure_gallery(self) -> None:
        self.matcher.ensure(self.repo)

    def recognize_frame(self, frame_bgr: np.ndarray) -> tuple[list[FaceResult], dict]:
        """Detect + embed + match all faces in one frame.

        Returns (face_results, stage_timings_ms).
        """
        timings: dict[str, float] = {}
        t0 = time.perf_counter()
        faces = detect_faces(frame_bgr, embed=True)
        timings["detect"] = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        results = [_face_to_result(f, self.matcher) for f in faces]
        timings["match"] = (time.perf_counter() - t1) * 1000.0
        return results, timings
