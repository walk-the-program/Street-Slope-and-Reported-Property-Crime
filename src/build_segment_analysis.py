"""Join crime, census, and building exposure onto street segments.

Segments are the confirmatory unit: they match the published comparison study
and the micro-places literature, and they are the only unit on which the network
mediators (betweenness, permeability, egress, stairs) are defined.

Incidents and buildings are attached to their nearest segment rather than to a
containing polygon, because a street segment is a line and open crime data is
geocoded to addresses along it.

Every city goes through the same `build`; the differences live in `CITIES`.
Three of them are worth stating.

*The CRS comes from the DEM, never from a lookup.* San Francisco's DEM is
EPSG:32610 and an earlier version of this file assumed 26910. Nothing errors:
`mid_x`/`mid_y` are written in one CRS and the incidents are projected into
another, and the join quietly returns the wrong block face for every segment.
Reading `src.crs` removes the chance to get it wrong.

*The analysis area is the incorporated place, not the bounding box.* San
Francisco is a consolidated city-county, so filtering its block groups to county
06075 is the same thing as filtering to the city. Seattle, Cincinnati and
Pittsburgh are each a minority of their county by area, and the DEM box (the
crime extent plus a 1.5 km pad) covers a good deal of suburb. Segments there are
outside the reporting agency's jurisdiction, so their zero counts are structural
rather than observed, and leaving them in would deflate the crime rate wherever
the suburbs happen to sit -- which around Cincinnati and Pittsburgh is
systematically on the uplands above the river valleys. `place_name` clips them.

*Offense text is classified per city by the same rules the grid pipeline uses.*
San Francisco publishes a clean `incident_subcategory` taxonomy and gets the
exact-match `classify`; everyone else gets `classify_text` over whatever
description fields the registry found. Using one classifier for SF and another
for the rest is deliberate: the taxonomies are not the same, and pretending they
are is what makes cross-city crime comparisons wrong.
"""
from __future__ import annotations

import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely

sys.path.insert(0, os.path.dirname(__file__))
import network as NW
from acs import block_groups
from crime_classes import PROPERTY_CLASSES, classify

ALL_CLASS_COLS = sorted(f"n_{c}" for c in PROPERTY_CLASSES + ["OTHER", "ROBBERY"])
MAX_SNAP_M = 60.0    # beyond this an incident is not plausibly on that block face
PLACE_PAD_M = 750.0  # slack around the city boundary when cropping the network box
BG_SHP = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_{st}_bg_500k.zip"
PLACE_SHP = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_{st}_place_500k.zip"
CRIME_CACHE = "data/raw/crime"


# ------------------------------------------------------------ city inputs ----
# Everything that differs between cities. `crime` says where incidents come
# from: ("file", path) for a hand-pulled extract, ("socrata", domain) for a row
# of registry.csv, ("arcgis", city) for a row of registry_arcgis.csv.
CITIES = {
    "sfgov": dict(
        city="San Francisco",
        dem="data/raw/dem/data_sfgov_org.tif",
        crime=("file", "data/raw/sf_property_crime.parquet"),
        state_fips="06", county_fips=["06075"], place_name=None,
        buildings="data_sfgov_org",
        # the SFPD incident bbox from registry.csv rather than the DEM box,
        # because sf_segments.parquet was built on it and seg_id must not move
        bbox=(-122.502975, 37.709541, -122.379507, 37.806864),
        segments="data/interim/segments/sf_segments.parquet",
    ),
    "seattle": dict(
        city="Seattle",
        dem="data/raw/dem/cos-data_seattle_gov.tif",
        crime=("socrata", "cos-data.seattle.gov"),
        state_fips="53", county_fips=["53033"], place_name="Seattle",
        buildings="cos-data_seattle_gov",
        segments="data/interim/segments/seattle_segments.parquet",
    ),
    "cincinnati": dict(
        city="Cincinnati",
        dem="data/raw/dem/data_cincinnati-oh_gov.tif",
        crime=("socrata", "data.cincinnati-oh.gov"),
        state_fips="39", county_fips=["39061"], place_name="Cincinnati",
        buildings="data_cincinnati-oh_gov",
        segments="data/interim/segments/cincinnati_segments.parquet",
    ),
    "pittsburgh": dict(
        city="Pittsburgh",
        dem="data/raw/dem/pittsburgh.tif",
        crime=("arcgis", "Pittsburgh"),
        state_fips="42", county_fips=["42003"], place_name="Pittsburgh",
        buildings="pittsburgh",
        segments="data/interim/segments/pittsburgh_segments.parquet",
    ),
}


def dem_frame(dem_path):
    """(lon/lat bbox, projected EPSG) of a DEM, read off the raster itself."""
    with rasterio.open(dem_path) as src:
        b, crs = src.bounds, src.crs
    epsg = int(crs.to_epsg())
    ll = gpd.GeoSeries([shapely.box(b.left, b.bottom, b.right, b.top)],
                       crs=crs).to_crs(4326).total_bounds
    return tuple(float(v) for v in ll), epsg


def place_polygon(state_fips, name, epsg):
    """The incorporated place, in EPSG:`epsg`.

    Names repeat within a state, so the largest match by land area wins -- the
    study city is never the village of the same name.
    """
    pl = gpd.read_file(PLACE_SHP.format(st=state_fips))
    hit = pl[pl["NAME"].str.lower() == name.lower()]
    if hit.empty:
        raise RuntimeError(f"no place named {name!r} in state {state_fips}")
    hit = hit.sort_values("ALAND", ascending=False).head(1)
    return hit.to_crs(epsg).geometry.iloc[0]


def analysis_bbox(cfg):
    """Lon/lat box the network is built on, and the CRS everything lands in.

    The DEM is the authority on both. The box is then cropped to the city plus
    `PLACE_PAD_M` where a place is named: terrain has to cover every segment we
    keep, so the box can never exceed the DEM, but there is no reason to run
    betweenness across tens of square kilometres of suburb that the place clip
    will discard anyway.
    """
    bbox, epsg = dem_frame(cfg["dem"])
    if cfg.get("bbox"):
        return tuple(cfg["bbox"]), epsg
    if not cfg.get("place_name"):
        return bbox, epsg
    poly = place_polygon(cfg["state_fips"], cfg["place_name"], epsg)
    pad = gpd.GeoSeries([poly.buffer(PLACE_PAD_M)], crs=epsg).to_crs(4326).total_bounds
    return (max(bbox[0], pad[0]), max(bbox[1], pad[1]),
            min(bbox[2], pad[2]), min(bbox[3], pad[3])), epsg


# ---------------------------------------------------------------- crime ----
def load_crime(cfg, slug):
    """Incidents as lat / lon / klass, cached per city under `CRIME_CACHE`.

    Every class is kept, including OTHER and ROBBERY, so the segment table can
    report the property classes as a share of what the department actually
    reported rather than as a share of what we had already decided to keep.
    """
    kind, key = cfg["crime"]
    if kind == "file":
        cr = pd.read_parquet(key).dropna(subset=["latitude", "longitude"])
        cr = cr.rename(columns={"latitude": "lat", "longitude": "lon"})
        cr["klass"] = [k[0] for k in cr["incident_subcategory"].fillna("").map(classify)]
        return cr[["lat", "lon", "klass"]]

    os.makedirs(CRIME_CACHE, exist_ok=True)
    path = os.path.join(CRIME_CACHE, f"{slug}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)

    if kind == "socrata":
        import harvest as HV
        reg = pd.read_csv("data/interim/registry.csv")
        row = next(iter(reg[reg.domain == key].itertuples()))
        cr = HV.fetch_crime(row, property_only=False)
    elif kind == "arcgis":
        import harvest_arcgis as HA
        reg = pd.read_csv(HA.OUT)
        row = next(iter(reg[reg.city == key].itertuples()))
        cr = HA.fetch_city_arcgis(row, property_only=False)
    else:
        raise ValueError(f"unknown crime source {kind!r}")

    cr = cr[["lat", "lon", "klass"]].dropna(subset=["lat", "lon"]).reset_index(drop=True)
    cr.to_parquet(path, index=False)
    return cr


# ---------------------------------------------------------------- build ----
def build(cfg, slug, out_path=None):
    epsg = cfg["_epsg"]
    out_path = out_path or f"data/interim/seg_analysis/{slug}.parquet"

    seg = gpd.read_parquet(cfg["segments"]).to_crs(epsg)
    seg["seg_id"] = seg["seg_id"].astype(str)
    print(f"  {len(seg):,} segments", flush=True)

    # --- crime -> nearest segment ---
    cr = load_crime(cfg, slug)
    pts = gpd.GeoDataFrame(cr, geometry=gpd.points_from_xy(cr.lon, cr.lat),
                           crs=4326).to_crs(epsg)
    j = gpd.sjoin_nearest(pts, seg[["seg_id", "geometry"]], how="left",
                          max_distance=MAX_SNAP_M, distance_col="snap_m")
    j = j[j["seg_id"].notna()]
    print(f"  {len(j):,}/{len(pts):,} incidents snapped within {MAX_SNAP_M:.0f} m"
          f" ({len(j) / max(len(pts), 1):.1%})", flush=True)

    counts = j.pivot_table(index="seg_id", columns="klass", aggfunc="size", fill_value=0)
    counts.columns = [f"n_{c}" for c in counts.columns]
    # Reindex onto the full taxonomy so every city has the same columns whether
    # or not it happens to report the class. Pittsburgh's statute text has no
    # auto-parts or commercial-burglary wording, so MASS_5 is genuinely empty
    # there -- a column of zeros says that, a missing column breaks the pool.
    counts = counts.reindex(columns=ALL_CLASS_COLS, fill_value=0)
    keep = [c for c in counts.columns if c != "n_OTHER"]
    counts["n_total"] = counts[keep].sum(axis=1)
    seg = seg.merge(counts, left_on="seg_id", right_index=True, how="left")
    for c in [c for c in seg.columns if c.startswith("n_")]:
        seg[c] = seg[c].fillna(0).astype(int)

    # --- block group by segment midpoint ---
    mids = gpd.GeoDataFrame(seg[["seg_id"]],
                            geometry=gpd.points_from_xy(seg.mid_x, seg.mid_y), crs=epsg)
    bg = gpd.read_file(BG_SHP.format(st=cfg["state_fips"]))
    bg = bg[bg["GEOID"].str[:5].isin(cfg["county_fips"])].to_crs(epsg)
    bj = gpd.sjoin(mids, bg[["GEOID", "ALAND", "geometry"]], how="left",
                   predicate="within").drop_duplicates("seg_id")
    seg = seg.merge(bj[["seg_id", "GEOID", "ALAND"]], on="seg_id", how="left")
    print(f"  {seg['GEOID'].notna().mean():.1%} of segments got a block group", flush=True)
    seg = seg[seg["GEOID"].notna()].copy()
    # the left join floats ALAND wherever a segment missed a block group; the
    # rows are gone by now, so put the dtype back for cross-city concatenation
    seg["ALAND"] = seg["ALAND"].astype("int64")

    if cfg.get("place_name"):
        inside = shapely.intersects(
            place_polygon(cfg["state_fips"], cfg["place_name"], epsg),
            shapely.points(seg["mid_x"], seg["mid_y"]))
        print(f"  {int(inside.sum()):,}/{len(seg):,} of those inside "
              f"{cfg['place_name']} city limits", flush=True)
        seg = seg[inside].copy()
    print(f"  {len(seg):,} segments inside the jurisdiction", flush=True)

    # --- building exposure -> nearest segment ---
    import exposure as EX
    b = EX.building_footprints(cfg["_bbox"], epsg, name=cfg["buildings"]).to_crs(epsg)
    bpts = gpd.GeoDataFrame(
        {"area": b.geometry.area.values,
         "resid": (b["bldg_class"].astype(str).str.contains("resid", case=False, na=False).values
                   if "bldg_class" in b else np.ones(len(b), bool))},
        geometry=b.geometry.centroid, crs=epsg)
    bj2 = gpd.sjoin_nearest(bpts, seg[["seg_id", "geometry"]], how="left",
                            max_distance=120.0)
    agg = bj2.dropna(subset=["seg_id"]).groupby("seg_id").agg(
        bldg_count=("area", "size"),
        resid_area=("area", lambda s: float(np.nansum(s))))
    seg = seg.merge(agg, on="seg_id", how="left")
    seg["bldg_count"] = seg["bldg_count"].fillna(0)
    seg["resid_area"] = seg["resid_area"].fillna(0.0)
    print(f"  {int(seg.bldg_count.sum()):,} buildings attached", flush=True)

    ses = block_groups()
    seg = seg.merge(ses, on="GEOID", how="left")

    # Apportion block-group housing units by residential building area where we
    # have footprints, falling back to segment length. Length alone overstates
    # exposure on long undeveloped edges, which is the same error that inflated
    # the grid-cell results in sprawling jurisdictions.
    if seg["resid_area"].notna().any() and seg["resid_area"].sum() > 0:
        share = seg["resid_area"] / seg.groupby("GEOID")["resid_area"].transform("sum")
        fallback = ~np.isfinite(share) | (share <= 0)
        lshare = seg["seg_len_m"] / seg.groupby("GEOID")["seg_len_m"].transform("sum")
        share = np.where(fallback, lshare, share)
        seg["exposure_fallback"] = fallback
    else:
        share = seg["seg_len_m"] / seg.groupby("GEOID")["seg_len_m"].transform("sum")
        seg["exposure_fallback"] = True
    seg["housing_units_cell"] = seg["housing_units"] * share
    seg["pop_cell"] = seg["population"] * share
    seg["city"] = cfg["city"]

    out = pd.DataFrame(seg.drop(columns="geometry"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.to_parquet(out_path, index=False)
    print(f"  wrote {out_path}  ({len(out):,} segments, {int(out.n_total.sum()):,} incidents)")
    return out


def run(slug):
    """Segments, then the joins, for one city. Both stages cache to disk."""
    cfg = dict(CITIES[slug])
    cfg["_bbox"], cfg["_epsg"] = analysis_bbox(cfg)
    print(f"[{cfg['city']}] EPSG:{cfg['_epsg']} "
          f" bbox={tuple(round(v, 5) for v in cfg['_bbox'])}", flush=True)

    if not os.path.exists(cfg["segments"]):
        NW.build_segments(city=cfg["city"], dem_path=cfg["dem"], bbox=cfg["_bbox"],
                          epsg=cfg["_epsg"], out_path=cfg["segments"])
    return build(cfg, slug)


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["sfgov"]):
        run(s)
