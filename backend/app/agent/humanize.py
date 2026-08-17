"""Human-friendly formatting shared by the agent + chat layers.

Internal descriptions must be searchable (they feed the embedding store) and
the chat layer must be readable. This module owns both sides so a report,
memory entry and chat answer never leak raw bboxes, confidence decimals or
ISO timestamps to the operator.
"""
from __future__ import annotations

from datetime import datetime


def readable_time(value) -> str:
    """2026-08-17T14:50:57.210610+00:00 -> 'Aug 17, 4:50 PM' (local time)."""
    if not value:
        return "recently"
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return "recently"
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")


def pretty_identity(identity) -> str:
    """'unknown' / 'aelx' -> readable label."""
    identity = str(identity or "unknown").strip() or "unknown"
    if identity.lower() in {"unknown", "none", ""}:
        return "an unknown person"
    return identity


def describe_event(event: dict) -> str:
    """One natural-language sentence for a stored event (searchable + readable)."""
    identity = event.get("identity_label") or event.get("identity") or "an unknown person"
    dtype = event.get("detection_type") or "person"
    camera = event.get("camera_id") or "?"
    when = readable_time(event.get("timestamp") or event.get("created_at"))
    return f"{identity} was seen as {dtype} at camera {camera} on {when}"


def describe_reference(ref: dict, event: dict | None = None) -> str:
    """Readable line for a chat reference (no event_id/bbox/similarity jargon)."""
    if event:
        identity = event.get("identity_label") or event.get("identity") or "an unknown person"
        camera = event.get("camera_id") or "?"
        when = readable_time(event.get("timestamp") or event.get("created_at"))
        return f"{identity} was seen at {camera} on {when}"
    return ref.get("description") or "a past event"