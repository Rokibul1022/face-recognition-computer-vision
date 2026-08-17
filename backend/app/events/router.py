"""CV ingestion endpoints: /events (POST push, GET list, GET single).

The heavy CV runs at the edge; this router only accepts structured events,
enqueues them for the agent pipeline, and serves history.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from typing import Any

from ..events.bus import EventBus
from ..db.store import AgentStore
from ..models import EventIn, EventOut

logger = logging.getLogger(__name__)


def build_events_router(store: AgentStore, bus: EventBus) -> APIRouter:
    router = APIRouter(prefix="/events", tags=["events"])

    @router.post("", response_model=EventOut)
    async def push_event(event: EventIn) -> EventOut:
        """CV pipeline pushes a new detected event; agent layer processes it async."""
        raw = event.model_dump(exclude_none=True)
        accepted = await bus.publish(raw)
        if not accepted:
            raise HTTPException(status_code=503, detail="Event queue full — retry later.")
        return _to_event_out(raw)

    @router.get("", response_model=list[EventOut])
    async def list_events(
        camera_id: str | None = Query(None),
        identity: str | None = Query(None),
        detection_type: str | None = Query(None),
        limit: int = Query(200, le=5000),
    ) -> list[EventOut]:
        rows = store.list_events(
            camera_id=camera_id,
            identity=identity,
            detection_type=detection_type,
            limit=limit,
        )
        return [_to_event_out(r) for r in rows]

    @router.get("/{event_id}", response_model=EventOut)
    async def get_event(event_id: str) -> EventOut:
        row = store.get_event(event_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Event not found.")
        return _to_event_out(row)

    return router


def _to_event_out(row: dict) -> EventOut:
    return EventOut(
        event_id=row.get("id") or row.get("event_id") or "",
        camera_id=row.get("camera_id") or "gate-1",
        track_id=row.get("track_id"),
        identity=row.get("identity_label") or row.get("identity") or "unknown",
        identity_confidence=row.get("identity_confidence") or 0.0,
        detection_type=row.get("detection_type") or "person",
        bbox=row.get("bbox") or [],
        duration_in_frame_sec=row.get("duration_in_frame_sec") or 0.0,
        timestamp=row.get("timestamp") or row.get("created_at") or "",
        snapshot_url=row.get("snapshot_url"),
    )
    return EventOut(
        event_id=row.get("id") or row.get("event_id") or "",
        camera_id=row.get("camera_id") or "gate-1",
        track_id=row.get("track_id"),
        identity=row.get("identity_label") or row.get("identity") or "unknown",
        identity_confidence=row.get("identity_confidence") or 0.0,
        detection_type=row.get("detection_type") or "person",
        bbox=row.get("bbox") or [],
        duration_in_frame_sec=row.get("duration_in_frame_sec") or 0.0,
        timestamp=row.get("timestamp") or row.get("created_at") or "",
        snapshot_url=row.get("snapshot_url"),
    )