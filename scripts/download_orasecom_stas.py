"""
Download critical ORASECOM STAS (Stampriet Transboundary Aquifer System) data files.
Organizes into subfolders matching the source directory structure.

Priority downloads:
  1. Borehole database (XLS - the single most valuable file for ML ground truth)
  2. All WGS84 shapefiles (geology, boreholes, faults, aquifer boundaries, hydraulic params)
  3. Geochemistry data (Botswana, Namibia, South Africa)
  4. Groundwater quality data
  5. Piezometric time-series (water level monitoring)
  6. Abstraction data
  7. GRACE satellite data
  8. Precipitation & evapotranspiration
  9. Cross-section shapefiles and rasters
  10. Key reference maps and reports
"""
import os
import sys
import time
import urllib.request
import urllib.error

BASE = "https://wis.orasecom.org/data_store/other/stas/"
OUT_ROOT = os.path.join("data", "external", "orasecom_stas")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Optional URL overrides for files that have moved or need a corrected path
URL_OVERRIDES = {}

# ---- PRIORITY 1: Borehole database ----
PRIORITY_1_BOREHOLE_DB = {
    "00_borehole_database": [
        "Hydrogeology%20Database/0%20-%20Borehole%20database/STAS_BoreholeDatabase_Clean_25072018.xls",
    ],
}

# ---- PRIORITY 2: WGS84 shapefiles (all components for each shapefile set) ----
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

# ---- PRIORITY 3: Tabular data (geochemistry, water quality, abstraction, climate, GRACE) ----
PRIORITY_3_TABULAR = {
    "02_groundwater_quality": [
        "Hydrogeology%20Database/6%20-%20Groundwater%20quality%20data/Stampriet%20data%20analysis%202010-2015.xls",
        "Hydrogeology%20Database/6%20-%20Groundwater%20quality%20data/Water%20quality%20changes%20in%20the%20SAB.xlsx",
    ],
    "03_abstraction": [
        "Hydrogeology%20Database/10%20-%20Abstraction%20data/Abstraction_File_Revised.xlsx",
    ],
    "04_precipitation_etr": [
        "Hydrogeology%20Database/9%20-%20Precipitation%20and%20evapotranspiration%20data/STAS_Precipitation_ETR.xlsx",
    ],
    "05_grace_satellite": [
        "Hydrogeology%20Database/11%20-%20GRACE%20data/Stampriet%20Aquifer%20System.xlsx",
    ],
    "06_piezometric": [
        "Hydrogeology%20Database/5%20-%20Piezometric%20data/PiezometricData.docx",
        "Hydrogeology%20Database/5%20-%20Piezometric%20data/STAMPRIET%20STATUS%20REPORT%202016.pdf",
    ],
}

# ---- PRIORITY 4: Key reference maps ----
PRIORITY_4_MAPS = {
    "07_reference_maps": [
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/basemap.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/elevation.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/Crosssections.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/landuse.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/rainfall.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/gwl_auob.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/gwl_kalahari.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/gwl_nossob.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/yield_auob.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/yield_kalahari.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/yield_nossob.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/tds_auob.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/tds_kalahari.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/tds_nossob.jpg",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/conceptualmodel_kalahari.pdf",
        "Hydrogeology%20Database/1%20-%20Maps%20(GGRETA%201%20report)/conceptualmodel_auobnossob.pdf",
    ],
}


import argparse

def retry_failed():
    """Retry downloading files listed in failed_files.txt"""
    failed_path = os.path.join(OUT_ROOT, "failed_files.txt")
    if not os.path.exists(failed_path):
        print("No failed_files.txt found; nothing to retry.")
        return 0, 0
    ok, fail = 0, 0
    with open(failed_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rel_url, local_path = line.split("\t")
            # Ensure parent directory exists (should already)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            # Attempt download using existing download_file logic
            if download_file(rel_url, local_path):
                ok += 1
            else:
                fail += 1
    # Overwrite failed_files.txt with any still-failing entries
    if fail > 0:
        with open(failed_path, "w", encoding="utf-8") as f:
            for line in open(failed_path, "r", encoding="utf-8"):
                if line.strip():
                    f.write(line)
    else:
        os.remove(failed_path)
    print(f"\n  Retry mode complete: {ok} OK, {fail} failed")
    return ok, fail


def download_batch(category_dict, label):
    """Download all files in a category dict."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    
    total = sum(len(v) for v in category_dict.values())
    ok = 0
    fail = 0
    
    for subfolder, urls in category_dict.items():
        local_dir = os.path.join(OUT_ROOT, subfolder)
        print(f"\n  -> {subfolder}/")
        
        for rel_url in urls:
            filename = urllib.request.url2pathname(rel_url.split("/")[-1])
            local_path = os.path.join(local_dir, filename)
            
            if download_file(rel_url, local_path):
                ok += 1
            else:
                fail += 1
            
            time.sleep(0.3)  # Respectful rate limiting
    
    print(f"\n  {label} complete: {ok}/{total} OK, {fail} failed")
    return ok, fail


def main():
    print("=" * 60)
    print("  ORASECOM STAS Data Acquisition")
    print("  Stampriet Transboundary Aquifer System")
    print("  Source: https://wis.orasecom.org/data_store/other/stas/")
    print("=" * 60)
    
    grand_ok = 0
    grand_fail = 0
    
    for batch, label in [
        (PRIORITY_1_BOREHOLE_DB, "PRIORITY 1: Borehole Database (ML Ground Truth)"),
        (PRIORITY_2_SHAPEFILES_WGS84, "PRIORITY 2: WGS84 Shapefiles (Geology, Faults, Boreholes)"),
        (PRIORITY_3_TABULAR, "PRIORITY 3: Tabular Data (Quality, Abstraction, Climate, GRACE)"),
        (PRIORITY_4_MAPS, "PRIORITY 4: Reference Maps & Conceptual Models"),
    ]:
        ok, fail = download_batch(batch, label)
        grand_ok += ok
        grand_fail += fail
    
    print(f"\n{'='*60}")
    print(f"  DOWNLOAD COMPLETE")
    print(f"  Total: {grand_ok + grand_fail} files, {grand_ok} OK, {grand_fail} failed")
    print(f"  Output: {os.path.abspath(OUT_ROOT)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
