from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram
    bot_token: str
    bot_webhook_secret: str
    vault_channel_id: int | None = None

    # Database
    database_url: str

    # Application
    app_env: Literal["development", "production", "test"] = "production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    webhook_base_url: str

    # Admin
    admin_user_ids: list[int] = []

    # Bot behavior
    default_upload_behavior: Literal["ask", "default"] = "ask"
    upload_session_timeout: int = 300
    max_folder_name_length: int = 64
    max_tag_length: int = 32
    max_tags_per_file: int = 10
    max_search_query_length: int = 128
    page_size: int = 8

    # Logging
    log_level: str = "INFO"

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: str | list) -> list[int]:
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, str) and v.strip():
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return []

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a valid PostgreSQL connection string")
        return v

    @field_validator("bot_token", mode="before")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        if not v or ":" not in v:
            raise ValueError("BOT_TOKEN must be a valid Telegram bot token")
        return v

    @field_validator("vault_channel_id", mode="before")
    @classmethod
    def validate_vault_channel_id(cls, v: str | int | None) -> int | None:
        if v is None or v == "":
            return None
        channel_id = int(v)
        if channel_id >= 0:
            raise ValueError("VAULT_CHANNEL_ID must be a negative integer (Telegram channel ID)")
        return channel_id

    @model_validator(mode="after")
    def validate_webhook_url(self) -> "Settings":
        if self.webhook_base_url.endswith("/"):
            self.webhook_base_url = self.webhook_base_url.rstrip("/")
        return self

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_base_url}/webhook"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
