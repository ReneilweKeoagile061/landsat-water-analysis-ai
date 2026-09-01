import urllib.request
import urllib.parse
import re
import csv
import json
import time

def parse_borehole_detail(view_id):
    url = f"https://bh.bgi.org.bw/borehole/viewBorehole/{view_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=12).read().decode("latin-1")
    except Exception as e:
        print(f"Failed {view_id}: {e}")
        return None

    def extract_field(pattern, text):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    bh_id = extract_field(r"<goh>(.*?)</goh>", html)
    coords_raw = extract_field(r"Coordinates:.*?q=([-\d\.\s,]+)", html)
    loc = extract_field(r"Location:\s*</b>\s*([^<]+)", html)
    yield_val = extract_field(r"Estimated Yield:\s*</b>\s*([\d\.]+)", html)
    strike = extract_field(r"Borehole Water Strike:\s*</b>\s*([\d\.]+)", html)
    depth = extract_field(r"End of Hole \(Depth\):\s*</b>\s*([\d\.]+)", html)
    swl = extract_field(r"Static Water Level:\s*</b>\s*([\d\.]+)", html)
    drill_date = extract_field(r"Start Drill:\s*</b>\s*([^<]+)", html)

    lat, lon = None, None
    if coords_raw:
        parts = [p.strip() for p in coords_raw.split(",")]
        if len(parts) == 2:
            try:
                lat = float(parts[0])
                lon = float(parts[1])
            except ValueError:
                pass

    return {
        "view_id": view_id,
        "borehole_id": bh_id,
        "location": loc,
        "latitude": lat,
        "longitude": lon,
        "yield_m3h": float(yield_val) if yield_val else 0.0,
        "water_strike_m": float(strike) if strike else None,
        "static_water_level_m": float(swl) if swl else None,
        "total_depth_m": float(depth) if depth else None,
        "drill_date": drill_date,
        "is_productive": 1 if (yield_val and float(yield_val) > 0) else 0
    }

def search_boreholes(location_name="Khudumelapye", max_results=500):
    url = "https://bh.bgi.org.bw/borehole/search"
    payload = {
        "shirts": str(max_results),
        "f1": "t_holes.c_holeno LIKE 'BH%' AND t_samplemethods.c_smpMethodName",
        "val_1": "",
        "f2": "t_locations.c_locname",
        "val_2": location_name,
        "submit": "Search for Information "
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=15).read().decode("latin-1")
    except Exception as e:
        print(f"Search failed: {e}")
        return []

    # Find viewBorehole links
    matches = re.findall(r'href="https://bh\.bgi\.org\.bw/borehole/viewBorehole/([a-zA-Z0-9+=/]+)"><u>([^<]+)</u></a>.*?<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]+)</td><td[^>]*>([^<]+)</td>', html, re.DOTALL)
    print(f"Found {len(matches)} boreholes for location '{location_name}'")
    results = []
    for m in matches[:10]:
        view_id, bh_no, bh_type, smp_type, loc = m
        results.append({
            "view_id": view_id,
            "borehole_no": bh_no,
            "type": bh_type.strip(),
            "sample_type": smp_type.strip(),
            "location": loc.strip()
        })
    return results

if __name__ == "__main__":
    locs = ["Khudumelapye", "Kanye", "Mochudi", "Toteng"]
    for loc in locs:
        found = search_boreholes(loc)
        print(f"Sample results for {loc}:", found[:3])
        if found:
            detail = parse_borehole_detail(found[0]["view_id"])
            print(f"Detail for {found[0]['borehole_no']}:", detail)

