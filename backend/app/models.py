"""Pydantic models matching the frontend API contract exactly."""
from __future__ import annotations

from pydantic import BaseModel


class MatchInfo(BaseModel):
    person_id: str
    score: float
    info: dict


class FaceResult(BaseModel):
    bbox: list[float]  # [x1, y1, x2, y2] in the input image's pixel coords
    landmarks: list[list[float]] = []
    match: MatchInfo | None = None
    matched: bool = False
    score: float = 0.0  # best similarity regardless of threshold


class RecognizeImageResponse(BaseModel):
    faces: list[FaceResult]
    processing_ms: float


class VideoTimelineEntry(BaseModel):
    frame_index: int
    timestamp: float  # seconds
    faces: list[FaceResult]


class RecognizeVideoResponse(BaseModel):
    timeline: list[VideoTimelineEntry]
    total_frames: int
    processed_frames: int
    processing_ms: float


class EnrollRequest(BaseModel):
    person_id: str
    name: str = ""
    nid: str = ""
    age: int = 0
    address: str = ""
    number: str = ""


class EnrollResponse(BaseModel):
    person_id: str
    photos: int
    embedded: bool
    gallery_size: int


class GalleryStatus(BaseModel):
    enrolled: list[str]
    size: int
