"""Gemini client — embeddings ONLY. Chat/vision moved to OpenRouter."""

from __future__ import annotations

import google.generativeai as genai

from core.config import settings
from core.log import log

genai.configure(api_key=settings.google_gemini_api_key)


async def embed(text: str) -> list[float]:
    """Generate embedding vector for text."""
    try:
        result = genai.embed_content(
            model=f"models/{settings.gemini_embedding_model}",
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]
    except Exception as e:
        log.error(f"Gemini embed error: {e}")
        return []


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Batch embedding."""
    try:
        result = genai.embed_content(
            model=f"models/{settings.gemini_embedding_model}",
            content=texts,
            task_type="retrieval_document",
        )
        return result["embedding"]
    except Exception as e:
        log.error(f"Gemini batch embed error: {e}")
        return [[] for _ in texts]
