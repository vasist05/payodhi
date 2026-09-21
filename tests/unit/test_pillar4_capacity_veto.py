"""Unit tests for Pillar 4: Capacity Veto logic."""

import pytest
from core.phase5_attribution.pillar4_capacity_veto import capacity_veto


def test_small_spill_small_fishing_boat_passes():
    """Case 1: Small spill (500 L), small fishing boat (500 DWT) -> pass (multiplier = 1.0)."""
    # 1000 m2 with medium (0.5mm) thickness yields 500 liters
    area_m2 = 1000.0
    res = capacity_veto(
        spill_area_m2=area_m2,
        vessel_dwt=500.0,
        vessel_type="fishing",
        fuel_type="medium",
    )
    assert res["multiplier"] == 1.0
    assert pytest.approx(res["spill_volume_liters"], rel=1e-3) == 500.0
    assert pytest.approx(res["vessel_capacity_liters"], rel=1e-3) == 500000.0
    assert "capacity_pass" in res["reason"]


def test_massive_spill_small_fishing_boat_vetoed():
    """Case 2: Massive spill (500,000 L), small fishing boat (500 DWT) -> veto (multiplier = 0.0)."""
    # 1,000,000 m2 with medium (0.5mm) thickness yields 500,000 liters
    area_m2 = 1000000.0
    res = capacity_veto(
        spill_area_m2=area_m2,
        vessel_dwt=500.0,
        vessel_type="fishing",
        fuel_type="medium",
    )
    assert res["multiplier"] == 0.0
    assert pytest.approx(res["spill_volume_liters"], rel=1e-3) == 500000.0
    assert pytest.approx(res["vessel_capacity_liters"], rel=1e-3) == 500000.0
    assert "capacity_veto" in res["reason"]


def test_medium_spill_crude_tanker_passes():
    """Case 3: Medium spill (10,000 L), crude tanker (300,000 DWT) -> pass (multiplier = 1.0)."""
    # 20,000 m2 with medium (0.5mm) thickness yields 10,000 liters
    area_m2 = 20000.0
    res = capacity_veto(
        spill_area_m2=area_m2,
        vessel_dwt=300000.0,
        vessel_type="crude_tanker",
        fuel_type="medium",
    )
    assert res["multiplier"] == 1.0
    assert pytest.approx(res["spill_volume_liters"], rel=1e-3) == 10000.0
    assert pytest.approx(res["vessel_capacity_liters"], rel=1e-3) == 300000000.0
    assert "capacity_pass" in res["reason"]


def test_missing_dwt_known_type_uses_fallback():
    """Case 4: Missing DWT (None), known type (crude_tanker) -> uses fallback DWT of 300,000."""
    area_m2 = 20000.0  # 10,000 L
    res = capacity_veto(
        spill_area_m2=area_m2,
        vessel_dwt=None,
        vessel_type="crude_tanker",
        fuel_type="medium",
    )
    assert res["multiplier"] == 1.0
    assert pytest.approx(res["vessel_capacity_liters"], rel=1e-3) == 300000000.0
    assert "dwt_fallback_used" in res["reason"]


def test_missing_dwt_unknown_type_low_confidence():
    """Case 5: Missing DWT, unknown vessel type -> multiplier = 0.5, LOW_CONFIDENCE."""
    area_m2 = 20000.0
    res = capacity_veto(
        spill_area_m2=area_m2,
        vessel_dwt=None,
        vessel_type="mysterious_ghost_ship",
        fuel_type="medium",
    )
    assert res["multiplier"] == 0.5
    assert "LOW_CONFIDENCE" in res["reason"]


def test_zero_or_negative_spill_area_invalid_input():
    """Case 6: Zero or negative spill area -> multiplier = 1.0, reason = invalid_spill_area."""
    res_zero = capacity_veto(
        spill_area_m2=0.0,
        vessel_dwt=50000.0,
        vessel_type="cargo",
    )
    assert res_zero["multiplier"] == 1.0
    assert res_zero["spill_volume_liters"] == 0.0
    assert "invalid_spill_area" in res_zero["reason"]

    res_neg = capacity_veto(
        spill_area_m2=-100.0,
        vessel_dwt=50000.0,
        vessel_type="cargo",
    )
    assert res_neg["multiplier"] == 1.0
    assert "invalid_spill_area" in res_neg["reason"]


def test_natural_seep_signal_huge_spill():
    """Case 7: Huge spill (> 3 billion L) -> multiplier = 0.0, reason flags NATURAL_SEEP_HYPOTHESIS."""
    # 7 billion m2 * 0.5mm = 3.5 billion liters (> 3,000,000,000 L)
    huge_area = 7000000000.0
    res = capacity_veto(
        spill_area_m2=huge_area,
        vessel_dwt=300000.0,
        vessel_type="crude_tanker",
        fuel_type="medium",
    )
    assert res["multiplier"] == 0.0
    assert res["spill_volume_liters"] > 3000000000.0
    assert "NATURAL_SEEP_HYPOTHESIS" in res["reason"]


def test_negative_dwt_treated_as_none_uses_fallback():
    """Case 8: Negative DWT is treated as None and uses fallback table."""
    area_m2 = 20000.0  # 10,000 L
    res = capacity_veto(
        spill_area_m2=area_m2,
        vessel_dwt=-500.0,
        vessel_type="cargo",
        fuel_type="medium",
    )
    assert res["multiplier"] == 1.0
    # Cargo fallback DWT is 80,000 -> 80,000,000 L capacity
    assert pytest.approx(res["vessel_capacity_liters"], rel=1e-3) == 80000000.0
    assert "negative_dwt_treated_as_none" in res["reason"]
    assert "dwt_fallback_used" in res["reason"]


def test_all_three_fuel_types_bonn_agreement():
    """Verify thickness calculations for light (0.1mm), medium (0.5mm), and heavy (1.0mm) fuels."""
    area_m2 = 10000.0

    res_light = capacity_veto(area_m2, 50000.0, "cargo", fuel_type="light")
    # 10,000 m2 * 0.1 mm = 1,000 L
    assert pytest.approx(res_light["spill_volume_liters"], rel=1e-3) == 1000.0

    res_medium = capacity_veto(area_m2, 50000.0, "cargo", fuel_type="medium")
    # 10,000 m2 * 0.5 mm = 5,000 L
    assert pytest.approx(res_medium["spill_volume_liters"], rel=1e-3) == 5000.0

    res_heavy = capacity_veto(area_m2, 50000.0, "cargo", fuel_type="heavy")
    # 10,000 m2 * 1.0 mm = 10,000 L
    assert pytest.approx(res_heavy["spill_volume_liters"], rel=1e-3) == 10000.0


def test_tiny_spill_under_100_liters_passes_any_vessel():
    """Verify tiny spill (< 100 L) passes unconditionally with multiplier = 1.0."""
    # 100 m2 * 0.5 mm = 50 L (< 100 L)
    res = capacity_veto(
        spill_area_m2=100.0,
        vessel_dwt=10.0,  # Even a tiny 10 DWT craft
        vessel_type="rowboat",
        fuel_type="medium",
    )
    assert res["multiplier"] == 1.0
    assert res["spill_volume_liters"] == 50.0
    assert "tiny_spill_pass" in res["reason"]
