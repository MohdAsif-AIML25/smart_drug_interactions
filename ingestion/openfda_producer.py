"""
OpenFDA Kafka Producer

Continuously polls the OpenFDA Drug API and publishes
raw drug interaction events to the 'raw_drug_events' Kafka topic.

Poll interval: 60 seconds
Target: 5,000+ drug-pair records
"""

import asyncio
import json
import time
import uuid
from datetime import datetime

import httpx
from aiokafka import AIOKafkaProducer
from loguru import logger

KAFKA_BOOTSTRAP = "kafka:9092"
TOPIC = "raw_drug_events"
OPENFDA_BASE = "https://api.fda.gov/drug"
POLL_INTERVAL = 60  # seconds

# Drug pairs to cycle through
DRUG_PAIRS = [
    ("warfarin", "aspirin"),
    ("metformin", "lisinopril"),
    ("atorvastatin", "clarithromycin"),
    ("digoxin", "amiodarone"),
    ("fluoxetine", "tramadol"),
    ("sildenafil", "nitroglycerine"),
    ("clopidogrel", "omeprazole"),
    ("ibuprofen", "heparin"),
    ("amlodipine", "simvastatin"),
    ("metoprolol", "verapamil"),
]


async def fetch_openfda_events(drug_a: str, drug_b: str, client: httpx.AsyncClient) -> list:
    """Fetch adverse event reports for a drug pair from OpenFDA."""
    url = f"{OPENFDA_BASE}/event.json"
    params = {
        "search": f"patient.drug.medicinalproduct:{drug_a}+AND+patient.drug.medicinalproduct:{drug_b}",
        "limit": 10,
    }

    try:
        response = await client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        events = []

        for r in results:
            event = {
                "event_id": str(uuid.uuid4()),
                "source": "openfda",
                "drug_a": drug_a,
                "drug_b": drug_b,
                "timestamp": datetime.utcnow().isoformat(),
                "serious": r.get("serious", 0),
                "outcomes": r.get("patient", {}).get("patientdeath", []),
                "reactions": [
                    reaction.get("reactionmeddrapt", "")
                    for reaction in r.get("patient", {}).get("reaction", [])
                ],
                "raw": json.dumps(r)[:500],  # Truncate for Kafka message size
            }
            events.append(event)

        return events

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            # No results found for this pair - that's okay
            return []
        logger.warning(f"OpenFDA HTTP error for {drug_a}+{drug_b}: {e}")
        return []
    except Exception as e:
        logger.warning(f"OpenFDA fetch failed for {drug_a}+{drug_b}: {e}")
        return []


async def run_producer():
    """Main producer loop - polls OpenFDA and publishes to Kafka."""
    logger.info("🚀 Starting OpenFDA Kafka Producer...")

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        compression_type="gzip",
        acks="all",
    )

    await producer.start()
    logger.info(f"✅ Kafka producer connected. Publishing to topic: {TOPIC}")

    async with httpx.AsyncClient() as http_client:
        pair_index = 0
        total_published = 0

        while True:
            drug_a, drug_b = DRUG_PAIRS[pair_index % len(DRUG_PAIRS)]
            logger.info(f"Polling OpenFDA for: {drug_a} + {drug_b}")

            events = await fetch_openfda_events(drug_a, drug_b, http_client)

            for event in events:
                await producer.send(
                    TOPIC,
                    value=event,
                    key=f"{drug_a}:{drug_b}".encode("utf-8"),
                )
                total_published += 1

            if events:
                logger.info(
                    f"Published {len(events)} events | Total: {total_published} | "
                    f"Pair: {drug_a}+{drug_b}"
                )

            pair_index += 1
            await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_producer())
