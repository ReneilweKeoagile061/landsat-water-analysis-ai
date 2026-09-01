# AgriPulse Phase 1 — Verification & Final Fixes

**Status:** ✅ **VERIFIED & CORRECTED**  
**Date:** 2026-09-01

---

## Issues Found on Verification & Fixed

### 1. Investigation_id Fallback Was Coarse (NOW FIXED)
**Problem Found:** Join script fell back to location-string grouping when no farm mapping provided  
**Impact:** Spatial CV would be weak without warning  
**Fix Applied:**
- Join script now **REQUIRES** `--investigation-map` to be provided
- Raises error if investigation_id missing or identical to location
- No more silent fallback to coarse grouping
- Pipeline validates and rejects if investigation_id == location

**Enforcement:**
```python
# In agripulse_gee_join.py
if not investigation_map_path:
    raise ValueError("FATAL: No investigation_id provided and no --investigation-map supplied...")
```

### 2. Spatial Join Was Fragile 1D (NOW FIXED)
**Problem Found:** `merge_asof` on longitude only—could match wrong latitude  
**Impact:** Could silently link wrong boreholes if BGI/GEE had similar lon but different lat  
**Fix Applied:**
- Now uses 2D spatial join on `borehole_id` (exact match, most reliable)
- Validates latitude AND longitude agreement within tolerance
- Raises error if any borehole unmatched
- Clear error message if GEE export missing boreholes

**Enforcement:**
```python
# In agripulse_gee_join.py
# Check coordinate divergence on both lat AND lon
lat_diff = (joined["latitude_bgi"] - joined["latitude_gee"]).abs()
lon_diff = (joined["longitude_bgi"] - joined["longitude_gee"]).abs()
coord_error = (lat_diff > tolerance) | (lon_diff > tolerance)
if coord_error.sum() > 0:
    logger.error(f"Coordinate divergence detected: {coord_error.sum()} records")
```

### 3. Sample CSV Mixed Data Conventions (NOW FIXED)
**Problem Found:** Some rows had yield=0.0 (value), others blank  
**Impact:** Confuses "measured zero" vs "not measured"  
**Fix Applied:**
- Standardized: blank yield → blank is_productive (excluded from training)
- Example rows (BH003, BH008) now consistently blank for both
- Only BH001-BH002, BH004, BH006-BH007, BH009-BH010 have productivity labels

---

## What's Now in Place

### ✅ Schema Validation (Strict)
- ❌ Rejects missing 14 GEE features (no synthetic fill)
- ❌ Rejects missing is_productive (can't train on unknown)
- ❌ Rejects missing borehole_id or coordinates
- ✅ Validates all 14 features present (GEE-derived, not fake)

### ✅ Spatial Join (2D, Validated)
- ✅ Joins on `borehole_id` (exact match)
- ✅ Validates lat/lon agreement within tolerance
- ✅ Raises error if any boreholes unmatched
- ✅ Logs coordinate divergence warnings

### ✅ Investigation_id (Farm-Specific, Required)
- ✅ Requires `--investigation-map` CSV (no coarse fallback)
- ✅ Validates investigation_id != location
- ✅ Pipeline detects and rejects coarse grouping
- ✅ Clear error messages guide user to fix

### ✅ Training Pipeline (Safe)
- ✅ Validates schema on load
- ✅ Drops rows with missing is_productive
- ✅ Uses farm-specific investigation_id for GroupKFold
- ✅ Logs clear warnings if grouping weak
- ✅ Saves metrics + trained model

---

## Files Created/Modified

| File | Purpose | Status |
|------|---------|--------|
| `agripulse_ml_pipeline.py` | ML training with strict schema validation | ✅ Updated with coarse-grouping backstop |
| `agripulse_gee_join.py` | 2D spatial join + farm ID assignment | ✅ Fixed to require investigation_map + validate coords |
| `agripulse_gee_feature_stack.js` | GEE feature extraction template | ✅ Created |
| `DATA_PIPELINE.md` | Complete step-by-step guide | ✅ Updated to make investigation_map mandatory |
| `agripulse_gee_features_sample.csv` | 10-row example (correct format) | ✅ Fixed blank/0.0 consistency |
| `investigation_map_sample.csv` | Example farm mapping (NEW) | ✅ Created |
| `PHASE1_COMPLETION_SUMMARY.md` | This file | ✅ Updated |

---

## Expected CSV Schema (Now Enforced)

```
borehole_id (str)
investigation_id (str) ← NEW, used for spatial CV grouping
longitude (float)
latitude (float)
yield_m3h (float or BLANK — never 0)
is_productive (1, 0, or BLANK)
water_strike_m (float or blank)
s1_vv, s1_vh, s1_vv_vh_ratio, radar_contrast (4 Sentinel-1 features)
ndvi, ndmi, ndwi (3 Sentinel-2 indices)
dem_elevation, slope_deg, twi, flow_accumulation (4 terrain features)
dist_to_structure_m, structural_density, intersection_index (3 structural features)
```

**All 14 GEE features MUST be present and non-synthetic.**  
**is_productive MUST be 1, 0, or blank (blank rows excluded from training).**

---

## Data Provenance Chain

```
1. BGI Scraper
   └─→ bgi_verified_boreholes.csv
       (id, location, coords, yield, strike, depth, date)
       
2. User uploads to GEE → runs agripulse_gee_feature_stack.js
   └─→ agripulse_bgi_ml_features.csv
       (id, coords, 14 GEE features)
       
3. agripulse_gee_join.py merges + adds investigation_id
   └─→ agripulse_gee_features.csv
       (all BGI cols + 14 GEE features + investigation_id)
       
4. agripulse_ml_pipeline.py validates + trains
   └─→ agripulse_classifier.pkl + metrics
       (XGBoost model + CV metrics)
```

---

## Critical Check Before Milestone 1 Demo

**Before claiming "84 boreholes trained successfully," you MUST:**

1. ✓ Run BGI scraper → verify `bgi_verified_boreholes.csv` has 84 records
2. ✓ Run GEE feature extraction → download `agripulse_bgi_ml_features.csv`
3. ✓ Run join script → generate `agripulse_gee_features.csv`
4. ✓ Run ML pipeline → confirms:
   - All 14 features present (no synthetic fill)
   - Spatial grouping by investigation_id works (shows # of unique investigations)
   - Out-of-fold metrics computed (mean CV AUC, F1, etc.)
   - Model saved successfully

**Expected log output:**
```
Loaded 84 borehole records from data/boreholes/agripulse_gee_features.csv
✓ All required base columns present.
✓ All 14 required GEE features present.
After coordinate QC: 84 boreholes remain
Dropped N boreholes with unknown productivity (blank is_productive)
✓ Using investigation_id for spatial CV grouping (K unique investigations)
Training supervised Classifier (Productive vs Dry) with Spatial Cross-Validation...
Model saved to data/models/agripulse_classifier.pkl
ML Metrics: {
  "accuracy": 0.XX,
  "mean_spatial_cv_auc": 0.XX,
  "n_samples": M,
  "class_balance_productive": X,
  "class_balance_unsuccessful": Y
}
```

**Key indicators of success:**
- ✅ n_samples > 70 (at least some is_productive labels in data)
- ✅ class_balance_productive > 5 (not all dry boreholes)
- ✅ class_balance_unsuccessful > 5 (not all productive)
- ✅ mean_spatial_cv_auc between 0.5–1.0 (not random)
- ✅ Log shows "Using investigation_id for spatial CV grouping" (not "Using location...")
- ✅ Investigation IDs are farm names (e.g., farm_khudumelapye_01), NOT location names

---

## What's NOT Yet Done

These remain for Phase 2–4:

- ❌ Farm grid generator (point prediction across systematic farm grid)
- ❌ ERT (electrical resistivity tomography) integration
- ❌ Yield & water-strike regression models
- ❌ Probability calibration (isotonic/Platt)
- ❌ Neighborhood spatial features (mean density in 100m radius)
- ❌ True cross-region holdout evaluation (Region A train / Region D test)
- ❌ Lithology/log-formation parsing

---

## Quick Start to Verify Pipeline

```bash
# 1. Run BGI scraper
python scripts/bgi_borehole_client.py

# 2. Upload result to GEE and run agripulse_gee_feature_stack.js
#    (manual step in GEE Code Editor)

# 3. PREPARE investigation mapping (farm IDs for each borehole)
#    Create data/boreholes/investigation_mapping.csv with columns:
#    borehole_id, investigation_id
#    (See investigation_map_sample.csv for format)

# 4. Download GEE export, then join with investigation map
python scripts/agripulse_gee_join.py \
  --bgi data/boreholes/bgi_verified_boreholes.csv \
  --gee ~/Downloads/agripulse_bgi_ml_features.csv \
  --output data/boreholes/agripulse_gee_features.csv \
  --investigation-map data/boreholes/investigation_mapping.csv

# 5. Train
python scripts/agripulse_ml_pipeline.py \
  --input data/boreholes/agripulse_gee_features.csv \
  --outdir data/models

# 6. Check model output
cat data/models/agripulse_ml_metrics.json
```

**If step 4 fails:** 
- Check investigation_mapping.csv format (must have borehole_id and investigation_id)
- Verify all borehole IDs from bgi_verified_boreholes.csv are in mapping
- Check GEE export has all 14 features

**If step 5 fails:**
- Check n_samples > 0 (need at least some is_productive=1 or 0)
- Check investigation_id is NOT identical to location (check CSV directly)
- Ensure no all-null feature columns

---

## Key Improvements

✅ **Schema Enforcement:** No more silent synthetic data  
✅ **Explicit Validation:** Clear error messages if data incomplete  
✅ **Proper Grouping:** Farm-level spatial CV (investigation_id)  
✅ **Complete Documentation:** Pipeline README + data format guide  
✅ **Sample Data:** Example CSV for testing and reference  
✅ **GEE Template:** Ready-to-use feature extraction script  
✅ **Join Automation:** Merge + investigate_id assignment in one script  

---

**Next step:** Run through the entire pipeline (Steps 1–4 above) with actual 84-borehole dataset to verify Milestone 1 readiness.
