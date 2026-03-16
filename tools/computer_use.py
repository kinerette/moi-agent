"""Computer use — screenshot + PyAutoGUI + Gemini vision."""

from __future__ import annotations

import base64
import io

import mss
import pyautogui
from PIL import Image

from core.log import log
from llm.gemini_vision import analyze_screenshot
from tools.registry import tool

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


def _take_screenshot() -> tuple[bytes, str]:
    """Take a screenshot, return (png_bytes, base64_str)."""
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # Primary monitor
        img = sct.grab(monitor)
        pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")

    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    b64 = base64.b64encode(png_bytes).decode()
    return png_bytes, b64


@tool(
    name="screenshot",
    description="Take a screenshot of the current screen.",
    parameters={},
)
async def screenshot() -> str:
    png_bytes, b64 = _take_screenshot()
    log.info(f"Screenshot taken: {len(png_bytes)} bytes")
    return f"data:image/png;base64,{b64}"


@tool(
    name="screen_analyze",
    description="Take a screenshot and describe what's on screen. Use this to SEE before acting.",
    parameters={
        "question": {"type": "string", "description": "What to look for on screen"},
    },
)
async def screen_analyze(question: str = "") -> str:
    png_bytes, _ = _take_screenshot()
    prompt = question or None
    analysis = await analyze_screenshot(png_bytes, prompt)
    return analysis


@tool(
    name="mouse_click",
    description="Click at screen coordinates (x, y).",
    parameters={
        "x": {"type": "integer", "description": "X coordinate"},
        "y": {"type": "integer", "description": "Y coordinate"},
        "button": {"type": "string", "description": "left/right/middle (default: left)"},
    },
)
async def mouse_click(x: int, y: int, button: str = "left") -> str:
    pyautogui.click(x, y, button=button)
    return f"Clicked ({x}, {y}) with {button} button"


@tool(
    name="mouse_move",
    description="Move mouse to screen coordinates (x, y).",
    parameters={
        "x": {"type": "integer", "description": "X coordinate"},
        "y": {"type": "integer", "description": "Y coordinate"},
    },
)
async def mouse_move(x: int, y: int) -> str:
    pyautogui.moveTo(x, y)
    return f"Mouse moved to ({x}, {y})"


@tool(
    name="keyboard_type",
    description="Type text using the keyboard.",
    parameters={
        "text": {"type": "string", "description": "Text to type"},
    },
)
async def keyboard_type(text: str) -> str:
    pyautogui.write(text, interval=0.02)
    return f"Typed: {text[:50]}..."


@tool(
    name="keyboard_press",
    description="Press a key or key combination (e.g., 'enter', 'ctrl+c').",
    parameters={
        "keys": {"type": "string", "description": "Key(s) to press"},
    },
)
async def keyboard_press(keys: str) -> str:
    if "+" in keys:
        parts = [k.strip() for k in keys.split("+")]
        pyautogui.hotkey(*parts)
    else:
        pyautogui.press(keys)
    return f"Pressed: {keys}"


@tool(
    name="wait",
    description="Wait for a number of seconds.",
    parameters={
        "seconds": {"type": "integer", "description": "Seconds to wait"},
    },
)
async def wait(seconds: int = 3) -> str:
    import asyncio
    await asyncio.sleep(min(seconds, 30))
    return f"Waited {seconds}s"


@tool(
    name="focus_app",
    description="Bring an application window to the front. Use 'chrome' for Chrome, 'code' for VS Code, etc.",
    parameters={
        "app_name": {"type": "string", "description": "App name (chrome, code, notepad, etc.)"},
    },
)
async def focus_app(app_name: str) -> str:
    import subprocess, asyncio
    # PowerShell: find, MAXIMIZE, and activate window
    script = f'''
    Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    public class Win32 {{
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    }}
"@
    $procs = Get-Process | Where-Object {{ $_.MainWindowTitle -ne "" -and $_.ProcessName -like "*{app_name}*" }}
    if ($procs) {{
        $hwnd = $procs[0].MainWindowHandle
        [Win32]::ShowWindow($hwnd, 3)  # SW_MAXIMIZE (not just restore — MAXIMIZE)
        Start-Sleep -Milliseconds 300
        [Win32]::SetForegroundWindow($hwnd)
        Write-Host "Focused+Maximized: $($procs[0].ProcessName) - $($procs[0].MainWindowTitle)"
    }} else {{
        Write-Host "App not found: {app_name}"
    }}
    '''
    result = subprocess.run(["powershell", "-Command", script], capture_output=True, text=True, timeout=10)
    output = (result.stdout + result.stderr).strip()
    await asyncio.sleep(0.5)
    log.info(f"Focus: {output}")
    return output or f"Focused {app_name}"
