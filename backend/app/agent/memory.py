"""Memory Agent: write the event + embedding to long-term memory and update
short-term memory for the active incident window."""

import logging

from .humanize import describe_event
from ..memory.short_term import ShortTermMemory
from ..memory.long_term import LongTermMemory

logger = logging.getLogger(__name__)


def summarize_event(event: dict) -> str:
    """Natural-language description fed to the long-term memory store.

    Human readable (no bbox / confidence / ISO timestamps) so retrieved
    memory can be shown to operators and the LLM directly.
    """
    return describe_event(event)


class MemoryAgent:
    def __init__(
        self,
        long_term: LongTermMemory,
        short_term: ShortTermMemory,
    ) -> None:
        self.long_term = long_term
        self.short_term = short_term

    def remember(self, event: dict, incident_id: str | None = None) -> None:
        description = summarize_event(event)
        self.long_term.add(
            description,
            event["id"],
            incident_id=incident_id,
            timestamp=event.get("timestamp"),
        )
        self.short_term.note_event(event["camera_id"], event["identity_label"], event["id"])
        self.short_term.prune()

    def similar_incidents(self, event: dict, k: int = 5) -> list[dict]:
        """RAG: top-k similar past events from long-term memory."""
        return self.long_term.search(summarize_event(event), k=k)