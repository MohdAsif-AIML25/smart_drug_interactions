# Deployment Guide — Smart Drug Interaction Platform

## Deployment Options

| Option | Best For | Cost | Effort |
|---|---|---|---|
| Local Docker Compose | Development + Demo | Free | Low |
| Render.com | Portfolio + Sharing | Free tier available | Low |
| AWS EC2 + Docker | Production | ~$20/month | Medium |
| Kubernetes (EKS/GKE) | Scale production | ~$100+/month | High |

---

## Option 1 — Local Docker Compose (Recommended for Demo)

See [Docker_Guide.md](Docker_Guide.md) for full instructions.

```bash
cp .env.example .env
# Add GROQ_API_KEY to .env
docker compose up -d
```

App runs at: http://localhost:3002

---

## Option 2 — Render.com (Free Cloud Deployment)

The repo includes `render.yaml` which defines all services for Render.com.

### Step 1 — Create Render account

Go to [render.com](https://render.com) → Sign up with GitHub

### Step 2 — Connect your GitHub repo

Dashboard → **New** → **Blueprint** → connect `MohdAsif-AIML25/smart_drug_interactions`

Render reads `render.yaml` automatically and creates all services.

### Step 3 — Add environment variables

In Render dashboard → select your backend service → **Environment** → add:

```
GROQ_API_KEY        = your_groq_api_key_here
DATABASE_URL        = (auto-filled by Render PostgreSQL)
REDIS_URL           = (auto-filled by Render Redis)
```

### Step 4 — Deploy

Click **Deploy** — Render builds and deploys automatically.

### What render.yaml creates

```yaml
services:
  - drug-interaction-backend   # Python web service (FastAPI)
  - drug-interaction-frontend  # Static site (React build)

databases:
  - drug-interaction-db        # PostgreSQL managed database

caches:
  - drug-interaction-redis     # Redis managed instance
```

> **Note:** Kafka is not available on Render free tier. The platform works without Kafka — the Kafka pipeline is for background data ingestion only. The core ML + RAG + LLM analysis runs independently.

---

## Option 3 — AWS EC2 (Production)

### Step 1 — Launch EC2 instance

- AMI: Ubuntu 22.04 LTS
- Instance type: `t3.medium` (2 vCPU, 4 GB RAM) minimum
- Security group: open ports 22, 80, 443, 8000, 3002

### Step 2 — Install Docker

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker ubuntu
```

### Step 3 — Clone and configure

```bash
git clone https://github.com/MohdAsif-AIML25/smart_drug_interactions.git
cd smart_drug_interactions
cp .env.example .env
nano .env   # add your GROQ_API_KEY and strong passwords
```

### Step 4 — Run

```bash
docker compose up -d
```

### Step 5 — Set up Nginx + SSL (optional but recommended)

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## Environment Variables Reference

| Variable | Local | Render | AWS |
|---|---|---|---|
| `GROQ_API_KEY` | Set in `.env` | Set in dashboard | Set in `.env` |
| `DATABASE_URL` | Auto (docker-compose) | Auto (managed DB) | Set in `.env` |
| `REDIS_URL` | Auto (docker-compose) | Auto (managed Redis) | Set in `.env` |
| `KAFKA_BOOTSTRAP_SERVERS` | Auto (docker-compose) | Not available | Set in `.env` |
| `CHROMA_DB_PATH` | `/app/chroma_data` | `/app/chroma_data` | `/app/chroma_data` |
| `ML_MODEL_PATH` | `/app/models/drug_interaction_model.pkl` | Same | Same |

---

## CI/CD with GitHub Actions (Optional)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Render

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Trigger Render Deploy
        run: |
          curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"
```

Add `RENDER_DEPLOY_HOOK_URL` to GitHub Secrets (from Render dashboard → service → Settings → Deploy Hook).

---

## Production Checklist

Before deploying to production, verify:

- [ ] `GROQ_API_KEY` is set and valid
- [ ] `DATABASE_URL` uses a strong password
- [ ] `REDIS_URL` is secured (password protected)
- [ ] `.env` is NOT committed to GitHub
- [ ] `CORS_ORIGINS` in `config.py` lists only your actual domain
- [ ] `JSON_LOGS=true` for structured log collection
- [ ] Grafana password changed from default `admin`
- [ ] Docker memory limits reviewed for your server's RAM
- [ ] Health checks passing: `GET /api/v1/health`

---

## Monitoring After Deployment

Once deployed, verify the platform is healthy:

```bash
# Health check
curl https://yourdomain.com/api/v1/health

# Expected response
{"status": "healthy", "version": "1.0.0", "timestamp": "2026-06-22T..."}

# Test drug analysis
curl -X POST https://yourdomain.com/api/v1/analyse \
  -H "Content-Type: application/json" \
  -d '{"drug_a": "Warfarin", "drug_b": "Aspirin"}'
```

See [Monitoring_Guide.md](Monitoring_Guide.md) for Grafana dashboard setup.
