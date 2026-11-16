#!/usr/bin/env python3
"""
fetch_open_borehole_data.py

Pull open borehole / water-point data for Botswana and neighbouring areas and
map it onto the columns the water-potential model trains on.

Sources
  1. Stampriet Transboundary Aquifer System boreholes (GeoNode WFS, DWS South Africa)
     https://data.amerigeoss.org/it/dataset/boreholes-in-the-stampriet-transboundary-aquifer-system
  2. Water Point Data Exchange (WPdx-Basic, Socrata API, CC BY)
     https://data.waterpointdata.org/dataset/Water-Point-Data-Exchange-WPDx-Basic-/jfkt-jmqa/data

Usage
  pip install requests pandas            # geopandas optional (boundary filter, shapefile fallback)
  python fetch_open_borehole_data.py --out data/boreholes/open_boreholes.csv
  python fetch_open_borehole_data.py --selftest     # offline logic check, no network

IMPORTANT - read before training on the output
  * Column names in both sources are discovered at run time (fuzzy matching),
    because they were not verified before this script was written. Check the
    printed "columns used" lines and the summary.
  * WPdx has NO drilling yield. A *functional* borehole means water was found
    (weak positive label). A *non-functional* one is usually a broken pump, NOT
    a dry hole, so it is left unlabelled unless you pass
    --wpdx-nonfunctional-as-negative (not recommended).
  * Align --yield-threshold-m3h with how is_productive is defined in your own
    bgi_verified_boreholes.csv, or the pooled labels will not be comparable.
  * Check each source's licence before commercial use. Always report model
    performance on Botswana-only held-out boreholes, not on the pooled set.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

try:
    import requests
except ImportError:  # selftest does not need it
    requests = None

# ---------------------------------------------------------------- config ----
# Exact download links copied from the AmeriGEOSS dataset page
# (https://data.amerigeoss.org/dataset/boreholes-in-the-stampriet-transboundary-aquifer-system).
# The page lists them with http://, and the server may only answer on https://,
# so every link is tried on both. Tried in order until one works.
_B = "ihp-wins.unesco.org/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typename=geonode%3Aboreholestas"
STAMPRIET_CANDIDATES = [
    f"http://{_B}&outputFormat=json&srs=EPSG%3A4326&srsName=EPSG%3A4326",
    f"https://{_B}&outputFormat=json&srs=EPSG%3A4326&srsName=EPSG%3A4326",
    f"http://{_B}&outputFormat=SHAPE-ZIP&srs=EPSG%3A4326&format_options=charset%3AUTF-8",
    f"https://{_B}&outputFormat=SHAPE-ZIP&srs=EPSG%3A4326&format_options=charset%3AUTF-8",
    f"http://{_B}&outputFormat=csv&srs=EPSG%3A4326",
    f"https://{_B}&outputFormat=csv&srs=EPSG%3A4326",
    "http://ihp-wins.unesco.org/download/1048",   # "original dataset" zip
    "https://ihp-wins.unesco.org/download/1048",
]
DEFAULT_STAMPRIET_URL = STAMPRIET_CANDIDATES[0]
WPDX_URL = "https://data.waterpointdata.org/resource/jfkt-jmqa.json"

# Botswana is roughly lon 20-29.4, lat -26.9 to -17.8. Default box adds a buffer
# for neighbouring Kalahari-fringe geology (Namibia, South Africa, Zimbabwe).
DEFAULT_BBOX = (17.5, -28.5, 31.0, -16.5)  # min_lon, min_lat, max_lon, max_lat
DEFAULT_COUNTRIES = ["Botswana", "Namibia", "South Africa", "Zimbabwe", "Zambia"]

OUT_COLUMNS = [
    "source", "source_id", "country", "longitude", "latitude", "drill_date",
    "depth_m", "yield_m3h", "static_water_level_m", "water_source",
    "status_raw", "is_productive", "label_quality", "yield_column_used",
]

YIELD_CANDS = ["yield", "blowyield", "bhyield", "yieldls", "yieldm3h", "yld", "pumpyield", "testyield", "discharge"]
DEPTH_CANDS = ["depth", "totaldepth", "boreholedepth", "bhdepth", "drilleddepth"]
SWL_CANDS = ["staticwaterlevel", "swl", "waterlevel", "restwaterlevel", "wl"]
DATE_CANDS = ["drilldate", "datedrilled", "constructiondate", "completiondate", "date", "year"]
ID_CANDS = ["boreholeid", "bhid", "stationid", "siteid", "id", "name", "fid"]
COUNTRY_CANDS = ["country", "countryname", "ctry"]


# --------------------------------------------------------------- helpers ----
def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def pick(df: pd.DataFrame, cands: list[str]) -> str | None:
    """First column whose normalised name equals a candidate, else contains one."""
    cols = {norm(c): c for c in df.columns}
    for cand in cands:
        if cand in cols:
            return cols[cand]
    for cand in cands:
        for n, c in cols.items():
            if cand in n:
                return c
    return None


def to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", ".", regex=False)
                         .str.extract(r"(-?\d+\.?\d*)")[0], errors="coerce")


def yield_factor_to_m3h(colname: str, forced: str | None) -> tuple[float, bool]:
    """Return (multiplier to m3/h, unit_was_verified)."""
    unit = forced
    if unit is None:
        n = colname.lower()
        if re.search(r"(l/s|lps|ls\b|_ls|l_s)", n):
            unit = "ls"
        elif re.search(r"(m3/h|m3h|m3_h|cmh)", n):
            unit = "m3h"
    if unit == "ls":
        return 3.6, True
    if unit == "m3h":
        return 1.0, True
    return 1.0, False  # unknown: assume m3/h, flag it


def parse_dates(series: pd.Series) -> pd.Series:
    d = pd.to_datetime(series, errors="coerce")
    bad = d.dt.year.lt(1900) | d.dt.year.gt(pd.Timestamp.today().year)
    return d.mask(bad)


def apply_geo_filter(df: pd.DataFrame, bbox, boundary: str | None) -> pd.DataFrame:
    min_lon, min_lat, max_lon, max_lat = bbox
    m = (df.longitude.between(min_lon, max_lon)) & (df.latitude.between(min_lat, max_lat))
    df = df[m].copy()
    if boundary:
        try:
            import geopandas as gpd
        except ImportError:
            print("  (geopandas not installed; skipping --boundary filter)")
            return df
        poly = gpd.read_file(boundary).to_crs(4326)
        pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs=4326)
        df = gpd.sjoin(pts, poly[["geometry"]], predicate="within").drop(columns=["geometry", "index_right"])
        df = pd.DataFrame(df)
    return df


# ------------------------------------------------------------- Stampriet ----
def load_stampriet(url: str, file: str | None) -> pd.DataFrame:
    if file:
        p = Path(file)
        if p.suffix.lower() in (".json", ".geojson"):
            import json
            return geojson_to_df(json.loads(p.read_text(encoding="utf-8")))
        if p.suffix.lower() == ".csv":
            return pd.read_csv(p)
        import geopandas as gpd  # zip / shp
        g = gpd.read_file(p).to_crs(4326)
        df = pd.DataFrame(g.drop(columns="geometry"))
        df["longitude"], df["latitude"] = g.geometry.x, g.geometry.y
        return df
    if requests is None:
        sys.exit("pip install requests")
    urls = [url] if url != DEFAULT_STAMPRIET_URL else STAMPRIET_CANDIDATES
    errors = []
    for u in urls:
        try:
            r = requests.get(u, timeout=120, allow_redirects=True)
            r.raise_for_status()
            df = parse_stampriet_bytes(r.content)
            if len(df):
                print(f"  Stampriet loaded from: {u}  ({len(df)} rows)")
                return df
            errors.append(f"{u} -> parsed 0 point rows")
        except Exception as e:  # try the next candidate
            errors.append(f"{u} -> {e}")
    raise RuntimeError("all Stampriet URLs failed:\n    " + "\n    ".join(errors))


def parse_stampriet_bytes(b: bytes) -> pd.DataFrame:
    """GeoJSON, zipped shapefile or WFS CSV (WKT geometry) -> DataFrame with longitude/latitude."""
    head = b[:200].lstrip()
    if head.startswith(b"{"):
        import json
        return geojson_to_df(json.loads(b.decode("utf-8", "replace")))
    if head.startswith(b"PK"):
        import geopandas as gpd  # needs geopandas for shapefiles
        g = gpd.read_file(io.BytesIO(b)).to_crs(4326)
        df = pd.DataFrame(g.drop(columns="geometry"))
        df["longitude"], df["latitude"] = g.geometry.x, g.geometry.y
        return df
    df = pd.read_csv(io.BytesIO(b))
    geo = pick(df, ["thegeom", "geom", "wkt", "geometry"])
    if geo is None:
        lon, lat = pick(df, ["longitude", "lon", "x"]), pick(df, ["latitude", "lat", "y"])
        if not (lon and lat):
            raise ValueError("CSV has no geometry or lon/lat columns")
        df["longitude"], df["latitude"] = to_num(df[lon]), to_num(df[lat])
        return df
    xy = df[geo].astype(str).str.extract(r"POINT\s*\(\s*(-?[\d.]+)\s+(-?[\d.]+)")
    df["longitude"], df["latitude"] = pd.to_numeric(xy[0]), pd.to_numeric(xy[1])
    return df.dropna(subset=["longitude", "latitude"])


def geojson_to_df(gj: dict) -> pd.DataFrame:
    rows = []
    for f in gj.get("features", []):
        geom = f.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        row = dict(f.get("properties") or {})
        row["longitude"], row["latitude"] = geom["coordinates"][:2]
        row["_fid"] = f.get("id")
        rows.append(row)
    return pd.DataFrame(rows)


def standardise_stampriet(raw: pd.DataFrame, threshold_m3h: float, unit: str | None) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=OUT_COLUMNS)
    y_col = pick(raw, YIELD_CANDS)
    d_col, s_col = pick(raw, DEPTH_CANDS), pick(raw, SWL_CANDS)
    t_col, i_col, c_col = pick(raw, DATE_CANDS), pick(raw, ID_CANDS), pick(raw, COUNTRY_CANDS)
    print(f"  Stampriet columns used -> yield={y_col}, depth={d_col}, swl={s_col}, "
          f"date={t_col}, id={i_col}, country={c_col}")
    out = pd.DataFrame(index=raw.index)
    out["source"] = "stampriet_dws"
    out["source_id"] = raw[i_col].astype(str) if i_col else raw.get("_fid", pd.Series(raw.index)).astype(str)
    out["country"] = raw[c_col] if c_col else pd.NA
    out["longitude"], out["latitude"] = raw["longitude"].astype(float), raw["latitude"].astype(float)
    out["drill_date"] = parse_dates(raw[t_col]) if t_col else pd.NaT
    out["depth_m"] = to_num(raw[d_col]) if d_col else float("nan")
    out["static_water_level_m"] = to_num(raw[s_col]) if s_col else float("nan")
    out["water_source"] = "borehole"
    out["status_raw"] = pd.NA
    if y_col:
        mult, verified = yield_factor_to_m3h(y_col, unit)
        out["yield_m3h"] = to_num(raw[y_col]) * mult
        out["yield_column_used"] = y_col
        out["is_productive"] = (out.yield_m3h >= threshold_m3h).astype("Int64").where(out.yield_m3h.notna())
        out["label_quality"] = "yield_threshold" if verified else "yield_threshold_unit_unverified"
        if not verified:
            print(f"  WARNING: unit of '{y_col}' unknown, assumed m3/h. Pass --stampriet-yield-unit ls|m3h.")
    else:
        out["yield_m3h"], out["is_productive"] = float("nan"), pd.NA
        out["yield_column_used"], out["label_quality"] = pd.NA, "no_yield_available"
        print("  WARNING: no yield column found; Stampriet rows are unlabelled.")
    return out.reindex(columns=OUT_COLUMNS)


# ------------------------------------------------------------------ WPdx ----
def load_wpdx(countries: list[str], bbox, max_rows: int) -> pd.DataFrame:
    if requests is None:
        sys.exit("pip install requests")
    probe = requests.get(WPDX_URL, params={"$limit": 1}, timeout=60)
    probe.raise_for_status()
    probe_df = pd.DataFrame(probe.json())
    c_col = pick(probe_df, ["clean_country_name", "country_name", "country"])
    lat_col = pick(probe_df, ["lat_deg", "latdeg", "lat", "latitude"])
    lon_col = pick(probe_df, ["lon_deg", "londeg", "lon", "longitude"])
    print(f"  WPdx columns used -> country={c_col}, lat={lat_col}, lon={lon_col}")
    if not (lat_col and lon_col):
        sys.exit("Could not find lat/lon columns in WPdx; inspect " + WPDX_URL + "?$limit=1")
    min_lon, min_lat, max_lon, max_lat = bbox
    where = [f"{lat_col} between {min_lat} and {max_lat}", f"{lon_col} between {min_lon} and {max_lon}"]
    if c_col:
        names = ",".join("'" + c.replace("'", "''") + "'" for c in countries)
        where.append(f"{c_col} in ({names})")
    frames, offset, page = [], 0, 50000
    while offset < max_rows:
        r = requests.get(WPDX_URL, params={"$where": " AND ".join(where), "$limit": min(page, max_rows - offset),
                                           "$offset": offset, "$order": ":id"}, timeout=180)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        frames.append(pd.DataFrame(rows))
        offset += len(rows)
        print(f"  WPdx rows fetched: {offset}")
        if len(rows) < page:
            break
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def standardise_wpdx(raw: pd.DataFrame, nonfunc_negative: bool) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=OUT_COLUMNS)
    lat, lon = pick(raw, ["lat_deg", "latdeg", "lat", "latitude"]), pick(raw, ["lon_deg", "londeg", "lon", "longitude"])
    st = pick(raw, ["status_clean", "status_id", "statusclean", "status"])
    src = pick(raw, ["water_source_clean", "watersourceclean", "watersource", "source"])
    yr = pick(raw, ["install_year", "installyear", "yearinstalled", "install"])
    cn, wid = pick(raw, COUNTRY_CANDS), pick(raw, ["row_id", "wpdxid", "id"])
    print(f"  WPdx standardise -> status={st}, source={src}, install_year={yr}")
    df = raw.copy()
    if src:  # keep boreholes / tubewells only; springs, rain tanks etc. say nothing about drilling
        df = df[df[src].astype(str).str.contains(r"borehole|tube ?well|deep well", case=False, regex=True)]
    else:
        print("  WARNING: no water-source column; keeping all water points.")
    out = pd.DataFrame(index=df.index)
    out["source"] = "wpdx"
    out["source_id"] = df[wid].astype(str) if wid else df.index.astype(str)
    out["country"] = df[cn] if cn else pd.NA
    out["longitude"], out["latitude"] = to_num(df[lon]), to_num(df[lat])
    out["drill_date"] = parse_dates(pd.to_datetime(df[yr].astype(str) + "-01-01", errors="coerce")) if yr else pd.NaT
    out["depth_m"] = out["yield_m3h"] = out["static_water_level_m"] = float("nan")
    out["water_source"] = df[src] if src else pd.NA
    out["status_raw"] = df[st] if st else pd.NA
    s = df[st].astype(str).str.strip().str.lower() if st else pd.Series("", index=df.index)
    functional = s.isin(["yes", "functional", "true"]) | s.str.startswith("functional")
    broken = s.isin(["no", "false"]) | s.str.startswith("non-functional") | s.str.startswith("non functional")
    lab = pd.Series(pd.NA, index=df.index, dtype="Int64")
    lab[functional] = 1
    if nonfunc_negative:
        lab[broken] = 0
    out["is_productive"] = lab
    out["label_quality"] = "weak_functional_water_point"
    out["yield_column_used"] = pd.NA
    return out.dropna(subset=["longitude", "latitude"]).reindex(columns=OUT_COLUMNS)


# ------------------------------------------------------------------ main ----
def combine(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=OUT_COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    df["_k"] = df.longitude.round(5).astype(str) + "_" + df.latitude.round(5).astype(str)
    df = df.sort_values("yield_m3h", na_position="last").drop_duplicates(["source", "_k"]).drop(columns="_k")
    return df.reindex(columns=OUT_COLUMNS)


def summarise(df: pd.DataFrame) -> None:
    print("\n=== SUMMARY ===")
    print(f"rows: {len(df)}")
    if df.empty:
        return
    print(df.groupby("source").size().to_string())
    print("\nlabel counts (1=productive, 0=dry/low-yield, NA=unlabelled):")
    for src, g in df.groupby("source"):
        lab = g["is_productive"]
        print(f"  {src}: productive={int((lab == 1).sum())}, "
              f"dry/low={int((lab == 0).sum())}, unlabelled={int(lab.isna().sum())}")
    print(f"\nrows with a real yield value: {int(df.yield_m3h.notna().sum())}")
    print("Reminder: report model results on Botswana-only held-out boreholes.")


def selftest() -> None:
    gj = {"features": [
        {"id": "a1", "geometry": {"type": "Point", "coordinates": [20.5, -24.0]},
         "properties": {"BH_ID": "S1", "Yield_l_s": "2.0", "Depth": "80", "Date_Drilled": "2005-03-01", "Country": "Namibia"}},
        {"id": "a2", "geometry": {"type": "Point", "coordinates": [21.0, -24.5]},
         "properties": {"BH_ID": "S2", "Yield_l_s": "0.05", "Depth": "60", "Date_Drilled": "0000-00-00", "Country": "Botswana"}},
        {"id": "a3", "geometry": {"type": "Point", "coordinates": [100.0, 10.0]}, "properties": {"BH_ID": "far"}},
    ]}
    st = standardise_stampriet(geojson_to_df(gj), threshold_m3h=1.0, unit=None)
    assert st.loc[0, "yield_m3h"] == 7.2 and st.loc[0, "is_productive"] == 1, st
    assert st.loc[1, "is_productive"] == 0 and pd.isna(st.loc[1, "drill_date"]), st
    st = apply_geo_filter(st, DEFAULT_BBOX, None)
    assert len(st) == 2, "bbox filter should drop the far point"

    wp = pd.DataFrame({"lat_deg": ["-22.0", "-22.1", "-22.2"], "lon_deg": ["24.0", "24.1", "24.2"],
                       "status_id": ["Yes", "No", "Yes"], "water_source_clean": ["Borehole", "Borehole", "Protected Spring"],
                       "country_name": ["Botswana"] * 3, "wpdx_id": ["w1", "w2", "w3"], "install_year": ["2010", "2012", "2015"]})
    w = standardise_wpdx(wp, nonfunc_negative=False)
    assert len(w) == 2 and w.is_productive.tolist() == [1, pd.NA], w
    w2 = standardise_wpdx(wp, nonfunc_negative=True)
    assert w2.is_productive.tolist() == [1, 0], w2
    out = combine([st, w])
    assert list(out.columns) == OUT_COLUMNS and len(out) == 4
    summarise(out)
    print("\nSELFTEST OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/boreholes/open_boreholes.csv")
    ap.add_argument("--yield-threshold-m3h", type=float, default=1.0,
                    help="yield >= this counts as productive (match your BGI label definition)")
    ap.add_argument("--stampriet-url", default=DEFAULT_STAMPRIET_URL,
                    help="override; by default all known links from the dataset page are tried")
    ap.add_argument("--stampriet-file", help="local .geojson/.csv/.zip(shapefile) instead of the URL")
    ap.add_argument("--stampriet-yield-unit", choices=["ls", "m3h"], help="force the yield unit")
    ap.add_argument("--countries", nargs="+", default=DEFAULT_COUNTRIES, help="WPdx country filter")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
                    default=list(DEFAULT_BBOX))
    ap.add_argument("--boundary", help="optional polygon file (e.g. Botswana + buffer) for a precise filter; needs geopandas")
    ap.add_argument("--wpdx-max-rows", type=int, default=200000)
    ap.add_argument("--wpdx-nonfunctional-as-negative", action="store_true",
                    help="NOT recommended: treats broken pumps as dry holes")
    ap.add_argument("--skip-stampriet", action="store_true")
    ap.add_argument("--skip-wpdx", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    frames = []
    if not a.skip_stampriet:
        print("Stampriet ...")
        try:
            frames.append(standardise_stampriet(load_stampriet(a.stampriet_url, a.stampriet_file),
                                                a.yield_threshold_m3h, a.stampriet_yield_unit))
        except Exception as e:  # keep going so WPdx can still run
            print(f"  Stampriet failed: {e}\n  -> download the file in your browser from the dataset page and "
                  "pass it with --stampriet-file")
    if not a.skip_wpdx:
        print("WPdx ...")
        try:
            frames.append(standardise_wpdx(load_wpdx(a.countries, tuple(a.bbox), a.wpdx_max_rows),
                                           a.wpdx_nonfunctional_as_negative))
        except Exception as e:
            print(f"  WPdx failed: {e}")

    df = combine([apply_geo_filter(f, tuple(a.bbox), a.boundary) for f in frames if not f.empty])
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    summarise(df)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
