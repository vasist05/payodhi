import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AisGap(Base):
    __tablename__ = "ais_gaps"

    __table_args__ = (
        CheckConstraint("gap_end > gap_start", name="chk_ais_gaps_time_order"),
        CheckConstraint("gap_duration_min > 0", name="chk_ais_gaps_duration"),
        Index("idx_ais_gaps_vessel", "vessel_id"),
        Index("idx_ais_gaps_time", "gap_start", "gap_end"),
        Index("idx_ais_gaps_center", "gap_center", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    vessel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vessels.id", ondelete="RESTRICT"),
        nullable=False,
    )
    gap_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    gap_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    gap_duration_min: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    last_position: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    next_position: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    gap_center: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    distance_from_coast_nm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    is_open_water: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    vessel = relationship("Vessel", back_populates="ais_gaps")
