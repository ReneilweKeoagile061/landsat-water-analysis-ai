import argparse
import json
import logging
import os
import sys
from typing import Dict, List

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agripulse_gate")


def apply_hydrogeological_gate(
    df_farm_candidates: pd.DataFrame,
    min_prospectivity: float = 0.65,
    max_dist_to_structure_m: float = 1200.0,
    min_structural_density: float = 0.25,
    max_slope_deg: float = 8.0,
    min_twi: float = 5.0,
) -> pd.DataFrame:
    """
    Applies AgriPulse domain hard constraints:
    1. Structural Proximity Gate: Must be within fracture influence zone.
    2. Structural Density Gate: Must exhibit persistent lineament/fracture networks.
    3. Runoff/Slope Gate: Exclude excessive shedding slopes.
    4. Topographic Wetness Index Gate: Exclude hyper-arid uncollecting ridges.
    """
    df = df_farm_candidates.copy()

    # Rule 1: Structural Proximity Gate
    struct_pass = (df["dist_to_structure_m"] <= max_dist_to_structure_m) | (
        df["structural_density"] >= min_structural_density
    )

    # Rule 2: Slope / Drainage Gate
    slope_pass = df["slope_deg"] <= max_slope_deg

    # Rule 3: Topographic Wetness Gate
    twi_pass = df["twi"] >= min_twi

    # Hard gate decision
    df["hydro_gate_passed"] = struct_pass & slope_pass & twi_pass
    df["gate_reasons"] = ""

    # Record rejection flags
    rejections = []
    for idx, row in df.iterrows():
        reasons = []
        if not struct_pass.iloc[idx]:
            reasons.append("No Fracture/Structure in Proximity (>1.2km)")
        if not slope_pass.iloc[idx]:
            reasons.append("High Slope (>8° Runoff Shedding)")
        if not twi_pass.iloc[idx]:
            reasons.append("Low Topographic Wetness (<5.0 TWI)")
        df.at[idx, "gate_reasons"] = "; ".join(reasons) if reasons else "Approved by Hydrogeological Gate"

    # Filter & rank passed candidates
    passed_df = df[df["hydro_gate_passed"]].copy()
    passed_df["final_priority_score"] = (
        passed_df["ml_prospectivity_score"] * 0.50
        + passed_df["structural_density"] * 0.30
        + (1.0 / (1.0 + passed_df["dist_to_structure_m"] / 500.0)) * 0.20
    )
    passed_df = passed_df.sort_values(by="final_priority_score", ascending=False).reset_index(drop=True)
    passed_df["target_rank"] = np.arange(1, len(passed_df) + 1)

    return passed_df


def rank_and_export_drill_targets(
    farm_csv: str, model_path: str, output_json: str, top_k: int = 3
) -> List[Dict]:
    """Scores candidate pixels with ML model, gates with domain rules, and outputs top drill sites."""
    import pickle
    from scripts.agripulse_ml_pipeline import FEATURE_COLUMNS, generate_synthetic_features_if_missing

    df = pd.read_csv(farm_csv)
    
    # Load model
    if model_path.endswith(".pkl"):
        with open(model_path, "rb") as f:
            clf = pickle.load(f)
    else:
        import xgboost as xgb
        clf = xgb.XGBClassifier()
        clf.load_model(model_path)

    df = generate_synthetic_features_if_missing(df)
    probs = clf.predict_proba(df[FEATURE_COLUMNS].values)[:, 1]
    df["ml_prospectivity_score"] = probs

    ranked_df = apply_hydrogeological_gate(df)
    top_targets = ranked_df.head(top_k)

    results = []
    for _, row in top_targets.iterrows():
        results.append(
            {
                "target_rank": int(row["target_rank"]),
                "longitude": float(row["longitude"]),
                "latitude": float(row["latitude"]),
                "ml_prospectivity_score": float(row["ml_prospectivity_score"]),
                "final_priority_score": float(row["final_priority_score"]),
                "structural_density": float(row["structural_density"]),
                "dist_to_structure_m": float(row["dist_to_structure_m"]),
                "slope_deg": float(row["slope_deg"]),
                "twi": float(row["twi"]),
                "recommended_action": f"ERT Geophysics Line 100m centered on ({row['latitude']:.5f}, {row['longitude']:.5f})",
            }
        )

    os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)
    with open(output_json, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Generated top {len(results)} drill targets saved to {output_json}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hydrogeological Hard Gate Ranker")
    parser.add_argument("--farm-csv", required=True, help="Farm grid features CSV")
    parser.add_argument("--model", default="data/models/agripulse_xgb_classifier.json", help="Trained XGBoost model")
    parser.add_argument("--output", default="data/exports/ranked_drill_targets.json", help="Output JSON path")
    args = parser.parse_args()
    rank_and_export_drill_targets(args.farm_csv, args.model, args.output)
