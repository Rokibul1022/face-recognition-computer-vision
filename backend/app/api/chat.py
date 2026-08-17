"""Chat / natural-language interface over event + incident memory (RAG)."""
from __future__ import annotations

import logging

from ..agent import llm as llm_helper
from ..agent.humanize import describe_reference, readable_time
from ..memory.long_term import LongTermMemory

logger = logging.getLogger(__name__)

SYSTEM_CHAT = (
    "You are a friendly security assistant who talks to a person like a human, "
    "NOT like a log file. Use plain, easy-to-understand English. "
    "Never show event IDs, bbox coordinates, confidence decimals, similarity "
    "scores, or raw timestamps. "
    "Refer to times as things like 'today at 4:50 PM' or 'yesterday evening'. "
    "Refer to people by name when known, otherwise say 'an unknown person'. "
    "Base your answer ONLY on the retrieved events and incidents below. "
    "Never invent data. If nothing is relevant, say so in one friendly sentence."
)


def build_chat_reply(message: str, store, long_term: LongTermMemory) -> tuple[str, list[dict]]:
    """Return (reply, references). Uses RAG; LLM if available, else deterministic."""
    # Retrieve similar historical events from long-term memory (RAG).
    references = long_term.search(message, k=5)

    # Enrich references with event details and make them human readable.
    enriched: list[dict] = []
    for ref in references:
        ev = store.get_event(ref.get("event_id") or "")
        if ev:
            ref = {**ref, **ev, "human": describe_reference(ref, ev)}
        else:
            ref = {**ref, "human": describe_reference(ref)}
        enriched.append(ref)
    references = enriched[:5]

    if llm_helper.llm_available():
        context = _format_context(references)
        reply = llm_helper.chat_text(
            SYSTEM_CHAT,
            f"Retrieved events:\n{context}\n\nUser question: {message}",
        )
        if reply:
            return reply, references

    # Deterministic fallback: summarize matched memory.
    if references:
        lines = [f"- {r['human']}" for r in references]
        return (
            f"Found {len(references)} past event(s):\n" + "\n".join(lines),
            references,
        )
    return "I don't have any matching records yet. Try asking about people, cameras, or recent activity.", []


def _format_context(references: list[dict]) -> str:
    """Only human-readable lines go to the LLM — no ids/bbox/confidence."""
    if not references:
        return "(no matching past events)"
    lines = []
    for i, r in enumerate(references[:5], 1):
        when = readable_time(r.get("timestamp") or r.get("created_at"))
        identity = (r.get("identity_label") or r.get("identity") or "an unknown person").lower()
        if identity in {"unknown", "none", ""}:
            identity = "an unknown person"
        camera = r.get("camera_id") or "?"
        lines.append(f"{i}. {identity} at camera {camera}, {when}")
    return "\n".join(lines)