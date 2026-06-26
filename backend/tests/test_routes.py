"""
Integration Tests — FastAPI Routes

Tests:
  - GET  /api/v1/health
  - GET  /api/v1/drugs/search
  - POST /api/v1/analyse (SSE streaming)
  - GET  /api/v1/history
  - Input validation (empty, too long, missing fields)
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models.schemas import SeverityLevel, MLPrediction, DrugSource


# ─── Health Check ─────────────────────────────────────────────────────

class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_health_response_body(self, client):
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data

    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


# ─── Drug Search ──────────────────────────────────────────────────────

class TestDrugSearch:

    def test_search_returns_suggestions(self, client):
        with patch("src.services.drug_service.drug_service.search_drugs",
                   new_callable=AsyncMock,
                   return_value=[MagicMock(model_dump=lambda: {"name": "Warfarin"})]):
            resp = client.get("/api/v1/drugs/search?q=war")
            assert resp.status_code == 200
            assert "suggestions" in resp.json()

    def test_search_requires_query(self, client):
        resp = client.get("/api/v1/drugs/search")
        assert resp.status_code == 422  # missing required param

    def test_search_empty_query_rejected(self, client):
        # q must be min_length=1
        resp = client.get("/api/v1/drugs/search?q=")
        assert resp.status_code == 422


# ─── Analysis Endpoint (SSE) ──────────────────────────────────────────

class TestAnalyseEndpoint:

    def _mock_ml_predict(self):
        return MLPrediction(
            severity=SeverityLevel.SEVERE,
            confidence=0.92,
            probabilities={
                "none": 0.01, "mild": 0.02,
                "moderate": 0.03, "severe": 0.92,
                "contraindicated": 0.02,
            },
        )

    def _mock_sources(self):
        return [
            DrugSource(
                title="Test Source",
                source="pubmed",
                url="https://pubmed.ncbi.nlm.nih.gov",
                snippet="Test snippet about drug interaction.",
            )
        ]

    def test_analyse_returns_200(self, client):
        with patch("src.services.ml_service.ml_service.predict",
                   new_callable=AsyncMock, return_value=self._mock_ml_predict()), \
             patch("src.services.rag_service.rag_service.retrieve_sources",
                   new_callable=AsyncMock, return_value=self._mock_sources()), \
             patch("src.services.rag_service.rag_service.stream_explanation",
                   return_value=self._async_gen(["Warfarin", " and ", "Aspirin", " interact."])), \
             patch("src.core.redis_client.get_redis", return_value=None), \
             patch("src.core.database.get_db", return_value=self._mock_db()):

            resp = client.post(
                "/api/v1/analyse",
                json={"drug_a": "Warfarin", "drug_b": "Aspirin"},
            )
            assert resp.status_code == 200

    def test_analyse_validates_empty_drug(self, client):
        resp = client.post("/api/v1/analyse", json={"drug_a": "", "drug_b": "Aspirin"})
        assert resp.status_code == 422

    def test_analyse_validates_missing_field(self, client):
        resp = client.post("/api/v1/analyse", json={"drug_a": "Warfarin"})
        assert resp.status_code == 422

    def test_analyse_validates_too_long(self, client):
        resp = client.post("/api/v1/analyse", json={
            "drug_a": "x" * 201,
            "drug_b": "Aspirin"
        })
        assert resp.status_code == 422

    def test_analyse_content_type_is_event_stream(self, client):
        with patch("src.services.ml_service.ml_service.predict",
                   new_callable=AsyncMock, return_value=self._mock_ml_predict()), \
             patch("src.services.rag_service.rag_service.retrieve_sources",
                   new_callable=AsyncMock, return_value=[]), \
             patch("src.services.rag_service.rag_service.stream_explanation",
                   return_value=self._async_gen(["test"])), \
             patch("src.core.redis_client.get_redis", return_value=None), \
             patch("src.core.database.get_db", return_value=self._mock_db()):

            resp = client.post(
                "/api/v1/analyse",
                json={"drug_a": "Metformin", "drug_b": "Aspirin"},
            )
            assert "text/event-stream" in resp.headers.get("content-type", "")

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    async def _async_gen(items):
        for item in items:
            yield item

    @staticmethod
    def _mock_db():
        """Context manager mock for get_db dependency."""
        import contextlib

        @contextlib.asynccontextmanager
        async def _db():
            session = AsyncMock()
            session.add = MagicMock()
            session.commit = AsyncMock()
            session.rollback = AsyncMock()
            session.close = AsyncMock()
            yield session

        return _db()


# ─── History Endpoint ─────────────────────────────────────────────────

class TestHistoryEndpoint:

    def test_history_returns_200(self, client):
        with patch("src.core.database.get_db", return_value=self._mock_db_empty()):
            resp = client.get("/api/v1/history")
            assert resp.status_code == 200

    def test_history_response_has_history_key(self, client):
        with patch("src.core.database.get_db", return_value=self._mock_db_empty()):
            resp = client.get("/api/v1/history")
            assert "history" in resp.json()

    @staticmethod
    def _mock_db_empty():
        import contextlib

        @contextlib.asynccontextmanager
        async def _db():
            session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            session.execute = AsyncMock(return_value=mock_result)
            session.commit = AsyncMock()
            session.close = AsyncMock()
            yield session

        return _db()
