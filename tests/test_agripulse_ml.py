import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.bgi_borehole_client import classify_productivity, extract_regex, parse_optional_yield
from scripts.agripulse_hydro_gate import apply_hydrogeological_gate
from scripts.agripulse_ml_pipeline import FEATURE_COLUMNS, require_ml_features_present


def test_extract_regex():
    html = "<goh>MTE3ODQ</goh> Coordinates: q=-23.90,24.95"
    bh_id = extract_regex(r"<goh>(.*?)</goh>", html)
    assert bh_id == "MTE3ODQ"

    coords = extract_regex(r"Coordinates:.*?q=([-\d\.\s,]+)", html)
    assert coords == "-23.90,24.95"


def test_missing_yield_is_unknown_not_dry():
    parsed, label, status = classify_productivity(None)
    assert parsed is None
    assert label is None
    assert status == "unknown"

    parsed, label, status = classify_productivity("")
    assert parsed is None
    assert label is None
    assert status == "unknown"

    assert parse_optional_yield(None) is None
    assert parse_optional_yield("N/A") is None


def test_verified_zero_yield_is_dry():
    parsed, label, status = classify_productivity("0")
    assert parsed == 0.0
    assert label == 0
    assert status == "verified_zero"

    parsed, label, status = classify_productivity(0.0)
    assert label == 0
    assert status == "verified_zero"


def test_positive_yield_is_productive():
    parsed, label, status = classify_productivity("4.54")
    assert parsed == pytest.approx(4.54)
    assert label == 1
    assert status == "measured"


def test_missing_ml_features_fail_loudly():
    df = pd.DataFrame({
        "latitude": [-23.9],
        "longitude": [24.95],
        "dist_to_structure_m": [500],
        "structural_density": [1.5],
        "slope_deg": [3.0],
        "twi": [6.5],
    })
    with pytest.raises(ValueError, match="Missing required ML features") as exc:
        require_ml_features_present(df, FEATURE_COLUMNS, context="Prediction")
    message = str(exc.value)
    assert "s1_vv" in message
    assert "ndvi" in message
    assert "Prediction aborted." in message
    import scripts.agripulse_ml_pipeline as mlp
    assert not hasattr(mlp, "generate_synthetic_features_if_missing")


def test_nan_feature_values_fail_loudly():
    row = {col: 0.1 for col in FEATURE_COLUMNS}
    row["ndvi"] = np.nan
    df = pd.DataFrame([row])
    with pytest.raises(ValueError, match="ndvi"):
        require_ml_features_present(df, FEATURE_COLUMNS, context="Prediction")


def test_unknown_productivity_excluded_from_training_frame():
    df = pd.DataFrame({
        "is_productive": [1, 0, np.nan, None, ""],
    })
    labels = pd.to_numeric(df["is_productive"], errors="coerce")
    trainable = df.loc[labels.notna()].copy()
    trainable["is_productive"] = labels.loc[labels.notna()].astype(int)
    assert list(trainable["is_productive"]) == [1, 0]


def test_hydro_gate_returns_accepted_and_rejected():
    df = pd.DataFrame({
        "slope_deg": [3.0, 9.0, 3.0, 3.0],
        "twi": [6.5, 6.5, 4.0, 6.5],
        "dist_to_structure_m": [500, 500, 500, 1500],
        "structural_density": [0.5, 0.5, 0.5, 0.10],
        "ml_prospectivity_score": [0.8, 0.8, 0.8, 0.8],
    })

    accepted, rejected = apply_hydrogeological_gate(df)

    assert len(accepted) == 1
    assert len(rejected) == 3
    assert accepted["slope_deg"].iloc[0] == 3.0
    assert accepted["twi"].iloc[0] == 6.5
    assert accepted["dist_to_structure_m"].iloc[0] == 500
    assert "gate_reasons" in rejected.columns


def test_hydro_gate_structure_or_density():
    """Far from structure still passes if structural density is high (intentional OR)."""
    df = pd.DataFrame({
        "slope_deg": [3.0],
        "twi": [6.5],
        "dist_to_structure_m": [1500],
        "structural_density": [0.5],
        "ml_prospectivity_score": [0.8],
    })
    accepted, rejected = apply_hydrogeological_gate(df)
    assert len(accepted) == 1
    assert len(rejected) == 0
