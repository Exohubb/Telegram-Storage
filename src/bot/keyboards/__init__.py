"""
Keyboard builder: all inline keyboards in one place.
Callback data format: PREFIX:arg1:arg2 (max 64 bytes enforced by Telegram)
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.core.constants import CB, FileType
from src.core.utils import build_callback_data, truncate
from src.db.models import File, Folder


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


def _url_btn(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, url=url)


# ── Home / Navigation ────────────────────────────────────────────────────────

def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn("📁 Folders", CB.FOLDER_LIST),
            _btn("🗂 All Files", build_callback_data(CB.VIEW_ALL, 1)),
        ],
        [
            _btn("⭐ Favorites", build_callback_data(CB.VIEW_FAVORITES, 1)),
            _btn("🕘 Recent", CB.VIEW_RECENT),
        ],
        [
            _btn("🔍 Search", CB.SEARCH_START),
            _btn("🗑 Trash", build_callback_data(CB.VIEW_TRASH, 1)),
        ],
        [
            _btn("⚙️ Settings", CB.SETTINGS),
            _btn("❓ Help", "help"),
        ],
    ])


def back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_btn("↩️ Home", CB.HOME)]])


# ── Folder keyboards ─────────────────────────────────────────────────────────

def folder_list_keyboard(
    folders: list[Folder],
    pagination: dict,
    parent_id: int | None = None,
) -> InlineKeyboardMarkup:
    rows = []
    for folder in folders:
        rows.append([_btn(f"📁 {truncate(folder.name, 28)}", build_callback_data(CB.FOLDER_OPEN, folder.id))])

    # Pagination row
    nav = _pagination_row(CB.FOLDER_LIST, pagination, extra_arg=str(parent_id or ""))
    if nav:
        rows.append(nav)

    action_row = [_btn("➕ New Folder", CB.FOLDER_CREATE)]
    if parent_id:
        action_row.append(_btn("↩️ Back", CB.FOLDER_LIST))
    else:
        action_row.append(_btn("↩️ Home", CB.HOME))
    rows.append(action_row)

    return InlineKeyboardMarkup(rows)


def folder_detail_keyboard(folder: Folder) -> InlineKeyboardMarkup:
    fid = folder.id
    return InlineKeyboardMarkup([
        [
            _btn("⬆️ Upload Here", build_callback_data(CB.FOLDER_UPLOAD, fid)),
            _btn("📄 View Files", build_callback_data(CB.FILE_LIST, fid, 1)),
        ],
        [
            _btn("✏️ Rename", build_callback_data(CB.FOLDER_RENAME, fid)),
            _btn("🗑 Delete", build_callback_data(CB.FOLDER_DELETE, fid)),
        ],
        [_btn("↩️ Folders", CB.FOLDER_LIST)],
    ])


def folder_delete_confirm_keyboard(folder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn("✅ Yes, Delete", build_callback_data(CB.FOLDER_DELETE_CONFIRM, folder_id)),
            _btn("❌ Cancel", build_callback_data(CB.FOLDER_OPEN, folder_id)),
        ]
    ])


def folder_picker_keyboard(
    folders: list[Folder],
    file_id: int,
    current_folder_id: int | None = None,
) -> InlineKeyboardMarkup:
    """Folder picker for moving a file."""
    rows = []
    for folder in folders:
        marker = " ✓" if folder.id == current_folder_id else ""
        rows.append([
            _btn(
                f"📁 {truncate(folder.name, 26)}{marker}",
                build_callback_data(CB.FILE_MOVE_TO, file_id, folder.id),
            )
        ])
    rows.append([_btn("↩️ Cancel", build_callback_data(CB.FILE_OPEN, file_id))])
    return InlineKeyboardMarkup(rows)


def upload_folder_picker_keyboard(folders: list[Folder]) -> InlineKeyboardMarkup:
    """Folder picker shown when user uploads without selecting a folder first."""
    rows = []
    for folder in folders:
        rows.append([
            _btn(f"📁 {truncate(folder.name, 28)}", build_callback_data(CB.FOLDER_UPLOAD, folder.id))
        ])
    rows.append([_btn("❌ Cancel", CB.UPLOAD_CANCEL)])
    return InlineKeyboardMarkup(rows)


# ── File keyboards ────────────────────────────────────────────────────────────

def file_list_keyboard(
    files: list[File],
    folder_id: int | None,
    pagination: dict,
) -> InlineKeyboardMarkup:
    rows = []
    for f in files:
        icon = _file_icon(f.file_type)
        rows.append([
            _btn(
                f"{icon} {truncate(f.label, 26)}",
                build_callback_data(CB.FILE_OPEN, f.id),
            )
        ])

    nav = _pagination_row(CB.FILE_LIST, pagination, extra_arg=str(folder_id or ""))
    if nav:
        rows.append(nav)

    back_target = build_callback_data(CB.FOLDER_OPEN, folder_id) if folder_id else CB.HOME
    rows.append([
        _btn("⬆️ Upload", build_callback_data(CB.FOLDER_UPLOAD, folder_id or "")),
        _btn("↩️ Back", back_target),
    ])
    return InlineKeyboardMarkup(rows)


def file_detail_keyboard(file: File) -> InlineKeyboardMarkup:
    fid = file.id
    fav_label = "★ Unfavorite" if file.is_favorite else "⭐ Favorite"
    return InlineKeyboardMarkup([
        [
            _btn("📥 Get File", build_callback_data(CB.FILE_GET, fid)),
            _btn("ℹ️ Info", build_callback_data(CB.FILE_INFO, fid)),
        ],
        [
            _btn("✏️ Rename", build_callback_data(CB.FILE_RENAME, fid)),
            _btn("📦 Move", build_callback_data(CB.FILE_MOVE, fid)),
        ],
        [
            _btn("🏷 Tags", build_callback_data(CB.FILE_TAGS, fid)),
            _btn(fav_label, build_callback_data(CB.FILE_FAVORITE, fid)),
        ],
        [
            _btn("🗑 Delete", build_callback_data(CB.FILE_DELETE, fid)),
            _btn("↩️ Back", build_callback_data(CB.FILE_LIST, file.folder_id or "", 1)),
        ],
    ])


def file_delete_confirm_keyboard(file_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn("✅ Move to Trash", build_callback_data(CB.FILE_DELETE_CONFIRM, file_id)),
            _btn("❌ Cancel", build_callback_data(CB.FILE_OPEN, file_id)),
        ]
    ])


def file_tags_keyboard(file: File) -> InlineKeyboardMarkup:
    fid = file.id
    rows = []
    if file.tags:
        for tag in file.tags:
            rows.append([
                _btn(f"🏷 #{tag.tag}", CB.NOOP),
                _btn("✕ Remove", build_callback_data(CB.FILE_TAG_REMOVE, fid, tag.tag)),
            ])
    rows.append([_btn("➕ Add Tag", build_callback_data(CB.FILE_TAG_ADD, fid))])
    rows.append([_btn("↩️ Back", build_callback_data(CB.FILE_OPEN, fid))])
    return InlineKeyboardMarkup(rows)


# ── Trash keyboards ───────────────────────────────────────────────────────────

def trash_list_keyboard(
    files: list[File],
    pagination: dict,
) -> InlineKeyboardMarkup:
    rows = []
    for f in files:
        icon = _file_icon(f.file_type)
        rows.append([
            _btn(
                f"{icon} {truncate(f.label, 26)}",
                build_callback_data(CB.FILE_OPEN, f.id),
            )
        ])

    nav = _pagination_row(CB.VIEW_TRASH, pagination)
    if nav:
        rows.append(nav)

    rows.append([
        _btn("🧹 Empty Trash", CB.TRASH_EMPTY),
        _btn("↩️ Home", CB.HOME),
    ])
    return InlineKeyboardMarkup(rows)


def trash_file_keyboard(file_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn("♻️ Restore", build_callback_data(CB.TRASH_RESTORE, file_id)),
            _btn("❌ Delete Forever", build_callback_data(CB.TRASH_DELETE, file_id)),
        ],
        [_btn("↩️ Trash", build_callback_data(CB.VIEW_TRASH, 1))],
    ])


def trash_delete_confirm_keyboard(file_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn("✅ Delete Forever", build_callback_data(CB.TRASH_DELETE_CONFIRM, file_id)),
            _btn("❌ Cancel", build_callback_data(CB.VIEW_TRASH, 1)),
        ]
    ])


def empty_trash_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn("✅ Empty All", CB.TRASH_EMPTY_CONFIRM),
            _btn("❌ Cancel", build_callback_data(CB.VIEW_TRASH, 1)),
        ]
    ])


# ── Search keyboards ──────────────────────────────────────────────────────────

def search_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn("🖼 Images", build_callback_data(CB.SEARCH_BY_TYPE, FileType.IMAGE, 1)),
            _btn("🎬 Videos", build_callback_data(CB.SEARCH_BY_TYPE, FileType.VIDEO, 1)),
        ],
        [
            _btn("🎵 Audio", build_callback_data(CB.SEARCH_BY_TYPE, FileType.AUDIO, 1)),
            _btn("📄 Documents", build_callback_data(CB.SEARCH_BY_TYPE, FileType.DOCUMENT, 1)),
        ],
        [_btn("↩️ Back", CB.HOME)],
    ])


def search_results_keyboard(
    files: list[File],
    pagination: dict,
    query: str = "",
    file_type: str = "",
    tag: str = "",
) -> InlineKeyboardMarkup:
    rows = []
    for f in files:
        icon = _file_icon(f.file_type)
        rows.append([
            _btn(
                f"{icon} {truncate(f.label, 26)}",
                build_callback_data(CB.FILE_OPEN, f.id),
            )
        ])

    nav = _pagination_row(CB.VIEW_SEARCH, pagination)
    if nav:
        rows.append(nav)

    rows.append([_btn("🔍 New Search", CB.SEARCH_START), _btn("↩️ Home", CB.HOME)])
    return InlineKeyboardMarkup(rows)


# ── Settings keyboard ─────────────────────────────────────────────────────────

def settings_keyboard(upload_behavior: str, notifications: bool = True, page_size: int = 8) -> InlineKeyboardMarkup:
    behavior_icon = "📂" if upload_behavior == "ask" else "📁"
    behavior_label = "Ask for folder" if upload_behavior == "ask" else "Default folder"
    notif_icon = "🔔" if notifications else "🔕"
    notif_label = "On" if notifications else "Off"
    return InlineKeyboardMarkup([
        [_btn(f"📤 Upload: {behavior_icon} {behavior_label}", CB.SETTINGS_UPLOAD_BEHAVIOR)],
        [_btn(f"{notif_icon} Notifications: {notif_label}", CB.SETTINGS_NOTIFICATIONS)],
        [_btn(f"📄 Files per page: {page_size}", CB.SETTINGS_PAGE_SIZE)],
        [_btn("🛠 Vault Setup", CB.SETUP_START)],
        [_btn("↩️ Home", CB.HOME)],
    ])


# ── Setup wizard keyboards ────────────────────────────────────────────────────

def setup_welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🚀 Start Setup", build_callback_data(CB.SETUP_STEP, 1))],
        [_btn("↩️ Skip for now", CB.HOME)],
    ])


def setup_step_keyboard(step: int, total: int = 3) -> InlineKeyboardMarkup:
    rows = []
    nav = []
    if step > 1:
        nav.append(_btn("⬅️ Back", build_callback_data(CB.SETUP_STEP, step - 1)))
    if step < total:
        nav.append(_btn(f"Next ➡️", build_callback_data(CB.SETUP_STEP, step + 1)))
    if nav:
        rows.append(nav)
    rows.append([_btn("❌ Cancel Setup", CB.HOME)])
    return InlineKeyboardMarkup(rows)


def setup_done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🏠 Go to Home", CB.HOME)],
    ])

def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn("📊 Stats", CB.ADMIN_STATS),
            _btn("👥 Users", CB.ADMIN_USERS),
        ],
        [_btn("↩️ Home", CB.HOME)],
    ])


# ── Upload keyboards ──────────────────────────────────────────────────────────

def upload_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_btn("❌ Cancel Upload", CB.UPLOAD_CANCEL)]])


def upload_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn("📁 Choose Folder", CB.UPLOAD_CHOOSE_FOLDER),
            _btn("📥 Default Folder", CB.UPLOAD_TO_DEFAULT),
        ],
        [_btn("❌ Cancel", CB.UPLOAD_CANCEL)],
    ])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _file_icon(file_type: str) -> str:
    from src.core.utils import get_file_icon
    return get_file_icon(file_type)


def _pagination_row(
    prefix: str,
    pagination: dict,
    extra_arg: str = "",
) -> list[InlineKeyboardButton] | None:
    if pagination["total_pages"] <= 1:
        return None

    page = pagination["page"]
    total = pagination["total_pages"]
    buttons = []

    if pagination["has_prev"]:
        data = build_callback_data(prefix, extra_arg, page - 1) if extra_arg else build_callback_data(prefix, page - 1)
        buttons.append(_btn("⬅️", data))

    buttons.append(_btn(f"{page}/{total}", CB.NOOP))

    if pagination["has_next"]:
        data = build_callback_data(prefix, extra_arg, page + 1) if extra_arg else build_callback_data(prefix, page + 1)
        buttons.append(_btn("➡️", data))

    return buttons if buttons else None
