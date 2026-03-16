"""MOI Agent — Point d'entrée unique. Lance tous les services en parallèle."""

import asyncio
import signal
import sys

from core.config import settings
from core.log import log


async def main():
    log.info("MOI Agent starting...")

    # Import services
    from dashboard.app import start_dashboard
    from tgbot.bot import start_telegram
    from agent.loop import start_agent_loop
    from agent.cron import run_cron_loop

    # Graceful shutdown
    stop_event = asyncio.Event()

    def _shutdown(*_):
        log.info("Shutting down...")
        stop_event.set()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(sig, _shutdown)

    tasks = [
        asyncio.create_task(start_dashboard(stop_event)),
        asyncio.create_task(start_agent_loop(stop_event)),
        asyncio.create_task(run_cron_loop(stop_event)),
    ]

    # Telegram is optional
    if settings.telegram_bot_token:
        tasks.append(asyncio.create_task(start_telegram(stop_event)))
        log.info("Telegram bot enabled")
    else:
        log.warning("TELEGRAM_BOT_TOKEN not set — bot disabled")

    log.info(
        f"Services running: dashboard(:8000), agent-loop, cron"
        f"{', telegram' if settings.telegram_bot_token else ''}"
    )

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        _shutdown()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
