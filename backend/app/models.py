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


class FaceDetail(BaseModel):
    person_id: str
    name: str = ""
    nid: str = ""
    age: int = 0
    address: str = ""
    number: str = ""
    photo_url: str | None = None


class FaceUpdate(BaseModel):
    name: str = ""
    nid: str = ""
    age: int = 0
    address: str = ""
    number: str = ""


# --- Agent layer -------------------------------------------------------------

class EventIn(BaseModel):
    """Structured event pushed by the CV pipeline (see README event schema)."""

    event_id: str | None = None
    camera_id: str = "gate-1"
    track_id: int | None = None
    identity: str = "unknown"
    identity_confidence: float = 0.0
    detection_type: str = "person"
    bbox: list[float] = []
    duration_in_frame_sec: float = 0.0
    timestamp: str | None = None
    snapshot_url: str | None = None


class EventOut(BaseModel):
    event_id: str
    camera_id: str
    track_id: int | None = None
    identity: str
    identity_confidence: float
    detection_type: str
    bbox: list[float]
    duration_in_frame_sec: float
    timestamp: str
    snapshot_url: str | None = None


class Decision(BaseModel):
    action: str  # notify | log_only | ignore | escalate
    severity: str  # INFO | WARNING | CRITICAL
    reasoning: str
    reference_incident_id: str | None = None


class IncidentOut(BaseModel):
    id: str
    event_id: str | None = None
    severity: str
    action: str
    reasoning: str
    reference_incident_id: str | None = None
    resolved: bool
    created_at: str


class AlertIn(BaseModel):
    message: str
    severity: str = "WARNING"
    channels: list[str] = []


class ChatIn(BaseModel):
    message: str


class ChatOut(BaseModel):
    reply: str
    references: list[dict] = []


class SummaryOut(BaseModel):
    generated_at: str
    window_seconds: int
    total_events: int
    incidents: list[dict]
    by_severity: dict[str, int]
    top_reference_incident_id: str | None = None


class IncidentReport(BaseModel):
    id: str
    incident_id: str
    format: str
    summary: str
    created_at: str
