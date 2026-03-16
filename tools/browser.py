"""Browser — web scraping silencieux. N'ouvre PAS Chrome a chaque navigation."""

from __future__ import annotations

import httpx
from html.parser import HTMLParser

from tools.registry import tool
from core.log import log


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False
    def handle_starttag(self, tag, _):
        if tag in ("script", "style", "noscript"):
            self._skip = True
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False
    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if t:
                self.parts.append(t)


async def _fetch_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        })
        ext = _TextExtractor()
        ext.feed(resp.text)
        return "\n".join(ext.parts)


@tool(
    name="browser_navigate",
    description="Fetch a URL and return its text content. Does NOT open Chrome — just reads the page silently.",
    parameters={"url": {"type": "string", "description": "URL to fetch"}},
)
async def browser_navigate(url: str) -> str:
    try:
        text = await _fetch_text(url)
        return f"Content of {url}:\n\n{text[:4000]}"
    except Exception as e:
        return f"Failed to fetch {url}: {e}"


@tool(
    name="browser_open_visible",
    description="Open a URL visually in Chrome (only when the user needs to SEE the page).",
    parameters={"url": {"type": "string", "description": "URL to open in Chrome"}},
)
async def browser_open_visible(url: str) -> str:
    import subprocess
    subprocess.Popen(["cmd", "/c", "start", "", url], shell=False,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"Opened {url} in Chrome."
