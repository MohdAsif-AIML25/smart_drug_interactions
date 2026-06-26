"""
ML Inference Kafka Consumer

Reads processed_features → runs ML model → stores predictions to Redis + PostgreSQL.

This enables:
  - Pre-computed severity scores for common drug pairs
  - Faster response times for frequent queries
  - Historical analysis for monitoring dashboards
"""

import asyncio
import json
from datetime import datetime

import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer
from loguru import logger

KAFKA_BOOTSTRAP = "kafka:9092"
INPUT_TOPIC = "processed_features"
CONSUMER_GROUP = "ml-inference-group"
REDIS_URL = "redis://redis:6379/0"


def predict_severity_from_features(features: dict) -> dict:
    """
    Rule-based ML inference from engineered features.
    Uses the same 5-class schema as ml_service.py and schemas.py:
      none / mild / moderate / severe / contraindicated

    Args:
        features: Feature dict from feature_consumer.py

    Returns:
        Prediction dict with severity and confidence
    """
    signals = features.get("severity_signals", {})
    is_serious = features.get("is_serious", False)
    source_weight = features.get("source_weight", 0.5)

    # Determine severity from signals — 5-class schema
    if signals.get("contraindicated", 0) > 0.3 or (is_serious and signals.get("severe", 0) > 0.2):
        severity = "contraindicated"
        confidence = min(0.70 + signals.get("contraindicated", 0), 0.97)
    elif signals.get("severe", 0) > 0.3 or is_serious:
        severity = "severe"
        confidence = min(0.65 + signals.get("severe", 0), 0.92)
    elif signals.get("moderate", 0) > 0.2:
        severity = "moderate"
        confidence = min(0.60 + signals.get("moderate", 0), 0.87)
    elif signals.get("mild", 0) > 0.2:
        severity = "mild"
        confidence = min(0.55 + signals.get("mild", 0), 0.83)
    else:
        severity = "none"
        confidence = 0.80

    # Adjust confidence by source reliability weight
    confidence = round(confidence * source_weight, 3)

    return {
        "drug_a": features.get("drug_a", ""),
        "drug_b": features.get("drug_b", ""),
        "severity": severity,
        "confidence": confidence,
        "pair_hash": features.get("pair_hash", ""),
        "source": features.get("source", ""),
        "predicted_at": datetime.utcnow().isoformat(),
    }


async def run_consumer():
    """
    ML inference consumer loop.
    Reads processed features and stores predictions to Redis.
    """
    logger.info("🚀 Starting ML Inference Consumer...")

    consumer = AIOKafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

    await consumer.start()
    logger.info(f"✅ ML inference consumer ready on: {INPUT_TOPIC}")

    inferred = 0

    try:
        async for msg in consumer:
            try:
                features = msg.value
                prediction = predict_severity_from_features(features)

                # Store in Redis with 24-hour TTL
                cache_key = f"prediction:{prediction['pair_hash']}"
                await redis_client.setex(
                    cache_key,
                    86400,
                    json.dumps(prediction),
                )

                inferred += 1
                if inferred % 50 == 0:
                    logger.info(f"ML inference: {inferred} predictions cached")

            except Exception as e:
                logger.error(f"ML inference failed: {e}")

    finally:
        await consumer.stop()
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(run_consumer())
