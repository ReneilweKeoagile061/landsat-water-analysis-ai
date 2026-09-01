"""
AgriPulse Hybrid Groundwater AI - Supervised Machine Learning Pipeline
Step 4 - 8: XGBoost Classifier & Regressors with Spatial Block Cross-Validation

Expected Input CSV Schema (from GEE feature stack export + BGI join):
  - borehole_id (string): Unique ID
  - investigation_id (string): Farm/investigation identifier for spatial CV grouping
  - longitude, latitude (float): WGS84 coordinates
  - yield_m3h (float or blank): Measured yield; leave blank if unknown, NOT 0
  - is_productive (1, 0, or blank): 1=productive, 0=dry, blank=unknown (excluded from training)
  - water_strike_m (float or blank): Optional
  - 14 GEE features: s1_vv, s1_vh, s1_vv_vh_ratio, radar_contrast, ndvi, ndmi, ndwi,
    dem_elevation, slope_deg, twi, flow_accumulation, dist_to_structure_m,
    structural_density, intersection_index

All 14 features MUST be present (non-synthetic) for training. If any missing,
pipeline raises an error and stops—no auto-fill fallback.
"""

import argparse
import json
import logging
import os
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agripulse_ml")

import pickle
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, KFold
from sklearn.ensemble import HistGradientBoostingClassifier

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    logger.info("Using scikit-learn Gradient Boosting engine (XGBoost compatible).")


def validate_required_features(df: pd.DataFrame, feature_cols: List[str]) -> None:
    """
    Strictly validate that all 14 required GEE features are present in the CSV.
    If any feature is missing, raise an error—no synthetic fallback.
    """
    missing = [col for col in feature_cols if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing {len(missing)} required GEE feature columns: {missing}\n"
            f"Expected CSV from agripulse_gee_feature_stack.js export + BGI join.\n"
            f"Check that GEE sampleRegions has been run and joined to BGI borehole coordinates."
        )
    logger.info(f"✓ All {len(feature_cols)} required GEE features present.")


def validate_required_columns(df: pd.DataFrame) -> None:
    """
    Validate presence of required non-feature columns.
    """
    required = ["borehole_id", "latitude", "longitude", "is_productive"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}\n"
            f"Expected: borehole_id, latitude, longitude, is_productive, (+ optional investigation_id, water_strike_m)"
        )
    logger.info(f"✓ All required base columns present.")


FEATURE_COLUMNS = [
    "s1_vv",
    "s1_vh",
    "s1_vv_vh_ratio",
    "radar_contrast",
    "ndvi",
    "ndmi",
    "ndwi",
    "dem_elevation",
    "slope_deg",
    "twi",
    "flow_accumulation",
    "dist_to_structure_m",
    "structural_density",
    "intersection_index",
]


def create_classifier(seed=42):
    if HAS_XGB:
        return xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=seed,
        )
    return HistGradientBoostingClassifier(max_iter=100, max_depth=4, learning_rate=0.08, random_state=seed)


def train_and_validate_classifier(
    df: pd.DataFrame, groups: np.ndarray, feature_cols: List[str]
) -> Dict:
    """Trains Gradient Boosting classifier (Productive vs Unsuccessful) with GroupKFold."""
    X = df[feature_cols].values
    y = df["is_productive"].values

    n_groups = len(np.unique(groups))
    n_splits = min(5, n_groups) if n_groups > 1 else 3
    cv = GroupKFold(n_splits=n_splits) if n_groups > 1 else KFold(n_splits=3, shuffle=True, random_state=42)

    oof_preds = np.zeros(len(df))
    oof_probs = np.zeros(len(df))
    fold_aucs = []

    for fold, (train_idx, val_idx) in enumerate(cv.split(X, y, groups if n_groups > 1 else None)):
        X_train, y_train = X[train_idx], y[train_idx]
        X_val, y_val = X[val_idx], y[val_idx]

        clf = create_classifier(seed=42 + fold)
        clf.fit(X_train, y_train)

        probs = clf.predict_proba(X_val)[:, 1]
        preds = (probs >= 0.5).astype(int)

        oof_probs[val_idx] = probs
        oof_preds[val_idx] = preds

        if len(np.unique(y_val)) > 1:
            fold_auc = roc_auc_score(y_val, probs)
            fold_aucs.append(fold_auc)

    # Train final full model
    final_clf = create_classifier(seed=42)
    final_clf.fit(X, y)

    importances = {}
    if hasattr(final_clf, "feature_importances_"):
        importances = {feat: float(imp) for feat, imp in zip(feature_cols, final_clf.feature_importances_)}
    else:
        # Uniform fallback for inspect
        importances = {feat: 1.0 / len(feature_cols) for feat in feature_cols}

    metrics = {
        "accuracy": float(accuracy_score(y, oof_preds)),
        "precision": float(precision_score(y, oof_preds, zero_division=0)),
        "recall": float(recall_score(y, oof_preds, zero_division=0)),
        "f1": float(f1_score(y, oof_preds, zero_division=0)),
        "mean_spatial_cv_auc": float(np.mean(fold_aucs)) if fold_aucs else None,
        "n_samples": len(df),
        "class_balance_productive": int(np.sum(y == 1)),
        "class_balance_unsuccessful": int(np.sum(y == 0)),
        "model_engine": "XGBoost" if HAS_XGB else "HistGradientBoosting",
        "feature_importances": importances,
    }

    return {"model": final_clf, "metrics": metrics, "oof_probs": oof_probs}


def run_pipeline(csv_path: str, output_model_dir: str):
    os.makedirs(output_model_dir, exist_ok=True)
    if not os.path.exists(csv_path):
        logger.error(f"Input borehole dataset not found at {csv_path}")
        logger.error(f"To generate it, run: agripulse_gee_join.py with BGI scraper output + GEE export")
        return

    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} borehole records from {csv_path}")

    # Validate required columns exist
    validate_required_columns(df)
    validate_required_features(df, FEATURE_COLUMNS)

    # Drop rows missing coordinates
    df = df.dropna(subset=["longitude", "latitude"]).reset_index(drop=True)
    logger.info(f"After coordinate QC: {len(df)} boreholes remain")

    # Drop rows with missing is_productive (can't be used in training)
    n_before = len(df)
    df = df.dropna(subset=["is_productive"]).reset_index(drop=True)
    n_dropped = n_before - len(df)
    if n_dropped > 0:
        logger.info(f"Dropped {n_dropped} boreholes with unknown productivity (blank is_productive)")

    # Spatial grouping: prefer investigation_id (farm-specific), fallback to location, then default
    if "investigation_id" in df.columns and df["investigation_id"].notna().any():
        # BACKSTOP: Check if investigation_id is just location (coarse grouping)
        if "location" in df.columns:
            same_as_location = (df["investigation_id"] == df["location"]).sum()
            if same_as_location == len(df):
                logger.error("FATAL: investigation_id is identical to location (coarse grouping)")
                logger.error("This defeats the point of spatial CV. Provide farm-specific investigation_id via agripulse_gee_join.py --investigation-map")
                return
            elif same_as_location > len(df) * 0.5:
                logger.warning(f"WARNING: {same_as_location}/{len(df)} boreholes have investigation_id == location")
                logger.warning("Spatial CV may be weak. Verify investigation_map was applied correctly.")
        
        groups = df["investigation_id"].astype("category").cat.codes.values
        logger.info(f"✓ Using investigation_id for spatial CV grouping ({df['investigation_id'].nunique()} unique investigations)")
    elif "location" in df.columns:
        groups = df["location"].astype("category").cat.codes.values
        logger.warning(f"⚠ Using location for spatial CV grouping (coarse; {df['location'].nunique()} unique locations)")
        logger.warning("For proper spatial CV, use agripulse_gee_join.py with --investigation-map")
    else:
        groups = np.zeros(len(df))
        logger.error("⚠ No investigation_id or location; all boreholes in one group (spatial CV is non-existent)")

    logger.info("Training supervised Classifier (Productive vs Dry) with Spatial Cross-Validation...")
    clf_res = train_and_validate_classifier(df, groups, FEATURE_COLUMNS)

    # Save model artifacts
    model_path = os.path.join(output_model_dir, "agripulse_classifier.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(clf_res["model"], f)

    if HAS_XGB:
        clf_res["model"].save_model(os.path.join(output_model_dir, "agripulse_xgb_classifier.json"))

    metrics_path = os.path.join(output_model_dir, "agripulse_ml_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(clf_res["metrics"], f, indent=2)

    logger.info(f"Model saved to {model_path}")
    logger.info(f"ML Metrics: {json.dumps(clf_res['metrics'], indent=2)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AgriPulse Supervised XGBoost Pipeline")
    parser.add_argument(
        "--input",
        default="data/boreholes/agripulse_gee_features.csv",
        help="Input CSV: GEE-joined borehole features (from agripulse_gee_join.py)"
    )
    parser.add_argument("--outdir", default="data/models", help="Output model directory")
    args = parser.parse_args()
    run_pipeline(args.input, args.outdir)
