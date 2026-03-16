"""Test Gemini client."""

import asyncio
import pytest
from llm import gemini


@pytest.mark.asyncio
async def test_gemini_chat():
    """Test Gemini chat."""
    response = await gemini.chat("Reply with exactly: PONG")
    assert "PONG" in response


@pytest.mark.asyncio
async def test_gemini_embed():
    """Test embedding generation."""
    vector = await gemini.embed("Hello world")
    assert isinstance(vector, list)
    assert len(vector) > 0
    assert isinstance(vector[0], float)
