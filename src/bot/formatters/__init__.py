"""
Message formatters: produce clean, consistent Telegram HTML messages.
All user-visible text lives here — no raw strings in handlers.
"""

from datetime import datetime

from src.core.utils import (
    escape_html,
    format_datetime,
    format_file_size,
    format_relative_time,
    get_file_icon,
    truncate,
)
from src.db.models import File, Folder, User


# ── Home / Welcome ────────────────────────────────────────────────────────────

def fmt_welcome(user: User, is_new: bool) -> str:
    name = escape_html(user.first_name)
    if is_new:
        return (
            f"👋 Welcome, <b>{name}</b>!\n\n"
            "I'm your personal cloud storage bot. Your files are stored securely "
            "in a private Telegram vault — nothing is kept on any external server.\n\n"
            "<b>Getting started:</b>\n"
            "• Create a folder with 📁 <b>Folders</b>\n"
            "• Upload files directly into any folder\n"
            "• Browse, search, and manage everything from here\n\n"
            "Use the menu below to navigate."
        )
    return (
        f"👋 Welcome back, <b>{name}</b>!\n\n"
        "What would you like to do?"
    )


def fmt_home() -> str:
    return "🗄 <b>My Storage</b>\n\nChoose an option below."


# ── Folders ───────────────────────────────────────────────────────────────────

def fmt_folder_list(folders: list[Folder], pagination: dict, total_folders: int) -> str:
    if not folders:
        return (
            "📁 <b>Folders</b>\n\n"
            "<i>No folders yet. Create one to get started.</i>"
        )
    page = pagination["page"]
    total_pages = pagination["total_pages"]
    header = f"📁 <b>Folders</b>  <i>({total_folders} total)</i>"
    if total_pages > 1:
        header += f"  · Page {page}/{total_pages}"
    return header


def fmt_folder_detail(folder: Folder, file_count: int) -> str:
    name = escape_html(folder.name)
    created = format_datetime(folder.created_at)
    return (
        f"📁 <b>{name}</b>\n\n"
        f"📄 Files: <b>{file_count}</b>\n"
        f"🗓 Created: {created}"
    )


def fmt_folder_created(folder: Folder) -> str:
    return f"✅ Folder <b>{escape_html(folder.name)}</b> created."


def fmt_folder_renamed(old_name: str, new_name: str) -> str:
    return f"✅ Renamed to <b>{escape_html(new_name)}</b>."


def fmt_folder_deleted(name: str) -> str:
    return f"🗑 Folder <b>{escape_html(name)}</b> deleted."


def fmt_ask_folder_name(action: str = "create") -> str:
    verb = "name" if action == "create" else "new name for"
    return f"✏️ Enter a {verb} the folder:"


def fmt_folder_not_empty_warning(name: str, count: int) -> str:
    return (
        f"⚠️ <b>{escape_html(name)}</b> contains <b>{count}</b> file(s).\n\n"
        "Deleting this folder will move its files to your default folder. Continue?"
    )


# ── Files ─────────────────────────────────────────────────────────────────────

def fmt_file_list(
    files: list[File],
    folder_name: str | None,
    pagination: dict,
    total: int,
) -> str:
    if not files:
        location = f"<b>{escape_html(folder_name)}</b>" if folder_name else "this folder"
        return f"📂 No files in {location} yet.\n\nUpload something to get started."

    page = pagination["page"]
    total_pages = pagination["total_pages"]
    location = f"📁 <b>{escape_html(folder_name)}</b>" if folder_name else "🗂 <b>All Files</b>"
    header = f"{location}  <i>({total} files)</i>"
    if total_pages > 1:
        header += f"  · Page {page}/{total_pages}"
    return header


def fmt_file_card(file: File, show_folder: bool = False) -> str:
    icon = get_file_icon(file.file_type)
    name = escape_html(truncate(file.label, 40))
    size = format_file_size(file.file_size)
    age = format_relative_time(file.created_at)
    fav = " ⭐" if file.is_favorite else ""
    tags = ""
    if file.tags:
        tag_list = " ".join(f"#{t.tag}" for t in file.tags[:3])
        tags = f"\n🏷 {escape_html(tag_list)}"
    folder_line = ""
    if show_folder and file.folder:
        folder_line = f"\n📁 {escape_html(file.folder.name)}"
    return f"{icon} <b>{name}</b>{fav}\n📦 {size}  ·  🕘 {age}{folder_line}{tags}"


def fmt_file_detail(file: File) -> str:
    icon = get_file_icon(file.file_type)
    name = escape_html(file.label)
    original = escape_html(file.original_filename or "—")
    size = format_file_size(file.file_size)
    mime = escape_html(file.mime_type or "—")
    file_type = file.file_type.capitalize()
    created = format_datetime(file.created_at)
    updated = format_datetime(file.updated_at)
    fav = "⭐ Yes" if file.is_favorite else "No"
    folder_name = escape_html(file.folder.name) if file.folder else "—"
    tags = ", ".join(f"#{t.tag}" for t in file.tags) if file.tags else "—"

    return (
        f"{icon} <b>{name}</b>\n\n"
        f"📄 Original: <code>{original}</code>\n"
        f"📦 Size: {size}\n"
        f"🗂 Type: {file_type}  ·  <code>{mime}</code>\n"
        f"📁 Folder: {folder_name}\n"
        f"⭐ Favorite: {fav}\n"
        f"🏷 Tags: {escape_html(tags)}\n"
        f"🗓 Uploaded: {created}\n"
        f"✏️ Modified: {updated}"
    )


def fmt_file_renamed(new_label: str) -> str:
    return f"✅ Renamed to <b>{escape_html(new_label)}</b>."


def fmt_file_moved(file: File, folder_name: str | None) -> str:
    dest = f"<b>{escape_html(folder_name)}</b>" if folder_name else "the default folder"
    return f"✅ <b>{escape_html(file.label)}</b> moved to {dest}."


def fmt_file_deleted(label: str) -> str:
    return f"🗑 <b>{escape_html(label)}</b> moved to trash."


def fmt_file_restored(label: str) -> str:
    return f"♻️ <b>{escape_html(label)}</b> restored."


def fmt_file_permanently_deleted(label: str) -> str:
    return f"❌ <b>{escape_html(label)}</b> permanently deleted."


def fmt_favorite_toggled(file: File) -> str:
    if file.is_favorite:
        return f"⭐ <b>{escape_html(file.label)}</b> added to favorites."
    return f"<b>{escape_html(file.label)}</b> removed from favorites."


def fmt_tag_added(tag: str) -> str:
    return f"✅ Tag <b>#{escape_html(tag)}</b> added."


def fmt_tag_removed(tag: str) -> str:
    return f"✅ Tag <b>#{escape_html(tag)}</b> removed."


def fmt_ask_tag() -> str:
    return "🏷 Enter a tag to add (letters, numbers, hyphens only):"


def fmt_ask_rename_file() -> str:
    return "✏️ Enter a new name for this file:"


def fmt_ask_rename_folder() -> str:
    return "✏️ Enter a new name for this folder:"


# ── Upload ────────────────────────────────────────────────────────────────────

def fmt_upload_ready(folder_name: str | None) -> str:
    dest = f"<b>{escape_html(folder_name)}</b>" if folder_name else "your default folder"
    return (
        f"⬆️ Ready to upload into {dest}.\n\n"
        "Send your file now. You can send multiple files in a row.\n"
        "Tap <b>Cancel</b> when done."
    )


def fmt_upload_success(file: File) -> str:
    icon = get_file_icon(file.file_type)
    return (
        f"✅ {icon} <b>{escape_html(file.label)}</b> saved.\n"
        f"📦 {format_file_size(file.file_size)}"
    )


def fmt_upload_choose_folder() -> str:
    return "📁 Choose a folder for this file, or use your default folder:"


# ── Views ─────────────────────────────────────────────────────────────────────

def fmt_recent_files(files: list[File]) -> str:
    if not files:
        return "🕘 <b>Recent Files</b>\n\n<i>No recent uploads yet.</i>"
    lines = ["🕘 <b>Recent Files</b>\n"]
    for f in files[:10]:
        icon = get_file_icon(f.file_type)
        age = format_relative_time(f.created_at)
        lines.append(f"{icon} {escape_html(truncate(f.label, 30))}  <i>{age}</i>")
    return "\n".join(lines)


def fmt_favorites_header(total: int, pagination: dict) -> str:
    if total == 0:
        return "⭐ <b>Favorites</b>\n\n<i>No favorites yet. Star a file to add it here.</i>"
    page = pagination["page"]
    total_pages = pagination["total_pages"]
    header = f"⭐ <b>Favorites</b>  <i>({total} files)</i>"
    if total_pages > 1:
        header += f"  · Page {page}/{total_pages}"
    return header


def fmt_trash_header(total: int, pagination: dict) -> str:
    if total == 0:
        return "🗑 <b>Trash</b>\n\n<i>Trash is empty.</i>"
    page = pagination["page"]
    total_pages = pagination["total_pages"]
    header = f"🗑 <b>Trash</b>  <i>({total} files)</i>"
    if total_pages > 1:
        header += f"  · Page {page}/{total_pages}"
    return header


# ── Search ────────────────────────────────────────────────────────────────────

def fmt_search_prompt() -> str:
    return (
        "🔍 <b>Search</b>\n\n"
        "Type a filename, or use the buttons to filter by type."
    )


def fmt_search_results(query: str | None, total: int, pagination: dict) -> str:
    if total == 0:
        q = f' for "<b>{escape_html(query)}</b>"' if query else ""
        return f"🔍 No results{q}."
    page = pagination["page"]
    total_pages = pagination["total_pages"]
    q = f' "<b>{escape_html(query)}</b>"' if query else ""
    header = f"🔍 <b>Results{q}</b>  <i>({total} files)</i>"
    if total_pages > 1:
        header += f"  · Page {page}/{total_pages}"
    return header


# ── Settings ──────────────────────────────────────────────────────────────────

def fmt_settings(upload_behavior: str) -> str:
    behavior = "Ask which folder" if upload_behavior == "ask" else "Use default folder"
    return (
        "⚙️ <b>Settings</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📤 <b>Upload behavior</b>\n"
        f"  └ {behavior}\n\n"
        "Tap any option below to change it."
    )


def fmt_settings_full(upload_behavior: str, notifications: bool, page_size: int) -> str:
    behavior = "Ask which folder" if upload_behavior == "ask" else "Default folder"
    notif = "On" if notifications else "Off"
    return (
        "⚙️ <b>Settings</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📤 Upload behavior  ·  <b>{behavior}</b>\n"
        f"🔔 Notifications  ·  <b>{notif}</b>\n"
        f"📄 Files per page  ·  <b>{page_size}</b>\n\n"
        "<i>Tap any row to toggle or change.</i>"
    )


# ── Setup Wizard ──────────────────────────────────────────────────────────────

def fmt_setup_welcome() -> str:
    return (
        "🛠 <b>Vault Setup Wizard</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "This bot stores your files in a <b>private Telegram channel</b> "
        "that only you and the bot can access.\n\n"
        "You need to create that channel once and connect it here.\n\n"
        "⏱ Takes about <b>2 minutes</b>.\n\n"
        "Tap <b>Start Setup</b> when ready."
    )


def fmt_setup_step1() -> str:
    return (
        "🛠 <b>Setup</b>  ·  Step 1 of 3\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📢 <b>Create a Private Channel</b>\n\n"
        "  1. Open Telegram\n"
        "  2. Tap the ✏️ compose icon\n"
        "  3. Select <b>New Channel</b>\n"
        "  4. Give it any name (e.g. <i>My Vault</i>)\n"
        "  5. Set it to <b>Private</b>\n"
        "  6. Skip adding subscribers\n\n"
        "✅ Done? Tap <b>Next</b> to continue."
    )


def fmt_setup_step2() -> str:
    return (
        "🛠 <b>Setup</b>  ·  Step 2 of 3\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🤖 <b>Add the Bot as Admin</b>\n\n"
        "  1. Open your new channel\n"
        "  2. Tap the channel name at the top\n"
        "  3. Go to <b>Administrators</b>\n"
        "  4. Tap <b>Add Administrator</b>\n"
        "  5. Search for this bot's username\n"
        "  6. Enable these permissions:\n"
        "       ✅ Post Messages\n"
        "       ✅ Delete Messages\n"
        "  7. Tap <b>Save</b>\n\n"
        "✅ Done? Tap <b>Next</b> to continue."
    )


def fmt_setup_step3() -> str:
    return (
        "🛠 <b>Setup</b>  ·  Step 3 of 3\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🆔 <b>Get Your Channel ID</b>\n\n"
        "  1. Open your vault channel\n"
        "  2. Send any message in it\n"
        "  3. <b>Forward that message</b> to 👉 @idbot\n"
        "  4. @idbot will reply with a number\n"
        "       starting with <code>-100...</code>\n\n"
        "  5. Copy that number\n"
        "  6. Send it here in this chat\n\n"
        "<i>Example: <code>-1001987654321</code></i>\n\n"
        "⬇️ <b>Paste your channel ID below:</b>"
    )


def fmt_setup_done(channel_id: int) -> str:
    return (
        "✅ <b>Vault Connected!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔐 Channel ID: <code>{channel_id}</code>\n\n"
        "Your storage vault is now active.\n\n"
        "You can now:\n"
        "  📁 Create folders\n"
        "  ⬆️ Upload files\n"
        "  🔍 Search and manage everything\n\n"
        "Tap <b>Go to Home</b> to get started."
    )


def fmt_setup_invalid_id() -> str:
    return (
        "⚠️ That doesn't look like a valid channel ID.\n\n"
        "It should be a negative number starting with <code>-100</code>\n"
        "Example: <code>-1001987654321</code>\n\n"
        "Please try again:"
    )

def fmt_help() -> str:
    return (
        "❓ <b>Help &amp; Guide</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "📤 <b>Uploading Files</b>\n"
        "  1. Tap 📁 <b>Folders</b> → open a folder\n"
        "  2. Tap <b>Upload Here</b> → send your file\n"
        "  <i>Or just send a file directly — the bot will ask where to put it.</i>\n\n"

        "📁 <b>Folders</b>\n"
        "  • Create folders to organize your files\n"
        "  • Rename or delete folders anytime\n"
        "  • Deleting a folder moves its files to your default folder\n\n"

        "🔍 <b>Search</b>\n"
        "  • Search by filename, file type, or tag\n"
        "  • Use /search or tap 🔍 from the home menu\n\n"

        "🏷 <b>Tags</b>\n"
        "  • Add tags to files for quick filtering\n"
        "  • Open a file → tap 🏷 Tags → add or remove\n\n"

        "⭐ <b>Favorites</b>\n"
        "  • Star important files for quick access\n"
        "  • Open a file → tap ⭐ Favorite\n\n"

        "🗑 <b>Trash</b>\n"
        "  • Deleted files go to trash first — nothing is lost immediately\n"
        "  • Restore or permanently delete from the 🗑 Trash view\n\n"

        "🔒 <b>Privacy &amp; Storage</b>\n"
        "  • Your files live in <b>your own private Telegram channel</b>\n"
        "  • This server stores only metadata — <b>never the file bytes</b>\n"
        "  • Only you can access your files\n\n"

        "⚙️ <b>Settings</b>\n"
        "  • Change upload behavior, notifications, and more\n"
        "  • Use /settings to open\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Commands</b>\n"
        "/start — Home dashboard\n"
        "/upload — Start uploading\n"
        "/folders — Browse folders\n"
        "/files — All files\n"
        "/search — Search files\n"
        "/favorites — Starred files\n"
        "/recent — Recent uploads\n"
        "/trash — Deleted files\n"
        "/settings — Preferences\n"
        "/setup — Vault setup guide\n"
        "/help — This screen"
    )


# ── Admin ─────────────────────────────────────────────────────────────────────

def fmt_admin_stats(
    total_users: int,
    total_files: int,
    total_folders: int,
    unresolved_failures: int,
) -> str:
    return (
        "📊 <b>Admin Stats</b>\n\n"
        f"👥 Users: <b>{total_users}</b>\n"
        f"📄 Files: <b>{total_files}</b>\n"
        f"📁 Folders: <b>{total_folders}</b>\n"
        f"⚠️ Unresolved errors: <b>{unresolved_failures}</b>"
    )


# ── Errors ────────────────────────────────────────────────────────────────────

def fmt_error(message: str) -> str:
    return f"⚠️ {escape_html(message)}"


def fmt_generic_error() -> str:
    return "⚠️ Something went wrong. Please try again."
