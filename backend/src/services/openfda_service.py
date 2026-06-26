"""
OpenFDA Service

Queries the FDA Adverse Event Reporting System (FAERS) API
to fetch real-time drug interaction adverse event data.

API Reference: https://open.fda.gov/apis/drug/event/
"""

from typing import List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.core.logger import logger
from src.models.schemas import DrugSource


class OpenFDAService:
    """
    Fetches real-time adverse event data from FDA FAERS.

    Returns DrugSource citations with reaction snippets
    for use in the RAG pipeline.
    """

    def __init__(self):
        self.base_url = settings.OPENFDA_BASE_URL
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if not self._client or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": "SmartDrugInteractionPlatform/1.0"},
            )
        return self._client

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
    )
    async def fetch_adverse_events(
        self,
        drug_a: str,
        drug_b: str,
        limit: int = 5,
    ) -> List[DrugSource]:
        """
        Query FAERS for adverse event reports co-involving both drugs.
        Returns real FDA-reported reaction data as DrugSource citations.
        """
        client = await self._get_client()

        search_query = (
            f"patient.drug.medicinalproduct:{drug_a.upper()}"
            f"+AND+patient.drug.medicinalproduct:{drug_b.upper()}"
        )

        try:
            response = await client.get(
                f"{self.base_url}/event.json",
                params={"search": search_query, "limit": limit},
            )
            response.raise_for_status()
            data = response.json()

            sources: List[DrugSource] = []
            for report in data.get("results", []):
                patient = report.get("patient", {})

                reactions = [
                    r.get("reactionmeddrapt", "")
                    for r in patient.get("reaction", [])
                    if r.get("reactionmeddrapt")
                ]

                serious = int(report.get("serious", 0))
                serious_label = "Serious" if serious == 1 else "Non-serious"

                outcomes = []
                if patient.get("patientdeath"):
                    outcomes.append("death")
                if report.get("seriousnesshospitalization") == "1":
                    outcomes.append("hospitalization")
                if report.get("seriousnesslifethreatening") == "1":
                    outcomes.append("life-threatening")

                outcome_str = ", ".join(outcomes) if outcomes else "adverse event"

                snippet = (
                    f"{serious_label} FDA adverse event report for "
                    f"{drug_a} + {drug_b}. "
                    f"Reactions: {', '.join(reactions[:5]) if reactions else 'not specified'}. "
                    f"Outcome: {outcome_str}."
                )

                sources.append(DrugSource(
                    title=f"FDA FAERS: {drug_a} + {drug_b}",
                    source="openfda",
                    url="https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers",
                    snippet=snippet,
                ))

            logger.info(f"OpenFDA: {len(sources)} adverse event reports for {drug_a}+{drug_b}")
            return sources

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"OpenFDA: no records for {drug_a}+{drug_b}")
                return []
            logger.warning(f"OpenFDA HTTP {e.response.status_code} for {drug_a}+{drug_b}")
            return []
        except Exception as e:
            logger.warning(f"OpenFDA fetch failed for {drug_a}+{drug_b}: {e}")
            return []

    async def get_drug_label(self, drug_name: str) -> Optional[str]:
        """
        Fetch FDA drug label warnings/interactions section.
        Used to enrich RAG context with official label text.
        """
        client = await self._get_client()
        try:
            response = await client.get(
                f"{self.base_url}/label.json",
                params={"search": f"openfda.generic_name:{drug_name}", "limit": 1},
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            if not results:
                return None

            label = results[0]
            parts = []
            if label.get("warnings"):
                parts.append(f"Warnings: {label['warnings'][0][:300]}")
            if label.get("drug_interactions"):
                parts.append(f"Interactions: {label['drug_interactions'][0][:300]}")
            return " | ".join(parts) if parts else None

        except Exception as e:
            logger.debug(f"Drug label fetch failed for {drug_name}: {e}")
            return None

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton
openfda_service = OpenFDAService()
