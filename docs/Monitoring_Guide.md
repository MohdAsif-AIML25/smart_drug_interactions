# Monitoring Guide — Smart Drug Interaction Platform

## Overview

The platform has a full observability stack:

| Tool | Purpose | URL |
|---|---|---|
| **Prometheus** | Collects metrics from FastAPI | http://localhost:9090 |
| **Grafana** | Visualizes metrics as dashboards | http://localhost:3001 |
| **Loguru** | Structured JSON logs from backend | Docker logs |

---

## Prometheus

### What is Prometheus?

Prometheus is a time-series database that **scrapes metrics** from your services every few seconds and stores them. You can then query them to understand how your system behaves.

### Accessing Prometheus

Open: http://localhost:9090

### Key Metrics in This Platform

| Metric | What It Tells You |
|---|---|
| `http_requests_total` | Total number of API requests (by endpoint + status code) |
| `http_request_duration_seconds` | How long each request took |
| `process_resident_memory_bytes` | Backend RAM usage |
| `process_cpu_seconds_total` | Backend CPU usage |

### How to Query (PromQL Examples)

**Request rate (per second, last 5 minutes):**
```
rate(http_requests_total[5m])
```

**95th percentile latency:**
```
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

**Error rate (4xx + 5xx):**
```
rate(http_requests_total{status=~"4..|5.."}[5m])
```

**Total analysis requests:**
```
http_requests_total{path="/api/v1/analyse"}
```

---

## Grafana

### What is Grafana?

Grafana connects to Prometheus and lets you build **visual dashboards** — charts, graphs, and alerts — without writing any code.

### Accessing Grafana

Open: http://localhost:3001
- Username: `admin`
- Password: `admin` (change this in production)

### Pre-built Dashboard

The platform comes with a pre-provisioned dashboard at:
`monitoring/grafana/provisioning/dashboards/platform-dashboard.json`

Grafana loads this automatically on startup — no manual import needed.

The dashboard shows:
- **API Request Rate** — requests per second over time
- **Response Latency** — p50, p95, p99 response times
- **Error Rate** — percentage of failed requests
- **Active Connections** — current concurrent users

### How Auto-Provisioning Works

```
monitoring/
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── datasources.yml    ← tells Grafana where Prometheus is
        └── dashboards/
            ├── dashboards.yml     ← tells Grafana where to find JSON files
            └── platform-dashboard.json  ← the actual dashboard
```

Grafana reads these files at startup via the Docker volume mount:
```yaml
volumes:
  - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
```

### Creating a New Dashboard Manually

1. Open Grafana → click **"+"** → **Dashboard**
2. Click **Add visualization**
3. Select **Prometheus** as data source
4. Enter a PromQL query (e.g. `rate(http_requests_total[5m])`)
5. Click **Apply** → **Save dashboard**

### Setting Up Alerts

1. In any panel → click the bell icon → **Create alert rule**
2. Example: alert if error rate > 5% for 2 minutes
3. Add notification channel (email, Slack, PagerDuty)

---

## Structured Logging (Loguru)

### What is Loguru?

Loguru is the logging library used in the backend. It writes **structured JSON logs** — each log line is valid JSON, making it easy to search and filter in log management tools.

### Log Format

Every log line looks like:
```json
{
  "timestamp": "2026-06-22T10:30:15.123Z",
  "level": "INFO",
  "message": "[a1b2c3d4] Severity: contraindicated",
  "service": "drug-interaction-backend"
}
```

### Viewing Logs

```bash
# Live backend logs
docker compose logs -f backend

# Search for errors only
docker compose logs backend | grep '"level":"ERROR"'

# Search for a specific trace ID
docker compose logs backend | grep "a1b2c3d4"

# Search for a specific drug pair
docker compose logs backend | grep "warfarin"
```

### Log Levels

| Level | When It's Used |
|---|---|
| `INFO` | Normal operation — startup, requests, predictions |
| `WARNING` | Non-fatal issues — cache miss, API retry |
| `ERROR` | Failures that affected a request but didn't crash the app |
| `EXCEPTION` | Unhandled exceptions with full stack trace |

### Trace IDs

Every analysis request gets a **trace ID** (8 characters) logged at the start:
```
[a1b2c3d4] Analysing: Warfarin + Aspirin
[a1b2c3d4] Severity: contraindicated
[a1b2c3d4] ✅ Saved to DB
```

This makes it easy to follow a single request through all log lines even under concurrent load.

---

## Health Check Endpoint

The backend exposes a health check endpoint used by Docker, load balancers, and monitoring tools:

```bash
curl http://localhost:8000/api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-06-22T10:30:00.000Z"
}
```

### Docker Health Check Config

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 90s
```

`start_period: 90s` gives the backend time to download the ChromaDB sentence-transformer model on first startup before health checks begin.

---

## What to Monitor in Production

| What | Why | Alert Threshold |
|---|---|---|
| Error rate | High errors = broken feature | > 5% for 2 minutes |
| p95 latency | Slow responses = bad UX | > 10 seconds |
| Backend memory | OOM = crash | > 700 MB |
| Kafka consumer lag | Pipeline falling behind | > 1000 messages |
| Redis memory | Cache evictions | > 60 MB |
| PostgreSQL connections | Connection pool exhaustion | > 80 active |

---

## Prometheus Scrape Config

`prometheus.yml` tells Prometheus what to scrape:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'drug-interaction-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
```

Prometheus scrapes `http://backend:8000/metrics` every 15 seconds.
