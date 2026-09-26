"""
backend/app/repositories/drift_repo.py

Repository for drift simulation runs (DataBaseFinal.md Table 5 drift_runs).
Handles persistence, status transitions, SHA-256 fingerprint deduplication,
and querying by scene, spill, and vessel.
"""

from __future__ import annotations

import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.drift_run import DriftRun
from app.db.models.enums import DriftStatusEnum
from app.db.models.vessel import Vessel
from app.repositories.base import AsyncRepository


class DriftRepository(AsyncRepository[DriftRun]):
    model = DriftRun

    async def get_or_create_system_vessel(self) -> Vessel:
        """
        Get or create a default unknown vessel record for backward origin reconstructions
        executed prior to candidate vessel identification.
        """
        stmt = select(Vessel).where(Vessel.vessel_name == "UNASSIGNED_ORIGIN_PROBE").limit(1)
        res = (await self.session.execute(stmt)).scalar_one_or_none()
        if res is not None:
            return res

        vessel = Vessel(
            vessel_name="UNASSIGNED_ORIGIN_PROBE",
            source="system",
            metadata_={"purpose": "Placeholder for Phase 3 backward drift origin estimation"},
        )
        self.session.add(vessel)
        await self.session.flush()
        return vessel

    async def create_drift_run(
        self,
        *,
        scene_id: UUID,
        vessel_id: UUID | None = None,
        spill_id: UUID | None = None,
        simulation_version: str,
        model_parameters: dict[str, Any],
        run_fingerprint: str,
        status: DriftStatusEnum = DriftStatusEnum.queued,
        output_storage_uri: str | None = None,
        output_sha256: str | None = None,
        result_summary: dict[str, Any] | None = None,
    ) -> DriftRun:
        """Create a new drift simulation run row."""
        if vessel_id is None:
            sys_vessel = await self.get_or_create_system_vessel()
            vessel_id = sys_vessel.id

        drift_run = DriftRun(
            scene_id=scene_id,
            vessel_id=vessel_id,
            spill_id=spill_id,
            simulation_version=simulation_version,
            model_parameters=model_parameters,
            run_fingerprint=run_fingerprint,
            status=status,
            output_storage_uri=output_storage_uri,
            output_sha256=output_sha256,
            result_summary=result_summary or {},
        )
        return await self.add(drift_run)

    async def get_by_fingerprint(self, fingerprint: str) -> DriftRun | None:
        """Check for existing drift run with identical parameters."""
        stmt = select(DriftRun).where(DriftRun.run_fingerprint == fingerprint)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_with_relations(self, drift_run_id: UUID) -> DriftRun | None:
        """Eager-load scene, spill, and vessel relationships."""
        stmt = (
            select(DriftRun)
            .options(
                selectinload(DriftRun.scene),
                selectinload(DriftRun.spill),
                selectinload(DriftRun.vessel),
            )
            .where(DriftRun.id == drift_run_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def update_status(
        self,
        drift_run_id: UUID,
        *,
        status: DriftStatusEnum,
        result_summary: dict[str, Any] | None = None,
        output_storage_uri: str | None = None,
        output_sha256: str | None = None,
        error_message: str | None = None,
        completed_at: datetime.datetime | None = None,
    ) -> DriftRun | None:
        """Update drift run execution status and summary."""
        drift_run = await self.get_by_id(drift_run_id)
        if drift_run is None:
            return None

        drift_run.status = status
        if result_summary is not None:
            drift_run.result_summary = result_summary
        if output_storage_uri is not None:
            drift_run.output_storage_uri = output_storage_uri
        if output_sha256 is not None:
            drift_run.output_sha256 = output_sha256
        if error_message is not None:
            drift_run.error_message = error_message
        if completed_at is not None:
            drift_run.completed_at = completed_at

        await self.session.flush()
        return drift_run

    async def list_by_scene(self, scene_id: UUID) -> list[DriftRun]:
        """List all drift runs associated with a satellite scene."""
        stmt = select(DriftRun).where(DriftRun.scene_id == scene_id).order_by(DriftRun.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_spill(self, spill_id: UUID) -> list[DriftRun]:
        """List all drift runs associated with an oil spill."""
        stmt = select(DriftRun).where(DriftRun.spill_id == spill_id).order_by(DriftRun.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())
