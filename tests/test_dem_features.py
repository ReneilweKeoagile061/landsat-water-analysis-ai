"""Slope helper checks (no rasterio / SRTM required)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dem_features import slope_degrees_from_grid, slope_from_point_elevation


def test_flat_grid_has_near_zero_slope():
    elevation = np.full((8, 8), 1000.0)
    transform = SimpleNamespace(a=30.0, e=-30.0)
    slope = slope_degrees_from_grid(elevation, transform)
    assert float(np.max(slope)) < 1e-6


def test_tilted_grid_has_positive_slope():
    y, x = np.mgrid[0:6, 0:6]
    elevation = x * 10.0
    transform = SimpleNamespace(a=30.0, e=-30.0)
    slope = slope_degrees_from_grid(elevation, transform)
    assert float(np.mean(slope)) > 5.0


def test_point_slope_is_finite():
    lat = np.linspace(-20.0, -19.0, 20)
    lon = np.linspace(23.0, 24.0, 20)
    elevation = np.linspace(900.0, 1100.0, 20)
    slope = slope_from_point_elevation(lat, lon, elevation)
    assert slope.shape == (20,)
    assert np.all(np.isfinite(slope))
