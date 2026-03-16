"""Web scraping via Spider / Firecrawl."""

from __future__ import annotations

import httpx

from core.config import settings
from tools.registry import tool


@tool(
    name="web_scrape",
    description="Scrape a web page and return its content as markdown.",
    parameters={
        "url": {"type": "string", "description": "URL to scrape"},
    },
)
async def web_scrape(url: str) -> str:
    # Try Spider first, then Firecrawl
    if settings.spider_api_key:
        return await _spider_scrape(url)
    if settings.firecrawl_api_key:
        return await _firecrawl_scrape(url)
    return "Error: No scraping API configured (SPIDER_API_KEY or FIRECRAWL_API_KEY)"


async def _spider_scrape(url: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.spider.cloud/crawl",
            headers={
                "Authorization": f"Bearer {settings.spider_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "url": url,
                "limit": 1,
                "return_format": "markdown",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if isinstance(data, list) and data:
        return data[0].get("content", "No content")
    return str(data)


async def _firecrawl_scrape(url: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={
                "Authorization": f"Bearer {settings.firecrawl_api_key}",
                "Content-Type": "application/json",
            },
            json={"url": url, "formats": ["markdown"]},
        )
        resp.raise_for_status()
        data = resp.json()

    return data.get("data", {}).get("markdown", "No content")
