from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import File, FileTag
from src.db.repositories.base import BaseRepository


class FileRepository(BaseRepository[File]):
    model = File

    async def get_by_id_and_user(self, file_id: int, user_id: int) -> File | None:
        stmt = (
            select(File)
            .options(selectinload(File.tags))
            .where(File.id == file_id, File.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_files_in_folder(
        self,
        user_id: int,
        folder_id: int | None,
        offset: int = 0,
        limit: int = 10,
        include_deleted: bool = False,
    ) -> list[File]:
        stmt = (
            select(File)
            .options(selectinload(File.tags))
            .where(File.user_id == user_id)
            .order_by(File.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if folder_id is None:
            stmt = stmt.where(File.folder_id.is_(None))
        else:
            stmt = stmt.where(File.folder_id == folder_id)
        if not include_deleted:
            stmt = stmt.where(File.is_deleted == False)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_files_in_folder(
        self, user_id: int, folder_id: int | None, include_deleted: bool = False
    ) -> int:
        stmt = select(func.count()).select_from(File).where(File.user_id == user_id)
        if folder_id is None:
            stmt = stmt.where(File.folder_id.is_(None))
        else:
            stmt = stmt.where(File.folder_id == folder_id)
        if not include_deleted:
            stmt = stmt.where(File.is_deleted == False)  # noqa: E712
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_recent_files(self, user_id: int, limit: int = 20) -> list[File]:
        stmt = (
            select(File)
            .options(selectinload(File.tags))
            .where(File.user_id == user_id, File.is_deleted == False)  # noqa: E712
            .order_by(File.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_favorites(
        self, user_id: int, offset: int = 0, limit: int = 10
    ) -> list[File]:
        stmt = (
            select(File)
            .options(selectinload(File.tags))
            .where(
                File.user_id == user_id,
                File.is_favorite == True,  # noqa: E712
                File.is_deleted == False,  # noqa: E712
            )
            .order_by(File.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_favorites(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(File)
            .where(
                File.user_id == user_id,
                File.is_favorite == True,  # noqa: E712
                File.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one()

    async def get_trash(self, user_id: int, offset: int = 0, limit: int = 10) -> list[File]:
        stmt = (
            select(File)
            .options(selectinload(File.tags))
            .where(File.user_id == user_id, File.is_deleted == True)  # noqa: E712
            .order_by(File.deleted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_trash(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(File)
            .where(File.user_id == user_id, File.is_deleted == True)  # noqa: E712
        )
        return result.scalar_one()

    async def search(
        self,
        user_id: int,
        query: str | None = None,
        file_type: str | None = None,
        folder_id: int | None = None,
        tag: str | None = None,
        offset: int = 0,
        limit: int = 10,
    ) -> list[File]:
        stmt = (
            select(File)
            .options(selectinload(File.tags))
            .where(File.user_id == user_id, File.is_deleted == False)  # noqa: E712
        )
        if query:
            pattern = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(File.label).like(pattern),
                    func.lower(File.original_filename).like(pattern),
                )
            )
        if file_type:
            stmt = stmt.where(File.file_type == file_type)
        if folder_id is not None:
            stmt = stmt.where(File.folder_id == folder_id)
        if tag:
            stmt = stmt.join(FileTag, File.id == FileTag.file_id).where(
                func.lower(FileTag.tag) == tag.lower()
            )
        stmt = stmt.order_by(File.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_search(
        self,
        user_id: int,
        query: str | None = None,
        file_type: str | None = None,
        folder_id: int | None = None,
        tag: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(File)
            .where(File.user_id == user_id, File.is_deleted == False)  # noqa: E712
        )
        if query:
            pattern = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(File.label).like(pattern),
                    func.lower(File.original_filename).like(pattern),
                )
            )
        if file_type:
            stmt = stmt.where(File.file_type == file_type)
        if folder_id is not None:
            stmt = stmt.where(File.folder_id == folder_id)
        if tag:
            stmt = stmt.join(FileTag, File.id == FileTag.file_id).where(
                func.lower(FileTag.tag) == tag.lower()
            )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def soft_delete(self, file_id: int, deleted_at: datetime) -> None:
        await self.session.execute(
            update(File)
            .where(File.id == file_id)
            .values(is_deleted=True, deleted_at=deleted_at)
        )
        await self.session.flush()

    async def restore(self, file_id: int) -> None:
        await self.session.execute(
            update(File)
            .where(File.id == file_id)
            .values(is_deleted=False, deleted_at=None)
        )
        await self.session.flush()

    async def toggle_favorite(self, file_id: int, is_favorite: bool) -> None:
        await self.session.execute(
            update(File).where(File.id == file_id).values(is_favorite=is_favorite)
        )
        await self.session.flush()

    async def rename(self, file_id: int, new_label: str) -> None:
        await self.session.execute(
            update(File).where(File.id == file_id).values(label=new_label)
        )
        await self.session.flush()

    async def move(self, file_id: int, folder_id: int | None) -> None:
        await self.session.execute(
            update(File).where(File.id == file_id).values(folder_id=folder_id)
        )
        await self.session.flush()

    async def count_total_files(self, include_deleted: bool = False) -> int:
        stmt = select(func.count()).select_from(File)
        if not include_deleted:
            stmt = stmt.where(File.is_deleted == False)  # noqa: E712
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_recent_uploads_admin(self, limit: int = 20) -> list[File]:
        stmt = (
            select(File)
            .options(selectinload(File.tags))
            .order_by(File.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class FileTagRepository(BaseRepository[FileTag]):
    model = FileTag

    async def get_tags_for_file(self, file_id: int) -> list[FileTag]:
        return await self._all(FileTag.file_id == file_id)

    async def get_tag(self, file_id: int, tag: str) -> FileTag | None:
        return await self._one_or_none(
            FileTag.file_id == file_id, FileTag.tag == tag.lower()
        )

    async def count_tags_for_file(self, file_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(FileTag).where(FileTag.file_id == file_id)
        )
        return result.scalar_one()

    async def delete_tag(self, file_id: int, tag: str) -> bool:
        tag_obj = await self.get_tag(file_id, tag)
        if not tag_obj:
            return False
        await self.delete(tag_obj)
        return True
