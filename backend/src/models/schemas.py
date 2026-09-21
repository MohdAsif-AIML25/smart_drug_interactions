"""
Pydantic v2 Models
Request/Response schemas for the Drug Interaction API.
"""

from datetime import datetime
from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    NONE = "none"                        # green
    MILD = "mild"                        # yellow
    MODERATE = "moderate"                # orange
    SEVERE = "severe"                    # red
    CONTRAINDICATED = "contraindicated"  # black
    UNKNOWN = "unknown"                  # gray


# ─── Request Models ───────────────────────────────────────────────

class AnalyseRequest(BaseModel):
    drug_a: str = Field(..., min_length=1, max_length=200, examples=["Warfarin"])
    drug_b: str = Field(..., min_length=1, max_length=200, examples=["Aspirin"])


# ─── Response Models ──────────────────────────────────────────────

class MLPrediction(BaseModel):
    severity: SeverityLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    probabilities: dict[str, float]


class DrugSource(BaseModel):
    title: str
    source: str  # "pubmed" | "openfda"
    url: Optional[str] = None
    snippet: str


class AnalysisResult(BaseModel):
    drug_a: str
    drug_b: str
    severity: SeverityLevel
    confidence: float
    explanation: str
    sources: List[DrugSource]
    created_at: datetime


class HistoryItem(BaseModel):
    id: str
    drug_a: str
    drug_b: str
    severity: SeverityLevel
    confidence: float
    explanation: Optional[str] = None
    created_at: datetime


class DrugSuggestion(BaseModel):
    name: str
    rxcui: Optional[str] = None
    generic_name: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime


# ─── SSE Event Payloads ────────────────────────────────────────────

class SeverityEvent(BaseModel):
    severity: SeverityLevel
    confidence: float
    probabilities: dict[str, float]


class SourcesEvent(BaseModel):
    sources: list[DrugSource]


class TokenEvent(BaseModel):
    token: str


class CompleteEvent(BaseModel):
    drug_a: str
    drug_b: str
    severity: SeverityLevel
    full_explanation: str


class ErrorEvent(BaseModel):
    message: str
    code: str
