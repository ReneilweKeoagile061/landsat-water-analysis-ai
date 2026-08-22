"""Standalone label-agreement check for CI.

Compares K-Means water-potential labels with independent NDWI rule labels.
A collapse toward 0% or a jump toward 100% is treated as a regression.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from labeling import assign_kmeans_labels, label_agreement, rule_based_labels

MIN_AGREEMENT = 0.20
MAX_AGREEMENT = 0.90


def load_frame(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def resolve_kmeans_labels(df: pd.DataFrame, refit: bool) -> np.ndarray:
    if not refit and "water_potential_class" in df.columns:
        return df["water_potential_class"].to_numpy()
    labeled = assign_kmeans_labels(df, holdout_region=None)
    return labeled["water_potential_class"].to_numpy()


def run_agreement(df: pd.DataFrame, refit: bool = False) -> dict:
    kmeans_labels = resolve_kmeans_labels(df, refit=refit)
    rule_labels = rule_based_labels(df["ndwi"].to_numpy())
    result = label_agreement(rule_labels, kmeans_labels)
    result["ok"] = MIN_AGREEMENT <= result["rule_based_vs_kmeans"] <= MAX_AGREEMENT
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate K-Means vs rule-based water labels.")
    parser.add_argument(
        "--input",
        help="CSV or parquet with ndwi and either water_potential_class or clustering features.",
    )
    parser.add_argument("--refit", action="store_true", help="Refit K-Means even if labels exist.")
    parser.add_argument("--json-out", help="Optional path to write the agreement report.")
    args = parser.parse_args()

    if args.input:
        df = load_frame(Path(args.input))
    else:
        fixture = ROOT.parent / "tests" / "fixtures" / "label_sample.csv"
        df = load_frame(fixture)

    report = run_agreement(df, refit=args.refit)
    print(json.dumps(report, indent=2))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")

    if not report["ok"]:
        print(
            "FAIL: agreement "
            f"{report['rule_based_vs_kmeans']} outside [{MIN_AGREEMENT}, {MAX_AGREEMENT}]",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
