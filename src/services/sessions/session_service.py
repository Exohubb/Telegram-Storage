from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config.settings import get_settings
from src.core.constants import UploadState
from src.core.errors import UploadSessionExpiredError
from src.core.logging import get_logger
from src.core.utils import utcnow
from src.db.models import UploadSession
from src.db.repositories.session_repo import UploadSessionRepository

logger = get_logger(__name__)


class SessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UploadSessionRepository(session)

    async def create_or_update_session(
        self,
        user_id: int,
        folder_id: int | None = None,
        state: str = UploadState.WAITING_FILE,
    ) -> UploadSession:
        settings = get_settings()
        expires_at = utcnow() + timedelta(seconds=settings.upload_session_timeout)
        upload_session = await self.repo.upsert_session(
            user_id=user_id,
            folder_id=folder_id,
            state=state,
            expires_at=expires_at,
        )
        logger.debug(
            "Upload session created/updated",
            user_id=user_id,
            folder_id=folder_id,
            state=state,
        )
        return upload_session

    async def get_active_session(self, user_id: int) -> UploadSession | None:
        session = await self.repo.get_active_session(user_id)
        if session is None:
            return None
        if session.expires_at.replace(tzinfo=None) < utcnow().replace(tzinfo=None):
            await self.repo.delete_session(user_id)
            logger.debug("Upload session expired and cleaned up", user_id=user_id)
            return None
        return session

    async def require_active_session(self, user_id: int) -> UploadSession:
        session = await self.get_active_session(user_id)
        if not session:
            raise UploadSessionExpiredError()
        return session

    async def clear_session(self, user_id: int) -> None:
        await self.repo.delete_session(user_id)

    async def cleanup_expired(self) -> int:
        count = await self.repo.delete_expired_sessions(utcnow())
        if count:
            logger.info("Cleaned up expired upload sessions", count=count)
        return count
