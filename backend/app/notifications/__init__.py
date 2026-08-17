"""Notification channel modules.

Each is optional and degrades to a logging no-op when unconfigured. Only stdlib
is used (urllib for webhooks, smtplib for email) to avoid extra dependencies.
"""
from .dispatcher import Dispatcher, dispatch

__all__ = ["Dispatcher", "dispatch"]