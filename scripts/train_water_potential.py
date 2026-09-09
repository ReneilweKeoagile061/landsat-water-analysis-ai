"""Train water-potential / productivity models against borehole ground truth.

K-Means cluster labels are not used. Unknown productivity is excluded.
Spatial validation is geographic (AOI holdout / longitude blocks), not random rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from subsurface_metrics import volumetric_water_change_mm

SPECTRAL_FEATURES = [
    "ndwi",
    "mndwi",
    "awei_nsh",
    "awei_sh",
    "ndvi",
    "evi",
    "ndmi",
    "lswi",
    "wri",
    "moisture_ratio",
    "water_score_norm",
]


def feature_columns(df: pd.DataFrame) -> list[str]:
    cols = [col for col in SPECTRAL_FEATURES if col in df.columns]
    if "slope" in df.columns:
        cols.append("slope")
    return cols


def spatial_blocks(df: pd.DataFrame, n_blocks: int = 5, lon_col: str = "lon_wgs84") -> pd.Series:
    return pd.qcut(df[lon_col], q=n_blocks, labels=False, duplicates="drop")


def _lon_col(df: pd.DataFrame) -> str:
    if "lon_wgs84" in df.columns:
        return "lon_wgs84"
    if "longitude" in df.columns:
        return "longitude"
    raise ValueError("Need lon_wgs84 or longitude for spatial blocks")


def _lat_col(df: pd.DataFrame) -> str:
    if "lat_wgs84" in df.columns:
        return "lat_wgs84"
    if "latitude" in df.columns:
        return "latitude"
    raise ValueError("Need lat_wgs84 or latitude")


def exclude_unknown_labels(df: pd.DataFrame, label_col: str = "is_productive") -> pd.DataFrame:
    work = df.copy()
    work[label_col] = pd.to_numeric(work[label_col], errors="coerce")
    work = work.dropna(subset=[label_col]).reset_index(drop=True)
    work[label_col] = work[label_col].astype(int)
    if work.empty:
        raise ValueError("No trainable rows: all labels are unknown/missing")
    return work


def apply_storage_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Convert recorded drawdown (dh) to millimetres of water using S or Sy.

    Requires drawdown_m (not raw static water level) and aquifer_class.
    """
    work = df.copy()
    if "drawdown_m" not in work.columns:
        return work
    if "aquifer_class" not in work.columns:
        raise ValueError("drawdown_m present but aquifer_class missing; refuse to guess storage")
    values = []
    for _, row in work.iterrows():
        if pd.isna(row["drawdown_m"]):
            values.append(np.nan)
            continue
        values.append(volumetric_water_change_mm(float(row["drawdown_m"]), str(row["aquifer_class"])))
    work["delta_gw_mm"] = values
    return work


def create_classifier(seed: int = 42):
    try:
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=80,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=seed,
            n_jobs=1,
        )
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingClassifier

        return HistGradientBoostingClassifier(
            max_iter=80, max_depth=5, learning_rate=0.1, random_state=seed
        )


def aoi_holdout_scores(
    df: pd.DataFrame,
    label_col: str = "is_productive",
    train_aois: tuple[str, ...] = ("OKAVANGO", "TRANSITIONAL"),
    test_aoi: str = "KALAHARI",
) -> dict:
    """Train on named AOIs, test on a geographically separate block."""
    if "aoi" not in df.columns:
        raise ValueError("aoi column required for geographic holdout")
    work = exclude_unknown_labels(df, label_col)
    cols = feature_columns(work)
    if not cols:
        raise ValueError("No spectral feature columns present")
    train_mask = work["aoi"].astype(str).str.upper().isin(train_aois)
    test_mask = work["aoi"].astype(str).str.upper() == test_aoi
    train = work[train_mask]
    test = work[test_mask]
    if train.empty or test.empty:
        raise ValueError(
            f"Holdout needs rows in {train_aois} and {test_aoi}; "
            f"got train={len(train)}, test={len(test)}"
        )
    model = create_classifier()
    model.fit(train[cols], train[label_col])
    pred = model.predict(test[cols])
    metrics = {
        "train_aois": list(train_aois),
        "test_aoi": test_aoi,
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "accuracy": float(accuracy_score(test[label_col], pred)),
        "weighted_f1": float(f1_score(test[label_col], pred, average="weighted", zero_division=0)),
        "target": "borehole_is_productive",
        "metric_interpretation": "geographic_holdout_against_borehole_labels",
    }
    if hasattr(model, "predict_proba") and test[label_col].nunique() > 1:
        proba = model.predict_proba(test[cols])
        if proba.shape[1] == 2:
            metrics["auc"] = float(roc_auc_score(test[label_col], proba[:, 1]))
    return metrics


def longitude_block_scores(
    df: pd.DataFrame,
    n_blocks: int = 5,
    label_col: str = "is_productive",
) -> dict:
    """Leave-one-longitude-block-out against borehole labels (no cluster relabeling)."""
    work = exclude_unknown_labels(df, label_col)
    lon = _lon_col(work)
    work = work.copy()
    work["spatial_block"] = spatial_blocks(work, n_blocks=n_blocks, lon_col=lon)
    cols = feature_columns(work)
    blocks = []
    for block in sorted(work["spatial_block"].dropna().unique()):
        train = work[work["spatial_block"] != block]
        test = work[work["spatial_block"] == block]
        if train[label_col].nunique() < 2 or test.empty:
            continue
        model = create_classifier(seed=42 + int(block))
        model.fit(train[cols], train[label_col])
        pred = model.predict(test[cols])
        blocks.append(round(float(accuracy_score(test[label_col], pred)), 4))
    return {
        "blocks": blocks,
        "mean": round(float(np.mean(blocks)), 4) if blocks else None,
        "target": "borehole_is_productive",
    }


def join_features_to_boreholes(
    features: pd.DataFrame, boreholes: pd.DataFrame, tolerance_deg: float = 0.01
) -> pd.DataFrame:
    """Nearest-neighbour join of screening points to borehole labels."""
    feat = features.copy()
    bh = exclude_unknown_labels(boreholes)
    fx, fy = _lon_col(feat), _lat_col(feat)
    bx, by = _lon_col(bh), _lat_col(bh)
    labels = []
    for _, row in feat.iterrows():
        dist = np.hypot(bh[bx] - row[fx], bh[by] - row[fy])
        j = int(dist.idxmin())
        if float(dist.loc[j]) > tolerance_deg:
            labels.append(np.nan)
        else:
            labels.append(int(bh.loc[j, "is_productive"]))
    feat["is_productive"] = labels
    return feat


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train against borehole productivity labels with spatial holdout."
    )
    parser.add_argument("--input", required=True, help="CSV/parquet of spectral features.")
    parser.add_argument("--boreholes", help="CSV of BGI/verified wells with is_productive.")
    parser.add_argument("--metrics-out", help="Write spatial-CV JSON here.")
    parser.add_argument(
        "--holdout-aoi",
        default="KALAHARI",
        help="AOI held out of training (default: KALAHARI).",
    )
    args = parser.parse_args()

    path = Path(args.input)
    df = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    if args.boreholes:
        bh = pd.read_csv(args.boreholes)
        df = join_features_to_boreholes(df, bh)
    if "is_productive" not in df.columns:
        raise SystemExit(
            "FATAL: is_productive is required. This script no longer trains on K-Means labels. "
            "Pass --boreholes or include is_productive in --input."
        )
    df = apply_storage_targets(df)
    df = exclude_unknown_labels(df)
    print(df["is_productive"].value_counts().sort_index().to_string())

    payload: dict = {"n_samples": int(len(df))}
    if "aoi" in df.columns and df["aoi"].astype(str).str.upper().nunique() > 1:
        train_aois = tuple(
            sorted(
                a
                for a in df["aoi"].astype(str).str.upper().unique()
                if a != args.holdout_aoi.upper()
            )
        )
        payload["aoi_holdout"] = aoi_holdout_scores(
            df, train_aois=train_aois, test_aoi=args.holdout_aoi.upper()
        )
    payload["longitude_blocks"] = longitude_block_scores(df)
    print(json.dumps(payload, indent=2))
    if args.metrics_out:
        Path(args.metrics_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
