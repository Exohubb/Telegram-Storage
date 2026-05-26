"""
Tests for webhook idempotency, session service, and search validation.
"""

import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from src.core.errors import UploadSessionExpiredError, ValidationError
from src.core.utils import utcnow
from src.services.sessions.session_service import SessionService
from src.services.search.search_service import SearchService


# ── Session service ───────────────────────────────────────────────────────────

@pytest.fixture
def session_service():
    svc = SessionService(AsyncMock())
    svc.repo = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_get_active_session_returns_valid(session_service):
    mock_session = MagicMock()
    mock_session.expires_at = utcnow() + timedelta(minutes=5)
    mock_session.expires_at = mock_session.expires_at.replace(tzinfo=None)
    session_service.repo.get_active_session = AsyncMock(return_value=mock_session)
    result = await session_service.get_active_session(user_id=1)
    assert result is not None


@pytest.mark.asyncio
async def test_get_active_session_expired_returns_none(session_service):
    mock_session = MagicMock()
    mock_session.expires_at = (utcnow() - timedelta(minutes=10)).replace(tzinfo=None)
    session_service.repo.get_active_session = AsyncMock(return_value=mock_session)
    session_service.repo.delete_session = AsyncMock()
    result = await session_service.get_active_session(user_id=1)
    assert result is None
    session_service.repo.delete_session.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_require_active_session_raises_when_none(session_service):
    session_service.repo.get_active_session = AsyncMock(return_value=None)
    with pytest.raises(UploadSessionExpiredError):
        await session_service.require_active_session(user_id=1)


@pytest.mark.asyncio
async def test_clear_session(session_service):
    session_service.repo.delete_session = AsyncMock()
    await session_service.clear_session(user_id=1)
    session_service.repo.delete_session.assert_called_once_with(1)


# ── Search service ────────────────────────────────────────────────────────────

@pytest.fixture
def search_service():
    svc = SearchService(AsyncMock())
    svc.file_repo = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_search_query_too_long_raises(search_service):
    with pytest.raises(ValidationError):
        await search_service.search(user_id=1, query="x" * 200)


@pytest.mark.asyncio
async def test_search_returns_results(search_service):
    files = [MagicMock(), MagicMock()]
    search_service.file_repo.search = AsyncMock(return_value=files)
    search_service.file_repo.count_search = AsyncMock(return_value=2)
    result_files, pagination = await search_service.search(user_id=1, query="report")
    assert len(result_files) == 2
    assert pagination["total"] == 2


@pytest.mark.asyncio
async def test_search_empty_query_treated_as_none(search_service):
    search_service.file_repo.search = AsyncMock(return_value=[])
    search_service.file_repo.count_search = AsyncMock(return_value=0)
    result_files, pagination = await search_service.search(user_id=1, query="   ")
    # Empty query should not raise, just return empty
    assert result_files == []


# ── Webhook idempotency ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_processed_update_idempotency():
    from src.db.repositories.session_repo import ProcessedUpdateRepository
    mock_session = AsyncMock()
    repo = ProcessedUpdateRepository(mock_session)

    # First call: not processed
    mock_session.get = AsyncMock(return_value=None)
    assert await repo.is_processed(12345) is False

    # Second call: already processed
    mock_session.get = AsyncMock(return_value=MagicMock())
    assert await repo.is_processed(12345) is True


# ── Callback data parsing ─────────────────────────────────────────────────────

def test_parse_callback_data():
    from src.core.utils import parse_callback_data, build_callback_data
    data = build_callback_data("xo", 42)
    parts = parse_callback_data(data)
    assert parts[0] == "xo"
    assert parts[1] == "42"


def test_build_callback_data_length():
    from src.core.utils import build_callback_data
    data = build_callback_data("fl", 1, 2)
    assert len(data) <= 64


# ── Utility functions ─────────────────────────────────────────────────────────

def test_format_file_size():
    from src.core.utils import format_file_size
    assert format_file_size(500) == "500 B"
    assert format_file_size(1536) == "1.5 KB"
    assert format_file_size(1_572_864) == "1.5 MB"
    assert format_file_size(None) == "Unknown size"


def test_sanitize_name():
    from src.core.utils import sanitize_name
    assert sanitize_name("  hello  ") == "hello"
    assert sanitize_name("a\x00b") == "ab"
    assert sanitize_name("x" * 100, max_length=10) == "x" * 10


def test_sanitize_tag():
    from src.core.utils import sanitize_tag
    assert sanitize_tag("  Work  ") == "work"
    assert sanitize_tag("hello world") == "helloworld"
    assert sanitize_tag("my-tag") == "my-tag"


def test_detect_file_type():
    from src.core.utils import detect_file_type
    from src.core.constants import FileType
    assert detect_file_type(telegram_type="photo") == FileType.IMAGE
    assert detect_file_type(telegram_type="video") == FileType.VIDEO
    assert detect_file_type(mime_type="image/png") == FileType.IMAGE
    assert detect_file_type(mime_type="audio/mpeg") == FileType.AUDIO
    assert detect_file_type() == FileType.OTHER
