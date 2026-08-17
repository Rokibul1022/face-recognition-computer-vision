"""Agent pipeline orchestrator.

Uses LangGraph's StateGraph when `langgraph` is installed (see
requirements-agent.txt); otherwise falls back to an equivalent async sequential
pipeline so the same agents run identically on a stock install.

Nodes: perceive -> classify_severity -> reason -> persist -> notify
"""
from __future__ import annotations

import logging
from typing import Any

from ..db.store import AgentStore
from ..memory.long_term import LongTermMemory
from ..memory.short_term import ShortTermMemory

from .memory import MemoryAgent
from .notifier import NotifierAgent
from .perception import PerceptionAgent
from .reasoning import Decision, ReasoningAgent
from .severity import SeverityClassifier

logger = logging.getLogger(__name__)


class AgentPipeline:
    """Composes the five agents and exposes `async process_event(..)`.

    Node implementations below are the single source of truth; both the LangGraph
    wrapper and the sequential fallback call the exact same node functions.
    """

    def __init__(
        self,
        store: AgentStore,
        short_term: ShortTermMemory,
        long_term: LongTermMemory,
    ) -> None:
        self.store = store
        self.perception = PerceptionAgent(store, short_term)
        self.severity = SeverityClassifier()
        self.memory_agent = MemoryAgent(long_term, short_term)
        self.reasoning = ReasoningAgent(store, short_term, self.memory_agent)
        self.notifier = NotifierAgent(store)

    # --- node implementations (shared by both paths) -------------------------
    def node_perceive(self, raw: dict) -> dict:
        return self.perception.process(raw)

    def node_classify_severity(self, event: dict) -> dict:
        verdict = self.severity.classify(event)
        event["severity"] = verdict.severity
        event["severity_reason"] = verdict.reason
        return event

    def node_reason(self, event: dict) -> dict:
        event["decision"] = self.reasoning.decide(event, event["severity"])
        return event

    def node_persist(self, event: dict) -> dict:
        decision: Decision = event["decision"]
        incident = {
            "event_id": event["id"],
            "severity": decision.severity,
            "action": decision.action,
            "reasoning": decision.reasoning,
            "reference_incident_id": decision.reference_incident_id,
        }
        incident["id"] = self.store.create_incident(incident)
        event["incident"] = incident
        self.memory_agent.remember(event, incident_id=incident["id"])
        return event

    def node_notify(self, event: dict) -> dict:
        if event.get("is_duplicate"):
            logger.info("Duplicate event %s skipped for notification.", event["id"])
            return event
        self.notifier.notify(event["incident"], event)
        return event

    # --- fallback sequential path ---------------------------------------------
    async def process_event(self, raw: dict) -> dict:
        event = self.node_perceive(raw)
        self.node_classify_severity(event)
        self.node_reason(event)
        self.node_persist(event)
        self.node_notify(event)
        return event

    def run_inline(self, raw: dict) -> dict:
        """Synchronous equivalent for scripts/tests running outside a loop."""
        event = self.node_perceive(raw)
        self.node_classify_severity(event)
        self.node_reason(event)
        self.node_persist(event)
        self.node_notify(event)
        return event


def _install_langgraph() -> bool:
    """Swap AgentPipeline.process_event for a LangGraph StateGraph invocation.

    Returns True if langgraph is importable. The nodes are the exact same
    functions as the sequential path, so behavior is identical either way.
    """
    try:  # pragma: no cover - optional dependency
        from langgraph.graph import END, StateGraph
        from typing_extensions import TypedDict

        _AgentState = TypedDict("_AgentState", {"raw": object, "event": dict})

        def _make_mut_node(pipe: AgentPipeline, fn):
            def _node(state: _AgentState) -> dict:
                event = dict(state["event"])
                fn(event)
                return {"event": event}

            return _node

        def _build(pipe: AgentPipeline):
            graph = StateGraph(_AgentState)

            def _perceive_node(state: _AgentState) -> dict:
                return {"event": pipe.node_perceive(state["raw"])}

            graph.add_node("perceive", _perceive_node)
            graph.add_node("severity", _make_mut_node(pipe, pipe.node_classify_severity))
            graph.add_node("reason", _make_mut_node(pipe, pipe.node_reason))
            graph.add_node("persist", _make_mut_node(pipe, pipe.node_persist))
            graph.add_node("notify", _make_mut_node(pipe, pipe.node_notify))
            graph.set_entry_point("perceive")
            graph.add_edge("perceive", "severity")
            graph.add_edge("severity", "reason")
            graph.add_edge("reason", "persist")
            graph.add_edge("persist", "notify")
            graph.add_edge("notify", END)
            return graph.compile()

        async def _process_via_graph(pipe: AgentPipeline, raw: dict) -> dict:
            graph = _build(pipe)
            result = await graph.ainvoke({"raw": raw, "event": {}})
            return result["event"]

        AgentPipeline.process_event = _process_via_graph
        return True
    except Exception:
        return False


if _install_langgraph():  # pragma: no cover
    logger.info("LangGraph available — agent pipeline runs on a state graph.")
else:
    logger.warning(
        "LangGraph not installed — using sequential agent pipeline. "
        "Install `langgraph` (requirements-agent.txt) to switch."
    )

__all__ = ["AgentPipeline"]