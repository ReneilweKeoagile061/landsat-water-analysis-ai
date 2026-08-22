"""Derive transparent subsurface screening metrics from exported observations."""

from __future__ import annotations

import math
from collections.abc import Mapping


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
    quality = str(row.get("subsurface_data_quality") or "screening")
    if not source:
        source = "Landsat-derived screening" if ndvi is not None else "Unverified catalog value"
    confidence = {
        "measured": 0.85,
        "modeled": 0.65,
        "screening": 0.45,
        "synthetic demonstration": 0.25,
    }.get(quality.lower(), 0.35)
    depth_min = round(depth + 15, 1) if depth is not None else None
    depth_max = round(depth + 40, 1) if depth is not None else None
    return {
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
        "validation_next_step": "Confirm with geophysics and a test borehole" if depth is not None else "Collect a groundwater depth observation",
        "subsurface_data_source": source,
        "subsurface_data_quality": quality,
        "soilgrids_query_date": row.get("soilgrids_query_date"),
    }
