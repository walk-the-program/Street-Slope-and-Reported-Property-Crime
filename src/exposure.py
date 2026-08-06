"""Building-based exposure: the denominator that turns crime counts into rates.

The Poisson models need an offset describing how much there is to steal in a
cell. `build_city.py` currently gets that by apportioning block-group housing
units to cells *in proportion to land area*, which assumes development is spread
uniformly inside a block group. That assumption is roughly harmless in a dense
gridded city and badly wrong in a sprawling one: a block group that is half
parkland and half subdivision hands the empty half as much exposure as the
built half, so undeveloped ground acquires phantom denominator and looks
crime-sparse for reasons that have nothing to do with terrain.

This module replaces land area with *residential building footprint area* as
the apportionment weight. Buildings are the thing being burgled, so the weight
is the quantity the offset is trying to describe rather than a proxy for it.

Footprint source is Microsoft Building Footprints (the Global ML release, which
is free, US-wide and machine-extracted, so its coverage does not depend on how
much a local OSM community has mapped). Microsoft footprints carry no use
attribute, so building type is layered on from OSM where OSM has an opinion and
left unknown where it does not. OSM buildings are the fallback geometry source
if the Microsoft tiles are unreachable.

Everything is cached hard. The Microsoft tiles are 10-80 MB compressed each and
the per-city extracts are the expensive part of a rebuild.
"""
from __future__ import annotations

import gzip
import math
import os
import shutil
import sys
import tempfile

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import requests

CACHE = "data/raw/buildings"
MS_INDEX = ("https://minedbuildings.z5.web.core.windows.net/global-buildings/"
            "dataset-links.csv")
MS_REGION = "UnitedStates"
MS_ZOOM = 9  # the quadkey level the Global ML release is partitioned at
BG_SHP = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_{st}_bg_500k.zip"

# Footprints below this are sheds, carports and the like. They stay in the raw
# building-area totals but are kept out of the residential weight, because a
# tool shed is not a dwelling and suburban parcels have several of them. The
# threshold sits under any plausible rowhouse footprint (~55 m2).
MIN_DWELLING_AREA_M2 = 20.0

# OSM building values. Anything not listed stays "unknown", which is the common
# case: Microsoft footprints have no use attribute and most US buildings are
# untagged in OSM. Unknown is treated as residential-eligible on the grounds
# that the US building stock is overwhelmingly housing -- see `apportion_to_cells`.
OSM_RESIDENTIAL = {
    "residential", "house", "detached", "semidetached_house", "terrace",
    "apartments", "bungalow", "dormitory", "cabin", "houseboat",
    "static_caravan", "farm", "annexe",
}
OSM_COMMERCIAL = {
    "commercial", "retail", "office", "industrial", "warehouse", "supermarket",
    "kiosk", "hotel", "motel", "shop", "mall", "restaurant", "bank",
}
OSM_OTHER = {
    "garage", "garages", "shed", "carport", "roof", "greenhouse", "hut",
    "barn", "stable", "silo", "storage_tank", "service", "hangar", "bunker",
    "ruins", "construction", "school", "university", "college", "kindergarten",
    "hospital", "church", "cathedral", "chapel", "mosque", "synagogue",
    "temple", "civic", "government", "public", "fire_station", "museum",
    "stadium", "sports_hall", "sports_centre", "train_station",
    "transportation", "parking", "toilets",
}


# --- Microsoft Building Footprints ----------------------------------------

def _tile_xy(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    n = 1 << zoom
    x = int((lon + 180.0) / 360.0 * n)
    r = math.radians(lat)
    y = int((1.0 - math.log(math.tan(r) + 1.0 / math.cos(r)) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def _quadkey(x: int, y: int, zoom: int) -> str:
    out = []
    for i in range(zoom, 0, -1):
        digit, mask = 0, 1 << (i - 1)
        if x & mask:
            digit += 1
        if y & mask:
            digit += 2
        out.append(str(digit))
    return "".join(out)


def quadkeys_for_bbox(bbox, zoom: int = MS_ZOOM) -> list[str]:
    """Quadkeys of every zoom-`zoom` tile touching a (W, S, E, N) lon/lat box."""
    w, s, e, n = bbox
    x0, y0 = _tile_xy(w, n, zoom)
    x1, y1 = _tile_xy(e, s, zoom)
    return [_quadkey(x, y, zoom)
            for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def _ms_index(cache_dir: str) -> pd.DataFrame:
    path = os.path.join(cache_dir, "ms_dataset_links.csv")
    if not os.path.exists(path):
        os.makedirs(cache_dir, exist_ok=True)
        print("  downloading Microsoft tile index ...", flush=True)
        r = requests.get(MS_INDEX, timeout=600)
        r.raise_for_status()
        with open(path, "wb") as fh:
            fh.write(r.content)
    idx = pd.read_csv(path)
    # QuadKey parses as an integer and loses its leading zeros; the partition
    # names in the URLs are zero-padded to the zoom level.
    idx["QuadKey"] = idx["QuadKey"].astype(str).str.zfill(MS_ZOOM)
    return idx


def _download(url: str, path: str) -> str:
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with requests.get(url, stream=True, timeout=1800) as r:
        r.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    os.replace(tmp, path)
    return path


def microsoft_footprints(bbox, cache_dir: str = CACHE) -> gpd.GeoDataFrame:
    """Microsoft Global ML footprints inside a (W, S, E, N) lon/lat box.

    Tiles are cached compressed and expanded to scratch for reading, because a
    zoom-9 tile is ~10x larger uncompressed and there is no reason to keep both.
    GDAL's GeoJSONSeq reader with a bbox filter is roughly two orders of
    magnitude faster than parsing the lines in Python.
    """
    idx = _ms_index(cache_dir)
    idx = idx[idx["Location"] == MS_REGION]
    keys = quadkeys_for_bbox(bbox)
    rows = idx[idx["QuadKey"].isin(keys)]
    missing = sorted(set(keys) - set(rows["QuadKey"]))
    if missing:
        print(f"  no Microsoft tile for quadkeys {missing} (likely all water)",
              flush=True)
    if rows.empty:
        raise RuntimeError("no Microsoft tiles intersect this bbox")

    parts = []
    for _, row in rows.iterrows():
        gz = os.path.join(cache_dir, "ms_tiles", f"{row['QuadKey']}.csv.gz")
        if not os.path.exists(gz):
            print(f"  fetching tile {row['QuadKey']} ({row['Size']}) ...", flush=True)
        _download(row["Url"], gz)
        with tempfile.TemporaryDirectory() as td:
            raw = os.path.join(td, "tile.geojsonl")
            with gzip.open(gz, "rb") as src, open(raw, "wb") as dst:
                shutil.copyfileobj(src, dst)
            g = pyogrio.read_dataframe(raw, bbox=bbox)
        print(f"  tile {row['QuadKey']}: {len(g):,} buildings in bbox", flush=True)
        parts.append(g)

    out = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame(out, geometry="geometry", crs=4326)


# --- OSM -------------------------------------------------------------------

def osm_footprints(bbox, tags=None) -> gpd.GeoDataFrame:
    """OSM features for a (W, S, E, N) lon/lat box. Defaults to all buildings."""
    import osmnx as ox

    return ox.features_from_bbox(tuple(bbox), tags or {"building": True})


def _osm_use_layer(bbox, cache_dir: str, name: str):
    """OSM features that say what a building is *used for*.

    Deliberately narrow. Asking Overpass for every building over a 1,000 km2
    county is slow and mostly returns untagged geometry that duplicates the
    Microsoft layer; asking only for typed buildings plus shop/office points
    returns the small subset that actually carries information. Returns
    (polygons, points) in EPSG:4326, or (None, None) if Overpass fails.
    """
    path = os.path.join(cache_dir, f"osm_use_{name}.parquet")
    if os.path.exists(path):
        g = gpd.read_parquet(path)
    else:
        tags = {
            "building": sorted(OSM_RESIDENTIAL | OSM_COMMERCIAL | OSM_OTHER),
            "shop": True,
            "office": True,
        }
        try:
            g = osm_footprints(bbox, tags)
        except Exception as exc:                      # network, timeout, empty
            print(f"  OSM use layer unavailable ({type(exc).__name__}: {exc})",
                  flush=True)
            return None, None
        keep = [c for c in ("building", "shop", "office", "geometry") if c in g.columns]
        g = g[keep].reset_index(drop=True)
        os.makedirs(cache_dir, exist_ok=True)
        g.to_parquet(path)
    poly = g[g.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    pts = g[g.geom_type == "Point"].copy()
    return poly, pts


def _classify(building: pd.Series, shop: pd.Series, office: pd.Series) -> pd.Series:
    """Collapse OSM tags to residential / commercial / other / unknown."""
    b = building.fillna("").astype(str).str.lower()
    out = pd.Series("unknown", index=b.index, dtype=object)
    out[b.isin(OSM_OTHER)] = "other"
    out[b.isin(OSM_RESIDENTIAL)] = "residential"
    out[b.isin(OSM_COMMERCIAL)] = "commercial"
    # A shop or office node inside a building overrides an untyped building=yes:
    # OSM maps the business as a point far more often than it retypes the shell.
    has_biz = shop.notna() | office.notna()
    out[has_biz & out.isin(["unknown", "other"])] = "commercial"
    return out


# --- public API ------------------------------------------------------------

def building_footprints(bbox, epsg, cache_dir: str = CACHE, name: str | None = None,
                        source: str = "auto", classify: bool = True
                        ) -> gpd.GeoDataFrame:
    """Building footprints for a (W, S, E, N) lon/lat box, in EPSG:`epsg`.

    Returns geometry plus `area_m2`, `bldg_class` and `source`. `source` is
    recorded per building and appended to a manifest in `cache_dir`, because
    Microsoft and OSM coverage differ enough that a cross-city comparison has to
    know which city got which.

    `source`: "ms" | "osm" | "auto" (Microsoft, falling back to OSM).
    """
    name = name or f"bbox_{'_'.join(f'{v:.4f}' for v in bbox)}"
    os.makedirs(cache_dir, exist_ok=True)
    cached = os.path.join(cache_dir, f"{name}_epsg{epsg}.parquet")
    if os.path.exists(cached):
        g = gpd.read_parquet(cached)
        print(f"  cached buildings: {len(g):,} ({g['source'].iloc[0]})", flush=True)
        return g

    used = None
    if source in ("auto", "ms"):
        try:
            g = microsoft_footprints(bbox, cache_dir)
            used = "ms"
        except Exception as exc:
            if source == "ms":
                raise
            print(f"  Microsoft footprints failed ({type(exc).__name__}: {exc});"
                  " falling back to OSM", flush=True)
    if used is None:
        g = osm_footprints(bbox)
        g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]
        used = "osm"

    g = g[g.geometry.notna() & ~g.geometry.is_empty].reset_index(drop=True)
    g = g.to_crs(epsg=epsg)
    g["area_m2"] = g.geometry.area
    g["source"] = used

    # Building use. OSM-sourced geometry already carries its own tags; Microsoft
    # geometry gets them by spatial overlay.
    g["bldg_class"] = "unknown"
    n_typed = 0
    if classify:
        if used == "osm":
            for c in ("building", "shop", "office"):
                if c not in g.columns:
                    g[c] = np.nan
            g["bldg_class"] = _classify(g["building"], g["shop"], g["office"]).values
        else:
            poly, pts = _osm_use_layer(bbox, cache_dir, name)
            if poly is not None:
                g["bldg_class"] = _overlay_class(g, poly, pts, epsg)
        n_typed = int((g["bldg_class"] != "unknown").sum())

    keep = ["geometry", "area_m2", "bldg_class", "source"]
    g = gpd.GeoDataFrame(g[keep], geometry="geometry", crs=g.crs)
    g.to_parquet(cached)

    manifest = os.path.join(cache_dir, "sources.csv")
    rec = pd.DataFrame([{
        "name": name, "epsg": epsg, "source": used, "n_buildings": len(g),
        "n_typed": n_typed, "typed_share": n_typed / max(len(g), 1),
        "bbox": ",".join(f"{v:.5f}" for v in bbox),
        "fetched": pd.Timestamp.now().strftime("%Y-%m-%d"),
    }])
    rec.to_csv(manifest, mode="a", header=not os.path.exists(manifest), index=False)
    print(f"  {len(g):,} buildings from {used}; "
          f"{n_typed:,} ({n_typed / max(len(g), 1):.1%}) carry an OSM use tag",
          flush=True)
    return g


def _overlay_class(bldg: gpd.GeoDataFrame, poly: gpd.GeoDataFrame,
                   pts: gpd.GeoDataFrame, epsg) -> np.ndarray:
    """Transfer OSM use tags onto Microsoft footprints.

    Polygons match on the Microsoft footprint's representative point falling
    inside the OSM shell; points (shop/office nodes) match on falling inside the
    Microsoft footprint. Ties go to the first match, which is arbitrary but rare.
    """
    out = pd.Series("unknown", index=bldg.index, dtype=object)
    reps = gpd.GeoDataFrame(geometry=bldg.geometry.representative_point(), crs=bldg.crs)

    if len(poly):
        p = poly.to_crs(epsg=epsg)
        for c in ("building", "shop", "office"):
            if c not in p.columns:
                p[c] = np.nan
        p["_cls"] = _classify(p["building"], p["shop"], p["office"]).values
        j = gpd.sjoin(reps, p[["_cls", "geometry"]], how="left", predicate="within")
        j = j[~j.index.duplicated()]
        hit = j["_cls"].notna() & (j["_cls"] != "unknown")
        out.loc[j.index[hit]] = j.loc[hit, "_cls"].values

    if len(pts):
        q = pts.to_crs(epsg=epsg)
        j = gpd.sjoin(gpd.GeoDataFrame(geometry=bldg.geometry, crs=bldg.crs),
                      q[["geometry"]], how="inner", predicate="contains")
        idx = pd.Index(j.index.unique())
        out.loc[out.index.isin(idx) & out.isin(["unknown", "other"])] = "commercial"
    return out.values


def block_group_polygons(state_fips, crs, cache_dir: str = "data/raw/bg"):
    """Cartographic block-group polygons for one or more states."""
    os.makedirs(cache_dir, exist_ok=True)
    parts = []
    for st in sorted({str(s).zfill(2) for s in np.atleast_1d(state_fips)}):
        path = os.path.join(cache_dir, f"bg_{st}.parquet")
        if not os.path.exists(path):
            print(f"  downloading block groups for state {st} ...", flush=True)
            g = gpd.read_file(BG_SHP.format(st=st))[["GEOID", "ALAND", "geometry"]]
            g.to_parquet(path)
        parts.append(gpd.read_parquet(path))
    out = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame(out, geometry="geometry", crs=parts[0].crs).to_crs(crs)


def _cell_fractions(b: gpd.GeoDataFrame, step: float, x0: float, y0: float):
    """Split every building across the grid cells it covers, by area.

    Assigning a whole building to the cell holding its centroid is fine for a
    detached house and wrong for a downtown block: a 150 m footprint straddles
    two 100 m cells, and centroid assignment hands one of them everything and
    the other nothing. In SoMa that produced cells with thousands of thefts and
    a denominator of zero.

    Returns (building index, row, col, fraction of the building's area in that
    cell). Buildings whose bounding box sits inside one cell skip the geometry
    work, which is most of them.
    """
    n = len(b)
    area = b["area_m2"].to_numpy()
    geom = b.geometry.to_numpy()
    bnd = b.geometry.bounds
    c0 = np.floor((bnd["minx"].to_numpy() - x0 + step / 2) / step).astype(np.int64)
    c1 = np.floor((bnd["maxx"].to_numpy() - x0 + step / 2) / step).astype(np.int64)
    r0 = np.floor((y0 + step / 2 - bnd["maxy"].to_numpy()) / step).astype(np.int64)
    r1 = np.floor((y0 + step / 2 - bnd["miny"].to_numpy()) / step).astype(np.int64)

    one = (c0 == c1) & (r0 == r1)
    idx = np.arange(n)
    parts = [(idx[one], r0[one], c0[one], np.ones(one.sum()))]

    m = ~one
    if m.any():
        import shapely

        ncol = (c1 - c0 + 1)[m]
        cnt = ((r1 - r0 + 1)[m] * ncol)
        take = np.repeat(idx[m], cnt)
        off = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        nc = np.repeat(ncol, cnt)
        rows = np.repeat(r0[m], cnt) + off // nc
        cols = np.repeat(c0[m], cnt) + off % nc
        boxes = shapely.box(x0 + (cols - 0.5) * step, y0 - (rows + 0.5) * step,
                            x0 + (cols + 0.5) * step, y0 - (rows - 0.5) * step)
        inter = shapely.area(shapely.intersection(geom[take], boxes))
        frac = inter / np.maximum(area[take], 1e-9)
        keep = frac > 1e-6
        print(f"  {m.sum():,} buildings span more than one cell "
              f"({cnt.sum():,} candidate overlaps)", flush=True)
        parts.append((take[keep], rows[keep], cols[keep], frac[keep]))

    return pd.DataFrame({
        "b": np.concatenate([p[0] for p in parts]),
        "row_": np.concatenate([p[1] for p in parts]),
        "col_": np.concatenate([p[2] for p in parts]),
        "frac": np.concatenate([p[3] for p in parts]),
    })


def _grid_geometry(cells: pd.DataFrame) -> tuple[float, float, float]:
    """Recover (step, x0, y0) of the regular analysis grid from cell centroids."""
    ux = np.unique(np.round(cells["x"].values, 3))
    uy = np.unique(np.round(cells["y"].values, 3))
    dx = np.diff(ux)
    dy = np.diff(uy)
    step = float(min(dx[dx > 0].min(), dy[dy > 0].min()))
    return step, float(ux.min()), float(uy.max())


def apportion_to_cells(buildings: gpd.GeoDataFrame, cells_gdf, bg_gdf) -> pd.DataFrame:
    """Reapportion block-group housing units and population by building area.

    For each cell, exposure is the block group's ACS count times the cell's share
    of that block group's *residential* footprint area. Residential means
    everything except footprints OSM explicitly calls commercial or accessory,
    and above `MIN_DWELLING_AREA_M2`. Untyped footprints count as residential:
    the US building stock is mostly housing, and the alternative -- counting only
    what OSM has bothered to tag -- would make exposure track OSM mapping effort,
    which is itself correlated with density and so would smuggle a second bias in.

    Block-group totals are taken over every building the fetch found in that
    block group, not just the ones inside the grid, so a block group that is
    half outside the study area keeps the reduced exposure it deserves -- which
    is what `ALAND` was doing for the area version.

    Block groups where no buildings were detected fall back to area
    apportionment and are flagged in `exposure_fallback`, so robustness checks
    can drop them. That case is real: it is mostly water-adjacent or
    park-dominated block groups where the ACS still reports a handful of units.

    Returns one row per cell, aligned to `cells_gdf`'s index, with the new
    exposures (`housing_units_bldg`, `pop_bldg`), the raw building measures that
    can serve as alternative denominators (`bldg_count`, `bldg_area_m2`,
    `resid_bldg_area_m2`, `commercial_bldg_area_m2`), the block-group totals the
    apportionment used, and `exposure_fallback`.

    Note that a cell can legitimately end up with zero exposure: a beach car
    park or a mall lot has crime and no dwellings. That is the honest answer for
    a housing denominator, but it means the offset cannot be logged raw.
    """
    cells = pd.DataFrame(cells_gdf).copy()
    crs = buildings.crs
    step, x0, y0 = _grid_geometry(cells)

    b = buildings.reset_index(drop=True).copy()
    reps = b.geometry.representative_point()
    b["bx"], b["by"] = reps.x.values, reps.y.values

    # block group of each building
    bg = bg_gdf.to_crs(crs)[["GEOID", "geometry"]]
    pts = gpd.GeoDataFrame(b[["bx", "by"]], geometry=reps.values, crs=crs)
    j = gpd.sjoin(pts, bg, how="left", predicate="within")
    b["GEOID"] = j[~j.index.duplicated()]["GEOID"].reindex(b.index)

    resid = (~b["bldg_class"].isin(["commercial", "other"])) & \
            (b["area_m2"] >= MIN_DWELLING_AREA_M2)
    b["resid_area"] = np.where(resid, b["area_m2"], 0.0)
    b["comm_area"] = np.where(b["bldg_class"] == "commercial", b["area_m2"], 0.0)

    # Cells are located by grid arithmetic rather than a spatial join: 110k cell
    # polygons against 300k buildings is minutes, this is milliseconds.
    cells["col_"] = np.floor((cells["x"].values - x0) / step + 0.5).astype(np.int64)
    cells["row_"] = np.floor((y0 - cells["y"].values) / step + 0.5).astype(np.int64)
    ov = _cell_fractions(b, step, x0, y0)

    # Split each block group's ACS counts across its own buildings first, then
    # sum those per-building shares into cells. Doing it building-first rather
    # than cell-first matters at block-group boundaries: a cell whose centroid
    # sits in block group X can hold buildings belonging to Y, and dividing that
    # cell's whole footprint area by X's total would credit it with units X does
    # not have. This way the units allocated inside a block group can never
    # exceed what the ACS reports for it.
    per_bg = b.dropna(subset=["GEOID"]).groupby("GEOID").agg(
        bg_resid_bldg_area_m2=("resid_area", "sum"),
        bg_bldg_area_m2=("area_m2", "sum"),
        bg_bldg_count=("area_m2", "size"),
    )
    acs = cells.groupby("GEOID")[["housing_units", "population"]].first()

    denom = b["GEOID"].map(per_bg["bg_resid_bldg_area_m2"]).replace(0, np.nan)
    w = b["resid_area"] / denom
    b["units_"] = (b["GEOID"].map(acs["housing_units"]) * w).fillna(0.0)
    b["pop_"] = (b["GEOID"].map(acs["population"]) * w).fillna(0.0)

    # Area-weighted spread of every per-building quantity into cells. `bldg_count`
    # stays a whole-building count keyed on the footprint's representative point,
    # because a fractional building is not a useful denominator.
    ov["_own"] = np.floor(
        (b["bx"].to_numpy()[ov["b"]] - x0) / step + 0.5).astype(np.int64) == ov["col_"]
    ov["_own"] &= np.floor(
        (y0 - b["by"].to_numpy()[ov["b"]]) / step + 0.5).astype(np.int64) == ov["row_"]
    for src, dst in (("area_m2", "bldg_area_m2"), ("resid_area", "resid_bldg_area_m2"),
                     ("comm_area", "commercial_bldg_area_m2"),
                     ("units_", "housing_units_bldg"), ("pop_", "pop_bldg")):
        ov[dst] = b[src].to_numpy()[ov["b"]] * ov["frac"].to_numpy()
    ov["bldg_count"] = ov["_own"].astype(int)

    per_cell = ov.groupby(["row_", "col_"])[
        ["bldg_count", "bldg_area_m2", "resid_bldg_area_m2",
         "commercial_bldg_area_m2", "housing_units_bldg", "pop_bldg"]
    ].sum().reset_index()

    idx = cells.index
    cells = cells.merge(per_cell, on=["row_", "col_"], how="left")
    cells.index = idx
    for c in ("bldg_count", "bldg_area_m2", "resid_bldg_area_m2",
              "commercial_bldg_area_m2", "housing_units_bldg", "pop_bldg"):
        cells[c] = cells[c].fillna(0.0)
    cells["bldg_count"] = cells["bldg_count"].astype(int)
    cells = cells.join(per_bg, on="GEOID")

    # Block groups where nothing was detected keep the old area apportionment,
    # flagged so they can be dropped in a robustness check.
    fallback = (cells["bg_resid_bldg_area_m2"].isna()
                | (cells["bg_resid_bldg_area_m2"] <= 0)).values
    cell_area = (step ** 2) * cells.get("land_frac", 1.0)
    area_share = cell_area / cells["ALAND"].replace(0, np.nan)

    out = pd.DataFrame(index=cells.index)
    for c in ("bldg_count", "bldg_area_m2", "resid_bldg_area_m2",
              "commercial_bldg_area_m2", "bg_resid_bldg_area_m2", "bg_bldg_count"):
        out[c] = cells[c]
    out["housing_units_bldg"] = np.where(
        fallback, cells["housing_units"] * area_share, cells["housing_units_bldg"])
    out["pop_bldg"] = np.where(
        fallback, cells["population"] * area_share, cells["pop_bldg"])
    out["exposure_fallback"] = fallback
    return out


def add_exposure(cells_parquet_path: str, bbox=None, epsg=None, out_path=None,
                 cache_dir: str = CACHE, name: str | None = None,
                 pad_deg: float = 0.01) -> pd.DataFrame:
    """Load a cells parquet, attach building-based exposure, write it back out.

    `bbox` and `epsg` default to the extent and CRS implied by the cell grid.
    The fetch box is padded so that block groups straddling the study-area edge
    still get their buildings counted; otherwise their in-grid cells would
    inherit the whole block group's housing units.
    """
    df = pd.read_parquet(cells_parquet_path)
    name = name or os.path.splitext(os.path.basename(cells_parquet_path))[0]
    if epsg is None:
        raise ValueError("epsg is required: the cells parquet stores x/y without a CRS")

    if bbox is None:
        step, _, _ = _grid_geometry(df)
        corners = gpd.GeoSeries(gpd.points_from_xy(
            [df["x"].min() - step, df["x"].max() + step],
            [df["y"].min() - step, df["y"].max() + step]), crs=epsg).to_crs(4326)
        bbox = (corners.x.min(), corners.y.min(), corners.x.max(), corners.y.max())
    bbox = (bbox[0] - pad_deg, bbox[1] - pad_deg, bbox[2] + pad_deg, bbox[3] + pad_deg)

    print(f"[{name}] buildings", flush=True)
    b = building_footprints(bbox, epsg, cache_dir=cache_dir, name=name)

    print(f"[{name}] block groups", flush=True)
    states = sorted(df["GEOID"].dropna().str[:2].unique())
    bg = block_group_polygons(states, b.crs)

    print(f"[{name}] apportioning", flush=True)
    cells = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["x"], df["y"]), crs=b.crs)
    new = apportion_to_cells(b, cells, bg)
    out = pd.concat([df, new], axis=1)

    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        out.to_parquet(out_path, index=False)
        print(f"[{name}] wrote {out_path}  ({len(out):,} cells)", flush=True)
    return out


# --- diagnostics -----------------------------------------------------------

def _corr(a, b, method="spearman"):
    s = pd.DataFrame({"a": np.asarray(a, float), "b": np.asarray(b, float)}).dropna()
    s = s[np.isfinite(s).all(axis=1)]
    return float(s["a"].corr(s["b"], method=method)) if len(s) > 2 else np.nan


def diagnose(df: pd.DataFrame, city: str, tpi_col: str = "tpi_500") -> dict:
    """Compare old (area) and new (building) exposure, and test it against terrain.

    The question the study needs answered is not whether the denominators differ
    but whether they differ *as a function of terrain*. If low ground was
    collecting phantom exposure, correcting it removes denominator from low
    ground, so the log ratio new/old should rise with TPI. A near-zero
    correlation means the old denominator was noisy but not confounded with the
    headline variable.
    """
    d = df.copy()
    old, new = d["housing_units_cell"], d["housing_units_bldg"]
    ok = old.notna() & new.notna() & (old > 0)
    solid = ok & ~d["exposure_fallback"]
    built = solid & (d["bldg_area_m2"] > 0)

    ratio = np.log((new + 1e-6) / (old + 1e-6))
    big = ok & ((new > 2 * old) | (new < old / 2))
    zero = d["bldg_area_m2"] <= 0
    ncrime = d["n_total"] if "n_total" in d else pd.Series(0, index=d.index)

    out = {
        "city": city,
        "cells": len(d),
        "buildings_in_cells": int(d["bldg_count"].sum()),
        "cells_with_no_building": int(zero.sum()),
        "cells_fallback": int(d["exposure_fallback"].sum()),
        "old_sum": float(old.sum()),
        "new_sum": float(new.sum()),
        "pearson_level": _corr(old[ok], new[ok], "pearson"),
        "spearman_level": _corr(old[ok], new[ok], "spearman"),
        "pearson_log": _corr(np.log1p(old[ok]), np.log1p(new[ok]), "pearson"),
        "n_change_gt_2x": int(big.sum()),
        "share_change_gt_2x": float(big.sum() / max(int(ok.sum()), 1)),
        "corr_logratio_tpi_all": _corr(ratio[ok], d[tpi_col][ok]),
        "corr_logratio_tpi_solid": _corr(ratio[solid], d[tpi_col][solid]),
        # Half of a sprawling county has no buildings at all, and those cells sit
        # at log-ratio negative infinity. Splitting the diagnostic in two says
        # whether the terrain signal is "empty land is low" or a gradient that
        # survives among cells that are actually developed.
        "corr_logratio_tpi_built": _corr(ratio[built], d[tpi_col][built]),
        "corr_hasbldg_tpi": _corr((~zero).astype(float)[ok], d[tpi_col][ok]),
        "corr_old_tpi": _corr(old[ok], d[tpi_col][ok]),
        "corr_new_tpi": _corr(new[ok], d[tpi_col][ok]),
        # If crime lands where the new denominator is zero, the offset cannot be
        # used raw; that share is the size of the problem.
        "crime_total": float(ncrime.sum()),
        "crime_share_in_zero_bldg_cells": float(
            ncrime[zero].sum() / max(ncrime.sum(), 1)),
    }

    # Terciles of TPI: the correlation alone hides whether the shift is a
    # gradient or a single tail.
    t = d.loc[solid, tpi_col]
    if t.notna().sum() > 30:
        q = pd.qcut(t, 3, labels=["low", "mid", "high"], duplicates="drop")
        g = d.loc[solid].groupby(q, observed=True).apply(
            lambda s: pd.Series({
                "old": s["housing_units_cell"].sum(),
                "new": s["housing_units_bldg"].sum()}), include_groups=False)
        out["tercile_new_over_old"] = (g["new"] / g["old"]).round(3).to_dict()
    return out


def _report(res: dict) -> None:
    print(f"\n=== {res['city']} ===")
    print(f"  cells                        {res['cells']:,}")
    print(f"  buildings inside grid        {res['buildings_in_cells']:,}")
    print(f"  cells with zero buildings    {res['cells_with_no_building']:,} "
          f"({res['cells_with_no_building'] / res['cells']:.1%})")
    print(f"  cells on area fallback       {res['cells_fallback']:,} "
          f"({res['cells_fallback'] / res['cells']:.1%})")
    print(f"  total exposure old -> new    {res['old_sum']:,.0f} -> {res['new_sum']:,.0f}")
    print(f"  corr(old, new)  pearson      {res['pearson_level']:.3f}")
    print(f"                  spearman     {res['spearman_level']:.3f}")
    print(f"                  pearson log  {res['pearson_log']:.3f}")
    print(f"  cells changing by >2x        {res['n_change_gt_2x']:,} "
          f"({res['share_change_gt_2x']:.1%})")
    print(f"  KEY: corr(log(new/old), tpi_500)  all cells   {res['corr_logratio_tpi_all']:+.3f}")
    print(f"                                    ex-fallback {res['corr_logratio_tpi_solid']:+.3f}")
    print(f"                                    built only  {res['corr_logratio_tpi_built']:+.3f}")
    print(f"  corr(has any building, tpi_500)   {res['corr_hasbldg_tpi']:+.3f}")
    print(f"  corr(exposure, tpi_500)  old {res['corr_old_tpi']:+.3f}   "
          f"new {res['corr_new_tpi']:+.3f}")
    print(f"  crime in zero-building cells {res['crime_share_in_zero_bldg_cells']:.1%}"
          f" of {res['crime_total']:,.0f} incidents")
    if "tercile_new_over_old" in res:
        s = "  ".join(f"{k}={v}" for k, v in res["tercile_new_over_old"].items())
        print(f"  exposure new/old by TPI tercile:  {s}")


CITIES = {
    "data_sfgov_org": "San Francisco",
    "data_montgomerycountymd_gov": "Montgomery County MD",
    "cos-data_seattle_gov": "Seattle",
    "data_kcmo_org": "Kansas City MO",
    "data_cincinnati-oh_gov": "Cincinnati",
    "data_cityofchicago_org": "Chicago",
}
DIAG = "outputs/exposure_diagnostics.csv"


def epsg_of(name: str) -> int:
    """The CRS the cell x/y columns are in, read off the city's DEM.

    Taken from the raster rather than hardcoded because the cells parquet stores
    projected coordinates with no CRS, and guessing wrong shifts every building
    relative to every cell. Both DEMs turn out to be WGS84 UTM (32610 / 32618),
    not the NAD83 equivalents.
    """
    import rasterio

    with rasterio.open(f"data/raw/dem/{name}.tif") as src:
        return int(src.crs.to_epsg())


if __name__ == "__main__":
    names = sys.argv[1:] or list(CITIES)
    rows = []
    for n in names:
        city, epsg = CITIES[n], epsg_of(n)
        df = add_exposure(f"data/interim/cells/{n}.parquet", epsg=epsg,
                          out_path=f"data/interim/cells_exposure/{n}.parquet", name=n)
        rows.append(diagnose(df, city))
    for r in rows:
        _report(r)

    new = pd.DataFrame(rows).drop(columns=["tercile_new_over_old"], errors="ignore")
    if os.path.exists(DIAG):
        old = pd.read_csv(DIAG)
        new = pd.concat([old[~old["city"].isin(new["city"])], new], ignore_index=True)
    os.makedirs("outputs", exist_ok=True)
    new.to_csv(DIAG, index=False)
    print(f"\nwrote {DIAG}  ({len(new)} cities)")
