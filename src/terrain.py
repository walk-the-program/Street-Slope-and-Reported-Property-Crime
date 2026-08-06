"""Terrain metrics: the "how do you define higher?" ladder.

City-agnostic. Everything takes a projected DEM array (metres, square pixels)
plus a validity mask, and returns arrays of the same shape.

Neighbourhood statistics use disk kernels evaluated by FFT convolution, with a
matching convolution of the validity mask as the denominator. That is what makes
edges and water bodies behave: a cell on the coast is compared against the land
around it, not against a pile of implicit zeros.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import maximum_filter, minimum_filter
from scipy.signal import fftconvolve
from scipy.special import ndtr


def disk_kernel(radius_px: float) -> np.ndarray:
    r = int(np.ceil(radius_px))
    y, x = np.ogrid[-r : r + 1, -r : r + 1]
    return ((x * x + y * y) <= radius_px * radius_px).astype(np.float32)


def _local_moments(z: np.ndarray, valid: np.ndarray, kernel: np.ndarray):
    """Neighbourhood mean and std, ignoring invalid cells."""
    zf = np.where(valid, z, 0.0).astype(np.float32)
    vf = valid.astype(np.float32)
    n = fftconvolve(vf, kernel, mode="same")
    s1 = fftconvolve(zf, kernel, mode="same")
    s2 = fftconvolve(zf * zf, kernel, mode="same")
    n = np.maximum(n, 1e-6)
    mean = s1 / n
    var = np.maximum(s2 / n - mean * mean, 0.0)
    return mean, np.sqrt(var), n


def tpi(z, valid, radius_m, cellsize):
    """Topographic Position Index: elevation minus the local mean (Weiss 2001).

    Positive = higher than surroundings. This is the core "relative height".
    """
    mean, _, n = _local_moments(z, valid, disk_kernel(radius_m / cellsize))
    out = np.where(valid & (n > 3), z - mean, np.nan)
    return out.astype(np.float32)


def tpi_standardized(z, valid, radius_m, cellsize):
    """TPI divided by local relief std.

    Makes "how much higher" comparable between a gentle city and a rugged one,
    which is what lets cities be pooled at all.
    """
    mean, std, n = _local_moments(z, valid, disk_kernel(radius_m / cellsize))
    out = np.where(valid & (n > 3) & (std > 1e-3), (z - mean) / np.maximum(std, 1e-3), np.nan)
    return out.astype(np.float32)


def elevation_percentile(z, valid, radius_m, cellsize):
    """Approximate share of nearby land lower than this cell, in [0, 1].

    Gaussian approximation to the local rank (normal CDF of the standardized
    TPI). Exact local ranking over a 400-cell radius is far more expensive and
    the approximation tracks it closely for the unimodal elevation
    distributions found inside a city. Scale-free and reads plainly:
    "higher than 94% of land within 500 m".
    """
    zs = tpi_standardized(z, valid, radius_m, cellsize)
    return ndtr(zs).astype(np.float32)


def local_relief(z, valid, radius_m, cellsize):
    """Neighbourhood max minus min: "hilliness" of the area around a cell.

    Distinct from TPI. This is Kim & Wo's dominant predictor, and it describes
    the terrain rather than the cell's position in it, so carry both.

    Uses a square window rather than a disk. A disk footprint is not separable,
    so at a 2 km radius the rank filter costs ~10^5 comparisons per cell; the
    square version is separable and runs in linear time. The two agree closely
    because a max over a slightly larger region rarely differs.
    """
    k = 2 * int(np.ceil(radius_m / cellsize)) + 1
    hi = maximum_filter(np.where(valid, z, -9e9), size=k, mode="nearest")
    lo = minimum_filter(np.where(valid, z, 9e9), size=k, mode="nearest")
    out = np.where(valid, hi - lo, np.nan)
    return np.where(np.abs(out) > 1e8, np.nan, out).astype(np.float32)


def slope_degrees(z, cellsize):
    """Slope via Horn's method, the standard 3x3 kernel."""
    gy, gx = np.gradient(z.astype(np.float64), cellsize, cellsize)
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)


def hillshade(z, cellsize, azimuth=315.0, altitude=45.0, zfactor=1.5):
    """Standard analytical hillshade, for use as a basemap."""
    gy, gx = np.gradient(z.astype(np.float64) * zfactor, cellsize, cellsize)
    slope = np.pi / 2.0 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az = np.radians(360.0 - azimuth + 90.0)
    alt = np.radians(altitude)
    shaded = np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect)
    return np.clip(shaded, 0, 1).astype(np.float32)


# --- Effort ---------------------------------------------------------------
# Metabolic cost of walking a gradient. These turn "higher" into "expensive to
# reach", which is the variable the hypothesis is actually about.

def minetti_cost(gradient: np.ndarray) -> np.ndarray:
    """Metabolic cost of walking, J/(kg*m), as a function of gradient.

    Herzog's (2013) 6th-degree polynomial fit to Minetti et al. (2002). The
    polynomial form is used because raw Minetti goes unphysically negative on
    steep descents. Valid roughly over gradients of -0.5 to +0.5.
    """
    g = np.clip(gradient, -0.5, 0.5)
    return (
        1337.8 * g**6
        + 278.19 * g**5
        - 517.39 * g**4
        - 78.199 * g**3
        + 93.419 * g**2
        + 19.825 * g
        + 1.64
    )


def tobler_speed(gradient: np.ndarray) -> np.ndarray:
    """Tobler's hiking function, km/h. Asymmetric: fastest on a slight decline."""
    return 6.0 * np.exp(-3.5 * np.abs(gradient + 0.05))


def vertical_work_kj(delta_h_m: float, mass_kg: float = 75.0) -> float:
    """Gross potential energy to lift a body a given height, in kJ.

    Only the against-gravity term, so it is a floor on true cost, but it makes
    the finding sayable: one storey is about 2 kJ.
    """
    return mass_kg * 9.81 * max(delta_h_m, 0.0) / 1000.0


RADII_M = [50, 100, 250, 500, 1000, 2000]


# --- Directional, load-dependent movement cost -----------------------------
# The core of the asymmetry argument. A property offender makes a round trip:
# in empty-handed, out carrying goods. Metabolic cost is strongly asymmetric in
# gradient, so those two legs price a hill in opposite directions, and the
# balance between them depends on how heavy the goods are.
#
# For a target x and a surrounding origin j:
#     approach  j -> x   at gradient +g, body mass only
#     escape    x -> j   at gradient -g, body mass + loot
# where g = (z(x) - z(j)) / distance.
#
# Cost is integrated over a ring-and-spoke quadrature of the catchment disk
# rather than a full pixel neighbourhood; a 500 m disk at 10 m holds ~7,900
# offsets, which is intractable, while 48 directions x 6 rings reproduces the
# integral closely at 288.

def _shift(a, dy, dx):
    out = np.full_like(a, np.nan, dtype=np.float32)
    ys = slice(max(dy, 0), a.shape[0] + min(dy, 0))
    xs = slice(max(dx, 0), a.shape[1] + min(dx, 0))
    yd = slice(max(-dy, 0), a.shape[0] + min(-dy, 0))
    xd = slice(max(-dx, 0), a.shape[1] + min(-dx, 0))
    out[ys, xs] = a[yd, xd]
    return out


def round_trip_cost(z, valid, cellsize, radius_m, loot_kg,
                    body_kg=75.0, n_dirs=48, n_rings=6, decay_m=None):
    """Mean metabolic cost of a round trip to x, in J/kg-equivalent per trip.

    Returns approach + loaded-escape cost averaged over the catchment. Higher
    means the location is expensive to rob and get away from with `loot_kg`.
    """
    zf = np.where(valid, z, np.nan).astype(np.float32)
    total = np.zeros(z.shape, np.float32)
    wsum = np.zeros(z.shape, np.float32)
    load = (body_kg + loot_kg) / body_kg

    for ring in range(1, n_rings + 1):
        R = radius_m * ring / n_rings
        ring_w = R  # disk area element, r dr
        if decay_m:
            ring_w *= np.exp(-R / decay_m)
        for k in range(n_dirs):
            th = 2 * np.pi * k / n_dirs
            dx = int(round(R * np.cos(th) / cellsize))
            dy = int(round(R * np.sin(th) / cellsize))
            if dx == 0 and dy == 0:
                continue
            d = float(np.hypot(dx * cellsize, dy * cellsize))
            zj = _shift(zf, dy, dx)
            g = (zf - zj) / d                    # + means x sits above origin j
            approach = minetti_cost(g)           # in, unloaded, against +g
            escape = minetti_cost(-g) * load     # out, loaded, along -g
            c = (approach + escape) * d
            ok = np.isfinite(c)
            total[ok] += (c * ring_w)[ok]
            wsum[ok] += ring_w
    out = np.where((wsum > 0) & valid, total / np.maximum(wsum, 1e-9), np.nan)
    return out.astype(np.float32)


def loot_penalty(z, valid, cellsize, radius_m, heavy_kg=20.0, light_kg=0.3, **kw):
    """Extra round-trip cost of heavy loot versus pocketable loot.

    This is the variable the whole argument turns on. It is the price of
    *removing weight* from a location, stripped of the approach cost that
    applies equally to both. It should be low on high ground (roll downhill
    with the goods) and high in hollows (haul them out).

    Under the standard reading of this literature it should not predict
    anything at all, because that reading has no escape term.
    """
    return (round_trip_cost(z, valid, cellsize, radius_m, heavy_kg, **kw)
            - round_trip_cost(z, valid, cellsize, radius_m, light_kg, **kw))
