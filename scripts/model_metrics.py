"""Published validation block for the dashboard.

The 0.996 figure is XGBoost reproducing K-Means labels (self-consistency),
not borehole-calibrated drilling skill. Borehole metrics belong on the AgriPulse path.
"""

MODEL_VALIDATION = {
    "accuracy": 0.996,
    "accuracy_name": "Model Self-Consistency Score",
    "metric_interpretation": "xgboost_vs_kmeans_not_borehole_skill",
    "weighted_f1": 0.996,
    "macro_f1": 0.9737,
    "test_samples": 2500,
    "spatial_cv": {
        "blocks": [0.996, 0.9925, 0.9955, 0.997, 0.9975],
        "mean": 0.9957,
    },
    "label_agreement": {
        "rule_based_vs_kmeans": 0.267,
        "chance_baseline": 0.333,
    },
    "per_class": {
        "low": {"f1": 0.9957},
        "medium": {"f1": 0.9968},
        "high": {"f1": 0.9286},
    },
    "nasa_arset": {
        "citation": "Lee et al.; NASA ARSET groundwater / data assimilation",
        "basin_scale_improvement": 0.36,
        "well_scale_improvement": 0.10,
        "satellite_screening_confidence": 0.45,
    },
}
