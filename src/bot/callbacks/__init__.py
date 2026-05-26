"""
Callback query handler: routes all inline button presses.
Each callback data string is parsed by prefix and dispatched to the
appropriate handler function.
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.container import Container
from src.bot.formatters import (
    fmt_admin_stats,
    fmt_ask_folder_name,
    fmt_ask_rename_file,
    fmt_ask_rename_folder,
    fmt_ask_tag,
    fmt_error,
    fmt_favorites_header,
    fmt_file_card,
    fmt_file_detail,
    fmt_file_deleted,
    fmt_file_list,
    fmt_file_moved,
    fmt_file_permanently_deleted,
    fmt_file_restored,
    fmt_folder_detail,
    fmt_folder_list,
    fmt_folder_not_empty_warning,
    fmt_folder_renamed,
    fmt_home,
    fmt_recent_files,
    fmt_search_prompt,
    fmt_search_results,

    fmt_tag_removed,
    fmt_trash_header,
    fmt_upload_ready,
    fmt_favorite_toggled,
)
from src.bot.keyboards import (
    admin_keyboard,
    back_home_keyboard,
    empty_trash_confirm_keyboard,
    file_detail_keyboard,
    file_delete_confirm_keyboard,
    file_list_keyboard,
    file_tags_keyboard,
    folder_delete_confirm_keyboard,
    folder_detail_keyboard,
    folder_list_keyboard,
    folder_picker_keyboard,
    home_keyboard,
    search_results_keyboard,
    search_type_keyboard,
    settings_keyboard,
    trash_file_keyboard,
    trash_list_keyboard,
    trash_delete_confirm_keyboard,
    upload_cancel_keyboard,
    upload_folder_picker_keyboard,
)
from src.core.config.settings import get_settings
from src.core.constants import CB, UserState
from src.core.errors import AppError, FolderNotEmptyError, ForbiddenError
from src.core.logging import get_logger
from src.core.utils import paginate, parse_callback_data

logger = get_logger(__name__)


def _get(context: ContextTypes.DEFAULT_TYPE) -> Container:
    return context.user_data["container"]


async def _edit(update: Update, text: str, keyboard=None) -> None:
    """Edit the current message text and keyboard."""
    try:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise


async def _answer(update: Update, text: str = "") -> None:
    await update.callback_query.answer(text)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data
    parts = parse_callback_data(data)
    prefix = parts[0]

    c = _get(context)
    user = context.user_data["db_user"]

    try:
        # ── Navigation ────────────────────────────────────────────────────
        if prefix == CB.HOME:
            await _edit(update, fmt_home(), home_keyboard())

        elif prefix == CB.NOOP:
            pass

        elif prefix == "help":
            from src.bot.formatters import fmt_help
            await _edit(update, fmt_help(), back_home_keyboard())

        # ── Folders ───────────────────────────────────────────────────────
        elif prefix == CB.FOLDER_LIST:
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            folders, total = await c.folders.get_user_folders(user.id, page=page)
            pagination = paginate(total, page, get_settings().page_size)
            text = fmt_folder_list(folders, pagination, total)
            await _edit(update, text, folder_list_keyboard(folders, pagination))

        elif prefix == CB.FOLDER_OPEN:
            folder_id = int(parts[1])
            folder = await c.folders.get_folder(folder_id, user.id)
            from src.db.repositories.folder_repo import FolderRepository
            repo = FolderRepository(c.session)
            file_count = await repo.count_files_in_folder(folder_id)
            await _edit(
                update,
                fmt_folder_detail(folder, file_count),
                folder_detail_keyboard(folder),
            )

        elif prefix == CB.FOLDER_CREATE:
            await c.users.set_state(user.id, UserState.CREATING_FOLDER)
            await _edit(update, fmt_ask_folder_name("create"), back_home_keyboard())

        elif prefix == CB.FOLDER_RENAME:
            folder_id = int(parts[1])
            folder = await c.folders.get_folder(folder_id, user.id)
            await c.users.set_state(
                user.id, UserState.RENAMING_FOLDER,
                {"folder_id": folder_id, "old_name": folder.name}
            )
            await _edit(update, fmt_ask_rename_folder(), back_home_keyboard())

        elif prefix == CB.FOLDER_DELETE:
            folder_id = int(parts[1])
            folder = await c.folders.get_folder(folder_id, user.id)
            from src.db.repositories.folder_repo import FolderRepository
            repo = FolderRepository(c.session)
            file_count = await repo.count_files_in_folder(folder_id)
            if file_count > 0:
                await _edit(
                    update,
                    fmt_folder_not_empty_warning(folder.name, file_count),
                    folder_delete_confirm_keyboard(folder_id),
                )
            else:
                await _edit(
                    update,
                    f"🗑 Delete folder <b>{folder.name}</b>? This cannot be undone.",
                    folder_delete_confirm_keyboard(folder_id),
                )

        elif prefix == CB.FOLDER_DELETE_CONFIRM:
            folder_id = int(parts[1])
            folder = await c.folders.get_folder(folder_id, user.id)
            name = folder.name
            await c.folders.delete_folder(folder_id, user.id, force=True)
            await _edit(update, f"🗑 Folder <b>{name}</b> deleted.", home_keyboard())

        elif prefix == CB.FOLDER_UPLOAD:
            raw = parts[1] if len(parts) > 1 else ""
            folder_id = int(raw) if raw.isdigit() else None
            folder_name = None
            if folder_id:
                folder = await c.folders.get_folder(folder_id, user.id)
                folder_name = folder.name
            await c.sessions.create_or_update_session(user.id, folder_id=folder_id)
            await c.users.set_state(user.id, UserState.UPLOADING)

            # Upload any queued pending files
            pending_ids = context.user_data.pop("pending_file_message_ids", [])
            if pending_ids:
                uploaded = []
                failed = 0
                for msg_id in pending_ids:
                    try:
                        from telegram import Message as TGMessage
                        msg = await update.effective_chat.forward(
                            chat_id=update.effective_chat.id,
                            from_chat_id=update.effective_chat.id,
                            message_id=msg_id,
                        )
                    except Exception:
                        # Can't re-fetch old messages — skip silently
                        failed += 1
                        continue
                if uploaded or failed:
                    pass  # summary handled below

                count = len(pending_ids)
                await _edit(
                    update,
                    f"✅ <b>{count} file{'s' if count != 1 else ''} queued for upload to {folder_name or 'default folder'}</b>\n\n"
                    f"Send the files again — folder is now selected and ready.",
                    upload_cancel_keyboard(),
                )
            else:
                await _edit(update, fmt_upload_ready(folder_name), upload_cancel_keyboard())

        # ── Files ─────────────────────────────────────────────────────────
        elif prefix == CB.FILE_LIST:
            raw_folder = parts[1] if len(parts) > 1 else ""
            folder_id = int(raw_folder) if raw_folder.isdigit() else None
            page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
            files, pagination = await c.files.list_files(user.id, folder_id=folder_id, page=page)
            folder_name = None
            if folder_id:
                folder = await c.folders.get_folder(folder_id, user.id)
                folder_name = folder.name
            text = fmt_file_list(files, folder_name, pagination, pagination["total"])
            await _edit(update, text, file_list_keyboard(files, folder_id, pagination))

        elif prefix == CB.FILE_OPEN:
            file_id = int(parts[1])
            file = await c.files.get_file(file_id, user.id)
            if file.is_deleted:
                await _edit(update, fmt_file_card(file), trash_file_keyboard(file_id))
            else:
                await _edit(update, fmt_file_card(file), file_detail_keyboard(file))

        elif prefix == CB.FILE_GET:
            file_id = int(parts[1])
            await c.files.retrieve_file(file_id, user.id, update.effective_chat.id)
            # Keep the detail view open

        elif prefix == CB.FILE_INFO:
            file_id = int(parts[1])
            file = await c.files.get_file(file_id, user.id)
            await _edit(update, fmt_file_detail(file), file_detail_keyboard(file))

        elif prefix == CB.FILE_RENAME:
            file_id = int(parts[1])
            await c.users.set_state(user.id, UserState.RENAMING_FILE, {"file_id": file_id})
            await _edit(update, fmt_ask_rename_file(), back_home_keyboard())

        elif prefix == CB.FILE_MOVE:
            file_id = int(parts[1])
            file = await c.files.get_file(file_id, user.id)
            folders = await c.folders.get_all_user_folders_flat(user.id)
            await _edit(
                update,
                f"📦 Move <b>{file.label}</b> to:",
                folder_picker_keyboard(folders, file_id, file.folder_id),
            )

        elif prefix == CB.FILE_MOVE_TO:
            file_id = int(parts[1])
            raw_folder = parts[2] if len(parts) > 2 else ""
            target_folder_id = int(raw_folder) if raw_folder.isdigit() else None
            file = await c.files.move_file(file_id, user.id, target_folder_id)
            folder_name = None
            if target_folder_id:
                folder = await c.folders.get_folder(target_folder_id, user.id)
                folder_name = folder.name
            await _edit(
                update,
                fmt_file_moved(file, folder_name),
                file_detail_keyboard(file),
            )

        elif prefix == CB.FILE_DELETE:
            file_id = int(parts[1])
            file = await c.files.get_file(file_id, user.id)
            await _edit(
                update,
                f"🗑 Move <b>{file.label}</b> to trash?",
                file_delete_confirm_keyboard(file_id),
            )

        elif prefix == CB.FILE_DELETE_CONFIRM:
            file_id = int(parts[1])
            file = await c.files.get_file(file_id, user.id)
            label = file.label
            await c.files.soft_delete(file_id, user.id)
            await _edit(update, fmt_file_deleted(label), home_keyboard())

        elif prefix == CB.FILE_FAVORITE:
            file_id = int(parts[1])
            file = await c.files.toggle_favorite(file_id, user.id)
            await _edit(update, fmt_favorite_toggled(file), file_detail_keyboard(file))

        elif prefix == CB.FILE_TAGS:
            file_id = int(parts[1])
            file = await c.files.get_file(file_id, user.id)
            await _edit(
                update,
                f"🏷 Tags for <b>{file.label}</b>:",
                file_tags_keyboard(file),
            )

        elif prefix == CB.FILE_TAG_ADD:
            file_id = int(parts[1])
            await c.users.set_state(user.id, UserState.ADDING_TAGS, {"file_id": file_id})
            await _edit(update, fmt_ask_tag(), back_home_keyboard())

        elif prefix == CB.FILE_TAG_REMOVE:
            file_id = int(parts[1])
            tag = parts[2] if len(parts) > 2 else ""
            await c.files.remove_tag(file_id, user.id, tag)
            file = await c.files.get_file(file_id, user.id)
            await _edit(
                update,
                fmt_tag_removed(tag) + f"\n\n🏷 Tags for <b>{file.label}</b>:",
                file_tags_keyboard(file),
            )

        # ── Views ─────────────────────────────────────────────────────────
        elif prefix == CB.VIEW_RECENT:
            files = await c.files.get_recent(user.id)
            await _edit(update, fmt_recent_files(files), back_home_keyboard())

        elif prefix == CB.VIEW_FAVORITES:
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            files, pagination = await c.files.get_favorites(user.id, page=page)
            text = fmt_favorites_header(pagination["total"], pagination)
            await _edit(update, text, file_list_keyboard(files, None, pagination))

        elif prefix == CB.VIEW_TRASH:
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            files, pagination = await c.files.get_trash(user.id, page=page)
            text = fmt_trash_header(pagination["total"], pagination)
            await _edit(update, text, trash_list_keyboard(files, pagination))

        elif prefix == CB.VIEW_ALL:
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            files, pagination = await c.files.list_files(user.id, folder_id=None, page=page)
            text = fmt_file_list(files, None, pagination, pagination["total"])
            await _edit(update, text, file_list_keyboard(files, None, pagination))

        # ── Trash ─────────────────────────────────────────────────────────
        elif prefix == CB.TRASH_RESTORE:
            file_id = int(parts[1])
            file = await c.files.restore_file(file_id, user.id)
            await _edit(update, fmt_file_restored(file.label), file_detail_keyboard(file))

        elif prefix == CB.TRASH_DELETE:
            file_id = int(parts[1])
            file = await c.files.get_file(file_id, user.id)
            await _edit(
                update,
                f"❌ Permanently delete <b>{file.label}</b>? This cannot be undone.",
                trash_delete_confirm_keyboard(file_id),
            )

        elif prefix == CB.TRASH_DELETE_CONFIRM:
            file_id = int(parts[1])
            file = await c.files.get_file(file_id, user.id)
            label = file.label
            await c.files.permanent_delete(file_id, user.id, delete_from_vault=True)
            await _edit(update, fmt_file_permanently_deleted(label), home_keyboard())

        elif prefix == CB.TRASH_EMPTY:
            files, pagination = await c.files.get_trash(user.id, page=1)
            if pagination["total"] == 0:
                await _edit(update, "🗑 Trash is already empty.", home_keyboard())
            else:
                await _edit(
                    update,
                    f"🧹 Permanently delete all <b>{pagination['total']}</b> trashed files?",
                    empty_trash_confirm_keyboard(),
                )

        elif prefix == CB.TRASH_EMPTY_CONFIRM:
            page = 1
            deleted = 0
            while True:
                files, pagination = await c.files.get_trash(user.id, page=page)
                if not files:
                    break
                for f in files:
                    await c.files.permanent_delete(f.id, user.id, delete_from_vault=True)
                    deleted += 1
                if not pagination["has_next"]:
                    break
            await _edit(update, f"🧹 Trash emptied. <b>{deleted}</b> files deleted.", home_keyboard())

        # ── Search ────────────────────────────────────────────────────────
        elif prefix == CB.SEARCH_START:
            await c.users.set_state(user.id, UserState.SEARCHING)
            await _edit(update, fmt_search_prompt(), search_type_keyboard())

        elif prefix == CB.SEARCH_BY_TYPE:
            file_type = parts[1] if len(parts) > 1 else ""
            page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
            files, pagination = await c.search.search(user.id, file_type=file_type, page=page)
            text = fmt_search_results(None, pagination["total"], pagination)
            await _edit(update, text, search_results_keyboard(files, pagination, file_type=file_type))

        elif prefix == CB.SEARCH_BY_TAG:
            tag = parts[1] if len(parts) > 1 else ""
            page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
            files, pagination = await c.search.search(user.id, tag=tag, page=page)
            text = fmt_search_results(f"#{tag}", pagination["total"], pagination)
            await _edit(update, text, search_results_keyboard(files, pagination, tag=tag))

        # ── Upload ────────────────────────────────────────────────────────
        elif prefix == CB.UPLOAD_CANCEL:
            await c.sessions.clear_session(user.id)
            await c.users.clear_state(user.id)
            await _edit(update, fmt_home(), home_keyboard())

        elif prefix == CB.UPLOAD_TO_DEFAULT:
            default_folder = await c.folders.get_default_folder(user.id)
            folder_id = default_folder.id if default_folder else None
            folder_name = default_folder.name if default_folder else None
            await c.sessions.create_or_update_session(user.id, folder_id=folder_id)
            await c.users.set_state(user.id, UserState.UPLOADING)
            await _edit(update, fmt_upload_ready(folder_name), upload_cancel_keyboard())

        elif prefix == CB.UPLOAD_CHOOSE_FOLDER:
            folders, _ = await c.folders.get_user_folders(user.id)
            await _edit(update, "📁 Choose a folder:", upload_folder_picker_keyboard(folders))

        # ── Settings ──────────────────────────────────────────────────────
        elif prefix == CB.SETTINGS:
            from src.db.repositories.user_repo import UserSettingsRepository
            from src.bot.formatters import fmt_settings_full
            from src.core.config.settings import get_settings as get_app_settings
            settings_repo = UserSettingsRepository(c.session)
            user_settings = await settings_repo.get_or_create(user.id)
            page_size = get_app_settings().page_size
            await _edit(
                update,
                fmt_settings_full(user_settings.upload_behavior, user_settings.notifications_enabled, page_size),
                settings_keyboard(user_settings.upload_behavior, user_settings.notifications_enabled, page_size),
            )

        elif prefix == CB.SETTINGS_UPLOAD_BEHAVIOR:
            from src.db.repositories.user_repo import UserSettingsRepository
            from src.bot.formatters import fmt_settings_full
            from src.core.config.settings import get_settings as get_app_settings
            settings_repo = UserSettingsRepository(c.session)
            user_settings = await settings_repo.get_or_create(user.id)
            new_behavior = "default" if user_settings.upload_behavior == "ask" else "ask"
            await settings_repo.update_upload_behavior(user.id, new_behavior)
            user_settings.upload_behavior = new_behavior
            page_size = get_app_settings().page_size
            await _edit(
                update,
                fmt_settings_full(new_behavior, user_settings.notifications_enabled, page_size),
                settings_keyboard(new_behavior, user_settings.notifications_enabled, page_size),
            )

        elif prefix == CB.SETTINGS_NOTIFICATIONS:
            from src.db.repositories.user_repo import UserSettingsRepository
            from src.bot.formatters import fmt_settings_full
            from src.core.config.settings import get_settings as get_app_settings
            settings_repo = UserSettingsRepository(c.session)
            user_settings = await settings_repo.get_or_create(user.id)
            new_val = not user_settings.notifications_enabled
            await c.session.execute(
                __import__("sqlalchemy").update(
                    __import__("src.db.models", fromlist=["UserSettings"]).UserSettings
                ).where(
                    __import__("src.db.models", fromlist=["UserSettings"]).UserSettings.user_id == user.id
                ).values(notifications_enabled=new_val)
            )
            await c.session.flush()
            user_settings.notifications_enabled = new_val
            page_size = get_app_settings().page_size
            await _edit(
                update,
                fmt_settings_full(user_settings.upload_behavior, new_val, page_size),
                settings_keyboard(user_settings.upload_behavior, new_val, page_size),
            )

        elif prefix == CB.SETTINGS_PAGE_SIZE:
            from src.db.repositories.user_repo import UserSettingsRepository
            from src.bot.formatters import fmt_settings_full
            from src.core.config.settings import get_settings as get_app_settings
            settings_repo = UserSettingsRepository(c.session)
            user_settings = await settings_repo.get_or_create(user.id)
            # Cycle through: 5 → 8 → 10 → 15 → 5
            sizes = [5, 8, 10, 15]
            current = get_app_settings().page_size
            try:
                next_size = sizes[(sizes.index(current) + 1) % len(sizes)]
            except ValueError:
                next_size = 8
            await query.answer(f"Files per page set to {next_size}", show_alert=False)
            await _edit(
                update,
                fmt_settings_full(user_settings.upload_behavior, user_settings.notifications_enabled, next_size),
                settings_keyboard(user_settings.upload_behavior, user_settings.notifications_enabled, next_size),
            )

        # ── Setup wizard ──────────────────────────────────────────────────
        elif prefix == CB.SETUP_START:
            from src.bot.formatters import fmt_setup_welcome
            from src.bot.keyboards import setup_welcome_keyboard
            await _edit(update, fmt_setup_welcome(), setup_welcome_keyboard())

        elif prefix == CB.SETUP_STEP:
            step = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            from src.bot.formatters import fmt_setup_step1, fmt_setup_step2, fmt_setup_step3
            from src.bot.keyboards import setup_step_keyboard
            if step == 1:
                await _edit(update, fmt_setup_step1(), setup_step_keyboard(1))
            elif step == 2:
                await _edit(update, fmt_setup_step2(), setup_step_keyboard(2))
            elif step == 3:
                # Step 3: ask user to type the channel ID
                await c.users.set_state(user.id, UserState.SETUP_WAITING_ID)
                await _edit(update, fmt_setup_step3(), setup_step_keyboard(3))

        elif prefix == CB.SETUP_DONE:
            await _edit(update, fmt_home(), home_keyboard())

        # ── Admin ─────────────────────────────────────────────────────────
        elif prefix == CB.ADMIN_PANEL:
            if not user.is_admin:
                raise ForbiddenError("access admin panel")
            await _edit(update, "🔧 <b>Admin Panel</b>", admin_keyboard())

        elif prefix == CB.ADMIN_STATS:
            if not user.is_admin:
                raise ForbiddenError("access admin stats")
            user_stats = await c.users.get_stats()
            from src.db.repositories.file_repo import FileRepository
            from src.db.repositories.folder_repo import FolderRepository
            from src.db.repositories.session_repo import OperationFailureRepository
            file_repo = FileRepository(c.session)
            folder_repo = FolderRepository(c.session)
            failure_repo = OperationFailureRepository(c.session)
            total_files = await file_repo.count_total_files()
            total_folders = await folder_repo.count_total_folders()
            unresolved = await failure_repo.count_unresolved()
            await _edit(
                update,
                fmt_admin_stats(
                    user_stats["total_users"], total_files, total_folders, unresolved
                ),
                admin_keyboard(),
            )

        else:
            logger.warning("Unknown callback prefix", prefix=prefix, data=data)

    except AppError as e:
        logger.warning("AppError in callback", code=e.code, message=str(e))
        try:
            await _edit(update, fmt_error(e.user_message), back_home_keyboard())
        except Exception:
            await query.answer(e.user_message, show_alert=True)
    except Exception as e:
        import traceback
        logger.error("Unhandled error in callback", error=str(e), tb=traceback.format_exc())
        try:
            await _edit(update, "⚠️ Something went wrong. Please try again.", back_home_keyboard())
        except Exception:
            await query.answer("Something went wrong.", show_alert=True)
