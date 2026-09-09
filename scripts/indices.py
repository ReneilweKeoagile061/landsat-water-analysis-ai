"""Spectral water indices used by the Landsat pipeline.

Formulas match the notebook feature-extraction cell (McFeeters NDWI, Xu MNDWI).
"""

from __future__ import annotations

import numpy as np

EPS = 1e-8


def safe_div(numerator, denominator):
    num = np.asarray(numerator, dtype=np.float64)
    den = np.asarray(denominator, dtype=np.float64)
    return num / np.where(np.abs(den) < EPS, EPS, den)


def ndwi(green, nir):
    """Normalized Difference Water Index (McFeeters 1996)."""
    green = np.asarray(green, dtype=np.float64)
    nir = np.asarray(nir, dtype=np.float64)
    return safe_div(green - nir, green + nir)


def mndwi(green, swir1):
    """Modified NDWI (Xu 2006)."""
    green = np.asarray(green, dtype=np.float64)
    swir1 = np.asarray(swir1, dtype=np.float64)
    return safe_div(green - swir1, green + swir1)


def ndvi(nir, red):
    nir = np.asarray(nir, dtype=np.float64)
    red = np.asarray(red, dtype=np.float64)
    return safe_div(nir - red, nir + red)


def ndmi(nir, swir1):
    nir = np.asarray(nir, dtype=np.float64)
    swir1 = np.asarray(swir1, dtype=np.float64)
    return safe_div(nir - swir1, nir + swir1)


def awei_nsh(green, swir1, nir, swir2):
    green = np.asarray(green, dtype=np.float64)
    swir1 = np.asarray(swir1, dtype=np.float64)
    nir = np.asarray(nir, dtype=np.float64)
    swir2 = np.asarray(swir2, dtype=np.float64)
    return 4.0 * (green - swir1) - 0.25 * nir - 2.75 * swir2


def clip_index(values, lo=-1.0, hi=1.0):
    return np.clip(np.asarray(values, dtype=np.float64), lo, hi)


def rule_based_labels(ndwi_values, low_max: float = 0.0, high_min: float = 0.3) -> np.ndarray:
    """Independent NDWI thresholds (physical screening, not cluster labels)."""
    values = np.asarray(ndwi_values, dtype=np.float64)
    labels = np.ones(values.shape, dtype=int)
    labels[values < low_max] = 0
    labels[values > high_min] = 2
    return labels
