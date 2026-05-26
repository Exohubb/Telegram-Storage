"""
Local development runner using polling instead of webhook.
Use this when running locally without ngrok.

Usage:
    .venv/bin/python run_polling.py
"""

import asyncio

from dotenv import load_dotenv
load_dotenv()

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.core.logging import configure_logging
from src.core.config.settings import get_settings
from src.bot.app import BOT_COMMANDS
from src.bot.callbacks import handle_callback
from src.bot.handlers.commands import (
    cmd_admin, cmd_favorites, cmd_files, cmd_folders,
    cmd_help, cmd_menu, cmd_recent, cmd_search,
    cmd_settings, cmd_setup, cmd_start, cmd_trash, cmd_upload,
)
from src.bot.handlers.messages import handle_message
from src.bot.middleware import resolve_user_middleware
from src.services.storage.storage_service import StorageService

configure_logging()


def _wrap(handler):
    async def wrapped(update, context):
        await resolve_user_middleware(update, context, handler)
    return wrapped


async def main() -> None:
    settings = get_settings()
    print(f"Starting bot in POLLING mode")
    print(f"Bot token: ...{settings.bot_token[-8:]}")

    # Build with updater enabled (no .updater(None))
    app = Application.builder().token(settings.bot_token).build()

    # Register all handlers
    app.add_handler(CommandHandler("start", _wrap(cmd_start)))
    app.add_handler(CommandHandler("menu", _wrap(cmd_menu)))
    app.add_handler(CommandHandler("help", _wrap(cmd_help)))
    app.add_handler(CommandHandler("upload", _wrap(cmd_upload)))
    app.add_handler(CommandHandler("folders", _wrap(cmd_folders)))
    app.add_handler(CommandHandler("files", _wrap(cmd_files)))
    app.add_handler(CommandHandler("search", _wrap(cmd_search)))
    app.add_handler(CommandHandler("favorites", _wrap(cmd_favorites)))
    app.add_handler(CommandHandler("recent", _wrap(cmd_recent)))
    app.add_handler(CommandHandler("trash", _wrap(cmd_trash)))
    app.add_handler(CommandHandler("settings", _wrap(cmd_settings)))
    app.add_handler(CommandHandler("setup", _wrap(cmd_setup)))
    app.add_handler(CommandHandler("admin", _wrap(cmd_admin)))
    app.add_handler(CallbackQueryHandler(_wrap(handle_callback)))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, _wrap(handle_message)))

    await app.initialize()

    # Clear any existing webhook so polling works
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("Webhook cleared")

    # Register bot command menu
    await app.bot.set_my_commands(BOT_COMMANDS)

    # Verify vault channel
    storage = StorageService(app.bot)
    vault_ok = await storage.verify_vault_access()
    if not vault_ok:
        print("WARNING: Vault channel not accessible — set VAULT_CHANNEL_ID in .env")
    else:
        print("Vault channel OK")

    print("Bot is running. Send /start in Telegram.")

    await app.start()
    await app.updater.start_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        print("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
