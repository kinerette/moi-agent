"""Dashboard — FastAPI + HTMX + WebSocket."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import uvicorn

from core.config import settings
from core.log import log, LOG_BUFFER
from core.events import subscribe, EVT_CHAT_MESSAGE, EVT_TASK_UPDATED, EVT_APPROVAL_NEEDED
from agent.loop import submit_task, handle_chat
from agent.cron import add_job, remove_job, list_jobs, toggle_job
from agent.skills import add_skill, remove_skill, list_skills

_DIR = Path(__file__).parent
app = FastAPI(title="MOI Agent")
app.mount("/static", StaticFiles(directory=str(_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(_DIR / "templates"))

# Active WebSocket connections
_ws_clients: set[WebSocket] = set()


async def _broadcast(event: str, data: dict):
    """Broadcast event to all WebSocket clients."""
    msg = json.dumps({"event": event, **data})
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _ws_clients -= dead


# Subscribe to events for real-time updates
async def _on_chat(msg):
    await _broadcast("chat", {
        "role": msg.role,
        "content": msg.content,
        "model": msg.model_used,
    })

async def _on_task(task):
    await _broadcast("task", {
        "id": task.id,
        "status": task.status.value,
        "instruction": task.instruction[:100],
        "result": task.result[:500] if task.result else "",
        "steps": task.steps,
        "current_step": task.current_step,
    })

async def _on_approval(data):
    await _broadcast("approval", data)

subscribe(EVT_CHAT_MESSAGE, _on_chat)
subscribe(EVT_TASK_UPDATED, _on_task)
subscribe(EVT_APPROVAL_NEEDED, _on_approval)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/welcome")
async def get_welcome():
    """Generate a personalized welcome message."""
    from datetime import datetime
    from llm import openrouter
    from memory.store import get_stats

    now = datetime.now()
    hour = now.hour
    day = now.strftime("%A")
    date = now.strftime("%d %B %Y")
    stats = get_stats()

    prompt = f"""Tu es MOI, l'agent IA personnel de l'utilisateur. Génère un message d'accueil court et percutant (2-3 phrases max).

Contexte:
- Il est {hour}h, {day} {date}
- L'agent a {stats['memories']} souvenirs en mémoire et a complété {stats['tasks_completed']} tâches
- Tu es un agent autonome et proactif, pas un simple chatbot
- Ton ton: confiant, direct, un peu stylé — comme un co-fondateur IA qui bosse pour lui

Règles:
- Adapte le message au moment de la journée (matin motivant, après-midi productif, soir récap)
- Si c'est le premier lancement (0 tâches), dis quelque chose sur le fait que c'est le début d'une aventure
- Jamais de "Comment puis-je vous aider?" — trop générique
- JAMAIS d'emoji
- Max 200 caractères"""

    try:
        message = await openrouter.chat(prompt)
        return {"message": message.strip()}
    except Exception:
        greetings = {
            range(5, 12): "Nouveau jour, nouvelles conquetes. On attaque quoi?",
            range(12, 18): "L'apres-midi est a nous. Balance ta prochaine mission.",
            range(18, 23): "Session du soir. Les meilleures idees arrivent maintenant.",
        }
        for hours, msg in greetings.items():
            if hour in hours:
                return {"message": msg}
        return {"message": "Pret. Dis-moi ce qu'on fait."}


@app.post("/chat")
async def post_chat(request: Request):
    data = await request.json()
    message = data.get("message", "").strip()
    if not message:
        return {"error": "Empty message"}

    # Check if it should be a task
    if message.startswith("/task "):
        task = await submit_task(message[6:], source="dashboard")
        return {"type": "task", "task_id": task.id}

    response = await handle_chat(message, source="dashboard")
    return {"type": "chat", "content": response}


@app.post("/task")
async def post_task(request: Request):
    data = await request.json()
    instruction = data.get("instruction", "").strip()
    if not instruction:
        return {"error": "Empty instruction"}

    task = await submit_task(instruction, source="dashboard")
    return {"task_id": task.id, "status": task.status.value}


@app.post("/approve")
async def post_approve(request: Request):
    from core.events import publish, EVT_APPROVAL_RESPONSE
    data = await request.json()
    approved = data.get("approved", False)
    await publish(EVT_APPROVAL_RESPONSE, approved)
    return {"ok": True}


@app.get("/logs")
async def get_logs():
    return list(LOG_BUFFER)[-50:]


# --- Cron Jobs API ---

@app.get("/cron")
async def get_cron_jobs():
    return list_jobs()


@app.post("/cron")
async def post_cron_job(request: Request):
    data = await request.json()
    job = add_job(
        name=data["name"],
        instruction=data["instruction"],
        interval_minutes=data.get("interval_minutes", 60),
    )
    return job


@app.delete("/cron/{name}")
async def delete_cron_job(name: str):
    return {"removed": remove_job(name)}


@app.post("/cron/{name}/toggle")
async def toggle_cron(name: str, request: Request):
    data = await request.json()
    return {"toggled": toggle_job(name, data.get("enabled", True))}


# --- Skills API ---

@app.get("/skills")
async def get_skills():
    return list_skills()


@app.post("/skills")
async def post_skill(request: Request):
    data = await request.json()
    skill = add_skill(
        name=data["name"],
        description=data["description"],
        instructions=data["instructions"],
        examples=data.get("examples", []),
    )
    return skill


@app.delete("/skills/{name}")
async def delete_skill(name: str):
    return {"removed": remove_skill(name)}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    log.info(f"WebSocket client connected ({len(_ws_clients)} total)")
    try:
        while True:
            await ws.receive_text()  # Keep alive
    except WebSocketDisconnect:
        _ws_clients.discard(ws)
        log.info(f"WebSocket client disconnected ({len(_ws_clients)} total)")


async def start_dashboard(stop_event: asyncio.Event):
    """Start the FastAPI dashboard."""
    import webbrowser
    import socket

    # Kill anything on the port first
    port = settings.dashboard_port
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        if result == 0:
            import subprocess
            subprocess.run(
                f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :{port} ^| findstr LISTENING\') do taskkill /F /PID %a',
                shell=True, capture_output=True,
            )
            await asyncio.sleep(1)
    except Exception:
        pass

    config = uvicorn.Config(
        app,
        host=settings.dashboard_host,
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    url = f"http://{settings.dashboard_host}:{port}"
    log.info(f"Dashboard: {url}")

    serve_task = asyncio.create_task(server.serve())

    # Auto-open browser after a short delay
    await asyncio.sleep(1.5)
    webbrowser.open(url)

    await stop_event.wait()
    server.should_exit = True
    await serve_task

    log.info("Dashboard stopped")
