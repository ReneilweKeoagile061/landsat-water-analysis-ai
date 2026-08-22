# Landsat Water Analysis AI

**AI-driven satellite imagery analysis for discovering, filtering, and visualizing high-quality Landsat scenes and surface water potential across Botswana.**

Developed for **CET313 – Artificial Intelligence** · Botswana Accountancy College

---

## Overview

This repository combines a Jupyter-based geospatial machine learning pipeline with an interactive web dashboard. The notebook workflow queries Microsoft Planetary Computer for Landsat 8/9 imagery, filters scenes by cloud cover and Tier-1 quality, engineers spectral water indices (NDWI, MNDWI), and trains an XGBoost classifier to map low, medium, and high water-potential zones.

The frontend presents those results on a map-first dashboard with heatmaps, AOI overlays, model metrics, and scene filtering — designed to showcase the project clearly for portfolios, demos, and coursework submission.

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

Those figures measure how faithfully the classifier copies internally generated labels. Independent NDWI/AOI rules agree with K-Means only **26.7%** of the time (chance baseline **33.3%**). The Model tab on the dashboard surfaces this directly.

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
│   ├── export_frontend_data.py                           # Notebook CSV → frontend exports
│   └── generate_catalog_data.py                          # Full scene/water-point catalog export
├── tests/
│   └── filters.test.js                                   # Unit tests for filter + geo helpers
└── README.md
```

---

## Technologies

| Layer | Stack |
|-------|-------|
| Notebook | Python, Jupyter, PySTAC, Planetary Computer, Rasterio, Shapely, XGBoost, scikit-learn |
| Frontend | HTML, CSS, JavaScript, Leaflet, Leaflet.heat |
| Data | GeoJSON, JSON, Landsat 8/9 Collection 2 L2SP |

---

## Getting Started

### Prerequisites

- **Python 3.8+** (for notebook and export script)
- **Modern web browser** (for dashboard)
- No Node.js required for the frontend

### 1. Run the notebook

**Google Colab**

1. Upload `CET313_Artificial_Intelligence_Prototype (1).ipynb` to Colab
2. Run all cells sequentially

**Local machine**

```bash
pip install planetary-computer pystac-client rasterio shapely xgboost scikit-learn pandas
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
python -m http.server 8000
```

Open [http://localhost:8000](http://localhost:8000)

### Dashboard usage

1. Use the **Filters** tab to select AOI, cloud threshold, season, and tier
2. Click **Apply filters** to refresh the map and scene table
3. Toggle map layers: **NDWI heat**, **MNDWI heat**, **AOI gradients**, **Class points**
4. Hover over regions and points for detailed spectral and classification info
5. Review model metrics in the **Model** tab

---

## Data Source

- [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/)
- Landsat Collection 2 Level-2 Surface Reflectance (L2SP)
- Landsat 8 and Landsat 9 sensors

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
