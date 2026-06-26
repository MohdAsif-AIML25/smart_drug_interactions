"""
FastAPI API Routes

Endpoints:
  POST /api/v1/analyse         -- SSE streaming drug interaction analysis
  GET  /api/v1/history         -- Query history (last 10)
  GET  /api/v1/drugs/search    -- Drug autocomplete
  GET  /api/v1/health          -- Health check
"""

import json
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal, get_db
from src.core.logger import logger
from src.core.redis_client import get_redis
from src.models.db_models import AnalysisHistory
from src.models.schemas import (
    AnalyseRequest,
    CompleteEvent,
    ErrorEvent,
    HealthResponse,
    HistoryItem,
    SeverityEvent,
    SourcesEvent,
    TokenEvent,
)
from src.services.drug_service import drug_service
from src.services.ml_service import ml_service
from src.services.rag_service import rag_service

router = APIRouter()

# Cache TTL: 1 hour for completed analyses
ANALYSIS_CACHE_TTL = 3600


# -----------------------------------------------
# Health Check
# -----------------------------------------------

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow(),
    )


# -----------------------------------------------
# Drug Search / Autocomplete
# -----------------------------------------------

@router.get("/drugs/search", tags=["Drugs"])
async def search_drugs(
    q: str = Query(..., min_length=1, max_length=100)
):
    suggestions = await drug_service.search_drugs(q, limit=10)
    return {
        "suggestions": [s.model_dump() for s in suggestions]
    }


# -----------------------------------------------
# Analysis History
# -----------------------------------------------

@router.get("/history", tags=["Analysis"])
async def get_history(
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AnalysisHistory)
        .order_by(desc(AnalysisHistory.created_at))
        .limit(10)
    )
    records = result.scalars().all()
    history = [
        HistoryItem(
            id=r.id,
            drug_a=r.drug_a,
            drug_b=r.drug_b,
            severity=r.severity,
            confidence=r.confidence,
            explanation=r.explanation,
            created_at=r.created_at,
        ).model_dump(mode="json")
        for r in records
    ]
    return {"history": history}


# -----------------------------------------------
# Drug Analysis SSE Endpoint
# -----------------------------------------------

@router.post("/analyse", tags=["Analysis"])
async def analyse_drugs(
    request: AnalyseRequest,
):
    """
    Server-Sent Events flow:
      event: connected   -- SSE handshake
      event: severity    -- ML prediction
      event: sources     -- RAG citations
      event: token       -- LLM stream token (repeated)
      event: complete    -- full explanation assembled
      event: error       -- on failure
    """
    drug_a = request.drug_a.strip()
    drug_b = request.drug_b.strip()

    trace_id = str(uuid.uuid4())[:8]
    logger.info(f"[{trace_id}] Analysing: {drug_a} + {drug_b}")

    redis = get_redis()

    # Canonical cache key -- order-independent (warfarin+aspirin == aspirin+warfarin)
    key_parts = sorted([drug_a.lower(), drug_b.lower()])
    cache_key = f"analysis:{key_parts[0]}:{key_parts[1]}"

    async def event_stream() -> AsyncGenerator[str, None]:
        full_explanation = ""

        try:
            # SSE handshake
            yield "event: connected\ndata: connected\n\n"

            # ------------------------------------------
            # Redis cache check -- skip ML+RAG+LLM for
            # repeated drug pairs (saves ~5-10s latency)
            # ------------------------------------------
            if redis:
                try:
                    cached_raw = await redis.get(cache_key)
                    if cached_raw:
                        cached = json.loads(cached_raw)
                        logger.info(f"[{trace_id}] Cache HIT: {cache_key}")

                        yield (
                            f"event: severity\n"
                            f"data: {json.dumps(cached['severity_event'])}\n\n"
                        )
                        yield (
                            f"event: sources\n"
                            f"data: {json.dumps(cached['sources_event'])}\n\n"
                        )

                        # Re-stream cached explanation in chunks
                        explanation = cached["full_explanation"]
                        chunk_size = 30
                        for i in range(0, len(explanation), chunk_size):
                            chunk = explanation[i:i + chunk_size]
                            yield (
                                f"event: token\n"
                                f"data: {json.dumps({'token': chunk})}\n\n"
                            )

                        complete_payload = CompleteEvent(
                            drug_a=drug_a,
                            drug_b=drug_b,
                            severity=cached["severity_event"]["severity"],
                            full_explanation=explanation,
                        ).model_dump()
                        yield (
                            f"event: complete\n"
                            f"data: {json.dumps(complete_payload)}\n\n"
                        )
                        return
                except Exception as cache_err:
                    logger.warning(f"[{trace_id}] Cache read error: {cache_err}")

            # ------------------------------------------
            # Step 1: ML Prediction
            # ------------------------------------------
            ml_result = await ml_service.predict(drug_a, drug_b)

            severity_event_data = SeverityEvent(
                severity=ml_result.severity,
                confidence=ml_result.confidence,
                probabilities=ml_result.probabilities,
            ).model_dump()

            yield (
                f"event: severity\n"
                f"data: {json.dumps(severity_event_data)}\n\n"
            )
            logger.info(f"[{trace_id}] Severity: {ml_result.severity}")

            # ------------------------------------------
            # Step 2: RAG Retrieval (ChromaDB + OpenFDA)
            # ------------------------------------------
            sources = await rag_service.retrieve_sources(drug_a, drug_b)

            sources_event_data = SourcesEvent(sources=sources).model_dump()
            yield (
                f"event: sources\n"
                f"data: {json.dumps(sources_event_data, default=str)}\n\n"
            )

            # ------------------------------------------
            # Step 3: LLM Streaming (Groq)
            # ------------------------------------------
            async for token in rag_service.stream_explanation(
                drug_a,
                drug_b,
                ml_result.severity.value,
                sources,
            ):
                full_explanation += token
                yield (
                    f"event: token\n"
                    f"data: {json.dumps({'token': token})}\n\n"
                )

            # ------------------------------------------
            # Step 4: Persist to PostgreSQL FIRST
            # Must happen BEFORE complete event so that
            # when the frontend calls GET /history after
            # receiving complete, the record already exists.
            # IMPORTANT: New session — Depends(get_db)
            # session closes before this generator runs.
            # ------------------------------------------
            try:
                async with AsyncSessionLocal() as save_db:
                    record = AnalysisHistory(
                        id=str(uuid.uuid4()),
                        drug_a=drug_a,
                        drug_b=drug_b,
                        severity=ml_result.severity.value,
                        confidence=ml_result.confidence,
                        explanation=full_explanation,
                        sources_json=json.dumps(
                            [s.model_dump() for s in sources],
                            default=str,
                        ),
                    )
                    save_db.add(record)
                    await save_db.commit()
                logger.info(f"[{trace_id}] ✅ Saved to DB")
            except Exception as db_error:
                logger.error(f"[{trace_id}] ❌ DB save failed: {db_error}")

            # ------------------------------------------
            # Step 5: Write to Redis cache (1 hour TTL)
            # ------------------------------------------
            if redis:
                try:
                    await redis.setex(
                        cache_key,
                        ANALYSIS_CACHE_TTL,
                        json.dumps({
                            "severity_event": severity_event_data,
                            "sources_event": sources_event_data,
                            "full_explanation": full_explanation,
                            "cached_at": datetime.utcnow().isoformat(),
                        }, default=str),
                    )
                    logger.info(f"[{trace_id}] Cached for {ANALYSIS_CACHE_TTL}s")
                except Exception as cache_err:
                    logger.warning(f"[{trace_id}] Cache write error: {cache_err}")

            # ------------------------------------------
            # Step 6: Complete Event — sent LAST so
            # history is already in DB when frontend
            # receives this and calls GET /history
            # ------------------------------------------
            complete_payload = CompleteEvent(
                drug_a=drug_a,
                drug_b=drug_b,
                severity=ml_result.severity,
                full_explanation=full_explanation,
            ).model_dump()
            yield (
                f"event: complete\n"
                f"data: {json.dumps(complete_payload)}\n\n"
            )

        except Exception as e:
            logger.exception(f"[{trace_id}] Analysis failed")
            yield (
                f"event: error\n"
                f"data: {json.dumps({'message': str(e), 'code': 'ANALYSIS_ERROR'})}\n\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Trace-ID": trace_id,
        },
    )
