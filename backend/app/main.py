"""FastAPI application: enrollment, image/video recognition, live WebSocket.

Run:
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import time
import uuid

import cv2
import numpy as np
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from . import config
from .logging_setup import request_id_var, setup_logging
from .matcher import GalleryMatcher
from .models import (
    EnrollResponse,
    GalleryStatus,
    RecognizeImageResponse,
    RecognizeVideoResponse,
    VideoTimelineEntry,
)
from .repository import PersonRepository
from .service import RecognitionService
from .validation import sniff_image

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Face Recognition System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    # Credentials can't be combined with a wildcard origin; we don't use
    # cookies/auth so disable them when origins are open.
    allow_credentials="*" not in config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

repo = PersonRepository()
matcher = GalleryMatcher()
service = RecognitionService(repo, matcher)


@app.middleware("http")
async def request_id_middleware(request, call_next):
    rid = uuid.uuid4().hex[:8]
    token = request_id_var.set(rid)
    try:
        return await call_next(request)
    finally:
        request_id_var.reset(token)


@app.on_event("startup")
async def _startup() -> None:
    service.ensure_gallery()


# --------------------------------------------------------------------------
# Enroll
# --------------------------------------------------------------------------
@app.post("/enroll", response_model=EnrollResponse)
async def enroll(
    image: UploadFile = File(...),
    person_id: str = Form(...),
    name: str = Form(""),
    nid: str = Form(""),
    age: int = Form(0),
    address: str = Form(""),
    number: str = Form(""),
) -> EnrollResponse:
    person_id = person_id.strip().lower()
    if not person_id:
        raise HTTPException(status_code=400, detail="person_id is required.")

    data, _fmt = sniff_image(image)
    png_bytes = _reencode_png(data)

    info = {"name": name, "nid": nid, "age": age, "address": address, "number": number}
    repo.save_photo(person_id, png_bytes)
    repo.save_meta(person_id, info)

    emb = repo.average_embedding(person_id)
    embedded = emb is not None
    # Rebuild index (cheap at this scale) so the new person is matchable.
    n = matcher.build_from_repo(repo, force=True)

    logger.info(
        "Enrolled person_id=%s embedded=%s gallery=%d",
        person_id,
        embedded,
        n,
    )
    return EnrollResponse(
        person_id=person_id,
        photos=len(repo.photo_paths(person_id)),
        embedded=embedded,
        gallery_size=n,
    )


def _reencode_png(data: bytes) -> bytes:
    """Re-encode any validated image as PNG for storage."""
    import numpy as np
    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        rgb = img.convert("RGB")
        arr = np.asarray(rgb)
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        raise HTTPException(status_code=400, detail="Could not store image.")
    return buf.tobytes()


# --------------------------------------------------------------------------
# Recognize
# --------------------------------------------------------------------------
@app.post("/recognize/image", response_model=RecognizeImageResponse)
async def recognize_image(image: UploadFile = File(...)) -> RecognizeImageResponse:
    t0 = time.perf_counter()
    data, _fmt = sniff_image(image)
    frame = _decode_to_bgr(data)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode image bytes.")

    faces, timings = service.recognize_frame(frame)
    processing_ms = (time.perf_counter() - t0) * 1000.0
    logger.info(
        "recognize/image faces=%d total_ms=%.1f",
        len(faces),
        processing_ms,
        extra={"data": {"stages_ms": {k: round(v, 1) for k, v in timings.items()}}},
    )
    return RecognizeImageResponse(faces=faces, processing_ms=round(processing_ms, 2))


@app.post("/recognize/video", response_model=RecognizeVideoResponse)
async def recognize_video(
    video: UploadFile = File(...),
    sample_every: int = Form(config.VIDEO_SAMPLE_EVERY),
) -> RecognizeVideoResponse:
    if not (video.filename or "").lower().endswith((".mp4", ".avi", ".mov", ".mkv", ".webm")):
        raise HTTPException(
            status_code=415,
            detail="Unsupported video type. Allowed: .mp4, .avi, .mov, .mkv, .webm",
        )
    sample_every = max(1, sample_every)
    raw = video.file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload.")

    t0 = time.perf_counter()
    # cv2.VideoCapture can't reliably open an in-memory buffer on all platforms;
    # spool to a temp file and let the OS file backend handle it.
    import tempfile

    tmp = tempfile.NamedTemporaryFile(
        suffix=Path(video.filename or "video.mp4").suffix, delete=False
    )
    try:
        tmp.write(raw)
        tmp.flush()
        tmp.close()
        cap = cv2.VideoCapture(tmp.name)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not decode video.")

        timeline: list[VideoTimelineEntry] = []
        idx = 0
        total = 0
        processed = 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                total += 1
                if idx % sample_every != 0:
                    idx += 1
                    continue
                faces, _ = service.recognize_frame(frame)
                timeline.append(
                    VideoTimelineEntry(
                        frame_index=idx,
                        timestamp=round(idx / fps, 3),
                        faces=faces,
                    )
                )
                processed += 1
                idx += 1
        finally:
            cap.release()
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    processing_ms = (time.perf_counter() - t0) * 1000.0
    logger.info(
        "recognize/video total=%d processed=%d ms=%.1f",
        total,
        processed,
        processing_ms,
    )
    return RecognizeVideoResponse(
        timeline=timeline,
        total_frames=total,
        processed_frames=processed,
        processing_ms=round(processing_ms, 2),
    )


# --------------------------------------------------------------------------
# WebSocket live scan
# --------------------------------------------------------------------------
@app.websocket("/ws/recognize")
async def ws_recognize(websocket: WebSocket) -> None:
    """Live webcam mode. Client sends base64 JPEG frames; we reply per-frame.

    Message in (text):   {"frame": "<base64-jpeg>"}
    Message out (text):  {"faces": [...], "processing_ms": 84}
    If the client is slower than the server, outbound messages are dropped
    (only the latest result is kept) so we never build an unbounded queue.
    """
    await websocket.accept()
    rid = uuid.uuid4().hex[:8]
    token = request_id_var.set(rid)
    logger.info("ws/recognize connected id=%s", rid)
    try:
        latest: dict | None = None
        while True:
            msg = await websocket.receive_text()
            try:
                payload = _parse_ws_frame(msg)
            except ValueError as exc:
                await websocket.send_json({"error": str(exc)})
                continue

            t0 = time.perf_counter()
            faces, _timings = await asyncio.to_thread(service.recognize_frame, payload)
            latest = {
                "faces": [f.model_dump() for f in faces],
                "processing_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }
            try:
                await websocket.send_json(latest)
            except Exception:
                pass
    except WebSocketDisconnect:
        logger.info("ws/recognize disconnected id=%s", rid)
    finally:
        request_id_var.reset(token)


def _parse_ws_frame(msg: str) -> np.ndarray:
    """Decode a {'frame': '<base64-jpeg>'} message into a BGR frame."""
    try:
        import json

        payload = json.loads(msg)
        raw = payload["frame"]
        if isinstance(raw, str) and raw.startswith("data:"):
            raw = raw.split(",", 1)[1]
        jpg = base64.b64decode(raw)
    except Exception as exc:
        raise ValueError("Malformed frame payload.") from exc
    frame = _decode_to_bgr(jpg)
    if frame is None:
        raise ValueError("Could not decode frame as JPEG.")
    return frame


def _decode_to_bgr(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return frame


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------
@app.get("/gallery", response_model=GalleryStatus)
async def gallery_status() -> GalleryStatus:
    service.ensure_gallery()
    return GalleryStatus(enrolled=matcher.ids, size=len(matcher.ids))


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "gallery_size": len(matcher.ids) if matcher.is_ready() else 0}
