"""Safety — classify actions and gate dangerous ones."""

from __future__ import annotations

from core.models import SafetyLevel

# Patterns that indicate dangerous actions
_DANGEROUS_PATTERNS = [
    "delete", "remove", "drop", "format", "shutdown", "reboot",
    "purchase", "buy", "pay", "send email", "send message",
    "post to", "publish", "deploy", "push",
    "rm -rf", "del /s",
    "pip install", "pip uninstall", "npm install",  # Don't break the venv
]

_MODERATE_PATTERNS = [
    "install", "download", "write file", "modify",
    "create", "update", "execute", "run",
]


def classify(action: str) -> SafetyLevel:
    """Classify an action's safety level."""
    action_lower = action.lower()

    for pattern in _DANGEROUS_PATTERNS:
        if pattern in action_lower:
            return SafetyLevel.DANGEROUS

    for pattern in _MODERATE_PATTERNS:
        if pattern in action_lower:
            return SafetyLevel.MODERATE

    return SafetyLevel.SAFE


def needs_approval(action: str) -> bool:
    """Only dangerous actions need explicit approval."""
    return classify(action) == SafetyLevel.DANGEROUS
