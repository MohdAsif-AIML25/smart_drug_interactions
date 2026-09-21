"""
SQLAlchemy ORM Models
Database table definitions for analysis history.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, Float, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class AnalysisHistory(Base):
    """Stores every drug interaction analysis result."""

    __tablename__ = "analysis_history"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    drug_a: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True
    )

    drug_b: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    sources_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<AnalysisHistory "
            f"{self.drug_a} + {self.drug_b} = {self.severity}>"
        )