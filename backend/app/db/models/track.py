# NOTE: This table will become a TimescaleDB hypertable in the migration
# partitioned on 'recorded_at' with a chunk interval of 7 days:
# SELECT create_hypertable('tracks', 'recorded_at', chunk_time_interval => INTERVAL '7 days');

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Track(Base):
    __tablename__ = "tracks"

    __table_args__ = (
        UniqueConstraint("source", "source_record_id", "recorded_at", name="uq_tracks_source"),
        CheckConstraint("speed_knots >= 0 AND speed_knots <= 100", name="chk_tracks_speed_knots"),
        CheckConstraint("course_degrees >= 0 AND course_degrees <= 360", name="chk_tracks_course_degrees"),
        CheckConstraint(
            "heading_degrees IS NULL OR (heading_degrees >= 0 AND heading_degrees <= 360)",
            name="chk_tracks_heading_degrees",
        ),
        Index("idx_tracks_vessel_time", "vessel_id", text("recorded_at DESC")),
        Index("idx_tracks_position", "position", postgresql_using="gist"),
        Index("idx_tracks_recorded_at_brin", "recorded_at", postgresql_using="brin"),
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
    recorded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        primary_key=True,
    )
    position: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    speed_knots: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    course_degrees: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    heading_degrees: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    navigational_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    ingestion_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    vessel = relationship("Vessel", back_populates="tracks")
