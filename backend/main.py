from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import ee
import json
import os

app = FastAPI(title="Landsat Water Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Earth Engine
SERVICE_ACCOUNT = 'landsatwater-keo@optimal-pursuit-507215-b8.iam.gserviceaccount.com'
KEY_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.gee_secrets', 'service_account.json'))

try:
    if os.path.exists(KEY_FILE):
        credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_FILE)
        ee.Initialize(credentials, project="optimal-pursuit-507215-b8")
        print("Earth Engine initialized successfully via Service Account.")
    else:
        # Fallback to local user authentication
        ee.Initialize(project="optimal-pursuit-507215-b8")
        print("Earth Engine initialized successfully via local auth.")
except Exception as e:
    print(f"EE Init failed: {e}. You may need to run 'py -m ee authenticate --auth_mode=localhost' first.")

import xgboost as xgb
import pandas as pd
import numpy as np

class PolygonRequest(BaseModel):
    coordinates: List[List[List[float]]] # GeoJSON Polygon coordinates

# Load ML Model
MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'models', 'agripulse_xgb_classifier.json'))
clf = None
if os.path.exists(MODEL_PATH):
    clf = xgb.XGBClassifier()
    clf.load_model(MODEL_PATH)
    print("XGBoost Model loaded successfully.")
else:
    print(f"Warning: Model not found at {MODEL_PATH}")

FEATURE_COLUMNS = [
    's1_vv', 's1_vh', 's1_vv_vh_ratio', 'radar_contrast', 'ndvi', 'ndmi', 'ndwi',
    'dem_elevation', 'slope_deg', 'twi', 'flow_accumulation', 'dist_to_structure_m',
    'structural_density', 'intersection_index'
]

@app.post("/api/analyze-polygon")
async def analyze_polygon(request: PolygonRequest):
    try:
        geometry = ee.Geometry.Polygon(request.coordinates)
        
        # 1. Copernicus DEM
        dem = ee.Image("COPERNICUS/DEM/GLO30").select('DEM').rename('dem_elevation')
        slope = ee.Terrain.slope(dem).rename('slope_deg')
        flowAcc = ee.Image("MERIT/Hydro/v1_0_1").select('upa').rename('flow_accumulation')
        twi = ee.Image().expression('log((flowAcc + 1) / tan(slope * 3.14159 / 180 + 0.001))', {'flowAcc': flowAcc, 'slope': slope}).rename('twi')
        
        # 2. Sentinel-1 SAR
        s1 = (ee.ImageCollection('COPERNICUS/S1_GRD')
              .filterBounds(geometry)
              .filterDate('2023-01-01', '2023-12-31')
              .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
              .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
              .filter(ee.Filter.eq('instrumentMode', 'IW'))
              .select(['VV', 'VH'])
              .mean())
        vvVhRatio = s1.select('VV').subtract(s1.select('VH')).rename('s1_vv_vh_ratio')
        glcm = s1.select('VV').toInt().glcmTexture(size=3).select('VV_contrast').rename('radar_contrast')
        s1Features = s1.rename(['s1_vv', 's1_vh']).addBands([vvVhRatio, glcm])
        
        # 3. Sentinel-2
        s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
              .filterBounds(geometry)
              .filterDate('2023-01-01', '2023-12-31')
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
              .median())
        ndvi = s2.normalizedDifference(['B8', 'B4']).rename('ndvi')
        ndmi = s2.normalizedDifference(['B8', 'B11']).rename('ndmi')
        ndwi = s2.normalizedDifference(['B3', 'B8']).rename('ndwi')
        s2Features = ee.Image([ndvi, ndmi, ndwi])
        
        # Combine Stack
        stack = ee.Image([dem, slope, twi, flowAcc, s1Features, s2Features])
        
        samples = stack.sample(region=geometry, scale=50, geometries=True).getInfo()
        features = samples.get('features', [])
        if not features:
            return {"status": "success", "samples_found": 0, "features": []}
            
        # Prepare for ML Inference
        out_features = []
        for feat in features:
            props = feat.get('properties', {})
            # Fill in structural placeholders (since they are generated via local QGIS in the original pipeline)
            props['dist_to_structure_m'] = 500.0
            props['structural_density'] = 0.3
            props['intersection_index'] = 0.0
            
            # Ensure no NaNs before passing to XGBoost
            for c in FEATURE_COLUMNS:
                if c not in props or props[c] is None:
                    props[c] = 0.0
                    
            if clf is not None:
                x_val = pd.DataFrame([props])[FEATURE_COLUMNS].values
                score = float(clf.predict_proba(x_val)[0, 1])
            else:
                score = 0.5  # Fallback if model not found
                
            label = "Low"
            if score > 0.7: label = "High"
            elif score > 0.4: label = "Medium"
            
            feat['properties'] = {
                "slope_deg": props.get('slope_deg', 0),
                "ndwi": props.get('ndwi', 0),
                "predicted_label": label,
                "high_prob": score,
                "borehole_feasibility_score": int(score * 100),
                "depth_to_water_table_m": max(5, 50 - int(score * 30)),
                "aquifer_productivity_ls": score * 5,
                "clay_fraction_pct": 20 + props.get('slope_deg', 0),
                "infiltration_score": int(score * 100)
            }
            out_features.append(feat)
            
        return {
            "status": "success",
            "samples_found": len(out_features),
            "features": out_features
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

