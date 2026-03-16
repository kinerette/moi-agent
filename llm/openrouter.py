"""OpenRouter client — access to uncensored models (Qwen, Kimi, DeepSeek, etc.)."""

from __future__ import annotations

import base64
import httpx

from core.config import settings
from core.log import log

_URL = "https://openrouter.ai/api/v1/chat/completions"


async def chat(
    prompt: str,
    system: str = "",
    model: str | None = None,
    image_b64: str | None = None,
) -> str:
    """Chat via OpenRouter. Supports text and vision."""
    model = model or settings.openrouter_model

    messages = []
    if system:
        messages.append({"role": "system", "content": system})

    if image_b64:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            ],
        })
    else:
        messages.append({"role": "user", "content": prompt})

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                _URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 4096,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"]
    except Exception as e:
        log.error(f"OpenRouter error: {e}")
        return f"[OpenRouter error: {e}]"


async def vision(prompt: str, image_bytes: bytes, mime: str = "image/png") -> str:
    """Vision via OpenRouter with image bytes."""
    b64 = base64.b64encode(image_bytes).decode()
    return await chat(prompt, image_b64=b64, model=settings.openrouter_vision_model)


async def vision_from_base64(prompt: str, b64: str) -> str:
    return await chat(prompt, image_b64=b64, model=settings.openrouter_vision_model)
