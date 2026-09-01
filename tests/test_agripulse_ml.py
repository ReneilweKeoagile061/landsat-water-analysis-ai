import pytest
import numpy as np
import pandas as pd
from scripts.bgi_borehole_client import extract_regex
from scripts.agripulse_ml_pipeline import generate_synthetic_features_if_missing
from scripts.agripulse_hydro_gate import apply_hydrogeological_gate

def test_extract_regex():
    html = "<goh>MTE3ODQ</goh> Coordinates: q=-23.90,24.95"
    bh_id = extract_regex(r"<goh>(.*?)</goh>", html)
    assert bh_id == "MTE3ODQ"
    
    coords = extract_regex(r"Coordinates:.*?q=([-\d\.\s,]+)", html)
    assert coords == "-23.90,24.95"


def test_generate_synthetic_features_if_missing():
    df = pd.DataFrame({
        "latitude": [-23.9], "longitude": [24.95],
        "dist_to_structure_m": [500], "structural_density": [1.5],
        "slope_deg": [3.0], "twi": [6.5]
    })
    df_filled = generate_synthetic_features_if_missing(df)
    
    expected_cols = [
        's1_vv', 's1_vh', 's1_vv_vh_ratio', 'radar_contrast',
        'ndvi', 'ndmi', 'ndwi', 'dem_elevation',
        'flow_accumulation', 'intersection_index'
    ]
    for col in expected_cols:
        assert col in df_filled.columns

    assert 0.0 <= df_filled["intersection_index"].iloc[0] <= 1.0

def test_hydro_gate():
    df = pd.DataFrame({
        "slope_deg": [3.0, 9.0, 3.0, 3.0],
        "twi": [6.5, 6.5, 4.0, 6.5],
        "dist_to_structure_m": [500, 500, 500, 1500],
        "structural_density": [0.5, 0.5, 0.5, 0.5],
        "ml_prospectivity_score": [0.8, 0.8, 0.8, 0.8]
    })
    
    accepted, rejected = apply_hydrogeological_gate(df)
    
    assert len(accepted) == 1
    assert len(rejected) == 3
    
    assert accepted["slope_deg"].iloc[0] == 3.0
    assert accepted["twi"].iloc[0] == 6.5
    assert accepted["dist_to_structure_m"].iloc[0] == 500
