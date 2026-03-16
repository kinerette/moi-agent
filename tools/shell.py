"""Shell command execution."""

from __future__ import annotations

import asyncio

from tools.registry import tool

# Commands that are never allowed
_BLOCKED = {"rm -rf /", "format", "del /s /q", "shutdown", "reboot"}


@tool(
    name="shell",
    description="Execute a shell command and return its output.",
    parameters={
        "command": {"type": "string", "description": "Shell command to execute"},
    },
)
async def shell(command: str) -> str:
    # Safety check
    cmd_lower = command.lower().strip()
    for blocked in _BLOCKED:
        if blocked in cmd_lower:
            return f"BLOCKED: '{command}' matches blocked pattern '{blocked}'"

    try:
        # For GUI apps, launch detached (don't wait)
        gui_apps = ["notepad", "calc", "mspaint", "explorer", "chrome", "firefox", "code"]
        if any(app in command.lower() for app in gui_apps):
            proc = await asyncio.create_subprocess_shell(
                f"start \"\" {command}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.sleep(2)
            return f"Launched: {command}"

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)

        output = stdout.decode(errors="replace")
        if stderr:
            output += f"\nSTDERR: {stderr.decode(errors='replace')}"
        if proc.returncode != 0:
            output += f"\nExit code: {proc.returncode}"

        return output[:10000]  # Limit output size
    except asyncio.TimeoutError:
        return "Command timed out (60s limit)"
    except Exception as e:
        return f"Error: {e}"
