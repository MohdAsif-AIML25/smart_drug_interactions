FROM python:3.11.1-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# CMD is set per-service in docker-compose.yml
# Available scripts:
#   python openfda_producer.py
#   python pubmed_producer.py
#   python feature_consumer.py
#   python ml_consumer.py