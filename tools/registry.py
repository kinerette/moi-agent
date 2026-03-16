"""Tool registry — decorator-based registration."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from core.log import log
from core.models import ToolResult

_TOOLS: dict[str, dict] = {}


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
):
    """Decorator to register a tool."""
    def decorator(func: Callable):
        _TOOLS[name] = {
            "name": name,
            "description": description,
            "parameters": parameters or {},
            "func": func,
        }
        return func
    return decorator


async def execute(name: str, args: dict[str, Any] | None = None) -> ToolResult:
    """Execute a registered tool by name."""
    if name not in _TOOLS:
        return ToolResult(name=name, output=f"Unknown tool: {name}", success=False)

    func = _TOOLS[name]["func"]
    args = args or {}

    try:
        if inspect.iscoroutinefunction(func):
            output = await func(**args)
        else:
            output = func(**args)
        return ToolResult(name=name, output=str(output), success=True)
    except Exception as e:
        log.error(f"Tool {name} failed: {e}")
        return ToolResult(name=name, output=str(e), success=False)


def list_tools() -> list[dict]:
    """Return tool definitions for Claude tool_use."""
    result = []
    for name, info in _TOOLS.items():
        schema = {
            "name": name,
            "description": info["description"],
            "input_schema": {
                "type": "object",
                "properties": info["parameters"],
            },
        }
        result.append(schema)
    return result


def get_tool_names() -> list[str]:
    return list(_TOOLS.keys())
