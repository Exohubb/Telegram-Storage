import html
import math
import re
from datetime import datetime, timezone

from src.core.constants import FILE_TYPE_ICONS, MIME_TO_FILE_TYPE, FileType


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def format_file_size(size_bytes: int | None) -> str:
    if not size_bytes:
        return "Unknown size"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    return f"{size_bytes / 1024 ** 3:.1f} GB"


def format_datetime(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d %b %Y, %H:%M")


def format_relative_time(dt: datetime | None) -> str:
    if not dt:
        return "—"
    now = utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        mins = seconds // 60
        return f"{mins}m ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h ago"
    if seconds < 86400 * 7:
        days = seconds // 86400
        return f"{days}d ago"
    return format_datetime(dt)


def detect_file_type(
    mime_type: str | None = None,
    telegram_type: str | None = None,
) -> str:
    """Detect FileType from Telegram message type or MIME type."""
    if telegram_type:
        type_map = {
            "photo": FileType.IMAGE,
            "video": FileType.VIDEO,
            "audio": FileType.AUDIO,
            "voice": FileType.VOICE,
            "video_note": FileType.VIDEO_NOTE,
            "sticker": FileType.STICKER,
            "animation": FileType.ANIMATION,
            "document": FileType.DOCUMENT,
        }
        if telegram_type in type_map:
            return type_map[telegram_type]

    if mime_type:
        for prefix, file_type in MIME_TO_FILE_TYPE.items():
            if mime_type.startswith(prefix):
                return file_type

    return FileType.OTHER


def get_file_icon(file_type: str) -> str:
    return FILE_TYPE_ICONS.get(file_type, "📎")


def escape_html(text: str | None) -> str:
    if not text:
        return ""
    return html.escape(str(text))


def sanitize_name(name: str, max_length: int = 64) -> str:
    """Strip dangerous characters and enforce length limit."""
    # Remove control characters and null bytes
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name).strip()
    return name[:max_length]


def sanitize_tag(tag: str, max_length: int = 32) -> str:
    """Normalize tag: lowercase, strip whitespace, remove special chars."""
    tag = tag.lower().strip()
    tag = re.sub(r"[^\w\-]", "", tag)
    return tag[:max_length]


def paginate(total: int, page: int, page_size: int) -> dict:
    """Return pagination metadata."""
    total_pages = max(1, math.ceil(total / page_size))
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "offset": offset,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


def build_callback_data(*parts: str | int) -> str:
    """Join callback data parts with ':' separator."""
    return ":".join(str(p) for p in parts)


def parse_callback_data(data: str) -> list[str]:
    return data.split(":")


def truncate(text: str, max_len: int = 30, suffix: str = "…") -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix
