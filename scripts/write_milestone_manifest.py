#!/usr/bin/env python3
"""Record hashes of committed AgriPulse artifacts. Does not invent a training CSV."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "MILESTONE_1_VERIFICATION"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe(relpath: str) -> dict:
    path = ROOT / relpath
    if not path.exists():
        return {"path": relpath, "present": False}
    return {
        "path": relpath.replace("\\", "/"),
        "present": True,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> None:
    training_candidates = [
        "data/boreholes/agripulse_gee_features.csv",
        "data/boreholes/agripulse_training_84.csv",
    ]
    training = None
    for candidate in training_candidates:
        info = describe(candidate)
        if info["present"]:
            training = info
            break

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "milestone": "1",
        "training_dataset": training
        or {
            "present": False,
            "expected_paths": training_candidates,
            "row_count_claimed_in_metrics": 84,
            "note": "Exact 84-row feature CSV is not in this repository; AUC 0.706 is unverified here.",
        },
        "schema": describe("MILESTONE_1_VERIFICATION/dataset_schema.json"),
        "sample_schema_fixture": describe("data/boreholes/agripulse_gee_features_sample.csv"),
        "legacy_bgi_csv_warning": describe("data/boreholes/bgi_verified_boreholes.csv"),
        "metrics_artifact": describe("data/models/agripulse_ml_metrics.json"),
        "model_json": describe("data/models/agripulse_xgb_classifier.json"),
        "generation_scripts": [
            "scripts/bgi_borehole_client.py",
            "scripts/agripulse_gee_join.py",
            "gee/agripulse_gee_feature_stack.js",
            "scripts/agripulse_ml_pipeline.py",
            "scripts/agripulse_hydro_gate.py",
        ],
        "claimed_metrics_unverified": json.loads(
            (ROOT / "data/models/agripulse_ml_metrics.json").read_text(encoding="utf-8")
        )
        if (ROOT / "data/models/agripulse_ml_metrics.json").exists()
        else None,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "dataset_manifest.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
