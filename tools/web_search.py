"""Web search via SerpAPI."""

from __future__ import annotations

import httpx

from core.config import settings
from tools.registry import tool


@tool(
    name="web_search",
    description="Search the web using Google via SerpAPI. Returns top results.",
    parameters={
        "query": {"type": "string", "description": "Search query"},
        "num_results": {"type": "integer", "description": "Number of results (default 5)"},
    },
)
async def web_search(query: str, num_results: int = 5) -> str:
    if not settings.serpapi_key:
        return "Error: SERPAPI_KEY not configured"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://serpapi.com/search",
            params={
                "q": query,
                "api_key": settings.serpapi_key,
                "num": num_results,
                "engine": "google",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("organic_results", [])[:num_results]:
        results.append(
            f"**{item.get('title', '')}**\n"
            f"{item.get('link', '')}\n"
            f"{item.get('snippet', '')}\n"
        )

    return "\n".join(results) if results else "No results found."
