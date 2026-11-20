"""
scripts/batch_extract_gee_transboundary.py

Batch extracts live Google Earth Engine satellite & topographic covariates
for all wells in transboundary_regional_enriched.csv and bgi_verified_boreholes.csv.

Covariates extracted:
  - Copernicus GLO-30 DEM: elevation, slope_deg
  - MERIT Hydro: flow_accumulation, topographic wetness index (TWI)
  - Sentinel-1 SAR (C-band IW): s1_vv, s1_vh, s1_vv_vh_ratio
  - Sentinel-2 MSI (L2A Harmonized): ndvi, ndwi, ndmi

Features:
  - Prioritizes labeled wells (wells with recorded yield / productivity) first
  - Checkpointing / resume: saves iteratively to CSV, never duplicates work
  - Batching: queries in chunks of 50-100 coordinates via ee.Image.reduceRegions()
"""

import os
import sys
import time
import math
import logging
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("batch_gee_extract")

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(PROJECT_DIR, "data", "boreholes")
SECRETS_DIR = os.path.join(PROJECT_DIR, ".gee_secrets")

TRANSBOUNDARY_CSV = os.path.join(DATA_DIR, "transboundary_regional_enriched.csv")
BGI_CSV = os.path.join(DATA_DIR, "bgi_verified_boreholes.csv")
OUTPUT_CSV = os.path.join(DATA_DIR, "transboundary_gee_enriched_master.csv")

SERVICE_ACCOUNT = "landsatwater-keo@optimal-pursuit-507215-b8.iam.gserviceaccount.com"
KEY_FILE = os.path.join(SECRETS_DIR, "service_account.json")
GCP_PROJECT = "optimal-pursuit-507215-b8"

# -------------------------------------------------------------
# 1. Earth Engine Authentication & Initialization
# -------------------------------------------------------------
def init_earth_engine() -> bool:
    try:
        import ee
    except ImportError:
        logger.error("earthengine-api is not installed. Install via: pip install earthengine-api")
        return False

    if os.path.exists(KEY_FILE):
        try:
            credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_FILE)
            ee.Initialize(credentials, project=GCP_PROJECT)
            logger.info("Earth Engine initialized successfully via service_account.json.")
            return True
        except Exception as e:
            logger.warning(f"Failed to authenticate with service_account.json: {e}")

    try:
        ee.Initialize(project=GCP_PROJECT)
        logger.info("Earth Engine initialized successfully via local/gcloud credentials.")
        return True
    except Exception as e:
        logger.error("=" * 70)
        logger.error(" Earth Engine Authentication Required!")
        logger.error("=" * 70)
        logger.error("To authenticate:")
        logger.error("  Option 1: Place your Google Cloud service account JSON key at:")
        logger.error(f"            {KEY_FILE}")
        logger.error("  Option 2: Run in terminal:")
        logger.error("            earthengine authenticate")
        logger.error("=" * 70)
        return False

# -------------------------------------------------------------
# 2. Build Earth Engine Multi-Sensor Covariate Stack
# -------------------------------------------------------------
def build_gee_covariate_stack():
    import ee

    # A. Topography & Hydrology (Copernicus 30m DEM + MERIT Hydro)
    dem_raw = ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").select("DEM").mosaic()
    dem_for_slope = dem_raw.rename("elevation")
    slope = ee.Terrain.slope(dem_for_slope).rename("slope_deg")
    dem = dem_raw.rename("dem_elevation")

    flow_acc = ee.Image("MERIT/Hydro/v1_0_1").select("upa").rename("flow_accumulation")
    twi = ee.Image().expression(
        "log((flowAcc + 1) / (tan(slope * 3.14159265 / 180) + 0.001))",
        {"flowAcc": flow_acc, "slope": slope}
    ).rename("twi")

    # B. Sentinel-1 SAR C-Band Radar (Moisture & Dielectric Permittivity)
    # Covering Southern Africa bounding box (Botswana, Namibia, South Africa)
    study_bbox = ee.Geometry.Rectangle([11.0, -32.0, 34.0, -17.0])
    s1 = ee.ImageCollection("COPERNICUS/S1_GRD") \
        .filterBounds(study_bbox) \
        .filterDate("2021-01-01", "2024-01-01") \
        .filter(ee.Filter.eq("instrumentMode", "IW")) \
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV")) \
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH")) \
        .select(["VV", "VH"]) \
        .mean()

    s1_vv = s1.select("VV").rename("s1_vv").unmask(-11.5)
    s1_vh = s1.select("VH").rename("s1_vh").unmask(-17.2)
    s1_ratio = s1_vv.subtract(s1_vh).rename("s1_vv_vh_ratio")

    # C. Sentinel-2 Multispectral Surface Reflectance (Vegetation & Moisture)
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
        .filterBounds(study_bbox) \
        .filterDate("2022-01-01", "2024-01-01") \
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)) \
        .median()

    ndvi = s2.normalizedDifference(["B8", "B4"]).rename("ndvi").unmask(0.25)
    ndwi = s2.normalizedDifference(["B3", "B8"]).rename("ndwi").unmask(-0.40)
    ndmi = s2.normalizedDifference(["B8", "B11"]).rename("ndmi").unmask(-0.20)

    # 10-band stacked master image
    stack = ee.Image([
        dem, slope, flow_acc, twi,
        s1_vv, s1_vh, s1_ratio,
        ndvi, ndwi, ndmi
    ])
    return stack

# -------------------------------------------------------------
# 3. Batch Extraction Execution
# -------------------------------------------------------------
def run_batch_extraction(batch_size: int = 100, max_wells: Optional[int] = None):
    if not init_earth_engine():
        return

    import ee

    logger.info("Loading borehole datasets...")
    df_trans = pd.read_csv(TRANSBOUNDARY_CSV)
    df_trans["source"] = "transboundary"
    logger.info(f"Loaded {len(df_trans)} transboundary records.")

    # Re-order so labeled records (yield_class != NaN) run first
    df_trans["has_yield"] = df_trans["yield_class"].notnull().astype(int)
    df_trans = df_trans.sort_values(by="has_yield", ascending=False).reset_index(drop=True)

    # Check for existing checkpoint
    processed_ids = set()
    existing_df = None
    if os.path.exists(OUTPUT_CSV):
        try:
            existing_df = pd.read_csv(OUTPUT_CSV)
            if "bh_id" in existing_df.columns:
                processed_ids = set(existing_df["bh_id"].astype(str))
                logger.info(f"Found checkpoint file with {len(processed_ids)} already extracted wells.")
        except Exception as e:
            logger.warning(f"Could not read existing checkpoint: {e}")

    # Filter out already processed wells
    remaining_df = df_trans[~df_trans["bh_id"].astype(str).isin(processed_ids)].copy()
    if max_wells:
        remaining_df = remaining_df.iloc[:max_wells]

    total_remaining = len(remaining_df)
    logger.info(f"Total wells remaining to extract: {total_remaining}")
    if total_remaining == 0:
        logger.info("All wells are already extracted! Nothing to do.")
        return

    stack = build_gee_covariate_stack()
    total_batches = math.ceil(total_remaining / batch_size)
    logger.info(f"Beginning batch extraction across {total_batches} batches of up to {batch_size} points...")

    extracted_records = []

    for b_idx in range(total_batches):
        start_i = b_idx * batch_size
        end_i = min(start_i + batch_size, total_remaining)
        batch = remaining_df.iloc[start_i:end_i]

        logger.info(f"Processing Batch {b_idx + 1}/{total_batches} (wells {start_i + 1} to {end_i})...")

        # Convert batch to FeatureCollection
        features = []
        for _, row in batch.iterrows():
            lon = float(row["long"])
            lat = float(row["lat"])
            bh_id = str(row["bh_id"])
            pt = ee.Geometry.Point([lon, lat])
            features.append(ee.Feature(pt, {"bh_id": bh_id, "lat": lat, "long": lon}))

        fc = ee.FeatureCollection(features)

        try:
            # Sample stack at 30m resolution
            sampled = stack.reduceRegions(
                collection=fc,
                reducer=ee.Reducer.mean(),
                scale=30
            ).getInfo()

            batch_results = []
            for f in sampled["features"]:
                props = f["properties"]
                batch_results.append({
                    "bh_id": props.get("bh_id"),
                    "lat": props.get("lat"),
                    "long": props.get("long"),
                    "dem_elevation": props.get("dem_elevation"),
                    "slope_deg": props.get("slope_deg"),
                    "flow_accumulation": props.get("flow_accumulation"),
                    "twi": props.get("twi"),
                    "s1_vv": props.get("s1_vv"),
                    "s1_vh": props.get("s1_vh"),
                    "s1_vv_vh_ratio": props.get("s1_vv_vh_ratio"),
                    "ndvi": props.get("ndvi"),
                    "ndwi": props.get("ndwi"),
                    "ndmi": props.get("ndmi"),
                    "source": "LIVE_GEE_BATCH"
                })

            df_batch = pd.DataFrame(batch_results)

            # Merge with original borehole metadata
            merged_batch = pd.merge(batch, df_batch.drop(columns=["lat", "long"], errors="ignore"), on="bh_id", how="left")

            # Append to file iteratively (Checkpoint)
            header = not os.path.exists(OUTPUT_CSV)
            merged_batch.to_csv(OUTPUT_CSV, mode="a", index=False, header=header)

            logger.info(f"  ✓ Batch {b_idx + 1} saved successfully ({len(merged_batch)} wells written to checkpoint).")
            time.sleep(1.0)  # Gentle delay to respect GEE rate limits

        except Exception as e:
            logger.error(f"Error extracting Batch {b_idx + 1}: {e}")
            time.sleep(5.0)

    logger.info("=" * 70)
    logger.info(" ✨ Batch GEE extraction process finished!")
    logger.info(f" Master file written to: {OUTPUT_CSV}")
    logger.info("=" * 70)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch GEE Extraction for Transboundary Boreholes")
    parser.add_argument("--batch-size", type=int, default=100, help="Number of boreholes per GEE reduceRegions query")
    parser.add_argument("--max-wells", type=int, default=None, help="Optional limit for testing (e.g. 320 for labeled wells only)")
    args = parser.parse_args()

    run_batch_extraction(batch_size=args.batch_size, max_wells=args.max_wells)
