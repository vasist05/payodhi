import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, CheckConstraint, Enum, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.enums import DossierStatusEnum
from app.db.session import Base


class Dossier(Base):
    __tablename__ = "dossiers"

    __table_args__ = (
        CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name="chk_dossiers_sha256"),
        Index("idx_dossiers_scene", "scene_id"),
        Index("idx_dossiers_status", "status"),
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
    spill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spills.id", ondelete="SET NULL"),
        nullable=True,
    )
    dossier_version: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    generated_by: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    evidence_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[DossierStatusEnum] = mapped_column(
        Enum(DossierStatusEnum, name="dossier_status_enum", native_enum=True),
        nullable=False,
        server_default=DossierStatusEnum.draft.value,
    )
    supersedes_dossier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dossiers.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    scene = relationship("Scene", back_populates="dossiers")
    spill = relationship("Spill", back_populates="dossiers")
    superseded_by = relationship(
        "Dossier",
        remote_side=[id],
        backref="supersedes",
    )
