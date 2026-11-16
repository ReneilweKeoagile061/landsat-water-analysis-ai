import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

POINTS_CSV = r"C:\Users\pc\Desktop\Landsat-Water Current\data\boreholes\transboundary_regional_training_master.csv"
DOLERITE_GEOJSON = r"C:\Users\pc\Desktop\Landsat-Water Current\data\processed\model_data\dolerite_structures.geojson"
RECHARGE_GEOJSON = r"C:\Users\pc\Desktop\Landsat-Water Current\data\processed\model_data\recharge_zones.geojson"
AQUIFER_BOUND_SHP = r"C:\Users\pc\Desktop\Landsat-Water Current\data\external\model_data\0_Boundary_shapefiles\SPR_physiography_stasboundary.shp"
OUTPUT_CSV = r"C:\Users\pc\Desktop\Landsat-Water Current\data\boreholes\transboundary_regional_enriched.csv"

print("="*70)
print(" 🔬 ENRICHING REGIONAL BOREHOLES WITH STRUCTURAL HYDROGEOLOGY")
print("="*70)

df_pts = pd.read_csv(POINTS_CSV)
print(f"Loaded {len(df_pts)} regional borehole points.")

# Convert to GeoDataFrame
geometry = [Point(xy) for xy in zip(df_pts['long'], df_pts['lat'])]
gdf_pts = gpd.GeoDataFrame(df_pts, geometry=geometry, crs="EPSG:4326")

# Reproject to a metric projection for accurate distance calculations (UTM Zone 33S or 32S, EPSG:32733)
gdf_pts_metric = gdf_pts.to_crs(epsg=32733)

# 1. Dolerite Dykes / Sills (Impermeable Flow Barriers)
if os.path.exists(DOLERITE_GEOJSON):
    gdf_dol = gpd.read_file(DOLERITE_GEOJSON).to_crs(epsg=32733)
    # Compute nearest distance to dolerite structure
    print("Calculating distance to nearest dolerite barrier (meters)...")
    # Spatial index nearest
    nearest_dist = []
    # Combine all dolerite geometries into a unary union for fast distance
    dol_union = gdf_dol.geometry.union_all() if hasattr(gdf_dol.geometry, 'union_all') else gdf_dol.geometry.unary_union
    gdf_pts['dist_to_dolerite_m'] = gdf_pts_metric.geometry.distance(dol_union)
    print("  -> Completed dist_to_dolerite_m")
else:
    gdf_pts['dist_to_dolerite_m'] = np.nan

# 2. Recharge Zone Flag (Infiltration areas)
if os.path.exists(RECHARGE_GEOJSON):
    gdf_rech = gpd.read_file(RECHARGE_GEOJSON).to_crs(epsg=4326)
    rech_union = gdf_rech.geometry.union_all() if hasattr(gdf_rech.geometry, 'union_all') else gdf_rech.geometry.unary_union
    gdf_pts['is_in_recharge_zone'] = gdf_pts.geometry.within(rech_union).astype(int)
    print("  -> Completed is_in_recharge_zone flag")
else:
    gdf_pts['is_in_recharge_zone'] = 0

# 3. Target Aquifer Mapping (Auob, Kalahari, Nossob)
# Use existing 'aquifer' column and standardize
def clean_aquifer_name(a):
    a = str(a).upper()
    if 'AUOB' in a:
        return 'Auob'
    elif 'NOSSOB' in a:
        return 'Nossob'
    elif 'KALA' in a:
        return 'Kalahari'
    elif 'BASE' in a:
        return 'Basement'
    else:
        return 'Other/Regional'

gdf_pts['standard_aquifer'] = gdf_pts['aquifer'].apply(clean_aquifer_name)

# Drop raw shapely geometry for clean CSV export
df_out = pd.DataFrame(gdf_pts.drop(columns=['geometry']))
df_out.to_csv(OUTPUT_CSV, index=False)

print(f"\n✅ Enriched Transboundary Dataset successfully saved to:\n  {OUTPUT_CSV}")
print("\nSample Enriched Records:")
print(df_out[['bh_id', 'country', 'long', 'lat', 'yield_class', 'dist_to_dolerite_m', 'is_in_recharge_zone', 'standard_aquifer']].head(8))
print("="*70)
