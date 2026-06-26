# Docker Guide — Smart Drug Interaction Platform

## Overview

The entire platform runs as **6 Docker containers** orchestrated by Docker Compose. One command starts everything.

```
docker compose up -d
```

---

## Services

| Container | Image | Port | Purpose |
|---|---|---|---|
| `drug_postgres` | postgres:16-alpine | 5432 | Stores analysis history |
| `drug_redis` | redis:7-alpine | 6379 | Caches results + drug search |
| `drug_kafka` | apache/kafka:3.7.0 | 9092 | Event pipeline (KRaft mode) |
| `drug_backend` | Built from `./backend` | 8000 | FastAPI AI backend |
| `drug_frontend` | Built from `./frontend` | 3002 | React app via Nginx |
| `drug_grafana` | grafana/grafana:latest | 3001 | Monitoring dashboards |

---

## Prerequisites

- Docker Desktop installed and running
- Docker Compose v2+ (comes with Docker Desktop)
- At least **2 GB free RAM**
- Groq API key (free at [groq.com](https://groq.com))

---

## Setup

### Step 1 — Clone the repo

```bash
git clone https://github.com/MohdAsif-AIML25/smart_drug_interactions.git
cd smart_drug_interactions
```

### Step 2 — Create your .env file

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
GROQ_API_KEY=your_groq_api_key_here

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=drugdb

GRAFANA_PASSWORD=admin
```

### Step 3 — Build and start

```bash
docker compose up -d
```

First build takes 3–5 minutes (downloads images, installs Python packages, builds React app).

### Step 4 — Verify all containers are running

```bash
docker compose ps
```

Expected output:
```
NAME             STATUS          PORTS
drug_postgres    Up (healthy)    0.0.0.0:5432->5432/tcp
drug_redis       Up (healthy)    0.0.0.0:6379->6379/tcp
drug_kafka       Up              0.0.0.0:9092->9092/tcp
drug_backend     Up (healthy)    0.0.0.0:8000->8000/tcp
drug_frontend    Up              0.0.0.0:3002->80/tcp
drug_grafana     Up              0.0.0.0:3001->3000/tcp
```

---

## Common Commands

### Start / Stop

```bash
# Start all services
docker compose up -d

# Stop all services (keeps data volumes)
docker compose down

# Stop and delete all data (fresh start)
docker compose down -v
```

### Rebuild after code change

```bash
# Rebuild only the backend
docker compose up -d --build backend

# Rebuild only the frontend
docker compose up -d --build frontend

# Rebuild everything
docker compose up -d --build
```

### View logs

```bash
# All services
docker compose logs -f

# Only backend
docker compose logs -f backend

# Only kafka
docker compose logs -f kafka

# Last 50 lines
docker compose logs --tail=50 backend
```

### Restart a service

```bash
docker compose restart backend
docker compose restart frontend
```

---

## Backend Dockerfile Explained

```dockerfile
# Stage 1: Builder — installs Python dependencies
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Production — lean final image
FROM python:3.11-slim AS production
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

**Why multi-stage?** The builder stage installs all build tools and compiles packages. The production stage only copies the result — no build tools in the final image. This makes the image smaller and more secure.

---

## Frontend Dockerfile Explained

```dockerfile
# Stage 1: Build React app
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**Why Nginx?** React builds to static files. Nginx serves them efficiently and also acts as a **reverse proxy** — all `/api/*` requests are forwarded to the backend container, so the frontend never calls `localhost:8000` directly.

---

## Nginx Proxy Config

```nginx
location /api/ {
    proxy_pass http://backend:8000;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding on;
}
```

The `Connection: ''` and `proxy_http_version 1.1` lines are critical for **SSE (Server-Sent Events)** — without them, Nginx buffers the stream and the frontend sees no tokens until the response completes.

---

## Volume Management

Docker creates 6 named volumes to persist data across container restarts:

| Volume | Used By | Contains |
|---|---|---|
| `postgres_data` | PostgreSQL | All analysis history |
| `redis_data` | Redis | Persisted cache (AOF) |
| `kafka_data` | Kafka | Topic offsets and messages |
| `chroma_data` | Backend | ChromaDB vector store |
| `model_data` | Backend | Trained ML model (.pkl) |
| `grafana_data` | Grafana | Dashboard configurations |

To inspect volumes:
```bash
docker volume ls
docker volume inspect smart-drug-interactions_postgres_data
```

---

## Memory Limits

Each service has explicit memory limits to prevent one service from crashing others:

```yaml
mem_limit: 768m      # backend (large — ML model + ChromaDB)
mem_limit: 320m      # kafka
mem_limit: 192m      # grafana
mem_limit: 96m       # postgres
mem_limit: 96m       # redis
mem_limit: 48m       # frontend
```

---

## Health Checks

Docker health checks ensure services start in the correct order:

- `postgres` must be healthy before `backend` starts
- `redis` must be healthy before `backend` starts
- `backend` must be healthy before `frontend` starts
- `postgres` must be healthy before `grafana` starts

```bash
# Check health status
docker inspect drug_backend | grep -A 5 '"Health"'
```

---

## Troubleshooting

**Backend stuck in "starting" for over 2 minutes:**
```bash
docker compose logs backend
# Common cause: ChromaDB downloading sentence-transformer model on first run
# Solution: wait — it's a one-time 90MB download
```

**Kafka health check failing:**
```bash
docker compose logs kafka
# Common cause: not enough memory
# Solution: increase Docker Desktop memory limit to 4GB in Settings
```

**Port already in use:**
```bash
# Check what's using port 8000
netstat -ano | findstr :8000  # Windows
lsof -i :8000                  # Mac/Linux
```

**Fresh start (wipe all data):**
```bash
docker compose down -v
docker compose up -d --build
```
