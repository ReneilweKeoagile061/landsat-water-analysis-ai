"""Train water-potential models with holdout-safe labels.

Optional slope column is included when present. XGBoost is imported only when
training, so unit tests can import helpers without the extra dependency.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from labeling import assign_kmeans_labels

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


def spatial_cv_scores(df: pd.DataFrame, n_blocks: int = 5, lon_col: str = "lon_wgs84") -> dict:
    """Relabel each fold with K-Means fitted outside the holdout block, then score XGBoost."""
    from xgboost import XGBClassifier

    work = df.copy()
    work["spatial_block"] = spatial_blocks(work, n_blocks=n_blocks, lon_col=lon_col)
    blocks = []
    for block in sorted(work["spatial_block"].dropna().unique()):
        labeled = assign_kmeans_labels(
            work,
            holdout_region={"block": int(block), "n_blocks": n_blocks},
            lon_col=lon_col,
        )
        cols = feature_columns(labeled)
        train = labeled[labeled["spatial_block"] != block]
        test = labeled[labeled["spatial_block"] == block]
        model = XGBClassifier(
            n_estimators=80,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="mlogloss",
            random_state=42,
            n_jobs=1,
        )
        model.fit(train[cols], train["water_potential_class"])
        pred = model.predict(test[cols])
        acc = float(accuracy_score(test["water_potential_class"], pred))
        blocks.append(round(acc, 4))

    return {"blocks": blocks, "mean": round(float(np.mean(blocks)), 4)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train water-potential classifier with holdout-safe labels.")
    parser.add_argument("--input", required=True, help="Parquet/CSV of spectral features.")
    parser.add_argument("--metrics-out", help="Write spatial-CV JSON here.")
    parser.add_argument("--skip-cv", action="store_true", help="Only assign labels, do not train.")
    args = parser.parse_args()

    path = Path(args.input)
    df = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    labeled = assign_kmeans_labels(df, holdout_region=None)
    print(labeled["water_potential_class"].value_counts().sort_index().to_string())

    if args.skip_cv:
        return

    scores = spatial_cv_scores(labeled)
    print(json.dumps(scores, indent=2))
    if args.metrics_out:
        Path(args.metrics_out).write_text(json.dumps(scores, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
