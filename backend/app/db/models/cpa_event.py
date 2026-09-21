import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CpaEvent(Base):
    __tablename__ = "cpa_events"

    __table_args__ = (
        CheckConstraint("min_distance_m >= 0", name="chk_cpa_min_distance"),
        Index("idx_cpa_drift_run", "drift_run_id"),
        Index("idx_cpa_vessel", "vessel_id"),
        Index("idx_cpa_vessel_position", "vessel_position_at_cpa", postgresql_using="gist"),
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
    vessel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vessels.id", ondelete="RESTRICT"),
        nullable=False,
    )
    min_distance_m: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cpa_timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    tcpa_seconds: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vessel_position_at_cpa: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    slick_position_at_cpa: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    drift_run = relationship("DriftRun", back_populates="cpa_events")
    vessel = relationship("Vessel", back_populates="cpa_events")
