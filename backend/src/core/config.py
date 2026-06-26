"""
Application Configuration
Loads settings from .env with validation.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =====================================================
    # APP
    # =====================================================

    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = True

    # =====================================================
    # CORS
    # =====================================================

    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:3002",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3002",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            import json
            try:
                return json.loads(value)
            except Exception:
                return [value]
        return value

    # =====================================================
    # GROQ
    # =====================================================

    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # =====================================================
    # DATABASE
    # =====================================================

    DATABASE_URL: str

    # =====================================================
    # REDIS
    # =====================================================

    REDIS_URL: str

    # =====================================================
    # KAFKA
    # =====================================================

    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"

    # =====================================================
    # CHROMADB
    # =====================================================

    CHROMA_DB_PATH: str = "./chroma_data"

    # =====================================================
    # OPENFDA
    # =====================================================

    OPENFDA_BASE_URL: str = "https://api.fda.gov/drug"

    # =====================================================
    # PUBMED
    # =====================================================

    PUBMED_BASE_URL: str = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    )

    # =====================================================
    # ML
    # =====================================================

    ML_MODEL_PATH: str = "./models/drug_interaction_model.pkl"

    ML_TIMEOUT_SECONDS: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
