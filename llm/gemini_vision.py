"""Gemini 3 Flash — vision only. Fastest option for screenshot analysis (~2s)."""

from __future__ import annotations

import google.generativeai as genai
from core.config import settings
from core.log import log

genai.configure(api_key=settings.google_gemini_api_key)
_model = genai.GenerativeModel("gemini-3-flash-preview")

_PROMPT = (
    "Decris EXACTEMENT ce que tu vois a l'ecran. "
    "Lis TOUT le texte visible. Boutons, menus, popups, erreurs. "
    "Positions: haut/bas/gauche/droite/centre. Sois precis et concis."
)


async def analyze_screenshot(image_bytes: bytes, prompt: str = "") -> str:
    try:
        image_part = {"mime_type": "image/png", "data": image_bytes}
        response = await _model.generate_content_async(
            [prompt or _PROMPT, image_part],
            generation_config={"max_output_tokens": 800},
        )
        return response.text
    except Exception as e:
        log.error(f"Gemini vision error: {e}")
        return f"[Vision error: {e}]"
