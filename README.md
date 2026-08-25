<div align="center">

# 🧬 Smart Drug Interaction Analysis Platform

**  AI platform that predicts drug-drug interaction severity using Machine Learning, Retrieval-Augmented Generation (RAG), and real-time LLM streaming.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Kafka](https://img.shields.io/badge/Apache_Kafka-KRaft-231F20?style=for-the-badge&logo=apache-kafka&logoColor=white)](https://kafka.apache.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[Features](#features) • [Architecture](#architecture) • [Quick Start](#quick-start) • [API Reference](#api-reference) • [Tech Stack](#tech-stack)

</div>

---

## What This Project Does

A doctor or patient enters two drug names (e.g. **Warfarin + Aspirin**). The platform:

1. **Predicts severity** in under 2 seconds using a trained ML model (GradientBoosting, 5 classes)
2. **Retrieves clinical evidence** from ChromaDB vector store (30+ drug pairs, PubMed + OpenFDA sources)
3. **Streams a medical explanation** token-by-token via Groq LLM (like ChatGPT streaming)
4. **Saves history** to PostgreSQL and caches results in Redis for instant repeat queries
5. **Ingests live data** continuously from OpenFDA and PubMed APIs via Apache Kafka pipeline

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite + TypeScript)           │
│   DrugSearch → AnalyseForm → SSE Stream → SeverityBadge        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP + Server-Sent Events (SSE)
┌──────────────────────────▼──────────────────────────────────────┐
│                  FastAPI Backend (Python 3.11)                  │
│                                                                 │
│  POST /api/v1/analyse                                           │
│       │                                                         │
│       ├─► ML Service (GradientBoosting) ──► Severity + Conf.   │
│       ├─► RAG Service (ChromaDB query)  ──► Clinical Sources   │
│       └─► Groq LLM (llama-3.3-70b)     ──► Streaming tokens   │
│                                                                 │
│  PostgreSQL (history) │ Redis (cache) │ Prometheus (metrics)   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  Kafka Pipeline (KRaft — no Zookeeper)          │
│                                                                 │
│  OpenFDA Producer ──┐                                           │
│                     ├──► raw_drug_events                        │
│  PubMed Producer  ──┘         │                                 │
│                               ▼                                 │
│                      Feature Consumer                           │
│                      (NLP + feature engineering)                │
│                               │                                 │
│                               ▼                                 │
│                      ML Inference Consumer                      │
│                               │                                 │
│                    Redis Cache + PostgreSQL                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│               Observability Stack                               │
│         Prometheus + Grafana + Loki + Node Exporter             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Technology | Detail |
|---|---|---|
| ML Severity Prediction | scikit-learn GradientBoosting | 5-class: none / mild / moderate / severe / contraindicated |
| Vector Search (RAG) | ChromaDB + sentence-transformers | 30+ drug pairs, cosine similarity |
| LLM Streaming | Groq (llama-3.3-70b) | Token-by-token via Server-Sent Events |
| Real-time Pipeline | Apache Kafka KRaft | No Zookeeper, feature engineering consumer |
| Drug Autocomplete | RxNorm + OpenFDA APIs | Real-time search with Redis cache |
| History | PostgreSQL + SQLAlchemy | Async ORM, last 10 analyses |
| Caching | Redis | 1-hour TTL, order-independent cache key |
| Observability | Prometheus + Grafana | Request rate, latency p95, ML inference time |
| Frontend | React 18 + TypeScript + Tailwind | SSE streaming, severity color coding |
| Deployment | Docker Compose + Render.com | Full stack in one command |

---

## Severity Classification

| Severity | Color | Meaning |
|---|---|---|
| None | 🟢 Green | No clinically significant interaction |
| Mild | 🟡 Yellow | Minor interaction, manageable |
| Moderate | 🟠 Orange | Requires monitoring |
| Severe | 🔴 Red | High risk, medical supervision needed |
| Contraindicated | ⚫ Black | Dangerous — never combine |

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Groq API key — free at [groq.com](https://groq.com)

### 1. Clone

```bash
git clone https://github.com/MohdAsif-AIML25/smart_drug_interactions.git
cd smart_drug_interactions
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 3. Run everything

```bash
docker compose up -d
```

### 4. Open

| Service | URL |
|---|---|
| Frontend | http://localhost:3002 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Grafana Dashboard | http://localhost:3001 (admin/admin) |
| Prometheus | http://localhost:9090 |

---

## API Reference

### POST /api/v1/analyse

Analyse drug-drug interaction with real-time SSE streaming.

**Request:**
```json
{
  "drug_a": "Warfarin",
  "drug_b": "Aspirin"
}
```

**SSE Event Stream:**
```
event: connected
data: connected

event: severity
data: {"severity": "contraindicated", "confidence": 0.97, "probabilities": {...}}

event: sources
data: {"sources": [{"title": "...", "source": "pubmed", "snippet": "..."}]}

event: token
data: {"token": "Warfarin"}

event: token
data: {"token": " and Aspirin..."}

event: complete
data: {"drug_a": "Warfarin", "drug_b": "Aspirin", "severity": "contraindicated", "full_explanation": "..."}
```

### GET /api/v1/history
Returns last 10 analyses from PostgreSQL.

### GET /api/v1/drugs/search?q=war
Drug autocomplete — searches RxNorm + OpenFDA + local curated list.

### GET /api/v1/health
Platform health check.

---

## ML Model Details

The severity classifier uses **Gradient Boosting** with 7 engineered features:

| Feature | Description |
|---|---|
| `len_a`, `len_b` | Normalized drug name lengths |
| `char_overlap` | Jaccard similarity between character sets |
| `hash_sim` | MD5-based hash similarity |
| `known_interaction` | Rule-based lookup signal |
| `same_drug_class` | Suffix detection (-olol, -statin, -pril, etc.) |
| `risk_flag` | High-risk drug detection |

Training: 4,000 synthetic samples + real known interactions as seed data.
Target: prediction in under 2 seconds.

---

## Kafka Pipeline

```
OpenFDA API  ──► raw_drug_events ──► feature_consumer ──► processed_features ──► ml_consumer ──► Redis
PubMed API   ──┘                     (NLP + features)                            (5-class pred.)
```

Topics:

| Topic | Purpose | Partitions |
|---|---|---|
| `raw_drug_events` | Raw OpenFDA + PubMed data | 3 |
| `processed_features` | Engineered ML features | 3 |

---

## Project Structure

```
smart-drug-interactions/
├── backend/
│   ├── main.py                      # FastAPI app + lifespan (DB, Redis, ML, RAG init)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── src/
│       ├── api/routes.py            # All endpoints + SSE streaming logic
│       ├── core/
│       │   ├── config.py            # Pydantic Settings (env validation)
│       │   ├── database.py          # Async SQLAlchemy + session factory
│       │   ├── redis_client.py      # Redis async connection
│       │   └── logger.py            # Loguru JSON structured logging
│       ├── models/
│       │   ├── schemas.py           # Pydantic v2 request/response models
│       │   └── db_models.py         # SQLAlchemy ORM models
│       └── services/
│           ├── ml_service.py        # GradientBoosting severity classifier
│           ├── rag_service.py       # ChromaDB retrieval + Groq LLM streaming
│           └── drug_service.py      # Drug autocomplete (RxNorm + OpenFDA)
├── frontend/
│   └── src/
│       ├── types/index.ts           # TypeScript types (SeverityLevel, SSE events)
│       ├── hooks/useSSE.ts          # SSE streaming React hook
│       ├── services/api.ts          # Axios API layer
│       └── components/              # DrugSearch, AnalyseForm, StreamingPanel, Dashboard...
├── ingestion/
│   ├── openfda_producer.py          # Polls OpenFDA → Kafka
│   ├── pubmed_producer.py           # Fetches PubMed abstracts → Kafka
│   ├── feature_consumer.py          # Raw events → engineered ML features
│   └── ml_consumer.py               # Features → predictions → Redis
├── monitoring/
│   └── grafana/provisioning/        # Auto-provisioned Grafana dashboards
├── kafka/                           # Kafka topic creation scripts
├── docker-compose.yml               # Full stack: 6 services
├── prometheus.yml                   # Metrics scraping config
├── render.yaml                      # One-click Render.com deployment
└── Makefile                         # Developer shortcuts
```

---

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GROQ_API_KEY` | Groq LLM API key | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka brokers | No (default: kafka:9092) |
| `CHROMA_DB_PATH` | ChromaDB persistence path | No |
| `GROQ_MODEL` | LLM model name | No (default: llama-3.3-70b-versatile) |

---

## Tech Stack

**Backend:** Python 3.11 · FastAPI · Pydantic v2 · SQLAlchemy (async) · Loguru

**AI/ML:** scikit-learn · GradientBoosting · ChromaDB · sentence-transformers · Groq API

**Data Pipeline:** Apache Kafka (KRaft) · OpenFDA API · PubMed NCBI API

**Frontend:** React 18 · TypeScript · Vite · Tailwind CSS · Axios · SSE

**Infrastructure:** Docker · Docker Compose · Nginx · PostgreSQL · Redis

**Observability:** Prometheus · Grafana · Loki

**Deployment:** Render.com · render.yaml

---

## Troubleshooting

**Backend won't start:**
```bash
docker compose logs backend
# Check: is GROQ_API_KEY set in .env?
```

**ChromaDB empty (no sources returned):**
```bash
# Restart backend — it auto-seeds ChromaDB on startup
docker compose restart backend
```

**Frontend can't reach API:**
```bash
# Check nginx proxy
docker exec drug_frontend cat /etc/nginx/conf.d/default.conf
```

---

## Author

**Mohammad Asif** — AI/ML Engineer

[![GitHub](https://img.shields.io/badge/GitHub-MohdAsif--AIML25-181717?style=flat-square&logo=github)](https://github.com/MohdAsif-AIML25)
[![Email](https://img.shields.io/badge/Email-mohdasif.m1996%40gmail.com-D14836?style=flat-square&logo=gmail&logoColor=white)](mailto:mohdasif.m1996@gmail.com)

---

<div align="center">
Built for production-grade AI healthcare tooling.
</div>
