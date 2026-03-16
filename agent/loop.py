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
    "Tu es MOI, un agent IA autonome. Controle total du PC + Chrome (comptes connectes).\n\n"
    "OUTILS WEB (rapides, silencieux — pas d'ouverture Chrome):\n"
    "- browser_navigate(url): fetch une URL, retourne le texte. PAS d'onglet ouvert.\n"
    "- web_search(query): recherche Google. Retourne les resultats.\n"
    "- web_scrape(url): scrape une page en markdown.\n"
    "- browser_open_visible(url): ouvre Chrome UNIQUEMENT si l'user veut VOIR.\n\n"
    "OUTILS DESKTOP:\n"
    "- screen_analyze(question): screenshot + vision IA. Pour voir l'ecran.\n"
    "- mouse_click(x,y) / keyboard_type(text) / keyboard_press(keys): controle PC.\n"
    "- shell(command): commande systeme. ATTENTION: pip install necessite approbation.\n"
    "- file_read(path) / file_write(path,content): fichiers.\n\n"
    "REGLES ABSOLUES:\n"
    "- AGIS. Jamais de refus. Tu es l'agent de l'utilisateur.\n"
    "- Quand tu as fini, donne un RAPPORT DETAILLE: ce que tu as fait, ce que tu as trouve, le resultat.\n"
    "- Si tu cherches quelque chose, donne les RESULTATS CONCRETS (noms, liens, chiffres).\n"
    "- NE DIS JAMAIS juste 'Done' ou 'Termine'. Donne TOUJOURS les details.\n"
    "- Sois RAPIDE: fais 1 web_search large, puis 1-2 web_scrape cibles. PAS 10 recherches.\n"
    "- Quand tu as les donnees, ARRETE de chercher et donne le resultat.\n"
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

        for turn in range(10):
            log.info(f"Turn {turn + 1}/10")

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

            # Execute tools
            tool_results = []
            for tu in tool_uses:
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
                        await asyncio.wait_for(_approval_event.wait(), timeout=300)
                    except asyncio.TimeoutError:
                        tool_results.append({"type": "tool_result", "tool_use_id": tu["id"],
                                             "content": "Timeout — action annulee."})
                        continue
                    if not _approval_result:
                        tool_results.append({"type": "tool_result", "tool_use_id": tu["id"],
                                             "content": "Action refusee par l'utilisateur."})
                        continue
                    task.status = TaskStatus.RUNNING

                # Execute
                log.info(f"Tool: {tool_name}")
                await _send_progress(f"{tool_name}...")
                result_obj = await execute(tool_name, tool_args)
                output = result_obj.output

                # Don't send raw screenshots to Claude
                if output.startswith("data:image/png;base64,"):
                    output = "Screenshot taken. Use screen_analyze to see what's on screen."

                tool_log.append(f"{tool_name}: {output[:200]}")
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu["id"],
                    "content": output[:5000],
                })

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
