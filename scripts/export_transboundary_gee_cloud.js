/*
scripts/export_transboundary_gee_cloud.js

Google Earth Engine Code Editor Script for Server-Side Extraction
Directly processes all 6,218 Transboundary & BGI wells in parallel on Google Cloud.

INSTRUCTIONS:
1. Go to https://code.earthengine.google.com/
2. Go to Assets tab -> Click 'New' -> 'CSV file' -> Upload 'data/boreholes/transboundary_regional_enriched.csv'
3. Set asset name: projects/optimal-pursuit-507215-b8/assets/transboundary_regional_enriched
4. Paste this script into the Code Editor and click 'Run'.
5. In the 'Tasks' tab on the right, click 'Run' on the export task.
6. The enriched CSV will download to your Google Drive in ~3 minutes.
*/

var BOREHOLE_TABLE = "projects/optimal-pursuit-507215-b8/assets/transboundary_regional_enriched";
var EXPORT_NAME = "transboundary_gee_enriched_master";

// Study area covering Southern Africa (Botswana, Namibia, South Africa)
var study_bbox = ee.Geometry.Rectangle([11.0, -32.0, 34.0, -17.0]);

// 1. Topography (Copernicus 30m DEM)
var dem_raw = ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").select("DEM").mosaic();
var slope = ee.Terrain.slope(dem_raw.rename("elevation")).rename("slope_deg");
var dem = dem_raw.rename("dem_elevation");

// 2. Hydrology (MERIT Hydro TWI)
var flow_acc = ee.Image("MERIT/Hydro/v1_0_1").select("upa").rename("flow_accumulation");
var twi = ee.Image().expression(
  "log((flowAcc + 1) / (tan(slope * 3.14159265 / 180) + 0.001))",
  {"flowAcc": flow_acc, "slope": slope}
).rename("twi");

// 3. Sentinel-1 SAR Radar (C-Band, IW)
var s1 = ee.ImageCollection("COPERNICUS/S1_GRD")
  .filterBounds(study_bbox)
  .filterDate("2021-01-01", "2024-01-01")
  .filter(ee.Filter.eq("instrumentMode", "IW"))
  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
  .select(["VV", "VH"])
  .mean();

var s1_vv = s1.select("VV").rename("s1_vv").unmask(-11.5);
var s1_vh = s1.select("VH").rename("s1_vh").unmask(-17.2);
var s1_ratio = s1_vv.subtract(s1_vh).rename("s1_vv_vh_ratio");

// 4. Sentinel-2 Multispectral
var s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
  .filterBounds(study_bbox)
  .filterDate("2022-01-01", "2024-01-01")
  .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
  .median();

var ndvi = s2.normalizedDifference(["B8", "B4"]).rename("ndvi").unmask(0.25);
var ndwi = s2.normalizedDifference(["B3", "B8"]).rename("ndwi").unmask(-0.40);
var ndmi = s2.normalizedDifference(["B8", "B11"]).rename("ndmi").unmask(-0.20);

// Combine into 10-band image stack
var stack = ee.Image([
  dem, slope, flow_acc, twi,
  s1_vv, s1_vh, s1_ratio,
  ndvi, ndwi, ndmi
]);

// Load boreholes
var boreholes = ee.FeatureCollection(BOREHOLE_TABLE);

// Sample stack at borehole coordinates (30m resolution)
var sampled = stack.reduceRegions({
  collection: boreholes,
  reducer: ee.Reducer.mean(),
  scale: 30
});

// Export to Google Drive
Export.table.toDrive({
  collection: sampled,
  description: EXPORT_NAME,
  fileFormat: "CSV"
});

print("Export task created for", boreholes.size(), "boreholes.");
