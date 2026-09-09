# AgriPulse Data Pipeline — BGI Scraper → GEE Features → ML Training

This document describes the complete data integration workflow required to train the AgriPulse XGBoost classifier.

## Overview

```
┌──────────────────────────────┐
│  BGI Borehole Scraper        │  → bgi_verified_boreholes.csv
│  (bgi_borehole_client.py)    │     (borehole_id, location, coords, yield, strike, depth)
└──────────────────────────────┘
          ↓ [User uploads to GEE]
┌──────────────────────────────────────────┐
│  GEE Feature Extraction                  │  → agripulse_bgi_ml_features.csv
│  (agripulse_gee_feature_stack.js)        │     (borehole_id, coords, 14 GEE features)
│  Extracts satellite/terrain at each point│
└──────────────────────────────────────────┘
          ↓ [User downloads from GEE]
┌──────────────────────────────┐
│  GEE-BGI Join Script         │  → agripulse_gee_features.csv
│  (agripulse_gee_join.py)     │     (all BGI cols + 14 features + investigation_id)
│  Merges on coordinates       │
│  Adds farm IDs               │
└──────────────────────────────┘
          ↓
┌──────────────────────────────┐
│  ML Training Pipeline        │
│  (agripulse_ml_pipeline.py)  │  → Trained classifier
│  XGBoost + GroupKFold CV     │     Out-of-fold metrics
│  Validates schema            │
└──────────────────────────────┘
```

---

## Step 1: Run BGI Scraper

**Input:** None (scrapes live from https://bh.bgi.org.bw)  
**Output:** `data/boreholes/bgi_verified_boreholes.csv`

### Command
```bash
python scripts/bgi_borehole_client.py
```

### Output Columns
- `borehole_id` — unique identifier (from BGI)
- `location` — town/district name
- `latitude`, `longitude` — WGS84 coordinates
- `yield_m3h` — measured yield (m³/hr); blank if unknown, `0` only if verified dry
- `is_productive` — `1` productive, `0` verified dry, blank unknown (excluded from training)
- `yield_status` — `measured`, `verified_zero`, or `unknown`
- `water_strike_m` — depth to water (meters)
- `static_water_level_m` — static water level
- `total_depth_m` — total borehole depth
- `drill_date` — drilling date

**⚠️ NOTE:** This CSV has NO satellite or terrain features yet.

---

## Step 2: Extract Features from Google Earth Engine

**Input:** BGI CSV (coordinates only)  
**Output:** `agripulse_bgi_ml_features.csv` (in your GEE Drive folder)

### Setup (One-time)
1. Go to [Google Earth Engine Code Editor](https://code.earthengine.google.com)
2. Upload your borehole CSV as a **Table Asset**:
   - Asset → New → Table Upload
   - CSV: `bgi_verified_boreholes.csv`
   - Parse columns: `longitude`, `latitude`
   - Save as: `projects/your-project/assets/agripulse_boreholes_table`

### Run GEE Script
1. Open [GEE Code Editor](https://code.earthengine.google.com)
2. Copy-paste entire contents of `agripulse_gee_feature_stack.js`
3. **Modify line 25:** Set `BOREHOLES_ASSET` to your table asset path
4. **Modify lines 28–31:** Adjust study area and date range if needed
5. Click **Run**
6. Check **Tasks** panel (top-right)
7. Click **RUN** on the export task
8. Wait for completion (~5–10 minutes for 100 boreholes)
9. Download CSV from your Google Drive → **AgriPulse** folder

### GEE Output Columns
The script exports all 14 required ML features:

**Sentinel-1 (Radar — 4 features)**
- `s1_vv` — VV backscatter (dB)
- `s1_vh` — VH backscatter (dB)
- `s1_vv_vh_ratio` — VV − VH ratio
- `radar_contrast` — GLCM texture contrast

**Sentinel-2 (Optical — 3 features)**
- `ndvi` — Normalized Difference Vegetation Index
- `ndmi` — Normalized Difference Moisture Index
- `ndwi` — Normalized Difference Water Index

**DEM & Terrain (4 features)**
- `dem_elevation` — elevation (meters)
- `slope_deg` — slope (degrees)
- `twi` — Topographic Wetness Index
- `flow_accumulation` — upslope contributing area

**Structural (3 features)**
- `dist_to_structure_m` — distance to nearest lineament/structure (meters)
- `structural_density` — lineament density index (0–1)
- `intersection_index` — structural intersection evidence (0–1)

---

## Step 3: Join BGI + GEE Features

**Input:**
- `data/boreholes/bgi_verified_boreholes.csv` (from Step 1)
- `agripulse_bgi_ml_features.csv` (downloaded from GEE in Step 2)
- **REQUIRED:** `investigation_mapping.csv` — assigns each borehole to a specific farm/investigation

**Output:** `data/boreholes/agripulse_gee_features.csv` (ready for training)

### CRITICAL: investigation_map is MANDATORY

The spatial cross-validation depends on having genuinely **farm-specific** investigation IDs, NOT coarse location names. This join script will **FAIL** if you don't provide a farm mapping.

### Command

```bash
python scripts/agripulse_gee_join.py \
  --bgi data/boreholes/bgi_verified_boreholes.csv \
  --gee agripulse_bgi_ml_features.csv \
  --output data/boreholes/agripulse_gee_features.csv \
  --investigation-map investigation_mapping.csv
```

### Required: investigation_mapping.csv Format

File must have columns: `borehole_id` and `investigation_id`

```csv
borehole_id,investigation_id
BH001,farm_khudumelapye_01
BH002,farm_khudumelapye_01
BH003,farm_khudumelapye_01
BH004,farm_molepolole_02
BH005,farm_molepolole_02
BH006,farm_palapye_03
BH007,farm_palapye_03
BH008,farm_palapye_03
BH009,farm_serowe_04
BH010,farm_serowe_04
```

**Where:**
- `borehole_id` must match BGI scraper output
- `investigation_id` = unique farm identifier (e.g., `farm_<location>_<number>`, or `AgriPulse_Investigation_2024_06_15`)

**Why this matters:**
- GroupKFold cross-validation groups by `investigation_id` to prevent data leakage between train/test
- If investigation_id is just location names (e.g., "Khudumelapye"), multiple boreholes from same town leak between folds
- Farm-specific ID ensures each farm/investigation is held out completely in validation

### What the Join Does

1. **Loads BGI + GEE datasets**
2. **2D spatial join on borehole_id** — exact match, validates coordinate agreement
3. **Assigns investigation_id** from your mapping CSV
4. **Validates schema** — ensures all 14 features present, no all-null columns
5. **Raises error** if any boreholes unmatched or investigation_id missing

### Coordinate Validation

The join checks that BGI and GEE coordinates agree within tolerance (~111m per 0.001°).
- If coordinates diverge beyond tolerance: logged as warning
- If borehole completely unmatched: raises error and stops (data integrity check)

### Sample Data

See `investigation_map_sample.csv` for example format.

---

## Step 4: Train ML Pipeline

**Input:** `data/boreholes/agripulse_gee_features.csv`  
**Output:**
- `data/models/agripulse_classifier.pkl` — trained model
- `data/models/agripulse_ml_metrics.json` — cross-validation metrics

### Command
```bash
python scripts/agripulse_ml_pipeline.py
```

### What Happens
1. **Loads and validates** — checks all 14 features present, no synthetic fill
2. **Spatial QC** — drops boreholes missing coordinates or `is_productive` label
3. **GroupKFold CV** — groups by `investigation_id` (farm-level holdout)
4. **Trains XGBoost classifier** — 5-fold CV on binary productivity (1=productive, 0=dry)
5. **Reports metrics** — accuracy, precision, recall, F1, ROC-AUC per fold
6. **Saves model** — pickle + optional XGBoost native format

### Output Metrics Example
```json
{
  "accuracy": 0.75,
  "precision": 0.80,
  "recall": 0.72,
  "f1": 0.76,
  "mean_spatial_cv_auc": 0.82,
  "n_samples": 42,
  "class_balance_productive": 28,
  "class_balance_unsuccessful": 14,
  "model_engine": "XGBoost",
  "feature_importances": {
    "ndvi": 0.18,
    "dem_elevation": 0.15,
    ...
  }
}
```

---

## Expected CSV Schema

The final `agripulse_gee_features.csv` must have this exact structure:

| Column | Type | Required | Source | Notes |
|--------|------|----------|--------|-------|
| `borehole_id` | string | ✓ | BGI | Unique ID |
| `investigation_id` | string | ✓ | Join script | Farm/investigation ID for spatial CV |
| `longitude` | float | ✓ | BGI | WGS84 |
| `latitude` | float | ✓ | BGI | WGS84 |
| `yield_m3h` | float or blank | ✓ | BGI | Blank if unknown; `0` only for verified dry |
| `is_productive` | 1, 0, or blank | ✓ | BGI | 1=productive, 0=verified dry, blank=unknown/excluded |
| `yield_status` | string |  | BGI | `measured` / `verified_zero` / `unknown` |
| `water_strike_m` | float or blank |  | BGI | Optional |
| `s1_vv` to `intersection_index` | float | ✓ | GEE | 14 features; NO blanks or synthetic |

### ⚠️ Important Rules
- **Yield:** Leave unknown yields blank. Use `0` only when BGI recorded a verified zero yield. Never coerce missing yield to dry.
- **is_productive:** `1` productive, `0` verified dry, blank unknown — blank rows are excluded from training
- **14 features:** ALL must be present and real (GEE-derived) — pipeline raises error if missing
- **investigation_id:** Use to group geographically close boreholes for proper spatial cross-validation

---

## Sample Data

See `agripulse_gee_features_sample.csv` for a 10-borehole example showing expected values and column arrangement.

---

## Troubleshooting

### "Missing required GEE feature columns"
- **Cause:** GEE script didn't run, or wrong export file used
- **Fix:** Verify you downloaded `agripulse_bgi_ml_features.csv` from GEE Drive → AgriPulse folder

### "Coordinate mismatch: 42 linked, 8 missing"
- **Cause:** Some BGI coords don't match GEE export coords (e.g., manual entry errors)
- **Fix:** Check join log; manually verify outliers; increase `--coord-tolerance` if needed

### "Dropped N boreholes with unknown productivity"
- **Cause:** `is_productive` is blank (expected behavior)
- **Fix:** If these boreholes should be labeled, update BGI source or join script

### "All boreholes in one group" warning
- **Cause:** No `investigation_id` or `location` column
- **Fix:** Run join script with `--investigation-map` or ensure location is populated

---

## Next Steps

1. ✓ Run BGI scraper → `bgi_verified_boreholes.csv`
2. ✓ Upload to GEE and run `agripulse_gee_feature_stack.js`
3. ✓ Download `agripulse_bgi_ml_features.csv` from Drive
4. ✓ Run `agripulse_gee_join.py` → `agripulse_gee_features.csv`
5. ✓ Run `agripulse_ml_pipeline.py` → trained model + metrics
6. **Predict on new farm grids** using trained model (coming: `rank_and_export_drill_targets.py`)

---

## References

- BGI: https://bh.bgi.org.bw/borehole
- Google Earth Engine: https://code.earthengine.google.com
- Sentinel-1 documentation: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD
- Sentinel-2 documentation: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED
