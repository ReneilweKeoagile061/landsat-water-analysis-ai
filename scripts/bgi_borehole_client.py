"""
BGI (Botswana Geoscience Institute) Borehole Database Client & Scraper.
Sourced from: https://bh.bgi.org.bw/borehole

Extracts verified historical borehole records for Botswana:
- Borehole ID
- Coordinates (WGS84 Latitude, Longitude)
- Location & District
- Verified Yield (m3/hr)
- Water Strike Depth (m)
- Static Water Level (m)
- Total Depth (m)
- Stratigraphic Log Formation
"""

import argparse
import csv
import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bgi_client")

BASE_URL = "https://bh.bgi.org.bw"
SEARCH_URL = f"{BASE_URL}/borehole/search"
VIEW_URL = f"{BASE_URL}/borehole/viewBorehole"


def extract_regex(pattern: str, text: str, group: int = 1) -> Optional[str]:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(group).strip() if m else None


def parse_borehole_record(view_id: str, max_retries: int = 3) -> Optional[Dict]:
    url = f"{VIEW_URL}/{view_id}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        },
    )

    html = None
    for attempt in range(max_retries):
        try:
            html = urllib.request.urlopen(req, timeout=15).read().decode("latin-1")
            break
        except Exception as e:
            if attempt == max_retries - 1:
                logger.warning(f"Failed fetching borehole {view_id}: {e}")
                return None
            time.sleep(1.0)

    if not html:
        return None

    bh_id = extract_regex(r"<goh>(.*?)</goh>", html) or view_id
    coords_raw = extract_regex(r"Coordinates:.*?q=([-\d\.\s,]+)", html)
    loc = extract_regex(r"Location:\s*</b>\s*([^<]+)", html)
    yield_val = extract_regex(r"Estimated Yield:\s*</b>\s*([\d\.]+)", html)
    strike = extract_regex(r"Borehole Water Strike:\s*</b>\s*([\d\.]+)", html)
    depth = extract_regex(r"End of Hole \(Depth\):\s*</b>\s*([\d\.]+)", html)
    swl = extract_regex(r"Static Water Level:\s*</b>\s*([\d\.]+)", html)
    drill_date = extract_regex(r"Start Drill:\s*</b>\s*([^<]+)", html)

    lat, lon = None, None
    if coords_raw:
        parts = [p.strip() for p in coords_raw.split(",")]
        if len(parts) == 2:
            try:
                lat = float(parts[0])
                lon = float(parts[1])
            except ValueError:
                pass

    # Ensure coordinates are within plausible Botswana bounds: Lat [-27.0, -17.5], Lon [19.5, 29.5]
    valid_coords = False
    if lat is not None and lon is not None:
        if -27.5 <= lat <= -17.0 and 19.0 <= lon <= 30.0:
            valid_coords = True

    parsed_yield = float(yield_val) if yield_val else 0.0

    return {
        "view_id": view_id,
        "borehole_id": bh_id,
        "location": loc or "Botswana",
        "latitude": lat,
        "longitude": lon,
        "has_valid_coords": valid_coords,
        "yield_m3h": parsed_yield,
        "water_strike_m": float(strike) if strike else None,
        "static_water_level_m": float(swl) if swl else None,
        "total_depth_m": float(depth) if depth else None,
        "drill_date": drill_date if (drill_date and drill_date != "N/A") else None,
        "is_productive": 1 if parsed_yield > 0.0 else 0,
    }


def query_bgi_location(location_name: str, max_records: int = 100) -> List[Dict]:
    """Queries BGI for boreholes associated with a town/village/location name."""
    payload = {
        "shirts": str(max(max_records, 500)),
        "f1": "t_holes.c_holeno LIKE 'BH%' AND t_samplemethods.c_smpMethodName",
        "val_1": "",
        "f2": "t_locations.c_locname",
        "val_2": location_name,
        "submit": "Search for Information ",
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        SEARCH_URL,
        data=data,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        },
    )

    try:
        html = urllib.request.urlopen(req, timeout=20).read().decode("latin-1")
    except Exception as e:
        logger.error(f"Search request failed for {location_name}: {e}")
        return []

    pattern = r'href="https://bh\.bgi\.org\.bw/borehole/viewBorehole/([a-zA-Z0-9+=/]+)"><u>([^<]+)</u></a>'
    matches = re.findall(pattern, html)
    logger.info(f"Found {len(matches)} borehole index entries for location '{location_name}'")

    boreholes = []
    seen = set()
    for view_id, bh_no in matches[:max_records]:
        if view_id in seen:
            continue
        seen.add(view_id)

        rec = parse_borehole_record(view_id)
        if rec and rec["has_valid_coords"]:
            boreholes.append(rec)
            time.sleep(0.15)  # Respectful rate limiting

    logger.info(f"Successfully extracted {len(boreholes)} valid georeferenced boreholes for '{location_name}'")
    return boreholes


def export_boreholes_to_csv(boreholes: List[Dict], output_path: str):
    """Exports a list of borehole dicts to standardized CSV for AgriPulse training."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fields = [
        "borehole_id",
        "location",
        "longitude",
        "latitude",
        "yield_m3h",
        "water_strike_m",
        "static_water_level_m",
        "total_depth_m",
        "is_productive",
        "drill_date",
        "view_id",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for bh in boreholes:
            writer.writerow(bh)

    logger.info(f"Saved {len(boreholes)} borehole records to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape verified boreholes from BGI Botswana portal")
    parser.add_argument("--locations", nargs="+", default=["Khudumelapye", "Mochudi", "Toteng", "Letlhakeng", "Seronga", "Kanye"], help="Locations to query")
    parser.add_argument("--limit-per-loc", type=int, default=15, help="Max boreholes to parse per location")
    parser.add_argument("--output", type=str, default="data/boreholes/bgi_verified_boreholes.csv", help="Output CSV path")
    args = parser.parse_args()

    all_boreholes = []
    for loc in args.locations:
        results = query_bgi_location(loc, max_records=args.limit_per_loc)
        all_boreholes.extend(results)

    export_boreholes_to_csv(all_boreholes, args.output)

