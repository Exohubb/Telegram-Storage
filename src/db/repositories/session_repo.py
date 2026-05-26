from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import OperationFailure, ProcessedUpdate, UploadSession
from src.db.repositories.base import BaseRepository


class UploadSessionRepository(BaseRepository[UploadSession]):
    model = UploadSession

    async def get_active_session(self, user_id: int) -> UploadSession | None:
        return await self._one_or_none(UploadSession.user_id == user_id)

    async def upsert_session(
        self,
        user_id: int,
        folder_id: int | None,
        state: str,
        expires_at: datetime,
    ) -> UploadSession:
        existing = await self.get_active_session(user_id)
        if existing:
            existing.folder_id = folder_id
            existing.state = state
            existing.expires_at = expires_at
            await self.session.flush()
            return existing

        session = UploadSession(
            user_id=user_id,
            folder_id=folder_id,
            state=state,
            expires_at=expires_at,
        )
        return await self.save(session)

    async def delete_session(self, user_id: int) -> None:
        await self.session.execute(
            delete(UploadSession).where(UploadSession.user_id == user_id)
        )
        await self.session.flush()

    async def delete_expired_sessions(self, now: datetime) -> int:
        result = await self.session.execute(
            delete(UploadSession).where(UploadSession.expires_at < now)
        )
        await self.session.flush()
        return result.rowcount


class ProcessedUpdateRepository(BaseRepository[ProcessedUpdate]):
    model = ProcessedUpdate

    async def is_processed(self, update_id: int) -> bool:
        result = await self.session.get(ProcessedUpdate, update_id)
        return result is not None

    async def mark_processed(self, update_id: int) -> None:
        record = ProcessedUpdate(update_id=update_id)
        self.session.add(record)
        try:
            await self.session.flush()
        except Exception:
            # Already exists — idempotent
            await self.session.rollback()

    async def cleanup_old_updates(self, before: datetime) -> int:
        result = await self.session.execute(
            delete(ProcessedUpdate).where(ProcessedUpdate.processed_at < before)
        )
        await self.session.flush()
        return result.rowcount


class OperationFailureRepository(BaseRepository[OperationFailure]):
    model = OperationFailure

    async def log_failure(
        self,
        operation: str,
        error_message: str,
        user_id: int | None = None,
        error_code: str | None = None,
        context: str | None = None,
    ) -> OperationFailure:
        failure = OperationFailure(
            user_id=user_id,
            operation=operation,
            error_code=error_code,
            error_message=error_message,
            context=context,
        )
        return await self.save(failure)

    async def get_recent_failures(self, limit: int = 50) -> list[OperationFailure]:
        stmt = (
            select(OperationFailure)
            .where(OperationFailure.resolved == False)  # noqa: E712
            .order_by(OperationFailure.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_unresolved(self) -> int:
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count())
            .select_from(OperationFailure)
            .where(OperationFailure.resolved == False)  # noqa: E712
        )
        return result.scalar_one()
