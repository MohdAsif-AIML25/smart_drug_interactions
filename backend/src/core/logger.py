"""
Structured Logging with Loguru
Supports JSON logging for production and readable logs for development.
"""

import sys
import json
from loguru import logger

from src.core.config import settings


# Remove default Loguru handler
logger.remove()


# ─────────────────────────────────────────────
# JSON Logging (Production)
# ─────────────────────────────────────────────

if settings.JSON_LOGS:

    def json_sink(message):
        """
        Custom JSON log sink for structured logging.
        """
        record = message.record

        log_data = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["module"],
            "function": record["function"],
            "line": record["line"],
        }

        # Include extra metadata if present
        if record["extra"]:
            log_data["extra"] = record["extra"]

        # Include exception traceback if present
        if record["exception"]:
            log_data["exception"] = str(record["exception"])

        print(json.dumps(log_data), file=sys.stdout)

    logger.add(
        json_sink,
        level=settings.LOG_LEVEL,
        colorize=False,
        backtrace=True,
        diagnose=True,
    )

# ─────────────────────────────────────────────
# Human Readable Logging (Development)
# ─────────────────────────────────────────────

else:

    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )