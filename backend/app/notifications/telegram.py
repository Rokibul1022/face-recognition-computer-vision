"""Telegram channel: send a message via Bot API. Requires a bot token + chat id."""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

from .. import config

logger = logging.getLogger(__name__)


def send(message: str, subject: str = "", **kwargs) -> bool:
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        logger.debug("Telegram not configured — skipping.")
        return False
    text = f"{subject}\n{message}" if subject else message
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": text[:4000],
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as res:
            body = json.loads(res.read().decode("utf-8"))
        return bool(body.get("ok"))
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False