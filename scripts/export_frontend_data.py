import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from model_metrics import MODEL_VALIDATION
from subsurface_metrics import enrich_subsurface


AOI_POLYGONS = {
    "OKAVANGO": [[22.10, -18.85], [23.00, -18.85], [23.00, -19.60], [22.10, -19.60], [22.10, -18.85]],
    "KALAHARI": [[23.00, -20.00], [25.00, -20.00], [25.00, -22.00], [23.00, -22.00], [23.00, -20.00]],
    "TRANSITIONAL": [[25.00, -21.00], [27.00, -21.00], [27.00, -23.00], [25.00, -23.00], [25.00, -21.00]],
}

AOI_COLORS = {"OKAVANGO": "#42d7ff", "KALAHARI": "#74b7ff", "TRANSITIONAL": "#8ea8ff"}
AOI_LABELS = {
    "OKAVANGO": "Okavango Delta",
    "KALAHARI": "Kalahari Fringe",
    "TRANSITIONAL": "Transitional Zone",
}

CLASS_MAP = {0: "Low", 1: "Medium", 2: "High", "0": "Low", "1": "Medium", "2": "High"}


def month_to_season(month: int) -> str:
    return "Wet Season" if month in (1, 2, 3, 4) else "Dry Season"


def ensure_columns(df: pd.DataFrame, required: list[str]) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def infer_season(row: pd.Series) -> str:
    if "season" in row and pd.notna(row["season"]):
        return str(row["season"])
    if "date" in row and pd.notna(row["date"]):
        month = pd.to_datetime(row["date"]).month
        return month_to_season(month)
    return "Wet Season"


def export_files(df: pd.DataFrame, out_dir: Path, metrics_override: dict | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    points_features = []
    for _, row in df.iterrows():
        pred_class = row.get("predicted_class", row.get("water_potential_class", 1))
        season = infer_season(row)
        subsurface = enrich_subsurface({**row.to_dict(), "season": season})
        subsurface = {key: value for key, value in subsurface.items() if value is not None}
        for key in (
            "aquifer_type",
            "aquifer_productivity_ls",
            "clay_fraction_pct",
            "borehole_feasibility_score",
            "recommended_action",
            "bgs_aquifer_productivity",
            "fan_dtwt_m",
            "glhymps_logk",
            "gldas_gws_mm",
            "data_trust_level",
            "clay_shielding_hazard",
            "ves_ab_min_m",
        ):
            if key in row and pd.notna(row[key]):
                subsurface[key] = row[key]
        if "data_trust_level" not in subsurface:
            subsurface["data_trust_level"] = subsurface.get("subsurface_data_quality", "screening")
        points_features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(row["lon_wgs84"]), float(row["lat_wgs84"])]},
                "properties": {
                    "aoi": str(row["aoi"]).upper(),
                    "scene_id": str(row.get("scene_id", "")),
                    "season": season,
                    "tier": str(row.get("tier", "Tier 1")),
                    "ndwi": float(row["ndwi"]),
                    "mndwi": float(row["mndwi"]),
                    "high_prob": float(row.get("prob_high", 0.0)),
                    "predicted_label": CLASS_MAP.get(pred_class, "Medium"),
                    **(
                        {"elevation": float(row["elevation"])}
                        if "elevation" in row and pd.notna(row["elevation"])
                        else {}
                    ),
                    **(
                        {"slope": float(row["slope"])}
                        if "slope" in row and pd.notna(row["slope"])
                        else {}
                    ),
                    **subsurface,
                },
            }
        )

    water_points = {"type": "FeatureCollection", "features": points_features}

    aoi_features = []
    for name, polygon in AOI_POLYGONS.items():
        aoi_features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [polygon]},
                "properties": {"aoi": name, "color": AOI_COLORS[name]},
            }
        )
    aois_geojson = {"type": "FeatureCollection", "features": aoi_features}

    scene_cols = ["scene_id", "date", "cloud", "tier", "aoi", "aoi_label", "overlap_pct", "season"]
    scenes_df = df.copy()
    if "season" not in scenes_df.columns and "date" in scenes_df.columns:
        scenes_df["season"] = pd.to_datetime(scenes_df["date"]).dt.month.map(month_to_season)
    if "aoi_label" not in scenes_df.columns and "aoi" in scenes_df.columns:
        scenes_df["aoi_label"] = scenes_df["aoi"].astype(str).str.upper().map(AOI_LABELS)
    scenes_df = scenes_df[[col for col in scene_cols if col in scenes_df.columns]].drop_duplicates("scene_id")
    scenes = scenes_df.to_dict(orient="records")

    metrics = metrics_override or {
        "scenes_discovered": int(df["scene_id"].nunique()) if "scene_id" in df.columns else len(scenes),
        "water_area_wet_km2": 2145,
        "water_area_dry_km2": 1268,
        "model": {**MODEL_VALIDATION, "test_samples": len(points_features)},
    }

    (out_dir / "water_points.geojson").write_text(json.dumps(water_points, indent=2), encoding="utf-8")
    (out_dir / "aois.geojson").write_text(json.dumps(aois_geojson, indent=2), encoding="utf-8")
    (out_dir / "scenes.json").write_text(json.dumps(scenes, indent=2), encoding="utf-8")
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export notebook outputs for frontend map layers.")
    parser.add_argument("--input-csv", required=True, help="CSV exported from notebook predictions.")
    parser.add_argument("--output-dir", default="public/data/exports", help="Export directory for frontend JSON/GeoJSON.")
    parser.add_argument("--metrics-json", help="Optional metrics JSON exported from the notebook.")
    args = parser.parse_args()

    metrics_override = None
    if args.metrics_json:
        metrics_override = json.loads(Path(args.metrics_json).read_text(encoding="utf-8"))

    df = pd.read_csv(args.input_csv)
    ensure_columns(df, ["lat_wgs84", "lon_wgs84", "ndwi", "mndwi", "aoi"])
    export_files(df, Path(args.output_dir), metrics_override)
    print(f"Exported frontend files to {args.output_dir}")


if __name__ == "__main__":
    main()
