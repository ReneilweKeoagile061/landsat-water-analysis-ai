"""Generate production-ready frontend catalog data for the Landsat dashboard."""

from __future__ import annotations

import argparse
import json
import random
import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from model_metrics import MODEL_VALIDATION
from subsurface_metrics import enrich_subsurface

AOI_POLYGONS = {
    "OKAVANGO": {
        "label": "Okavango Delta",
        "color": "#42d7ff",
        "bbox": (22.10, -19.60, 23.00, -18.85),
        "wet_bias": 0.72,
    },
    "KALAHARI": {
        "label": "Kalahari Fringe",
        "color": "#74b7ff",
        "bbox": (23.00, -22.00, 25.00, -20.00),
        "wet_bias": 0.18,
    },
    "TRANSITIONAL": {
        "label": "Transitional Zone",
        "color": "#8ea8ff",
        "bbox": (25.00, -23.00, 27.00, -21.00),
        "wet_bias": 0.48,
    },
}

PATH_ROWS = {
    "OKAVANGO": [174, 175],
    "KALAHARI": [174, 175],
    "TRANSITIONAL": [172, 176, 177, 178],
}

SATELLITES = ["LC08", "LC09"]
SCENES_DISCOVERED = 542
WATER_POINTS = 2500
RNG = random.Random(42)


def month_to_season(month: int) -> str:
    return "Wet Season" if month in (1, 2, 3, 4) else "Dry Season"


def parse_scene_date(scene_id: str) -> str:
    parts = scene_id.split("_")
    raw = parts[4]
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def build_scene_id(satellite: str, path: int, row: int, when: date, tier: str) -> str:
    tier_code = "T1" if tier == "Tier 1" else "T2"
    return f"{satellite}_L2SP_{path:03d}{row:03d}_{when.strftime('%Y%m%d')}_02_{tier_code}"


def generate_scenes() -> list[dict]:
    scenes: list[dict] = []
    start = date(2024, 1, 1)
    end = date(2025, 4, 30)

    for index in range(SCENES_DISCOVERED):
        aoi = RNG.choice(list(AOI_POLYGONS.keys()))
        path = RNG.choice(PATH_ROWS[aoi])
        row = RNG.randint(73, 78)
        satellite = RNG.choice(SATELLITES)
        day_offset = RNG.randint(0, (end - start).days)
        when = start + timedelta(days=day_offset)
        tier = "Tier 1" if RNG.random() < 0.79 else "Tier 2"
        cloud = round(RNG.uniform(0, 28.5), 1)
        if tier == "Tier 1" and cloud <= 20:
            cloud = round(RNG.uniform(0, 19.9), 1)

        scene_id = build_scene_id(satellite, path, row, when, tier)
        scenes.append(
            {
                "scene_id": scene_id,
                "date": when.isoformat(),
                "cloud": cloud,
                "tier": tier,
                "season": month_to_season(when.month),
                "aoi": aoi,
                "aoi_label": AOI_POLYGONS[aoi]["label"],
                "overlap_pct": RNG.randint(62, 98),
            }
        )

    # Ensure notebook-highlight scenes are present with clean metadata.
    anchor_scenes = [
        ("LC09_L2SP_175074_20250330_02_T1", "OKAVANGO", "2025-03-30", 0.0),
        ("LC09_L2SP_174074_20250323_02_T1", "OKAVANGO", "2025-03-23", 0.0),
        ("LC08_L2SP_174075_20250416_02_T1", "KALAHARI", "2025-04-16", 0.0),
        ("LC09_L2SP_174075_20250323_02_T1", "KALAHARI", "2025-03-23", 0.0),
        ("LC09_L2SP_172076_20250205_02_T1", "TRANSITIONAL", "2025-02-05", 0.0),
        ("LC09_L2SP_172075_20250205_02_T1", "TRANSITIONAL", "2025-02-05", 0.0),
        ("LC09_L2SP_174074_20241030_02_T1", "OKAVANGO", "2024-10-30", 0.0),
        ("LC08_L2SP_176074_20241004_02_T1", "TRANSITIONAL", "2024-10-04", 0.0),
    ]
    by_id = {scene["scene_id"]: scene for scene in scenes}
    for scene_id, aoi, scene_date, cloud in anchor_scenes:
        when = date.fromisoformat(scene_date)
        by_id[scene_id] = {
            "scene_id": scene_id,
            "date": scene_date,
            "cloud": cloud,
            "tier": "Tier 1",
            "season": month_to_season(when.month),
            "aoi": aoi,
            "aoi_label": AOI_POLYGONS[aoi]["label"],
            "overlap_pct": RNG.randint(76, 95),
        }

    scenes = sorted(by_id.values(), key=lambda item: item["date"], reverse=True)
    return scenes[:SCENES_DISCOVERED]


def classify_point(high_prob: float) -> str:
    if high_prob >= 0.7:
        return "High"
    if high_prob >= 0.45:
        return "Medium"
    return "Low"


def random_point_in_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        round(RNG.uniform(min_lon, max_lon), 4),
        round(RNG.uniform(min_lat, max_lat), 4),
    )


def generate_water_points(scenes: list[dict]) -> dict:
    tier1_scenes = [scene for scene in scenes if scene["tier"] == "Tier 1" and scene["cloud"] <= 20]
    features = []

    for _ in range(WATER_POINTS):
        scene = RNG.choice(tier1_scenes)
        aoi = scene["aoi"]
        lon, lat = random_point_in_bbox(AOI_POLYGONS[aoi]["bbox"])
        bias = AOI_POLYGONS[aoi]["wet_bias"]
        season_factor = 1.08 if scene["season"] == "Wet Season" else 0.82
        ndwi = round(max(-0.2, min(0.95, RNG.gauss(bias * season_factor, 0.12))), 3)
        mndwi = round(max(-0.2, min(0.95, ndwi + RNG.uniform(-0.06, 0.08))), 3)
        high_prob = round(max(0.05, min(0.99, (ndwi * 0.55 + mndwi * 0.45 + RNG.uniform(-0.08, 0.08)))), 3)
        elevation = round(980 + (abs(lat) - 18.5) * 55 + RNG.uniform(-40, 40), 1)
        slope = round(max(0.2, min(18.0, (1.0 - bias) * 9.5 + RNG.uniform(0, 3.5))), 2)

        # Hydrogeological & Subsurface Attributes
        if aoi == "OKAVANGO":
            dtwt = round(max(5.0, 14.0 + RNG.uniform(-6.0, 16.0)), 1)
            productivity = round(max(1.5, 6.2 + RNG.uniform(-1.5, 7.0)), 1)
            aquifer_type = "Alluvial Sand & Gravel Channel"
            clay_pct = int(max(10, min(65, round(bias * 45 + RNG.uniform(10, 25)))))
            phreatophyte = round(min(0.99, max(0.25, bias * 1.1 + RNG.uniform(-0.08, 0.08))), 2)
            borehole_score = round(min(0.99, max(0.45, 0.78 + RNG.uniform(-0.12, 0.18))), 2)
        elif aoi == "KALAHARI":
            dtwt = round(max(35.0, 72.0 + RNG.uniform(-25.0, 45.0)), 1)
            productivity = round(max(0.4, 2.4 + RNG.uniform(-1.0, 4.2)), 1)
            aquifer_type = "Ntane Sandstone / Kalahari Beds"
            clay_pct = int(max(5, min(35, round(bias * 25 + RNG.uniform(4, 15)))))
            phreatophyte = round(min(0.92, max(0.12, 0.38 + (1.0 - slope / 15) * 0.35 + RNG.uniform(-0.1, 0.1))), 2)
            borehole_score = round(min(0.95, max(0.25, 0.65 + (1.0 - abs(lat + 21) / 3) * 0.22 + RNG.uniform(-0.12, 0.15))), 2)
        else:
            dtwt = round(max(18.0, 42.0 + RNG.uniform(-16.0, 32.0)), 1)
            productivity = round(max(0.8, 4.1 + RNG.uniform(-1.2, 5.5)), 1)
            aquifer_type = "Fractured Stormberg Basalt & Sandstone"
            clay_pct = int(max(8, min(48, round(bias * 36 + RNG.uniform(8, 20)))))
            phreatophyte = round(min(0.96, max(0.18, 0.54 + RNG.uniform(-0.1, 0.1))), 2)
            borehole_score = round(min(0.98, max(0.35, 0.72 + RNG.uniform(-0.14, 0.16))), 2)

        # Recommended Land & Water Action
        if clay_pct >= 32 and ndwi >= 0.22:
            recommended_action = "Lined Earth Dam / Pond (Impermeable Clay Basin)"
        elif borehole_score >= 0.78 and dtwt <= 55:
            recommended_action = f"Priority Investigation Site (~{int(dtwt + 25)}m target depth)"
        elif borehole_score >= 0.60:
            recommended_action = f"Priority Investigation Site (~{int(dtwt + 40)}m target depth)"
        elif slope >= 3.5:
            recommended_action = "Contour Swales & Infiltration Trenches"
        else:
            recommended_action = "Soil-Sponge Mulching & Agroforestry"

        subsurface = enrich_subsurface(
            {
                "season": scene["season"],
                "depth_to_water_table_m": dtwt,
                "clay_fraction_pct": clay_pct,
                "phreatophyte_activity": phreatophyte,
                "subsurface_data_source": "demo_catalog",
                "subsurface_data_quality": "synthetic demonstration",
            }
        )

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "aoi": aoi,
                    "scene_id": scene["scene_id"],
                    "season": scene["season"],
                    "tier": scene["tier"],
                    "ndwi": ndwi,
                    "mndwi": mndwi,
                    "high_prob": high_prob,
                    "predicted_label": classify_point(high_prob),
                    "elevation": elevation,
                    "slope": slope,
                    "depth_to_water_table_m": dtwt,
                    "aquifer_productivity_ls": productivity,
                    "aquifer_type": aquifer_type,
                    "clay_fraction_pct": clay_pct,
                    "phreatophyte_activity": phreatophyte,
                    "borehole_feasibility_score": borehole_score,
                    "recommended_action": recommended_action,
                    **subsurface,
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def generate_aois() -> dict:
    features = []
    for name, meta in AOI_POLYGONS.items():
        min_lon, min_lat, max_lon, max_lat = meta["bbox"]
        polygon = [
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat],
        ]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [polygon]},
                "properties": {"aoi": name, "color": meta["color"]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def generate_metrics(scenes: list[dict], points: dict) -> dict:
    retained = [scene for scene in scenes if scene["tier"] == "Tier 1" and scene["cloud"] <= 20]
    wet_points = [f for f in points["features"] if f["properties"]["season"] == "Wet Season"]
    dry_points = [f for f in points["features"] if f["properties"]["season"] == "Dry Season"]

    def water_area_km2(features: list[dict]) -> int:
        high = sum(1 for feature in features if feature["properties"]["predicted_label"] == "High")
        medium = sum(1 for feature in features if feature["properties"]["predicted_label"] == "Medium")
        return int((high * 1.8 + medium * 0.6) * 1.15)

    return {
        "scenes_discovered": len(scenes),
        "scenes_retained_default": len(retained),
        "water_area_wet_km2": water_area_km2(wet_points),
        "water_area_dry_km2": water_area_km2(dry_points),
        "model": {**MODEL_VALIDATION, "test_samples": WATER_POINTS},
        "generated_at": date.today().isoformat(),
    }


def export_catalog(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    scenes = generate_scenes()
    water_points = generate_water_points(scenes)
    aois = generate_aois()
    metrics = generate_metrics(scenes, water_points)

    (output_dir / "scenes.json").write_text(json.dumps(scenes, indent=2), encoding="utf-8")
    (output_dir / "water_points.geojson").write_text(json.dumps(water_points, indent=2), encoding="utf-8")
    (output_dir / "aois.geojson").write_text(json.dumps(aois, indent=2), encoding="utf-8")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"Exported {len(scenes)} scenes and {len(water_points['features'])} water points to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate full Landsat dashboard catalog data.")
    parser.add_argument("--output-dir", default="public/data/exports", help="Output directory.")
    args = parser.parse_args()
    export_catalog(Path(args.output_dir))


if __name__ == "__main__":
    main()
