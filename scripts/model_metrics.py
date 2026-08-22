"""Published validation block for the dashboard (notebook findings)."""

MODEL_VALIDATION = {
    "accuracy": 0.996,
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
}
