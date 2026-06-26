# Demo Script — Smart Drug Interaction Platform

> Use this script when presenting the project in interviews, demos, or video recordings.
> Each section tells you exactly what to show, what to say, and what questions to expect.

---

## Before You Start (Setup Checklist)

```bash
# 1. Start the platform
docker compose up -d

# 2. Wait for all services to be healthy (about 2 minutes)
docker compose ps

# 3. Open these tabs in your browser:
#    Tab 1: http://localhost:3002         (Frontend)
#    Tab 2: http://localhost:8000/docs    (API Swagger)
#    Tab 3: http://localhost:3001         (Grafana)
#    Tab 4: http://localhost:9090         (Prometheus)
```

---

## Demo Flow (10 minutes total)

---

### Part 1 — Introduce the Project (1 minute)

**What to say:**

> "This is a production-grade AI platform for drug interaction analysis. A doctor or patient enters two drug names and the platform immediately predicts how dangerous the combination is, retrieves clinical evidence, and streams a medical explanation — exactly like ChatGPT but specialized for pharmacology."

> "It uses a Machine Learning classifier for speed, ChromaDB for RAG retrieval, and Groq's LLaMA 3.3 for streaming explanation. The entire backend is FastAPI with async Python, PostgreSQL for history, Redis for caching, and a real-time Kafka pipeline ingesting data from OpenFDA and PubMed."

---

### Part 2 — Live Drug Analysis Demo (3 minutes)

**Open Tab 1: http://localhost:3002**

**Demo 1 — Contraindicated pair (most dramatic)**

1. In Drug A field, type: `Warfarin`
2. In Drug B field, type: `Aspirin`
3. Click **Analyse**
4. Watch the SSE stream — severity badge appears first, then sources, then text streams token by token

**What to say while streaming:**

> "Notice how the response is not a single JSON — it's a real-time stream. The frontend uses Server-Sent Events. The first event sends the ML prediction — contraindicated, 97% confidence. The second event sends the clinical sources from ChromaDB. Then the LLM explanation streams token by token."

> "This is the same pattern ChatGPT uses — it feels responsive because you see the answer building in real time instead of waiting 10 seconds for the full response."

**Demo 2 — Moderate interaction**

1. Drug A: `Metformin`
2. Drug B: `Prednisone`
3. Click **Analyse**

**What to say:**

> "Now let's try a moderate interaction. Notice the confidence is lower — around 87% — because the ML model is less certain. The severity badge is orange for moderate. The explanation explains that prednisone raises blood sugar, counteracting metformin's effect."

**Demo 3 — Same pair again (cache hit)**

1. Drug A: `Warfarin`
2. Drug B: `Aspirin` again
3. Click **Analyse**

**What to say:**

> "Same pair again. This time Redis returns the cached result instantly — you'll notice the stream completes in under 1 second instead of 5–10 seconds. The cache key is order-independent — aspirin+warfarin hits the same cache entry as warfarin+aspirin."

---

### Part 3 — Show the API (2 minutes)

**Open Tab 2: http://localhost:8000/docs**

**What to say:**

> "This is the auto-generated Swagger documentation. FastAPI generates this from the Pydantic schemas automatically — no extra documentation work needed."

**Live demo in Swagger:**

1. Click `POST /api/v1/analyse` → **Try it out**
2. Enter: `{"drug_a": "Simvastatin", "drug_b": "Clarithromycin"}`
3. Click **Execute**
4. Show the SSE response in the response body

**Show GET /api/v1/history:**

> "This endpoint returns the last 10 analyses from PostgreSQL — every analysis is persisted, so doctors can review past queries."

**Show GET /api/v1/drugs/search:**

1. Enter `q=war` → Execute
2. Show the autocomplete suggestions

> "The drug search hits our local curated list first, then RxNorm, then OpenFDA — all merged and deduplicated, cached in Redis."

---

### Part 4 — Show Monitoring (2 minutes)

**Open Tab 3: http://localhost:3001 (Grafana)**

Login: admin / admin

**What to say:**

> "This is Grafana. The dashboards are auto-provisioned — they load automatically when the container starts. No manual configuration needed."

Point to charts:

> "This shows API request rate per second, response latency at p95, and error rate. In production, we'd add alerts — for example, page on-call if error rate exceeds 5% for 2 minutes."

**Open Tab 4: http://localhost:9090 (Prometheus)**

Type in query box:
```
rate(http_requests_total[5m])
```

Click **Execute** → switch to **Graph** view

**What to say:**

> "Prometheus scrapes metrics from the FastAPI backend every 15 seconds. This query shows request rate over the last 5 minutes. We can see the spike from our demo requests."

---

### Part 5 — Show the Code (2 minutes)

Open your code editor. Show these 3 files:

**File 1: `backend/src/api/routes.py` — SSE streaming**

> "The key insight here is the async generator. The `event_stream()` function is an async generator that yields SSE events. Redis cache check, ML prediction, RAG retrieval, LLM streaming — all inside one generator. The database session is created fresh inside the generator because the FastAPI dependency session closes before the generator runs."

**File 2: `backend/src/services/ml_service.py` — ML classifier**

> "The ML model uses GradientBoosting with 7 features engineered from the drug names. No external drug database needed — everything is computed from the name string itself plus a known interactions lookup. The model trains on startup if no saved model exists."

**File 3: `ingestion/feature_consumer.py` — Kafka pipeline**

> "This is the Kafka consumer. It reads raw drug events from OpenFDA and PubMed, engineers 8 features including NLP keyword scanning for severity signals, and publishes to the processed_features topic. The ML inference consumer then picks those up and pre-computes predictions into Redis."

---

## Expected Interview Questions

### On ML

**Q: Why GradientBoosting instead of a real drug database?**

> "For a portfolio project, I wanted to demonstrate ML engineering skills — feature engineering, model training, serialization, async loading. A lookup table would show no ML knowledge. GradientBoosting also shows I understand ensemble methods and can explain trade-offs. In production, I'd integrate DrugBank or RxNav for authoritative interaction data and use the ML model for novel pairs."

**Q: Your training data is synthetic — isn't that a problem?**

> "Yes, this is a tutorial-level limitation, not a production system. The known interactions dictionary seeds realistic training labels. In production, I'd train on FDA adverse event reports, PubMed clinical studies, and DrugBank interaction data — all available via API. The architecture is identical; only the training data changes."

**Q: What accuracy does your model achieve?**

> "On the synthetic test set, ~85%. On real known interactions — the 40 seeded pairs — it achieves 100% because those pairs are in training. I'm transparent that this isn't a clinically validated model. The value is in the system architecture, not the model accuracy."

---

### On RAG

**Q: Why ChromaDB over Pinecone or Qdrant?**

> "ChromaDB is embedded — no separate service, no API key, no cost. For a portfolio project running in Docker, it's the right choice. Pinecone would add an external dependency and cost. If I were scaling this to production with millions of documents, I'd move to Qdrant (open source, self-hosted, more performant) or Pinecone for managed cloud."

**Q: What happens if ChromaDB has no relevant documents?**

> "The RAG service returns an empty list. The LLM still generates an explanation — it just uses general pharmacological knowledge from its training instead of the retrieved context. The prompt tells it explicitly to use general knowledge if context is empty."

---

### On Kafka

**Q: Why Kafka for this project? Isn't it overkill?**

> "You're right that for the core analysis, Kafka is not needed. The analysis pipeline — ML + RAG + LLM — runs entirely within the FastAPI request. Kafka handles the background data ingestion pipeline: continuously pulling new adverse events from OpenFDA and PubMed, engineering features, and pre-computing predictions into Redis. This separates data ingestion from request serving — a standard pattern in production ML systems."

**Q: What is KRaft mode?**

> "KRaft mode removes Zookeeper from Kafka. Before Kafka 3.3, you needed a separate Zookeeper cluster to manage Kafka metadata. KRaft moves metadata management into Kafka itself. Simpler deployment, fewer containers, lower operational complexity."

---

### On System Design

**Q: What would fail first if traffic increased 100x?**

> "The backend. A single Uvicorn worker handles one request at a time. With 100x traffic, the LLM streaming would queue up and timeouts would spike. Fix: multiple Uvicorn workers, then move to Kubernetes with horizontal pod autoscaling. Second bottleneck: ChromaDB — a local embedded DB doesn't scale horizontally. Fix: Qdrant cluster or Pinecone."

**Q: How would you add authentication?**

> "JWT tokens via FastAPI's dependency injection. Add `Depends(verify_token)` to each route. Store user sessions in Redis. For a healthcare application I'd use OAuth2 with a proper identity provider — Auth0 or AWS Cognito."

---

## Demo Tips

- **Always demo the contraindicated pair first** — it has the highest visual impact (⚫ black badge)
- **Show the cache demo** — the speed difference is immediately impressive
- **Have Grafana open with the dashboard** — metrics moving in real time during demo is very impressive
- **If Groq API is slow**, explain: *"Groq is free tier — in production we'd use a paid plan or a self-hosted LLM like vLLM"*
- **If asked about medical accuracy**, always say: *"This is a portfolio demonstration, not a clinical tool — it would need FDA-approved drug interaction data and clinical validation before any real use"*
