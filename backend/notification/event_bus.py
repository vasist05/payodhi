"""Minimal asyncio pub/sub for Phase 8 alert fan-out.

The response engine publishes alerts here. The WebSocket endpoint in
response_api.py subscribes. This keeps the engine decoupled from FastAPI:
the engine never imports the API layer, so it stays testable in isolation.

Each subscriber is an asyncio.Queue. publish() is non-blocking: if a
subscriber's queue is full (slow client), the alert is dropped for that
subscriber only — the engine never blocks on a slow consumer.

Usage:
    bus = EventBus()
    q = bus.subscribe()
    bus.publish({"id": "..."})
    alert = await q.get()
    bus.unsubscribe(q)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Per-subscriber queue depth. Beyond this, alerts are dropped for that
# subscriber — prevents a stalled dashboard from backpressuring the engine.
_QUEUE_MAXSIZE = 64


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    def subscribe(self) -> asyncio.Queue:
        """Create a new subscriber queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        self._subscribers.discard(q)

    def publish(self, event: dict[str, Any]) -> None:
        """Fan out an event to all subscribers. Never blocks."""
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "EventBus: subscriber queue full, dropping event %s",
                    event.get("id"),
                )

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# Module-level singleton. The engine publishes; the API subscribes.
bus = EventBus()