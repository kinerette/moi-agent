"""File operations — read, write, list."""

from __future__ import annotations

from pathlib import Path

from tools.registry import tool


@tool(
    name="file_read",
    description="Read a file and return its contents.",
    parameters={"path": {"type": "string", "description": "File path"}},
)
async def file_read(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"File not found: {path}"
    if not p.is_file():
        return f"Not a file: {path}"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 3000:
            return content[:3000] + f"\n... (truncated, total {len(content)} chars)"
        return content
    except Exception as e:
        return f"Error reading {path}: {e}"


@tool(
    name="file_write",
    description="Write content to a file. Creates directories if needed.",
    parameters={
        "path": {"type": "string", "description": "File path"},
        "content": {"type": "string", "description": "Content to write"},
    },
)
async def file_write(path: str, content: str) -> str:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


@tool(
    name="file_list",
    description="List files in a directory.",
    parameters={
        "path": {"type": "string", "description": "Directory path"},
        "pattern": {"type": "string", "description": "Glob pattern (default: *)"},
    },
)
async def file_list(path: str = ".", pattern: str = "*") -> str:
    p = Path(path)
    if not p.exists():
        return f"Directory not found: {path}"
    if not p.is_dir():
        return f"Not a directory: {path}"

    files = sorted(p.glob(pattern))[:100]
    lines = []
    for f in files:
        kind = "D" if f.is_dir() else "F"
        lines.append(f"[{kind}] {f.name}")
    return "\n".join(lines) if lines else "Empty directory"
