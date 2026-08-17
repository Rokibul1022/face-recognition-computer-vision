"""Perception Agent: normalize raw CV events, resolve context, dedupe."""

from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PerceptionAgent:
    """Turns a raw CV event into a normalized, de-duplicated event record."""

    def __init__(self, store, short_term) -> None:
        self.store = store
        self.short_term = short_term

    def process(self, raw: dict) -> dict:
        """Normalize + persist the event; return the stored record.

        Dedupes: the same person_id on the same camera inside the dedupe window
        is tagged so downstream agents can merge into the existing incident.
        """
        ts = raw.get("timestamp") or _now_iso()
        identity = str(raw.get("identity") or "unknown").lower()
        camera_id = str(raw.get("camera_id") or "gate-1")
        confidence = float(raw.get("identity_confidence") or 0.0)

        event = {
            "id": raw.get("event_id"),
            "camera_id": camera_id,
            "track_id": raw.get("track_id"),
            "identity_label": identity,
            "identity_confidence": confidence,
            "detection_type": str(raw.get("detection_type") or "person"),
            "bbox": list(raw.get("bbox") or []),
            "duration_in_frame_sec": float(raw.get("duration_in_frame_sec") or 0.0),
            "snapshot_url": raw.get("snapshot_url"),
            "raw_payload": raw,
            "timestamp": ts,
        }

        # Dedupe check: same identity on same camera in the configured window.
        if identity != "unknown" and self.short_term.recently_seen(camera_id, identity):
            event["is_duplicate"] = True

        event_id = self.store.create_event(event)
        event["id"] = event_id
        self.short_term.note_seen(camera_id, identity)
        self.short_term.note_event(camera_id, identity, event_id)
        return event