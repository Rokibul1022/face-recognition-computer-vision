"""Reasoning Agent: the core decision-maker.

Deterministic path: pull short-term context (last events on this camera) and
long-term memory (similar past incidents), then emit a Decision. When an LLM is
configured it reviews the same context and can escalate/override the verdict.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from . import llm as llm_helper

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    action: str  # notify | log_only | ignore | escalate
    severity: str  # INFO | WARNING | CRITICAL
    reasoning: str
    reference_incident_id: str | None = field(default=None)


class ReasoningAgent:
    def __init__(self, store, short_term, memory_agent) -> None:
        self.store = store
        self.short_term = short_term
        self.memory_agent = memory_agent

    def decide(self, event: dict, severity: str) -> Decision:
        identity = event.get("identity_label") or "unknown"
        camera = event.get("camera_id") or "?"
        confidence = float(event.get("identity_confidence") or 0.0)

        # Short-term context: what else just happened on this camera?
        recent = self.short_term.recent_event_ids(camera, identity)
        # Long-term context: has this pattern appeared before?
        similar = self.memory_agent.similar_incidents(event, k=3)
        reference = None
        for s in similar:
            if s.get("incident_id"):
                reference = s["incident_id"]
                break

        action, reasoning = self._rule_decision(severity, confidence, identity, recent)

        # LLM refinement when available and severity is at least WARNING.
        if llm_helper.llm_available() and severity in ("WARNING", "CRITICAL"):
            llm = self._llm_decision(event, severity, recent, similar)
            if llm:
                action, severity, reasoning = llm
                reference = llm.get("reference_incident_id") or reference

        return Decision(action=action, severity=severity, reasoning=reasoning, reference_incident_id=reference)

    def _rule_decision(self, severity: str, confidence: float, identity: str, recent: list[str]) -> tuple[str, str]:
        if severity == "CRITICAL":
            return "escalate", "Critical severity — escalate immediately to a human operator."
        if severity == "WARNING":
            if confidence < 0.6:
                return "log_only", (f"Warning but low confidence ({confidence:.2f}); logging for review.")
            if len(recent) >= 3:
                return "escalate", "Repeated events on this camera — escalate for operator review."
            return "notify", "Warning-level event — notify the security desk."
        return "log_only", "Informational event; log only."

    def _llm_decision(self, event, severity, recent, similar) -> dict | None:
        prompt_user = (
            f"New event: {event}\n"
            f"Severity (pre-classified): {severity}\n"
            f"Short-term context (this camera): {recent}\n"
            f"Similar past incidents: {similar}\n"
            f"Decide: notify | log_only | ignore | escalate. Reference past incidents by incident_id."
        )
        result = llm_helper.chat_json(SYSTEM_REASONING, prompt_user)
        if not result:
            return None
        action = str(result.get("action", "log_only"))
        if action not in ("notify", "log_only", "ignore", "escalate"):
            action = "log_only"
        return {
            "action": action,
            "severity": str(result.get("severity", severity)),
            "reasoning": str(result.get("reasoning", "LLM review.")),
            "reference_incident_id": result.get("reference_incident_id"),
        }


SYSTEM_REASONING = (
    "You are a security reasoning agent. Review the event, its pre-classified "
    "severity, short-term context, and similar past incidents. Choose one action: "
    "notify, log_only, ignore, escalate. Explain in 1-2 sentences for a security "
    "officer and cite a reference_incident_id if one clearly matches. Respond ONLY "
    'with JSON: {"action":"...","severity":"...","reasoning":"...","reference_incident_id":"... or null"}'
)