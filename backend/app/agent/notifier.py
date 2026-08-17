"""Notifier Agent: apply confidence + severity gates and route alerts.

Low-severity events are batched into a digest; CRITICAL escalations go out
immediately. Channels are optional — unconfigured ones log instead of sending.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from .. import config
from ..notifications import dispatch

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}


class NotifierAgent:
    def __init__(self, store) -> None:
        self.store = store
        self._digest: list[dict] = []
        self._digest_times: list[float] = []

    def notify(self, incident: dict, event: dict) -> None:
        """Decide whether this incident warrants an alert, then dispatch."""
        severity = incident["severity"]
        confidence = float(event.get("identity_confidence") or 0.0)
        action = incident["action"]

        # Escalation: CRITICAL always notifies immediately, bypassing gating.
        if severity == "CRITICAL" or action == "escalate":
            self._send_channels(incident, event, bypass=True)
            return

        gate_ok = (
            _SEVERITY_RANK.get(severity, 0) >= config.NOTIFY_MIN_SEVERITY
            and confidence >= config.NOTIFY_MIN_CONFIDENCE
        )
        if not gate_ok:
            logger.info("Below notification gate — log only. severity=%s conf=%.2f", severity, confidence)
            self._queue_digest(incident, event)
            return

        self._send_channels(incident, event, bypass=False)

    def _message(self, incident: dict, event: dict) -> str:
        identity = event.get("identity_label") or "unknown"
        return (
            f"[{incident['severity']}] {incident['action'].upper()} — {identity} "
            f"at {event.get('camera_id')}. {incident['reasoning']}"
        )

    def _send_channels(self, incident: dict, event: dict, bypass: bool) -> None:
        msg = self._message(incident, event)
        channels = ["telegram", "slack", "discord", "email"]
        results = dispatch.send_all(
            msg,
            subject=f"IDENT-SCAN {incident['severity']} — {event.get('identity_label', 'unknown')}",
            severity=incident["severity"],
            override_bypass=bypass,
        )
        for channel, status in results.items():
            self.store.create_alert(
                incident["id"],
                channel,
                "configured-recipient",
                "sent" if status else "failed",
            )
        logger.info("Sent alerts for incident %s: %s", incident["id"], results)

    def _queue_digest(self, incident: dict, event: dict) -> None:
        self._digest.append(incident)
        self._digest_times.append(datetime.now(timezone.utc).timestamp())
        if len(self._digest) >= 5:
            self.flush_digest()

    def flush_digest(self) -> None:
        if not self._digest:
            return
        summary = "\n".join(
            f"- [{i['severity']}] {i['reasoning']}" for i in self._digest
        )
        dispatch.send_all(
            f"DIGEST ({len(self._digest)} low-severity incidents):\n{summary}",
            subject=f"IDENT-SCAN digest — {len(self._digest)} events",
            severity="DIGEST",
            override_bypass=False,
        )
        logger.info("Flushed digest with %d incidents.", len(self._digest))
        self._digest = []
        self._digest_times = []