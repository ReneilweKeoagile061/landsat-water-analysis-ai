"""Query real Planetary Computer STAC metadata for optical and radar scenes."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import requests

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTIONS = {
    "landsat": "landsat-c2-l2",
    "sentinel1": "sentinel-1-rtc",
}


def query_scenes(
    collection: str,
    bbox: tuple[float, float, float, float],
    start: date,
    end: date,
    limit: int,
) -> list[dict]:
    response = requests.get(
        f"{STAC_URL}/search",
        params={
            "collections": COLLECTIONS[collection],
            "bbox": ",".join(str(value) for value in bbox),
            "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
            "limit": limit,
        },
        timeout=60,
    )
    response.raise_for_status()
    features = response.json().get("features", [])
    scenes = []
    for item in features:
        scenes.append(
            {
                "id": item["id"],
                "collection": collection,
                "datetime": item.get("properties", {}).get("datetime"),
                "cloud_cover": item.get("properties", {}).get("eo:cloud_cover"),
                "assets": sorted(item.get("assets", {})),
                "bbox": item.get("bbox"),
            }
        )
    return scenes


def main() -> None:
    parser = argparse.ArgumentParser(description="Query real Planetary Computer Landsat or Sentinel-1 STAC metadata.")
    parser.add_argument("--collection", choices=COLLECTIONS, default="landsat")
    parser.add_argument("--bbox", nargs=4, type=float, default=[22.1, -23.0, 27.0, -18.8], metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    parser.add_argument("--start", type=date.fromisoformat, default=date(2024, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    scenes = query_scenes(args.collection, tuple(args.bbox), args.start, args.end, args.limit)
    payload = {"source": STAC_URL, "collection": COLLECTIONS[args.collection], "scenes": scenes}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
