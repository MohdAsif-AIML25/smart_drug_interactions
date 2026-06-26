# Architecture — Smart Drug Interaction Platform

## Overview

The platform is designed as a **production-grade, event-driven AI system** with three clearly separated layers:

1. **Request Layer** — React frontend talks to FastAPI via HTTP + Server-Sent Events (SSE)
2. **Intelligence Layer** — ML model + RAG pipeline + Groq LLM produce the analysis
3. **Data Pipeline Layer** — Kafka continuously ingests live drug data from OpenFDA and PubMed

---

## Full System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite + TypeScript)           │
│                                                                 │
│   DrugSearch (autocomplete)                                     │
│       │                                                         │
│   AnalyseForm (submit drug pair)                                │
│       │                                                         │
│   useSSE hook (reads SSE stream)                                │
│       │                                                         │
│   StreamingPanel ──► SeverityBadge + SourcesPanel + TextStream │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    HTTP + SSE (port 3002)
                           │
                    Nginx reverse proxy
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend (port 8000)                   │
│                                                                 │
│  POST /api/v1/analyse  ─────────────────────────────────────►  │
│                                                                 │
│   Step 1: Redis cache check (order-independent key)            │
│           HIT  → stream cached result immediately              │
│           MISS → continue below                                 │
│                                                                 │
│   Step 2: ML Service                                           │
│           normalize drug names → extract 7 features            │
│           GradientBoosting.predict_proba() → severity + conf.  │
│           known interaction lookup → confidence boost           │
│           ── SSE event: severity ──────────────────────────►   │
│                                                                 │
│   Step 3: RAG Service (ChromaDB)                               │
│           query vector store → top 3 clinical documents         │
│           ── SSE event: sources ──────────────────────────►    │
│                                                                 │
│   Step 4: Groq LLM Streaming                                   │
│           build prompt (severity + sources + drug names)        │
│           stream tokens from llama-3.3-70b-versatile           │
│           ── SSE event: token (repeated) ─────────────────►    │
│                                                                 │
│   Step 5: Complete + Persist                                   │
│           ── SSE event: complete ─────────────────────────►    │
│           write to Redis (1-hour TTL)                           │
│           write to PostgreSQL (permanent history)               │
│                                                                 │
│  GET /api/v1/history    → PostgreSQL (last 10)                  │
│  GET /api/v1/drugs/search → Redis → RxNorm + OpenFDA           │
│  GET /api/v1/health     → status check                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┼──────────────────┐
         │                 │                  │
    PostgreSQL          Redis            Prometheus
    (history)           (cache)          (metrics)
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  Kafka Pipeline (KRaft Mode)                    │
│                                                                 │
│  openfda_producer.py ──┐                                        │
│                        ├──► Topic: raw_drug_events              │
│  pubmed_producer.py  ──┘           │                            │
│                                    ▼                            │
│                         feature_consumer.py                     │
│                         - normalize drug names                  │
│                         - compute char overlap, suffix match    │
│                         - NLP keyword scan → severity signals   │
│                                    │                            │
│                                    ▼                            │
│                         Topic: processed_features               │
│                                    │                            │
│                                    ▼                            │
│                         ml_consumer.py                          │
│                         - rule-based 5-class prediction         │
│                         - store in Redis (24-hour TTL)          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│              Observability Stack                                │
│   Prometheus ──► Grafana (dashboards: latency, error rate)     │
│   Loguru (JSON logs) ──► Loki (log aggregation)                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Service Responsibilities

### FastAPI Backend
- Single entry point for all client requests
- Manages async sessions for PostgreSQL and Redis
- Coordinates ML → RAG → LLM pipeline inside one SSE generator
- Uses `AsyncSessionLocal` for DB writes inside the streaming generator (not the Depends session, which closes before the generator runs)

### ML Service (`ml_service.py`)
- **Primary classifier:** GradientBoosting with 7 engineered features
- **Fallback:** known interaction lookup when ML model fails
- **Confidence boost:** when ML prediction matches known interaction, raises confidence to the known interaction's calibrated value
- Trained on 4,000 synthetic samples + seeded known pairs
- Model saved as `.pkl` via joblib, loaded at startup

### RAG Service (`rag_service.py`)
- ChromaDB loaded **lazily** on first request (saves 350 MB RAM at startup)
- `sentence-transformers/all-MiniLM-L6-v2` for embedding
- 30+ drug pair documents seeded at collection creation
- Groq LLM client created at startup (lightweight)
- Fallback explanation returned if Groq API fails

### Drug Service (`drug_service.py`)
- Priority: Redis cache → local curated list → RxNorm API → OpenFDA API
- Retry logic via `tenacity` (2 attempts, exponential backoff)
- Results cached in Redis for 1 hour

### Kafka Pipeline
- `openfda_producer.py` — polls OpenFDA adverse events API
- `pubmed_producer.py` — fetches drug interaction abstracts from PubMed NCBI
- `feature_consumer.py` — engineers 8 features from raw events, publishes to `processed_features`
- `ml_consumer.py` — consumes features, runs rule-based prediction, stores in Redis

---

## Data Flow: Drug Analysis Request

```
User types "Warfarin" + "Aspirin" → clicks Analyse
    │
    ▼
POST /api/v1/analyse  {"drug_a": "Warfarin", "drug_b": "Aspirin"}
    │
    ▼
Cache key: "analysis:aspirin:warfarin"  (sorted, lowercase)
    │
    ├── CACHE HIT → stream cached severity + sources + explanation
    │
    └── CACHE MISS
            │
            ▼
        normalize: "warfarin", "aspirin"
            │
            ▼
        extract features: [0.40, 0.35, 0.67, 0.42, 1.0, 0.0, 1.0]
            │
            ▼
        GradientBoosting → "contraindicated" (confidence: 0.97)
            │
            ▼ SSE: severity event
            │
        ChromaDB query: "drug interaction warfarin aspirin..."
        → returns 3 clinical documents (warfarin_aspirin_1, ...)
            │
            ▼ SSE: sources event
            │
        Groq prompt → stream tokens
            │
            ▼ SSE: token (×N)
            │
        SSE: complete event
            │
        Redis.setex(cache_key, 3600, {...})
        PostgreSQL INSERT INTO analysis_history (...)
```

---

## Key Design Decisions

| Decision | Why |
|---|---|
| SSE instead of WebSocket | One-way server push is enough; SSE is simpler, works over HTTP/1.1, no upgrade needed |
| ChromaDB lazy loading | sentence-transformer model is ~350 MB — loading at startup would spike RAM above Docker limits |
| Order-independent cache key | `sorted([drug_a, drug_b])` means warfarin+aspirin and aspirin+warfarin hit the same cache |
| New DB session inside generator | `Depends(get_db)` session closes when `analyse_drugs()` returns the `StreamingResponse` — before the generator runs |
| KRaft mode Kafka | Removes Zookeeper dependency, simpler deployment, fewer containers |
| GradientBoosting over XGBoost | Lighter dependency for Docker image size; accuracy difference negligible at this scale |
| Loguru over stdlib logging | Structured JSON output, zero config, automatic exception serialization |

---

## Memory Budget (Docker)

| Service | Actual Usage | Docker Limit |
|---|---|---|
| PostgreSQL | ~40 MB | 96 MB |
| Redis | ~10 MB | 96 MB |
| Kafka | ~160 MB | 320 MB |
| Backend | ~450 MB | 768 MB |
| Frontend (Nginx) | ~15 MB | 48 MB |
| Grafana | ~80 MB | 192 MB |
| **Total** | **~755 MB** | **~1.5 GB** |

---

## Security Considerations

- All secrets loaded from `.env` via Pydantic `BaseSettings` — never hardcoded
- `.env` is in `.gitignore` — only `.env.example` is committed
- CORS origins explicitly whitelisted in `config.py`
- Redis keys use normalized, lowercase drug names — no user input injected raw
- Input validation via Pydantic (`min_length=1`, `max_length=200`) before any processing
- GZip middleware on FastAPI reduces response payload size

---

## Scalability Path

| Current | Production Upgrade |
|---|---|
| Single FastAPI worker | Multiple Uvicorn workers behind a load balancer |
| ChromaDB (local) | Qdrant or Pinecone for distributed vector search |
| SQLite ChromaDB backend | PostgreSQL-backed ChromaDB |
| Single Kafka broker | 3-broker Kafka cluster with replication factor 3 |
| Redis single node | Redis Cluster or Redis Sentinel |
| Docker Compose | Kubernetes with HPA (auto-scaling) |
