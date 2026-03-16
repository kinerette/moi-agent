"""Safety — classify actions and gate dangerous ones."""

from __future__ import annotations

from core.models import SafetyLevel

# Tools that ALWAYS need approval
_DANGEROUS_TOOLS = {
    "shell",  # Only when command matches dangerous patterns
}

# Shell commands that need approval
_DANGEROUS_COMMANDS = [
    "pip install", "pip uninstall", "npm install",
    "rm -rf", "del /s", "format", "shutdown", "reboot",
    "git push", "git reset --hard",
]

# These tools are ALWAYS safe — never block them
_SAFE_TOOLS = {
    "web_search", "web_scrape", "browser_navigate", "browser_open_visible",
    "browser_get_text", "browser_get_links",
    "screenshot", "screen_analyze",
    "file_read", "file_list", "file_write",
    "mouse_click", "mouse_move", "keyboard_type", "keyboard_press",
}


def classify(action: str) -> SafetyLevel:
    action_lower = action.lower()

    # Extract tool name (before the parenthesis)
    tool_name = action_lower.split("(")[0].strip()

    # Safe tools are never blocked
    if tool_name in _SAFE_TOOLS:
        return SafetyLevel.SAFE

    # Shell commands — check the command content
    if tool_name == "shell":
        for pattern in _DANGEROUS_COMMANDS:
            if pattern in action_lower:
                return SafetyLevel.DANGEROUS

    return SafetyLevel.SAFE


def needs_approval(action: str) -> bool:
    return classify(action) == SafetyLevel.DANGEROUS
