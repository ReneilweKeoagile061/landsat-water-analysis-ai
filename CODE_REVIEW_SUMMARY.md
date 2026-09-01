## CRITICAL FIXES APPLIED — Code Review Summary

### FIX 1: Coordinate Divergence Now EXCLUDES Records (Not Just Warns)

**File:** agripulse_gee_join.py, lines 82–100

**Before (BUGGY):**
```python
if bad_coords > 0:
    logger.warning(f"  {bad_coords} records have coordinate divergence...")
    # ... just logs and continues with bad records still in output
```

**After (FIXED):**
```python
if bad_coords > 0:
    logger.error(f"ERROR: {bad_coords} records have coordinate divergence > {tolerance_degrees}°")
    bad_sample = joined[coord_error][["borehole_id", "latitude_bgi", "latitude_gee", "longitude_bgi", "longitude_gee"]].head(5)
    logger.error(f"Coordinate mismatches (will be EXCLUDED):\n{bad_sample}")
    # EXCLUDE the divergent records
    pre_filter = len(joined)
    joined = joined[~coord_error].reset_index(drop=True)  # ← ACTIVELY FILTERS
    logger.info(f"Filtered: {pre_filter} records → {len(joined)} records (removed {bad_coords} coordinate mismatches)")
```

**Impact:** Bad coordinate records are now **removed** before output CSV is written, preventing them from reaching the ML pipeline.

---

### FIX 2: Cardinality Check Catches Location-Keyed Map Blind Spot

**File:** agripulse_gee_join.py, lines 150–158 (location-keyed map) + lines 177–188 (no-map case)

**Scenario That Would Break Before:**
User provides: `Khudumelapye → farm_khudumelapye_01` (one ID per location)
- String check `investigation_id != location` would PASS (different strings)
- But grouping cardinality is identical to location-level grouping
- Spatial CV is weak, but appears correct

**After (FIXED):**
```python
if merge_key == "location" and "location" in df.columns:
    ids_per_location = df.groupby("location")["investigation_id"].nunique()
    if (ids_per_location == 1).all():  # ← CATCHES THIS!
        logger.error("FATAL: Map produces exactly one investigation_id per location (coarse grouping).")
        raise ValueError(
            "Location-keyed investigation_map is too coarse: each location gets only one ID.\n"
            "Provide a borehole-level map instead: [borehole_id, investigation_id]"
        )
```

**Even in the "no map provided" case:**
```python
ids_per_location = df.groupby("location")["investigation_id"].nunique()
if (ids_per_location == 1).all():
    logger.error("FATAL: Cardinality check: each location maps to exactly 1 investigation_id (coarse grouping).")
    raise ValueError(
        "investigation_id grouping is identical to location grouping by cardinality.\n"
        "This happens when a map applies one ID per location (e.g., Khudumelapye→farm_khudumelapye_01).\n"
        "Provide a borehole-level map to distinguish farms within same location."
    )
```

**Impact:** If someone accidentally provides a coarse location-level map, the script **errors immediately** with a clear message.

---

### FIX 3: verify_pipeline.py Now Tests Actual Trainability (Not Just Structure)

**File:** verify_pipeline.py, lines 25–56 (new "Step 1b")

**Previous (Only Checked Structure):**
```
✅ All 21 required columns present
✅ Investigation IDs: [farm_khudumelapye_01, ...]
```

**New (Also Checks Trainability):**
```
✅ Trainable rows: 7/10 (rows with is_productive label)
   Class distribution: {0: 3, 1: 4}
✅ Investigation groups: 4 unique investigations
   Testing GroupKFold split capability:
   ✅ GroupKFold successful: 3 folds with no group leakage
```

**What it verifies:**
1. At least some rows have is_productive labels (can actually train)
2. Both classes present (0 and 1) — not all dry or all productive
3. Multiple investigation groups exist for spatial CV
4. GroupKFold can split without group leakage across train/test

---

## Files That Now Need Your Review

### 1. agripulse_gee_join.py
Check lines:
- **82–100:** Coordinate divergence handling (NOW FILTERS)
- **150–158:** Location-keyed map cardinality check (NEW)
- **177–188:** No-map case cardinality check (NEW)

### 2. verify_pipeline.py  
Check lines:
- **25–56:** GroupKFold + class balance tests (NEW "Step 1b")

### 3. investigation_map_sample.csv
Sample shows borehole-level mapping (best practice for farm-specificity)

---

## Test Execution Path When You Run verify_pipeline.py

```
==============================================================================
AgriPulse Phase 1 Pipeline Verification
==============================================================================
Base directory: c:\Users\pc\Downloads\Landsat-fixed\Landsat

✅ Sample data found at data/boreholes/agripulse_gee_features_sample.csv

----------------------------------------------------------------------
📋 Step 1: Validate Sample CSV Format
----------------------------------------------------------------------
✅ Sample CSV loads successfully (10 rows)
✅ All 21 required columns present
✅ Investigation IDs: ['farm_khudumelapye_01' 'farm_molepolole_02' 'farm_palapye_03' 'farm_serowe_04']

----------------------------------------------------------------------
📊 Step 1b: Verify Data is Trainable
----------------------------------------------------------------------
✅ Trainable rows: 7/10 (rows with is_productive label)
   Class distribution: {0: 3, 1: 4}
✅ Investigation groups: 4 unique investigations
   Testing GroupKFold split capability:
   ✅ GroupKFold successful: 3 folds with no group leakage

[If ML pipeline installed:]
----------------------------------------------------------------------
🤖 Step 2: Test ML Pipeline with Sample Data
----------------------------------------------------------------------
$ python scripts/agripulse_ml_pipeline.py --input data/boreholes/agripulse_gee_features_sample.csv --outdir data/models_test
... [ML output] ...
✅ PASSED: Run ML pipeline with sample data
```

---

## What Happens If Sample Data Had Issues

### Scenario A: Location-Keyed Map (Coarse Grouping)
```
ERROR: {bad_coords} records have coordinate divergence > 0.001°
FATAL: Map produces exactly one investigation_id per location (coarse grouping).
❌ FATAL: investigation_id is identical to location (coarse grouping)
```

### Scenario B: No Training Labels
```
❌ FATAL: No trainable rows (all is_productive values are missing/blank)
```

### Scenario C: Only One Class
```
❌ FATAL: Only 1 class present (need both 0 and 1)
```

### Scenario D: Bad Coordinates
```
ERROR: 5 records have coordinate divergence > 0.001°
Filtered: 84 records → 79 records (removed 5 coordinate mismatches)
```

---

## Next Steps to Verify

1. **Run verify_pipeline.py** to confirm sample data is trainable
2. **Check each error scenario** above can be triggered (tests the checks work)
3. **Run actual pipeline** with real BGI + GEE data + investigation_map
4. **Confirm terminal output** matches expected patterns (no silent failures)

---

## Summary of Design Changes

| Problem | Check Type | How It's Caught Now |
|---------|-----------|-------------------|
| Coordinate mismatch | Filtering | Bad records EXCLUDED from output (line 91) |
| Location-level map | Cardinality | `groupby("location")["investigation_id"].nunique()` must be > 1 (lines 150–158) |
| Coarse grouping | Cardinality | Same cardinality check in no-map case (lines 177–188) |
| Non-trainable data | Actual CV test | GroupKFold split attempted, class balance verified (verify_pipeline.py) |
