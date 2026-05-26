"""
Bot middleware: user resolution, ban check, state injection, error handling.
Every update passes through this before reaching a handler.
"""

import traceback
from collections.abc import Callable, Awaitable
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from src.core.errors import AppError, UserBannedError
from src.core.logging import get_logger
from src.db.engine import get_session_factory
from src.bot.container import Container
from src.db.repositories.user_repo import UserSettingsRepository

logger = get_logger(__name__)


async def resolve_user_middleware(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    next_handler: Callable,
) -> None:
    """Resolve or create the user record and attach container to context."""
    tg_user = update.effective_user
    if not tg_user:
        return

    factory = get_session_factory()
    async with factory() as session:
        try:
            container = Container(session, context.bot)
            user, is_new = await container.users.get_or_create_user(
                telegram_user_id=tg_user.id,
                first_name=tg_user.first_name,
                username=tg_user.username,
                last_name=tg_user.last_name,
            )
            # Load per-user vault channel
            settings_repo = UserSettingsRepository(session)
            user_settings = await settings_repo.get_by_user_id(user.id)
            vault_channel_id = user_settings.vault_channel_id if user_settings else None
            container = Container(session, context.bot, vault_channel_id=vault_channel_id)
            context.user_data["db_user"] = user
            context.user_data["is_new_user"] = is_new
            context.user_data["container"] = container
            await next_handler(update, context)
            await session.commit()
        except UserBannedError:
            if update.effective_message:
                await update.effective_message.reply_text(
                    "⛔ Your account has been restricted. Contact support."
                )
        except AppError as e:
            logger.warning("AppError in middleware", code=e.code, message=str(e))
            if update.effective_message:
                await update.effective_message.reply_text(f"⚠️ {e.user_message}")
            await session.rollback()
        except Exception as e:
            logger.error(
                "Unhandled exception in update handler",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            if update.effective_message:
                await update.effective_message.reply_text(
                    "⚠️ An unexpected error occurred. Please try again."
                )
            await session.rollback()


def get_container(context: ContextTypes.DEFAULT_TYPE) -> Container:
    container = context.user_data.get("container")
    if not container:
        raise RuntimeError("Container not initialized — middleware not applied")
    return container
