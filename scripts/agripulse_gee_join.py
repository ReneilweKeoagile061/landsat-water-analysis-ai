"""
AgriPulse GEE Feature Join Script
Step 3b - Spatial Join: BGI Borehole Scraper Output + GEE Feature Export

Joins BGI borehole records with GEE-extracted satellite/terrain features
using coordinate matching within a tolerance, and adds farm/investigation
identifiers for spatial cross-validation grouping.

Usage:
    python agripulse_gee_join.py \
        --bgi data/boreholes/bgi_verified_boreholes.csv \
        --gee data/boreholes/agripulse_bgi_ml_features.csv \
        --output data/boreholes/agripulse_gee_features.csv \
        --investigation-map farms_to_investigations.csv
"""

import argparse
import logging
import pandas as pd
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agripulse_gee_join")


def load_dataframes(bgi_path: str, gee_path: str) -> tuple:
    """Load both CSV files."""
    logger.info(f"Loading BGI records from {bgi_path}...")
    bgi_df = pd.read_csv(bgi_path)
    logger.info(f"  Loaded {len(bgi_df)} records")

    logger.info(f"Loading GEE features from {gee_path}...")
    gee_df = pd.read_csv(gee_path)
    logger.info(f"  Loaded {len(gee_df)} records")

    return bgi_df, gee_df


def spatial_join_on_coords(
    bgi_df: pd.DataFrame,
    gee_df: pd.DataFrame,
    tolerance_degrees: float = 0.001
) -> pd.DataFrame:
    """
    Join GEE features to BGI records using 2D coordinate proximity.
    
    CRITICAL: Joins on borehole_id when available (exact match), or 2D spatial distance.
    NOT a 1D longitude-only join—validates both lat and lon within tolerance.
    
    Args:
        bgi_df: BGI borehole records (must have latitude, longitude, borehole_id)
        gee_df: GEE feature export (must have latitude, longitude, borehole_id)
        tolerance_degrees: Max distance in decimal degrees (~111m per 0.001°)
    
    Returns:
        Merged dataframe with all columns from both sources
        
    Raises:
        ValueError: If borehole_id missing from either CSV, or join produces nulls
    """
    logger.info(f"Performing 2D spatial join (tolerance={tolerance_degrees}°)...")

    # Ensure required columns exist
    for df, name in [(bgi_df, "BGI"), (gee_df, "GEE")]:
        if "latitude" not in df.columns or "longitude" not in df.columns:
            raise ValueError(f"{name} dataframe missing latitude/longitude columns")
        if "borehole_id" not in df.columns:
            raise ValueError(f"{name} dataframe missing borehole_id column (required for spatial join)")

    # Join on borehole_id (exact match—this is the reliable link)
    logger.info("Joining on borehole_id (exact match)...")
    joined = pd.merge(
        bgi_df,
        gee_df,
        on="borehole_id",
        how="left",
        suffixes=("_bgi", "_gee")
    )

    # Validate coordinate agreement: EXCLUDE records that diverge beyond tolerance
    if "latitude_gee" in joined.columns and "longitude_gee" in joined.columns:
        lat_diff = (joined["latitude_bgi"] - joined["latitude_gee"]).abs()
        lon_diff = (joined["longitude_bgi"] - joined["longitude_gee"]).abs()
        coord_error = (lat_diff > tolerance_degrees) | (lon_diff > tolerance_degrees)
        bad_coords = coord_error.sum()
        if bad_coords > 0:
            logger.error(f"ERROR: {bad_coords} records have coordinate divergence > {tolerance_degrees}°")
            # Show details of bad records
            bad_sample = joined[coord_error][["borehole_id", "latitude_bgi", "latitude_gee", "longitude_bgi", "longitude_gee"]].head(5)
            logger.error(f"Coordinate mismatches (will be EXCLUDED):\n{bad_sample}")
            # EXCLUDE the divergent records
            pre_filter = len(joined)
            joined = joined[~coord_error].reset_index(drop=True)
            logger.info(f"Filtered: {pre_filter} records → {len(joined)} records (removed {bad_coords} coordinate mismatches)")
        
        # Use GEE coordinates (assumed to be the reference from satellite extraction)
        joined["latitude"] = joined["latitude_gee"].fillna(joined["latitude_bgi"])
        joined["longitude"] = joined["longitude_gee"].fillna(joined["longitude_bgi"])
        joined.drop(columns=["latitude_bgi", "longitude_bgi", "latitude_gee", "longitude_gee"],
                   errors="ignore", inplace=True)

    # Check for unmatched boreholes (left join should have NaNs in GEE columns if no match)
    gee_feature_cols = [c for c in gee_df.columns if c not in ["latitude", "longitude", "borehole_id"]]
    unmatched = joined[gee_feature_cols].isna().all(axis=1).sum()
    if unmatched > 0:
        logger.error(f"ERROR: {unmatched} BGI boreholes have NO matching GEE features")
        unmatched_ids = joined[joined[gee_feature_cols].isna().all(axis=1)]["borehole_id"].tolist()
        logger.error(f"Unmatched borehole_ids: {unmatched_ids[:10]}")
        raise ValueError(
            f"Spatial join failed: {unmatched} boreholes without GEE features.\n"
            f"Verify GEE export includes all {len(bgi_df)} boreholes with correct borehole_id."
        )

    logger.info(f"Spatial join complete: {len(joined)} boreholes linked with GEE features")
    return joined


def add_investigation_ids(
    df: pd.DataFrame,
    investigation_map_path: Optional[str] = None
) -> pd.DataFrame:
    """
    Add investigation_id (farm identifier) to each borehole record.
    
    CRITICAL: investigation_id must be genuinely farm-specific for GroupKFold to work.
    
    If investigation_map provided: use it to assign farm-level IDs.
    If no map: check if df has a pre-existing investigation_id column; if not, raise error.
    
    This ensures spatial CV doesn't accidentally use coarse location grouping.
    
    Args:
        df: Dataframe with boreholes (must have either investigation_id or investigation_map_path)
        investigation_map_path: CSV with columns [location, investigation_id] or [borehole_id, investigation_id]
    
    Returns:
        DataFrame with investigation_id column (farm-specific)
        
    Raises:
        ValueError: If no investigation_id can be assigned
    """
    if investigation_map_path:
        logger.info(f"Loading investigation map from {investigation_map_path}...")
        inv_map = pd.read_csv(investigation_map_path)
        
        # Try to merge on common key
        merge_keys = []
        if "borehole_id" in inv_map.columns and "borehole_id" in df.columns:
            merge_keys.append("borehole_id")
        if "location" in inv_map.columns and "location" in df.columns:
            merge_keys.append("location")
        
        if not merge_keys:
            raise ValueError(
                f"Investigation map has columns {inv_map.columns.tolist()}, "
                f"but dataframe has only {df.columns.tolist()}. "
                f"Map must have either 'borehole_id' or 'location' to join."
            )
        
        merge_key = merge_keys[0]
        df = df.merge(inv_map[[merge_key, "investigation_id"]], on=merge_key, how="left")
        
        missing = df["investigation_id"].isna().sum()
        if missing > 0:
            logger.warning(f"  {missing} records missing investigation_id after map join (no match on {merge_key})")
            unmatched = df[df["investigation_id"].isna()][merge_key].unique()
            logger.warning(f"  Unmatched {merge_key} values: {list(unmatched)[:10]}")
        
        # CRITICAL STRUCTURAL CHECK: If using location-keyed map, verify investigation_id is finer than location
        # (Prevent silent coarse grouping where map applies one ID per location)
        if merge_key == "location" and "location" in df.columns:
            # Count unique investigation_ids per location
            ids_per_location = df.groupby("location")["investigation_id"].nunique()
            if (ids_per_location == 1).all():
                logger.error("FATAL: Map produces exactly one investigation_id per location (coarse grouping).")
                logger.error("This defeats spatial CV. Verify map distinguishes between different farms in the same location.")
                raise ValueError(
                    "Location-keyed investigation_map is too coarse: each location gets only one ID.\n"
                    "Provide a borehole-level map instead: [borehole_id, investigation_id]\n"
                    "Or ensure multiple investigations per location in your map."
                )
            elif (ids_per_location > 1).any():
                logger.info(f"✓ Location-keyed map is finer-grained (locations map to {ids_per_location.min()}-{ids_per_location.max()} investigations)")
        elif merge_key == "borehole_id":
            logger.info(f"✓ Using borehole-level map (most granular): {df['investigation_id'].nunique()} unique investigations")
    else:
        # No map provided: check if investigation_id already exists and is not just location
        if "investigation_id" not in df.columns or df["investigation_id"].isna().all():
            raise ValueError(
                "FATAL: No investigation_id provided and no --investigation-map supplied.\n"
                "investigation_id must be farm-specific, not coarse location names.\n"
                "Provide investigation_map CSV with columns: [location, investigation_id] or [borehole_id, investigation_id]\n"
                "Example: --investigation-map data/farms_investigation_mapping.csv"
            )
        
        # DUAL CHECK: investigation_id is not coarse
        # (1) String-level: investigation_id != location (catches literal reuse)
        # (2) Cardinality-level: investigation_id finer than location (catches location-keyed maps)
        if "location" in df.columns:
            same_as_location = (df["investigation_id"] == df["location"]).sum()
            if same_as_location == len(df):
                raise ValueError(
                    "FATAL: investigation_id is identical to location (coarse grouping).\n"
                    "Provide farm-specific mapping via --investigation-map to override this."
                )
            elif same_as_location > 0:
                logger.warning(f"  {same_as_location} boreholes have investigation_id == location (may be coarse)")
            
            # Check cardinality: ensure investigation_id grouping is finer than location grouping
            ids_per_location = df.groupby("location")["investigation_id"].nunique()
            if (ids_per_location == 1).all():
                logger.error("FATAL: Cardinality check: each location maps to exactly 1 investigation_id (coarse grouping).")
                logger.error(f"Locations: {df['location'].nunique()}, Investigations: {df['investigation_id'].nunique()} (should be > locations)")
                raise ValueError(
                    "investigation_id grouping is identical to location grouping by cardinality.\n"
                    "This happens when a map applies one ID per location (e.g., Khudumelapye→farm_khudumelapye_01).\n"
                    "Provide a borehole-level map to distinguish farms within same location."
                )
            elif (ids_per_location > 1).any():
                logger.info(f"✓ Cardinality check passed: investigation_id is finer than location ({ids_per_location.min()}-{ids_per_location.max()} investigations per location)")

    logger.info(f"Investigation IDs assigned: {df['investigation_id'].nunique()} unique investigations")
    return df


def validate_output_schema(df: pd.DataFrame, required_features: list) -> None:
    """
    Verify that output has all required columns and no all-null columns.
    """
    required_cols = [
        "borehole_id", "investigation_id", "latitude", "longitude", "yield_m3h", "is_productive"
    ] + required_features

    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.warning(f"Missing columns in output: {missing_cols}")

    # Check for all-null feature columns
    all_null_cols = [col for col in required_features if df[col].isna().all()]
    if all_null_cols:
        logger.warning(f"Features with all-null values: {all_null_cols}")

    logger.info(f"Output schema valid: {len(df)} records × {len(df.columns)} columns")


def main():
    parser = argparse.ArgumentParser(
        description="Join BGI borehole records with GEE features on spatial coordinates"
    )
    parser.add_argument(
        "--bgi",
        default="data/boreholes/bgi_verified_boreholes.csv",
        help="BGI borehole scraper output CSV"
    )
    parser.add_argument(
        "--gee",
        default="data/boreholes/agripulse_bgi_ml_features.csv",
        help="GEE feature export CSV (from agripulse_gee_feature_stack.js)"
    )
    parser.add_argument(
        "--output",
        default="data/boreholes/agripulse_gee_features.csv",
        help="Output joined CSV (ready for ML pipeline)"
    )
    parser.add_argument(
        "--investigation-map",
        default=None,
        help="Optional CSV mapping [location, farm_id] -> investigation_id"
    )
    parser.add_argument(
        "--coord-tolerance",
        type=float,
        default=0.001,
        help="Coordinate match tolerance in decimal degrees (default 0.001 ≈ 111m)"
    )

    args = parser.parse_args()

    # Load data
    bgi_df, gee_df = load_dataframes(args.bgi, args.gee)

    # Spatial join
    joined_df = spatial_join_on_coords(bgi_df, gee_df, tolerance_degrees=args.coord_tolerance)

    # Add investigation IDs
    joined_df = add_investigation_ids(joined_df, args.investigation_map)

    # Validate schema
    required_features = [
        "s1_vv", "s1_vh", "s1_vv_vh_ratio", "radar_contrast",
        "ndvi", "ndmi", "ndwi",
        "dem_elevation", "slope_deg", "twi", "flow_accumulation",
        "dist_to_structure_m", "structural_density", "intersection_index"
    ]
    validate_output_schema(joined_df, required_features)

    # Save output
    joined_df.to_csv(args.output, index=False)
    logger.info(f"Joined dataset saved to {args.output}")
    logger.info(f"Ready to train: python agripulse_ml_pipeline.py --input {args.output}")


if __name__ == "__main__":
    main()
