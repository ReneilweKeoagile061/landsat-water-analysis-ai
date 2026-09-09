# AgriPulse Groundwater Prospectivity + Landsat Dashboard

This repository currently contains **two related systems**. They must not be evaluated as one.

| System | What it is | Status |
|--------|------------|--------|
| **AgriPulse Milestone 1** | Supervised groundwater prospectivity: BGI borehole labels → GEE features → spatial-CV XGBoost → hydrogeological gate → ranked drill targets | **Active commercial path.** Code is in `scripts/agripulse_*.py` and `scripts/bgi_borehole_client.py`. |
| **Landsat water-potential dashboard** | Coursework / demo UI trained against **K-Means-generated** labels (the 99.6% accuracy figure) | **Legacy frontend.** Still the Vite dashboard. Those scores are not borehole-calibrated groundwater skill. |

`run_84_borehole_pipeline.py` is **not** part of this branch. Do not treat it as delivered.

The 84-sample / 0.706 AUC figures in `data/models/agripulse_ml_metrics.json` are **not independently reproducible from this repository** until the exact training CSV (or a signed dataset manifest) is committed. See `MILESTONE_1_VERIFICATION/reproducibility.md`.

**Milestone 1 acceptance pipeline (intended, not yet fully re-run after label fixes):**

```
BGI (three-state labels) → GEE feature export → spatial join → training CSV
  → quality checks → spatial CV → XGBoost → metrics → model reload
  → new-farm pixel scores → hydro gate → ranked targets
```

ERT / resistivity / drilling feedback is **Phase 2**. It is not claimed here.

---

# Landsat Water Analysis AI (legacy dashboard)

**AI-driven satellite imagery analysis for discovering, filtering, and visualizing high-quality Landsat scenes and surface water potential across Botswana.**

Developed for **CET313 – Artificial Intelligence** · Botswana Accountancy College

---

## Overview

This repository combines a Jupyter-based geospatial machine learning pipeline with an interactive web dashboard. The notebook workflow queries Microsoft Planetary Computer for Landsat 8/9 imagery, filters scenes by cloud cover and Tier-1 quality, engineers spectral water indices (NDWI, MNDWI), and trains an XGBoost classifier to map low, medium, and high water-potential zones.

The frontend presents those results on a map-first dashboard with heatmaps, AOI overlays, model metrics, and scene filtering — designed to showcase the project clearly for portfolios, demos, and coursework submission.

## Current Project Status

This repository is a working static web application plus a Python geospatial data pipeline. The
dashboard runs from checked-in GeoJSON/JSON exports, while the pipeline consumes notebook prediction
CSVs and produces validated frontend data.

The checked-in catalog is a deterministic demonstration catalog. Its hydrogeology values are marked
`synthetic demonstration` and must not be interpreted as field measurements. Real public connectors
are available for Microsoft Planetary Computer STAC metadata and ISRIC SoilGrids v2.0 point queries.
The project does not currently claim live BGS Africa, Fan DTWT, GLHYMPS, GRACE-FO, or Botswana AEM
coverage; those sources require separate downloads, credentials, service agreements, or local survey
files.

---

## Problem Statement

Satellite imagery for environmental monitoring is often compromised by:

- High cloud cover
- Inconsistent processing quality
- Large volumes of unusable scenes
- Manual, time-consuming scene selection

This project automates scene discovery and quality filtering, then applies machine learning to identify hydrologically meaningful water-potential areas across multiple AOIs in Botswana.

---

## Key Features

### Notebook pipeline

- Automated Landsat 8 & 9 scene discovery via STAC API
- Cloud cover filtering (< 20%) and Tier-1 quality enforcement
- Wet-season focused acquisition (Jan–Apr)
- AOI-driven search across three ecological zones
- Spectral feature engineering (NDWI, MNDWI, AWEI, NDVI, and more)
- XGBoost classification of water potential (Low / Medium / High)
- Model evaluation with accuracy, F1-score, and confusion matrix

### Web dashboard

- **Map-first layout** — map occupies most of the screen
- **Interactive heatmaps** — NDWI and MNDWI layers with gradient styling
- **Soft AOI region overlays** — elliptical gradient polygons (not rigid boxes)
- **Hover tooltips** — rich detail on regions and sample points
- **Right-side tabbed panel** — Overview, Filters, Scenes, Model
- **Live filtering** — AOI, cloud threshold, season, and data tier
- **Data-driven** — loads exported GeoJSON and JSON from `data/exports/`

### Subsurface screening

- DTWT categories: shallow (`<25 m`), moderate (`25-75 m`), and deep (`>75 m`)
- Dry-season phreatophyte screening from NDVI, optionally weighted by land-surface temperature
- Shallow-soil infiltration proxy from clay fraction, with an explicit infiltration/seal class
- Provenance and data-quality fields on every subsurface point
- Export support for measured hydrogeology columns when supplied by an enrichment dataset

The checked-in catalog is a deterministic demonstration dataset and marks its subsurface values as
`synthetic demonstration`. It is not a substitute for BGS, Fan DTWT, GLHYMPS, SoilGrids, GRACE,
SAR, or AEM observations. Those sources must be joined into the notebook export before their values
can be treated as measured.

---

## Areas of Interest (AOIs)

| AOI | Description |
|-----|-------------|
| **Okavango Delta** | Water-dominant ecosystem; seasonal flooding dynamics |
| **Kalahari Fringe** | Dry/desert terrain; reduces false-positive water detections |
| **Transitional Zone** | Mixed hydrological conditions between wet and dry regions |

---

## Model Performance

Headline XGBoost scores (against **K-Means labels**, 2,500 test samples):

| Metric | Value |
|--------|-------|
| Accuracy | 99.60% |
| Weighted F1 | 0.9960 |
| Macro F1 | 0.9737 |
| Spatial-block CV mean | 99.57% |

Per-class F1: Low 0.9957 · Medium 0.9968 · High 0.9286.

Those figures measure how faithfully the classifier copies internally generated K-Means labels. They are **not** AgriPulse borehole-calibrated results. Independent NDWI/AOI rules agree with K-Means only **26.7%** of the time (chance baseline **33.3%**). The Model tab on the dashboard surfaces this directly.

K-Means is fitted with an optional `holdout_region` so spatial CV no longer labels the held-out longitude block during `.fit()`.

---

## Architecture

```
┌─────────────────────────────┐     STAC API      ┌──────────────────────────┐
│  Jupyter Notebook Pipeline  │ ◄───────────────► │  Microsoft Planetary     │
│  (scene discovery + ML)   │                   │  Computer (Landsat C2)   │
└──────────────┬──────────────┘                   └──────────────────────────┘
               │
               │  export CSV → scripts/export_frontend_data.py
               ▼
┌─────────────────────────────┐     fetch()       ┌──────────────────────────┐
│  data/exports/              │ ◄───────────────► │  Web Dashboard           │
│  GeoJSON + JSON             │                   │  (Leaflet + vanilla JS)  │
└─────────────────────────────┘                   └──────────────────────────┘
```

### System design

The system separates offline data preparation from a lightweight browser client:

1. **Acquisition:** the notebook and `fetch_stac_catalog.py` query Planetary Computer. The STAC
    command records scene IDs, dates, cloud cover, bounds, and available assets for Landsat Collection
    2 or Sentinel-1 RTC.
2. **Feature engineering:** notebook code computes NDWI, MNDWI, NDVI, AWEI, NDMI, LSWI, WRI, moisture
    ratio, elevation, and slope features.
3. **Labeling and modeling:** `labeling.py` creates composite-score/K-Means labels. XGBoost and the
    other models are trained by `train_water_potential.py`, with spatial holdout support.
4. **Subsurface enrichment:** `fetch_soilgrids.py` adds real modeled clay observations at four depths.
    `subsurface_metrics.py` derives DTWT classes, phreatophyte screening, infiltration interpretation,
    evidence confidence, drill-depth ranges, and validation steps.
5. **Export contract:** `export_frontend_data.py` converts prediction rows into GeoJSON/JSON and
    preserves optional hydrogeology, provenance, quality, and query timestamp fields.
6. **Browser state:** `loadData.js` fetches four static resources and validates them with Zod.
    `filters.js` applies AOI, season, tier, cloud, and water-confidence filters.
7. **Map and interaction:** `mapController.js` renders Leaflet base maps, heatmaps, DTWT/borehole
    layers, clustered points, popups, property drawing, and site reports.
8. **Decision support:** polygon analysis aggregates point classes and subsurface averages, then
    synchronizes with the water-capture calculator.

### Data trust model

| Evidence level | Meaning | Appropriate use |
|---|---|---|
| `measured` | Field or survey observation | Engineering review and calibration |
| `modeled` | External model such as SoilGrids | Regional screening with uncertainty |
| `screening` | Derived satellite or proxy feature | Prioritizing investigation areas |
| `synthetic demonstration` | Generated catalog value | UI and demo testing only |

Every subsurface point can carry `subsurface_data_source`, `subsurface_data_quality`,
`evidence_confidence`, and `validation_next_step`. A recommendation means “investigate here next,”
not “drill here with guaranteed success.”

### Main logic

- Surface water potential uses normalized spectral indices and produces Low, Medium, or High classes.
- DTWT is categorized as Shallow (`<25 m`), Moderate (`25-75 m`), or Deep (`>75 m`).
- The phreatophyte index scores NDVI persistence and optionally weights cooler dry-season LST.
- The infiltration score is a shallow-clay proxy: `100 - clay percentage`; it is not a hydraulic model.
- Property analysis counts points inside a polygon and averages available subsurface fields.
- Water capture is a planning estimate based on area, rainfall, and class shares, not calibrated recharge.

---

## Project Structure

```
landsat-water-analysis-ai/
├── CET313_Artificial_Intelligence_Prototype (1).ipynb   # Main ML pipeline
├── index.html                                            # Dashboard entry point
├── styles.css                                            # Shared design tokens (colors, layout)
├── src/
│   ├── main.js                                           # App bootstrap and event wiring
│   ├── config.js                                         # AOI labels, filter defaults, constants
│   ├── styles.css                                        # Component styles (imports root styles.css)
│   ├── api/
│   │   ├── loadData.js                                   # Fetch + retry logic for all data sources
│   │   └── schema.js                                     # Zod schemas validating every loaded file
│   ├── state/
│   │   └── filters.js                                    # Pure filtering logic + DOM filter reader
│   ├── map/
│   │   └── mapController.js                              # Leaflet layers, heatmaps, clustering, tooltips
│   ├── ui/
│   │   ├── dashboard.js                                  # Safe (non-innerHTML) DOM rendering
│   │   └── tabs.js                                       # Tab/panel toggle behavior
│   └── utils/
│       ├── dom.js                                        # DOM helpers, loading/error UI
│       └── geo.js                                        # Normalization, sampling, debounce
├── data/
│   └── exports/
│       ├── aois.geojson                                  # AOI polygon boundaries
│       ├── water_points.geojson                          # Prediction points + indices
│       ├── scenes.json                                   # Filtered Landsat scenes
│       └── metrics.json                                  # Model KPIs
├── scripts/
│   ├── agripulse_ml_pipeline.py                         # Supervised XGBoost + spatial CV
│   ├── agripulse_hydro_gate.py                          # Hard hydro gate → accepted/rejected
│   ├── agripulse_gee_join.py                            # BGI ↔ GEE spatial join
│   ├── agripulse_gee_feature_stack.js                   # GEE feature export
│   ├── bgi_borehole_client.py                           # BGI scrape + three-state labels
│   ├── export_frontend_data.py                          # Notebook CSV → frontend exports
│   ├── fetch_soilgrids.py                                # Real ISRIC clay enrichment
│   ├── fetch_stac_catalog.py                             # Planetary Computer STAC query
│   ├── generate_catalog_data.py                          # Deterministic demo catalog
│   ├── subsurface_metrics.py                             # DTWT and proxy logic
│   ├── indices.py                                        # Spectral index functions
│   ├── dem_features.py                                   # Elevation and slope features
│   ├── labeling.py                                       # K-Means and rule labels
│   ├── train_water_potential.py                          # Training and spatial validation
│   └── validate_labels.py                                # Independent agreement checks
├── tests/
│   ├── filters.test.js                                   # Frontend filter and geometry tests
│   ├── test_indices.py                                  # Python feature/label tests
│   ├── test_dem_features.py                             # DEM feature tests
│   └── fixtures/label_sample.csv                        # Validation fixture
├── public/data/exports/                                  # Files served by Vite
├── data/landsat_stac.json                               # Example live STAC response
├── data/sentinel1_stac.json                             # Example radar STAC response
├── .github/workflows/ci.yml                             # Automated CI
└── README.md
```

---

## Technologies

| Layer | Stack |
|-------|-------|
| Notebook | Python, Jupyter, PySTAC, Planetary Computer, Rasterio, Shapely, XGBoost, scikit-learn |
| Frontend | HTML, CSS, JavaScript, Vite, Leaflet, Leaflet.heat, Zod |
| Data clients | Requests, Planetary Computer STAC, ISRIC SoilGrids v2.0 |
| Data | GeoJSON, JSON, Landsat 8/9 L2SP, optional Sentinel-1 RTC |

---

## Getting Started

### Prerequisites

- **Python 3.10+** (for notebook and export scripts)
- **Modern web browser** (for dashboard)
- **Node.js 18+ and npm** (for Vite, lint, build, and tests)

### 1. Run the notebook

**Google Colab**

1. Upload `CET313_Artificial_Intelligence_Prototype (1).ipynb` to Colab
2. Run all cells sequentially

**Local machine**

```bash
pip install -r requirements.txt
jupyter notebook
```

### 2. Export data for the dashboard

After the notebook produces a predictions CSV, generate frontend-ready files:

```bash
pip install pandas
python scripts/export_frontend_data.py --input-csv path/to/predictions.csv --output-dir data/exports
```

**Required CSV columns:** `lat_wgs84`, `lon_wgs84`, `ndwi`, `mndwi`, `aoi`

**Optional columns:** `predicted_class`, `prob_high`, `scene_id`, `date`, `cloud`, `tier`, `aoi_label`, `overlap_pct`

Optional enrichment columns include `depth_to_water_table_m`, `aquifer_type`,
`aquifer_productivity_ls`, `borehole_feasibility_score`, `clay_fraction_pct`, `ndvi`, and
`land_surface_temperature_c`.

### Real SoilGrids enrichment

ISRIC SoilGrids v2.0 provides modeled clay percentages at four depth horizons through a public point
API. Enrich a notebook prediction CSV before exporting it to the dashboard:

```bash
pip install -r requirements.txt
python scripts/fetch_soilgrids.py --input-csv path/to/predictions.csv --output-csv data/enriched_predictions.csv
python scripts/export_frontend_data.py --input-csv data/enriched_predictions.csv --output-dir public/data/exports
```

Use `--limit 5` for a trial run. The exporter preserves the SoilGrids source, query timestamp, depth
horizons, and modeled quality label. Planetary Computer remains the real Landsat/STAC source. GRACE,
BGS, Fan DTWT, GLHYMPS, and Botswana AEM require separate downloaded products or authenticated services;
they are not guessed or represented as live data by this static dashboard.

Query live optical Landsat or Sentinel-1 radar metadata from Planetary Computer:

```bash
python scripts/fetch_stac_catalog.py --collection landsat --limit 20 --output data/landsat_stac.json
python scripts/fetch_stac_catalog.py --collection sentinel1 --limit 20 --output data/sentinel1_stac.json
```

The STAC command records scene IDs, dates, cloud cover, bounding boxes, and available assets. It does
not claim that radar penetration equals a fixed depth; penetration depends on soil moisture, roughness,
vegetation, wavelength, and processing conditions.

### 3. Run the web dashboard

The dashboard loads data via `fetch()`, so it must be served over HTTP (not opened as a `file://` URL).

```bash
npm install
npm run dev
```

Open the Vite URL shown in the terminal, normally [http://localhost:5173](http://localhost:5173).

For a production-like check:

```bash
npm run build
npm run preview
```

### Dashboard usage

1. Use the **Filters** tab to select AOI, cloud threshold, season, and tier
2. Click **Apply filters** to refresh the map and scene table
3. Toggle map layers: **NDWI**, **MNDWI**, **slope**, **groundwater depth**, **borehole feasibility**,
   AOI gradients, and class points
4. Hover over regions and points for detailed spectral and classification info
5. Open a point popup to review evidence quality, DTWT class, infiltration, and the next validation step
6. Download a site-investigation report from a point popup
7. Draw a property boundary to aggregate points and synchronize the water-capture calculator

### Developer commands

```bash
npm run lint
npm test
python -m pytest
npm run generate-data
npm run fetch-stac -- --collection landsat --limit 20 --output data/landsat_stac.json
npm run fetch-soilgrids -- --input-csv predictions.csv --output-csv data/enriched_predictions.csv --limit 5
```

---

## Data Source

- [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/)
- Landsat Collection 2 Level-2 Surface Reflectance (L2SP)
- Landsat 8 and Landsat 9 sensors
- [ISRIC SoilGrids v2.0](https://rest.isric.org/soilgrids/v2.0/properties/query) for modeled soil clay horizons
- Optional Planetary Computer `sentinel-1-rtc` collection for radar scene metadata

Source data should be cached with acquisition/query dates and version information. Do not put API
secrets in the browser or commit private survey data to this repository.

---

## Improvement Roadmap

### Phase 1: Data credibility and reproducibility

- Replace generated DTWT, productivity, aquifer type, and borehole scores with sourced BGS/Fan/GLHYMPS
    layers where licensing and download terms permit.
- Add robust spatial joins with CRS checks, nearest-cell distance, source resolution, and no-data handling.
- Store dataset version, acquisition date, processing commit, and uncertainty for every metric.
- Add retry, caching, rate-limit handling, and partial-failure reporting to enrichment jobs.
- Add fixtures for real API responses so tests do not depend on live network availability.

### Phase 2: Scientific quality

- Add Landsat LST/TIRS processing for dry-season September-October phreatophyte screening.
- Process Sentinel-1 backscatter/coherence and document radar as a surface/structure proxy where appropriate.
- Add GRACE-FO as a regional groundwater anomaly layer, clearly showing its coarse resolution.
- Add AEM/resistivity imports for high-confidence investigation zones and saline-water risk.
- Calibrate prospectivity against verified boreholes, static water levels, pump-test yields, and seasonal records.
- Replace K-Means-only labels with independently validated targets and report calibration, precision/recall,
    spatial transfer performance, and confidence intervals.

### Phase 3: Commercial product

- Add accounts, projects, saved AOIs, role-based sharing, and an auditable report history.
- Provide PDF/CSV/GeoJSON reports with maps, source citations, uncertainty, and professional disclaimers.
- Provide an API and batch processing for consultants, government teams, and drilling partners.
- Add time-series charts, drought monitoring, groundwater trend alerts, and wetland-change alerts.
- Add field feedback so surveyors can upload borehole outcomes as training and validation data.
- Add billing, usage quotas, observability, job queues, and notifications.

### Phase 4: Production architecture

- Move long-running enrichment and model jobs from the static browser build to a versioned backend worker.
- Use object storage for immutable datasets and a spatial database for AOIs, observations, and reports.
- Add API authentication, input validation, audit logs, secret management, and rate limits.
- Add CI checks for schema compatibility, dependency security, data freshness, and reproducible exports.
- Publish a model card and data card covering intended use, limitations, bias, resolution, and failure modes.

## Product Positioning

The commercially defensible product is a **groundwater prospectivity and land-water planning platform**.
It should prioritize and explain investigation areas, help plan field surveys, and combine satellite,
soil, geological, geophysical, and field evidence. A map score should not be marketed as a guaranteed
borehole success probability until it has been calibrated against an independent borehole dataset.

---

## Deployment

The frontend is static (HTML/CSS/JS). Deploy to any static host:

- **GitHub Pages** — enable Pages on the `main` branch
- **Netlify / Vercel** — point to the repo root

Ensure `data/exports/` is included in the deployment so the map can load its data files.

---

## Academic Context

This project was developed as an Artificial Intelligence prototype for environmental and water-related analysis using Landsat satellite imagery. It demonstrates an end-to-end workflow from raw satellite scene discovery through feature engineering, machine learning classification, and interactive geospatial visualization.

---

## Author

**Reneilwe Keoagile** — CET313 Artificial Intelligence

---

## License

Educational and demonstration use. Developed as coursework at Botswana Accountancy College.
