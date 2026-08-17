"""Slack channel: send a message to an incoming webhook URL."""
from __future__ import annotations

import json
import logging
import urllib.request

from .. import config

logger = logging.getLogger(__name__)


def send(message: str, subject: str = "", **kwargs) -> bool:
    if not config.SLACK_WEBHOOK_URL:
        logger.debug("Slack not configured — skipping.")
        return False
    text = f"*{subject}*\n{message}" if subject else message
    try:
        payload = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            config.SLACK_WEBHOOK_URL, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status < 300
    except Exception as exc:
        logger.warning("Slack send failed: %s", exc)
        return False