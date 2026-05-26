"""
Tests for file service: upload metadata, rename, move, delete/restore, tags.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.errors import (
    FileNotFoundError,
    TagDuplicateError,
    TagLimitExceededError,
    ValidationError,
)
from src.services.files.file_service import FileService, _extract_file_info


def _make_file(id=1, label="test.pdf", user_id=1, folder_id=1, is_deleted=False, is_favorite=False, vault_message_id=100):
    f = MagicMock()
    f.id = id
    f.label = label
    f.user_id = user_id
    f.folder_id = folder_id
    f.is_deleted = is_deleted
    f.is_favorite = is_favorite
    f.vault_message_id = vault_message_id
    f.tags = []
    f.file_type = "document"
    f.file_size = 1024
    return f


def _make_tg_message(has_document=True):
    msg = MagicMock()
    msg.chat_id = 123
    msg.message_id = 456
    msg.caption = None
    if has_document:
        doc = MagicMock()
        doc.file_id = "file_id_abc"
        doc.file_unique_id = "unique_abc"
        doc.file_name = "report.pdf"
        doc.mime_type = "application/pdf"
        doc.file_size = 2048
        msg.document = doc
        msg.photo = None
        msg.video = None
        msg.audio = None
        msg.voice = None
        msg.video_note = None
        msg.animation = None
        msg.sticker = None
    else:
        msg.document = None
        msg.photo = None
        msg.video = None
        msg.audio = None
        msg.voice = None
        msg.video_note = None
        msg.animation = None
        msg.sticker = None
    return msg


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_storage():
    s = AsyncMock()
    s.vault_channel_id = -1001234567890
    vault_msg = MagicMock()
    vault_msg.message_id = 999
    s.copy_to_vault = AsyncMock(return_value=vault_msg)
    s.send_file_to_user = AsyncMock()
    s.delete_from_vault = AsyncMock(return_value=True)
    return s


@pytest.fixture
def file_service(mock_session, mock_storage):
    svc = FileService(mock_session, mock_storage)
    svc.file_repo = AsyncMock()
    svc.tag_repo = AsyncMock()
    svc.folder_repo = AsyncMock()
    svc.audit = AsyncMock()
    return svc


def test_extract_file_info_document():
    msg = _make_tg_message(has_document=True)
    info = _extract_file_info(msg)
    assert info["telegram_type"] == "document"
    assert info["telegram_file_id"] == "file_id_abc"
    assert info["original_filename"] == "report.pdf"
    assert info["mime_type"] == "application/pdf"


def test_extract_file_info_no_file():
    msg = _make_tg_message(has_document=False)
    info = _extract_file_info(msg)
    assert info == {}


@pytest.mark.asyncio
async def test_upload_file_success(file_service, mock_storage):
    msg = _make_tg_message()
    file_service.folder_repo.get_by_id_and_user = AsyncMock(return_value=MagicMock())
    saved_file = _make_file()
    file_service.file_repo.save = AsyncMock(return_value=saved_file)
    result = await file_service.upload_file(user_id=1, tg_message=msg, folder_id=1)
    mock_storage.copy_to_vault.assert_called_once()
    file_service.file_repo.save.assert_called_once()
    assert result.id == 1


@pytest.mark.asyncio
async def test_upload_file_no_file_raises(file_service):
    msg = _make_tg_message(has_document=False)
    with pytest.raises(ValidationError):
        await file_service.upload_file(user_id=1, tg_message=msg)


@pytest.mark.asyncio
async def test_get_file_not_found_raises(file_service):
    file_service.file_repo.get_by_id_and_user = AsyncMock(return_value=None)
    with pytest.raises(FileNotFoundError):
        await file_service.get_file(99, user_id=1)


@pytest.mark.asyncio
async def test_rename_file_success(file_service):
    f = _make_file()
    file_service.file_repo.get_by_id_and_user = AsyncMock(return_value=f)
    file_service.file_repo.rename = AsyncMock()
    result = await file_service.rename_file(1, user_id=1, new_label="new_name.pdf")
    file_service.file_repo.rename.assert_called_once_with(1, "new_name.pdf")


@pytest.mark.asyncio
async def test_rename_file_empty_raises(file_service):
    f = _make_file()
    file_service.file_repo.get_by_id_and_user = AsyncMock(return_value=f)
    with pytest.raises(ValidationError):
        await file_service.rename_file(1, user_id=1, new_label="   ")


@pytest.mark.asyncio
async def test_soft_delete_success(file_service):
    f = _make_file(is_deleted=False)
    file_service.file_repo.get_by_id_and_user = AsyncMock(return_value=f)
    file_service.file_repo.soft_delete = AsyncMock()
    await file_service.soft_delete(1, user_id=1)
    file_service.file_repo.soft_delete.assert_called_once()


@pytest.mark.asyncio
async def test_soft_delete_already_deleted_raises(file_service):
    f = _make_file(is_deleted=True)
    file_service.file_repo.get_by_id_and_user = AsyncMock(return_value=f)
    with pytest.raises(ValidationError):
        await file_service.soft_delete(1, user_id=1)


@pytest.mark.asyncio
async def test_restore_file_success(file_service):
    f = _make_file(is_deleted=True)
    file_service.file_repo.get_by_id_and_user = AsyncMock(return_value=f)
    file_service.file_repo.restore = AsyncMock()
    result = await file_service.restore_file(1, user_id=1)
    file_service.file_repo.restore.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_restore_file_not_in_trash_raises(file_service):
    f = _make_file(is_deleted=False)
    file_service.file_repo.get_by_id_and_user = AsyncMock(return_value=f)
    with pytest.raises(ValidationError):
        await file_service.restore_file(1, user_id=1)


@pytest.mark.asyncio
async def test_add_tag_success(file_service):
    f = _make_file()
    file_service.file_repo.get_by_id_and_user = AsyncMock(return_value=f)
    file_service.tag_repo.get_tag = AsyncMock(return_value=None)
    file_service.tag_repo.count_tags_for_file = AsyncMock(return_value=0)
    tag_obj = MagicMock()
    tag_obj.tag = "work"
    file_service.tag_repo.save = AsyncMock(return_value=tag_obj)
    result = await file_service.add_tag(1, user_id=1, tag="work")
    assert result.tag == "work"


@pytest.mark.asyncio
async def test_add_tag_duplicate_raises(file_service):
    f = _make_file()
    file_service.file_repo.get_by_id_and_user = AsyncMock(return_value=f)
    file_service.tag_repo.get_tag = AsyncMock(return_value=MagicMock())
    with pytest.raises(TagDuplicateError):
        await file_service.add_tag(1, user_id=1, tag="work")


@pytest.mark.asyncio
async def test_add_tag_limit_exceeded_raises(file_service):
    f = _make_file()
    file_service.file_repo.get_by_id_and_user = AsyncMock(return_value=f)
    file_service.tag_repo.get_tag = AsyncMock(return_value=None)
    file_service.tag_repo.count_tags_for_file = AsyncMock(return_value=10)
    with pytest.raises(TagLimitExceededError):
        await file_service.add_tag(1, user_id=1, tag="newtag")
