"""Event bus: in-process asyncio queue + background agent worker.

CV pushes a structured event via POST /events; the endpoint enqueues it here and
returns immediately. The worker drains the queue through the agent pipeline.
"""
from __future__ import annotations

import asyncio
import logging

from .. import config
from ..agent.graph import AgentPipeline
from ..websocket.realtime import realtime

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self, pipeline: AgentPipeline) -> None:
        self.pipeline = pipeline
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=config.EVENT_QUEUE_MAX)
        self._task: asyncio.Task | None = None
        self._stopping = False

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    async def publish(self, raw: dict) -> bool:
        try:
            self._queue.put_nowait(raw)
            return True
        except asyncio.QueueFull:
            logger.warning("Event queue full — dropping event %s", raw.get("event_id"))
            return False

    async def _drain(self) -> None:
        logger.info("Agent worker started.")
        while not self._stopping:
            try:
                raw = await asyncio.wait_for(self._queue.get(), timeout=10.0)
            except asyncio.TimeoutError:
                continue
            except Exception:  # pragma: no cover
                continue
            try:
                result = await self.pipeline.process_event(raw)
                incident = result.get("incident", {})
                logger.info(
                    "Agent processed event %s -> %s/%s (%s)",
                    result.get("id"),
                    result.get("severity"),
                    incident.get("action"),
                    result.get("reasoning", "")[:80],
                )
                await realtime.broadcast("incident", {
                    "id": incident.get("id"),
                    "event_id": result.get("id"),
                    "severity": incident.get("severity") or result.get("severity"),
                    "action": incident.get("action"),
                    "reasoning": incident.get("reasoning", ""),
                    "identity": result.get("identity_label"),
                    "camera_id": result.get("camera_id"),
                })
            except Exception:
                logger.exception("Agent failed to process event %s", raw.get("event_id"))
            finally:
                self._queue.task_done()

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._drain())

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None