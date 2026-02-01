# 🌍 AI-Driven Satellite Imagery Analysis Using Landsat

## 📌 Project Overview
This project is an **Artificial Intelligence prototype** focused on discovering and filtering high-quality **Landsat satellite imagery** for environmental and water-related analysis.  

The notebook uses the **Microsoft Planetary Computer** to query, filter, and prepare satellite scenes based on **cloud cover, data quality, and seasonal relevance**.

This work was developed as part of **CET313 – Artificial Intelligence**.

---

## 🎯 Problem Statement
Satellite imagery is often affected by:
- High cloud cover
- Inconsistent data quality
- Large volumes of unusable scenes  

Manually identifying suitable images for environmental analysis is time-consuming. This project automates that process using AI-driven filtering logic.

---

## 🧠 Key Features
- Automated discovery of Landsat 8 & 9 scenes
- Filtering by:
  - Cloud cover (< 20%)
  - Tier 1 data quality
- Wet-season focused scene selection
- AOI-driven satellite search
- Preparation of data for downstream AI analysis

---

## 🛰️ Data Source
- **Microsoft Planetary Computer**
- **Landsat Collection 2 Level-2 Surface Reflectance (L2SP)**

---

## 🛠 Technologies Used
- Python
- Jupyter / Google Colab
- Microsoft Planetary Computer
- PySTAC Client
- Rasterio
- Shapely
- Geospatial satellite data (Landsat 8 & 9)

---

## 🚀 How to Run the Project

### Option 1 — Google Colab
1. Upload the notebook to Google Colab
2. Run all cells sequentially
3. Required libraries install automatically

### Option 2 — Local Machine
```bash
pip install planetary-computer pystac-client rasterio shapely
jupyter notebook
