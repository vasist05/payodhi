import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VesselStaticHistory(Base):
    __tablename__ = "vessel_static_history"

    __table_args__ = (
        CheckConstraint("draft_meters IS NULL OR draft_meters >= 0", name="chk_vessel_static_history_draft"),
        Index("idx_vessel_static_history_vessel_time", "vessel_id", text("recorded_at DESC")),
        Index("idx_vessel_static_history_recorded_at", "recorded_at"),
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
        nullable=False,
    )
    draft_meters: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    eta: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    dimension_length: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    dimension_beam: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    vessel = relationship("Vessel", back_populates="static_history")
