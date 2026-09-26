from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Enum as SAEnum, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from app.db.models.enums import MatchStatusEnum
from app.db.session import Base


class TargetCorrelation(Base):
    __tablename__ = "target_correlations"
    __table_args__ = (
        CheckConstraint(
            "(match_status = 'dark_vessel' AND vessel_id IS NULL) OR "
            "(match_status = 'matched' AND vessel_id IS NOT NULL) OR "
            "(match_status = 'borderline')",
            name="chk_target_correlations_status_vessel",
        ),
        UniqueConstraint("sar_target_id", name="uq_target_correlations_sar_target"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    sar_target_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sar_targets.id", ondelete="RESTRICT"), nullable=False)
    vessel_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("vessels.id", ondelete="SET NULL"), nullable=True)
    match_status: Mapped[MatchStatusEnum] = mapped_column(
        SAEnum(MatchStatusEnum, name="match_status_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    haversine_distance_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    anomaly_flags: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)

    sar_target: Mapped["SarTarget"] = relationship("SarTarget", back_populates="correlation")
    vessel: Mapped[Optional["Vessel"]] = relationship("Vessel", viewonly=True)
