"""Skip-permission integration — creates Instagram carousel posts via the pipeline API."""

from __future__ import annotations

import json
import httpx

from tools.registry import tool
from core.log import log

_BASE = "http://localhost:3001/api/pipeline"


async def _call(endpoint: str, payload: dict, timeout: int = 120) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{_BASE}/{endpoint}",
            headers={"Content-Type": "application/json"},
            json=payload,
        )
        return resp.json()


@tool(
    name="create_instagram_post",
    description="Create an Instagram carousel post using skip-permission pipeline. Provide a topic/query and it runs the full pipeline: search tweets, research, generate hooks, plan carousel. Returns the carousel plan with slide contents.",
    parameters={
        "query": {"type": "string", "description": "Topic to search for (e.g. 'AI agents', 'LLMOS', 'OpenClaw')"},
    },
)
async def create_instagram_post(query: str) -> str:
    try:
        # Step 1: Search tweets
        log.info(f"[skip-permission] Searching: {query}")
        search = await _call("search", {"query": query})
        if not search.get("success") or not search.get("tweets"):
            return f"Search failed or no tweets found for '{query}'"

        tweets = search["tweets"]
        tweet = tweets[0]  # Best tweet
        log.info(f"[skip-permission] Found {len(tweets)} tweets, using: {tweet.get('text', '')[:60]}")

        # Step 2: Research
        log.info("[skip-permission] Researching...")
        research_resp = await _call("research", {"tweet": tweet})
        if not research_resp.get("success"):
            return f"Research failed: {research_resp.get('error', 'unknown')}"
        research = research_resp["research"]

        # Step 3: Generate hooks
        log.info("[skip-permission] Generating hooks...")
        hooks_resp = await _call("hooks", {"tweet": tweet, "research": research})
        if not hooks_resp.get("success"):
            return f"Hooks failed: {hooks_resp.get('error', 'unknown')}"
        hooks = hooks_resp["hooks"]
        best_hook = hooks[0]
        log.info(f"[skip-permission] Best hook: {best_hook.get('text', '')[:60]}")

        # Step 4: Carousel plan
        log.info("[skip-permission] Planning carousel...")
        plan_resp = await _call("carousel-plan", {
            "tweet": tweet,
            "research": research,
            "selectedHook": best_hook,
        })

        # Step 5: Generate visual
        log.info("[skip-permission] Generating visual...")
        visual_resp = await _call("visual", {
            "tweet": tweet,
            "research": research,
            "selectedHook": best_hook,
        }, timeout=180)

        # Compile result
        result_parts = [
            f"POST INSTAGRAM CREE AVEC SUCCES",
            f"",
            f"Sujet: {query}",
            f"Tweet source: {tweet.get('text', '')[:100]}",
            f"Engagement: {tweet.get('engagement', 'N/A')}",
            f"",
            f"HOOK SELECTIONNE: {best_hook.get('text', '')}",
            f"",
        ]

        if plan_resp.get("success") and plan_resp.get("plan"):
            plan = plan_resp["plan"]
            result_parts.append("CAROUSEL PLAN:")
            slides = plan.get("slides", [])
            for i, slide in enumerate(slides):
                result_parts.append(f"  Slide {i+1}: {json.dumps(slide, ensure_ascii=False)[:200]}")

        if visual_resp.get("success"):
            img_url = visual_resp.get("imageUrl", "")
            if img_url:
                result_parts.append(f"\nIMAGE GENEREE: {img_url}")
            config = visual_resp.get("config", {})
            if config:
                result_parts.append(f"SUPERTITLE: {config.get('supertitle', '')}")
                result_parts.append(f"HEADLINE: {config.get('headline', '')}")

        result_parts.append(f"\nTOUS LES HOOKS GENERES:")
        for i, h in enumerate(hooks[:5]):
            result_parts.append(f"  {i+1}. {h.get('text', '')}")

        return "\n".join(result_parts)

    except Exception as e:
        log.error(f"[skip-permission] Pipeline error: {e}")
        return f"Pipeline error: {e}"
