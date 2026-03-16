"""Vision with UI element grounding — Qwen2.5-VL via OpenRouter.
Returns pixel coordinates of clickable elements."""

from __future__ import annotations

import httpx
import base64

from core.config import settings
from core.log import log

_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODEL = "qwen/qwen2.5-vl-72b-instruct"

_GROUNDING_PROMPT = (
    "Tu es un assistant de computer use. Analyse cette capture d'ecran.\n"
    "Pour CHAQUE element interactif visible, donne son nom et ses coordonnees en pixels (x, y) depuis le coin haut-gauche de l'ecran.\n"
    "Format OBLIGATOIRE pour chaque element:\n"
    "ELEMENT: 'texte visible' @ (x, y)\n\n"
    "Exemples:\n"
    "BOUTON: 'Rechercher' @ (750, 400)\n"
    "CHAMP: 'Tapez ici...' @ (600, 350)\n"
    "LIEN: 'AI News' @ (500, 320)\n"
    "ONGLET: 'Chrome' @ (200, 15)\n\n"
    "Liste TOUS les elements cliquables. Sois PRECIS sur les coordonnees.\n"
    "Puis decris brievement la page (quelle app, quel etat)."
)


async def analyze_screenshot(image_bytes: bytes, prompt: str = "") -> str:
    """Analyze screenshot with Qwen2.5-VL — returns element coordinates."""
    try:
        b64 = base64.b64encode(image_bytes).decode()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt or _GROUNDING_PROMPT},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                            ],
                        }
                    ],
                    "max_tokens": 1500,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        result = data["choices"][0]["message"]["content"]
        return result
    except Exception as e:
        log.error(f"Vision error: {e}")
        return f"[Vision error: {e}]"
