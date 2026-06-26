"""
Drug Service — Autocomplete and Drug Information

Integrates with:
  - OpenFDA API for drug labels
  - RxNorm API for standardized drug names
  - Local cache for performance

Features:
  - Async HTTP with httpx
  - Retry logic with tenacity
  - Response caching with Redis
"""

import json
from typing import List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.core.logger import logger
from src.core.redis_client import get_redis
from src.models.schemas import DrugSuggestion


# Curated list of common drugs for fast autocomplete
COMMON_DRUGS = [
    # Anticoagulants and Antiplatelets
    "Warfarin", "Aspirin", "Clopidogrel", "Heparin", "Enoxaparin",
    "Rivaroxaban", "Apixaban", "Dabigatran",

    # NSAIDs and Analgesics
    "Ibuprofen", "Paracetamol", "Acetaminophen", "Tramadol",
    "Diclofenac", "Naproxen", "Oxycodone", "Morphine", "Codeine",

    # Antibiotics
    "Amoxicillin", "Clarithromycin", "Azithromycin",
    "Ciprofloxacin", "Doxycycline", "Trimethoprim",
    "Vancomycin", "Metronidazole",

    # Cardiovascular
    "Metoprolol", "Atorvastatin", "Simvastatin",
    "Amlodipine", "Lisinopril", "Losartan",
    "Valsartan", "Digoxin", "Amiodarone",
    "Verapamil", "Nitroglycerin", "Furosemide",
    "Hydrochlorothiazide", "Spironolactone",
    "Propranolol",

    # Diabetes
    "Metformin", "Insulin", "Glipizide", "Sitagliptin",

    # Psychiatric / Neurological
    "Sertraline", "Fluoxetine", "Escitalopram",
    "Lithium", "Alprazolam", "Diazepam",
    "Gabapentin", "Pregabalin", "Ondansetron",

    # GI
    "Omeprazole", "Pantoprazole",
    "Esomeprazole", "Domperidone",

    # Endocrine
    "Levothyroxine", "Prednisone", "Dexamethasone",

    # Antifungals
    "Ketoconazole", "Fluconazole",

    # Muscle Relaxants
    "Tizanidine", "Baclofen",

    # Allergy
    "Cetirizine", "Levocetirizine",
    "Montelukast", "Loratadine",

    # Sildenafil Group
    "Sildenafil", "Tadalafil",

    # Supplements
    "Vitamin D", "Calcium Carbonate", "Folic Acid",

    # Chemotherapy
    "Methotrexate", "Tamoxifen", "Paclitaxel",
]


class DrugService:
    """
    Drug information and autocomplete service.

    Data Sources:
      1. Local curated list
      2. RxNorm API (real-time)
      3. OpenFDA API (real-time)
      4. Redis cache
    """

    def __init__(self):
        self.http_client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """
        Reusable async HTTP client.
        """
        if not self.http_client or self.http_client.is_closed:
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                headers={
                    "User-Agent": "SmartDrugInteractionPlatform/1.0"
                },
            )

        return self.http_client

    async def search_drugs(
        self,
        query: str,
        limit: int = 10
    ) -> List[DrugSuggestion]:
        """
        Drug autocomplete search.

        Priority:
          1. Redis cache
          2. Local curated list
          3. RxNorm API
          4. OpenFDA API
        """

        if len(query.strip()) < 2:
            return []

        cache_key = f"drug_search:{query.lower()}"
        redis = get_redis()

        # Cache lookup
        if redis:
            try:
                cached = await redis.get(cache_key)

                if cached:
                    data = json.loads(cached)

                    return [
                        DrugSuggestion(**item)
                        for item in data
                    ]

            except Exception as e:
                logger.debug(f"Redis cache read failed: {e}")

        # Local matches
        q_lower = query.lower()

        local_matches = [
            DrugSuggestion(name=drug)
            for drug in COMMON_DRUGS
            if q_lower in drug.lower()
        ]

        # Real-time API calls
        rxnorm_results = await self._search_rxnorm(
            query,
            limit
        )

        openfda_results = await self._search_openfda(
            query,
            limit
        )

        # Merge and deduplicate
        combined = []
        seen = set()

        for item in (
            local_matches +
            rxnorm_results +
            openfda_results
        ):
            name = item.name.strip().lower()

            if name not in seen:
                seen.add(name)
                combined.append(item)

        combined = combined[:limit]

        await self._cache_results(
            cache_key,
            combined,
            redis
        )

        return combined

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=3
        )
    )
    async def _search_rxnorm(
        self,
        query: str,
        limit: int = 10
    ) -> List[DrugSuggestion]:
        """
        Real-time RxNorm search.
        """

        try:
            client = await self.get_client()

            url = (
                "https://rxnav.nlm.nih.gov/REST/"
                f"spellingsuggestions.json?name={query}"
            )

            response = await client.get(url)

            response.raise_for_status()

            data = response.json()

            suggestions = (
                data.get("suggestionGroup", {})
                .get("suggestionList", {})
                .get("suggestion", [])
            )

            return [
                DrugSuggestion(name=name.title())
                for name in suggestions[:limit]
            ]

        except Exception as e:
            logger.debug(
                f"RxNorm search failed for '{query}': {e}"
            )
            return []

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=3
        )
    )
    async def _search_openfda(
        self,
        query: str,
        limit: int = 10
    ) -> List[DrugSuggestion]:
        """
        Real-time OpenFDA search.
        """

        try:
            client = await self.get_client()

            url = (
                f"{settings.OPENFDA_BASE_URL}/label.json"
                f"?search=openfda.brand_name:{query}*"
                f"&limit={limit}"
            )

            response = await client.get(url)

            response.raise_for_status()

            data = response.json()

            suggestions = []
            seen = set()

            for item in data.get("results", []):

                brand_names = (
                    item.get("openfda", {})
                    .get("brand_name", [])
                )

                for brand in brand_names:

                    key = brand.lower()

                    if key not in seen:
                        seen.add(key)

                        suggestions.append(
                            DrugSuggestion(
                                name=brand
                            )
                        )

            return suggestions[:limit]

        except Exception as e:
            logger.debug(
                f"OpenFDA search failed for '{query}': {e}"
            )
            return []

    async def _cache_results(
        self,
        key: str,
        results: List[DrugSuggestion],
        redis
    ) -> None:
        """
        Cache search results for 1 hour.
        """

        if not redis or not results:
            return

        try:
            data = [
                item.model_dump()
                for item in results
            ]

            await redis.setex(
                key,
                3600,
                json.dumps(data)
            )

        except Exception as e:
            logger.debug(
                f"Redis cache write failed: {e}"
            )

    async def close(self):
        """
        Close HTTP client.
        """

        if (
            self.http_client
            and not self.http_client.is_closed
        ):
            await self.http_client.aclose()


# Singleton instance
drug_service = DrugService()