"""
PubMed Kafka Producer

Fetches scientific abstracts from PubMed NCBI E-utilities API
and publishes them to the 'raw_drug_events' Kafka topic.

Uses rotating drug pair queries to collect 3,000+ abstracts.
"""

import asyncio
import json
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from itertools import cycle

import httpx
from aiokafka import AIOKafkaProducer
from loguru import logger

KAFKA_BOOTSTRAP = "kafka:9092"
TOPIC = "raw_drug_events"
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
POLL_INTERVAL = 30  # seconds between queries

DRUG_QUERIES = [
    "drug interaction warfarin aspirin",
    "drug interaction metformin lisinopril",
    "drug interaction statin clarithromycin",
    "drug interaction SSRI MAOI serotonin syndrome",
    "drug interaction anticoagulant NSAID bleeding",
    "drug interaction digoxin amiodarone toxicity",
    "drug interaction sildenafil nitrate hypotension",
    "drug interaction ACE inhibitor potassium hyperkalemia",
    "drug interaction clopidogrel PPI efficacy",
    "drug interaction fluoroquinolone QT prolongation",
    "pharmacokinetic drug drug interaction CYP450",
    "adverse drug reaction combination therapy elderly",
]


async def search_pubmed(query: str, client: httpx.AsyncClient, max_results: int = 5) -> list:
    """Search PubMed and fetch abstracts for a drug interaction query."""
    results = []

    try:
        # Step 1: esearch — get PMIDs
        search_url = f"{PUBMED_BASE}/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }

        search_resp = await client.get(search_url, params=search_params, timeout=15.0)
        search_resp.raise_for_status()
        search_data = search_resp.json()

        pmids = search_data.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        # Step 2: efetch — get abstracts
        fetch_url = f"{PUBMED_BASE}/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "abstract",
            "retmode": "xml",
        }

        fetch_resp = await client.get(fetch_url, params=fetch_params, timeout=20.0)
        fetch_resp.raise_for_status()

        # Parse XML response
        root = ET.fromstring(fetch_resp.text)

        for article in root.findall(".//PubmedArticle"):
            try:
                pmid_el = article.find(".//PMID")
                title_el = article.find(".//ArticleTitle")
                abstract_el = article.find(".//AbstractText")

                pmid = pmid_el.text if pmid_el is not None else ""
                title = title_el.text if title_el is not None else ""
                abstract = abstract_el.text if abstract_el is not None else ""

                if not abstract:
                    continue

                event = {
                    "event_id": str(uuid.uuid4()),
                    "source": "pubmed",
                    "pmid": pmid,
                    "title": title,
                    "abstract": abstract[:1000],  # Truncate for Kafka
                    "query": query,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                results.append(event)

            except Exception as e:
                logger.debug(f"Error parsing PubMed article: {e}")

        return results

    except Exception as e:
        logger.warning(f"PubMed search failed for '{query}': {e}")
        return []


async def run_producer():
    """Main producer loop - fetches PubMed abstracts and publishes to Kafka."""
    logger.info("🚀 Starting PubMed Kafka Producer...")

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        compression_type="gzip",
        acks="all",
    )

    await producer.start()
    logger.info(f"✅ PubMed producer connected. Publishing to: {TOPIC}")

    async with httpx.AsyncClient() as http_client:
        query_cycle = cycle(DRUG_QUERIES)
        total_published = 0

        while True:
            query = next(query_cycle)
            logger.info(f"Searching PubMed: '{query}'")

            abstracts = await search_pubmed(query, http_client, max_results=5)

            for abstract in abstracts:
                await producer.send(
                    TOPIC,
                    value=abstract,
                    key=f"pubmed:{abstract['pmid']}".encode("utf-8"),
                )
                total_published += 1

            if abstracts:
                logger.info(
                    f"Published {len(abstracts)} PubMed abstracts | "
                    f"Total: {total_published}"
                )

            await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_producer())
