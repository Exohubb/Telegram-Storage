"""
StorageService: handles forwarding/copying files to the vault channel
and retrieving them back. This is the core of the zero-server-storage architecture.

Files are NEVER downloaded to the server. We use Telegram's copyMessage API
to move files between chats, storing only the resulting message reference.
"""

from telegram import Bot, Message
from telegram.error import BadRequest, Forbidden, TelegramError

from src.core.config.settings import get_settings
from src.core.errors import (
    StaleReferenceError,
    TelegramAPIError,
    VaultAccessError,
)
from src.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    def __init__(self, bot: Bot, vault_channel_id: int | None = None) -> None:
        self.bot = bot
        self._settings = get_settings()
        self._vault_channel_id = vault_channel_id

    @property
    def vault_channel_id(self) -> int:
        if self._vault_channel_id is not None:
            return self._vault_channel_id
        if self._settings.vault_channel_id is None:
            raise VaultAccessError()
        return self._settings.vault_channel_id

    async def copy_to_vault(
        self,
        from_chat_id: int,
        message_id: int,
        caption: str | None = None,
    ) -> Message:
        """
        Copy a user's file message to the private vault channel.
        Returns the vault Message object containing the new message_id.
        Uses copyMessage so the vault message has no "forwarded from" header.
        """
        try:
            vault_message = await self.bot.copy_message(
                chat_id=self.vault_channel_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
                caption=caption,
            )
            logger.info(
                "File copied to vault",
                from_chat_id=from_chat_id,
                source_message_id=message_id,
                vault_message_id=vault_message.message_id,
            )
            return vault_message
        except Forbidden as e:
            logger.error("Bot lacks access to vault channel", error=str(e))
            raise VaultAccessError() from e
        except BadRequest as e:
            logger.error(
                "Bad request copying to vault",
                from_chat_id=from_chat_id,
                message_id=message_id,
                error=str(e),
            )
            raise TelegramAPIError(f"Failed to copy file to vault: {e}", str(e)) from e
        except TelegramError as e:
            logger.error("Telegram error copying to vault", error=str(e))
            raise TelegramAPIError(f"Telegram error: {e}", str(e)) from e

    async def send_file_to_user(
        self,
        user_chat_id: int,
        vault_message_id: int,
        caption: str | None = None,
    ) -> Message:
        """
        Resend a file from the vault channel to the requesting user.
        Uses copyMessage so the user sees a clean file without vault metadata.
        """
        try:
            sent = await self.bot.copy_message(
                chat_id=user_chat_id,
                from_chat_id=self.vault_channel_id,
                message_id=vault_message_id,
                caption=caption,
            )
            logger.info(
                "File sent to user from vault",
                user_chat_id=user_chat_id,
                vault_message_id=vault_message_id,
            )
            return sent
        except BadRequest as e:
            error_str = str(e).lower()
            if "message to copy not found" in error_str or "message_id_invalid" in error_str:
                raise StaleReferenceError(vault_message_id) from e
            raise TelegramAPIError(f"Failed to retrieve file: {e}", str(e)) from e
        except Forbidden as e:
            raise VaultAccessError() from e
        except TelegramError as e:
            raise TelegramAPIError(f"Telegram error retrieving file: {e}", str(e)) from e

    async def delete_from_vault(self, vault_message_id: int) -> bool:
        """
        Permanently delete a message from the vault channel.
        Returns True if deleted, False if already gone (idempotent).
        """
        try:
            await self.bot.delete_message(
                chat_id=self.vault_channel_id,
                message_id=vault_message_id,
            )
            logger.info("Vault message deleted", vault_message_id=vault_message_id)
            return True
        except BadRequest as e:
            if "message to delete not found" in str(e).lower():
                logger.warning("Vault message already gone", vault_message_id=vault_message_id)
                return False
            raise TelegramAPIError(f"Failed to delete vault message: {e}", str(e)) from e
        except Forbidden as e:
            raise VaultAccessError() from e
        except TelegramError as e:
            raise TelegramAPIError(f"Telegram error deleting vault message: {e}", str(e)) from e

    async def verify_vault_access(self) -> bool:
        """Startup check: verify bot can access the vault channel."""
        try:
            chat = await self.bot.get_chat(self.vault_channel_id)
            logger.info("Vault channel verified", chat_id=self.vault_channel_id, title=chat.title)
            return True
        except (Forbidden, BadRequest) as e:
            logger.error(
                "Cannot access vault channel — bot must be admin",
                vault_channel_id=self.vault_channel_id,
                error=str(e),
            )
            return False
        except TelegramError as e:
            logger.error("Telegram error verifying vault", error=str(e))
            return False
