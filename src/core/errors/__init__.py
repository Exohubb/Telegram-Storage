from enum import IntEnum


class ErrorCode(IntEnum):
    # Generic
    UNKNOWN = 1000
    VALIDATION_ERROR = 1001
    NOT_FOUND = 1002
    ALREADY_EXISTS = 1003
    UNAUTHORIZED = 1004
    FORBIDDEN = 1005
    RATE_LIMITED = 1006

    # User
    USER_NOT_FOUND = 2001
    USER_BANNED = 2002

    # Folder
    FOLDER_NOT_FOUND = 3001
    FOLDER_ALREADY_EXISTS = 3002
    FOLDER_NOT_EMPTY = 3003
    FOLDER_ACCESS_DENIED = 3004
    FOLDER_NAME_INVALID = 3005

    # File
    FILE_NOT_FOUND = 4001
    FILE_ACCESS_DENIED = 4002
    FILE_ALREADY_IN_TRASH = 4003
    FILE_NOT_IN_TRASH = 4004
    FILE_MOVE_INVALID_TARGET = 4005
    FILE_RENAME_INVALID = 4006

    # Tags
    TAG_DUPLICATE = 5001
    TAG_LIMIT_EXCEEDED = 5002
    TAG_INVALID = 5003

    # Upload session
    UPLOAD_SESSION_NOT_FOUND = 6001
    UPLOAD_SESSION_EXPIRED = 6002
    UPLOAD_SESSION_CONFLICT = 6003

    # Telegram API
    TELEGRAM_API_ERROR = 7001
    TELEGRAM_VAULT_ACCESS_DENIED = 7002
    TELEGRAM_FORWARD_FAILED = 7003
    TELEGRAM_RETRIEVAL_FAILED = 7004
    TELEGRAM_STALE_REFERENCE = 7005
    TELEGRAM_BOT_NOT_ADMIN = 7006

    # Database
    DB_CONNECTION_ERROR = 8001
    DB_CONSTRAINT_VIOLATION = 8002
    DB_QUERY_ERROR = 8003

    # Webhook
    WEBHOOK_INVALID_PAYLOAD = 9001
    WEBHOOK_DUPLICATE_UPDATE = 9002
    WEBHOOK_SIGNATURE_INVALID = 9003


class AppError(Exception):
    """Base application error with structured metadata."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.UNKNOWN,
        user_message: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.user_message = user_message or "Something went wrong. Please try again."
        self.details = details or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code}, message={str(self)})"


class ValidationError(AppError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(
            message,
            code=ErrorCode.VALIDATION_ERROR,
            user_message=message,
            details={"field": field} if field else {},
        )


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str | int | None = None) -> None:
        msg = f"{resource} not found"
        if resource_id:
            msg = f"{resource} '{resource_id}' not found"
        super().__init__(msg, code=ErrorCode.NOT_FOUND, user_message=f"{resource} not found.")


class AlreadyExistsError(AppError):
    def __init__(self, resource: str, identifier: str | None = None) -> None:
        msg = f"{resource} already exists"
        if identifier:
            msg = f"{resource} '{identifier}' already exists"
        super().__init__(msg, code=ErrorCode.ALREADY_EXISTS, user_message=f"{resource} already exists.")


class ForbiddenError(AppError):
    def __init__(self, action: str = "perform this action") -> None:
        super().__init__(
            f"Forbidden: {action}",
            code=ErrorCode.FORBIDDEN,
            user_message="You don't have permission to do that.",
        )


class UserBannedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "User is banned",
            code=ErrorCode.USER_BANNED,
            user_message="Your account has been restricted. Contact support.",
        )


class FolderNotFoundError(NotFoundError):
    def __init__(self, folder_id: int | None = None) -> None:
        super().__init__("Folder", folder_id)
        self.code = ErrorCode.FOLDER_NOT_FOUND


class FolderAlreadyExistsError(AlreadyExistsError):
    def __init__(self, name: str) -> None:
        super().__init__("Folder", name)
        self.code = ErrorCode.FOLDER_ALREADY_EXISTS
        self.user_message = f"A folder named \"{name}\" already exists."


class FolderNotEmptyError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "Folder is not empty",
            code=ErrorCode.FOLDER_NOT_EMPTY,
            user_message="This folder still has files. Move or delete them first.",
        )


class FileNotFoundError(NotFoundError):
    def __init__(self, file_id: int | None = None) -> None:
        super().__init__("File", file_id)
        self.code = ErrorCode.FILE_NOT_FOUND


class FileAccessDeniedError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__("access this file")
        self.code = ErrorCode.FILE_ACCESS_DENIED


class TagDuplicateError(AppError):
    def __init__(self, tag: str) -> None:
        super().__init__(
            f"Tag '{tag}' already exists on this file",
            code=ErrorCode.TAG_DUPLICATE,
            user_message=f"Tag \"{tag}\" is already added.",
        )


class TagLimitExceededError(AppError):
    def __init__(self, limit: int) -> None:
        super().__init__(
            f"Tag limit of {limit} exceeded",
            code=ErrorCode.TAG_LIMIT_EXCEEDED,
            user_message=f"Maximum {limit} tags per file.",
        )


class UploadSessionExpiredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "Upload session expired",
            code=ErrorCode.UPLOAD_SESSION_EXPIRED,
            user_message="Upload session expired. Please start again.",
        )


class TelegramAPIError(AppError):
    def __init__(self, message: str, telegram_error: str | None = None) -> None:
        super().__init__(
            message,
            code=ErrorCode.TELEGRAM_API_ERROR,
            user_message="Telegram API error. Please try again.",
            details={"telegram_error": telegram_error} if telegram_error else {},
        )


class VaultAccessError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "Bot cannot access vault channel",
            code=ErrorCode.TELEGRAM_VAULT_ACCESS_DENIED,
            user_message="Storage vault is temporarily unavailable. Contact admin.",
        )


class StaleReferenceError(AppError):
    def __init__(self, file_id: int) -> None:
        super().__init__(
            f"Vault message reference for file {file_id} is stale or deleted",
            code=ErrorCode.TELEGRAM_STALE_REFERENCE,
            user_message="This file's vault reference is no longer valid. It may have been deleted from the vault.",
        )


class DuplicateWebhookUpdateError(AppError):
    def __init__(self, update_id: int) -> None:
        super().__init__(
            f"Duplicate webhook update: {update_id}",
            code=ErrorCode.WEBHOOK_DUPLICATE_UPDATE,
        )
