"""Patch notebook labeling / spatial-CV cells to use holdout-safe scripts."""

from __future__ import annotations

import json
from pathlib import Path

NB = Path(__file__).with_name("CET313_Artificial_Intelligence_Prototype (1).ipynb")

CELL_39 = r'''# CELL 1: Analyze Data Distribution & Create Better Labels
# K-Means is fitted in scripts/labeling.py so a spatial holdout can be excluded
# before .fit() -- the same helper is used by spatial CV and CI.
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path.cwd()
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
from labeling import assign_kmeans_labels

print("DATA-DRIVEN LABEL GENERATION")
print("=" * 60)

df = pd.read_parquet("data/features/landsat_features_wgs84.parquet")
print(f"Loaded: {len(df):,} samples\n")

print("Water Index Statistics:")
print(f"  NDWI:  {df['ndwi'].mean():.3f} +/- {df['ndwi'].std():.3f}")
print(f"  MNDWI: {df['mndwi'].mean():.3f} +/- {df['mndwi'].std():.3f}")
print(f"  NDVI:  {df['ndvi'].mean():.3f} +/- {df['ndvi'].std():.3f}")

# Global labels for the training export. Spatial CV (next cells) re-fits K-Means
# with holdout_region so the held-out longitude block never enters .fit().
df = assign_kmeans_labels(df, holdout_region=None)

print(f"\nWater Score Range: {df['water_score_norm'].min():.3f} to {df['water_score_norm'].max():.3f}")
print("\nClass Distribution (Data-Driven):")
for cls in [0, 1, 2]:
    count = (df['water_potential_class'] == cls).sum()
    pct = 100 * count / len(df)
    label = ['Low', 'Medium', 'High'][cls]
    mean_score = df[df['water_potential_class'] == cls]['water_score_norm'].mean()
    print(f"  {label:8s}: {count:5,} ({pct:5.1f}%) | Avg Score: {mean_score:.3f}")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
scatter = axes[0].scatter(df['lon_wgs84'], df['lat_wgs84'],
                         c=df['water_potential_class'],
                         cmap='RdYlGn', s=2, alpha=0.5)
axes[0].set_title('Data-Driven Water Potential Classes')
axes[0].set_xlabel('Longitude')
axes[0].set_ylabel('Latitude')
plt.colorbar(scatter, ax=axes[0], ticks=[0, 1, 2], label='Class')

for cls, color, label in [(0, 'red', 'Low'), (1, 'orange', 'Medium'), (2, 'green', 'High')]:
    mask = df['water_potential_class'] == cls
    axes[1].hist(df[mask]['water_score_norm'], bins=30, alpha=0.5,
                color=color, label=label, density=True)
axes[1].set_title('Water Score Distribution by Class')
axes[1].set_xlabel('Water Score')
axes[1].set_ylabel('Density')
axes[1].legend()

plt.tight_layout()
Path('data/ml_ready').mkdir(parents=True, exist_ok=True)
plt.savefig('data/ml_ready/label_analysis.png', dpi=300)
print("\nSaved: data/ml_ready/label_analysis.png")
plt.show()

df.to_parquet("data/ml_ready/training_dataset_improved.parquet", index=False)
print("Saved: data/ml_ready/training_dataset_improved.parquet")
'''

CELL_45 = r'''# SPATIAL CROSS-VALIDATION WITH LABEL HOLDOUT
# For each longitude block: fit K-Means on the other blocks, then train XGBoost
# on those labels. The holdout region is excluded from K-Means.fit().
from pathlib import Path
import sys
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from xgboost import XGBClassifier

ROOT = Path.cwd()
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
from labeling import assign_kmeans_labels
from train_water_potential import feature_columns, spatial_blocks

print("Performing SPATIAL cross-validation with label holdout...")

df = pd.read_parquet("data/ml_ready/training_dataset_improved.parquet")
df["spatial_block"] = spatial_blocks(df, n_blocks=5)
block_scores = []

for block in sorted(df["spatial_block"].unique()):
    labeled = assign_kmeans_labels(df, holdout_region={"block": int(block), "n_blocks": 5})
    cols = feature_columns(labeled)
    train = labeled[labeled["spatial_block"] != block]
    test = labeled[labeled["spatial_block"] == block]

    model = XGBClassifier(
        n_estimators=200, max_depth=7, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, eval_metric="mlogloss"
    )
    model.fit(train[cols], train["water_potential_class"])
    y_pred = model.predict(test[cols])
    acc = accuracy_score(test["water_potential_class"], y_pred)
    f1 = f1_score(test["water_potential_class"], y_pred, average="weighted")
    block_scores.append((acc, f1))
    print(f"Block {block}: ACC={acc:.4f}, F1={f1:.4f} | holdout rows excluded from K-Means.fit()")

print("\nSPATIAL CV RESULTS")
print(pd.DataFrame(block_scores, columns=["Accuracy", "F1"]))
'''

CELL_49 = r'''# LABEL AGREEMENT CHECK (also runnable as scripts/validate_labels.py)
from pathlib import Path
import sys
import pandas as pd

ROOT = Path.cwd()
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
from labeling import label_agreement, rule_based_labels
from validate_labels import run_agreement

df_new = pd.read_parquet("data/ml_ready/training_dataset_improved.parquet")

old_path = Path("data/ml_ready/training_dataset.parquet")
if old_path.exists():
    df_old = pd.read_parquet(old_path)
    merged = df_new.merge(
        df_old[["lon_wgs84", "lat_wgs84", "water_potential"]],
        on=["lon_wgs84", "lat_wgs84"],
        how="left",
    )
    merged["manual_class"] = merged["water_potential"].map({0: 0, 0.5: 1, 1: 2})
    valid = merged.dropna(subset=["manual_class"])
    print("Agreement between manual/AOI labels and K-Means labels:")
    print(label_agreement(valid["manual_class"], valid["water_potential_class"]))

print("\nAgreement vs independent NDWI rule labels:")
print(run_agreement(df_new, refit=False))
'''


def as_source(text: str) -> list[str]:
    lines = text.split("\n")
    return [line + "\n" for line in lines[:-1]] + ([lines[-1] + "\n"] if lines[-1] else [])


def main() -> None:
    nb = json.loads(NB.read_text(encoding="utf-8"))
    nb["cells"][39]["source"] = as_source(CELL_39)
    nb["cells"][45]["source"] = as_source(CELL_45)
    nb["cells"][49]["source"] = as_source(CELL_49)
    NB.write_text(json.dumps(nb, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Patched notebook cells 39, 45, 49")


if __name__ == "__main__":
    main()
