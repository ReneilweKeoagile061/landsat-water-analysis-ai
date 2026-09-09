#!/usr/bin/env python3
"""
Quick verification of AgriPulse Phase 1 pipeline.
Tests each stage with sample data to ensure everything works before using real data.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a shell command and report status."""
    print(f"\n{'='*70}")
    print(f"🧪 {description}")
    print(f"{'='*70}")
    print(f"$ {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"❌ FAILED: {description}")
        return False
    print(f"✅ PASSED: {description}")
    return True

def main():
    base_dir = Path(__file__).parent.parent
    script_dir = base_dir / "scripts"
    data_dir = base_dir / "data" / "boreholes"
    
    # Try to import sklearn for GroupKFold test
    try:
        from sklearn.model_selection import GroupKFold
        HAS_SKLEARN = True
    except ImportError:
        HAS_SKLEARN = False
    
    print("\n" + "="*70)
    print("AgriPulse Phase 1 Pipeline Verification")
    print("="*70)
    print(f"Base directory: {base_dir}")
    
    # Check that sample files exist
    sample_csv = data_dir / "agripulse_gee_features_sample.csv"
    if not sample_csv.exists():
        print(f"❌ ERROR: Sample CSV not found at {sample_csv}")
        return False
    
    print(f"\n✅ Sample data found at {sample_csv}")
    
    # Test 1: Validate sample CSV format
    print("\n" + "-"*70)
    print("📋 Step 1: Validate Sample CSV Format")
    print("-"*70)
    try:
        import pandas as pd
        df = pd.read_csv(sample_csv)
        print(f"✅ Sample CSV loads successfully ({len(df)} rows)")
        
        required_cols = [
            "borehole_id", "investigation_id", "latitude", "longitude",
            "is_productive", "yield_m3h", "water_strike_m",
            "s1_vv", "s1_vh", "s1_vv_vh_ratio", "radar_contrast",
            "ndvi", "ndmi", "ndwi",
            "dem_elevation", "slope_deg", "twi", "flow_accumulation",
            "dist_to_structure_m", "structural_density", "intersection_index"
        ]
        
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            print(f"❌ Missing columns: {missing}")
            return False
        print(f"✅ All {len(required_cols)} required columns present")
        
        # Check investigation_id values
        unique_inv = df["investigation_id"].unique()
        print(f"✅ Investigation IDs: {list(unique_inv)}")
        
        # Verified dry holes may have yield=0.0. Missing yield must not be stored as 0.
        missing_yield_marked_dry = df["yield_m3h"].isna() & (df["is_productive"] == 0)
        if missing_yield_marked_dry.any():
            print(
                f"❌ FATAL: {int(missing_yield_marked_dry.sum())} rows have missing yield labeled dry"
            )
            return False
        zero_yield = (df["yield_m3h"] == 0.0).sum()
        if zero_yield > 0:
            print(f"ℹ️  {zero_yield} rows have yield=0.0 (allowed only as verified dry)")
        
        # Check that investigation_id is not identical to location
        has_location = "location" in df.columns
        if has_location:
            same = (df["investigation_id"] == df["location"]).sum()
            if same == len(df):
                print(f"❌ FATAL: investigation_id is identical to location (coarse grouping)")
                return False
            elif same > 0:
                print(f"⚠️  WARNING: {same}/{len(df)} rows have investigation_id == location")
        
    except Exception as e:
        print(f"❌ Failed to load sample CSV: {e}")
        return False
    
    # Test 1b: Verify data is actually trainable (GroupKFold + class balance)
    print("\n" + "-"*70)
    print("📊 Step 1b: Verify Data is Trainable")
    print("-"*70)
    try:
        # Filter to rows with productivity label (this is what ML pipeline trains on)
        trainable_rows = df[df["is_productive"].notna() & (df["is_productive"] != "")]
        if len(trainable_rows) == 0:
            print(f"❌ FATAL: No trainable rows (all is_productive values are missing/blank)")
            print(f"   Loaded {len(df)} rows but {len(df)} have missing is_productive")
            return False
        
        print(f"✅ Trainable rows: {len(trainable_rows)}/{len(df)} (rows with is_productive label)")
        
        # Check class balance
        class_counts = trainable_rows["is_productive"].value_counts()
        print(f"   Class distribution: {dict(class_counts)}")
        if len(class_counts) < 2:
            print(f"❌ FATAL: Only {len(class_counts)} class present (need both 0 and 1)")
            return False
        
        # Check investigation_id grouping for GroupKFold
        n_groups = trainable_rows["investigation_id"].nunique()
        print(f"✅ Investigation groups: {n_groups} unique investigations")
        if n_groups < 2:
            print(f"❌ WARNING: Only {n_groups} investigation group (GroupKFold needs >= 2)")
        
        # Simulate GroupKFold to verify it can actually split
        if HAS_SKLEARN:
            print("\n   Testing GroupKFold split capability:")
            gkf = GroupKFold(n_splits=min(5, n_groups))  # Use min(5, n_groups) to avoid failure with small groups
            groups_array = trainable_rows["investigation_id"].astype("category").cat.codes.values
            
            fold_count = 0
            for train_idx, test_idx in gkf.split(trainable_rows, groups=groups_array):
                fold_count += 1
                # Verify no group leakage
                train_groups = set(groups_array[train_idx])
                test_groups = set(groups_array[test_idx])
                if train_groups & test_groups:  # intersection
                    print(f"   ❌ FOLD {fold_count}: Group leakage detected!")
                    return False
            
            print(f"   ✅ GroupKFold successful: {fold_count} folds with no group leakage")
        else:
            print("   ⚠️  scikit-learn not available (skipping GroupKFold test)")
            
    except Exception as e:
        print(f"❌ Trainability check failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Run ML pipeline with sample data
    print("\n" + "-"*70)
    print("🤖 Step 2: Test ML Pipeline with Sample Data")
    print("-"*70)
    
    pipeline_script = script_dir / "agripulse_ml_pipeline.py"
    if not pipeline_script.exists():
        print(f"⚠️  Pipeline script not found at {pipeline_script}")
        print("   (This is OK for verification; file may not be created yet)")
    else:
        cmd = [
            sys.executable, str(pipeline_script),
            "--input", str(sample_csv),
            "--outdir", str(base_dir / "data" / "models_test")
        ]
        if not run_command(cmd, "Run ML pipeline with sample data"):
            print("\n❌ Pipeline test failed. Check that:")
            print("   - agripulse_ml_pipeline.py is in scripts/")
            print("   - Sample CSV has valid data")
            print("   - XGBoost and scikit-learn are installed")
            return False
    
    # Test 3: Verify investigation mapping requirement
    print("\n" + "-"*70)
    print("📊 Step 3: Verify Investigation Mapping")
    print("-"*70)
    
    join_script = script_dir / "agripulse_gee_join.py"
    if join_script.exists():
        inv_map_sample = data_dir / "investigation_map_sample.csv"
        if inv_map_sample.exists():
            print(f"✅ Investigation mapping template found at {inv_map_sample}")
            
            # Try to import and check logic
            try:
                # Load the sample map
                inv_map = pd.read_csv(inv_map_sample)
                print(f"✅ Sample mapping has {len(inv_map)} entries")
                
                if "borehole_id" in inv_map.columns and "investigation_id" in inv_map.columns:
                    print(f"✅ Mapping has required columns: borehole_id, investigation_id")
                else:
                    print(f"❌ Mapping missing required columns")
                    return False
                    
            except Exception as e:
                print(f"⚠️  Could not verify mapping format: {e}")
        else:
            print(f"⚠️  Investigation mapping template not found")
            print(f"   (This is OK; create one at {inv_map_sample})")
    
    # Summary
    print("\n" + "="*70)
    print("✅ VERIFICATION COMPLETE")
    print("="*70)
    print("""
Next steps to run with real data:

1. Create investigation_mapping.csv for your 84 boreholes
   - Format: borehole_id, investigation_id
   - Run agripulse_gee_join.py with --investigation-map parameter

2. Run GEE feature extraction:
   - Use agripulse_gee_feature_stack.js in Google Earth Engine
   - Download CSV from GEE

3. Join BGI + GEE data:
   $ python scripts/agripulse_gee_join.py \\
       --bgi data/boreholes/bgi_verified_boreholes.csv \\
       --gee agripulse_bgi_ml_features.csv \\
       --output data/boreholes/agripulse_gee_features.csv \\
       --investigation-map data/boreholes/investigation_mapping.csv

4. Train model:
   $ python scripts/agripulse_ml_pipeline.py \\
       --input data/boreholes/agripulse_gee_features.csv \\
       --outdir data/models
""")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
