import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, CheckConstraint, Enum, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.enums import DriftStatusEnum
from app.db.session import Base


class DriftRun(Base):
    __tablename__ = "drift_runs"

    __table_args__ = (
        UniqueConstraint("run_fingerprint", name="uq_drift_runs_fingerprint"),
        CheckConstraint("run_fingerprint ~ '^[a-f0-9]{64}$'", name="chk_drift_runs_fingerprint"),
        CheckConstraint(
            "output_sha256 IS NULL OR output_sha256 ~ '^[a-f0-9]{64}$'",
            name="chk_drift_runs_output_sha256",
        ),
        Index("idx_drift_runs_scene", "scene_id"),
        Index("idx_drift_runs_vessel", "vessel_id"),
        Index("idx_drift_runs_fingerprint", "run_fingerprint", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    scene_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vessel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vessels.id", ondelete="RESTRICT"),
        nullable=False,
    )
    spill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spills.id", ondelete="SET NULL"),
        nullable=True,
    )
    simulation_version: Mapped[str] = mapped_column(Text, nullable=False)
    model_parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    run_fingerprint: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    status: Mapped[DriftStatusEnum] = mapped_column(
        Enum(DriftStatusEnum, name="drift_status_enum", native_enum=True),
        nullable=False,
        server_default=DriftStatusEnum.queued.value,
    )
    output_storage_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_sha256: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    result_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    scene = relationship("Scene", back_populates="drift_runs")
    vessel = relationship("Vessel", back_populates="drift_runs")
    spill = relationship("Spill", back_populates="drift_runs")
    attribution_scores = relationship("AttributionScore", back_populates="drift_run")
    cpa_events = relationship("CpaEvent", back_populates="drift_run")
