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

---

## Areas of Interest (AOIs)

| AOI | Description |
|-----|-------------|
| **Okavango Delta** | Water-dominant ecosystem; seasonal flooding dynamics |
| **Kalahari Fringe** | Dry/desert terrain; reduces false-positive water detections |
| **Transitional Zone** | Mixed hydrological conditions between wet and dry regions |

---

## Model Performance

From the improved XGBoost run in the notebook:

| Metric | Value |
|--------|-------|
| Accuracy | 99.60% |
| Weighted F1 | 0.9960 |
| Macro F1 | 0.9737 |
| Test samples | 2,500 |

Per-class results:

| Class | Precision | Recall | F1-Score |
|-------|-----------|--------|----------|
| Low | 0.9968 | 0.9946 | 0.9957 |
| Medium | 0.9961 | 0.9974 | 0.9968 |
| High | 0.9286 | 0.9286 | 0.9286 |

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
├── styles.css                                            # Dashboard styling
├── app.js                                                # Map logic, filters, data loading
├── data/
│   └── exports/
│       ├── aois.geojson                                  # AOI polygon boundaries
│       ├── water_points.geojson                          # Prediction points + indices
│       ├── scenes.json                                   # Filtered Landsat scenes
│       └── metrics.json                                  # Model KPIs
├── scripts/
│   └── export_frontend_data.py                           # Notebook CSV → frontend exports
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
