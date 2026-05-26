"""
FastAPI application factory and lifespan manager.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.health.router import router as health_router
from src.api.webhook.router import router as webhook_router
from src.bot.app import create_bot_app, setup_webhook
from src.core.config.settings import get_settings
from src.core.logging import configure_logging, get_logger
from src.db.engine import close_engine
from src.services.storage.storage_service import StorageService

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    logger.info("Starting up", env=settings.app_env)

    # Build and initialize PTB bot application
    bot_app = create_bot_app()
    await bot_app.initialize()

    # Verify vault channel access
    storage = StorageService(bot_app.bot)
    vault_ok = await storage.verify_vault_access()
    if not vault_ok:
        logger.error(
            "VAULT CHANNEL NOT ACCESSIBLE — bot must be admin in the vault channel. "
            "File uploads will fail until this is resolved."
        )

    # Register webhook with Telegram
    await setup_webhook(bot_app)

    app.state.bot_app = bot_app
    logger.info("Bot application ready")

    yield

    # Shutdown
    logger.info("Shutting down")
    await bot_app.shutdown()
    await close_engine()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Telegram Cloud Storage Bot",
        version="1.0.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(webhook_router)

    return app
