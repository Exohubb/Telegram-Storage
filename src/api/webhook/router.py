"""
FastAPI webhook endpoint.
Receives Telegram updates, validates the secret token,
checks idempotency, and dispatches to the PTB Application.
"""

import orjson
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from telegram import Update

from src.core.config.settings import get_settings
from src.core.logging import get_logger
from src.db.engine import get_session_factory
from src.db.repositories.session_repo import ProcessedUpdateRepository

logger = get_logger(__name__)

router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    settings = get_settings()

    # Validate webhook secret
    if x_telegram_bot_api_secret_token != settings.bot_webhook_secret:
        logger.warning("Invalid webhook secret token received")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # Parse body
    try:
        body = await request.body()
        data = orjson.loads(body)
    except Exception as e:
        logger.warning("Invalid webhook payload", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    update_id = data.get("update_id")
    if not update_id:
        logger.warning("Webhook payload missing update_id")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing update_id")

    # Idempotency check
    factory = get_session_factory()
    async with factory() as session:
        processed_repo = ProcessedUpdateRepository(session)
        if await processed_repo.is_processed(update_id):
            logger.debug("Duplicate webhook update ignored", update_id=update_id)
            return Response(status_code=status.HTTP_200_OK)
        await processed_repo.mark_processed(update_id)
        await session.commit()

    # Dispatch to PTB
    bot_app = request.app.state.bot_app
    try:
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
    except Exception as e:
        logger.error("Error processing Telegram update", update_id=update_id, error=str(e))
        # Always return 200 to Telegram to prevent retries for permanent errors
        return Response(status_code=status.HTTP_200_OK)

    return Response(status_code=status.HTTP_200_OK)
