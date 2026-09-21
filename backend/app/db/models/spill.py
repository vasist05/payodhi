import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.enums import SpillStatusEnum
from app.db.session import Base


class Spill(Base):
    __tablename__ = "spills"

    __table_args__ = (
        CheckConstraint("area_sq_km > 0", name="chk_spills_area_sq_km"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="chk_spills_confidence_score"),
        Index("idx_spills_scene", "scene_id"),
        Index("idx_spills_polygon", "spill_polygon", postgresql_using="gist"),
        Index("idx_spills_status", "status"),
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
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    spill_polygon: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326),
        nullable=False,
    )
    area_sq_km: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    detection_model_name: Mapped[str] = mapped_column(Text, nullable=False)
    detection_model_version: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    processing_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[SpillStatusEnum] = mapped_column(
        Enum(SpillStatusEnum, name="spill_status_enum", native_enum=True),
        nullable=False,
        server_default=SpillStatusEnum.detected.value,
    )
    reviewed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    scene = relationship("Scene", back_populates="spills")
    drift_runs = relationship("DriftRun", back_populates="spill")
    dossiers = relationship("Dossier", back_populates="spill")
