"""
Command handlers: /start, /menu, /help, /upload, /folders, /files,
/search, /favorites, /recent, /trash, /settings, /admin
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.bot.container import Container
from src.bot.formatters import (
    fmt_help,
    fmt_home,
    fmt_recent_files,
    fmt_search_prompt,
    fmt_settings,
    fmt_upload_ready,
    fmt_welcome,
    fmt_admin_stats,
)
from src.bot.keyboards import (
    admin_keyboard,
    back_home_keyboard,
    home_keyboard,
    search_type_keyboard,
    settings_keyboard,
    upload_cancel_keyboard,
    upload_folder_picker_keyboard,
)
from src.core.constants import UserState
from src.core.errors import ForbiddenError
from src.core.logging import get_logger

logger = get_logger(__name__)


def _get(context: ContextTypes.DEFAULT_TYPE) -> Container:
    return context.user_data["container"]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = context.user_data["db_user"]
    is_new = context.user_data.get("is_new_user", False)
    text = fmt_welcome(user, is_new)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=home_keyboard())


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        fmt_home(), parse_mode=ParseMode.HTML, reply_markup=home_keyboard()
    )


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.bot.formatters import fmt_setup_welcome
    from src.bot.keyboards import setup_welcome_keyboard
    await update.message.reply_text(
        fmt_setup_welcome(),
        parse_mode=ParseMode.HTML,
        reply_markup=setup_welcome_keyboard(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.bot.keyboards import back_home_keyboard
    await update.message.reply_text(
        fmt_help(), parse_mode=ParseMode.HTML, reply_markup=back_home_keyboard()
    )


async def cmd_folders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = _get(context)
    user = context.user_data["db_user"]
    folders, total = await c.folders.get_user_folders(user.id)
    from src.core.utils import paginate
    from src.core.config.settings import get_settings
    pagination = paginate(total, 1, get_settings().page_size)
    from src.bot.formatters import fmt_folder_list
    from src.bot.keyboards import folder_list_keyboard
    text = fmt_folder_list(folders, pagination, total)
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=folder_list_keyboard(folders, pagination)
    )


async def cmd_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = _get(context)
    user = context.user_data["db_user"]
    files, pagination = await c.files.list_files(user.id, folder_id=None, page=1)
    from src.bot.formatters import fmt_file_list
    from src.bot.keyboards import file_list_keyboard
    text = fmt_file_list(files, None, pagination, pagination["total"])
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=file_list_keyboard(files, None, pagination)
    )


async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = _get(context)
    user = context.user_data["db_user"]
    from src.core.config.settings import get_settings
    settings = get_settings()

    if settings.default_upload_behavior == "default":
        default_folder = await c.folders.get_default_folder(user.id)
        folder_id = default_folder.id if default_folder else None
        folder_name = default_folder.name if default_folder else None
        await c.sessions.create_or_update_session(user.id, folder_id=folder_id)
        await c.users.set_state(user.id, UserState.UPLOADING)
        await update.message.reply_text(
            fmt_upload_ready(folder_name),
            parse_mode=ParseMode.HTML,
            reply_markup=upload_cancel_keyboard(),
        )
    else:
        folders, _ = await c.folders.get_user_folders(user.id)
        await update.message.reply_text(
            "📁 Choose a folder to upload into:",
            parse_mode=ParseMode.HTML,
            reply_markup=upload_folder_picker_keyboard(folders),
        )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = context.user_data["db_user"]
    c = _get(context)
    await c.users.set_state(user.id, UserState.SEARCHING)
    await update.message.reply_text(
        fmt_search_prompt(),
        parse_mode=ParseMode.HTML,
        reply_markup=search_type_keyboard(),
    )


async def cmd_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = _get(context)
    user = context.user_data["db_user"]
    files, pagination = await c.files.get_favorites(user.id, page=1)
    from src.bot.formatters import fmt_favorites_header
    from src.bot.keyboards import file_list_keyboard
    text = fmt_favorites_header(pagination["total"], pagination)
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=file_list_keyboard(files, None, pagination)
    )


async def cmd_recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = _get(context)
    user = context.user_data["db_user"]
    files = await c.files.get_recent(user.id)
    from src.bot.keyboards import back_home_keyboard
    await update.message.reply_text(
        fmt_recent_files(files),
        parse_mode=ParseMode.HTML,
        reply_markup=back_home_keyboard(),
    )


async def cmd_trash(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = _get(context)
    user = context.user_data["db_user"]
    files, pagination = await c.files.get_trash(user.id, page=1)
    from src.bot.formatters import fmt_trash_header
    from src.bot.keyboards import trash_list_keyboard
    text = fmt_trash_header(pagination["total"], pagination)
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=trash_list_keyboard(files, pagination)
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = _get(context)
    user = context.user_data["db_user"]
    from src.db.repositories.user_repo import UserSettingsRepository
    from src.bot.formatters import fmt_settings_full
    settings_repo = UserSettingsRepository(c.session)
    user_settings = await settings_repo.get_or_create(user.id)
    from src.core.config.settings import get_settings as get_app_settings
    page_size = get_app_settings().page_size
    await update.message.reply_text(
        fmt_settings_full(user_settings.upload_behavior, user_settings.notifications_enabled, page_size),
        parse_mode=ParseMode.HTML,
        reply_markup=settings_keyboard(user_settings.upload_behavior, user_settings.notifications_enabled, page_size),
    )


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = context.user_data["db_user"]
    if not user.is_admin:
        raise ForbiddenError("access admin panel")
    await update.message.reply_text(
        "🔧 <b>Admin Panel</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard(),
    )
