"""Agent loop v2 — todo-list + self-check + real-time progress."""

from __future__ import annotations

import asyncio
import json

from core.log import log
from core.models import Task, TaskStatus, ChatMessage
from core.events import publish, subscribe, EVT_TASK_CREATED, EVT_TASK_UPDATED, EVT_CHAT_MESSAGE, EVT_APPROVAL_NEEDED, EVT_APPROVAL_RESPONSE
from agent.safety import needs_approval, classify
from agent.skills import get_skills_prompt
from llm.claude import claude_client
from llm import router as llm_router
from memory.context import add_message, build_context
from memory import store as memory_store
from tools.registry import execute, list_tools

_task_queue: asyncio.Queue[Task] = asyncio.Queue()
_active_task: Task | None = None
_approval_event: asyncio.Event = asyncio.Event()
_approval_result: bool = False

_SYSTEM = (
    "Agent IA autonome. PC + Chrome (comptes connectes). AGIS, jamais de refus.\n"
    "Outils: web_search, web_scrape, browser_navigate(silencieux), shell, file_read/write,\n"
    "screen_analyze (donne coordonnees des elements), mouse_click, keyboard_type, focus_app, wait.\n"
    "IMPORTANT pour computer use: TOUJOURS faire focus_app('chrome') AVANT de cliquer dans Chrome.\n"
    "screen_analyze donne les coordonnees (x,y) de chaque element. Utilise-les pour mouse_click.\n"
    "REGLES: Parallele quand possible. Max 4 tours. Rapport detaille (jamais 'Done').\n"
)


async def submit_task(instruction: str, source: str = "dashboard") -> Task:
    task = Task(instruction=instruction, source=source)
    await _task_queue.put(task)
    await publish(EVT_TASK_CREATED, task)
    log.info(f"Task submitted: {instruction[:60]} [{task.id}]")
    return task


def _is_actionable(msg: str) -> bool:
    msg_lower = msg.lower()
    signals = [
        "va sur", "ouvre", "navigue", "cherche", "trouve",
        "go to", "open", "navigate", "search", "find",
        "clique", "click", "tape", "type", "ecris", "write",
        "screenshot", "capture", "regarde", "look",
        "telecharge", "download", "installe", "install",
        "execute", "lance", "run", "fais", "do",
        "envoie", "send", "poste", "post",
        "scrape", "browse", "surf",
        "ameliore", "autoameliore",
        "cree", "create", "genere", "generate",
        "supprime", "delete", "remove",
        "verifie", "check", "analyse", "analyze",
        "liste", "list", "montre", "show",
    ]
    return any(s in msg_lower for s in signals)


async def _send_progress(msg: str):
    """Send a progress update to the dashboard in real-time."""
    await publish(EVT_CHAT_MESSAGE, ChatMessage(
        role="assistant", content=f"[...] {msg}", model_used="system"
    ))


async def handle_chat(message: str, source: str = "dashboard") -> str:
    add_message(ChatMessage(role="user", content=message))

    if _is_actionable(message):
        log.info(f"Task detected: {message[:60]}")
        task = Task(instruction=message, source=source)
        await _execute_task(task)
        result = task.result if task.result else "Aucun resultat obtenu."
        add_message(ChatMessage(role="assistant", content=result, model_used="claude"))
        return result

    # Simple chat
    context = await build_context(message)
    system = "Tu es MOI, un agent IA autonome et proactif. Reponds en francais, sois direct.\n"
    if context:
        system += f"\n{context}"

    response, model = await llm_router.chat(message, system=system)
    add_message(ChatMessage(role="assistant", content=response, model_used=model))
    await publish(EVT_CHAT_MESSAGE, ChatMessage(role="assistant", content=response, model_used=model))
    return response


async def _handle_approval(data):
    global _approval_result
    _approval_result = bool(data)
    _approval_event.set()


async def _execute_task(task: Task):
    global _active_task
    _active_task = task
    task.status = TaskStatus.RUNNING
    await publish(EVT_TASK_UPDATED, task)

    # Collect all tool outputs for the final summary
    tool_log = []

    try:
        skills_section = get_skills_prompt()
        system = _SYSTEM
        if skills_section:
            system += f"\n{skills_section}\n"

        messages = [{"role": "user", "content": task.instruction}]
        tools = list_tools()

        for turn in range(20):  # 12 turns — enough for computer use workflows
            log.info(f"Turn {turn + 1}/12")

            result = await claude_client.chat(
                messages=messages, tools=tools, system=system,
            )

            stop_reason = result.get("stop_reason")
            content_blocks = result.get("content", [])

            assistant_content = []
            tool_uses = []
            for block in content_blocks:
                if block["type"] == "text":
                    assistant_content.append(block)
                    text = block.get("text", "").strip()
                    if text:
                        task.result = text
                elif block["type"] == "tool_use":
                    tool_uses.append(block)
                    assistant_content.append(block)

            messages.append({"role": "assistant", "content": assistant_content})

            # No more tools → done
            if not tool_uses or stop_reason == "end_turn":
                break

            # Execute ALL tools in PARALLEL (massive speed boost)
            async def _run_tool(tu):
                tool_name = tu["name"]
                tool_args = tu.get("input", {})

                # Safety gate
                action_desc = f"{tool_name}({json.dumps(tool_args, ensure_ascii=False)[:80]})"
                if needs_approval(action_desc):
                    log.warning(f"Approval needed: {action_desc}")
                    await _send_progress(f"Approbation requise: {action_desc}")
                    task.status = TaskStatus.WAITING_APPROVAL
                    await publish(EVT_APPROVAL_NEEDED, {
                        "task_id": task.id, "action": action_desc,
                        "safety": classify(action_desc).value,
                    })
                    _approval_event.clear()
                    try:
                        await asyncio.wait_for(_approval_event.wait(), timeout=120)
                    except asyncio.TimeoutError:
                        return {"type": "tool_result", "tool_use_id": tu["id"],
                                "content": "Timeout — action annulee."}
                    if not _approval_result:
                        return {"type": "tool_result", "tool_use_id": tu["id"],
                                "content": "Action refusee."}
                    task.status = TaskStatus.RUNNING

                log.info(f"Tool: {tool_name}")
                result_obj = await execute(tool_name, tool_args)
                output = result_obj.output

                if output.startswith("data:image/png;base64,"):
                    output = "Screenshot taken. Use screen_analyze to see."

                # AUTO-VERIFY: after click/type actions, auto screenshot+analyze
                _ui_actions = {"mouse_click", "keyboard_type", "keyboard_press", "focus_app"}
                if tool_name in _ui_actions:
                    import asyncio as _aio
                    await _aio.sleep(1)  # Wait for UI to update
                    verify = await execute("screen_analyze", {"question": "Decris brievement ce qui est visible. Donne les coordonnees des elements cliquables."})
                    output += f"\n\n[AUTO-VERIFY apres {tool_name}]\n{verify.output[:800]}"

                # Condense long outputs to save tokens (avoid rate limits)
                if len(output) > 2000:
                    output = output[:2000] + "\n...(truncated)"

                tool_log.append(f"{tool_name}: {output[:200]}")
                return {"type": "tool_result", "tool_use_id": tu["id"],
                        "content": output}

            # Run all tool calls at once
            names = [tu["name"] for tu in tool_uses]
            await _send_progress(f"{', '.join(names)}...")
            tool_results = await asyncio.gather(*[_run_tool(tu) for tu in tool_uses])

            messages.append({"role": "user", "content": tool_results})

        # === SELF-CHECK: ALWAYS verify the result is actually useful ===
        bad_results = {"", "done.", "done", "termine.", "termine", "ok", "ok."}
        result_lower = (task.result or "").strip().lower()
        incomplete_signals = [
            "je vais", "laissez-moi", "laisse-moi", "parfait", "excellent",
            "d'accord", "plus de details", "plus de détails",
            "je continue", "en cours", "je cherche", "attendez",
        ]
        result_is_bad = (
            result_lower in bad_results
            or len(task.result or "") < 50
            or any(sig in result_lower for sig in incomplete_signals)
        )
        if result_is_bad:
            log.info("Result was empty/useless — forcing summary via Qwen...")
            tool_summary = "\n".join(tool_log[-10:]) if tool_log else "Aucun outil appele."
            from llm import openrouter
            task.result = await openrouter.chat(
                prompt=(
                    f"DEMANDE ORIGINALE: {task.instruction}\n\n"
                    f"DONNEES RECOLTEES PAR LES OUTILS:\n{tool_summary}\n\n"
                    f"Compile ces donnees en un rapport clair et complet qui repond a la demande. "
                    f"Donne les noms, liens, chiffres concrets. "
                    f"Ne dis JAMAIS 'je vais' ou 'laisse-moi' — donne les RESULTATS."
                ),
                system="Tu es un compilateur de donnees. Tu recois des resultats bruts et tu les transformes en rapport structure. Reponds en francais.",
            )

        # Final fallback
        if not task.result or task.result.strip().lower() in bad_results:
            task.result = "Tache executee mais aucun resultat exploitable. Reformule ta demande."

        task.status = TaskStatus.DONE
        log.info(f"Task done: {task.id} — {task.result[:80]}")

        # Save to memory
        try:
            await memory_store.add(
                content=f"Task: {task.instruction}\nResult: {task.result[:500]}",
                metadata={"task_id": task.id, "source": task.source},
            )
        except Exception:
            pass

    except Exception as e:
        task.status = TaskStatus.FAILED
        task.result = f"Erreur: {e}"
        log.error(f"Task failed: {task.id} — {e}")

    finally:
        _active_task = None
        await publish(EVT_TASK_UPDATED, task)


async def start_agent_loop(stop_event: asyncio.Event):
    subscribe(EVT_APPROVAL_RESPONSE, _handle_approval)

    import tools.web_search
    import tools.web_scrape
    import tools.browser
    import tools.shell
    import tools.file_ops
    import tools.computer_use
    import tools.skip_permission

    log.info("Agent loop started")

    while not stop_event.is_set():
        try:
            task = await asyncio.wait_for(_task_queue.get(), timeout=1.0)
            await _execute_task(task)
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            log.error(f"Agent loop error: {e}")
            await asyncio.sleep(1)

    log.info("Agent loop stopped")


def get_active_task() -> Task | None:
    return _active_task

def get_queue_size() -> int:
    return _task_queue.qsize()
