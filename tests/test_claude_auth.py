"""Test Claude OAuth authentication."""

import asyncio
import pytest
from llm.claude import claude_client


def test_credentials_loaded():
    """Verify credentials were loaded from ~/.claude/.credentials.json."""
    assert claude_client._access_token is not None
    assert claude_client._access_token.startswith("sk-ant-oat01-")


@pytest.mark.asyncio
async def test_claude_ask():
    """Test a simple question to Claude."""
    response = await claude_client.ask("Reply with exactly: PONG")
    assert "PONG" in response


@pytest.mark.asyncio
async def test_claude_chat_with_system():
    """Test chat with system prompt."""
    response = await claude_client.ask(
        prompt="What is 2+2?",
        system="You are a math assistant. Reply with just the number.",
    )
    assert "4" in response
