"""
Base repository with common CRUD helpers.
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, record_id: int) -> ModelT | None:
        return await self.session.get(self.model, record_id)

    async def save(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def _all(self, *where: Any) -> list[ModelT]:
        stmt = select(self.model)
        if where:
            stmt = stmt.where(*where)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _one_or_none(self, *where: Any) -> ModelT | None:
        stmt = select(self.model).where(*where)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
