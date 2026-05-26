from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User, UserSettings
from src.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return await self._one_or_none(User.telegram_user_id == telegram_user_id)

    async def get_or_create(
        self,
        telegram_user_id: int,
        first_name: str,
        username: str | None = None,
        last_name: str | None = None,
        is_admin: bool = False,
    ) -> tuple[User, bool]:
        user = await self.get_by_telegram_id(telegram_user_id)
        if user:
            # Update mutable fields and sync admin status from settings
            user.first_name = first_name
            user.username = username
            user.last_name = last_name
            user.is_admin = is_admin
            await self.session.flush()
            return user, False

        user = User(
            telegram_user_id=telegram_user_id,
            first_name=first_name,
            username=username,
            last_name=last_name,
            is_admin=is_admin,
        )
        user = await self.save(user)
        return user, True

    async def set_state(self, user_id: int, state: str, state_data: str | None = None) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(state=state, state_data=state_data)
        )
        await self.session.flush()

    async def get_all_users(self, offset: int = 0, limit: int = 50) -> list[User]:
        stmt = select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_users(self) -> int:
        from sqlalchemy import func
        result = await self.session.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    async def ban_user(self, user_id: int, banned: bool = True) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(is_banned=banned)
        )
        await self.session.flush()


class UserSettingsRepository(BaseRepository[UserSettings]):
    model = UserSettings

    async def get_by_user_id(self, user_id: int) -> UserSettings | None:
        return await self._one_or_none(UserSettings.user_id == user_id)

    async def get_or_create(self, user_id: int) -> UserSettings:
        settings = await self.get_by_user_id(user_id)
        if not settings:
            settings = UserSettings(user_id=user_id)
            settings = await self.save(settings)
        return settings

    async def update_upload_behavior(self, user_id: int, behavior: str) -> None:
        await self.session.execute(
            update(UserSettings)
            .where(UserSettings.user_id == user_id)
            .values(upload_behavior=behavior)
        )
        await self.session.flush()

    async def mark_setup_completed(self, user_id: int, vault_channel_id: int) -> None:
        await self.session.execute(
            update(UserSettings)
            .where(UserSettings.user_id == user_id)
            .values(setup_completed=True, vault_channel_id=vault_channel_id)
        )
        await self.session.flush()
