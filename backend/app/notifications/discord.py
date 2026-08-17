"""Discord channel: send a message to an incoming webhook URL."""
from __future__ import annotations

import json
import logging
import urllib.request

from .. import config

logger = logging.getLogger(__name__)


def send(message: str, subject: str = "", **kwargs) -> bool:
    if not config.DISCORD_WEBHOOK_URL:
        logger.debug("Discord not configured — skipping.")
        return False
    text = f"**{subject}**\n{message}" if subject else message
    try:
        payload = json.dumps({"content": text[:2000]}).encode("utf-8")
        req = urllib.request.Request(
            config.DISCORD_WEBHOOK_URL, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status < 300
    except Exception as exc:
        logger.warning("Discord send failed: %s", exc)
        return False