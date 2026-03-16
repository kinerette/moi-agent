"""Skip-permission — full Instagram carousel pipeline via API. No Chrome needed."""

from __future__ import annotations

import json
import base64
from pathlib import Path

import httpx

from tools.registry import tool
from core.log import log

_BASE = "http://localhost:3001/api/pipeline"
_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "posts"


async def _call(endpoint: str, payload: dict, timeout: int = 120) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{_BASE}/{endpoint}",
            headers={"Content-Type": "application/json"},
            json=payload,
        )
        return resp.json()


async def _download_image(url: str, path: Path) -> bool:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                path.write_bytes(resp.content)
                return True
    except Exception:
        pass
    return False


@tool(
    name="create_instagram_post",
    description="Create a full Instagram carousel post. Runs the entire pipeline: search tweets, research, hooks, carousel plan, generate images for each slide. Saves PNG images to data/posts/. Returns the carousel content and image paths.",
    parameters={
        "query": {"type": "string", "description": "Topic to search for (e.g. 'AI agents', 'LLMOS')"},
    },
)
async def create_instagram_post(query: str) -> str:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # === 1. SEARCH ===
        log.info(f"[POST] 1/6 Search: {query}")
        search = await _call("search", {"query": query})
        if not search.get("success") or not search.get("tweets"):
            return f"Search failed for '{query}'"

        tweets = search["tweets"]
        # Pick tweet with most engagement
        tweet = tweets[1] if len(tweets) > 1 else tweets[0]
        log.info(f"[POST] Found {len(tweets)} tweets. Selected: {tweet.get('titleFr', tweet.get('text', ''))[:60]}")

        # === 2. RESEARCH ===
        log.info("[POST] 2/6 Research...")
        research_resp = await _call("research", {"tweet": tweet})
        if not research_resp.get("success"):
            return f"Research failed: {research_resp.get('error')}"
        research = research_resp["research"]
        log.info(f"[POST] Research: {research.get('mainSubject', '')[:50]}")

        # === 3. HOOKS ===
        log.info("[POST] 3/6 Hooks...")
        hooks_resp = await _call("hooks", {"tweet": tweet, "research": research})
        if not hooks_resp.get("success"):
            return f"Hooks failed: {hooks_resp.get('error')}"
        hooks = hooks_resp["hooks"]
        hook = hooks[0]
        log.info(f"[POST] Best hook: {hook.get('text', '')[:60]}")

        # === 4. CAROUSEL PLAN ===
        log.info("[POST] 4/6 Carousel plan...")
        plan_resp = await _call("carousel-plan", {
            "tweet": tweet, "research": research, "selectedHook": hook,
        })
        slides = []
        if plan_resp.get("success") and plan_resp.get("plan"):
            slides = plan_resp["plan"].get("slides", [])
        log.info(f"[POST] Plan: {len(slides)} slides")

        # === 5. VISUAL (cover image) ===
        log.info("[POST] 5/6 Cover visual...")
        visual_resp = await _call("visual", {
            "tweet": tweet, "research": research, "selectedHook": hook,
        }, timeout=180)

        cover_url = ""
        config = {}
        if visual_resp.get("success"):
            cover_url = visual_resp.get("imageUrl", "")
            config = visual_resp.get("config", {})
            if cover_url:
                cover_path = _OUTPUT_DIR / f"{query.replace(' ', '_')}_cover.png"
                if await _download_image(cover_url, cover_path):
                    log.info(f"[POST] Cover saved: {cover_path}")

        # === 6. SLIDE IMAGES ===
        log.info("[POST] 6/6 Generating slide images...")
        saved_images = []
        for i, slide in enumerate(slides[:6]):  # Max 6 slides
            slide_type = slide.get("type", "content")
            content = slide.get("content", {})

            resp = await _call("slide-generate", {
                "slideNumber": i + 1,
                "slideType": slide_type,
                "content": content,
            }, timeout=120)

            if resp.get("success") and resp.get("imageUrl"):
                img_path = _OUTPUT_DIR / f"{query.replace(' ', '_')}_slide_{i+1}.png"
                if await _download_image(resp["imageUrl"], img_path):
                    saved_images.append(str(img_path))
                    log.info(f"[POST] Slide {i+1} saved: {img_path}")

        # === COMPILE RESULT ===
        result = [
            "POST INSTAGRAM CAROUSEL CREE",
            f"",
            f"Sujet: {query}",
            f"Tweet: {tweet.get('titleFr', tweet.get('text', ''))[:100]}",
            f"Engagement: {tweet.get('engagement', 'N/A')}",
            f"",
            f"Hook: {hook.get('text', '')}",
            f"Supertitle: {config.get('supertitle', '')}",
            f"",
            f"SLIDES ({len(slides)}):",
        ]
        for i, slide in enumerate(slides):
            result.append(f"  {i+1}. [{slide.get('type','')}] {json.dumps(slide.get('content',{}), ensure_ascii=False)[:150]}")

        result.append(f"")
        result.append(f"IMAGES GENEREES ({len(saved_images)}):")
        for p in saved_images:
            result.append(f"  {p}")
        if cover_url:
            result.append(f"Cover: {cover_url}")

        result.append(f"")
        result.append(f"HOOKS DISPONIBLES:")
        for i, h in enumerate(hooks[:5]):
            result.append(f"  {i+1}. {h.get('text', '')}")

        return "\n".join(result)

    except Exception as e:
        log.error(f"[POST] Error: {e}")
        return f"Pipeline error: {e}"
