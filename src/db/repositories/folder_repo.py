from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Folder
from src.db.repositories.base import BaseRepository


class FolderRepository(BaseRepository[Folder]):
    model = Folder

    async def get_user_folders(
        self,
        user_id: int,
        parent_id: int | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Folder]:
        stmt = (
            select(Folder)
            .where(Folder.user_id == user_id)
            .order_by(Folder.name)
            .offset(offset)
            .limit(limit)
        )
        if parent_id is None:
            stmt = stmt.where(Folder.parent_id.is_(None))
        else:
            stmt = stmt.where(Folder.parent_id == parent_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_user_folders(self, user_id: int, parent_id: int | None = None) -> int:
        stmt = select(func.count()).select_from(Folder).where(Folder.user_id == user_id)
        if parent_id is None:
            stmt = stmt.where(Folder.parent_id.is_(None))
        else:
            stmt = stmt.where(Folder.parent_id == parent_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id_and_user(self, folder_id: int, user_id: int) -> Folder | None:
        return await self._one_or_none(
            Folder.id == folder_id, Folder.user_id == user_id
        )

    async def get_by_name_and_parent(
        self, user_id: int, name: str, parent_id: int | None = None
    ) -> Folder | None:
        stmt = select(Folder).where(
            Folder.user_id == user_id,
            Folder.name == name,
        )
        if parent_id is None:
            stmt = stmt.where(Folder.parent_id.is_(None))
        else:
            stmt = stmt.where(Folder.parent_id == parent_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_default_folder(self, user_id: int) -> Folder | None:
        return await self._one_or_none(
            Folder.user_id == user_id, Folder.is_default == True  # noqa: E712
        )

    async def rename(self, folder_id: int, new_name: str) -> None:
        await self.session.execute(
            update(Folder).where(Folder.id == folder_id).values(name=new_name)
        )
        await self.session.flush()

    async def count_files_in_folder(self, folder_id: int) -> int:
        from sqlalchemy import func
        from src.db.models import File
        result = await self.session.execute(
            select(func.count())
            .select_from(File)
            .where(File.folder_id == folder_id, File.is_deleted == False)  # noqa: E712
        )
        return result.scalar_one()

    async def count_total_folders(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Folder))
        return result.scalar_one()
