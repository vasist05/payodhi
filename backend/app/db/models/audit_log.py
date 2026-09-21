import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, CheckConstraint, Enum, Index, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.enums import ActorTypeEnum, AuditActionEnum
from app.db.session import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    __table_args__ = (
        CheckConstraint("event_hash ~ '^[a-f0-9]{64}$'", name="chk_audit_log_event_hash"),
        CheckConstraint(
            "hash_chain_previous IS NULL OR hash_chain_previous ~ '^[a-f0-9]{64}$'",
            name="chk_audit_log_hash_previous",
        ),
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_occurred_at", "occurred_at"),
        Index("idx_audit_actor", "actor_type", "actor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    actor_type: Mapped[ActorTypeEnum] = mapped_column(
        Enum(ActorTypeEnum, name="actor_type_enum", native_enum=True),
        nullable=False,
    )
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[AuditActionEnum] = mapped_column(
        Enum(AuditActionEnum, name="audit_action_enum", native_enum=True),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    hash_chain_previous: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
