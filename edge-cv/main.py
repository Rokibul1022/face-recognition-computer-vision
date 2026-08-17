"""Edge CV worker: captures a camera stream and pushes structured Events.

This is the on-prem piece of the AGENT.md architecture. It reuses the backend's
detector + matcher directly (they're importable — add `backend/` to sys.path or
run uvicorn from the repo root), recognizes faces, and POSTs an Event to the
FastAPI `/events` endpoint for the agent layer.

Run:
    python edge-cv/main.py --source 0            # webcam index 0
    python edge-cv/main.py --source rtsp://...   # RTSP camera
    python edge-cv/main.py --source demo.mp4     # local video file
    python edge-cv/main.py --source demo.mp4 --camera-id gate-1 --sample-every 10
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import urllib.request

# Expose the backend package so we can reuse detector/matcher/service.
BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.detector import detect_faces  # noqa: E402
from app.matcher import GalleryMatcher  # noqa: E402
from app.repository import PersonRepository  # noqa: E402

logger = logging.getLogger("edge-cv")


def _open_capture(source: str | int) -> cv2.VideoCapture:
    if isinstance(source, int) or source.isdigit():
        return cv2.VideoCapture(int(source))
    if str(source).startswith(("rtsp://", "http://", "https://", "rtmp://")):
        return cv2.VideoCapture(str(source))
    path = Path(source)
    if path.exists():
        return cv2.VideoCapture(str(path))
    raise SystemExit(f"Could not open source: {source}")


class EventClient:
    """Thin HTTP client for POST /events."""

    def __init__(self, backend_url: str) -> None:
        self.url = backend_url.rstrip("/") + "/events"

    def post(self, event: dict[str, Any]) -> bool:
        data = json.dumps(event).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                return res.status < 300
        except Exception as exc:
            logger.warning("Failed to push event: %s", exc)
            return False


def _snapshot_data_url(frame: np.ndarray) -> str | None:
    """Optional in-payload frame snapshot as a data URL (small JPEG)."""
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 40])
    if not ok:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def run() -> None:
    parser = argparse.ArgumentParser(description="Edge CV worker")
    parser.add_argument("--source", default="0", help="webcam index, RTSP URL, or video path")
    parser.add_argument("--backend", default="http://localhost:8000", help="FastAPI backend base URL")
    parser.add_argument("--camera-id", default="gate-1")
    parser.add_argument("--sample-every", type=int, default=10, help="process every Nth frame")
    parser.add_argument("--fps", type=float, default=1.0, help="max pushes per second")
    parser.add_argument("--zone", default="general")
    parser.add_argument("--snapshot", action="store_true", help="embed a JPEG snapshot data-URL in each event")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    repo = PersonRepository()
    matcher = GalleryMatcher()
    matcher.ensure(repo)

    cap = _open_capture(args.source)
    if not cap.isOpened():
        raise SystemExit("Could not open capture source.")

    client = EventClient(args.backend)
    frame_idx = 0
    min_interval = 1.0 / max(args.fps, 0.05)
    last_send = 0.0

    logger.info("Edge CV worker started (camera=%s, source=%s)", args.camera_id, args.source)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                logger.info("End of stream; waiting for more frames...")
                time.sleep(0.5)
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            frame_idx += 1
            if frame_idx % args.sample_every != 0:
                continue

            faces = detect_faces(frame, embed=True)
            for face in faces:
                person_id, score = None, 0.0
                if face.embedding is not None:
                    person_id, score = matcher.search(face.embedding)

                identity = person_id or "unknown"
                event = {
                    "event_id": str(uuid.uuid4()),
                    "camera_id": args.camera_id,
                    "zone": args.zone,
                    "track_id": None,
                    "identity": identity,
                    "identity_confidence": round(score, 4) if person_id else round(float(face.score), 4),
                    "detection_type": "person",
                    "bbox": [round(float(v), 1) for v in face.bbox],
                    "duration_in_frame_sec": round(1.0 / max(args.fps, 0.05), 2),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                if args.snapshot:
                    event["snapshot_url"] = _snapshot_data_url(frame)

                now = time.monotonic()
                if now - last_send >= min_interval:
                    if client.post(event):
                        last_send = now
                        logger.info("Pushed %s confidence=%.3f", identity, score if person_id else face.score)
                    else:
                        time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Stopping edge CV worker.")
    finally:
        cap.release()


if __name__ == "__main__":
    run()