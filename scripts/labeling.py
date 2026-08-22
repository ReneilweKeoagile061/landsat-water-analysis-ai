"""K-Means water-potential labels with optional spatial holdout.

Fitting on the full dataset, then holding out regions only from the classifier,
lets K-Means leak holdout structure into the labels. Pass holdout_region so
.fit() never sees the excluded block.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

try:
    from .indices import ndwi as ndwi_index
except ImportError:
    from indices import ndwi as ndwi_index

CLUSTER_FEATURES = ["ndwi", "mndwi", "ndvi", "awei_nsh", "water_score_norm"]
CLASS_NAMES = {0: "Low", 1: "Medium", 2: "High"}


def add_water_score(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["water_score"] = (
        0.35 * work["ndwi"]
        + 0.35 * work["mndwi"]
        + 0.15 * work["awei_nsh"]
        + 0.10 * work["ndmi"]
        + -0.05 * work["ndvi"]
    )
    lo = work["water_score"].min()
    hi = work["water_score"].max()
    span = hi - lo if hi != lo else 1.0
    work["water_score_norm"] = (work["water_score"] - lo) / span
    return work


def holdout_mask(df: pd.DataFrame, holdout_region, lon_col: str = "lon_wgs84") -> np.ndarray:
    """True for rows excluded from K-Means.fit()."""
    n = len(df)
    if holdout_region is None:
        return np.zeros(n, dtype=bool)

    if isinstance(holdout_region, np.ndarray):
        mask = np.asarray(holdout_region, dtype=bool)
        if mask.shape != (n,):
            raise ValueError("holdout mask length must match dataframe")
        return mask

    if isinstance(holdout_region, (int, np.integer)):
        holdout_region = {"block": int(holdout_region), "n_blocks": 5}

    if isinstance(holdout_region, dict):
        if "mask" in holdout_region:
            return holdout_mask(df, holdout_region["mask"], lon_col)
        if "lon_min" in holdout_region or "lon_max" in holdout_region:
            lon = df[lon_col].to_numpy()
            mask = np.ones(n, dtype=bool)
            if "lon_min" in holdout_region:
                mask &= lon >= float(holdout_region["lon_min"])
            if "lon_max" in holdout_region:
                mask &= lon < float(holdout_region["lon_max"])
            return mask
        if "block" in holdout_region:
            n_blocks = int(holdout_region.get("n_blocks", 5))
            block = int(holdout_region["block"])
            if "spatial_block" in df.columns:
                return df["spatial_block"].to_numpy() == block
            blocks = pd.qcut(df[lon_col], q=n_blocks, labels=False, duplicates="drop")
            return np.asarray(blocks) == block

    raise TypeError(f"Unsupported holdout_region: {type(holdout_region)!r}")


def assign_kmeans_labels(
    df: pd.DataFrame,
    holdout_region=None,
    n_clusters: int = 3,
    random_state: int = 42,
    lon_col: str = "lon_wgs84",
) -> pd.DataFrame:
    """Fit K-Means on non-holdout rows, then label the full frame."""
    missing = [col for col in ("ndwi", "mndwi", "ndvi", "awei_nsh", "ndmi") if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    work = add_water_score(df)
    excluded = holdout_mask(work, holdout_region, lon_col=lon_col)
    fit_mask = ~excluded
    if fit_mask.sum() < n_clusters:
        raise ValueError("Not enough non-holdout samples to fit K-Means")

    features = work[CLUSTER_FEATURES].to_numpy(dtype=np.float64)
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    kmeans.fit(features[fit_mask])
    work["cluster"] = kmeans.predict(features)

    cluster_means = (
        work.loc[fit_mask].groupby("cluster")["water_score_norm"].mean().sort_values()
    )
    cluster_mapping = {int(cluster_means.index[i]): i for i in range(len(cluster_means))}
    work["water_potential_class"] = work["cluster"].map(cluster_mapping).astype(int)
    work["held_out"] = excluded
    return work


def rule_based_labels(ndwi_values, low_max: float = 0.0, high_min: float = 0.3) -> np.ndarray:
    """Independent NDWI thresholds from the landholder guide (not K-Means)."""
    values = np.asarray(ndwi_values, dtype=np.float64)
    labels = np.ones(values.shape, dtype=int)
    labels[values < low_max] = 0
    labels[values > high_min] = 2
    return labels


def label_agreement(rule_labels, kmeans_labels) -> dict:
    rule = np.asarray(rule_labels)
    kmeans = np.asarray(kmeans_labels)
    if rule.shape != kmeans.shape:
        raise ValueError("Label arrays must have the same shape")
    n = len(rule)
    if n == 0:
        raise ValueError("Cannot score empty labels")

    agreement = float((rule == kmeans).mean())
    rule_p = np.array([(rule == c).mean() for c in range(3)], dtype=np.float64)
    kmeans_p = np.array([(kmeans == c).mean() for c in range(3)], dtype=np.float64)
    chance = float(np.dot(rule_p, kmeans_p))
    return {
        "rule_based_vs_kmeans": round(agreement, 4),
        "chance_baseline": round(chance, 4),
        "n": int(n),
        "rule_distribution": {CLASS_NAMES[i]: float(rule_p[i]) for i in range(3)},
        "kmeans_distribution": {CLASS_NAMES[i]: float(kmeans_p[i]) for i in range(3)},
    }


def ndwi_rule_labels_from_bands(green, nir) -> np.ndarray:
    return rule_based_labels(ndwi_index(green, nir))
