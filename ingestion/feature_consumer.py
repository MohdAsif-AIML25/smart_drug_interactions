"""
Feature Engineering Kafka Consumer

Reads raw_drug_events -> engineers features -> publishes to processed_features.

Features Computed:
  - severity signals from reaction terms
  - source reliability weight
  - drug pair normalized identifiers
  - seriousness flag
"""

import asyncio
import hashlib
import json
import re
from datetime import datetime

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from loguru import logger

KAFKA_BOOTSTRAP = "kafka:9092"
INPUT_TOPIC = "raw_drug_events"
OUTPUT_TOPIC = "processed_features"
CONSUMER_GROUP = "feature-engineering-group"

# Severity signal keywords — 5-class schema matching ml_service.py + schemas.py
# Classes: none / mild / moderate / severe / contraindicated
SEVERITY_KEYWORDS = {
    "contraindicated": ["contraindicated", "never combine", "absolutely avoid", "fatal", "lethal", "cardiac arrest", "anaphylaxis", "coma"],
    "severe": ["death", "hospitalization", "serious", "bleeding", "hemorrhage", "thrombosis", "seizure", "stroke", "rhabdomyolysis", "dangerous"],
    "moderate": ["rash", "nausea", "dizziness", "elevated", "reduced efficacy", "interaction", "caution", "monitor"],
    "mild": ["mild", "slight", "minimal", "temporary", "manageable", "minor"],
    "none": ["no interaction", "safe", "beneficial", "no significant interaction"],
}


def compute_severity_signal(text: str) -> dict:
    """
    Score severity level from text keywords.
    Returns normalized signal per class: none / mild / moderate / severe / contraindicated
    """
    text_lower = text.lower()
    scores = {level: 0 for level in SEVERITY_KEYWORDS}
    for level, keywords in SEVERITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[level] += 1
    total = sum(scores.values()) or 1
    return {level: count / total for level, count in scores.items()}


def normalize_name(name: str) -> str:
    """Lowercase, strip non-alphanumeric characters."""
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())


def extract_drug_names(event: dict) -> tuple:
    """
    Extract drug_a and drug_b regardless of event source.

    OpenFDA events have explicit drug_a / drug_b fields.
    PubMed events use the query string (e.g. 'drug interaction warfarin aspirin').
    """
    source = event.get("source", "unknown")

    if source == "openfda":
        return event.get("drug_a", ""), event.get("drug_b", "")

    if source == "pubmed":
        query = event.get("query", "")
        stop_words = {
            "drug", "interaction", "and", "with", "pharmacokinetic",
            "adverse", "reaction", "combination", "therapy", "elderly",
            "between", "the", "for", "using", "via", "after",
        }
        tokens = [
            t for t in query.lower().split()
            if t not in stop_words and len(t) > 2
        ]
        drug_a = tokens[0] if len(tokens) > 0 else ""
        drug_b = tokens[1] if len(tokens) > 1 else ""
        return drug_a, drug_b

    return event.get("drug_a", ""), event.get("drug_b", "")


def compute_features(event: dict) -> dict:
    """
    Transform a raw Kafka drug event into an ML-ready feature dict.

    Handles both OpenFDA and PubMed event formats.
    """
    source = event.get("source", "unknown")
    drug_a, drug_b = extract_drug_names(event)

    # Combine all available text
    text_parts = [
        event.get("abstract", ""),
        event.get("raw", ""),
        " ".join(event.get("reactions", [])),
        str(event.get("outcomes", "")),
    ]
    text = " ".join(filter(None, text_parts))

    severity_signals = compute_severity_signal(text)
    source_weight = {"pubmed": 0.9, "openfda": 0.85}.get(source, 0.5)
    is_serious = int(event.get("serious", 0)) > 0

    drug_a_norm = normalize_name(drug_a)
    drug_b_norm = normalize_name(drug_b)

    # Sort for order-independent hash (warfarin+aspirin == aspirin+warfarin)
    pair_key = "_".join(sorted([drug_a_norm, drug_b_norm]))
    pair_hash = hashlib.md5(pair_key.encode()).hexdigest()

    return {
        "event_id": event.get("event_id", ""),
        "drug_a": drug_a_norm,
        "drug_b": drug_b_norm,
        "pair_hash": pair_hash,
        "source": source,
        "source_weight": source_weight,
        "is_serious": is_serious,
        "severity_signals": severity_signals,
        "text_length": len(text),
        "has_abstract": bool(event.get("abstract")),
        "processed_at": datetime.utcnow().isoformat(),
    }


async def run_consumer():
    """
    Feature engineering consumer loop.
    Reads raw_drug_events, engineers features, publishes to processed_features.
    """
    logger.info("Starting Feature Engineering Consumer...")

    consumer = AIOKafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        compression_type="gzip",
    )

    await consumer.start()
    await producer.start()
    logger.info(f"Feature consumer ready: {INPUT_TOPIC} -> {OUTPUT_TOPIC}")

    processed = 0
    try:
        async for msg in consumer:
            try:
                raw_event = msg.value
                features = compute_features(raw_event)

                await producer.send(
                    OUTPUT_TOPIC,
                    value=features,
                    key=features["pair_hash"].encode("utf-8"),
                )

                processed += 1
                if processed % 100 == 0:
                    logger.info(f"Feature engineering: {processed} events processed")

            except Exception as e:
                logger.error(f"Feature engineering failed for message: {e}")

    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(run_consumer())
