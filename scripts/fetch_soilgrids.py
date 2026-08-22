"""Fetch real SoilGrids clay observations and enrich a prediction CSV."""

from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
DEPTHS = ("0-5cm", "15-30cm", "60-100cm", "100-200cm")


def fetch_clay(session: requests.Session, lon: float, lat: float) -> dict[str, float]:
    params = [("lon", lon), ("lat", lat), ("property", "clay")]
    params.extend(("depth", depth) for depth in DEPTHS)
    response = session.get(SOILGRIDS_URL, params=params, timeout=30)
    response.raise_for_status()
    layers = response.json().get("properties", {}).get("layers", [])
    if not layers:
        raise ValueError("SoilGrids returned no clay layer")
    values = {}
    for depth in layers[0].get("depths", []):
        label = depth.get("label")
        mean = depth.get("values", {}).get("mean")
        if label in DEPTHS and mean is not None:
            values[f"clay_{label.replace('-', '_').replace('cm', '')}_pct"] = float(mean)
    if not values:
        raise ValueError("SoilGrids returned no clay depth values")
    return values


def enrich_csv(input_csv: Path, output_csv: Path, limit: int | None = None, pause: float = 0.15) -> int:
    frame = pd.read_csv(input_csv)
    required = {"lon_wgs84", "lat_wgs84"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    session = requests.Session()
    queried_at = datetime.now(UTC).isoformat()
    rows = frame.head(limit) if limit else frame
    fetched = 0
    for index, row in rows.iterrows():
        values = fetch_clay(session, float(row["lon_wgs84"]), float(row["lat_wgs84"]))
        for key, value in values.items():
            frame.loc[index, key] = value
        shallow = [value for key, value in values.items() if key in {"clay_0_5_pct", "clay_15_30_pct"}]
        if shallow:
            frame.loc[index, "clay_fraction_pct"] = sum(shallow) / len(shallow)
        frame.loc[index, "subsurface_data_source"] = "ISRIC SoilGrids v2.0"
        frame.loc[index, "subsurface_data_quality"] = "modeled"
        frame.loc[index, "soilgrids_query_date"] = queried_at
        fetched += 1
        if pause:
            time.sleep(pause)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_csv, index=False)
    return fetched


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich prediction CSV with real ISRIC SoilGrids clay data.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--limit", type=int, help="Only enrich the first N rows for a trial run.")
    parser.add_argument("--pause", type=float, default=0.15, help="Seconds between requests.")
    args = parser.parse_args()
    count = enrich_csv(Path(args.input_csv), Path(args.output_csv), args.limit, args.pause)
    print(f"Enriched {count} points from {SOILGRIDS_URL}")


if __name__ == "__main__":
    main()
