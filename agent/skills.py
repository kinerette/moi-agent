"""Skills — learnable, user-addable capabilities that grow over time."""

from __future__ import annotations

import json
from pathlib import Path

from core.log import log

_SKILLS_FILE = Path(__file__).resolve().parent.parent / "skills.json"
_skills: dict[str, dict] = {}


def _load():
    global _skills
    if _SKILLS_FILE.exists():
        _skills = json.loads(_SKILLS_FILE.read_text())
        log.info(f"Loaded {len(_skills)} skills")


def _save():
    _SKILLS_FILE.write_text(json.dumps(_skills, indent=2))


def add_skill(
    name: str,
    description: str,
    instructions: str,
    examples: list[str] | None = None,
) -> dict:
    """Add or update a skill the agent can use."""
    skill = {
        "name": name,
        "description": description,
        "instructions": instructions,
        "examples": examples or [],
        "use_count": 0,
    }
    _skills[name] = skill
    _save()
    log.info(f"Skill added: {name}")
    return skill


def remove_skill(name: str) -> bool:
    if name in _skills:
        del _skills[name]
        _save()
        return True
    return False


def get_skill(name: str) -> dict | None:
    return _skills.get(name)


def list_skills() -> list[dict]:
    return list(_skills.values())


def record_use(name: str):
    """Track skill usage for the snowball effect."""
    if name in _skills:
        _skills[name]["use_count"] += 1
        _save()


def get_skills_prompt() -> str:
    """Generate a prompt section describing available skills."""
    if not _skills:
        return ""

    lines = ["## Learned Skills"]
    for s in _skills.values():
        lines.append(f"- **{s['name']}**: {s['description']}")
        if s["examples"]:
            lines.append(f"  Examples: {', '.join(s['examples'][:3])}")
    return "\n".join(lines)


# Load on import
_load()
