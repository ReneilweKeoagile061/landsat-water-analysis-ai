# List missing shapefile components from the ORASECOM STAS download
import os
import urllib.parse

BASE = "https://wis.orasecom.org/data_store/other/stas/"
OUT_ROOT = os.path.join("data", "external", "orasecom_stas")

# Subset of the PRIORITY_2 dictionary (full list needed for accurate reporting).
# For brevity we include all entries that were defined in download_orasecom_stas.py.
PRIORITY_2_SHAPEFILES_WGS84 = {
    "01_shapefiles_wgs84/01_aquifer_boundaries": [
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/01%20-%20Aquifer%20boundaries/STAS_boundaries.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/01%20-%20Aquifer%20boundaries/STAS_boundaries.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/01%20-%20Aquifer%20boundaries/STAS_boundaries.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/01%20-%20Aquifer%20boundaries/STAS_boundaries.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/01%20-%20Aquifer%20boundaries/STAS_boundaries.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/01%20-%20Aquifer%20boundaries/STAS_boundaries.shx",
    ],
    "01_shapefiles_wgs84/02_boreholes": [
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/02%20-%20Boreholes/Boreholes.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/02%20-%20Boreholes/Boreholes.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/02%20-%20Boreholes/Boreholes.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/02%20-%20Boreholes/Boreholes.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/02%20-%20Boreholes/Boreholes.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/02%20-%20Boreholes/Boreholes.shx",
    ],
    "01_shapefiles_wgs84/03_country_boundaries": [
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/03%20-%20Country%20boundaries/Country_boundaries.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/03%20-%20Country%20boundaries/Country_boundaries.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/03%20-%20Country%20boundaries/Country_boundaries.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/03%20-%20Country%20boundaries/Country_boundaries.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/03%20-%20Country%20boundaries/Country_boundaries.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/03%20-%20Country%20boundaries/Country_boundaries.shx",
    ],
    "01_shapefiles_wgs84/04_cross_sections": [
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/04%20-%20Cross%20sections/Cross_sections.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/04%20-%20Cross%20sections/Cross_sections.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/04%20-%20Cross%20sections/Cross_sections.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/04%20-%20Cross%20sections/Cross_sections.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/04%20-%20Cross%20sections/Cross_sections.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/04%20-%20Cross%20sections/Cross_sections.shx",
    ],
    "01_shapefiles_wgs84/05_geological_units": [
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/05%20-%20Geological%20units/Geological_units.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/05%20-%20Geological%20units/Geological_units.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/05%20-%20Geological%20units/Geological_units.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/05%20-%20Geological%20units/Geological_units.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/05%20-%20Geological%20units/Geological_units.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/05%20-%20Geological%20units/Geological_units.shx",
    ],
    "01_shapefiles_wgs84/06_faults": [
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/06%20-%20Faults/Faults.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/06%20-%20Faults/Faults.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/06%20-%20Faults/Faults.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/06%20-%20Faults/Faults.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/06%20-%20Faults/Faults.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/06%20-%20Faults/Faults.shx",
    ],
    "01_shapefiles_wgs84/07_piezometric_boreholes": [
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/07%20-%20Piezometric%20boreholes/Piezometric_boreholes.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/07%20-%20Piezometric%20boreholes/Piezometric_boreholes.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/07%20-%20Piezometric%20boreholes/Piezometric_boreholes.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/07%20-%20Piezometric%20boreholes/Piezometric_boreholes.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/07%20-%20Piezometric%20boreholes/Piezometric_boreholes.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/07%20-%20Piezometric%20boreholes/Piezometric_boreholes.shx",
    ],
    "01_shapefiles_wgs84/08_rivers": [
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/08%20-%20Rivers/Rivers.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/08%20-%20Rivers/Rivers.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/08%20-%20Rivers/Rivers.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/08%20-%20Rivers/Rivers.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/08%20-%20Rivers/Rivers.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/08%20-%20Rivers/Rivers.shx",
    ],
    "01_shapefiles_wgs84/09_towns": [
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/09%20-%20Towns/Towns.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/09%20-%20Towns/Towns.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/09%20-%20Towns/Towns.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/09%20-%20Towns/Towns.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/09%20-%20Towns/Towns.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/09%20-%20Towns/Towns.shx",
    ],
    "01_shapefiles_wgs84/10_hydraulic_parameters": [
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Auob_hydraulic_parameter_and_thickness_points.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Auob_hydraulic_parameter_and_thickness_points.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Auob_hydraulic_parameter_and_thickness_points.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Auob_hydraulic_parameter_and_thickness_points.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Auob_hydraulic_parameter_and_thickness_points.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Auob_hydraulic_parameter_and_thickness_points.shx",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Kalahari_hydraulic_parameter_and_thickness_points.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Kalahari_hydraulic_parameter_and_thickness_points.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Kalahari_hydraulic_parameter_and_thickness_points.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Kalahari_hydraulic_parameter_and_thickness_points.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Kalahari_hydraulic_parameter_and_thickness_points.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Kalahari_hydraulic_parameter_and_thickness_points.shx",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Nossob_hydraulic_parameter_and_thickness_points.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Nossob_hydraulic_parameter_and_thickness_points.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Nossob_hydraulic_parameter_and_thickness_points.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Nossob_hydraulic_parameter_and_thickness_points.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Nossob_hydraulic_parameter_and_thickness_points.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/10%20-%20Hydraulic%20parameters/Nossob_hydraulic_parameter_and_thickness_points.shx",
    ],
    "01_shapefiles_wgs84/11_groundwater_quality": [
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/11%20-%20Groundwater%20quality/Groundwater_quality.cpg",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/11%20-%20Groundwater%20quality/Groundwater_quality.dbf",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/11%20-%20Groundwater%20quality/Groundwater_quality.prj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/11%20-%20Groundwater%20quality/Groundwater_quality.qpj",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/11%20-%20Groundwater%20quality/Groundwater_quality.shp",
        "Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/11%20-%20Groundwater%20quality/Groundwater_quality.shx",
    ],
}

failed = []
for subfolder, rel_urls in PRIORITY_2_SHAPEFILES_WGS84.items():
    local_dir = os.path.join(OUT_ROOT, subfolder)
    for rel in rel_urls:
        filename = urllib.parse.unquote(rel.split('/')[-1])
        local_path = os.path.join(local_dir, filename)
        if not os.path.exists(local_path):
            failed.append((BASE + rel, local_path))

print(f"Failed files: {len(failed)}")
for remote, local in failed:
    print(f"{remote}  →  {local}")
