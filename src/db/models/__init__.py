"""
Database models using SQLAlchemy 2.0 async ORM.
All tables use integer primary keys for simplicity and join performance.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class FileTypeEnum(str, enum.Enum):
    document = "document"
    image = "image"
    video = "video"
    audio = "audio"
    voice = "voice"
    video_note = "video_note"
    sticker = "sticker"
    animation = "animation"
    other = "other"


class UserStateEnum(str, enum.Enum):
    idle = "idle"
    uploading = "uploading"
    renaming_file = "renaming_file"
    renaming_folder = "renaming_folder"
    creating_folder = "creating_folder"
    adding_tags = "adding_tags"
    searching = "searching"
    moving_file = "moving_file"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    state: Mapped[str] = mapped_column(
        String(32),
        default="idle",
        nullable=False,
    )
    state_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON blob for state context
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    folders: Mapped[list["Folder"]] = relationship("Folder", back_populates="user", lazy="noload")
    files: Mapped[list["File"]] = relationship("File", back_populates="user", lazy="noload")
    upload_sessions: Mapped[list["UploadSession"]] = relationship(
        "UploadSession", back_populates="user", lazy="noload"
    )


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="folders", lazy="noload")
    files: Mapped[list["File"]] = relationship("File", back_populates="folder", lazy="noload")
    children: Mapped[list["Folder"]] = relationship("Folder", lazy="noload")

    __table_args__ = (
        UniqueConstraint("user_id", "name", "parent_id", name="uq_folder_name_per_parent"),
        Index("ix_folders_user_id", "user_id"),
        Index("ix_folders_parent_id", "parent_id"),
    )


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    folder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True
    )

    # User-visible label (can be renamed without touching vault)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    extension: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_type: Mapped[str] = mapped_column(
        String(32), default="other", nullable=False
    )
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Telegram source references
    source_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    telegram_file_unique_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # Vault references — primary retrieval mechanism
    vault_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    vault_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Flags
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="files", lazy="noload")
    folder: Mapped["Folder | None"] = relationship("Folder", back_populates="files", lazy="noload")
    tags: Mapped[list["FileTag"]] = relationship(
        "FileTag", back_populates="file", lazy="noload", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_files_user_id", "user_id"),
        Index("ix_files_folder_id", "folder_id"),
        Index("ix_files_user_deleted", "user_id", "is_deleted"),
        Index("ix_files_user_favorite", "user_id", "is_favorite"),
        Index("ix_files_created_at", "created_at"),
    )


class FileTag(Base):
    __tablename__ = "file_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    tag: Mapped[str] = mapped_column(String(32), nullable=False)

    file: Mapped["File"] = relationship("File", back_populates="tags", lazy="noload")

    __table_args__ = (
        UniqueConstraint("file_id", "tag", name="uq_file_tag"),
        Index("ix_file_tags_file_id", "file_id"),
        Index("ix_file_tags_tag", "tag"),
    )


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    folder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="waiting_file")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="upload_sessions", lazy="noload")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_upload_session_per_user"),
        Index("ix_upload_sessions_user_id", "user_id"),
        Index("ix_upload_sessions_expires_at", "expires_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
    )


class OperationFailure(Base):
    __tablename__ = "operation_failures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_op_failures_user_id", "user_id"),
        Index("ix_op_failures_operation", "operation"),
        Index("ix_op_failures_resolved", "resolved"),
        Index("ix_op_failures_created_at", "created_at"),
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    upload_behavior: Mapped[str] = mapped_column(String(16), default="ask", nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    setup_completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    vault_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_user_settings_user_id", "user_id"),)


class ProcessedUpdate(Base):
    """Idempotency table to prevent duplicate webhook processing."""

    __tablename__ = "processed_updates"

    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_processed_updates_processed_at", "processed_at"),)
