import json
import orjson

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.db.models import AuditLog
from src.db.repositories.session_repo import OperationFailureRepository

logger = get_logger(__name__)


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.failure_repo = OperationFailureRepository(session)

    async def log(
        self,
        user_id: int | None,
        action: str,
        resource_type: str | None = None,
        resource_id: int | None = None,
        details: dict | None = None,
    ) -> None:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=orjson.dumps(details).decode() if details else None,
        )
        self.session.add(entry)
        try:
            await self.session.flush()
        except Exception as e:
            logger.warning("Failed to write audit log", action=action, error=str(e))

    async def log_failure(
        self,
        operation: str,
        error_message: str,
        user_id: int | None = None,
        error_code: str | None = None,
        context: dict | None = None,
    ) -> None:
        ctx_str = orjson.dumps(context).decode() if context else None
        try:
            await self.failure_repo.log_failure(
                operation=operation,
                error_message=error_message,
                user_id=user_id,
                error_code=error_code,
                context=ctx_str,
            )
        except Exception as e:
            logger.error("Failed to log operation failure", operation=operation, error=str(e))
