import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Enum, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.enums import JobStatusEnum
from app.db.session import Base


class Job(Base):
    __tablename__ = "jobs"

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_jobs_idempotency"),
        CheckConstraint("retry_count >= 0", name="chk_jobs_retry_count"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_idempotency", "idempotency_key", unique=True),
        Index("idx_jobs_type", "job_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatusEnum] = mapped_column(
        Enum(JobStatusEnum, name="job_status_enum", native_enum=True),
        nullable=False,
        server_default=JobStatusEnum.queued.value,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
