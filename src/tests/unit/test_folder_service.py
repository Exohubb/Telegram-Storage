"""
Tests for folder service: creation, rename, delete, duplicate detection.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.errors import (
    FolderAlreadyExistsError,
    FolderNotEmptyError,
    FolderNotFoundError,
    ValidationError,
)
from src.services.folders.folder_service import FolderService


def _make_folder(id=1, name="Test", user_id=1, is_default=False, parent_id=None):
    f = MagicMock()
    f.id = id
    f.name = name
    f.user_id = user_id
    f.is_default = is_default
    f.parent_id = parent_id
    return f


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def folder_service(mock_session):
    svc = FolderService(mock_session)
    svc.repo = AsyncMock()
    svc.audit = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_create_folder_success(folder_service):
    folder_service.repo.get_by_name_and_parent = AsyncMock(return_value=None)
    folder_service.repo.save = AsyncMock(return_value=_make_folder(name="Work"))
    result = await folder_service.create_folder(user_id=1, name="Work")
    assert result.name == "Work"
    folder_service.repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_create_folder_duplicate_raises(folder_service):
    folder_service.repo.get_by_name_and_parent = AsyncMock(return_value=_make_folder(name="Work"))
    with pytest.raises(FolderAlreadyExistsError):
        await folder_service.create_folder(user_id=1, name="Work")


@pytest.mark.asyncio
async def test_create_folder_empty_name_raises(folder_service):
    with pytest.raises(ValidationError):
        await folder_service.create_folder(user_id=1, name="   ")


@pytest.mark.asyncio
async def test_create_folder_name_too_long_raises(folder_service):
    with pytest.raises(ValidationError):
        await folder_service.create_folder(user_id=1, name="x" * 200)


@pytest.mark.asyncio
async def test_rename_folder_success(folder_service):
    folder = _make_folder(id=1, name="Old")
    folder_service.repo.get_by_id_and_user = AsyncMock(return_value=folder)
    folder_service.repo.get_by_name_and_parent = AsyncMock(return_value=None)
    folder_service.repo.rename = AsyncMock()
    result = await folder_service.rename_folder(1, user_id=1, new_name="New")
    folder_service.repo.rename.assert_called_once_with(1, "New")


@pytest.mark.asyncio
async def test_rename_folder_not_found_raises(folder_service):
    folder_service.repo.get_by_id_and_user = AsyncMock(return_value=None)
    with pytest.raises(FolderNotFoundError):
        await folder_service.rename_folder(99, user_id=1, new_name="New")


@pytest.mark.asyncio
async def test_delete_folder_not_empty_raises(folder_service):
    folder = _make_folder(id=1, is_default=False)
    folder_service.repo.get_by_id_and_user = AsyncMock(return_value=folder)
    folder_service.repo.count_files_in_folder = AsyncMock(return_value=3)
    with pytest.raises(FolderNotEmptyError):
        await folder_service.delete_folder(1, user_id=1, force=False)


@pytest.mark.asyncio
async def test_delete_folder_force_succeeds(folder_service):
    folder = _make_folder(id=1, is_default=False)
    folder_service.repo.get_by_id_and_user = AsyncMock(return_value=folder)
    folder_service.repo.count_files_in_folder = AsyncMock(return_value=3)
    folder_service.repo.delete = AsyncMock()
    await folder_service.delete_folder(1, user_id=1, force=True)
    folder_service.repo.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_default_folder_raises(folder_service):
    folder = _make_folder(id=1, is_default=True)
    folder_service.repo.get_by_id_and_user = AsyncMock(return_value=folder)
    from src.core.errors import ForbiddenError
    with pytest.raises(ForbiddenError):
        await folder_service.delete_folder(1, user_id=1)
