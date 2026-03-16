"""Route requests to Claude or OpenRouter based on task type."""

from __future__ import annotations

from core.log import log
from llm import openrouter
from llm.claude import claude_client


# Short, trivial messages that OpenRouter (Qwen) can handle fast and cheap
_TRIVIAL_PATTERNS = {
    "salut", "hello", "bonjour", "hey", "coucou", "yo", "sasa",
    "ca va", "ça va", "quoi de neuf", "comment tu vas",
    "quelle heure", "quel jour", "quel temps",
    "merci", "ok", "d'accord", "oui", "non",
}


def _is_trivial(msg: str) -> bool:
    msg_clean = msg.lower().strip().rstrip("?!. ")
    if len(msg_clean) < 15 and any(p in msg_clean for p in _TRIVIAL_PATTERNS):
        return True
    if len(msg_clean.split()) <= 2 and any(p in msg_clean for p in _TRIVIAL_PATTERNS):
        return True
    return False


async def chat(prompt: str, system: str = "", force_claude: bool = False) -> tuple[str, str]:
    """Route chat. Claude by default, Qwen for trivial only."""
    if force_claude or not _is_trivial(prompt):
        log.info("Routing >> Claude")
        resp = await claude_client.ask(prompt, system=system)
        return resp, "claude"
    else:
        log.info("Routing >> Qwen (trivial)")
        resp = await openrouter.chat(prompt, system=system)
        return resp, "qwen"


async def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    system: str = "",
) -> dict:
    """Always use Claude for tool use."""
    return await claude_client.chat(
        messages=messages,
        tools=tools,
        system=system,
    )
