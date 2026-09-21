"""Pillar 4: Spill Volume vs. Vessel Capacity Gating (Veto Logic).

Estimates slick volume using the Bonn Agreement standard thickness formula:
    Volume (m³) = Area (m²) × Thickness (m)
    Volume (liters) = Volume (m³) × 1000

Calculates vessel capacity from Deadweight Tonnage (DWT) and applies physical
gating logic:
    - If spill_volume > 5% of vessel_capacity → VETO (multiplier = 0.0)
    - If spill_volume <= 5% of vessel_capacity → PASS (multiplier = 1.0)
    - Missing DWT + unknown vessel type → multiplier = 0.5, LOW_CONFIDENCE
    - Spill volume < 100 liters → any vessel passes (multiplier = 1.0)
    - Spill volume > 3,000,000,000 liters → flag NATURAL_SEEP_HYPOTHESIS (multiplier = 0.0)
"""

from __future__ import annotations

import logging
from typing import Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Bonn Agreement thickness standards in meters
BONN_THICKNESS_M: Dict[str, float] = {
    "light": 0.0001,   # 0.1 mm
    "medium": 0.0005,  # 0.5 mm
    "heavy": 0.0010,   # 1.0 mm
}

# DWT fallback lookup table (metric tons) when DWT is missing or non-positive
DWT_FALLBACK_TABLE: Dict[str, float] = {
    "crude_tanker": 300000.0,
    "chemical_tanker": 50000.0,
    "cargo": 80000.0,
    "container": 100000.0,
    "fishing": 500.0,
}

VETO_THRESHOLD_PERCENT = 0.05  # 5% of vessel capacity
NATURAL_SEEP_VOLUME_LITERS = 3000000000.0  # 3 billion liters
TINY_SPILL_VOLUME_LITERS = 100.0  # 100 liters


class CapacityVetoResult(BaseModel):
    multiplier: float = Field(..., description="0.0 (veto), 1.0 (pass), or 0.5 (low confidence)")
    db_multiplier: int = Field(..., description="PostgreSQL-compliant multiplier: 0 (veto) or 1 (pass)")
    spill_volume_liters: float = Field(..., description="Estimated spill volume in liters")
    vessel_capacity_liters: float = Field(..., description="Estimated vessel bunker/cargo capacity in liters")
    reason: str = Field(..., description="Detailed explanation or edge case flag")


def capacity_veto(
    spill_area_m2: float,
    vessel_dwt: Optional[float],
    vessel_type: str,
    fuel_type: str = "medium",
) -> dict:
    """Evaluate whether a vessel has sufficient capacity to cause a given spill.

    Args:
        spill_area_m2: Estimated slick area in square meters.
        vessel_dwt: Deadweight Tonnage (metric tons). Treated as None if <= 0.
        vessel_type: Vessel classification string (e.g. crude_tanker, cargo, fishing).
        fuel_type: Oil type determining thickness under Bonn Agreement:
            'light' (0.1mm), 'medium' (0.5mm), or 'heavy' (1.0mm). Defaults to 'medium'.

    Returns:
        dict:
            multiplier (float): 1.0 (pass), 0.0 (vetoed), or 0.5 (low confidence).
            spill_volume_liters (float): Estimated slick volume in liters.
            vessel_capacity_liters (float): Vessel capacity in liters.
            reason (str): Explanatory code and edge case annotations.
    """
    # Edge case 1: Invalid spill area (<= 0)
    if spill_area_m2 is None or spill_area_m2 <= 0:
        logger.warning("Invalid spill area: %s m². Passing veto with neutral multiplier.", spill_area_m2)
        return CapacityVetoResult(
            multiplier=1.0,
            db_multiplier=1,
            spill_volume_liters=0.0,
            vessel_capacity_liters=0.0,
            reason="invalid_spill_area",
        ).model_dump()

    # Determine thickness under Bonn Agreement
    normalized_fuel = (fuel_type or "medium").strip().lower()
    if normalized_fuel in BONN_THICKNESS_M:
        thickness_m = BONN_THICKNESS_M[normalized_fuel]
        thickness_flag = ""
    else:
        logger.warning(
            "Unknown fuel type '%s'. Defaulting to 0.5 mm (medium) [ESTIMATED_THICKNESS].",
            fuel_type,
        )
        thickness_m = BONN_THICKNESS_M["medium"]
        thickness_flag = " [ESTIMATED_THICKNESS]"

    # Volume calculation: Area (m²) × Thickness (m) × 1000 L/m³
    spill_volume_liters = round(spill_area_m2 * thickness_m * 1000.0, 3)

    # Edge case 5: Massive spill exceeding 3 billion liters -> Natural Seep Hypothesis
    if spill_volume_liters > NATURAL_SEEP_VOLUME_LITERS:
        logger.warning(
            "Spill volume %.1f L exceeds 3 billion liters. Flagging NATURAL_SEEP_HYPOTHESIS.",
            spill_volume_liters,
        )
        return CapacityVetoResult(
            multiplier=0.0,
            db_multiplier=0,
            spill_volume_liters=spill_volume_liters,
            vessel_capacity_liters=0.0,
            reason="NATURAL_SEEP_HYPOTHESIS_volume_exceeds_threshold" + thickness_flag,
        ).model_dump()

    # Edge case 4: Tiny spill (< 100 liters) -> Any vessel passes
    if spill_volume_liters < TINY_SPILL_VOLUME_LITERS:
        logger.info("Spill volume %.1f L is < 100 L. Any vessel passes.", spill_volume_liters)
        # Even for tiny spill, determine capacity if possible for reporting
        norm_type = (vessel_type or "").strip().lower().replace(" ", "_")
        eff_dwt = vessel_dwt if (vessel_dwt is not None and vessel_dwt > 0) else DWT_FALLBACK_TABLE.get(norm_type, 0.0)
        vessel_capacity_liters = eff_dwt * 1000.0
        return CapacityVetoResult(
            multiplier=1.0,
            db_multiplier=1,
            spill_volume_liters=spill_volume_liters,
            vessel_capacity_liters=round(vessel_capacity_liters, 1),
            reason="tiny_spill_pass_below_100L" + thickness_flag,
        ).model_dump()

    # Normalize vessel type and handle DWT
    norm_type = (vessel_type or "").strip().lower().replace(" ", "_")
    dwt_notes = []

    # Edge case 6: Negative DWT treated as None
    effective_dwt = vessel_dwt
    if effective_dwt is not None and effective_dwt <= 0:
        logger.warning("Negative or zero DWT (%s) provided; treating as None and using fallback.", vessel_dwt)
        dwt_notes.append("negative_dwt_treated_as_none")
        effective_dwt = None

    # Handle missing DWT
    if effective_dwt is None:
        if norm_type in DWT_FALLBACK_TABLE:
            # Edge case 2: vessel_dwt is None + type known → use fallback table
            effective_dwt = DWT_FALLBACK_TABLE[norm_type]
            dwt_notes.append(f"dwt_fallback_used_{norm_type}_{effective_dwt:.0f}")
            logger.info("DWT missing for vessel type '%s'. Using fallback DWT of %.0f.", norm_type, effective_dwt)
        else:
            # Edge case 3: vessel_dwt is None + type unknown → multiplier=0.5, LOW_CONFIDENCE
            logger.warning("DWT missing and vessel type '%s' unknown. Returning 0.5 LOW_CONFIDENCE.", vessel_type)
            reason_str = "missing_dwt_unknown_type_LOW_CONFIDENCE"
            if dwt_notes:
                reason_str += f" ({', '.join(dwt_notes)})"
            return CapacityVetoResult(
                multiplier=0.5,
                db_multiplier=1,
                spill_volume_liters=spill_volume_liters,
                vessel_capacity_liters=0.0,
                reason=reason_str + thickness_flag,
            ).model_dump()

    # Vessel capacity in liters: 1 metric ton DWT ≈ 1,000 liters
    vessel_capacity_liters = round(effective_dwt * 1000.0, 1)

    # Veto rule: veto if spill_volume > 5% of vessel_capacity
    max_permitted_spill = VETO_THRESHOLD_PERCENT * vessel_capacity_liters

    if spill_volume_liters > max_permitted_spill:
        reason = f"capacity_veto_spill_exceeds_5_percent (spill={spill_volume_liters:.1f}L > 5% capacity={max_permitted_spill:.1f}L)"
        multiplier = 0.0
        logger.info(
            "VETO: Vessel %s (DWT %.0f) capacity %.0f L cannot dump %.1f L.",
            norm_type,
            effective_dwt,
            vessel_capacity_liters,
            spill_volume_liters,
        )
    else:
        reason = f"capacity_pass (spill={spill_volume_liters:.1f}L <= 5% capacity={max_permitted_spill:.1f}L)"
        multiplier = 1.0

    if dwt_notes:
        reason += f" [{'; '.join(dwt_notes)}]"
    if thickness_flag:
        reason += thickness_flag

    return CapacityVetoResult(
        multiplier=multiplier,
        db_multiplier=int(multiplier),
        spill_volume_liters=spill_volume_liters,
        vessel_capacity_liters=vessel_capacity_liters,
        reason=reason,
    ).model_dump()
