"""Fetch NASA GLDAS catchment groundwater storage via Earth Engine.

Band: gws_tavg (groundwater storage average, millimetres).
Native resolution is ~0.25° (~27.8 km). That is a regional screening layer,
not well-scale truth (Lee et al. / NASA ARSET: skill falls from ~36% at
basin scale to ~10% at individual wells).

Does not use xarray/netCDF. EE performs the reduction; this script writes GeoJSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BOTSWANA = {"min_lon": 19.9, "min_lat": -26.9, "max_lon": 29.4, "max_lat": -17.8}
COLLECTION = "NASA/GLDAS/V022/CLSM/G025/DA1D"
BAND = "gws_tavg"


def fetch_monthly_geojson(start: str, end: str, scale_m: int = 27800) -> dict:
    try:
        import ee
    except ImportError as exc:
        raise SystemExit(
            "earthengine-api is not installed. Install it in the GEE environment, "
            "authenticate (`earthengine authenticate`), then re-run. "
            "Do not add xarray/netcdf4 for this job."
        ) from exc

    ee.Initialize()
    region = ee.Geometry.Rectangle(
        [BOTSWANA["min_lon"], BOTSWANA["min_lat"], BOTSWANA["max_lon"], BOTSWANA["max_lat"]]
    )
    collection = (
        ee.ImageCollection(COLLECTION)
        .filterDate(start, end)
        .filterBounds(region)
        .select(BAND)
    )
    mean = collection.mean().clip(region)
    samples = mean.sample(
        region=region,
        scale=scale_m,
        geometries=True,
    )
    features = samples.getInfo()
    for feature in features.get("features", []):
        props = feature.setdefault("properties", {})
        props["gws_tavg_mm"] = props.pop(BAND, None)
        props["source"] = COLLECTION
        props["band"] = BAND
        props["data_trust_level"] = "screening"
        props["evidence_confidence"] = 0.45
        props["resolution_note"] = "~27.8 km GLDAS CLSM; not a well-point measurement"
    features["properties"] = {
        "collection": COLLECTION,
        "band": BAND,
        "start": start,
        "end": end,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "units": "mm",
        "data_trust_level": "screening",
    }
    return features


def main() -> None:
    parser = argparse.ArgumentParser(description="Export GLDAS gws_tavg monthly mean as GeoJSON via Earth Engine.")
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2023-12-31")
    parser.add_argument("--output", default="public/data/exports/gldas_monthly.geojson")
    args = parser.parse_args()
    payload = fetch_monthly_geojson(args.start, args.end)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out} ({len(payload.get('features', []))} cells)")


if __name__ == "__main__":
    main()
