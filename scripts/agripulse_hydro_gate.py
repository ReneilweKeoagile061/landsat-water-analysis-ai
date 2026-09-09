import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Tuple

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
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Applies AgriPulse domain hard constraints and returns (accepted, rejected).

    Structural condition (OR is intentional): a candidate passes structure if it is
    close to a mapped structure OR has sufficient structural density.
    The overall hard gate is AND across structure, slope, and TWI.
    """
    df = df_farm_candidates.copy().reset_index(drop=True)

    struct_pass = (df["dist_to_structure_m"] <= max_dist_to_structure_m) | (
        df["structural_density"] >= min_structural_density
    )
    slope_pass = df["slope_deg"] <= max_slope_deg
    twi_pass = df["twi"] >= min_twi

    df["hydro_gate_passed"] = struct_pass & slope_pass & twi_pass
    df["gate_reasons"] = ""

    for idx in df.index:
        reasons = []
        if not bool(struct_pass.loc[idx]):
            reasons.append("No Fracture/Structure in Proximity (>1.2km)")
        if not bool(slope_pass.loc[idx]):
            reasons.append("High Slope (>8° Runoff Shedding)")
        if not bool(twi_pass.loc[idx]):
            reasons.append("Low Topographic Wetness (<5.0 TWI)")
        df.at[idx, "gate_reasons"] = (
            "; ".join(reasons) if reasons else "Approved by Hydrogeological Gate"
        )

    accepted_df = df[df["hydro_gate_passed"]].copy()
    rejected_df = df[~df["hydro_gate_passed"]].copy().reset_index(drop=True)

    if accepted_df.empty:
        logger.info("Hydro gate: 0 accepted, %s rejected", len(rejected_df))
        return accepted_df.reset_index(drop=True), rejected_df

    accepted_df["final_priority_score"] = (
        accepted_df["ml_prospectivity_score"] * 0.50
        + accepted_df["structural_density"] * 0.30
        + (1.0 / (1.0 + accepted_df["dist_to_structure_m"] / 500.0)) * 0.20
    )
    accepted_df = accepted_df.sort_values(
        by="final_priority_score", ascending=False
    ).reset_index(drop=True)
    accepted_df["target_rank"] = np.arange(1, len(accepted_df) + 1)

    logger.info(
        "Hydro gate: %s accepted, %s rejected", len(accepted_df), len(rejected_df)
    )
    return accepted_df, rejected_df


def rank_and_export_drill_targets(
    farm_csv: str, model_path: str, output_json: str, top_k: int = 3
) -> List[Dict]:
    """Scores candidate pixels with ML model, gates with domain rules, and outputs top drill sites."""
    import pickle
    from scripts.agripulse_ml_pipeline import FEATURE_COLUMNS, require_ml_features_present

    df = pd.read_csv(farm_csv)
    require_ml_features_present(df, FEATURE_COLUMNS, context="Prediction")

    if model_path.endswith(".pkl"):
        with open(model_path, "rb") as f:
            clf = pickle.load(f)
    else:
        import xgboost as xgb
        clf = xgb.XGBClassifier()
        clf.load_model(model_path)

    probs = clf.predict_proba(df[FEATURE_COLUMNS].values)[:, 1]
    df["ml_prospectivity_score"] = probs

    accepted_df, rejected_df = apply_hydrogeological_gate(df)
    logger.info(
        "Rejected %s candidates (see gate_reasons). Ranking %s accepted sites.",
        len(rejected_df),
        len(accepted_df),
    )
    top_targets = accepted_df.head(top_k)

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
