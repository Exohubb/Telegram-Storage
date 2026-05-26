"""
FileService: orchestrates file upload, retrieval, metadata management,
tagging, favorites, trash, and permanent deletion.

The actual file bytes never touch this server — StorageService handles
the Telegram vault copy/retrieve operations.
"""

from telegram import Bot, Message as TelegramMessage

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config.settings import get_settings
from src.core.errors import (
    FileAccessDeniedError,
    FileNotFoundError,
    FolderNotFoundError,
    TagDuplicateError,
    TagLimitExceededError,
    ValidationError,
)
from src.core.logging import get_logger
from src.core.utils import (
    detect_file_type,
    paginate,
    sanitize_name,
    sanitize_tag,
    utcnow,
)
from src.db.models import File, FileTag
from src.db.repositories.file_repo import FileRepository, FileTagRepository
from src.db.repositories.folder_repo import FolderRepository
from src.services.audit.audit_service import AuditService
from src.services.storage.storage_service import StorageService

logger = get_logger(__name__)


def _extract_file_info(tg_message: TelegramMessage) -> dict:
    """Extract file metadata from a Telegram message."""
    info: dict = {}

    if tg_message.document:
        doc = tg_message.document
        info.update(
            telegram_type="document",
            telegram_file_id=doc.file_id,
            telegram_file_unique_id=doc.file_unique_id,
            original_filename=doc.file_name,
            mime_type=doc.mime_type,
            file_size=doc.file_size,
        )
    elif tg_message.photo:
        photo = tg_message.photo[-1]  # largest size
        info.update(
            telegram_type="photo",
            telegram_file_id=photo.file_id,
            telegram_file_unique_id=photo.file_unique_id,
            file_size=photo.file_size,
            mime_type="image/jpeg",
        )
    elif tg_message.video:
        vid = tg_message.video
        info.update(
            telegram_type="video",
            telegram_file_id=vid.file_id,
            telegram_file_unique_id=vid.file_unique_id,
            original_filename=vid.file_name,
            mime_type=vid.mime_type,
            file_size=vid.file_size,
        )
    elif tg_message.audio:
        aud = tg_message.audio
        info.update(
            telegram_type="audio",
            telegram_file_id=aud.file_id,
            telegram_file_unique_id=aud.file_unique_id,
            original_filename=aud.file_name,
            mime_type=aud.mime_type,
            file_size=aud.file_size,
        )
    elif tg_message.voice:
        voice = tg_message.voice
        info.update(
            telegram_type="voice",
            telegram_file_id=voice.file_id,
            telegram_file_unique_id=voice.file_unique_id,
            mime_type=voice.mime_type,
            file_size=voice.file_size,
        )
    elif tg_message.video_note:
        vn = tg_message.video_note
        info.update(
            telegram_type="video_note",
            telegram_file_id=vn.file_id,
            telegram_file_unique_id=vn.file_unique_id,
            file_size=vn.file_size,
        )
    elif tg_message.animation:
        anim = tg_message.animation
        info.update(
            telegram_type="animation",
            telegram_file_id=anim.file_id,
            telegram_file_unique_id=anim.file_unique_id,
            original_filename=anim.file_name,
            mime_type=anim.mime_type,
            file_size=anim.file_size,
        )
    elif tg_message.sticker:
        sticker = tg_message.sticker
        info.update(
            telegram_type="sticker",
            telegram_file_id=sticker.file_id,
            telegram_file_unique_id=sticker.file_unique_id,
            file_size=sticker.file_size,
        )

    return info


class FileService:
    def __init__(self, session: AsyncSession, storage: StorageService) -> None:
        self.session = session
        self.storage = storage
        self.file_repo = FileRepository(session)
        self.tag_repo = FileTagRepository(session)
        self.folder_repo = FolderRepository(session)
        self.audit = AuditService(session)

    async def upload_file(
        self,
        user_id: int,
        tg_message: TelegramMessage,
        folder_id: int | None = None,
        label: str | None = None,
    ) -> File:
        """
        Core upload flow:
        1. Extract file metadata from Telegram message
        2. Copy message to vault channel (no bytes on server)
        3. Persist metadata + vault reference to DB
        """
        file_info = _extract_file_info(tg_message)
        if not file_info:
            raise ValidationError("Unsupported file type. Please send a document, image, video, or audio file.")

        # Validate folder ownership
        if folder_id is not None:
            folder = await self.folder_repo.get_by_id_and_user(folder_id, user_id)
            if not folder:
                raise FolderNotFoundError(folder_id)

        # Copy to vault — this is the only Telegram API call for upload
        vault_message = await self.storage.copy_to_vault(
            from_chat_id=tg_message.chat_id,
            message_id=tg_message.message_id,
        )

        telegram_type = file_info.pop("telegram_type", "document")
        original_filename = file_info.get("original_filename")
        mime_type = file_info.get("mime_type")
        file_type = detect_file_type(mime_type, telegram_type)

        # Derive label: user-provided > original filename > file type
        if not label:
            label = original_filename or f"{file_type.capitalize()} file"
        label = sanitize_name(label, 256)

        # Extract extension
        extension = None
        if original_filename and "." in original_filename:
            extension = original_filename.rsplit(".", 1)[-1].lower()[:32]

        file = File(
            user_id=user_id,
            folder_id=folder_id,
            label=label,
            original_filename=original_filename,
            extension=extension,
            mime_type=mime_type,
            file_size=file_info.get("file_size"),
            file_type=file_type,
            caption=tg_message.caption,
            source_chat_id=tg_message.chat_id,
            source_message_id=tg_message.message_id,
            telegram_file_id=file_info.get("telegram_file_id"),
            telegram_file_unique_id=file_info.get("telegram_file_unique_id"),
            vault_chat_id=self.storage.vault_channel_id,
            vault_message_id=vault_message.message_id,
        )
        file = await self.file_repo.save(file)
        await self.audit.log(user_id, "file_uploaded", "file", file.id, {"label": label, "folder_id": folder_id})
        logger.info("File uploaded", user_id=user_id, file_id=file.id, label=label)
        return file

    async def get_file(self, file_id: int, user_id: int) -> File:
        file = await self.file_repo.get_by_id_and_user(file_id, user_id)
        if not file:
            raise FileNotFoundError(file_id)
        return file

    async def retrieve_file(self, file_id: int, user_id: int, target_chat_id: int) -> None:
        """Send file from vault to user — no bytes on server."""
        file = await self.get_file(file_id, user_id)
        if file.is_deleted:
            raise FileNotFoundError(file_id)
        if not file.vault_message_id:
            from src.core.errors import StaleReferenceError
            raise StaleReferenceError(file_id)

        await self.storage.send_file_to_user(
            user_chat_id=target_chat_id,
            vault_message_id=file.vault_message_id,
        )
        await self.audit.log(user_id, "file_retrieved", "file", file_id)

    async def list_files(
        self,
        user_id: int,
        folder_id: int | None,
        page: int = 1,
    ) -> tuple[list[File], dict]:
        settings = get_settings()
        offset = (page - 1) * settings.page_size
        files = await self.file_repo.get_files_in_folder(
            user_id, folder_id, offset=offset, limit=settings.page_size
        )
        total = await self.file_repo.count_files_in_folder(user_id, folder_id)
        pagination = paginate(total, page, settings.page_size)
        return files, pagination

    async def get_recent(self, user_id: int) -> list[File]:
        from src.core.constants import RECENT_FILES_LIMIT
        return await self.file_repo.get_recent_files(user_id, RECENT_FILES_LIMIT)

    async def get_favorites(self, user_id: int, page: int = 1) -> tuple[list[File], dict]:
        settings = get_settings()
        offset = (page - 1) * settings.page_size
        files = await self.file_repo.get_favorites(user_id, offset=offset, limit=settings.page_size)
        total = await self.file_repo.count_favorites(user_id)
        pagination = paginate(total, page, settings.page_size)
        return files, pagination

    async def get_trash(self, user_id: int, page: int = 1) -> tuple[list[File], dict]:
        settings = get_settings()
        offset = (page - 1) * settings.page_size
        files = await self.file_repo.get_trash(user_id, offset=offset, limit=settings.page_size)
        total = await self.file_repo.count_trash(user_id)
        pagination = paginate(total, page, settings.page_size)
        return files, pagination

    async def rename_file(self, file_id: int, user_id: int, new_label: str) -> File:
        settings = get_settings()
        new_label = sanitize_name(new_label, 256)
        if not new_label:
            raise ValidationError("File name cannot be empty.")
        file = await self.get_file(file_id, user_id)
        await self.file_repo.rename(file_id, new_label)
        await self.audit.log(user_id, "file_renamed", "file", file_id, {"new_label": new_label})
        file.label = new_label
        return file

    async def move_file(self, file_id: int, user_id: int, target_folder_id: int | None) -> File:
        file = await self.get_file(file_id, user_id)
        if target_folder_id is not None:
            folder = await self.folder_repo.get_by_id_and_user(target_folder_id, user_id)
            if not folder:
                raise FolderNotFoundError(target_folder_id)
        await self.file_repo.move(file_id, target_folder_id)
        await self.audit.log(
            user_id, "file_moved", "file", file_id,
            {"from_folder": file.folder_id, "to_folder": target_folder_id}
        )
        file.folder_id = target_folder_id
        return file

    async def toggle_favorite(self, file_id: int, user_id: int) -> File:
        file = await self.get_file(file_id, user_id)
        new_state = not file.is_favorite
        await self.file_repo.toggle_favorite(file_id, new_state)
        await self.audit.log(user_id, "file_favorite_toggled", "file", file_id, {"is_favorite": new_state})
        file.is_favorite = new_state
        return file

    async def soft_delete(self, file_id: int, user_id: int) -> None:
        file = await self.get_file(file_id, user_id)
        if file.is_deleted:
            raise ValidationError("File is already in trash.")
        await self.file_repo.soft_delete(file_id, utcnow())
        await self.audit.log(user_id, "file_soft_deleted", "file", file_id)

    async def restore_file(self, file_id: int, user_id: int) -> File:
        file = await self.file_repo.get_by_id_and_user(file_id, user_id)
        if not file:
            raise FileNotFoundError(file_id)
        if not file.is_deleted:
            raise ValidationError("File is not in trash.")
        await self.file_repo.restore(file_id)
        await self.audit.log(user_id, "file_restored", "file", file_id)
        file.is_deleted = False
        file.deleted_at = None
        return file

    async def permanent_delete(
        self, file_id: int, user_id: int, delete_from_vault: bool = True
    ) -> None:
        file = await self.file_repo.get_by_id_and_user(file_id, user_id)
        if not file:
            raise FileNotFoundError(file_id)

        vault_message_id = file.vault_message_id

        await self.file_repo.delete(file)
        await self.audit.log(user_id, "file_permanently_deleted", "file", file_id)

        if delete_from_vault and vault_message_id:
            try:
                await self.storage.delete_from_vault(vault_message_id)
            except Exception as e:
                logger.warning(
                    "Could not delete vault message after permanent delete",
                    vault_message_id=vault_message_id,
                    error=str(e),
                )

    # ── Tag management ──────────────────────────────────────────────────────

    async def add_tag(self, file_id: int, user_id: int, tag: str) -> FileTag:
        settings = get_settings()
        tag = sanitize_tag(tag, settings.max_tag_length)
        if not tag:
            raise ValidationError("Tag cannot be empty.")

        file = await self.get_file(file_id, user_id)

        existing = await self.tag_repo.get_tag(file_id, tag)
        if existing:
            raise TagDuplicateError(tag)

        count = await self.tag_repo.count_tags_for_file(file_id)
        if count >= settings.max_tags_per_file:
            raise TagLimitExceededError(settings.max_tags_per_file)

        tag_obj = FileTag(file_id=file_id, tag=tag)
        tag_obj = await self.tag_repo.save(tag_obj)
        await self.audit.log(user_id, "tag_added", "file", file_id, {"tag": tag})
        return tag_obj

    async def remove_tag(self, file_id: int, user_id: int, tag: str) -> None:
        await self.get_file(file_id, user_id)  # ownership check
        removed = await self.tag_repo.delete_tag(file_id, tag)
        if not removed:
            raise ValidationError(f'Tag "{tag}" not found on this file.')
        await self.audit.log(user_id, "tag_removed", "file", file_id, {"tag": tag})
