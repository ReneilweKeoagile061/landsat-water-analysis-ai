# Groundwater Prospectivity Prediction — Project Overview
### Stampriet Transboundary Aquifer System (STAS) · Botswana / Namibia / South Africa

> **Version:** 1.0 · **Last Updated:** November 2026  
> **Region of Focus:** Stampriet Transboundary Aquifer System (Kalahari Basin)  
> **Core Objective:** Use multi-source satellite imagery, in-situ borehole records, and machine learning to predict where productive groundwater exists — without drilling blindly.

---

## Table of Contents

1. [The Problem Being Solved](#1-the-problem-being-solved)
2. [Limitations Before This Project](#2-limitations-before-this-project)
3. [How the New ORASECOM STAS Data Solves Those Limitations](#3-how-the-new-orasecom-stas-data-solves-those-limitations)
4. [What the Shapefiles Would Add](#4-what-the-shapefiles-would-add)
5. [Current Model — What It Does and What It Gets Right](#5-current-model--what-it-does-and-what-it-gets-right)
6. [How to Improve the Model for Accurate Borehole Prediction](#6-how-to-improve-the-model-for-accurate-borehole-prediction)
7. [Commercialisation Roadmap](#7-commercialisation-roadmap)

---

## 1. The Problem Being Solved

### Background
The **Stampriet Transboundary Aquifer System (STAS)** stretches across Botswana, Namibia, and South Africa and is one of the largest confined aquifer systems in sub-Saharan Africa. Millions of rural people and livestock across this semi-arid region depend on groundwater as their **only reliable fresh-water source**.

### The Core Challenge
Drilling a borehole is expensive — typically **$15,000–$80,000 USD per hole** depending on depth and equipment mobilisation in remote areas. Without prior knowledge of where productive water exists, **failure rates can exceed 50%** in complex aquifer systems like the Kalahari. Governments and water utilities currently rely on:

- Outdated hydrogeological maps
- Expensive geophysical surveys (ERT, seismic)
- Expert geologist judgement and legacy borehole records
- Trial-and-error drilling campaigns

### What This Project Does
This system uses **satellite remote sensing + machine learning** to predict **borehole prospectivity** (the likelihood of striking productive groundwater at a given location) before a single metre of ground is drilled. Specifically it:

| Task | Description |
|------|-------------|
| **Satellite Feature Extraction** | Pulls 12+ spectral and radar indices per GPS point from Google Earth Engine (Landsat 8/9, Sentinel-1 SAR, SRTM DEM) |
| **ML Classification** | Trains an XGBoost classifier on 84 verified boreholes to label each location as `low`, `medium`, or `high` prospectivity |
| **Drill Target Ranking** | Scores a spatial grid of candidate locations and ranks the top targets with recommended next steps (e.g. ERT geophysics line) |
| **Interactive Web Map** | Presents all predictions, borehole data, and confidence scores in a browser-based map dashboard |

### Who Benefits
- **Government water departments** (DWMWA Botswana, NamWater, DWS South Africa) — reduce campaign failure rates
- **Rural communities** — faster access to reliable boreholes at lower cost per successful well
- **NGOs and development finance** — data-driven justification for where to invest drilling budgets
- **Private hydrogeology consultancies** — a scalable tool that augments expert field work

---

## 2. Limitations Before This Project

Before the ORASECOM STAS data was incorporated, the model was operating with significant blind spots:

### 2.1 Tiny, Localised Ground-Truth Dataset
- Only **84 verified borehole records** from the BGI (Bureau for Geological Survey and Infrastructure, Botswana) dataset, all concentrated in the **Khudumelapye** sub-area
- No records from Namibia or South Africa portions of the STAS
- Class imbalance: very few `high`-yield boreholes → the model struggles to generalise the "high" class (F1 = 0.93 vs 0.99 for low/medium)

### 2.2 No Sub-Surface / Hydrogeological Context
- The model only saw surface signals from satellites — NDVI, NDWI, SAR backscatter, slope, TWI
- It had **zero knowledge** of aquifer type (confined vs unconfined), aquifer thickness, transmissivity, or storativity
- Two locations with identical satellite signatures but different aquifer depths would receive identical (and potentially wrong) predictions

### 2.3 No Groundwater Quality Information
- A borehole might be hydrologically productive (good yield) but chemically unusable (high TDS, fluoride, nitrates)
- Without water quality data, a "productive" prediction could still result in an unusable borehole
- The model had no way to flag locations where yield is likely high but quality is poor

### 2.4 No Temporal Groundwater Trend Data
- Groundwater levels fluctuate seasonally and are declining in many over-abstracted areas
- Without piezometric time-series or GRACE satellite anomaly data, the model could not distinguish between:
  - A location that is currently saturated (wet season)
  - A location that is permanently reliable (perennial)

### 2.5 No Abstraction Context
- Some areas are over-exploited — existing boreholes pump them down faster than recharge
- Without abstraction records, the model could rank an already-depleted zone as high-prospectivity

### 2.6 No Spatial Structural Controls
- Fault zones, geological contacts, and fracture networks are the **primary conduits** for groundwater movement in the Kalahari
- Without fault/geology shapefiles, the model could not use distance-to-structure as a feature — one of the most predictive hydrogeological signals
- `dist_to_structure_m` appears in the ranked drill targets output, meaning it was **estimated or placeholder-valued**, not computed from real vector data

### 2.7 Single-Point-in-Time Satellite Composites
- Features were computed from median composites (single period), masking seasonal variability
- Seasonal NDWI and SAR changes correlate strongly with shallow aquifer recharge but were invisible to the model

---

## 3. How the New ORASECOM STAS Data Solves Those Limitations

The ORASECOM STAS dataset (downloaded from `wis.orasecom.org`) is the **official transboundary hydrogeological database** for the Stampriet Aquifer System, compiled under the GGRETA project (Governance of Groundwater Resources in Transboundary Aquifers). Here is what it contributes:

### 3.1 Borehole Database — `STAS_BoreholeDatabase_Clean_25072018.xls`
- **~500+ borehole records** spanning Botswana, Namibia, and South Africa
- Columns: borehole ID, coordinates, aquifer unit (Auob / Nossob / Kalahari), depth, yield (m³/h), water strike depth, static water level, drilling date, pumping test results
- **Impact:** Expands ground truth from 84 → 500+ points and adds multi-country, multi-aquifer coverage. Critically enables separate model training per aquifer unit

### 3.2 Groundwater Quality — `Stampriet data analysis 2010-2015.xls` + `Water quality changes in the SAB.xlsx`
- TDS (Total Dissolved Solids), pH, electrical conductivity, fluoride, nitrates, sulphates per borehole
- **Impact:** Allows the model (or a secondary classifier) to predict not just *yield* but *water potability* — a critical dual-output for real-world deployment

### 3.3 Abstraction Data — `Abstraction_File_Revised.xlsx`
- Monthly abstraction volumes per production borehole by town/farm (Stampriet, Aminuis, Aranos, Gochas, Leonardville, Kries)
- **Impact:** Can be used to flag over-exploited zones and penalise their prospectivity score, or to train a **depletion risk model**

### 3.4 Precipitation & ETR — `STAS_Precipitation_ETR.xlsx`
- Multi-year monthly precipitation and evapotranspiration for STAS sub-catchments
- **Impact:** Enables temporal recharge modelling. When combined with GRACE anomaly data, enables a **groundwater balance estimate** per zone

### 3.5 GRACE Satellite Data — `Stampriet Aquifer System.xlsx`
- GRACE total water storage anomalies (TWS) over the STAS from NASA/GRACE-FO
- **Impact:** Time-series of aquifer-scale mass change — the only satellite signal that directly measures **sub-surface water storage volume**. Adding this as a temporal feature dramatically improves predictions for deeper confined aquifers

### 3.6 Piezometric Time-Series — `PiezometricData.docx` + station `.xls` files
- Water level measurements at monitoring boreholes (stations like Stampriet, Olifantwater, Tweerivier, Auob, Nossob, Kalahari)
- **Impact:** Provides temporal trend data — is the aquifer recharging or declining? This is the most direct sub-surface signal available without drilling

### 3.7 Hydraulic Parameter Shapefiles (Partial — `.shp` / `.shx` Present)
- `Auob_hydraulic_parameter_and_thickness_points.shp`  
- `Kalahari_hydraulic_parameter_and_thickness_points.shp`  
- `Nossob_hydraulic_parameter_and_thickness_points.shp`
- **Impact:** Transmissivity, hydraulic conductivity, and aquifer thickness per point — the **most physically meaningful features** for predicting sustainable yield. Even partially available, these can be spatially interpolated (Kriging) to create a raster feature layer

### 3.8 Rainfall Reference Maps (JPEGs)
- `rainfall.jpg`, `gwl_auob.jpg`, `gwl_kalahari.jpg`, `gwl_nossob.jpg`, `yield_auob.jpg`, etc.
- **Current use:** Visual reference for domain understanding
- **Future use:** Can be georeferenced (GDAL) and used as coarse raster covariates if no better raster exists

### Summary Table

| Old Limitation | STAS Data That Addresses It |
|---|---|
| 84 boreholes, Botswana only | 500+ boreholes, 3 countries, 3 aquifer units |
| No water quality | Groundwater quality dataset (2010–2015) |
| No abstraction context | Abstraction records per production borehole |
| No temporal trend | Piezometric time-series + GRACE anomalies |
| No recharge data | Precipitation + ETR dataset |
| No hydraulic parameters | Hydraulic parameter shapefiles (Auob, Kalahari, Nossob) |
| No structural features | Fault + geology shapefiles (still pending full download) |

---

## 4. What the Shapefiles Would Add

The 11 shapefile categories from ORASECOM STAS are **not fully downloaded yet** (63 of the `.dbf`, `.cpg`, `.prj`, `.qpj` component files returned 403/404). What they would unlock:

### 4.1 Aquifer Boundaries — `STAS_boundaries.shp`
- Polygon layer defining the exact extent of the Auob, Nossob, and Kalahari aquifer units
- **Model feature:** Each borehole/candidate point can be tagged with its aquifer unit ID → enables **aquifer-stratified model training** (separate classifiers per aquifer, or aquifer-unit as a one-hot feature)
- **Current workaround:** Aquifer unit is inferred from name strings in the borehole database, which is unreliable

### 4.2 Faults — `Faults.shp`
- Polyline layer of mapped fault traces across the STAS
- **Model feature:** `dist_to_fault_m` — distance from candidate point to nearest fault
- **Why it matters:** Faults create secondary porosity and preferential flow paths in the Karoo sandstone aquifers (Auob, Nossob). Boreholes within 500 m of a fault are statistically 2–3x more likely to be productive
- **Currently:** `dist_to_structure_m` in the ranked targets output is estimated, not computed from real fault data

### 4.3 Geological Units — `Geological_units.shp`
- Polygon layer of surface geology (Kalahari sand, Karoo sandstone, basement granite, etc.)
- **Model feature:** `geology_class` as a categorical feature — different lithologies have fundamentally different recharge and storage properties
- **Why it matters:** Karoo sandstones (Auob/Nossob) are confined, fractured, and deep; Kalahari sands are unconfined and shallow. Knowing which unit a point is in changes the prediction entirely

### 4.4 Boreholes Shapefile — `Boreholes.shp`
- Point layer of all STAS boreholes with attribute table linking to the borehole database
- **Use:** Spatial validation — cross-check that point coordinates in the Excel database match the shapefile geometries. Any discrepancies indicate GPS errors in the tabular data
- **Also enables:** Spatial density analysis (are there clusters of productive boreholes that reveal a structural control?)

### 4.5 Piezometric Boreholes — `Piezometric_boreholes.shp`
- Point layer of monitoring borehole network
- **Use:** Identify which monitoring stations are within the study area and can be spatially joined to the prediction grid for temporal water-level features

### 4.6 Rivers — `Rivers.shp`
- Polyline layer of surface drainage network (ephemeral rivers: Auob, Nossob, Molopo)
- **Model feature:** `dist_to_river_m` — ephemeral rivers are preferential recharge zones in the Kalahari
- **Why it matters:** Boreholes close to dry riverbeds (< 2 km) often intersect paleochannel sediments with significantly higher permeability

### 4.7 Cross Sections — `Cross_sections.shp`
- Lines defining the hydrogeological cross-section transects
- **Use:** Visual interpretation aid and depth-to-aquifer estimation along transects

### 4.8 Groundwater Quality Shapefile — `Groundwater_quality.shp`
- Spatially-explicit water quality observations
- **Model feature:** Enables **spatial interpolation of TDS/EC** across the aquifer — building a continuous "water quality risk" surface raster

### 4.9 Country Boundaries — `Country_boundaries.shp`
- Used for cartographic context and for disaggregating model predictions per country for regulatory reporting

### Complete Shapefile Impact on Model Accuracy

If all shapefiles were available and integrated:

```
Expected new features added:
  + aquifer_unit          (categorical: Auob / Nossob / Kalahari)
  + geology_class         (categorical: 5–8 lithology classes)
  + dist_to_fault_m       (continuous: metres to nearest mapped fault)
  + dist_to_river_m       (continuous: metres to nearest ephemeral river)
  + tds_interpolated      (continuous: estimated groundwater TDS via Kriging)
  + aquifer_thickness_m   (continuous: from hydraulic parameter points)
  + transmissivity_m2d    (continuous: from hydraulic parameter points)

Expected improvement: +3–8% macro-F1, largest gain on "high" class
(currently F1 = 0.93, target ≥ 0.97)
```

---

## 5. Current Model — What It Does and What It Gets Right

### Architecture
- **Algorithm:** XGBoost gradient boosted classifier (3-class: `low` / `medium` / `high`)
- **Features (12):** `dem_elevation`, `flow_accumulation`, `ndmi`, `ndvi`, `ndvi_variance`, `ndwi`, `radar_contrast`, `s1_vh`, `s1_vv`, `s1_vv_vh_ratio`, `slope_deg`, `twi`
- **Training data:** 84 BGI-verified boreholes (Khudumelapye, Botswana)
- **Labels:** Rule-based threshold labelling on yield (`low` < 0.5 m³/h, `medium` 0.5–5, `high` > 5), then validated against k-means clusters

### Current Performance (`data/exports/metrics.json`)

| Metric | Value |
|--------|-------|
| Accuracy | **99.6%** |
| Weighted F1 | **99.6%** |
| Macro F1 | **97.4%** |
| Spatial CV (5-fold mean) | **99.6%** |
| High-class F1 | **92.9%** ⚠️ |
| Label agreement (rule vs k-means) | 26.7% (barely above 33% chance) ⚠️ |

### Key Warning
The 99.6% accuracy is **inflated** due to:
1. **Spatial autocorrelation** — nearby boreholes in a 84-point dataset share identical satellite pixels; a spatial CV helps but the blocks may still be small
2. **Label noise** — rule-based vs k-means label agreement of only 26.7% (barely above the 33% random baseline) suggests the labels themselves are uncertain
3. **Training-distribution mismatch** — the model was trained only on Khudumelapye. When applied to new regions (Namibia, South Africa), generalisation is unknown

---

## 6. How to Improve the Model for Accurate Borehole Prediction

This section outlines a systematic improvement path from the current state toward a production-grade hydrogeological prediction system.

### Step 1 — Fix and Expand Ground Truth (Highest Priority)

| Action | Details |
|--------|---------|
| Integrate STAS Borehole Database | Adds ~500 labelled boreholes across 3 aquifer units |
| Re-label using physical yield thresholds | Use domain expert thresholds per aquifer unit (Auob yields differ from Kalahari) |
| Add Namibia production data | `Stampriet Production.xls`, `Aminuis Production.xls`, `Aranos Production.xls`, `Gochas Production.xls`, `Leonardville Production.xls`, `Kries Production.xls` |
| Cross-validate with WPDX | Use Water Point Data Exchange records for additional Botswana boreholes |
| Minimum target dataset | 300+ points with 50+ "high" class examples |

### Step 2 — Add Hydrogeological Features

```python
# New features to engineer from STAS data
features_to_add = {
    # From shapefiles (once downloaded)
    "dist_to_fault_m":        "Spatial join to Faults.shp",
    "dist_to_river_m":        "Spatial join to Rivers.shp",
    "aquifer_unit":           "Point-in-polygon join to STAS_boundaries.shp",
    "geology_class":          "Point-in-polygon join to Geological_units.shp",
    "aquifer_thickness_m":    "IDW interpolation from hydraulic parameter points",
    "transmissivity_m2d":     "IDW interpolation from hydraulic parameter points",

    # From tabular STAS data (already downloaded)
    "mean_annual_precip_mm":  "From STAS_Precipitation_ETR.xlsx",
    "mean_etr_mm":            "From STAS_Precipitation_ETR.xlsx",
    "grace_tws_anomaly":      "From Stampriet Aquifer System.xlsx (GRACE)",
    "piezometric_trend":      "Linear trend from PiezometricData station nearest to point",
    "abstraction_density":    "Nearby abstraction volume per km2 from Abstraction_File_Revised.xlsx",

    # From expanded satellite time series (GEE)
    "ndwi_seasonal_range":    "Max − min NDWI across wet/dry seasons",
    "s1_seasonal_std":        "SAR backscatter seasonal standard deviation",
    "lst_mean_K":             "Landsat land surface temperature (evapotranspiration proxy)",
}
```

### Step 3 — Improve Label Quality

The current label agreement (rule-based vs k-means = 26.7%) is a red flag. Fix by:

1. **Use continuous yield regression first** — predict actual yield (m³/h) as a regression target, then threshold into classes. This avoids arbitrary label binning
2. **Multi-label approach** — combine yield + static water level + depth as a composite "borehole value index"
3. **Aquifer-stratified labelling** — the yield threshold for "productive" in the deep confined Auob aquifer is different from the shallow Kalahari unit

### Step 4 — Better Model Architecture

| Upgrade | Rationale |
|---------|-----------|
| **Stratified k-fold spatial CV** (block size 20+ km) | Prevents spatial leakage; gives honest accuracy estimates |
| **Two-stage model** (yield classifier then quality classifier) | Predict yield first; for high-yield locations, run a separate quality model |
| **Probabilistic output** (XGBoost `predict_proba`) | Return confidence intervals, not just class labels |
| **SHAP explanations per prediction** | Show which features drove each prediction → builds trust with domain experts |
| **Aquifer-unit stratified models** | Train separate models for Auob, Nossob, Kalahari — each has distinct geology and hydraulics |
| **Temporal GRACE + piezometric features** | Use LSTM or time-series features for the monitoring borehole trend signal |
| **Ensemble: XGBoost + Random Forest + Logistic Regression** | Reduces variance, improves calibration |

### Step 5 — Spatial Validation

After training, validate using:
- **Leave-one-region-out CV** — train on Botswana, test on Namibia
- **Prospectivity map vs. known-productive areas** — do the high-score zones align with areas where existing boreholes are clustered?
- **Comparison with existing hydrogeological expert maps** — the STAS reference maps (yield_auob.jpg, etc.) are ground-truth visual validation

### Step 6 — Continuous Improvement Loop

```
Deploy → collect new drilling outcomes → re-label → retrain → redeploy
```

Every new borehole drilled using the system's recommendations becomes training data. After 50+ new drill outcomes are recorded, the model should be retrained with the actuals. This creates a **self-improving system** where accuracy increases over time.

---

## 7. Commercialisation Roadmap

### Market Context
- Sub-Saharan Africa has a **$2.4 billion annual rural water supply investment gap**
- Groundwater prospecting services are currently dominated by expensive geophysical surveys (ERT, seismic) that cost $5,000–$20,000 per line-km
- A data-driven pre-screening tool that reduces failed-hole rates by even 20–30% represents **$3,000–$24,000 saved per campaign**

---

### Tier 1 — Minimum Viable Product (Now → 6 Months)

**What it is:** A cloud-deployed web application that accepts GPS coordinates and returns a prospectivity score with confidence intervals and recommended next steps.

| Feature | Status |
|---------|--------|
| Borehole map dashboard (Leaflet + GEE) | Built |
| XGBoost prospectivity classifier | Trained |
| Ranked drill target output (JSON) | Working |
| FastAPI backend | Built |
| Multi-country STAS data integration | In progress |
| Shapefile feature engineering | Pending download |
| Production deployment (Render/Vercel) | Pending |

**Revenue model:** Per-report SaaS (e.g., $500/investigation area report for a 50 km2 zone)

---

### Tier 2 — Full SaaS Platform (6–18 Months)

| Addition | Description |
|----------|-------------|
| **Self-service dashboard** | Users upload their own borehole CSV → model re-ranks predictions for their area |
| **Water quality risk layer** | Secondary output: TDS/fluoride risk index alongside yield prospectivity |
| **Depletion risk model** | Flags zones where abstraction > estimated recharge (uses GRACE + abstraction data) |
| **ERT line optimizer** | Given a ranked target list, compute the optimal ERT line placement to verify subsurface |
| **API access tier** | Programmatic access for GIS firms and government systems to query the model |
| **Multilingual reporting** | Auto-generate PDF reports in English, Setswana, Afrikaans |
| **Offline mobile app** | Field hydrogeologists can collect data and sync when back in connectivity |

**Revenue model:** Subscription tiers — Government ($2,000/month per province), Consulting Firms ($800/month), NGO/Development Finance ($300/month with nonprofit discount)

---

### Tier 3 — Regional Scale-Out (18–36 Months)

| Addition | Description |
|----------|-------------|
| **Pan-African coverage** | Expand beyond STAS to other transboundary aquifer systems (NWSAS, Iullemeden, Congo) |
| **Partnerships with water utilities** | NamWater, DWMWA, WRC South Africa — white-label the tool under their branding |
| **Carbon credit linkage** | Productive boreholes reduce diesel-pump reliance; certifiable as clean-water carbon offset |
| **Insurance product** | "Borehole insurance" backed by model confidence score — if the hole is dry, partial refund |
| **ERT / geophysics data ingestion** | Accept geophysicist's field ERT data as an additional input feature for reranking |
| **Real-time GRACE monitoring alerts** | Alert subscribers when GRACE anomalies indicate aquifer depletion events |
| **Drilling success database** | Community-contributed borehole outcomes to continuously improve the model |
| **Integration with DWS / BIMS** | Auto-import borehole records from national borehole information management systems |

---

### Competitive Advantages

| Advantage | Detail |
|-----------|--------|
| **Multi-source data fusion** | Combines satellite (Landsat, Sentinel-1, GRACE), in-situ (borehole DB), and hydrogeological (STAS shapefiles) — no single competitor does all three |
| **Transboundary coverage** | Operates across Botswana, Namibia, South Africa simultaneously using shared ORASECOM data — bypasses the need for each country's separate database |
| **Explainable predictions** | SHAP feature importance per location builds trust with hydrogeologists who are sceptical of black-box ML |
| **Low barrier to entry** | A hydrogeologist or driller only needs GPS coordinates and a browser — no GIS software, no satellite data licence required |
| **Continuous improvement** | Every drilling outcome feeds back into the model; the product gets better the more it is used |
| **Open-data foundation** | Built on ORASECOM, GRACE, Landsat, and SRTM — all public datasets — keeping marginal data costs near zero |

---

## Appendix: Data Assets Inventory

### Currently Available (Fully Loaded)

| Dataset | Location | Records / Size | Key Fields |
|---------|----------|----------------|------------|
| BGI Verified Boreholes | `data/boreholes/bgi_verified_boreholes.csv` | 84 boreholes | yield_m3h, water_strike_m, static_water_level_m, total_depth_m |
| ML Feature Matrix | `data/boreholes/agripulse_bgi_ml_features_v2_12feat.csv` | 84 rows × 18 col | 12 GEE features + coordinates |
| STAS Borehole Database | `data/external/orasecom_stas/STAS_BoreholeDatabase_Clean.csv` | 500+ boreholes | Multi-aquifer, 3 countries |
| Groundwater Quality | `data/external/orasecom_stas/02_groundwater_quality/` | 2010–2015 | TDS, pH, EC, ions |
| Abstraction Records | `data/external/orasecom_stas/03_abstraction/Abstraction_File_Revised.xlsx` | Town-level monthly | m3/month per station |
| Precipitation & ETR | `data/external/orasecom_stas/04_precipitation_etr/STAS_Precipitation_ETR.xlsx` | Multi-year monthly | mm/month |
| GRACE Anomalies | `data/external/orasecom_stas/05_grace_satellite/Stampriet Aquifer System.xlsx` | 2002–2017 | TWS anomaly (cm) |
| Hydraulic Parameters | `data/external/orasecom_stas/01_shapefiles_wgs84/10_hydraulic_parameters/*.shp` | Point data | Transmissivity, thickness, 3 aquifer units |
| Reference Maps | `data/external/orasecom_stas/07_reference_maps/` | 14 images/PDFs | GWL, yield, TDS, rainfall, elevation |

### Pending (Shapefile Components — 403/404 on Download)

| Shapefile Set | Missing Components | Impact |
|---------------|-------------------|--------|
| Aquifer Boundaries | .dbf, .cpg, .prj, .qpj | Cannot tag points with aquifer unit |
| Faults | .dbf, .cpg, .prj, .qpj | Cannot compute dist_to_fault_m |
| Geological Units | .dbf, .cpg, .prj, .qpj | Cannot assign lithology class |
| Boreholes (vector) | .dbf, .cpg, .prj, .qpj | Cannot spatial-validate borehole coordinates |
| Rivers | .dbf, .cpg, .prj, .qpj | Cannot compute dist_to_river_m |
| Piezometric Boreholes | .dbf, .cpg, .prj, .qpj | Cannot spatially join monitoring stations |
| Cross Sections | .dbf, .cpg, .prj, .qpj | Interpretive reference only |
| Groundwater Quality (vector) | .dbf, .cpg, .prj, .qpj | Cannot interpolate quality surface |
| Country Boundaries | .dbf, .cpg, .prj, .qpj | Cartographic only |
| Towns | .dbf, .cpg, .prj, .qpj | Proximity-to-settlement feature |

> **Resolution:** Contact ORASECOM directly at `wis@orasecom.org` to request corrected download links or a bulk data package. Alternative: source geometry-only equivalents from GADM (country/admin boundaries), OSM (rivers, towns), and published GGRETA1 report supplementary files.

---

*This document is part of the Landsat-Water Groundwater Prospectivity project.*  
*For technical implementation details see `README.md`, `DATA_PIPELINE.md`, and `CHANGELOG.md`.*
