"""
Async PostgreSQL Database Setup
Uses SQLAlchemy 2.0 async engine with asyncpg driver.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base

from src.core.config import settings
from src.core.logger import logger

Base = declarative_base()

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Initialize database tables on startup with retry logic."""
    import asyncio

    # Import models so metadata registers tables
    import src.models.db_models

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables initialized")
            return
        except Exception as e:
            logger.warning(f"DB init attempt {attempt}/{max_retries} failed: {e}")
            if attempt == max_retries:
                logger.error("Database initialization failed after all retries")
                raise
            await asyncio.sleep(2 * attempt)  # 2s, 4s, 6s, 8s backoff


async def get_db():
    """Dependency: yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()