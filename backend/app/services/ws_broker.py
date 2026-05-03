"""Tiny in-process pub/sub for WebSocket fan-out."""
from __future__ import annotations

import asyncio
from typing import Any


class Broker:
    def __init__(self) -> None:
        self._subs: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    async def publish(self, payload: Any) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass


broker = Broker()
