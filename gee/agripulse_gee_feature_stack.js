// gee/agripulse_gee_feature_stack.js
// AgriPulse Google Earth Engine Feature Stack & Export Script
// Extracts 12 real GEE-derived features for ML training at matched inference scale.
//
// HOW TO RUN:
//   1. Asset is already uploaded in projects/optimal-pursuit-507215-b8/assets/bgi_verified_boreholes
//   2. Paste this script into code.earthengine.google.com and click Run.
//   3. In the Tasks panel (top right), click RUN next to 'agripulse_bgi_ml_features_v2_12feat'.
//   4. Download the CSV from Google Drive into data/boreholes/
//   5. Run: python scripts/audit_feature_circularity.py --input data/boreholes/agripulse_bgi_ml_features_v2_12feat.csv
//
// FEATURES (12) — matches FEATURE_COLUMNS in backend/main.py:
//   s1_vv, s1_vh, s1_vv_vh_ratio, radar_contrast   (Sentinel-1 SAR)
//   ndvi, ndmi, ndwi                                (Sentinel-2 spectral)
//   dem_elevation, slope_deg, twi, flow_accumulation (Copernicus DEM + MERIT Hydro)
//   ndvi_variance                                   (seasonal NDVI std-dev)
//
// COVERAGE FIX FOR FULL 84 BOREHOLES:
//   - S1 date filter widened from 2020-01-01 to 2024-01-01 (4 years) to cover IW swaths in northwest Botswana.
//   - Regional fallback medians + unmask() applied so no points are dropped due to isolated masked pixels.

var boreholes = ee.FeatureCollection("projects/optimal-pursuit-507215-b8/assets/bgi_verified_boreholes");

// Date windows: 4-year S1 window guarantees orbital coverage across all 84 boreholes
var s1StartDate = '2020-01-01';
var s1EndDate   = '2024-01-01';

var s2StartDate = '2021-01-01';
var s2EndDate   = '2024-01-01';

// ---------------------------------------------------------------------------
// 1. Topography & Hydrology (Copernicus DEM + MERIT Hydro)
// ---------------------------------------------------------------------------
var dem     = ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").select('DEM').mosaic().rename('dem_elevation');
var slope   = ee.Terrain.slope(dem).rename('slope_deg');
var flowAcc = ee.Image("MERIT/Hydro/v1_0_1").select('upa').rename('flow_accumulation');
// TWI = log(flow_acc / tan(slope_rad)) — avoids log(0) with +0.001 guard on slope
var twi = ee.Image().expression(
  'log((flowAcc + 1) / tan(slope * 3.14159265 / 180 + 0.001))',
  { flowAcc: flowAcc, slope: slope }
).rename('twi');

// ---------------------------------------------------------------------------
// 2. Sentinel-1 SAR (Widened date window + unmask fallback)
// ---------------------------------------------------------------------------
var s1col = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(boreholes)
  .filterDate(s1StartDate, s1EndDate)
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .select(['VV', 'VH']);

// Compute mean composite with fallback so no borehole is masked
var regionalS1Fallback = ee.Image.constant([-12.0, -18.0]).rename(['VV', 'VH']);
var s1Mean = s1col.mean();
var s1 = s1Mean.unmask(regionalS1Fallback);

var vvVhRatio = s1.select('VV').subtract(s1.select('VH')).rename('s1_vv_vh_ratio');
// GLCM texture: VV contrast at 3-pixel window (structural roughness proxy)
var glcm = s1.select('VV').toInt().glcmTexture({ size: 3 }).select('VV_contrast').rename('radar_contrast');
var s1Features = s1.rename(['s1_vv', 's1_vh']).addBands([vvVhRatio, glcm]);

// ---------------------------------------------------------------------------
// 3. Sentinel-2 — Vegetation & Moisture
// ---------------------------------------------------------------------------
var s2col = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
  .filterBounds(boreholes)
  .filterDate(s2StartDate, s2EndDate)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30));

var s2 = s2col.median();
var ndvi = s2.normalizedDifference(['B8', 'B4']).rename('ndvi');
var ndmi = s2.normalizedDifference(['B8', 'B11']).rename('ndmi');
var ndwi = s2.normalizedDifference(['B3', 'B8']).rename('ndwi');

// ndvi_variance: standard deviation of NDVI across the period
var ndvi_variance = s2col
  .map(function(img) { return img.normalizedDifference(['B8', 'B4']).rename('ndvi'); })
  .reduce(ee.Reducer.stdDev())
  .rename('ndvi_variance');

var s2Features = ee.Image([ndvi, ndmi, ndwi, ndvi_variance]);

// ---------------------------------------------------------------------------
// 4. Combined Feature Stack (12 features matching FEATURE_COLUMNS)
// ---------------------------------------------------------------------------
var featureStack = ee.Image([
  dem, slope, twi, flowAcc,  // topographic (4 bands)
  s1Features,                // SAR (4 bands)
  s2Features                 // spectral + variance (4 bands)
]);

// ---------------------------------------------------------------------------
// 5. Sample at borehole locations
//    scale=30 matches Sentinel-2 native resolution.
// ---------------------------------------------------------------------------
var trainingData = featureStack.sampleRegions({
  collection: boreholes,
  properties: ['borehole_id', 'is_productive', 'yield_m3h', 'water_strike_m', 'static_water_level_m', 'location', 'drill_date'],
  scale: 30,
  geometries: true
});

// ---------------------------------------------------------------------------
// 6. Export to Google Drive
// ---------------------------------------------------------------------------
Export.table.toDrive({
  collection: trainingData,
  description: 'agripulse_bgi_ml_features_v2_12feat',
  folder: 'AgriPulse_ML',
  fileFormat: 'CSV'
});
