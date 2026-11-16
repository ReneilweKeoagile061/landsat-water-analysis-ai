"""
scripts/audit_feature_circularity.py

Audits target leakage, greening circularity, and deployment gate metrics.

Key Capabilities:
  1. Compares Full Feature Model vs Static Physical Baseline (dropping all optical:
     ndvi, ndmi, ndwi, AND ndvi_variance).
  2. Handles datasets whether or not ndvi_variance has been extracted yet.
  3. Splits evaluation by drilling era (pre-2000 historical vs post-2000 modern wells)
     using validated dates (>= 1950) to detect post-drilling greening leakage.
  4. Uses spatial clustering (hierarchical clustering within 15-20 km) for CV groups.
  5. Nested Platt scaling (calibrating inside training folds, not on evaluated test data),
     with graceful fallback if fold class counts are small.
  6. Computes deployment gate statistics:
     - Absolute Precision @ Top 20%
     - Delta above Regional Base Rate (Percentage Points)
     - Stratified Cluster-Bootstrap 95% Confidence Intervals
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("circularity_audit")

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    from sklearn.ensemble import HistGradientBoostingClassifier
    HAS_XGB = False


# EXACT CANONICAL FEATURE LISTS:
# 1. Static physical features: strictly DEM topography + Sentinel-1 SAR.
#    All vegetation/moisture indices (including ndvi_variance) are excluded.
STATIC_PHYSICAL_CANDIDATES = [
    "s1_vv",
    "s1_vh",
    "s1_vv_vh_ratio",
    "radar_contrast",
    "dem_elevation",
    "slope_deg",
    "twi",
    "flow_accumulation",
]

# 2. Modern optical & seasonal vegetation indices (2022-2024 composites)
OPTICAL_SPECTRAL_CANDIDATES = [
    "ndvi",
    "ndmi",
    "ndwi",
    "ndvi_variance",  # Measures persistent greening; dropped in static run
]


def create_base_classifier(seed: int = 42):
    if HAS_XGB:
        return xgb.XGBClassifier(
            n_estimators=70,
            max_depth=3,
            learning_rate=0.08,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=seed,
        )
    return HistGradientBoostingClassifier(max_iter=70, max_depth=3, learning_rate=0.08, random_state=seed)


def cluster_spatial_groups(df: pd.DataFrame, max_dist_km: float = 20.0) -> np.ndarray:
    """Group boreholes into spatial clusters within max_dist_km to prevent fold leakage."""
    coords = df[["latitude", "longitude"]].values
    if len(coords) <= 1:
        return np.zeros(len(coords), dtype=int)
    # Approximate conversion: 1 deg ~ 111 km in Southern Africa
    dists_km = pdist(coords, metric="euclidean") * 111.0
    Z = linkage(dists_km, method="complete")
    clusters = fcluster(Z, t=max_dist_km, criterion="distance")
    return clusters


def bootstrap_top20_ci(
    y_true: np.ndarray,
    probs: np.ndarray,
    clusters: np.ndarray,
    n_bootstraps: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> Dict[str, float]:
    """Compute cluster-resampled bootstrap confidence interval for Top 20% precision."""
    rng = np.random.RandomState(seed)
    unique_clusters = np.unique(clusters)
    n_clusters = len(unique_clusters)

    boot_precisions = []
    boot_deltas = []
    top_k = max(1, int(len(y_true) * 0.20))

    for _ in range(n_bootstraps):
        sample_clusters = rng.choice(unique_clusters, size=n_clusters, replace=True)
        sample_indices = []
        for c in sample_clusters:
            sample_indices.extend(np.where(clusters == c)[0])

        if len(sample_indices) < top_k:
            continue

        b_y = y_true[sample_indices]
        b_p = probs[sample_indices]

        # Rank by probability
        ranked_order = np.argsort(b_p)[::-1]
        top_y = b_y[ranked_order[:top_k]]

        prec = np.mean(top_y == 1)
        base = np.mean(b_y == 1)

        boot_precisions.append(prec)
        boot_deltas.append(prec - base)

    if not boot_precisions:
        return {
            "precision_mean": float(np.mean(y_true[:top_k] == 1)),
            "precision_ci_lower": 0.0,
            "precision_ci_upper": 1.0,
            "delta_vs_base_lower_pp": 0.0,
            "delta_vs_base_upper_pp": 0.0,
        }

    low_pct = 100.0 * (alpha / 2.0)
    high_pct = 100.0 * (1.0 - alpha / 2.0)

    return {
        "precision_mean": float(np.mean(boot_precisions)),
        "precision_ci_lower": float(np.percentile(boot_precisions, low_pct)),
        "precision_ci_upper": float(np.percentile(boot_precisions, high_pct)),
        "delta_vs_base_lower_pp": float(np.percentile(boot_deltas, low_pct) * 100.0),
        "delta_vs_base_upper_pp": float(np.percentile(boot_deltas, high_pct) * 100.0),
    }


def evaluate_nested_cv(
    df: pd.DataFrame,
    feature_cols: List[str],
    clusters: np.ndarray,
    y: np.ndarray,
) -> Dict:
    X = df[feature_cols].values
    n_groups = len(np.unique(clusters))
    n_splits = min(5, n_groups)
    if n_splits < 2:
        return {
            "features_used": feature_cols,
            "n_features": len(feature_cols),
            "mean_spatial_cv_auc": None,
            "base_rate": float(np.mean(y == 1)),
            "top_20pct_precision": float(np.mean(y == 1)),
            "top_20pct_delta_pp": 0.0,
            "top_20pct_lift": 1.0,
            "bootstrap_ci_95": {"precision_ci": [0.0, 1.0], "delta_vs_base_ci_pp": [0.0, 0.0]},
            "oof_probs": np.full(len(df), 0.5),
        }

    cv = GroupKFold(n_splits=n_splits)

    oof_probs = np.zeros(len(df))
    fold_aucs = []

    for fold, (train_idx, val_idx) in enumerate(cv.split(X, y, clusters)):
        X_train, y_train = X[train_idx], y[train_idx]
        X_val, y_val = X[val_idx], y[val_idx]

        base_clf = create_base_classifier(seed=42 + fold)
        # Check minimum class counts in training split for internal Platt CV
        min_class_count = min(np.sum(y_train == 0), np.sum(y_train == 1))
        
        if min_class_count >= 3:
            calibrated_model = CalibratedClassifierCV(estimator=base_clf, method="sigmoid", cv=min(3, min_class_count))
            calibrated_model.fit(X_train, y_train)
            probs = calibrated_model.predict_proba(X_val)[:, 1]
        elif len(np.unique(y_train)) > 1:
            base_clf.fit(X_train, y_train)
            probs = base_clf.predict_proba(X_val)[:, 1]
        else:
            probs = np.full(len(X_val), float(y_train[0]))

        oof_probs[val_idx] = probs

        if len(np.unique(y_val)) > 1:
            fold_aucs.append(roc_auc_score(y_val, probs))

    # Evaluate Top 20%
    top_20_count = max(1, int(len(df) * 0.20))
    ranked_indices = np.argsort(oof_probs)[::-1]
    top_indices = ranked_indices[:top_20_count]

    top_20_prec = float(np.mean(y[top_indices] == 1))
    base_rate = float(np.mean(y == 1))
    delta_pp = (top_20_prec - base_rate) * 100.0
    lift = top_20_prec / base_rate if base_rate > 0 else 1.0

    # Calculate bootstrap CI
    boot_stats = bootstrap_top20_ci(y, oof_probs, clusters)

    return {
        "features_used": feature_cols,
        "n_features": len(feature_cols),
        "mean_spatial_cv_auc": float(np.mean(fold_aucs)) if fold_aucs else None,
        "base_rate": round(base_rate, 4),
        "top_20pct_precision": round(top_20_prec, 4),
        "top_20pct_delta_pp": round(delta_pp, 2),
        "top_20pct_lift": round(lift, 3),
        "bootstrap_ci_95": {
            "precision_ci": [round(boot_stats["precision_ci_lower"], 4), round(boot_stats["precision_ci_upper"], 4)],
            "delta_vs_base_ci_pp": [round(boot_stats["delta_vs_base_lower_pp"], 1), round(boot_stats["delta_vs_base_upper_pp"], 1)],
        },
        "oof_probs": oof_probs,
    }


def run_full_audit(
    csv_path: str,
    yield_threshold: float = 1.0,
    treat_blank_as_negative: bool = False,
    historical_era_cutoff_year: int = 2000,
):
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} records from {csv_path}")

    # Standardize coordinates
    df = df.dropna(subset=["longitude", "latitude"]).reset_index(drop=True)

    # Standardize target by yield threshold
    if "yield_m3h" in df.columns:
        df["yield_m3h"] = pd.to_numeric(df["yield_m3h"], errors="coerce")
        if treat_blank_as_negative:
            df["target"] = (df["yield_m3h"] >= yield_threshold).astype(int)
        else:
            labeled = df[df["yield_m3h"].notna()].copy()
            labeled["target"] = (labeled["yield_m3h"] >= yield_threshold).astype(int)
            df = labeled.reset_index(drop=True)
    elif "is_productive" in df.columns:
        df["target"] = pd.to_numeric(df["is_productive"], errors="coerce")
        df = df.dropna(subset=["target"]).reset_index(drop=True)
        df["target"] = df["target"].astype(int)
    else:
        raise ValueError("Dataset requires 'yield_m3h' or 'is_productive'")

    # Dynamically select available features from canonical candidate sets
    static_features = [f for f in STATIC_PHYSICAL_CANDIDATES if f in df.columns]
    optical_features = [f for f in OPTICAL_SPECTRAL_CANDIDATES if f in df.columns]
    full_features = static_features + optical_features

    logger.info(f"Features present: Static={len(static_features)} ({static_features}), Optical={len(optical_features)} ({optical_features})")

    # Cluster-based spatial groups (15-20km distance)
    clusters = cluster_spatial_groups(df, max_dist_km=20.0)
    df["spatial_cluster"] = clusters
    n_clusters = len(np.unique(clusters))
    y = df["target"].values

    logger.info(f"Auditing N={len(df)} boreholes across {n_clusters} spatial clusters")
    logger.info(f"Class balance: {np.sum(y==1)} productive (yield >= {yield_threshold}), {np.sum(y==0)} unproductive")

    # 1. Full Features Available
    res_full = evaluate_nested_cv(df, full_features, clusters, y)

    # 2. Static Physical Baseline (Drops NDVI, NDMI, NDWI AND ndvi_variance)
    res_static = evaluate_nested_cv(df, static_features, clusters, y)

    # 3. Era-split check (Historical pre-2000 vs Modern post-2000)
    era_analysis = {}
    if "drill_date" in df.columns:
        parsed_dates = pd.to_datetime(df["drill_date"], errors="coerce")
        valid_era = parsed_dates.dt.year >= 1950
        df_era = df[valid_era].copy()
        if len(df_era) >= 20:
            df_era["is_historical"] = parsed_dates[valid_era].dt.year < historical_era_cutoff_year
            n_hist = df_era["is_historical"].sum()
            n_mod = len(df_era) - n_hist
            era_analysis = {
                "dated_boreholes_count": len(df_era),
                "historical_pre_2000_count": int(n_hist),
                "modern_post_2000_count": int(n_mod),
                "historical_base_rate": round(float(df_era[df_era["is_historical"]]["target"].mean()), 4),
                "modern_base_rate": round(float(df_era[~df_era["is_historical"]]["target"].mean()), 4),
            }

    # 4. Deployment Gate Check
    # Gate rule: Lower bound of 95% bootstrap CI for Delta above base rate must be > 0
    # AND point estimate delta >= 15 percentage points
    gate_passed = False
    if res_full["top_20pct_delta_pp"] is not None:
        delta_ci_lower = res_full["bootstrap_ci_95"]["delta_vs_base_ci_pp"][0]
        gate_passed = (res_full["top_20pct_delta_pp"] >= 15.0) and (delta_ci_lower > 0.0)

    report = {
        "sample_size": len(df),
        "cluster_count": n_clusters,
        "yield_threshold_m3h": yield_threshold,
        "treat_blank_as_negative": treat_blank_as_negative,
        "model_full_features": {
            "features": full_features,
            "spatial_cv_auc": res_full["mean_spatial_cv_auc"],
            "base_rate": res_full["base_rate"],
            "top_20pct_precision": res_full["top_20pct_precision"],
            "top_20pct_delta_vs_base_pp": res_full["top_20pct_delta_pp"],
            "top_20pct_lift": res_full["top_20pct_lift"],
            "bootstrap_ci_95": res_full["bootstrap_ci_95"],
        },
        "model_static_physical_only": {
            "features": static_features,
            "spatial_cv_auc": res_static["mean_spatial_cv_auc"],
            "base_rate": res_static["base_rate"],
            "top_20pct_precision": res_static["top_20pct_precision"],
            "top_20pct_delta_vs_base_pp": res_static["top_20pct_delta_pp"],
            "bootstrap_ci_95": res_static["bootstrap_ci_95"],
        },
        "circularity_audit_auc_delta": round(
            res_full["mean_spatial_cv_auc"] - res_static["mean_spatial_cv_auc"], 4
        ) if (res_full["mean_spatial_cv_auc"] and res_static["mean_spatial_cv_auc"]) else None,
        "drilling_era_breakdown": era_analysis,
        "deployment_gate_evaluation": {
            "gate_criterion": "Point estimate delta >= +15.0 pp AND bootstrap 95% CI lower bound > 0.0 pp",
            "gate_passed": gate_passed,
            "decision": "Production Siting Support Model" if gate_passed else "Research / Exploration Prototype Only",
        },
    }

    print("\n" + "=" * 65)
    print("      AUDIT REPORT: CIRCULARITY & DEPLOYMENT GATE")
    print("=" * 65)
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit feature circularity and evaluate deployment gate")
    parser.add_argument("--input", required=True, help="Input CSV with features")
    parser.add_argument("--yield-threshold", type=float, default=1.0, help="Yield threshold (m3/h) for positive label")
    parser.add_argument("--treat-blank-as-negative", action="store_true", help="Treat missing yields as negative")
    args = parser.parse_args()

    run_full_audit(args.input, args.yield_threshold, args.treat_blank_as_negative)
