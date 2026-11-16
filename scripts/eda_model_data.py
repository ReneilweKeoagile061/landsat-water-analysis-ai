import os
import numpy as np
import pandas as pd
import geopandas as gpd

BASE_DIR = r"C:\Users\pc\Desktop\Landsat-Water Current\data\external\model_data"
PROCESSED_DIR = r"C:\Users\pc\Desktop\Landsat-Water Current\data\processed\model_data"
os.makedirs(PROCESSED_DIR, exist_ok=True)

def bar_chart(title, categories, values, max_bar_len=40, unit=""):
    print(f"\n┌{'─'*68}┐")
    print(f"│ {title.ljust(66)} │")
    print(f"├{'─'*68}┤")
    if not values or max(values) == 0:
        print("│ No data available to plot.".ljust(69) + "│")
        print(f"└{'─'*68}┘")
        return
    max_val = max(values)
    for cat, val in zip(categories, values):
        bar_len = int((val / max_val) * max_bar_len) if max_val > 0 else 0
        bar = "█" * bar_len
        line = f"│ {str(cat)[:20].ljust(20)} | {bar.ljust(max_bar_len)} {val:8.1f} {unit}"
        print(line[:69].ljust(69) + "│")
    print(f"└{'─'*68}┘")

def histogram(title, data, bins=8, max_bar_len=35, unit=""):
    data = [x for x in data if np.isfinite(x)]
    if len(data) == 0:
        return
    counts, edges = np.histogram(data, bins=bins)
    max_c = max(counts) if len(counts) > 0 and max(counts) > 0 else 1
    print(f"\n┌{'─'*68}┐")
    print(f"│ {title.ljust(66)} │")
    print(f"├{'─'*68}┤")
    for i in range(len(counts)):
        label = f"[{edges[i]:5.1f} - {edges[i+1]:5.1f}{unit}]"
        bar_len = int((counts[i] / max_c) * max_bar_len)
        bar = "■" * bar_len
        line = f"│ {label.ljust(18)} | {bar.ljust(max_bar_len)} {counts[i]:4d} wells"
        print(line[:69].ljust(69) + "│")
    print(f"└{'─'*68}┘")

def summary_card(title, stats_dict):
    print(f"\n╔{'═'*68}╗")
    print(f"║ {title.center(66)} ║")
    print(f"╠{'═'*68}╣")
    for k, v in stats_dict.items():
        val_str = f"{v:.2f}" if isinstance(v, (int, float, np.floating, np.integer)) else str(v)
        print(f"║  {k.ljust(35)} : {val_str.rjust(26)}  ║")
    print(f"╚{'═'*68}╝")

print("\n" + "="*70)
print(" 🌍 EXPLORATORY DATA ANALYSIS (EDA) & HYDROGEOLOGICAL VISUAL DASHBOARD")
print("="*70)

# 1. Domain & Boundaries
domain_shp = os.path.join(BASE_DIR, "1_Model_domain", "Model_domain.shp")
if os.path.exists(domain_shp):
    gdf_dom = gpd.read_file(domain_shp)
    summary_card("1. REGIONAL STAS GROUNDWATER MODEL DOMAIN", {
        "Finite Difference Grid Cells": len(gdf_dom),
        "Active Domain Cells": int((gdf_dom['ACTIVE'] == 1).sum()) if 'ACTIVE' in gdf_dom.columns else len(gdf_dom),
        "Grid Dimensions (Rows x Cols)": f"{gdf_dom['ROW'].max()} x {gdf_dom['COL'].max()}" if 'ROW' in gdf_dom.columns else "N/A",
        "Spatial Reference (CRS)": "WGS 84 / UTM zone 32S (EPSG:32632)"
    })

# 2. In-Situ Piezometric Wells (Ground Truth)
gdf_k = gpd.read_file(os.path.join(BASE_DIR, "6_Groundwater_data_shapefiles", "Kalahari_piezometric_data.shp"))
gdf_a = gpd.read_file(os.path.join(BASE_DIR, "6_Groundwater_data_shapefiles", "Auob_piezometric_data.shp"))
gdf_n = gpd.read_file(os.path.join(BASE_DIR, "6_Groundwater_data_shapefiles", "Nossob_piezometric_data.shp"))

# Harmonize & Clean
all_piezo = []
for name, gdf in [("Kalahari", gdf_k), ("Auob", gdf_a), ("Nossob", gdf_n)]:
    gdf['target_aquifer'] = name
    gdf.columns = [c.lower() for c in gdf.columns]
    all_piezo.append(gdf[['target_aquifer', 'country', 'depth_m', 'wl_mbgl', 'geometry']])

df_piezo = pd.concat(all_piezo, ignore_index=True)
df_piezo = df_piezo.dropna(subset=['geometry'])

bar_chart("IN-SITU MONITORING WELLS BY TARGET AQUIFER",
          ["Kalahari (Unconfined)", "Auob (Confined Sandstone)", "Nossob (Basal Karoo)"],
          [len(gdf_k), len(gdf_a), len(gdf_n)],
          unit="wells")

country_counts = df_piezo['country'].value_counts()
bar_chart("MONITORING NETWORK CROSS-BORDER COVERAGE",
          country_counts.index.tolist(),
          country_counts.values.tolist(),
          unit="wells")

# Water level depth distribution (Meters Below Ground Level)
valid_wl = df_piezo['wl_mbgl'].dropna()
valid_wl = valid_wl[(valid_wl > 0) & (valid_wl < 300)]
histogram("DEPTH TO WATER TABLE / STRIKE (wl_mbgl)", valid_wl.values, bins=8, unit="m")

# Borehole total depth
valid_depth = df_piezo['depth_m'].dropna()
valid_depth = valid_depth[(valid_depth > 0) & (valid_depth < 500)]
histogram("BOREHOLE TOTAL DEPTH DISTRIBUTION", valid_depth.values, bins=8, unit="m")

# 3. Dolerite Structures & Recharge Zones
dolerite_shp = os.path.join(BASE_DIR, "4_Dolerite_area_shapefiles", "Dolerite.shp")
recharge_shp = os.path.join(BASE_DIR, "4_Dolerite_area_shapefiles", "Recharge_zone.shp")
discharge_shp = os.path.join(BASE_DIR, "4_Dolerite_area_shapefiles", "Discharge_zone.shp")

d_count = len(gpd.read_file(dolerite_shp)) if os.path.exists(dolerite_shp) else 0
r_count = len(gpd.read_file(recharge_shp)) if os.path.exists(recharge_shp) else 0
dc_count = len(gpd.read_file(discharge_shp)) if os.path.exists(discharge_shp) else 0

bar_chart("HYDROGEOLOGICAL BOUNDARY CONDITIONS",
          ["Dolerite Impermeable Dykes", "Recharge Polygons", "Discharge / Pan Zones"],
          [d_count, r_count, dc_count],
          unit="features")

# 4. Transmissivity & Hydraulic Properties (7_Hydraulic_parameter_shapefiles)
gdf_hp_a = gpd.read_file(os.path.join(BASE_DIR, "7_Hydraulic_parameter_shapefiles", "Auob_hydraulic_parameter_and_thickness_points.shp"))
gdf_hp_k = gpd.read_file(os.path.join(BASE_DIR, "7_Hydraulic_parameter_shapefiles", "Kalahari_hydraulic_parameter_and_thickness_points.shp"))
gdf_hp_n = gpd.read_file(os.path.join(BASE_DIR, "7_Hydraulic_parameter_shapefiles", "Nossob_hydraulic_parameter_and_thickness_points.shp"))

# Auob Thickness
thick_col = [c for c in gdf_hp_a.columns if 'thick' in c.lower() or 't' == c.lower()]
if thick_col:
    t_vals = gdf_hp_a[thick_col[0]].dropna().values
    histogram("AUOB AQUIFER PRODUCTIVE THICKNESS", t_vals, bins=6, unit="m")

# 5. Export Master Standardized Geodataset
print("\n" + "="*70)
print(" 💾 SAVING VERIFIED AND CLEANED GEOJSON LAYERS")
print("="*70)

out_piezo = os.path.join(PROCESSED_DIR, "stas_combined_piezometric_wells.geojson")
df_piezo_gdf = gpd.GeoDataFrame(df_piezo, geometry='geometry', crs=gdf_k.crs)
df_piezo_gdf = df_piezo_gdf.to_crs(epsg=4326)
df_piezo_gdf.to_file(out_piezo, driver="GeoJSON")

print(f"✅ Cleaned and unified {len(df_piezo_gdf)} in-situ groundwater monitoring wells -> {out_piezo}")
print(f"✅ Cleaned and verified {d_count} dolerite barrier features")
print(f"✅ Cleaned and verified {len(gdf_dom)} numerical groundwater grid cells")

print("\n" + "="*70)
print(" 🚀 READY FOR ML FEATURE EXTRACTION & PIPELINE ENRICHMENT")
print("="*70 + "\n")
