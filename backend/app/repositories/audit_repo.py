"""
backend/app/repositories/audit_repo.py

Append-only repository for cryptographic audit logging (DataBaseFinal.md Table 8).
Calculates SHA-256 hash chains: event_hash = sha256(previous_hash + payload).
"""

from __future__ import annotations

import hashlib
import json
from uuid import UUID, uuid4

from sqlalchemy import desc, select

from app.db.models.audit_log import AuditLog
from app.repositories.base import AsyncRepository


class AuditRepository(AsyncRepository[AuditLog]):
    model = AuditLog

    async def append(
        self,
        *,
        actor_type: str,
        actor_id: str | None,
        action: str,
        entity_type: str,
        entity_id: UUID,
        request_id: UUID | None = None,
        ip_address: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        # Fetch previous hash for the cryptographic chain
        prev = (
            await self.session.execute(
                select(AuditLog.event_hash).order_by(desc(AuditLog.occurred_at)).limit(1)
            )
        ).scalar_one_or_none()

        payload = {
            "actor_type": actor_type,
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "before": before,
            "after": after,
            "metadata": metadata or {},
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode()
        h = hashlib.sha256()
        if prev:
            h.update(prev.encode())
        h.update(encoded)
        event_hash = h.hexdigest()

        row = AuditLog(
            id=uuid4(),
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=request_id,
            ip_address=ip_address,
            before_data=before,
            after_data=after,
            metadata=metadata or {},
            hash_chain_previous=prev,
            event_hash=event_hash,
        )
        return await self.add(row)
