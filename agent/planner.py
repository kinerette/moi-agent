"""Planner — decomposes objectives into steps using Claude."""

from __future__ import annotations

from llm.claude import claude_client
from core.log import log

_SYSTEM = """You are a task planner for an autonomous AI agent.
Given a user objective, break it down into concrete, actionable steps.
Each step should be a single tool call or a simple action.

Available tools:
- web_search: Search the web
- web_scrape: Scrape a URL to markdown
- browser_navigate: Open a URL in browser
- browser_screenshot: Screenshot the browser
- browser_click: Click a CSS selector
- browser_type: Type into a CSS selector
- browser_get_text: Get page text
- shell: Execute shell command
- file_read: Read a file
- file_write: Write a file
- file_list: List directory contents
- screenshot: Screenshot the screen
- screen_analyze: Screenshot + Gemini vision analysis
- mouse_click: Click at coordinates
- mouse_move: Move mouse
- keyboard_type: Type text
- keyboard_press: Press keys

Return ONLY a JSON array of step descriptions. Example:
["Search for current weather in Paris", "Format the results as a summary"]
"""


async def plan(objective: str) -> list[str]:
    """Break an objective into steps."""
    try:
        response = await claude_client.ask(
            prompt=f"Break this objective into steps:\n\n{objective}",
            system=_SYSTEM,
        )

        # Parse JSON array from response
        import json
        # Find JSON array in response
        text = response.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            steps = json.loads(text[start:end])
            if isinstance(steps, list):
                log.info(f"Planned {len(steps)} steps for: {objective[:50]}")
                return [str(s) for s in steps]

        # Fallback: treat whole response as single step
        return [objective]
    except Exception as e:
        log.error(f"Planning failed: {e}")
        return [objective]
