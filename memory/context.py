"""Build context window from memories + conversation history."""

from __future__ import annotations

from collections import deque

from core.models import ChatMessage
from memory import store

# In-memory conversation buffer
_conversation: deque[ChatMessage] = deque(maxlen=50)


def add_message(msg: ChatMessage):
    _conversation.append(msg)


def get_conversation() -> list[ChatMessage]:
    return list(_conversation)


def clear_conversation():
    _conversation.clear()


async def build_context(query: str) -> str:
    """Build a context string from relevant memories + recent conversation."""
    parts = []

    # Relevant memories
    memories = await store.search(query, limit=5)
    if memories:
        parts.append("## Relevant memories")
        for m in memories:
            parts.append(f"- {m.get('content', '')}")

    # Recent conversation
    recent = list(_conversation)[-10:]
    if recent:
        parts.append("\n## Recent conversation")
        for msg in recent:
            parts.append(f"{msg.role}: {msg.content[:200]}")

    return "\n".join(parts) if parts else ""
