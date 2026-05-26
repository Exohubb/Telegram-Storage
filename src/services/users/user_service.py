import json
import orjson

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config.settings import get_settings
from src.core.constants import DEFAULT_FOLDER_NAME, UserState
from src.core.errors import UserBannedError
from src.core.logging import get_logger
from src.core.utils import utcnow
from src.db.models import User
from src.db.repositories.folder_repo import FolderRepository
from src.db.repositories.user_repo import UserRepository, UserSettingsRepository
from src.services.audit.audit_service import AuditService

logger = get_logger(__name__)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.settings_repo = UserSettingsRepository(session)
        self.folder_repo = FolderRepository(session)
        self.audit = AuditService(session)

    async def get_or_create_user(
        self,
        telegram_user_id: int,
        first_name: str,
        username: str | None = None,
        last_name: str | None = None,
    ) -> tuple[User, bool]:
        settings = get_settings()
        is_admin = telegram_user_id in settings.admin_user_ids

        user, created = await self.user_repo.get_or_create(
            telegram_user_id=telegram_user_id,
            first_name=first_name,
            username=username,
            last_name=last_name,
            is_admin=is_admin,
        )

        if user.is_banned:
            raise UserBannedError()

        if created:
            await self._bootstrap_new_user(user)
            await self.audit.log(user.id, "user_created", "user", user.id)
            logger.info("New user registered", telegram_id=telegram_user_id, user_id=user.id)

        return user, created

    async def _bootstrap_new_user(self, user: User) -> None:
        """Create default folder and settings for a new user."""
        from src.db.models import Folder, UserSettings

        default_folder = Folder(
            user_id=user.id,
            name=DEFAULT_FOLDER_NAME,
            is_default=True,
        )
        self.session.add(default_folder)

        user_settings = UserSettings(user_id=user.id)
        self.session.add(user_settings)

        await self.session.flush()

    async def set_state(
        self, user_id: int, state: str, state_data: dict | None = None
    ) -> None:
        data_str = orjson.dumps(state_data).decode() if state_data else None
        await self.user_repo.set_state(user_id, state, data_str)

    async def get_state_data(self, user: User) -> dict:
        if not user.state_data:
            return {}
        try:
            return orjson.loads(user.state_data)
        except Exception:
            return {}

    async def clear_state(self, user_id: int) -> None:
        await self.user_repo.set_state(user_id, UserState.IDLE, None)

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return await self.user_repo.get_by_telegram_id(telegram_user_id)

    async def require_user(self, telegram_user_id: int) -> User:
        user = await self.user_repo.get_by_telegram_id(telegram_user_id)
        if not user:
            raise ValueError(f"User {telegram_user_id} not found — call get_or_create first")
        if user.is_banned:
            raise UserBannedError()
        return user

    async def is_admin(self, telegram_user_id: int) -> bool:
        settings = get_settings()
        return telegram_user_id in settings.admin_user_ids

    async def ban_user(self, admin_telegram_id: int, target_telegram_id: int) -> None:
        if not await self.is_admin(admin_telegram_id):
            from src.core.errors import ForbiddenError
            raise ForbiddenError("ban users")
        target = await self.user_repo.get_by_telegram_id(target_telegram_id)
        if not target:
            from src.core.errors import NotFoundError
            raise NotFoundError("User", target_telegram_id)
        await self.user_repo.ban_user(target.id, True)
        await self.audit.log(None, "user_banned", "user", target.id, {"by": admin_telegram_id})

    async def unban_user(self, admin_telegram_id: int, target_telegram_id: int) -> None:
        if not await self.is_admin(admin_telegram_id):
            from src.core.errors import ForbiddenError
            raise ForbiddenError("unban users")
        target = await self.user_repo.get_by_telegram_id(target_telegram_id)
        if not target:
            from src.core.errors import NotFoundError
            raise NotFoundError("User", target_telegram_id)
        await self.user_repo.ban_user(target.id, False)
        await self.audit.log(None, "user_unbanned", "user", target.id, {"by": admin_telegram_id})

    async def get_stats(self) -> dict:
        total_users = await self.user_repo.count_users()
        return {"total_users": total_users}
