"""
Bot application factory: builds the PTB Application with all handlers registered.
"""

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.bot.callbacks import handle_callback
from src.bot.handlers.commands import (
    cmd_admin,
    cmd_favorites,
    cmd_files,
    cmd_folders,
    cmd_help,
    cmd_menu,
    cmd_recent,
    cmd_search,
    cmd_settings,
    cmd_setup,
    cmd_start,
    cmd_trash,
    cmd_upload,
)
from src.bot.handlers.messages import handle_message
from src.bot.middleware import resolve_user_middleware
from src.core.config.settings import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

BOT_COMMANDS = [
    BotCommand("start", "Home dashboard"),
    BotCommand("menu", "Open main menu"),
    BotCommand("upload", "Upload a file"),
    BotCommand("folders", "Browse folders"),
    BotCommand("files", "Browse all files"),
    BotCommand("search", "Search files"),
    BotCommand("favorites", "Starred files"),
    BotCommand("recent", "Recently uploaded"),
    BotCommand("trash", "Deleted files"),
    BotCommand("settings", "Bot settings"),
    BotCommand("setup", "Vault setup wizard"),
    BotCommand("help", "How to use this bot"),
]


def _wrap(handler):
    """Wrap a handler with the user-resolution middleware."""
    async def wrapped(update, context):
        await resolve_user_middleware(update, context, handler)
    return wrapped


def create_bot_app() -> Application:
    settings = get_settings()

    app = (
        Application.builder()
        .token(settings.bot_token)
        .updater(None)  # Webhook mode — no polling
        .build()
    )

    # Commands
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

    # Callback queries (inline buttons)
    app.add_handler(CallbackQueryHandler(_wrap(handle_callback)))

    # All other messages (files + text input for state flows)
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            _wrap(handle_message),
        )
    )

    return app


async def setup_webhook(app: Application) -> None:
    settings = get_settings()
    await app.bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.bot_webhook_secret,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Webhook configured", url=settings.webhook_url)
