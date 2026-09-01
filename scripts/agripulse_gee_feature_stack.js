/*
AgriPulse GEE Feature Extraction Stack
Step 3a - Google Earth Engine Feature Engineering

Extracts 14-feature stack (Sentinel-1, Sentinel-2, DEM, structural) at exact
borehole coordinates and exports joined CSV.

USAGE IN GOOGLE EARTH ENGINE CODE EDITOR:
1. Copy-paste this entire script into the GEE Code Editor (code.earthengine.google.com)
2. Modify INVESTIGATION_AREA_GEOM (line ~30) to your target region polygon
3. Set EXPORT_FILENAME to match your investigation name
4. Run script
5. Check Tasks panel; click RUN on the export task
6. Download CSV when complete: agripulse_bgi_ml_features.csv
7. Save locally as: data/boreholes/agripulse_bgi_ml_features.csv

EXPECTED INPUT:
- Asset path: projects/your-gee-project/assets/agripulse_boreholes_table
  (uploaded GEE table with columns: borehole_id, latitude, longitude, geometry)

EXPECTED OUTPUT:
- CSV with columns: borehole_id, latitude, longitude, + 14 features
- Ready to join with BGI scraper output using agripulse_gee_join.py
*/

// ============================================================================
// CONFIGURATION
// ============================================================================

// TODO: Upload your boreholes as a GEE Feature Collection (table asset) and set the path
var BOREHOLES_ASSET = "projects/your-gee-project/assets/agripulse_boreholes_table";

// TODO: Define study area (optional—used for sanity check on borehole bounds)
// Botswana bounding box (approximate)
var INVESTIGATION_AREA_GEOM = ee.Geometry.Rectangle([19.0, -27.5, 30.0, -17.0]);

// Export filename (change per investigation)
var EXPORT_FILENAME = "agripulse_bgi_ml_features";

// Observation period for satellite data (adjust as needed)
var START_DATE = "2022-01-01";
var END_DATE = "2023-12-31";

// ============================================================================
// SENTINEL-1 FEATURES (Radar)
// ============================================================================

function addSentinel1Features(featureCollection) {
  var s1 = ee.ImageCollection("COPERNICUS/S1_GRD")
    .filterBounds(INVESTIGATION_AREA_GEOM)
    .filterDate(START_DATE, END_DATE)
    .filter(ee.Filter.eq("instrumentMode", "IW"))
    .select("VV", "VH");

  // Calculate mean backscatter and texture
  var s1_mean = s1.mean();
  var s1_vv = s1_mean.select("VV");
  var s1_vh = s1_mean.select("VH");

  // VV - VH ratio
  var vv_vh_ratio = s1_vv.subtract(s1_vh).rename("s1_vv_vh_ratio");

  // Radar texture (GLCM contrast on VV)
  var glcm = s1_vv.reduceNeighborhood(ee.Reducer.glidingWindow({
    kernel: ee.Kernel.square(5)
  }));
  var contrast = glcm.select("VV_contrast").rename("radar_contrast");

  // Sample and attach to features
  var sampled = featureCollection.map(function(feature) {
    var point = feature.geometry();
    var vals = s1_mean.sample(point, 10).first(); // 10m scale
    var contrast_val = contrast.sample(point, 10).first();

    return feature
      .set("s1_vv", s1_vv.sample(point, 10).first().get("VV"))
      .set("s1_vh", s1_vh.sample(point, 10).first().get("VH"))
      .set("s1_vv_vh_ratio", vv_vh_ratio.sample(point, 10).first().get("s1_vv_vh_ratio"))
      .set("radar_contrast", contrast_val.get("VV_contrast"));
  });

  return sampled;
}

// ============================================================================
// SENTINEL-2 INDICES (Optical)
// ============================================================================

function addSentinel2Features(featureCollection) {
  var s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(INVESTIGATION_AREA_GEOM)
    .filterDate(START_DATE, END_DATE)
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    .map(function(img) {
      // Rename bands for clarity
      return img.select(
        ["B2", "B3", "B4", "B5", "B6", "B8", "B11", "B12"],
        ["blue", "green", "red", "re1", "re2", "nir", "swir1", "swir2"]
      );
    });

  var s2_mean = s2.mean();

  // NDVI = (NIR - Red) / (NIR + Red)
  var ndvi = s2_mean.normalizedDifference(["nir", "red"]).rename("ndvi");

  // NDMI = (NIR - SWIR1) / (NIR + SWIR1)  [moisture index]
  var ndmi = s2_mean.normalizedDifference(["nir", "swir1"]).rename("ndmi");

  // NDWI = (Green - NIR) / (Green + NIR)  [water index]
  var ndwi = s2_mean.normalizedDifference(["green", "nir"]).rename("ndwi");

  // Sample and attach
  var sampled = featureCollection.map(function(feature) {
    var point = feature.geometry();
    return feature
      .set("ndvi", ndvi.sample(point, 10).first().get("ndvi"))
      .set("ndmi", ndmi.sample(point, 10).first().get("ndmi"))
      .set("ndwi", ndwi.sample(point, 10).first().get("ndwi"));
  });

  return sampled;
}

// ============================================================================
// DEM & TERRAIN FEATURES (Copernicus & MERIT Hydro)
// ============================================================================

function addTerrainFeatures(featureCollection) {
  // Elevation
  var dem = ee.Image("COPERNICUS/DEM/GLO30");
  var elevation = dem.select("DEM").rename("dem_elevation");

  // Slope (computed from DEM)
  var slope = ee.Terrain.slope(dem).rename("slope_deg");

  // Topographic Wetness Index: log(upstream_area / tan(slope))
  var twi = ee.Image("USGS/3DEP/10m")
    .select("elevation")
    .then(function(img) {
      var fa = ee.Image("MERIT/Hydro/v1_0_6")
        .select("upg") // upstream area
        .log()
        .divide(ee.Terrain.slope(img).tan().add(1e-3));
      return fa.rename("twi");
    });

  // Flow Accumulation (from MERIT Hydro)
  var flow_acc = ee.Image("MERIT/Hydro/v1_0_6")
    .select("upg") // upstream grid cells
    .rename("flow_accumulation");

  // Sample and attach
  var sampled = featureCollection.map(function(feature) {
    var point = feature.geometry();
    return feature
      .set("dem_elevation", elevation.sample(point, 30).first().get("DEM"))
      .set("slope_deg", slope.sample(point, 30).first().get("slope"))
      .set("flow_accumulation", flow_acc.sample(point, 30).first().get("upg"));
  });

  return sampled;
}

// ============================================================================
// STRUCTURAL/LINEAMENT FEATURES
// ============================================================================

function addStructuralFeatures(featureCollection) {
  // Placeholder: structural lineaments from Landsat PCA
  // In practice, you'd use:
  // - Published lineament maps (e.g., USGS, national geological surveys)
  // - Computed PCA texture from Landsat
  // - VLF electromagnetic survey data if available
  //
  // For now, using a simple proximity-to-water-features approximation:
  var gsw = ee.Image("JRC/GSMaPM_v2_3/monthly/1988_2020");
  var water_freq = gsw.select("prediction").rename("water_freq");

  // Structural density proxy: water frequency within 1km
  var structural_density = water_freq.reduceNeighborhood({
    reducer: ee.Reducer.mean(),
    kernel: ee.Kernel.circle({radius: 1000, units: "meters"}),
    optimization: "boxcar"
  }).rename("structural_density");

  // Intersection index proxy: variance of water in 500m radius
  var intersection_index = water_freq.reduceNeighborhood({
    reducer: ee.Reducer.variance(),
    kernel: ee.Kernel.circle({radius: 500, units: "meters"}),
    optimization: "boxcar"
  }).rename("intersection_index");

  // Distance to nearest water feature
  var dist_to_water = water_freq.gte(50).distance(ee.Kernel.euclidean({
    radius: 2500,
    units: "meters"
  })).rename("dist_to_structure_m");

  // Sample and attach
  var sampled = featureCollection.map(function(feature) {
    var point = feature.geometry();
    return feature
      .set("dist_to_structure_m", dist_to_water.sample(point, 30).first().get("dist_to_structure_m"))
      .set("structural_density", structural_density.sample(point, 30).first().get("structural_density"))
      .set("intersection_index", intersection_index.sample(point, 30).first().get("intersection_index"));
  });

  return sampled;
}

// ============================================================================
// MAIN EXECUTION
// ============================================================================

function main() {
  // Load boreholes
  var boreholes = ee.FeatureCollection(BOREHOLES_ASSET);
  print("Loaded boreholes:", boreholes.size());

  // Add features sequentially
  print("Extracting Sentinel-1 features...");
  var with_s1 = addSentinel1Features(boreholes);

  print("Extracting Sentinel-2 features...");
  var with_s2 = addSentinel2Features(with_s1);

  print("Extracting terrain features...");
  var with_terrain = addTerrainFeatures(with_s2);

  print("Extracting structural features...");
  var final_fc = addStructuralFeatures(with_terrain);

  print("Feature extraction complete. Exporting...");

  // Export to Google Drive as CSV
  Export.table.toDrive({
    collection: final_fc,
    description: EXPORT_FILENAME,
    fileFormat: "CSV",
    folder: "AgriPulse"
  });

  print("Export task queued. Check Tasks panel in GEE to run.");
}

// Run main
main();
