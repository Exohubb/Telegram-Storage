"""
Application entry point.
"""

import uvicorn

from src.api.app import create_app
from src.core.config.settings import get_settings
from src.core.logging import configure_logging

configure_logging()
app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.is_development,
        log_config=None,  # Use structlog instead
    )
