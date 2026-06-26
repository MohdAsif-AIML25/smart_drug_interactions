"""
Smart Drug Interaction Analysis Platform
Main FastAPI Application Entry Point
"""

# SQLite Fix for ChromaDB — MUST be before importing chromadb or FastAPI routes
__import__("pysqlite3")
import sys
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from prometheus_fastapi_instrumentator import Instrumentator

from src.api.routes import router
from src.core.config import settings
from src.core.database import init_db
from src.core.logger import logger
from src.core.redis_client import init_redis
from src.services.ml_service import ml_service
from src.services.rag_service import rag_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + shutdown lifecycle."""
    logger.info("Starting Smart Drug Interaction Platform...")
    try:
        await init_db()
        logger.info("PostgreSQL connected")

        await init_redis()
        logger.info("Redis connected")

        await ml_service.initialize()
        logger.info("ML model loaded")

        await rag_service.initialize()
        logger.info("RAG initialized")

        logger.info("Platform ready")
        yield

    except Exception as e:
        logger.exception(f"Startup failed: {e}")
        raise

    finally:
        logger.info("Shutting down platform...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Drug Interaction Analysis Platform",
        description="AI-powered drug interaction analysis using ML + RAG + LLM streaming",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.get("/")
    async def root():
        return {"status": "ok", "service": "Smart Drug Interaction Platform"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    app.include_router(router, prefix="/api/v1")

    # Expose /metrics for Prometheus scraping
    Instrumentator().instrument(app).expose(app)

    return app


app = create_app()
