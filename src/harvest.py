"""Run the whole pipeline over every city in the registry.

Per city: pull incidents -> robust bounding box -> fetch a 3DEP DEM for that box
-> terrain metrics -> grid -> join block-group SES -> write an analysis table.

Cities are independent, so a failure is logged and skipped rather than fatal.
"""
from __future__ import annotations

import io
import os
import sys
import time
import traceback

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.transform import from_origin

sys.path.insert(0, os.path.dirname(__file__))
import terrain as T
from acs import block_groups
from crime_classes import PROPERTY_CLASSES, classify_text

REGISTRY = "data/interim/registry.csv"
CELL_M = 100
DEM_RES = 10.0
MAX_TILE_PX = 2000
START_DATE = "2018-01-01"
MAX_ROWS = 600_000
ELEV_URL = ("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation"
            "/ImageServer/exportImage")
COUNTY_SHP = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip"
BG_SHP = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_{st}_bg_500k.zip"


# ---------------------------------------------------------------- crime ----
def fetch_crime(row, property_only=True):
    """Incidents for one Socrata city, classified.

    `property_only=False` keeps OTHER and ROBBERY. The grid pipeline never wants
    them, but the segment tables carry `n_OTHER`/`n_ROBBERY` so that the class
    distribution can be read as a share of everything the department reported,
    not as a share of what we already decided to keep.
    """
    base = f"https://{row.domain}/resource/{row.id}.json"
    la, lo, dt, ds = row.lat_col, row.lon_col, row.date_col, row.desc_col
    descs = [c for c in str(row.all_desc).split(";") if c][:3]
    sel = ",".join(dict.fromkeys([dt, la, lo] + descs))
    where = f"{la} IS NOT NULL AND {lo} IS NOT NULL AND {dt} >= '{START_DATE}T00:00:00'"

    frames, offset, page = [], 0, 50_000
    while offset < MAX_ROWS:
        # Newest first. Big cities are capped at MAX_ROWS, and taking the most
        # recent window keeps the panel roughly contemporaneous instead of
        # leaving Chicago stuck in 2018-2020 while smaller cities run to 2026.
        r = requests.get(base, params={"$select": sel, "$where": where,
                                       "$order": f"{dt} DESC", "$limit": page,
                                       "$offset": offset},
                         timeout=300)
        if r.status_code != 200:
            if offset == 0:
                raise RuntimeError(f"crime {r.status_code}: {r.text[:120]}")
            break
        chunk = pd.DataFrame(r.json())
        if chunk.empty:
            break
        frames.append(chunk)
        offset += page
        if len(chunk) < page:
            break
        time.sleep(0.2)
    if not frames:
        raise RuntimeError("no rows")

    df = pd.concat(frames, ignore_index=True)
    df["lat"] = pd.to_numeric(df[la], errors="coerce")
    df["lon"] = pd.to_numeric(df[lo], errors="coerce")
    df = df[df.lat.between(-90, 90) & df.lon.between(-180, 180)]
    df = df[(df.lat != 0) & (df.lon != 0)]

    # Drop null sentinels. Testing only for exact zero is not enough: Seattle
    # marks missing coordinates with values near -1, which survived that check
    # and dragged the bounding box from latitude 47.5 down to -1. Anchoring on
    # the median and keeping a generous window around it removes sentinels of
    # any flavour without assuming what they are, and is safe because a single
    # agency's incidents always sit inside a degree or so of their own centre.
    mla, mlo = df.lat.median(), df.lon.median()
    df = df[(df.lat - mla).abs().le(1.0) & (df.lon - mlo).abs().le(1.5)].copy()

    # fillna before astype: on pandas 3 `astype(str)` keeps NaN as NaN rather
    # than writing "nan", so a single null description column propagates through
    # the concatenation and sends the entire row to OTHER. Cincinnati publishes
    # its NIBRS sub-code only on thefts, which silently emptied every other
    # class in that city.
    text = df[descs[0]].fillna("").astype(str)
    for c in descs[1:]:
        text = text + " " + df[c].fillna("").astype(str)
    kl = text.map(classify_text)
    df["klass"] = [k[0] for k in kl]
    df["loot_mass"] = [k[1] for k in kl]
    if not property_only:
        return df.copy()
    return df[df.klass.isin(PROPERTY_CLASSES)].copy()


def robust_bbox(df, pad_m=1500):
    la = np.percentile(df.lat, [0.3, 99.7])
    lo = np.percentile(df.lon, [0.3, 99.7])
    padlat = pad_m / 111_000.0
    padlon = pad_m / (111_000.0 * np.cos(np.radians(la.mean())))
    return (lo[0] - padlon, la[0] - padlat, lo[1] + padlon, la[1] + padlat)


# ------------------------------------------------------------------ DEM ----
def utm_epsg(lon, lat):
    zone = int((lon + 180) // 6) + 1
    return 32600 + zone if lat >= 0 else 32700 + zone


def fetch_dem(bbox_ll, epsg, path):
    """Fetch a 3DEP DEM, tiling when the request would be too large.

    The ImageServer caps a single export, and a big city at 10 m easily exceeds
    it, so the extent is split into tiles and mosaicked. Resolution is held
    fixed at 10 m across every city -- letting it float would make the terrain
    metrics mean different things in different places, which is fatal for a
    cross-city comparison.
    """
    if os.path.exists(path):
        return path
    tr = gpd.GeoSeries(gpd.points_from_xy([bbox_ll[0], bbox_ll[2]],
                                          [bbox_ll[1], bbox_ll[3]]), crs=4326).to_crs(epsg)
    x0, x1 = float(tr.x.min()), float(tr.x.max())
    y0, y1 = float(tr.y.min()), float(tr.y.max())
    nx = int(np.ceil((x1 - x0) / DEM_RES))
    ny = int(np.ceil((y1 - y0) / DEM_RES))

    tx = int(np.ceil(nx / MAX_TILE_PX))
    ty = int(np.ceil(ny / MAX_TILE_PX))
    mosaic = np.full((ny, nx), np.nan, dtype=np.float32)

    for j in range(ty):
        for i in range(tx):
            c0, c1 = i * MAX_TILE_PX, min((i + 1) * MAX_TILE_PX, nx)
            r0, r1 = j * MAX_TILE_PX, min((j + 1) * MAX_TILE_PX, ny)
            bx0 = x0 + c0 * DEM_RES
            bx1 = x0 + c1 * DEM_RES
            by1 = y1 - r0 * DEM_RES
            by0 = y1 - r1 * DEM_RES
            params = {"bbox": f"{bx0},{by0},{bx1},{by1}", "bboxSR": epsg,
                      "size": f"{c1-c0},{r1-r0}", "imageSR": epsg, "format": "tiff",
                      "pixelType": "F32", "interpolation": "RSP_BilinearInterpolation",
                      "noDataInterpretation": "esriNoDataMatchAny", "f": "image"}
            for attempt in range(3):
                try:
                    resp = requests.get(ELEV_URL, params=params, timeout=420)
                    if resp.status_code == 200 and resp.content[:2] in (b"II", b"MM"):
                        with rasterio.open(io.BytesIO(resp.content)) as s:
                            mosaic[r0:r1, c0:c1] = s.read(1)[: r1 - r0, : c1 - c0]
                        break
                except Exception:
                    pass
                time.sleep(3)

    prof = {"driver": "GTiff", "height": ny, "width": nx, "count": 1,
            "dtype": "float32", "crs": f"EPSG:{epsg}",
            "transform": from_origin(x0, y1, DEM_RES, DEM_RES), "compress": "deflate"}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(mosaic, 1)
    return path


# ----------------------------------------------------------------- build ----
def to_grid(arr, f):
    ny, nx = arr.shape
    ny, nx = (ny // f) * f, (nx // f) * f
    a = arr[:ny, :nx].reshape(ny // f, f, nx // f, f)
    with np.errstate(invalid="ignore"):
        return np.nanmean(a, axis=(1, 3))


_COUNTIES = None


def counties():
    global _COUNTIES
    if _COUNTIES is None:
        _COUNTIES = gpd.read_file(COUNTY_SHP)[["GEOID", "STATEFP", "geometry"]]
    return _COUNTIES


def build_city(city, crime, dem_path, epsg, out_path):
    with rasterio.open(dem_path) as src:
        z = src.read(1).astype(np.float32)
        transform, cell = src.transform, abs(src.transform.a)
    valid = np.isfinite(z) & (z > -5) & (z < 5000)
    if valid.mean() < 0.02:
        raise RuntimeError("DEM mostly empty")

    stack = {"elev": np.where(valid, z, np.nan).astype(np.float32),
             "slope_deg": np.where(valid, T.slope_degrees(z, cell), np.nan).astype(np.float32)}
    for r in T.RADII_M:
        stack[f"tpi_{r}"] = T.tpi(z, valid, r, cell)
        stack[f"tpiz_{r}"] = T.tpi_standardized(z, valid, r, cell)
        stack[f"relief_{r}"] = T.local_relief(z, valid, r, cell)

    f = int(round(CELL_M / cell))
    land = to_grid(valid.astype(np.float32), f)
    gy, gx = land.shape
    df = pd.DataFrame({k: to_grid(v, f).ravel() for k, v in stack.items()})
    df["land_frac"] = land.ravel()
    rows, cols = np.divmod(np.arange(gy * gx), gx)
    df["x"] = transform.c + (cols + 0.5) * f * cell
    df["y"] = transform.f - (rows + 0.5) * f * cell
    df["cell"] = np.arange(gy * gx)
    df = df[df.land_frac > 0.25].reset_index(drop=True)

    pts = gpd.GeoSeries(gpd.points_from_xy(crime.lon, crime.lat), crs=4326).to_crs(epsg)
    cx, cy = pts.x.values, pts.y.values
    col = ((cx - transform.c) / (f * cell)).astype(int)
    row = ((transform.f - cy) / (f * cell)).astype(int)
    ok = (row >= 0) & (row < gy) & (col >= 0) & (col < gx)
    cr = crime[ok].copy()
    cr["cell"] = row[ok] * gx + col[ok]

    counts = cr.pivot_table(index="cell", columns="klass", aggfunc="size", fill_value=0)
    counts.columns = [f"n_{c}" for c in counts.columns]
    counts["n_total"] = counts.sum(axis=1)
    df = df.merge(counts, left_on="cell", right_index=True, how="left")
    for c in [c for c in df.columns if c.startswith("n_")]:
        df[c] = df[c].fillna(0).astype(int)

    # jurisdiction = the counties the incidents actually fall in
    cpts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(cr.lon, cr.lat), crs=4326)
    hit = gpd.sjoin(cpts, counties().to_crs(4326), how="inner", predicate="within")
    share = hit["GEOID"].value_counts(normalize=True)
    keep_counties = list(share[share >= 0.02].index)
    states = sorted({c[:2] for c in keep_counties})
    if not states:
        raise RuntimeError("no county match")

    bg = pd.concat([gpd.read_file(BG_SHP.format(st=s)) for s in states], ignore_index=True)
    bg = bg[bg["GEOID"].str[:5].isin(keep_counties)].to_crs(epsg)
    cells = gpd.GeoDataFrame(df[["cell"]], geometry=gpd.points_from_xy(df.x, df.y), crs=epsg)
    j = gpd.sjoin(cells, bg[["GEOID", "ALAND", "geometry"]], how="left",
                  predicate="within").drop_duplicates("cell")
    df = df.merge(j[["cell", "GEOID", "ALAND"]], on="cell", how="left")
    df = df[df.GEOID.notna()].reset_index(drop=True)

    df = df.merge(block_groups(), on="GEOID", how="left")
    area = (CELL_M ** 2) * df.land_frac
    df["housing_units_cell"] = df.housing_units * area / df.ALAND.replace(0, np.nan)
    df["pop_cell"] = df.population * area / df.ALAND.replace(0, np.nan)
    df["city"] = city
    df.to_parquet(out_path, index=False)
    return df


def run_one(row):
    city = row.domain.replace("data.", "").replace(".gov", "").replace(".org", "")
    slug = row.domain.replace(".", "_")
    out = f"data/interim/cells/{slug}.parquet"
    if os.path.exists(out):
        return city, "cached", 0

    crime = fetch_crime(row)
    if len(crime) < 5000:
        raise RuntimeError(f"only {len(crime)} classified property crimes")
    bbox = robust_bbox(crime)
    epsg = utm_epsg((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    dem = fetch_dem(bbox, epsg, f"data/raw/dem/{slug}.tif")
    os.makedirs("data/interim/cells", exist_ok=True)
    df = build_city(city, crime, dem, epsg, out)
    return city, "ok", len(df)


def main():
    reg = pd.read_csv(REGISTRY)
    print(f"{len(reg)} cities in registry\n", flush=True)
    log = []
    for row in reg.itertuples():
        t0 = time.time()
        try:
            city, status, n = run_one(row)
            print(f"  [{status:6s}] {city:34s} {n:7,} cells  ({time.time()-t0:.0f}s)", flush=True)
            log.append({"domain": row.domain, "status": status, "cells": n})
        except Exception as e:
            print(f"  [FAIL  ] {row.domain:34s} {type(e).__name__}: {str(e)[:90]}", flush=True)
            log.append({"domain": row.domain, "status": f"fail: {type(e).__name__}", "cells": 0})
    pd.DataFrame(log).to_csv("data/interim/harvest_log.csv", index=False)
    ok = sum(1 for r in log if r["status"] in ("ok", "cached"))
    print(f"\n{ok}/{len(reg)} cities built")


if __name__ == "__main__":
    main()
