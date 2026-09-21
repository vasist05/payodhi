import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import CHAR, CheckConstraint, Enum, Index, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.enums import SceneStatusEnum
from app.db.session import Base


class Scene(Base):
    __tablename__ = "scenes"

    __table_args__ = (
        UniqueConstraint("source_provider", "external_scene_id", name="uq_scenes_provider_external"),
        CheckConstraint(
            "cloud_cover_percentage IS NULL OR (cloud_cover_percentage >= 0 AND cloud_cover_percentage <= 100)",
            name="chk_scenes_cloud_cover",
        ),
        CheckConstraint("wind_speed IS NULL OR wind_speed >= 0", name="chk_scenes_wind_speed"),
        CheckConstraint(
            "wind_direction IS NULL OR (wind_direction >= 0 AND wind_direction <= 360)",
            name="chk_scenes_wind_direction",
        ),
        CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name="chk_scenes_sha256"),
        Index("idx_scenes_footprint", "footprint", postgresql_using="gist"),
        Index("idx_scenes_captured_at", "captured_at"),
        Index("idx_scenes_provider_external", "source_provider", "external_scene_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_provider: Mapped[str] = mapped_column(Text, nullable=False)
    external_scene_id: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    footprint: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326),
        nullable=False,
    )
    cloud_cover_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    wind_speed: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    wind_direction: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    processing_status: Mapped[SceneStatusEnum] = mapped_column(
        Enum(SceneStatusEnum, name="scene_status_enum", native_enum=True),
        nullable=False,
        server_default=SceneStatusEnum.pending.value,
    )
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
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
    spills = relationship("Spill", back_populates="scene")
    drift_runs = relationship("DriftRun", back_populates="scene")
    dossiers = relationship("Dossier", back_populates="scene")
