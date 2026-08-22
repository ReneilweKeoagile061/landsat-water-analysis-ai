"""Range and distribution checks for spectral indices and labels."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.indices import awei_nsh, clip_index, mndwi, ndvi, ndwi
from scripts.labeling import assign_kmeans_labels, holdout_mask, label_agreement, rule_based_labels
from scripts.subsurface_metrics import classify_dtwt, infiltration_class, phreatophyte_index
from scripts.validate_labels import run_agreement


def test_ndwi_mndwi_stay_in_unit_interval():
    rng = np.random.default_rng(42)
    green = rng.uniform(0.01, 0.4, 500)
    nir = rng.uniform(0.01, 0.5, 500)
    swir = rng.uniform(0.01, 0.5, 500)
    assert np.all((ndwi(green, nir) >= -1.0) & (ndwi(green, nir) <= 1.0))
    assert np.all((mndwi(green, swir) >= -1.0) & (mndwi(green, swir) <= 1.0))
    assert np.all((ndvi(nir, green) >= -1.0) & (ndvi(nir, green) <= 1.0))


def test_safe_div_does_not_nan_on_zero_denominator():
    values = ndwi(np.array([0.0, 0.2]), np.array([0.0, 0.2]))
    assert np.all(np.isfinite(values))


def test_clip_index():
    clipped = clip_index(np.array([-2.0, 0.0, 3.0]))
    assert clipped.tolist() == [-1.0, 0.0, 1.0]


def test_rule_based_thresholds():
    labels = rule_based_labels(np.array([-0.2, 0.15, 0.45]))
    assert labels.tolist() == [0, 1, 2]


def test_label_distributions_sum_to_one():
    rule = np.array([0, 0, 1, 2, 2, 2])
    kmeans = np.array([0, 1, 1, 2, 2, 0])
    report = label_agreement(rule, kmeans)
    assert pytest.approx(sum(report["rule_distribution"].values()), rel=1e-9) == 1.0
    assert pytest.approx(sum(report["kmeans_distribution"].values()), rel=1e-9) == 1.0
    assert 0.0 <= report["rule_based_vs_kmeans"] <= 1.0
    assert 0.0 <= report["chance_baseline"] <= 1.0


def test_kmeans_holdout_excludes_region_from_fit():
    rng = np.random.default_rng(0)
    n = 120
    lon = np.linspace(22.0, 26.0, n)
    df = pd.DataFrame(
        {
            "ndwi": rng.normal(0.0, 0.2, n),
            "mndwi": rng.normal(0.0, 0.2, n),
            "ndvi": rng.normal(0.2, 0.1, n),
            "awei_nsh": rng.normal(0.0, 0.1, n),
            "ndmi": rng.normal(0.0, 0.1, n),
            "lon_wgs84": lon,
            "lat_wgs84": np.full(n, -20.0),
        }
    )
    labeled = assign_kmeans_labels(df, holdout_region={"lon_min": 25.0, "lon_max": 27.0})
    excluded = holdout_mask(df, {"lon_min": 25.0, "lon_max": 27.0})
    assert excluded.sum() > 0
    assert labeled["held_out"].to_numpy().tolist() == excluded.tolist()
    assert set(labeled["water_potential_class"].unique()).issubset({0, 1, 2})


def test_fixture_agreement_is_in_ci_band():
    df = pd.read_csv(ROOT / "tests" / "fixtures" / "label_sample.csv")
    report = run_agreement(df, refit=False)
    assert report["ok"]


def test_awei_is_finite():
    values = awei_nsh(0.1, 0.08, 0.2, 0.09)
    assert np.isfinite(values)


def test_subsurface_thresholds_and_dry_season_index():
    assert classify_dtwt(24.9) == "Shallow (<25 m)"
    assert classify_dtwt(25.0) == "Moderate (25-75 m)"
    assert classify_dtwt(75.0) == "Moderate (25-75 m)"
    assert classify_dtwt(75.1) == "Deep (>75 m)"
    assert phreatophyte_index(0.5, 30.0, dry_season=True) > phreatophyte_index(0.5, 40.0, dry_season=True)
    assert infiltration_class(80.0).startswith("High infiltration")
