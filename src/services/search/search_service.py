from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config.settings import get_settings
from src.core.errors import ValidationError
from src.core.utils import paginate, sanitize_tag
from src.db.models import File
from src.db.repositories.file_repo import FileRepository


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.file_repo = FileRepository(session)

    async def search(
        self,
        user_id: int,
        query: str | None = None,
        file_type: str | None = None,
        folder_id: int | None = None,
        tag: str | None = None,
        page: int = 1,
    ) -> tuple[list[File], dict]:
        settings = get_settings()

        if query:
            query = query.strip()
            if len(query) > settings.max_search_query_length:
                raise ValidationError(
                    f"Search query too long (max {settings.max_search_query_length} chars)."
                )
            if len(query) < 1:
                query = None

        if tag:
            tag = sanitize_tag(tag, settings.max_tag_length)
            if not tag:
                tag = None

        offset = (page - 1) * settings.page_size
        files = await self.file_repo.search(
            user_id=user_id,
            query=query,
            file_type=file_type,
            folder_id=folder_id,
            tag=tag,
            offset=offset,
            limit=settings.page_size,
        )
        total = await self.file_repo.count_search(
            user_id=user_id,
            query=query,
            file_type=file_type,
            folder_id=folder_id,
            tag=tag,
        )
        pagination = paginate(total, page, settings.page_size)
        return files, pagination
