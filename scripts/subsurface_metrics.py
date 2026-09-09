"""Derive transparent subsurface screening metrics from exported observations."""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping
from typing import Any

SY_UNCONFINED_SAND = 0.15
S_CONFINED_BEDROCK = 0.0001
CLAY_SHIELD_PCT = 35.0
INVESTIGATION_DEPTH_FACTOR = 0.19
MIN_AB_OVER_TARGET_DEPTH = 3.0
MIN_AB_OVER_MN = 5.0


def _number(row: Mapping[str, object], key: str) -> float | None:
    value = row.get(key)
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def classify_dtwt(depth_m: float | None) -> str | None:
    if depth_m is None:
        return None
    if depth_m < 25:
        return "Shallow (<25 m)"
    if depth_m <= 75:
        return "Moderate (25-75 m)"
    return "Deep (>75 m)"


def phreatophyte_index(
    ndvi: float | None,
    land_surface_temperature_c: float | None = None,
    dry_season: bool = False,
) -> float | None:
    """Score dry-season green vegetation, optionally weighted by cool LST."""
    if ndvi is None:
        return None
    vegetation = max(0.0, min(1.0, (ndvi - 0.1) / 0.35))
    if not dry_season:
        return round(vegetation, 3)
    if land_surface_temperature_c is None:
        return round(vegetation, 3)
    coolness = max(0.0, min(1.0, (42.0 - land_surface_temperature_c) / 18.0))
    return round(0.7 * vegetation + 0.3 * coolness, 3)


def infiltration_score(clay_fraction_pct: float | None) -> float | None:
    """Proxy score for infiltration potential from shallow-soil clay fraction."""
    if clay_fraction_pct is None:
        return None
    clay = max(0.0, min(100.0, clay_fraction_pct))
    return round(100.0 - clay, 1)


def infiltration_class(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 65:
        return "High infiltration / weak clay seal"
    if score >= 35:
        return "Moderate infiltration"
    return "Low infiltration / strong clay seal"


def enrich_subsurface(row: Mapping[str, object]) -> dict[str, object]:
    depth = _number(row, "depth_to_water_table_m")
    clay = _number(row, "clay_fraction_pct")
    if clay is None:
        shallow_clay = [_number(row, key) for key in ("clay_0_5_pct", "clay_15_30_pct")]
        shallow_clay = [value for value in shallow_clay if value is not None]
        clay = sum(shallow_clay) / len(shallow_clay) if shallow_clay else None
    ndvi = _number(row, "ndvi")
    lst = _number(row, "land_surface_temperature_c")
    season = str(row.get("season", ""))
    dry = season.lower().startswith("dry")
    phreatophyte = _number(row, "phreatophyte_activity")
    if phreatophyte is None:
        phreatophyte = phreatophyte_index(ndvi, lst, dry)
    score = infiltration_score(clay)
    source = str(row.get("subsurface_data_source") or row.get("subsurface_source") or "")
    quality = str(row.get("subsurface_data_quality") or row.get("data_trust_level") or "screening")
    if not source:
        source = "Landsat-derived screening" if ndvi is not None else "Unverified catalog value"
    confidence = {
        "measured": 0.85,
        "modeled": 0.65,
        "screening": 0.45,
        "synthetic demonstration": 0.25,
    }.get(quality.lower(), 0.35)
    clay_hazard = clay_shielding(clay)
    ves = None
    if depth is not None:
        ves = plan_ves_survey(target_borehole_depth_m=depth)
    depth_min = round(depth + 15, 1) if depth is not None else None
    depth_max = round(depth + 40, 1) if depth is not None else None
    next_step = "Confirm with geophysics and a test borehole" if depth is not None else "Collect a groundwater depth observation"
    recommended = row.get("recommended_action")
    if clay_hazard["clay_shielding_hazard"]:
        next_step = clay_hazard["recommended_action"]
        recommended = clay_hazard["recommended_action"]
        confidence = min(confidence, 0.45)
    payload = {
        "depth_to_water_table_m": depth,
        "dtwt_class": classify_dtwt(depth),
        "phreatophyte_activity": phreatophyte,
        "phreatophyte_index": phreatophyte,
        "phreatophyte_method": "NDVI + cool LST dry-season screen" if lst is not None and dry else "NDVI screen; LST unavailable",
        "infiltration_score": score,
        "infiltration_class": infiltration_class(score),
        "evidence_confidence": confidence,
        "drill_depth_min_m": depth_min,
        "drill_depth_max_m": depth_max,
        "validation_next_step": next_step,
        "subsurface_data_source": source,
        "subsurface_data_quality": quality,
        "data_trust_level": quality,
        "soilgrids_query_date": row.get("soilgrids_query_date"),
        "clay_shielding_hazard": clay_hazard["clay_shielding_hazard"],
        "apparent_resistivity_note": clay_hazard["apparent_resistivity_note"],
    }
    if recommended:
        payload["recommended_action"] = recommended
    if ves is not None:
        payload["ves_ab_min_m"] = ves["ab_min_m"]
        payload["ves_mn_max_m"] = ves["mn_max_m"]
        payload["ves_investigation_depth_m"] = ves["investigation_depth_m"]
    for key in (
        "bgs_aquifer_productivity",
        "fan_dtwt_m",
        "glhymps_logk",
        "gldas_gws_mm",
        "aquifer_class",
        "delta_gw_mm",
    ):
        value = row.get(key)
        if value is not None and value != "":
            payload[key] = value
    return payload


def storage_coefficient(aquifer_class: str | None) -> float:
    """Return S or Sy for volumetric conversion. Unknown class is not guessed as sand."""
    token = (aquifer_class or "").strip().lower()
    if any(part in token for part in ("kalahari", "unconfined", "sand", "specific yield", "sy")):
        return SY_UNCONFINED_SAND
    if any(part in token for part in ("confined", "bedrock", "crystalline", "basement", "elastic")):
        return S_CONFINED_BEDROCK
    raise ValueError(
        "aquifer_class is required for storage scaling. Use 'unconfined sand' "
        f"(Sy={SY_UNCONFINED_SAND}) or 'confined bedrock' (S={S_CONFINED_BEDROCK})."
    )


def volumetric_water_change_mm(drawdown_m: float, aquifer_class: str) -> float:
    """ΔGW = dh × S, returned in millimetres of water.

    Unconfined sands: 1 m drop × 0.15 = 150 mm.
    Confined bedrock: 1 m drop × 0.0001 = 0.1 mm (elastic pressure release).
    """
    storage = storage_coefficient(aquifer_class)
    return float(drawdown_m) * storage * 1000.0


def schlumberger_geometric_factor(ab_m: float, mn_m: float) -> float:
    """K = π ((AB/2)² − (MN/2)²) / (2 × (MN/2))."""
    if ab_m <= 0 or mn_m <= 0:
        raise ValueError("AB and MN must be positive")
    if ab_m < MIN_AB_OVER_MN * mn_m:
        raise ValueError(f"Array geometry requires AB >= {MIN_AB_OVER_MN} × MN")
    half_ab = ab_m / 2.0
    half_mn = mn_m / 2.0
    return math.pi * (half_ab**2 - half_mn**2) / (2.0 * half_mn)


def plan_ves_survey(
    target_borehole_depth_m: float,
    n_expansions: int = 8,
) -> dict[str, Any]:
    """Schlumberger VES layout after Andreas de Jong field practice.

    AB >= 3 × target depth, and AB is also large enough that Z_e = 0.19 × AB
    reaches the target. MN satisfies AB >= 5 × MN.
    """
    if target_borehole_depth_m <= 0:
        raise ValueError("target_borehole_depth_m must be positive")
    ab_from_third = MIN_AB_OVER_TARGET_DEPTH * target_borehole_depth_m
    ab_from_investigation = target_borehole_depth_m / INVESTIGATION_DEPTH_FACTOR
    ab_min = max(ab_from_third, ab_from_investigation)
    mn_max = ab_min / MIN_AB_OVER_MN
    investigation_depth = INVESTIGATION_DEPTH_FACTOR * ab_min
    steps = []
    for i in range(1, n_expansions + 1):
        ab = ab_min * (i / n_expansions)
        mn = ab / MIN_AB_OVER_MN
        k = schlumberger_geometric_factor(ab, mn)
        steps.append(
            {
                "step": i,
                "ab_m": round(ab, 2),
                "mn_m": round(mn, 2),
                "geometric_factor_k": round(k, 3),
                "ze_m": round(INVESTIGATION_DEPTH_FACTOR * ab, 2),
            }
        )
    return {
        "target_borehole_depth_m": target_borehole_depth_m,
        "ab_min_m": round(ab_min, 2),
        "mn_max_m": round(mn_max, 2),
        "investigation_depth_m": round(investigation_depth, 2),
        "rule_ab_ge_3x_depth": True,
        "rule_ab_ge_5x_mn": True,
        "layout": "Schlumberger",
        "cable_table": steps,
    }


def ves_survey_csv(plan: dict[str, Any]) -> str:
    rows = plan["cable_table"]
    if not rows:
        return ""
    fieldnames = list(rows[0].keys())
    from io import StringIO

    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def clay_shielding(clay_fraction_pct: float | None) -> dict[str, Any]:
    if clay_fraction_pct is None:
        return {
            "clay_shielding_hazard": False,
            "apparent_resistivity_note": None,
            "recommended_action": None,
        }
    if clay_fraction_pct > CLAY_SHIELD_PCT:
        return {
            "clay_shielding_hazard": True,
            "apparent_resistivity_note": "Conductive Clay Shielding Hazard (apparent resistivity <10 Ω·m)",
            "recommended_action": (
                "Lined surface rainwater harvesting (earth dams or ponds); "
                "heavy clay seals prevent deep recharge — do not site a deep borehole here"
            ),
        }
    return {
        "clay_shielding_hazard": False,
        "apparent_resistivity_note": None,
        "recommended_action": None,
    }
