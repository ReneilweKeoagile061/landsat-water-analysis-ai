// gee/agripulse_gee_feature_stack.js
// AgriPulse Google Earth Engine Feature Stack & Export Script
// Extracts structural, topographic, and spectral features for ML training

var farmAsset = ee.FeatureCollection("users/agripulse/current_farm"); // Load Farm Asset
var boreholes = ee.FeatureCollection("users/agripulse/bgi_verified_boreholes"); // Load Borehole Coordinates

var startDate = '2023-01-01';
var endDate = '2023-12-31';

// 1. Copernicus DEM - Topography & Hydrology
var dem = ee.Image("COPERNICUS/DEM/GLO30").select('DEM');
var slope = ee.Terrain.slope(dem).rename('slope_deg');
var flowAcc = ee.Image("MERIT/Hydro/v1_0_1").select('upa').rename('flow_accumulation');
var twi = ee.Image().expression(
    'log((flowAcc + 1) / tan(slope * 3.14159 / 180 + 0.001))', 
    {'flowAcc': flowAcc, 'slope': slope}
).rename('twi');

// 2. Sentinel-1 SAR - Structural Evidence
var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(farmAsset)
  .filterDate(startDate, endDate)
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .select(['VV', 'VH'])
  .mean();

var vvVhRatio = s1.select('VV').subtract(s1.select('VH')).rename('s1_vv_vh_ratio');
var glcm = s1.select('VV').toInt().glcmTexture({size: 3}).select('VV_contrast').rename('radar_contrast');
var s1Features = s1.rename(['s1_vv', 's1_vh']).addBands([vvVhRatio, glcm]);

// 3. Sentinel-2 - Vegetation & Moisture
var s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
  .filterBounds(farmAsset)
  .filterDate(startDate, endDate)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
  .median();

var ndvi = s2.normalizedDifference(['B8', 'B4']).rename('ndvi');
var ndmi = s2.normalizedDifference(['B8', 'B11']).rename('ndmi');
var ndwi = s2.normalizedDifference(['B3', 'B8']).rename('ndwi');
var s2Features = ee.Image([ndvi, ndmi, ndwi]);

// Combine into single stack
var featureStack = ee.Image([
  dem.rename('dem_elevation'), slope, twi, flowAcc,
  s1Features,
  s2Features
]);

// Sample features at borehole locations
var trainingData = featureStack.sampleRegions({
  collection: boreholes,
  properties: ['borehole_id', 'is_productive', 'yield_m3h', 'water_strike_m'],
  scale: 10,
  geometries: true
});

// Export to Google Drive
Export.table.toDrive({
  collection: trainingData,
  description: 'agripulse_bgi_ml_features',
  folder: 'AgriPulse_ML',
  fileFormat: 'CSV'
});
