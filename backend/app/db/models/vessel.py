import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CHAR, CheckConstraint, Enum, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.enums import VesselTypeEnum
from app.db.session import Base


class Vessel(Base):
    __tablename__ = "vessels"

    __table_args__ = (
        CheckConstraint("mmsi IS NULL OR mmsi ~ '^[0-9]{9}$'", name="chk_vessels_mmsi_format"),
        CheckConstraint("imo IS NULL OR imo ~ '^[0-9]{7}$'", name="chk_vessels_imo_format"),
        CheckConstraint("deadweight_tonnage IS NULL OR deadweight_tonnage > 0", name="chk_vessels_deadweight_tonnage"),
        Index("idx_vessels_mmsi", "mmsi", unique=True, postgresql_where=text("mmsi IS NOT NULL")),
        Index("idx_vessels_imo", "imo", unique=True, postgresql_where=text("imo IS NOT NULL")),
        Index("idx_vessels_type", "vessel_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    mmsi: Mapped[str | None] = mapped_column(Text, nullable=True)
    imo: Mapped[str | None] = mapped_column(Text, nullable=True)
    vessel_name: Mapped[str] = mapped_column(Text, nullable=False)
    vessel_type: Mapped[VesselTypeEnum] = mapped_column(
        Enum(VesselTypeEnum, name="vessel_type_enum", native_enum=True),
        nullable=False,
        server_default=VesselTypeEnum.unknown.value,
    )
    flag_country_code: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    deadweight_tonnage: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
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
    tracks = relationship("Track", back_populates="vessel")
    ais_gaps = relationship("AisGap", back_populates="vessel")
    drift_runs = relationship("DriftRun", back_populates="vessel")
    cpa_events = relationship("CpaEvent", back_populates="vessel")
