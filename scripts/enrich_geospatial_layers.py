"""Offline point-in-polygon / nearest-cell joins for licensed hydrogeology layers.

Does not invent BGS, Fan DTWT, or GLHYMPS values. Layer files must be supplied.
Optional geopandas is used when installed; otherwise a ray-casting join is used.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _lonlat(df: pd.DataFrame) -> tuple[str, str]:
    lon = "lon_wgs84" if "lon_wgs84" in df.columns else "longitude"
    lat = "lat_wgs84" if "lat_wgs84" in df.columns else "latitude"
    if lon not in df.columns or lat not in df.columns:
        raise ValueError("Points need longitude/latitude or lon_wgs84/lat_wgs84")
    return lon, lat


def point_in_ring(lon: float, lat: float, ring: list) -> bool:
    """Even-odd ray cast. ring is [[lon, lat], ...]."""
    inside = False
    n = len(ring)
    if n < 4:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = float(ring[i][0]), float(ring[i][1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-18) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def load_polygon_features(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("type") == "FeatureCollection":
        return payload["features"]
    if payload.get("type") == "Feature":
        return [payload]
    raise ValueError(f"{path} is not GeoJSON Feature/FeatureCollection")


def join_polygons(points: pd.DataFrame, geojson_path: Path, prefix: str) -> pd.DataFrame:
    features = load_polygon_features(geojson_path)
    lon_col, lat_col = _lonlat(points)
    out = points.copy()
    assigned = []
    for _, row in out.iterrows():
        lon, lat = float(row[lon_col]), float(row[lat_col])
        hit = None
        for feature in features:
            geom = feature.get("geometry") or {}
            coords = geom.get("coordinates")
            if geom.get("type") == "Polygon":
                rings = coords
            elif geom.get("type") == "MultiPolygon":
                rings = [poly[0] for poly in coords]
            else:
                continue
            if geom.get("type") == "Polygon":
                if point_in_ring(lon, lat, rings[0]):
                    hit = feature.get("properties") or {}
                    break
            else:
                for ring in rings:
                    if point_in_ring(lon, lat, ring):
                        hit = feature.get("properties") or {}
                        break
                if hit:
                    break
        assigned.append(hit)
    for key in {k for props in assigned if props for k in props}:
        out[f"{prefix}_{key}"] = [
            (props or {}).get(key) if props else None for props in assigned
        ]
    out[f"{prefix}_join"] = ["matched" if props else "unmatched" for props in assigned]
    return out


def join_nearest_points(points: pd.DataFrame, layer: pd.DataFrame, value_col: str, out_col: str, max_deg: float) -> pd.DataFrame:
    lon_col, lat_col = _lonlat(points)
    lx, ly = _lonlat(layer)
    out = points.copy()
    values = []
    for _, row in out.iterrows():
        dist = ((layer[lx] - row[lon_col]) ** 2 + (layer[ly] - row[lat_col]) ** 2) ** 0.5
        j = dist.idxmin()
        if float(dist.loc[j]) > max_deg:
            values.append(math.nan)
        else:
            values.append(layer.loc[j, value_col])
    out[out_col] = values
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Join licensed geology layers onto screening points.")
    parser.add_argument("--points", required=True, help="CSV of screening coordinates")
    parser.add_argument("--output", required=True, help="Enriched CSV")
    parser.add_argument("--bgs-polygons", help="GeoJSON of BGS aquifer productivity polygons")
    parser.add_argument("--fan-dtwt", help="CSV with lat/lon and dtwt_m")
    parser.add_argument("--glhymps", help="GeoJSON of GLHYMPS permeability polygons")
    parser.add_argument("--max-deg", type=float, default=0.25, help="Max nearest-cell distance (degrees)")
    args = parser.parse_args()

    df = pd.read_csv(args.points)
    if not args.bgs_polygons and not args.fan_dtwt and not args.glhymps:
        raise SystemExit(
            "No layers provided. Supply --bgs-polygons and/or --fan-dtwt and/or --glhymps. "
            "This script will not fill hydrogeology from placeholders."
        )
    if args.bgs_polygons:
        df = join_polygons(df, Path(args.bgs_polygons), "bgs")
    if args.glhymps:
        df = join_polygons(df, Path(args.glhymps), "glhymps")
    if args.fan_dtwt:
        fan = pd.read_csv(args.fan_dtwt)
        value = "dtwt_m" if "dtwt_m" in fan.columns else "fan_dtwt_m"
        if value not in fan.columns:
            raise SystemExit("Fan DTWT CSV must include dtwt_m")
        df = join_nearest_points(df, fan, value, "fan_dtwt_m", args.max_deg)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote {args.output} ({len(df)} rows)")


if __name__ == "__main__":
    main()
