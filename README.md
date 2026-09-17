# Landsat Water Intelligence Platform
[![Status](https://img.shields.io/badge/Status-Active-success.svg)]()
[![Python Backend](https://img.shields.io/badge/Backend-FastAPI-009688.svg)]()
[![Frontend](https://img.shields.io/badge/Frontend-Vite%20%2B%20JS-F7DF1E.svg)]()
[![Cloud](https://img.shields.io/badge/Cloud-Google%20Earth%20Engine-4285F4.svg)]()
[![ML](https://img.shields.io/badge/AI-XGBoost-F9A03C.svg)]()

A commercial-grade geographic intelligence platform designed for hydrogeologists and farm owners in arid terrains (like the Kalahari and Okavango). It leverages real-time Google Earth Engine telemetry, Sentinel/Landsat satellite imagery, and an XGBoost machine learning model to predict high-yield borehole targets and evaluate subsurface water feasibility.

---

## 🚀 Live Application Architecture

```mermaid
graph TD
    %% Define Styles
    classDef user fill:#ffffff,stroke:#333,stroke-width:2px,color:#000;
    classDef cloud fill:#e6f4e9,stroke:#1e8a3c,stroke-width:2px,color:#000;
    classDef ml fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#000;
    classDef front fill:#e8f4f8,stroke:#2daadf,stroke-width:2px,color:#000;

    User(("🧑‍💼 Farm Owner / Geologist")):::user
    
    subgraph Frontend ["Web Interface (Vite / Leaflet)"]
        UI["🗺️ Map Dashboard"]:::front
        Draw["✏️ Property Boundary Drawing"]:::front
    end

    subgraph Backend ["Python API (FastAPI)"]
        API["🔌 /api/analyze-polygon"]:::ml
        XGB["🧠 XGBoost ML Engine"]:::ml
    end

    subgraph GCP ["Google Cloud & Earth Engine"]
        EE["🌍 Google Earth Engine (Python API)"]:::cloud
        DEM["⛰️ Copernicus DEM 30m"]:::cloud
        SAR["📡 Sentinel-1 (Radar)"]:::cloud
        Multi["🛰️ Sentinel-2 (Multispectral)"]:::cloud
    end

    User -- "Draws Farm Boundary" --> Draw
    Draw -- "GeoJSON Polygon" --> API
    API -- "Request Pixel Grid" --> EE
    EE --> DEM
    EE --> SAR
    EE --> Multi
    EE -- "11 Live Feature Layers" --> API
    API -- "Feature Stack" --> XGB
    XGB -- "Drill Targets & Feasibility" --> UI
    UI -- "Actionable Dashboard" --> User
```

| Component | Technology |
|---|---|
| **Frontend App** | Vite, Vanilla JS, Leaflet.js |
| **Map Tiles** | Microsoft Planetary Computer, Esri |
| **Backend API** | Python 3, FastAPI, Uvicorn |
| **Cloud Telemetry** | Google Earth Engine Python API |
| **Machine Learning** | XGBoost, Scikit-Learn |
| **Authentication** | GCP Service Accounts (.json keys) |
| **Styling** | Custom CSS (Field-Survey Palette) |

---

## 🛠️ Key Features
- **Interactive Farm Drawing:** Draw dynamic polygon boundaries directly on the map to bound the investigation.
- **Live Earth Engine Telemetry:** The Python backend queries Google Earth Engine dynamically, extracting Live Topography (Slope, TWI), Structure (SAR VV/VH), and Vegetation indices (NDWI, NDVI).
- **XGBoost Subsurface Predictions:** Processes satellite data instantly through an XGBoost model trained on historical BGI borehole data to score locations on Water Table Depth, Yield, and Borehole Feasibility.
- **Automated Dossier Generation:** Prepares printable, professional hydrogeological reports instantly based on the drawn property boundaries.

---

## 💻 Local Installation & Usage

### Prerequisites
1. Node.js (v18+)
2. Python (3.9+)
3. A Google Cloud Service Account JSON Key with Earth Engine Access

### 1. Setup the Frontend
```bash
npm install
npm run dev
```
*The frontend will launch on `http://localhost:5173`.*

### 2. Setup the Backend API
Install backend dependencies:
```bash
pip install fastapi uvicorn earthengine-api xgboost pandas
```

Place your Google Cloud Service Account JSON key inside `.gee_secrets/service_account.json` (you will need to create this directory).

Start the FastAPI server:
```bash
python -m uvicorn backend.main:app --reload
```
*The API will listen on `http://127.0.0.1:8000`.*

---

## 📜 License
Proprietary / Closed Source. Developed for Landsat Water Intelligence operations.
