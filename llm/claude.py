"""Claude OAuth client — uses shared credentials from Claude CLI."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
from filelock import FileLock

from core.config import settings
from core.log import log

_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
_REFRESH_URL = "https://console.anthropic.com/api/oauth/token"
_LOCK_PATH = Path(settings.claude_credentials_path).with_suffix(".lock")


class ClaudeClient:
    def __init__(self):
        self._creds_path = Path(settings.claude_credentials_path)
        self._lock = FileLock(str(_LOCK_PATH), timeout=10)
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0
        self._load_credentials()

    def _load_credentials(self):
        try:
            with self._lock:
                data = json.loads(self._creds_path.read_text())
            oauth = data.get("claudeAiOauth", {})
            self._access_token = oauth.get("accessToken")
            self._refresh_token = oauth.get("refreshToken")
            self._expires_at = oauth.get("expiresAt", 0) / 1000  # ms → s
            log.info("Claude credentials loaded")
        except Exception as e:
            log.error(f"Failed to load Claude credentials: {e}")

    async def _refresh_if_needed(self):
        if time.time() < self._expires_at - 300:  # 5 min buffer
            return
        if not self._refresh_token:
            log.error("No refresh token available")
            return

        log.info("Refreshing Claude OAuth token...")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _REFRESH_URL,
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]  # single-use
        self._expires_at = time.time() + data.get("expires_in", 3600)

        # Persist back
        with self._lock:
            creds = json.loads(self._creds_path.read_text())
            creds["claudeAiOauth"]["accessToken"] = self._access_token
            creds["claudeAiOauth"]["refreshToken"] = self._refresh_token
            creds["claudeAiOauth"]["expiresAt"] = int(self._expires_at * 1000)
            self._creds_path.write_text(json.dumps(creds, indent=2))

        log.info("Claude token refreshed")

    async def chat(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
        model: str | None = None,
    ) -> dict:
        await self._refresh_if_needed()

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "oauth-2025-04-20",
        }

        body: dict = {
            "model": model or settings.claude_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = tools

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(_MESSAGES_URL, headers=headers, json=body)
            resp.raise_for_status()

        return resp.json()

    async def ask(self, prompt: str, system: str = "") -> str:
        """Simple text question → text answer."""
        result = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
        )
        # Extract text from content blocks
        for block in result.get("content", []):
            if block.get("type") == "text":
                return block["text"]
        return ""


claude_client = ClaudeClient()
