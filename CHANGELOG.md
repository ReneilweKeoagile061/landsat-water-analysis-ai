# Changelog

## v2.0.0 — Feature integrity & API security (2026-10)

### Breaking Changes
- `FEATURE_COLUMNS` updated: removed `dist_to_structure_m`, `structural_density`,
  `intersection_index` (were hardcoded constants, not real data). Model must be
  retrained with `scripts/agripulse_ml_pipeline.py` against the new 15-feature
  GEE export.
- API response no longer includes `depth_to_water_table_m`, `aquifer_productivity_ls`,
  `clay_fraction_pct`, `infiltration_score` — these were formulas of the probability
  score, not real measurements.
- CORS is now restricted to known origins. The wildcard `*` has been removed.

### New Features
- `grace_lwe_trend` and `ndvi_variance` are now active in `FEATURE_COLUMNS`
  (were computed but unused in v1).
- Added 250m neighbourhood statistics: `twi_mean_250m`, `s1_vv_mean_250m`.
- `/healthz` health endpoint added to backend.
- Async `.getInfo()` is now non-blocking (`run_in_executor`).
- Polygon size cap (50,000 km²) prevents runaway EE quota use.
- Structured logging replaces `print()` in backend.
- `data_quality` field on each API response feature flags structural data status.

### Bug Fixes
- Sampling scale fixed from 100 m → 30 m (matches training data scale).
- Error responses no longer leak stack traces to clients.
- `backend/requirements.txt` fully pinned.
- CI now tests backend import integrity and verifies demo data flag.

### Data / ML
- Bad-date boreholes (0000-00-00, 1929, 1900) flagged for exclusion before retraining.
- Model README section updated: "commercial-grade" removed, replaced with honest AUC/n metrics.
- Structural features roadmap documented: BWA_DGS_1M_MLF/MSF shapefiles needed from BGI.

### Repo Cleanup
- Removed: `fix_ui.py`, `refine_ui.py`, `check_boxes.py`, `fix_ternaries.py`,
  `_extract_nb.py`, `_patch_notebook.py`, `_nb_extract/`
- Removed: 5 overlapping SUMMARY/VERIFICATION docs → consolidated into CHANGELOG.md
- Removed: root-level duplicate `styles.css`
- Moved: test CSVs from `data/boreholes/` → `tests/fixtures/`
- Moved: `data/models_test/` → `tests/fixtures/models/`
