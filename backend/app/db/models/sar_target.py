from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from app.db.session import Base


class SarTarget(Base):
    __tablename__ = "sar_targets"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="chk_sar_targets_confidence"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    scene_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="RESTRICT"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    position: Mapped[Any] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    intensity: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    patch_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)

    correlation: Mapped[Optional["TargetCorrelation"]] = relationship("TargetCorrelation", back_populates="sar_target", uselist=False)
