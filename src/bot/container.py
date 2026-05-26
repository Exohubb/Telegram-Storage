"""
Dependency injection container for services.
Provides a clean way to instantiate services with a shared DB session.
"""

from telegram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.audit.audit_service import AuditService
from src.services.files.file_service import FileService
from src.services.folders.folder_service import FolderService
from src.services.search.search_service import SearchService
from src.services.sessions.session_service import SessionService
from src.services.storage.storage_service import StorageService
from src.services.users.user_service import UserService


class Container:
    """Lightweight service container scoped to a single request/update."""

    def __init__(self, session: AsyncSession, bot: Bot, vault_channel_id: int | None = None) -> None:
        self.session = session
        self.bot = bot
        self._vault_channel_id = vault_channel_id
        self._storage: StorageService | None = None
        self._users: UserService | None = None
        self._folders: FolderService | None = None
        self._files: FileService | None = None
        self._sessions: SessionService | None = None
        self._search: SearchService | None = None
        self._audit: AuditService | None = None

    @property
    def storage(self) -> StorageService:
        if not self._storage:
            self._storage = StorageService(self.bot, vault_channel_id=self._vault_channel_id)
        return self._storage

    @property
    def users(self) -> UserService:
        if not self._users:
            self._users = UserService(self.session)
        return self._users

    @property
    def folders(self) -> FolderService:
        if not self._folders:
            self._folders = FolderService(self.session)
        return self._folders

    @property
    def files(self) -> FileService:
        if not self._files:
            self._files = FileService(self.session, self.storage)
        return self._files

    @property
    def sessions(self) -> SessionService:
        if not self._sessions:
            self._sessions = SessionService(self.session)
        return self._sessions

    @property
    def search(self) -> SearchService:
        if not self._search:
            self._search = SearchService(self.session)
        return self._search

    @property
    def audit(self) -> AuditService:
        if not self._audit:
            self._audit = AuditService(self.session)
        return self._audit
