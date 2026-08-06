"""Assemble the analysis table for one city.

Grid cell -> terrain metrics + crime counts by class + block-group SES.

Written city-agnostic on purpose. The unit of analysis is a fixed-size grid
rather than a street segment because street centreline files are not uniformly
available across US cities, while a DEM and a grid are. Segment-level analysis
stays available in cities (like San Francisco) that publish a CNN on each
incident, and is the natural robustness check.
"""
from __future__ import annotations

import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, os.path.dirname(__file__))
import terrain as T
from acs import block_groups
from crime_classes import classify

CELL_M = 100          # grid resolution
WATER_CUTOFF = -5.0   # below this the DEM is bay/ocean fill, not land
BG_SHP = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_{st}_bg_500k.zip"


def load_dem(path):
    with rasterio.open(path) as src:
        z = src.read(1).astype(np.float32)
        return z, src.transform, src.crs, abs(src.transform.a)


def terrain_stack(z, valid, cell):
    """All the "what does higher mean" metrics, at every radius."""
    out = {"elev": np.where(valid, z, np.nan).astype(np.float32)}
    out["slope_deg"] = np.where(valid, T.slope_degrees(z, cell), np.nan).astype(np.float32)
    for r in T.RADII_M:
        print(f"    radius {r} m", flush=True)
        out[f"tpi_{r}"] = T.tpi(z, valid, r, cell)
        out[f"tpiz_{r}"] = T.tpi_standardized(z, valid, r, cell)
        out[f"pctl_{r}"] = np.where(valid, T.elevation_percentile(z, valid, r, cell), np.nan)
        out[f"relief_{r}"] = T.local_relief(z, valid, r, cell)

    # Directional round-trip costs. Same terrain, priced for three different
    # loads, which is what lets approach cost and escape cost be separated.
    for label, kg in (("light", 0.3), ("mid", 5.0), ("heavy", 20.0)):
        print(f"    round-trip cost, {kg} kg load", flush=True)
        out[f"rtc_{label}"] = T.round_trip_cost(z, valid, cell, 500.0, kg)
    out["loot_penalty"] = out["rtc_heavy"] - out["rtc_light"]
    return out


def to_grid(arr, factor, how="mean"):
    """Block-average a DEM array down to the analysis grid."""
    ny, nx = arr.shape
    ny, nx = (ny // factor) * factor, (nx // factor) * factor
    a = arr[:ny, :nx].reshape(ny // factor, factor, nx // factor, factor)
    with np.errstate(invalid="ignore"):
        return np.nanmean(a, axis=(1, 3)) if how == "mean" else np.nanmax(a, axis=(1, 3))


def build(city, dem_path, crime_path, state_fips, county_fips, out_path):
    print(f"[{city}] DEM", flush=True)
    z, transform, crs, cell = load_dem(dem_path)
    valid = np.isfinite(z) & (z > WATER_CUTOFF)
    print(f"  {valid.mean():.1%} of raster is land; relief {np.nanmin(z[valid]):.0f}"
          f" to {np.nanmax(z[valid]):.0f} m", flush=True)

    print(f"[{city}] terrain metrics", flush=True)
    stack = terrain_stack(z, valid, cell)

    factor = int(round(CELL_M / cell))
    land_frac = to_grid(valid.astype(np.float32), factor)
    gy, gx = land_frac.shape

    grid = {k: to_grid(v, factor).ravel() for k, v in stack.items()}
    df = pd.DataFrame(grid)
    df["land_frac"] = land_frac.ravel()

    # cell centroids in the DEM's projected CRS
    rows, cols = np.divmod(np.arange(gy * gx), gx)
    df["x"] = transform.c + (cols + 0.5) * factor * cell
    df["y"] = transform.f - (rows + 0.5) * factor * cell
    df["row"], df["col"] = rows, cols
    df = df[df["land_frac"] > 0.25].reset_index(drop=True)
    print(f"  {len(df):,} land grid cells", flush=True)

    # --- crime ---
    print(f"[{city}] crime", flush=True)
    cr = pd.read_parquet(crime_path)
    cr = cr.dropna(subset=["latitude", "longitude"])
    pts = gpd.GeoSeries(
        gpd.points_from_xy(cr["longitude"], cr["latitude"]), crs=4326
    ).to_crs(crs)
    cr["x"], cr["y"] = pts.x.values, pts.y.values

    col = ((cr["x"] - transform.c) / (factor * cell)).astype(int)
    row = ((transform.f - cr["y"]) / (factor * cell)).astype(int)
    inb = (row >= 0) & (row < gy) & (col >= 0) & (col < gx)
    cr, row, col = cr[inb], row[inb], col[inb]
    cr["cell"] = (row * gx + col).values
    print(f"  {len(cr):,} incidents inside the raster", flush=True)

    classes = cr["incident_subcategory"].fillna("").map(classify)
    cr["klass"] = [c[0] for c in classes]
    cr["loot_mass"] = [c[1] for c in classes]

    counts = cr.pivot_table(index="cell", columns="klass", aggfunc="size", fill_value=0)
    counts.columns = [f"n_{c}" for c in counts.columns]
    counts["n_total"] = counts.sum(axis=1)

    df["cell"] = df["row"].values * gx + df["col"].values
    df = df.merge(counts, left_on="cell", right_index=True, how="left")
    for c in [c for c in df.columns if c.startswith("n_")]:
        df[c] = df[c].fillna(0).astype(int)

    # --- block-group SES ---
    print(f"[{city}] block groups", flush=True)
    bg = gpd.read_file(BG_SHP.format(st=state_fips)).to_crs(crs)
    cells = gpd.GeoDataFrame(
        df[["cell"]], geometry=gpd.points_from_xy(df["x"], df["y"]), crs=crs
    )
    joined = gpd.sjoin(cells, bg[["GEOID", "ALAND", "geometry"]], how="left", predicate="within")
    joined = joined.drop_duplicates(subset="cell")
    df = df.merge(joined[["cell", "GEOID", "ALAND"]], on="cell", how="left")

    # Clip to the reporting jurisdiction. The DEM bbox is a rectangle and spills
    # into neighbouring counties, which have block groups but are not covered by
    # this city's crime feed; leaving them in would read as thousands of
    # zero-crime cells. Cartographic block-group boundaries are coastline-
    # clipped, so requiring a match also drops open water.
    before = len(df)
    df = df[df["GEOID"].notna() & df["GEOID"].str.startswith(tuple(county_fips))]
    df = df.reset_index(drop=True)
    print(f"  clipped to jurisdiction: {before:,} -> {len(df):,} cells", flush=True)

    ses = block_groups()
    df = df.merge(ses, on="GEOID", how="left")

    # exposure: housing units apportioned by area, so counts become rates
    cell_area = (CELL_M ** 2) * df["land_frac"]
    df["housing_units_cell"] = df["housing_units"] * cell_area / df["ALAND"].replace(0, np.nan)
    df["pop_cell"] = df["population"] * cell_area / df["ALAND"].replace(0, np.nan)
    df["city"] = city

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_parquet(out_path, index=False)
    print(f"[{city}] wrote {out_path}  ({len(df):,} cells)", flush=True)
    return df


if __name__ == "__main__":
    build(
        city="San Francisco",
        dem_path="data/raw/sf_dem_10m.tif",
        crime_path="data/raw/sf_property_crime.parquet",
        state_fips="06",
        county_fips=["06075"],  # San Francisco County = the SFPD reporting area
        out_path="data/interim/sf_cells.parquet",
    )
