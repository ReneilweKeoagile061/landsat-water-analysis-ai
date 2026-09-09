# Milestone 1 reproducibility

This folder is the audit trail for AgriPulse Milestone 1. It is **not** a completed
acceptance pack until a clean re-run is executed after the three-state label fix.

## What is in the repo now

| Artifact | Present? | Meaning |
|----------|----------|---------|
| Training / prediction Python | Yes | `scripts/agripulse_ml_pipeline.py`, `scripts/agripulse_hydro_gate.py` |
| BGI client with three-state labels | Yes | missing yield → unknown, not dry |
| 10-row schema fixture | Yes | `data/boreholes/agripulse_gee_features_sample.csv` |
| Exact 84-row training CSV | **No** | Not committed |
| `agripulse_ml_metrics.json` (n=84, AUC≈0.706) | Yes | **Unverified** without the matching CSV |
| XGBoost JSON | Yes | Cannot be independently re-derived here |
| ERT ingestion | No | Phase 2 |
| Field validation | No | Phase 2 |

## Label contract (required for any re-run)

```
yield > 0          → is_productive = 1
verified zero      → is_productive = 0
missing / unknown  → is_productive blank; excluded from training
```

Do not coerce missing yield to 0.0. The committed `data/boreholes/bgi_verified_boreholes.csv`
was produced by the old client and may still contain missing-as-zero labels. Re-scrape
before treating it as ground truth.

## Clean re-run (acceptance evidence)

When GEE + BGI access is available:

```bash
python scripts/bgi_borehole_client.py --output data/boreholes/bgi_verified_boreholes.csv
# Upload coordinates to GEE, run gee/agripulse_gee_feature_stack.js, download features
python scripts/agripulse_gee_join.py --bgi data/boreholes/bgi_verified_boreholes.csv --gee data/boreholes/agripulse_bgi_ml_features.csv --output data/boreholes/agripulse_gee_features.csv
python scripts/agripulse_ml_pipeline.py --input data/boreholes/agripulse_gee_features.csv --outdir data/models
python scripts/write_milestone_manifest.py
python -m pytest
npm test
npm run build
```

Copy the resulting training CSV (if licensing allows), model, and metrics into this
folder. Then fill:

- `training_dataset.csv`
- `model.pkl` / `model.json`
- `metrics.json`
- `ranked_targets.json`
- `test_results.txt`

Until that re-run exists, do not present 0.706 AUC as independently reproducible.
