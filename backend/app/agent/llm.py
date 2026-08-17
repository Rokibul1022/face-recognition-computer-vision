"""Minimal OpenAI-compatible chat helper for the optional LLM paths.

Uses only stdlib `urllib` so no extra dependency is required; works against any
OpenAI-compatible endpoint (OpenAI, local Ollama/TGI, etc.) by setting
OPENAI_BASE_URL. Returns None on any failure so the deterministic fallbacks
always have a path forward.
"""
from __future__ import annotations

import json
import logging
import urllib.request

from .. import config

logger = logging.getLogger(__name__)


def llm_available() -> bool:
    return bool(config.LLM_API_KEY)


def chat_json(
    system: str,
    user: str,
    *,
    as_json: bool = True,
    timeout: int = 20,
) -> dict | None:
    """Call the configured LLM and return parsed JSON (or None on any error)."""
    if not llm_available():
        return None
    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    if as_json:
        payload["response_format"] = {"type": "json_object"}
    try:
        req = urllib.request.Request(
            f"{config.LLM_BASE_URL}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.LLM_API_KEY}",
                # Some providers (Groq via Cloudflare) return HTTP 1010 / 403
                # when they see urllib's default User-Agent. Use a normal one.
                "User-Agent": "ident-scan/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = json.loads(res.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        if as_json:
            return json.loads(content)
        return {"text": content}
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        return None


def chat_text(system: str, user: str, timeout: int = 30) -> str | None:
    """Call the LLM and return plain text (None on any error)."""
    result = chat_json(system, user, as_json=False, timeout=timeout)
    return result.get("text") if result else None