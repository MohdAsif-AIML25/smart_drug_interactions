# ============================================
# Smart Drug Interaction Platform — Backend
# ============================================

FROM python:3.11-slim-bookworm AS base

# ───────────────── System Dependencies ─────────────────

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    gcc \
    sqlite3 \
    libsqlite3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# HuggingFace writable cache
RUN mkdir -p /tmp/huggingface

# ───────────────── Dependencies Stage ─────────────────

FROM base AS deps

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip

# IMPORTANT: sqlite fix for ChromaDB
RUN pip install --no-cache-dir pysqlite3-binary

RUN pip install --no-cache-dir -r requirements.txt

# ───────────────── Production Stage ─────────────────

FROM deps AS production

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH=/app


# HuggingFace cache
ENV HF_HOME=/tmp/huggingface
ENV TRANSFORMERS_CACHE=/tmp/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/tmp/huggingface

COPY . .

# Create writable directories
RUN mkdir -p \
    /app/chroma_data \
    /app/models \
    /app/logs \
    /tmp/huggingface

# Non-root user
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app /tmp/huggingface

USER appuser

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# 1 worker: ChromaDB and the ML model are loaded in-memory at startup.
# Using 2+ workers causes each process to load its own copy of the
# sentence-transformer model, doubling RAM usage (~1.3 GB per worker).
# Keep at 1 worker; horizontal scaling should be done at the container level.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "75"]