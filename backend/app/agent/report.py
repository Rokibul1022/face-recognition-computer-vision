"""Report Agent: generate daily/weekly summaries from stored events + incidents.

Phase 3 scheduling lives here; `/summary` delegates to it synchronously.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .. import config

logger = logging.getLogger(__name__)


class ReportAgent:
    def __init__(self, store) -> None:
        self.store = store

    def report_for_incident(self, incident_id: str) -> dict | None:
        """Produce a human-readable report for a single incident."""
        incident = self.store.get_incident(incident_id)
        if not incident:
            return None
        event = None
        if incident.get("event_id"):
            event = self.store.get_event(incident["event_id"])

        lines = [
            f"Incident {incident['id']}",
            f"Severity: {incident['severity']}  Action: {incident['action']}",
            f"Reasoning: {incident.get('reasoning') or '—'}",
        ]
        if incident.get("reference_incident_id"):
            lines.append(f"Related to: {incident['reference_incident_id']}")
        if event:
            lines.append(
                f"Event: camera={event.get('camera_id')} identity={event.get('identity')} "
                f"confidence={event.get('identity_confidence')} type={event.get('detection_type')}"
            )
            lines.append(f"BBox: {event.get('bbox')}")
        lines.append(f"Created: {incident.get('created_at')}")

        return {
            "id": str(uuid4()),
            "incident_id": incident_id,
            "format": "text",
            "summary": "\n".join(lines),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def summary(self, window_seconds: int | None = None) -> dict:
        window = window_seconds or config.REPORT_WINDOW_SEC
        events = self.store.list_events(limit=5000)
        incidents = self.store.list_incidents(limit=5000)

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window)
        cutoff_iso = cutoff.isoformat()

        by_severity: dict[str, int] = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}
        for inc in incidents:
            created = inc.get("created_at", "")
            if created > cutoff_iso:
                by_severity[inc["severity"]] = by_severity.get(inc["severity"], 0) + 1

        top_ref = None
        ref_counts: dict[str, int] = {}
        for inc in incidents:
            ref = inc.get("reference_incident_id")
            if ref:
                ref_counts[ref] = ref_counts.get(ref, 0) + 1
        if ref_counts:
            top_ref = max(ref_counts, key=ref_counts.get)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_seconds": window,
            "total_events": len(events),
            "incidents": incidents[:50],
            "by_severity": by_severity,
            "top_reference_incident_id": top_ref,
        }