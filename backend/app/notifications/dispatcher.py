"""Notification dispatcher: routes a message to configured channels.

`dispatch.channel(name, message, subject)` returns True/False for each channel.
Every channel is optional; missing config returns False (and logs why at debug).
"""
from __future__ import annotations

import logging

from .. import config
from . import discord, email, slack, telegram

logger = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self) -> None:
        self._channels = {
            "telegram": telegram.send,
            "slack": slack.send,
            "discord": discord.send,
            "email": email.send,
        }

    def channel(self, name: str, message: str, subject: str = "", **kwargs) -> bool:
        fn = self._channels.get(name)
        if fn is None:
            return False
        return fn(message=message, subject=subject, **kwargs)

    def send_all(
        self,
        message: str,
        subject: str = "",
        severity: str = "INFO",
        override_bypass: bool = False,
    ) -> dict[str, bool]:
        """Dispatch to every configured channel; returns {channel: delivered}."""
        results: dict[str, bool] = {}
        for name, fn in self._channels.items():
            results[name] = fn(message=message, subject=subject, severity=severity)
        return results


# Module-level singleton used across the app.
dispatch = Dispatcher()