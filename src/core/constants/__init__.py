from enum import StrEnum


class FileType(StrEnum):
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    STICKER = "sticker"
    ANIMATION = "animation"
    OTHER = "other"


class UploadState(StrEnum):
    WAITING_FILE = "waiting_file"
    WAITING_FOLDER_CHOICE = "waiting_folder_choice"


class UserState(StrEnum):
    IDLE = "idle"
    UPLOADING = "uploading"
    RENAMING_FILE = "renaming_file"
    RENAMING_FOLDER = "renaming_folder"
    CREATING_FOLDER = "creating_folder"
    ADDING_TAGS = "adding_tags"
    SEARCHING = "searching"
    MOVING_FILE = "moving_file"
    SETUP_WAITING_ID = "setup_waiting_id"


# Callback data prefixes — kept short to stay within Telegram's 64-byte limit
class CB:
    # Navigation
    HOME = "home"
    MENU = "menu"
    BACK = "back"
    NOOP = "noop"

    # Folders
    FOLDER_LIST = "fl"
    FOLDER_OPEN = "fo"
    FOLDER_CREATE = "fc"
    FOLDER_RENAME = "fr"
    FOLDER_DELETE = "fd"
    FOLDER_DELETE_CONFIRM = "fdc"
    FOLDER_UPLOAD = "fu"

    # Files
    FILE_LIST = "xl"
    FILE_OPEN = "xo"
    FILE_GET = "xg"
    FILE_INFO = "xi"
    FILE_RENAME = "xr"
    FILE_MOVE = "xm"
    FILE_MOVE_TO = "xmt"
    FILE_DELETE = "xd"
    FILE_DELETE_CONFIRM = "xdc"
    FILE_FAVORITE = "xf"
    FILE_TAGS = "xt"
    FILE_TAG_ADD = "xta"
    FILE_TAG_REMOVE = "xtr"

    # Views
    VIEW_RECENT = "vr"
    VIEW_FAVORITES = "vf"
    VIEW_TRASH = "vt"
    VIEW_ALL = "va"
    VIEW_SEARCH = "vs"

    # Trash
    TRASH_RESTORE = "tr"
    TRASH_DELETE = "td"
    TRASH_DELETE_CONFIRM = "tdc"
    TRASH_EMPTY = "te"
    TRASH_EMPTY_CONFIRM = "tec"

    # Search
    SEARCH_START = "ss"
    SEARCH_BY_TYPE = "sbt"
    SEARCH_BY_FOLDER = "sbf"
    SEARCH_BY_TAG = "sbg"

    # Settings
    SETTINGS = "cfg"
    SETTINGS_UPLOAD_BEHAVIOR = "cfgub"
    SETTINGS_NOTIFICATIONS = "cfgn"
    SETTINGS_PAGE_SIZE = "cfgps"

    # Setup wizard
    SETUP_START = "swst"
    SETUP_STEP = "swsp"
    SETUP_DONE = "swdn"

    # Admin
    ADMIN_PANEL = "adm"
    ADMIN_STATS = "adms"
    ADMIN_USERS = "admu"
    ADMIN_BAN = "admb"
    ADMIN_BROADCAST = "admbc"

    # Pagination
    PAGE = "pg"

    # Upload
    UPLOAD_CANCEL = "uc"
    UPLOAD_TO_DEFAULT = "utd"
    UPLOAD_CHOOSE_FOLDER = "ucf"


# File type icons
FILE_TYPE_ICONS: dict[str, str] = {
    FileType.IMAGE: "🖼",
    FileType.VIDEO: "🎬",
    FileType.AUDIO: "🎵",
    FileType.VOICE: "🎙",
    FileType.VIDEO_NOTE: "📹",
    FileType.DOCUMENT: "📄",
    FileType.STICKER: "🎭",
    FileType.ANIMATION: "🎞",
    FileType.OTHER: "📎",
}

# MIME type to FileType mapping
MIME_TO_FILE_TYPE: dict[str, str] = {
    "image/": FileType.IMAGE,
    "video/": FileType.VIDEO,
    "audio/": FileType.AUDIO,
    "application/pdf": FileType.DOCUMENT,
    "application/zip": FileType.DOCUMENT,
    "application/x-zip": FileType.DOCUMENT,
    "application/x-rar": FileType.DOCUMENT,
    "application/x-tar": FileType.DOCUMENT,
    "application/gzip": FileType.DOCUMENT,
    "text/": FileType.DOCUMENT,
    "application/msword": FileType.DOCUMENT,
    "application/vnd.openxmlformats": FileType.DOCUMENT,
    "application/vnd.ms-": FileType.DOCUMENT,
}

DEFAULT_FOLDER_NAME = "My Files"

MAX_CALLBACK_DATA_LENGTH = 64

# How many recent files to show
RECENT_FILES_LIMIT = 20

# Permanent delete grace period (files in trash older than this can be auto-purged)
TRASH_RETENTION_DAYS = 30
