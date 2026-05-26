from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.core.config.settings import get_settings
from src.db.engine import get_engine

router = APIRouter()


@router.get("/health")
async def health_check() -> JSONResponse:
    settings = get_settings()
    db_ok = False
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    status = "ok" if db_ok else "degraded"
    return JSONResponse(
        content={
            "status": status,
            "env": settings.app_env,
            "db": "ok" if db_ok else "error",
        },
        status_code=200 if db_ok else 503,
    )


@router.get("/")
async def root() -> JSONResponse:
    return JSONResponse({"status": "running"})
