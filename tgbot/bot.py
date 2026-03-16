"""Telegram bot — remote control interface."""

from __future__ import annotations

import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from core.config import settings
from core.log import log
from core.events import subscribe, publish, EVT_APPROVAL_NEEDED, EVT_APPROVAL_RESPONSE
from agent.loop import submit_task, handle_chat, get_active_task, get_queue_size


def _authorized(func):
    """Only allow configured chat ID."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if settings.telegram_chat_id and str(update.effective_chat.id) != settings.telegram_chat_id:
            await update.message.reply_text("Unauthorized.")
            return
        return await func(update, context)
    return wrapper


@_authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "MOI Agent connected.\n\n"
        "Commands:\n"
        "/task <instruction> — Submit a task\n"
        "/status — Current status\n"
        "Or just send a message to chat."
    )


@_authorized
async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    instruction = " ".join(context.args) if context.args else ""
    if not instruction:
        await update.message.reply_text("Usage: /task <instruction>")
        return

    task = await submit_task(instruction, source="telegram")
    await update.message.reply_text(f"Task submitted: {task.id}\n{instruction[:100]}")


@_authorized
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = get_active_task()
    queue_size = get_queue_size()

    if active:
        status = (
            f"Active task: {active.id}\n"
            f"Status: {active.status.value}\n"
            f"Step: {active.current_step}/{len(active.steps)}\n"
            f"Queue: {queue_size} pending"
        )
    else:
        status = f"No active task. Queue: {queue_size} pending"

    await update.message.reply_text(status)


@_authorized
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages as chat."""
    text = update.message.text
    if not text:
        return

    response = await handle_chat(text, source="telegram")

    # Split long messages
    for i in range(0, len(response), 4000):
        await update.message.reply_text(response[i:i + 4000])


async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approval button presses."""
    query = update.callback_query
    await query.answer()

    approved = query.data == "approve_yes"
    await publish(EVT_APPROVAL_RESPONSE, approved)

    result = "Approved" if approved else "Denied"
    await query.edit_message_text(f"Action {result}.")


_app: Application | None = None


async def _send_approval_request(data):
    """Send approval request to Telegram."""
    if not _app or not settings.telegram_chat_id:
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes", callback_data="approve_yes"),
            InlineKeyboardButton("No", callback_data="approve_no"),
        ]
    ])

    text = (
        f"Approval needed\n\n"
        f"Task: {data.get('task_id', '?')}\n"
        f"Action: {data.get('action', '?')}\n"
        f"Safety: {data.get('safety', '?')}"
    )

    await _app.bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=text,
        reply_markup=keyboard,
    )


async def start_telegram(stop_event: asyncio.Event):
    """Start the Telegram bot."""
    global _app

    if not settings.telegram_bot_token:
        log.warning("Telegram bot token not set — skipping")
        return

    _app = Application.builder().token(settings.telegram_bot_token).build()

    _app.add_handler(CommandHandler("start", cmd_start))
    _app.add_handler(CommandHandler("task", cmd_task))
    _app.add_handler(CommandHandler("status", cmd_status))
    _app.add_handler(CallbackQueryHandler(handle_approval_callback))
    _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    subscribe(EVT_APPROVAL_NEEDED, _send_approval_request)

    log.info("Telegram bot starting...")

    await _app.initialize()
    await _app.start()
    await _app.updater.start_polling()

    # Wait until stop
    await stop_event.wait()

    await _app.updater.stop()
    await _app.stop()
    await _app.shutdown()

    log.info("Telegram bot stopped")
