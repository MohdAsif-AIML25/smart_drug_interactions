"""
Pytest Configuration & Shared Fixtures
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os

# Ensure backend src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Mock environment so tests don't need a real .env ──────────────────

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY",          "test-key-123")
    monkeypatch.setenv("DATABASE_URL",          "postgresql+asyncpg://postgres:postgres@localhost:5432/testdb")
    monkeypatch.setenv("REDIS_URL",             "redis://localhost:6379/0")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    monkeypatch.setenv("CHROMA_DB_PATH",        "/tmp/test_chroma")
    monkeypatch.setenv("ML_MODEL_PATH",         "/tmp/test_model.pkl")


# ── FastAPI test client ────────────────────────────────────────────────

@pytest.fixture
def client():
    """
    Test client with DB, Redis, ML, RAG mocked out.
    Tests only check routing, validation, and business logic.
    """
    with patch("src.core.database.init_db", new_callable=AsyncMock), \
         patch("src.core.redis_client.init_redis", new_callable=AsyncMock), \
         patch("src.services.ml_service.ml_service.initialize", new_callable=AsyncMock), \
         patch("src.services.rag_service.rag_service.initialize", new_callable=AsyncMock):

        from main import create_app
        app = create_app()

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
