import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.enums import VerdictEnum
from app.db.session import Base


class AttributionScore(Base):
    __tablename__ = "attribution_scores"

    __table_args__ = (
        UniqueConstraint("drift_run_id", "scoring_version", name="uq_attribution_run_version"),
        CheckConstraint("cpa_score >= 0 AND cpa_score <= 1", name="chk_attribution_cpa_score"),
        CheckConstraint("dark_vessel_score >= 0 AND dark_vessel_score <= 1", name="chk_attribution_dark_vessel_score"),
        CheckConstraint("loitering_score >= 0 AND loitering_score <= 1", name="chk_attribution_loitering_score"),
        CheckConstraint("capacity_multiplier = 0 OR capacity_multiplier = 1", name="chk_attribution_capacity_multiplier"),
        CheckConstraint("draft_change_score >= 0 AND draft_change_score <= 1", name="chk_attribution_draft_change_score"),
        CheckConstraint("permutation_p_value >= 0 AND permutation_p_value <= 1", name="chk_attribution_p_value"),
        CheckConstraint("stability_index >= 0 AND stability_index <= 1", name="chk_attribution_stability_index"),
        CheckConstraint("total_score >= 0 AND total_score <= 100", name="chk_attribution_total_score"),
        Index("idx_attribution_run_version", "drift_run_id", "scoring_version", unique=True),
        Index("idx_attribution_verdict", "verdict"),
        Index("idx_attribution_total_score", "total_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    drift_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drift_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scoring_version: Mapped[str] = mapped_column(Text, nullable=False)
    cpa_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    dark_vessel_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    loitering_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    capacity_multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    draft_change_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    permutation_p_value: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    stability_index: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    total_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    verdict: Mapped[VerdictEnum] = mapped_column(
        Enum(VerdictEnum, name="verdict_enum", native_enum=True),
        nullable=False,
    )
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    drift_run = relationship("DriftRun", back_populates="attribution_scores")
