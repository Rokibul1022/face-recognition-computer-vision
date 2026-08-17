"""Severity Classifier: rule-based first pass, optional LLM second pass.

Severity levels (0=INFO, 1=WARNING, 2=CRITICAL). The LLM only runs for
ambiguous confidence windows to keep token spend low.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .. import config
from . import llm as llm_helper

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}
_WEAPON_LIKE = {"weapon", "fire", "smoke"}


@dataclass
class SeverityVerdict:
    severity: str
    reason: str
    source: str = "rule"
    anchors: list[str] = field(default_factory=list)


class SeverityClassifier:
    """Deterministic first-pass classifier with an LLM fallback."""

    def __init__(self) -> None:
        self.rule_hits: list[str] = []
        self.confidence = 0.0
        self.is_unknown = False

    def classify(self, event: dict) -> SeverityVerdict:
        self.rule_hits = []
        identity = event.get("identity_label") or "unknown"
        confidence = float(event.get("identity_confidence") or 0.0)
        self.confidence = confidence
        self.is_unknown = identity == "unknown"
        dtype = event.get("detection_type") or "person"

        severity, reason = self._rule_pass(identity, confidence, dtype)
        verdict = SeverityVerdict(severity=severity, reason=reason, anchors=list(self.rule_hits))

        # LLM second pass: ambiguous confidence only.
        if llm_helper.llm_available() and (
            config.SEVERITY_LLM_AMBIGUOUS_MIN
            <= confidence
            <= config.SEVERITY_LLM_AMBIGUOUS_MAX
        ):
            verdict.source = "llm"
            try:
                self._llm_pass(event, verdict)
            except Exception:
                logger.exception("LLM severity pass failed; keeping rule verdict.")

        return verdict

    def _rule_pass(self, identity: str, confidence: float, dtype: str) -> tuple[str, str]:
        # Noisy/low-confidence detections never go above WARNING on identity alone.
        if dtype in _WEAPON_LIKE:
            self.rule_hits.append("flagged-detection-type")
            return "CRITICAL", f"{dtype.upper()} flag — assume danger regardless of other factors."

        if confidence > 0:
            self.rule_hits.append("low-confidence")
            if confidence < 0.5:
                return "INFO", (f"Low confidence ({confidence:.2f}) — {identity}; treating as informational.")

        now = datetime.now(timezone.utc).hour
        after_hours = now < 8 or now > 20

        if not identity or identity == "unknown":
            if after_hours:
                self.rule_hits.append("unknown-after-hours")
                return "CRITICAL", "Unknown person during off-hours."
            self.rule_hits.append("unknown-hours")
            return "WARNING", "Unknown person on site during normal hours."

        self.rule_hits.append("known-employee")
        return "INFO", f"Known identity ({identity}) — routine presence."

    def _llm_pass(self, event: dict, verdict: SeverityVerdict) -> None:
        prompt_user = (
            f"Event: {event}\n"
            f"Zone: {event.get('zone', 'general')}\n"
            f"Known identity: {event.get('identity_label')}\n"
            f"Rule verdict so far: {verdict.severity} ({verdict.reason})"
        )
        result = llm_helper.chat_json(
            SYSTEM_SEVERITY, prompt_user
        )
        if not result:
            return
        sev = str(result.get("severity", ""))
        if sev in _SEVERITY_RANK and _SEVERITY_RANK[sev] >= _SEVERITY_RANK[verdict.severity]:
            verdict.severity = sev
            verdict.reason = str(result.get("reason") or verdict.reason)


SYSTEM_SEVERITY = (
    "You are a security severity classifier. Given an event, classify it as "
    "INFO, WARNING, or CRITICAL using the rules: unknown+off-hours or any "
    "weapon/fire/smoke flag -> CRITICAL; known employee normal hours -> INFO; "
    "loitering or unknown during hours -> at least WARNING. Respond ONLY with "
    'JSON: {"severity": "...", "reason": "..."}'
)