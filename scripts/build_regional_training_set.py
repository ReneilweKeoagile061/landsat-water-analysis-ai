import os
import sys
import pandas as pd
import numpy as np

STAS_CSV = r"C:\Users\pc\Desktop\Landsat-Water Current\data\external\orasecom_stas\STAS_BoreholeDatabase_Clean.csv"
BGI_CSV = r"C:\Users\pc\Desktop\Landsat-Water Current\data\boreholes\bgi_verified_boreholes.csv"
OUT_CSV = r"C:\Users\pc\Desktop\Landsat-Water Current\data\boreholes\transboundary_regional_training_master.csv"

print("="*70)
print(" 🚀 SCALING UP: BUILDING TRANSBOUNDARY REGIONAL BOREHOLE TRAINING DATASET")
print("="*70)

# 1. Load STAS Database (Botswana, Namibia, South Africa)
df_stas = pd.read_csv(STAS_CSV, low_memory=False)

def clean_val(x):
    try:
        val = float(x)
        return np.nan if val <= -9000 else val
    except:
        return np.nan

df_stas['clean_yield_m3h'] = df_stas['yield_m3_h'].apply(clean_val)
df_stas['clean_tds_mgl'] = df_stas['tds_mg_l'].apply(clean_val)
df_stas['clean_depth_m'] = df_stas['depth_m'].apply(clean_val)
df_stas['clean_wl_mbgl'] = df_stas['wl_mbgl'].apply(clean_val)

def assign_yield_label(y):
    if pd.isna(y):
        return np.nan
    if y >= 5.0:
        return 'high'
    elif y >= 0.5:
        return 'medium'
    else:
        return 'low'

df_stas['yield_class'] = df_stas['clean_yield_m3h'].apply(assign_yield_label)

# 2. Load Existing Verified BGI Botswana Points
df_bgi = pd.read_csv(BGI_CSV)
df_bgi['bh_id'] = df_bgi['borehole_id']
df_bgi['clean_yield_m3h'] = df_bgi['yield_m3h']
df_bgi['country'] = 'BOTSWANA'
df_bgi['yield_class'] = df_bgi['clean_yield_m3h'].apply(assign_yield_label)
df_bgi['long'] = df_bgi['longitude']
df_bgi['lat'] = df_bgi['latitude']
df_bgi['clean_depth_m'] = df_bgi['total_depth_m']
df_bgi['clean_wl_mbgl'] = df_bgi['static_water_level_m']
df_bgi['clean_tds_mgl'] = np.nan
df_bgi['aquifer'] = 'Unknown/BGI'

# 3. Standardize & Merge
keep_cols = ['bh_id', 'country', 'long', 'lat', 'clean_depth_m', 'clean_yield_m3h', 'yield_class', 'clean_tds_mgl', 'clean_wl_mbgl', 'aquifer']

df_stas_sub = df_stas[keep_cols].copy()
df_bgi_sub = df_bgi[keep_cols].copy()

df_combined = pd.concat([df_stas_sub, df_bgi_sub], ignore_index=True)
df_combined = df_combined.drop_duplicates(subset=['lat', 'long'])

# Filter only points with valid coordinates
df_combined = df_combined.dropna(subset=['lat', 'long'])
df_combined = df_combined[(df_combined['lat'] >= -35) & (df_combined['lat'] <= -15) & 
                           (df_combined['long'] >= 10) & (df_combined['long'] <= 35)]

df_combined.to_csv(OUT_CSV, index=False)

print(f"\n✅ Total Consolidated Regional Boreholes: {len(df_combined)}")
print("\nRegional Distribution:")
print(df_combined['country'].value_counts())

print("\nBoreholes with Verified Measured Yields (for Model Training):")
yield_df = df_combined.dropna(subset=['yield_class'])
print(yield_df.groupby(['country', 'yield_class']).size().unstack(fill_value=0))

print("\nBoreholes with Measured Depth Profile:")
print(df_combined.dropna(subset=['clean_depth_m'])['country'].value_counts())

print("\nBoreholes with Measured Groundwater Quality (TDS mg/L):")
print(df_combined.dropna(subset=['clean_tds_mgl'])['country'].value_counts())

print(f"\n💾 Saved Master Regional Dataset -> {OUT_CSV}")
print("="*70)
