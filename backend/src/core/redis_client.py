"""
Redis Async Client
Used for caching drug interaction results and analysis history.
"""

import redis.asyncio as aioredis
from src.core.config import settings
from src.core.logger import logger

redis_client: aioredis.Redis | None = None


async def init_redis():
    """Initialize Redis connection pool."""
    global redis_client
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis unavailable, caching disabled: {e}")
        redis_client = None


def get_redis() -> aioredis.Redis | None:
    return redis_client
