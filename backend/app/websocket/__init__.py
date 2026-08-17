"""WebSocket integration for the dashboard (live incident push)."""
from .realtime import RealtimeHub, realtime

__all__ = ["RealtimeHub", "realtime"]