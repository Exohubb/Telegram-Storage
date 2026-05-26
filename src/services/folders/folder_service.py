from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config.settings import get_settings
from src.core.errors import (
    FolderAlreadyExistsError,
    FolderNotEmptyError,
    FolderNotFoundError,
    ForbiddenError,
    ValidationError,
)
from src.core.logging import get_logger
from src.core.utils import sanitize_name
from src.db.models import Folder
from src.db.repositories.folder_repo import FolderRepository
from src.services.audit.audit_service import AuditService

logger = get_logger(__name__)


class FolderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FolderRepository(session)
        self.audit = AuditService(session)

    async def get_user_folders(
        self,
        user_id: int,
        parent_id: int | None = None,
        page: int = 1,
    ) -> tuple[list[Folder], int]:
        settings = get_settings()
        offset = (page - 1) * settings.page_size
        folders = await self.repo.get_user_folders(
            user_id, parent_id=parent_id, offset=offset, limit=settings.page_size
        )
        total = await self.repo.count_user_folders(user_id, parent_id=parent_id)
        return folders, total

    async def get_folder(self, folder_id: int, user_id: int) -> Folder:
        folder = await self.repo.get_by_id_and_user(folder_id, user_id)
        if not folder:
            raise FolderNotFoundError(folder_id)
        return folder

    async def get_default_folder(self, user_id: int) -> Folder | None:
        return await self.repo.get_default_folder(user_id)

    async def create_folder(
        self,
        user_id: int,
        name: str,
        parent_id: int | None = None,
    ) -> Folder:
        settings = get_settings()
        name = sanitize_name(name, settings.max_folder_name_length)
        if not name:
            raise ValidationError("Folder name cannot be empty.", "name")
        if len(name) > settings.max_folder_name_length:
            raise ValidationError(
                f"Folder name too long (max {settings.max_folder_name_length} chars).", "name"
            )

        # Validate parent belongs to user
        if parent_id is not None:
            parent = await self.repo.get_by_id_and_user(parent_id, user_id)
            if not parent:
                raise FolderNotFoundError(parent_id)

        existing = await self.repo.get_by_name_and_parent(user_id, name, parent_id)
        if existing:
            raise FolderAlreadyExistsError(name)

        folder = Folder(user_id=user_id, name=name, parent_id=parent_id)
        folder = await self.repo.save(folder)
        await self.audit.log(user_id, "folder_created", "folder", folder.id, {"name": name})
        logger.info("Folder created", user_id=user_id, folder_id=folder.id, name=name)
        return folder

    async def rename_folder(self, folder_id: int, user_id: int, new_name: str) -> Folder:
        settings = get_settings()
        new_name = sanitize_name(new_name, settings.max_folder_name_length)
        if not new_name:
            raise ValidationError("Folder name cannot be empty.", "name")

        folder = await self.get_folder(folder_id, user_id)

        # Check name collision in same parent
        existing = await self.repo.get_by_name_and_parent(user_id, new_name, folder.parent_id)
        if existing and existing.id != folder_id:
            raise FolderAlreadyExistsError(new_name)

        old_name = folder.name
        await self.repo.rename(folder_id, new_name)
        await self.audit.log(
            user_id, "folder_renamed", "folder", folder_id, {"old": old_name, "new": new_name}
        )
        folder.name = new_name
        return folder

    async def delete_folder(
        self, folder_id: int, user_id: int, force: bool = False
    ) -> None:
        folder = await self.get_folder(folder_id, user_id)

        if folder.is_default:
            raise ForbiddenError("delete the default folder")

        file_count = await self.repo.count_files_in_folder(folder_id)
        if file_count > 0 and not force:
            raise FolderNotEmptyError()

        await self.repo.delete(folder)
        await self.audit.log(user_id, "folder_deleted", "folder", folder_id, {"name": folder.name})
        logger.info("Folder deleted", user_id=user_id, folder_id=folder_id)

    async def get_all_user_folders_flat(self, user_id: int) -> list[Folder]:
        """Return all folders for a user (for move-target picker)."""
        folders = await self.repo.get_user_folders(user_id, parent_id=None, limit=200)
        return folders
