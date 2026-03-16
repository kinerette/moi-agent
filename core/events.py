"""Simple async pub/sub between modules."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine

_subscribers: dict[str, list[Callable[..., Coroutine]]] = defaultdict(list)


def subscribe(event: str, handler: Callable[..., Coroutine]):
    _subscribers[event].append(handler)


async def publish(event: str, data: Any = None):
    for handler in _subscribers[event]:
        try:
            await handler(data)
        except Exception:
            pass  # Don't crash the bus


# Event names
EVT_TASK_CREATED = "task:created"
EVT_TASK_UPDATED = "task:updated"
EVT_CHAT_MESSAGE = "chat:message"
EVT_LOG = "log:new"
EVT_SCREENSHOT = "screenshot:new"
EVT_APPROVAL_NEEDED = "approval:needed"
EVT_APPROVAL_RESPONSE = "approval:response"
