"""DEM / slope features sampled onto Landsat point frames.

Elevation is expected in metres (SRTM / Copernicus DEM). Slope is returned in
degrees. Point sampling uses rasterio when a DEM path is provided; otherwise a
local finite-difference slope can be computed from a regular elevation grid.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

EARTH_RADIUS_M = 6371000.0


def slope_degrees_from_grid(elevation: np.ndarray, transform) -> np.ndarray:
    """Slope in degrees from a 2-D elevation array.

    ``transform`` is a GDAL-style affine (pixel size in metres or degrees).
    If ``transform.a`` looks like degrees (abs < 1), pixel size is converted
    using a mid-latitude approximation of 111_320 m/deg.
    """
    z = np.asarray(elevation, dtype=np.float64)
    dy, dx = np.gradient(z)

    pix_x = abs(float(transform.a))
    pix_y = abs(float(transform.e))
    if pix_x < 1.0:
        pix_x *= 111_320.0
        pix_y *= 111_320.0

    slope_rad = np.arctan(np.hypot(dx / pix_x, dy / pix_y))
    return np.degrees(slope_rad)


def point_spacing_m(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Approximate east/north spacing between consecutive sorted samples."""
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    dlat = np.gradient(lat)
    dlon = np.gradient(lon)
    north = dlat * (math.pi / 180.0) * EARTH_RADIUS_M
    east = dlon * (math.pi / 180.0) * EARTH_RADIUS_M * np.cos(np.deg2rad(lat))
    east = np.where(np.abs(east) < 1.0, 1.0, east)
    north = np.where(np.abs(north) < 1.0, 1.0, north)
    return east, north


def slope_from_point_elevation(lat, lon, elevation) -> np.ndarray:
    """Rough slope (degrees) from scattered points using coordinate gradients."""
    z = np.asarray(elevation, dtype=np.float64)
    east, north = point_spacing_m(lat, lon)
    dz_east = np.gradient(z) / east
    dz_north = np.gradient(z) / north
    return np.degrees(np.arctan(np.hypot(dz_east, dz_north)))


def attach_slope_column(df: pd.DataFrame, elevation_col: str = "elevation") -> pd.DataFrame:
    work = df.copy()
    lat_col = "lat_wgs84" if "lat_wgs84" in work.columns else "lat"
    lon_col = "lon_wgs84" if "lon_wgs84" in work.columns else "lon"
    work["slope"] = slope_from_point_elevation(
        work[lat_col].to_numpy(),
        work[lon_col].to_numpy(),
        work[elevation_col].to_numpy(),
    )
    return work


def sample_dem(lons, lats, dem_path: str | Path) -> np.ndarray:
    """Sample a DEM raster at WGS84 points. Requires rasterio."""
    try:
        import rasterio
        from rasterio.warp import transform as warp_transform
    except ImportError as exc:
        raise ImportError("rasterio is required to sample DEM tiles") from exc

    lons = np.asarray(lons, dtype=np.float64)
    lats = np.asarray(lats, dtype=np.float64)
    with rasterio.open(dem_path) as src:
        xs, ys = lons, lats
        if src.crs and src.crs.to_string() not in ("EPSG:4326", "OGC:CRS84"):
            xs, ys = warp_transform("EPSG:4326", src.crs, list(lons), list(lats))
        values = np.array(list(src.sample(zip(xs, ys))), dtype=np.float64).reshape(-1)
        nodata = src.nodata
        if nodata is not None:
            values = np.where(values == nodata, np.nan, values)
    return values


FEATURE_COLUMNS = [
    "ndwi",
    "mndwi",
    "awei_nsh",
    "awei_sh",
    "ndvi",
    "evi",
    "ndmi",
    "lswi",
    "wri",
    "moisture_ratio",
    "water_score_norm",
    "slope",
]
