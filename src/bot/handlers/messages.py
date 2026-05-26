"""
Message handler: processes incoming file uploads and text input
based on the user's current state.
"""

import asyncio

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.bot.container import Container
from src.bot.formatters import (
    fmt_error,
    fmt_file_renamed,
    fmt_folder_created,
    fmt_folder_renamed,
    fmt_search_prompt,
    fmt_search_results,
    fmt_tag_added,
    fmt_upload_ready,
    fmt_upload_success,
    fmt_upload_choose_folder,
)
from src.bot.keyboards import (
    file_detail_keyboard,
    home_keyboard,
    search_results_keyboard,
    search_type_keyboard,
    upload_cancel_keyboard,
    upload_folder_picker_keyboard,
)
from src.core.config.settings import get_settings
from src.core.constants import UserState
from src.core.errors import AppError, ValidationError
from src.core.logging import get_logger

logger = get_logger(__name__)

_FILE_TYPES = {"document", "photo", "video", "audio", "voice", "video_note", "animation", "sticker"}


def _has_file(msg) -> bool:
    if msg is None:
        return False
    return any(getattr(msg, t, None) for t in _FILE_TYPES)


def _get(context: ContextTypes.DEFAULT_TYPE) -> Container:
    return context.user_data["container"]


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = context.user_data["db_user"]
    c = _get(context)
    state = user.state

    if _has_file(update.message):
        await _handle_file_upload(update, context, c, user)
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    if state == UserState.SEARCHING:
        await _handle_search_text(update, context, c, user, text)
    elif state == UserState.CREATING_FOLDER:
        await _handle_create_folder(update, context, c, user, text)
    elif state == UserState.RENAMING_FOLDER:
        await _handle_rename_folder(update, context, c, user, text)
    elif state == UserState.RENAMING_FILE:
        await _handle_rename_file(update, context, c, user, text)
    elif state == UserState.ADDING_TAGS:
        await _handle_add_tag(update, context, c, user, text)
    elif state == UserState.SETUP_WAITING_ID:
        await _handle_setup_vault_id(update, context, c, user, text)
    else:
        # Idle — show home
        from src.bot.formatters import fmt_home
        await update.message.reply_text(
            fmt_home(), parse_mode=ParseMode.HTML, reply_markup=home_keyboard()
        )


async def _handle_file_upload(update, context, c: Container, user) -> None:
    # Block upload if setup not completed
    from src.db.repositories.user_repo import UserSettingsRepository
    from src.bot.keyboards import setup_welcome_keyboard
    settings_repo = UserSettingsRepository(c.session)
    user_settings = await settings_repo.get_or_create(user.id)
    if not user_settings.setup_completed:
        await update.message.reply_text(
            "⚠️ <b>Setup Required</b>\n\n"
            "Before uploading files, you need to complete the vault setup.\n\n"
            "Please follow the setup steps carefully:\n"
            "1. Create a private Telegram channel\n"
            "2. Add this bot as admin with Post &amp; Delete permissions\n"
            "3. Get the channel ID and enter it via /setup\n\n"
            "Tap <b>Start Setup</b> to begin.",
            parse_mode=ParseMode.HTML,
            reply_markup=setup_welcome_keyboard(),
        )
        return

    upload_session = await c.sessions.get_active_session(user.id)

    if not upload_session:
        # No active session — ask where to put it
        settings = get_settings()
        if settings.default_upload_behavior == "default":
            default_folder = await c.folders.get_default_folder(user.id)
            folder_id = default_folder.id if default_folder else None
            folder_name = default_folder.name if default_folder else None
            await c.sessions.create_or_update_session(user.id, folder_id=folder_id)
            await c.users.set_state(user.id, UserState.UPLOADING)
            # Proceed with upload immediately
            upload_session = await c.sessions.get_active_session(user.id)
        else:
            folders, _ = await c.folders.get_user_folders(user.id)
            await update.message.reply_text(
                fmt_upload_choose_folder(),
                parse_mode=ParseMode.HTML,
                reply_markup=upload_folder_picker_keyboard(folders),
            )
            # Store the pending message for later processing
            context.user_data["pending_file_message_id"] = update.message.message_id
            return

    try:
        file = await c.files.upload_file(
            user_id=user.id,
            tg_message=update.message,
            folder_id=upload_session.folder_id if upload_session else None,
        )
        # Batch uploads — collect files and send one summary after 2s of silence
        batch = context.user_data.setdefault("upload_batch", [])
        batch.append(file)

        # Cancel previous pending summary task
        prev_task = context.user_data.pop("upload_batch_task", None)
        if prev_task:
            prev_task.cancel()

        async def _send_summary():
            await asyncio.sleep(2)
            files = context.user_data.pop("upload_batch", [])
            context.user_data.pop("upload_batch_task", None)
            if not files:
                return
            if len(files) == 1:
                await update.message.reply_text(
                    fmt_upload_success(files[0]),
                    parse_mode=ParseMode.HTML,
                    reply_markup=file_detail_keyboard(files[0]),
                )
            else:
                lines = "\n".join(f"• {f.label}" for f in files)
                await update.message.reply_text(
                    f"✅ <b>{len(files)} files uploaded</b>\n\n{lines}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=home_keyboard(),
                )

        task = asyncio.create_task(_send_summary())
        context.user_data["upload_batch_task"] = task

    except AppError as e:
        await update.message.reply_text(fmt_error(e.user_message), parse_mode=ParseMode.HTML)


async def _handle_search_text(update, context, c: Container, user, text: str) -> None:
    try:
        files, pagination = await c.search.search(user.id, query=text, page=1)
        await c.users.clear_state(user.id)
        text_out = fmt_search_results(text, pagination["total"], pagination)
        await update.message.reply_text(
            text_out,
            parse_mode=ParseMode.HTML,
            reply_markup=search_results_keyboard(files, pagination, query=text),
        )
    except ValidationError as e:
        await update.message.reply_text(fmt_error(e.user_message), parse_mode=ParseMode.HTML)


async def _handle_create_folder(update, context, c: Container, user, text: str) -> None:
    state_data = await c.users.get_state_data(user)
    parent_id = state_data.get("parent_id")
    try:
        folder = await c.folders.create_folder(user.id, text, parent_id=parent_id)
        await c.users.clear_state(user.id)
        from src.bot.keyboards import folder_detail_keyboard
        await update.message.reply_text(
            fmt_folder_created(folder),
            parse_mode=ParseMode.HTML,
            reply_markup=folder_detail_keyboard(folder),
        )
    except AppError as e:
        await update.message.reply_text(fmt_error(e.user_message), parse_mode=ParseMode.HTML)


async def _handle_rename_folder(update, context, c: Container, user, text: str) -> None:
    state_data = await c.users.get_state_data(user)
    folder_id = state_data.get("folder_id")
    if not folder_id:
        await c.users.clear_state(user.id)
        return
    try:
        folder = await c.folders.rename_folder(folder_id, user.id, text)
        await c.users.clear_state(user.id)
        from src.bot.keyboards import folder_detail_keyboard
        await update.message.reply_text(
            fmt_folder_renamed(state_data.get("old_name", ""), folder.name),
            parse_mode=ParseMode.HTML,
            reply_markup=folder_detail_keyboard(folder),
        )
    except AppError as e:
        await update.message.reply_text(fmt_error(e.user_message), parse_mode=ParseMode.HTML)


async def _handle_rename_file(update, context, c: Container, user, text: str) -> None:
    state_data = await c.users.get_state_data(user)
    file_id = state_data.get("file_id")
    if not file_id:
        await c.users.clear_state(user.id)
        return
    try:
        file = await c.files.rename_file(file_id, user.id, text)
        await c.users.clear_state(user.id)
        await update.message.reply_text(
            fmt_file_renamed(file.label),
            parse_mode=ParseMode.HTML,
            reply_markup=file_detail_keyboard(file),
        )
    except AppError as e:
        await update.message.reply_text(fmt_error(e.user_message), parse_mode=ParseMode.HTML)


async def _handle_add_tag(update, context, c: Container, user, text: str) -> None:
    state_data = await c.users.get_state_data(user)
    file_id = state_data.get("file_id")
    if not file_id:
        await c.users.clear_state(user.id)
        return
    try:
        await c.files.add_tag(file_id, user.id, text)
        await c.users.clear_state(user.id)
        file = await c.files.get_file(file_id, user.id)
        await update.message.reply_text(
            fmt_tag_added(text),
            parse_mode=ParseMode.HTML,
            reply_markup=file_detail_keyboard(file),
        )
    except AppError as e:
        await update.message.reply_text(fmt_error(e.user_message), parse_mode=ParseMode.HTML)


async def _handle_setup_vault_id(update, context, c: Container, user, text: str) -> None:
    from src.bot.formatters import fmt_setup_done, fmt_setup_invalid_id
    from src.bot.keyboards import setup_done_keyboard, back_home_keyboard
    from src.services.storage.storage_service import StorageService

    text = text.strip()
    # Validate: must be negative integer starting with -100
    try:
        channel_id = int(text)
        if channel_id >= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            fmt_setup_invalid_id(), parse_mode=ParseMode.HTML
        )
        return

    # Verify bot can access the channel
    storage = StorageService(context.bot)
    try:
        chat = await context.bot.get_chat(channel_id)
    except Exception:
        await update.message.reply_text(
            "⚠️ Could not access that channel.\n\n"
            "Make sure:\n"
            "• The channel is <b>private</b>\n"
            "• The bot is an <b>admin</b> with Post + Delete permissions\n\n"
            "Try again:",
            parse_mode=ParseMode.HTML,
        )
        return

    # Save to user state_data as their personal vault override
    await c.users.set_state(user.id, "idle", {"vault_channel_id": channel_id})
    await c.users.clear_state(user.id)

    # Mark setup as completed in user settings, saving their vault channel
    from src.db.repositories.user_repo import UserSettingsRepository
    settings_repo = UserSettingsRepository(c.session)
    await settings_repo.get_or_create(user.id)
    await settings_repo.mark_setup_completed(user.id, channel_id)

    await update.message.reply_text(
        fmt_setup_done(channel_id),
        parse_mode=ParseMode.HTML,
        reply_markup=setup_done_keyboard(),
    )
