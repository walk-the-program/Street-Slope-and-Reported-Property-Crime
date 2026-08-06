"""Target-matched exposure denominators for San Francisco.

The headline result -- roughly 6% less property crime per degree of street slope
-- is estimated against a denominator of block-group housing units apportioned
to segments by residential building footprint. That denominator says how much
*housing* a segment holds. It does not say how many *targets* a segment
presents, and the two can come apart on exactly the dimension under test: a
steep block physically holds fewer parked cars per metre of curb, and hillside
lots put more of their dwellings behind garages and up flights of steps. If
steep streets simply present fewer targets per housing unit, the slope
coefficient is partly definitional rather than behavioural.

This module rebuilds the denominator out of the things actually stolen from,
and refits the models with it. Three target counts, each matched to a crime
family:

  parked-vehicle capacity   theft from vehicle, motor vehicle theft
  street-facing front doors burglary
  both                      vandalism (no loot, so neither target class is
                            privileged a priori)

Sources are all public and all San Francisco specific, which is the point --
this is a deep single-city audit of a claim estimated across cities, not a
replacement pipeline.

  SFMTA On-Street Parking Census (DataSF 9ivs-nf5y). Field and remote counts of
      publicly available on-street spaces per street segment, surveyed 2008-2014
      at 17 ft per undemarcated space. 14,346 segments, 275,339 spaces, which
      matches SFMTA's published citywide total. This is a real capacity census,
      not a proxy, and it is the reason San Francisco is the city worth auditing.
  Enterprise Addressing System (DataSF ramy-di5m). 388,551 active addresses
      including sub-unit records. Distinct `eas_baseid` values are base
      addresses -- the closest thing to a count of front doors that exists.
  San Francisco Land Use (DataSF c5ge-t6pj). Parcel-level `resunits`, giving
      dwelling counts that never pass through the block-group apportionment step
      the artifact objection is aimed at.
  Parking Meters (DataSF 8vzz-qzz9) and OSM `amenity=parking` are carried as
      cross-checks; both are reported but neither is used as a headline offset,
      for coverage reasons documented in `coverage_report`.

OSM `entrance=*` was tried and abandoned: 1,512 mapped entrance nodes for a city
with 224,250 base addresses is under 1% coverage, concentrated in downtown
transit stations. It is recorded in the coverage table and used nowhere.
"""
from __future__ import annotations

import os
import sys
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shapely

sys.path.insert(0, os.path.dirname(__file__))
from analyze import SES, coef, poisson

warnings.filterwarnings("ignore")

EPSG = 32610
SF_BBOX = (-122.5030, 37.7095, -122.3795, 37.8069)
CACHE = "data/raw/parking"
SEG_GEOM = "data/interim/segments/sf_segments.parquet"
SEG_TABLE = "data/interim/seg_analysis/sfgov.parquet"
BUILDINGS = "data/raw/buildings/data_sfgov_org_epsg32610.parquet"
CRIME = "data/raw/sf_property_crime.parquet"
TARGETS = "data/interim/seg_analysis/sfgov_targets.parquet"
OUT = "outputs"

# Sentinel in the parking census: divided streets whose whole-block count was
# aggregated onto one side carry 5555 on the other. Documented by the publisher.
PARKING_SENTINEL = 5555

SAMPLE_STEP_M = 10.0    # densification step when apportioning census lines
LINE_SNAP_M = 25.0      # CNN centreline vs OSM centreline disagreement tolerance
POINT_SNAP_M = 60.0     # matches MAX_SNAP_M in build_segment_analysis.py
FRONTAGE_M = 15.0       # a footprint this close to the centreline fronts it

# Crime subcategories regrouped by which target class they attack. The published
# MASS_* classes are ordered by loot weight, which mixes target types: MASS_2
# holds theft-from-vehicle and shoplifting together, and MASS_4 holds burglary
# and bicycle theft together. A denominator test needs the target, not the
# weight, so these are rebuilt from the raw incident file.
VEHICLE_SUBCATS = {
    "n_TFV": ["Larceny - From Vehicle", "Theft From Vehicle"],
    "n_AUTOPARTS": ["Larceny - Auto Parts"],
    "n_MVT_chk": ["Motor Vehicle Theft", "Motor Vehicle Theft (Attempted)"],
}
BURG_SUBCATS = {
    "n_BURG_RES": ["Burglary - Residential", "Burglary - Hot Prowl"],
    "n_BURG_ALL": ["Burglary - Residential", "Burglary - Hot Prowl",
                   "Burglary - Other", "Burglary - Commercial"],
}


# --- data acquisition ------------------------------------------------------

def _socrata_geojson(dataset_id: str, name: str, limit: int = 200_000) -> gpd.GeoDataFrame:
    path = os.path.join(CACHE, f"{name}.geojson")
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        r = requests.get(f"https://data.sfgov.org/resource/{dataset_id}.geojson",
                         params={"$limit": limit}, timeout=300)
        r.raise_for_status()
        with open(path, "wb") as fh:
            fh.write(r.content)
    return gpd.read_file(path)


def _socrata_rows(dataset_id: str, select: str, name: str, page_size: int = 50_000) -> pd.DataFrame:
    """Paged Socrata JSON with an on-disk cache.

    Ordered by `:id` rather than left unordered, because Socrata gives no
    stability guarantee across pages otherwise and silently duplicates or drops
    rows on a large offset walk.
    """
    path = os.path.join(CACHE, f"{name}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    os.makedirs(CACHE, exist_ok=True)
    parts, off = [], 0
    while True:
        r = requests.get(
            f"https://data.sfgov.org/resource/{dataset_id}.json",
            params={"$select": select, "$limit": page_size, "$offset": off,
                    "$order": ":id"}, timeout=300)
        r.raise_for_status()
        d = r.json()
        if not d:
            break
        parts.append(pd.DataFrame(d))
        off += len(d)
        if len(d) < page_size:
            break
    out = pd.concat(parts, ignore_index=True)
    out.to_parquet(path)
    return out


def parking_census() -> gpd.GeoDataFrame:
    g = _socrata_geojson("9ivs-nf5y", "on_street_parking_census")
    g["prkg_sply"] = pd.to_numeric(g["prkg_sply"], errors="coerce")
    g = g[g["prkg_sply"].notna() & (g["prkg_sply"] != PARKING_SENTINEL)]
    return g.to_crs(EPSG)


def parking_meters(active_only: bool = True) -> gpd.GeoDataFrame:
    m = _socrata_rows("8vzz-qzz9",
                      "objectid,active_meter_flag,on_offstreet_type,longitude,latitude",
                      "parking_meters")
    if active_only:
        m = m[m["active_meter_flag"].isin(["M", "T"])]
    m = m[m["on_offstreet_type"] == "ON"]
    xy = m[["longitude", "latitude"]].astype(float)
    return gpd.GeoDataFrame(m, geometry=gpd.points_from_xy(xy.longitude, xy.latitude),
                            crs=4326).to_crs(EPSG)


def addresses() -> gpd.GeoDataFrame:
    a = _socrata_rows("ramy-di5m",
                      "eas_baseid,eas_subid,unit_number,cnn,longitude,latitude",
                      "eas_addresses")
    xy = a[["longitude", "latitude"]].astype(float)
    return gpd.GeoDataFrame(a, geometry=gpd.points_from_xy(xy.longitude, xy.latitude),
                            crs=4326).to_crs(EPSG)


def land_use() -> gpd.GeoDataFrame:
    lu = _socrata_rows("c5ge-t6pj",
                       "ludb_id,centroid_l,centroid_1,resunits,retail,total_comm,"
                       "garage,parking_lo", "land_use")
    for c in ("centroid_l", "centroid_1", "resunits", "retail", "total_comm"):
        lu[c] = pd.to_numeric(lu[c], errors="coerce")
    lu = lu.dropna(subset=["centroid_l", "centroid_1"])
    # centroid_l is latitude and centroid_1 is longitude, despite the names.
    return gpd.GeoDataFrame(
        lu, geometry=gpd.points_from_xy(lu.centroid_1, lu.centroid_l), crs=4326
    ).to_crs(EPSG)


def osm_points(tags: dict, name: str) -> gpd.GeoDataFrame | None:
    """OSM features for the SF bbox, cached. Returns None if Overpass is down."""
    path = os.path.join(CACHE, f"osm_{name}.parquet")
    if os.path.exists(path):
        return gpd.read_parquet(path).to_crs(EPSG)
    try:
        import osmnx as ox
        ox.settings.use_cache = True
        ox.settings.cache_folder = "data/raw/osm/cache"
        g = ox.features_from_bbox(SF_BBOX, tags)
    except Exception as exc:
        print(f"  OSM {name} unavailable ({type(exc).__name__}: {exc})", flush=True)
        return None
    keep = [c for c in (list(tags) + ["capacity", "geometry"]) if c in g.columns]
    g = g[keep].reset_index(drop=True)
    for c in keep:
        if c != "geometry":
            g[c] = g[c].astype(str)
    os.makedirs(CACHE, exist_ok=True)
    g.to_parquet(path)
    return g.to_crs(EPSG)


# --- spatial apportionment -------------------------------------------------

def _densify(lines: gpd.GeoSeries, step: float = SAMPLE_STEP_M):
    """Evenly spaced interior points along each line, with per-point weights.

    Returns (points, line_index, share) where `share` is each point's fraction
    of its parent line, so any per-line quantity can be split across the
    segments its points land on.
    """
    geoms = lines.values
    lens = shapely.length(geoms)
    n = np.maximum(np.ceil(lens / step).astype(int), 1)
    idx = np.repeat(np.arange(len(geoms)), n)
    starts = np.repeat(np.concatenate([[0], np.cumsum(n)[:-1]]), n)
    pos = np.arange(n.sum()) - starts
    frac = (pos + 0.5) / n[idx]
    pts = shapely.line_interpolate_point(geoms[idx], frac * lens[idx])
    return pts, idx, 1.0 / n[idx]


def apportion_lines(lines: gpd.GeoDataFrame, value_col: str, seg: gpd.GeoDataFrame,
                    max_dist: float = LINE_SNAP_M, step: float = SAMPLE_STEP_M):
    """Split a per-line quantity across the street segments it overlaps.

    The parking census is drawn on the city's CNN centrelines and the analysis
    runs on OSM segments. The two networks break at different places -- CNN
    blocks are intersection-to-intersection, OSM ways split at every geometry
    change -- so neither a key join nor a nearest-line join is correct. Sampling
    each census line every 10 m and sending each sample to its nearest OSM
    segment splits a census block across the OSM pieces that make it up, in
    proportion to how much of the block each piece carries.

    Also returns matched length per segment, which is what makes coverage
    auditable: a segment credited with parking over 12 m of its 130 m length has
    a bad estimate even though it has a number.
    """
    pts, li, share = _densify(lines.geometry, step)
    lens = shapely.length(lines.geometry.values)
    val = lines[value_col].astype(float).values
    samp = gpd.GeoDataFrame(
        {"val": val[li] * share, "mlen": lens[li] * share},
        geometry=pts, crs=lines.crs)
    j = gpd.sjoin_nearest(samp, seg[["seg_id", "geometry"]], how="left",
                          max_distance=max_dist, distance_col="_d")
    matched = float(j["seg_id"].notna().mean())
    # A sample point equidistant from two segments joins to both; keep one so
    # the apportioned total is conserved.
    j = j[j["seg_id"].notna()]
    j = j[~j.index.duplicated(keep="first")]
    agg = j.groupby("seg_id").agg(value=("val", "sum"), matched_len_m=("mlen", "sum"))
    return agg, matched


def count_points(pts: gpd.GeoDataFrame, seg: gpd.GeoDataFrame, cols: dict,
                 max_dist: float = POINT_SNAP_M) -> pd.DataFrame:
    """Attach points to their nearest segment and aggregate. `cols` maps output
    name to either 'size' or a column to sum."""
    j = gpd.sjoin_nearest(pts, seg[["seg_id", "geometry"]], how="left",
                          max_distance=max_dist)
    j = j[j["seg_id"].notna()]
    j = j[~j.index.duplicated(keep="first")]
    spec = {k: (("seg_id", "size") if v == "size" else (v, "sum")) for k, v in cols.items()}
    return j.groupby("seg_id").agg(**spec)


# --- target builders -------------------------------------------------------

def parked_vehicle_capacity(seg: gpd.GeoDataFrame) -> pd.DataFrame:
    """On-street parking capacity per segment, plus its coverage diagnostics."""
    pc = parking_census()
    agg, matched = apportion_lines(pc, "prkg_sply", seg)
    agg = agg.rename(columns={"value": "park_spaces", "matched_len_m": "park_len_m"})
    print(f"  parking census: {len(pc):,} lines, {pc.prkg_sply.sum():,.0f} spaces, "
          f"{matched:.1%} of 10 m samples matched an OSM segment", flush=True)

    mt = parking_meters()
    meters = count_points(mt, seg, {"meters": "size"}, max_dist=25.0)
    print(f"  parking meters: {len(mt):,} active on-street", flush=True)

    op = osm_points({"amenity": "parking"}, "amenity_parking")
    if op is not None:
        op = op.copy()
        op["geometry"] = op.geometry.centroid
        cap = pd.to_numeric(op.get("capacity"), errors="coerce")
        op["cap"] = cap.fillna(0.0)
        osm_park = count_points(op, seg, {"osm_park_n": "size", "osm_park_cap": "cap"},
                                max_dist=POINT_SNAP_M)
        print(f"  OSM amenity=parking: {len(op):,} features, "
              f"{int(cap.notna().sum()):,} with a capacity tag", flush=True)
    else:
        osm_park = pd.DataFrame(columns=["osm_park_n", "osm_park_cap"])

    return agg.join([meters, osm_park], how="outer")


def frontage_targets(seg: gpd.GeoDataFrame) -> pd.DataFrame:
    """Street-facing target counts: front doors, dwelling units, buildings."""
    a = addresses()
    # One row per base address is one front door; the sub-unit rows behind it are
    # dwellings reached through that door. Both matter, for different crimes.
    base = a.drop_duplicates("eas_baseid")
    doors = count_points(base, seg, {"front_doors": "size"})
    units = count_points(a, seg, {"addr_units": "size"})
    print(f"  EAS: {len(base):,} base addresses, {len(a):,} address+unit records",
          flush=True)

    lu = land_use()
    lu["resunits"] = lu["resunits"].fillna(0.0)
    lu["retail"] = lu["retail"].fillna(0.0)
    lu["garage_i"] = lu["garage"].astype(str).str.lower().isin(["true", "1"]).astype(float)
    parcels = count_points(lu, seg, {"parcel_n": "size", "resunits": "resunits",
                                     "retail_sqft": "retail", "garage_parcels": "garage_i"})
    print(f"  land use: {len(lu):,} parcels, {lu.resunits.sum():,.0f} residential units",
          flush=True)

    b = gpd.read_parquet(BUILDINGS).to_crs(EPSG)
    b["resid_i"] = b["bldg_class"].astype(str).str.contains("resid", case=False,
                                                            na=False).astype(float)
    # Footprint-to-centreline distance, not centroid-to-centreline: a 100 m deep
    # warehouse should count as fronting the street its wall is on.
    bj = gpd.sjoin_nearest(b[["resid_i", "geometry"]], seg[["seg_id", "geometry"]],
                           how="left", max_distance=FRONTAGE_M)
    bj = bj[bj["seg_id"].notna()]
    bj = bj[~bj.index.duplicated(keep="first")]
    front = bj.groupby("seg_id").agg(bldg_front=("seg_id", "size"),
                                     bldg_front_resid=("resid_i", "sum"))
    print(f"  buildings: {len(b):,} footprints, {len(bj):,} within {FRONTAGE_M:.0f} m "
          f"of a segment centreline", flush=True)

    ent = osm_points({"entrance": True}, "entrances")
    if ent is not None:
        ent = ent[ent.geom_type == "Point"]
        ents = count_points(ent, seg, {"osm_entrances": "size"}, max_dist=30.0)
        print(f"  OSM entrance nodes: {len(ent):,} citywide "
              f"({len(ent)/max(len(base),1):.1%} of base addresses) -- too sparse to use",
              flush=True)
    else:
        ents = pd.DataFrame(columns=["osm_entrances"])

    return doors.join([units, parcels, front, ents], how="outer")


def target_crime_counts(seg: gpd.GeoDataFrame) -> pd.DataFrame:
    """Rebuild crime counts grouped by target class rather than by loot weight."""
    cr = pd.read_parquet(CRIME).dropna(subset=["latitude", "longitude"])
    wanted = {k: v for d in (VEHICLE_SUBCATS, BURG_SUBCATS) for k, v in d.items()}
    keep = sorted({s for v in wanted.values() for s in v})
    cr = cr[cr["incident_subcategory"].isin(keep)]
    pts = gpd.GeoDataFrame(cr, geometry=gpd.points_from_xy(cr.longitude, cr.latitude),
                           crs=4326).to_crs(EPSG)
    j = gpd.sjoin_nearest(pts, seg[["seg_id", "geometry"]], how="left",
                          max_distance=POINT_SNAP_M)
    j = j[j["seg_id"].notna()]
    j = j[~j.index.duplicated(keep="first")]
    out = pd.DataFrame(index=pd.Index(seg["seg_id"].unique(), name="seg_id"))
    for col, subs in wanted.items():
        s = j[j["incident_subcategory"].isin(subs)].groupby("seg_id").size()
        out[col] = s.reindex(out.index).fillna(0.0)
    out["n_VEH"] = out["n_TFV"] + out["n_AUTOPARTS"] + out["n_MVT_chk"]
    return out


# --- assembly --------------------------------------------------------------

def build(force: bool = False) -> pd.DataFrame:
    """Join every target count onto the SF segment analysis table."""
    if os.path.exists(TARGETS) and not force:
        return pd.read_parquet(TARGETS)

    seg = gpd.read_parquet(SEG_GEOM).to_crs(EPSG)
    seg["seg_id"] = seg["seg_id"].astype(str)
    base = pd.read_parquet(SEG_TABLE)
    base["seg_id"] = base["seg_id"].astype(str)
    print(f"  {len(seg):,} segments", flush=True)

    parts = [parked_vehicle_capacity(seg), frontage_targets(seg), target_crime_counts(seg)]
    tgt = parts[0].join(parts[1:], how="outer")
    tgt.index = tgt.index.astype(str)

    df = base.merge(tgt, left_on="seg_id", right_index=True, how="left")
    fill = [c for c in tgt.columns]
    df[fill] = df[fill].fillna(0.0)

    df["park_cov"] = df["park_len_m"] / df["seg_len_m"].clip(lower=1.0)
    # A segment is credited with a real capacity estimate when the census
    # covered most of its length. Anything less is a fragment of a neighbouring
    # block bleeding across the snap tolerance.
    df["park_measured"] = df["park_cov"] >= 0.5

    os.makedirs(os.path.dirname(TARGETS), exist_ok=True)
    df.to_parquet(TARGETS, index=False)
    print(f"  wrote {TARGETS} ({len(df):,} segments)")
    return df


# --- modelling -------------------------------------------------------------

def prep(df: pd.DataFrame) -> pd.DataFrame:
    """Model frame. Mirrors analyze_national.prep_city for the columns the
    segment table actually carries, and adds the alternative denominators."""
    df = df.copy()
    df["expo_housing"] = df["housing_units_cell"].fillna(0) + df["pop_cell"].fillna(0)
    df = df[df["expo_housing"] > 5]
    df["log_income"] = np.log(df["median_hh_income"].clip(lower=5000))
    df["log_value"] = np.log(df["median_home_value"].clip(lower=50000))
    df["log_density"] = np.log(df["expo_housing"])
    df["owner_share"] = df["owner_share"].astype(float)
    df["vacancy_rate"] = df["vacancy_rate"].astype(float)

    # Same jurisdiction and geocoding-sink rules as the published pipeline.
    df = df[df.groupby("GEOID")["n_total"].transform("sum") > 0]
    df = df[df["n_total"] / df["expo_housing"].clip(lower=1) < 50]

    df["expo_park"] = df["park_spaces"]
    df["expo_park_all"] = df["park_spaces"] + df["garage_parcels"] + df["osm_park_cap"]
    df["expo_doors"] = df["front_doors"]
    df["expo_units"] = df["addr_units"]
    df["expo_resunits"] = df["resunits"]
    df["expo_bldg"] = df["bldg_front"]
    df["expo_both"] = df["park_spaces"] + df["front_doors"]

    need = SES + ["slope_deg", "tpi_500", "GEOID", "n_total"]
    df = df.dropna(subset=[c for c in need if c in df])
    for c in ("slope_deg", "tpi_500"):
        df[f"{c}_z"] = (df[c] - df[c].mean()) / df[c].std()
    return df[df.groupby("GEOID")["GEOID"].transform("size") >= 3].reset_index(drop=True)


def _fit(df, y, offset_col, xvar="slope_deg", controls=None):
    d = df.copy()
    d["exposure"] = d[offset_col]
    d = d[d["exposure"] > 0]
    d = d[d.groupby("GEOID")["GEOID"].transform("size") >= 3]
    xs = [xvar] + list(controls if controls is not None else SES)
    res, names = poisson(d, y, xs, bg_fe=True)
    c = coef(res, names, xvar)
    c.update({"n_seg": len(d), "n_bg": d["GEOID"].nunique(),
              "n_events": int(d[y].sum()),
              "pct_per_sd": 100 * (np.exp(c["beta"] * d[xvar].std()) - 1)})
    return c


def compare(df, y, target_col, family, label, controls=None, controls_label="SES",
            sample="all"):
    """Fit the same outcome under the housing offset and the target offset, on
    the identical rows, so the only thing that changes is the denominator.

    `sample` selects the robustness variant:
      all       every segment with a positive count of both denominators
      measured  only where the parking census covered 50-200% of the segment,
                which removes both thin bleed-over and short stubs that absorbed
                a whole neighbouring block's spaces
      floored   target count floored at 0.5 instead of dropping zeros, so
                segments that genuinely present no targets stay in the sample.
                A segment with no parking and no doors is exactly where the
                artifact story would live, and dropping it would hide it.
    """
    d = df.copy()
    if sample == "measured":
        d = d[d["park_cov"].between(0.5, 2.0)]
    if sample == "floored":
        d[target_col] = d[target_col].clip(lower=0.5)
    d = d[(d["expo_housing"] > 0) & (d[target_col] > 0)]
    d = d[d.groupby("GEOID")["GEOID"].transform("size") >= 3]
    rows = []
    for tag, off in (("housing", "expo_housing"), ("target", target_col)):
        c = _fit(d, y, off, controls=controls)
        c.update({"family": family, "outcome": y, "offset": tag,
                  "offset_col": off, "target": label, "controls": controls_label,
                  "sample": sample})
        rows.append(c)
    b0, b1 = rows[0]["beta"], rows[1]["beta"]
    shrink = 1 - abs(b1) / abs(b0) if abs(b0) > 1e-9 else np.nan
    for r in rows:
        r["shrinkage_vs_housing"] = shrink
    return rows


def denominator_test(df):
    """The artifact hypothesis, stated directly and tested directly.

    If steep streets present fewer targets per housing unit, then a Poisson of
    target count on slope with the housing offset must return a clear negative.
    This does not depend on any crime outcome, so it separates the mechanical
    claim from the behavioural one before any crime model is fitted.
    """
    rows = []
    for col, label in (("park_spaces", "on-street parking spaces"),
                       ("front_doors", "base addresses (front doors)"),
                       ("addr_units", "addresses incl. units"),
                       ("resunits", "parcel residential units"),
                       ("bldg_front", "buildings within 15 m")):
        d = df[df[col] > 0].copy()
        d["exposure"] = d["expo_housing"]
        d = d[d.groupby("GEOID")["GEOID"].transform("size") >= 3]
        res, names = poisson(d, col, ["slope_deg"] + SES, bg_fe=True)
        c = coef(res, names, "slope_deg")
        c.update({"target": label, "n_seg": len(d),
                  "pct_per_sd": 100 * (np.exp(c["beta"] * d["slope_deg"].std()) - 1)})
        rows.append(c)
    return pd.DataFrame(rows)


def coverage_report(df) -> pd.DataFrame:
    """What the target data actually covers. Reported alongside every coefficient
    because a denominator swap is only as good as the denominator's coverage."""
    n = len(df)
    rows = [
        ("segments in the SF analysis table", n, 1.0),
        ("parking census matched any length", int((df.park_len_m > 0).sum()),
         float((df.park_len_m > 0).mean())),
        ("parking census covers >=50% of segment length",
         int(df.park_measured.sum()), float(df.park_measured.mean())),
        ("parking census covers >=80% of segment length",
         int((df.park_cov >= 0.8).sum()), float((df.park_cov >= 0.8).mean())),
        ("non-zero on-street capacity", int((df.park_spaces > 0).sum()),
         float((df.park_spaces > 0).mean())),
        ("has an active parking meter", int((df.meters > 0).sum()),
         float((df.meters > 0).mean())),
        ("has >=1 base address", int((df.front_doors > 0).sum()),
         float((df.front_doors > 0).mean())),
        ("has >=1 parcel residential unit", int((df.resunits > 0).sum()),
         float((df.resunits > 0).mean())),
        ("has >=1 building within 15 m", int((df.bldg_front > 0).sum()),
         float((df.bldg_front > 0).mean())),
        ("has an OSM entrance node", int((df.osm_entrances > 0).sum()),
         float((df.osm_entrances > 0).mean())),
        ("housing exposure came from the length fallback",
         int(df.exposure_fallback.sum()), float(df.exposure_fallback.mean())),
    ]
    return pd.DataFrame(rows, columns=["item", "n_segments", "share"])


def run_tests(out_csv: str = f"{OUT}/target_exposure_tests.csv"):
    raw = build()
    df = prep(raw)
    print(f"\nanalysis sample: {len(df):,} segments, {df.GEOID.nunique():,} block groups, "
          f"{int(df.n_total.sum()):,} incidents")
    print(f"slope: mean {df.slope_deg.mean():.2f} deg, SD {df.slope_deg.std():.2f} deg\n")

    cov = coverage_report(raw).merge(
        coverage_report(df).rename(columns={"n_segments": "n_in_sample",
                                            "share": "share_in_sample"}),
        on="item")
    print("=" * 86)
    print("COVERAGE  (all segments | estimation sample)")
    print("=" * 86)
    for _, r in cov.iterrows():
        print(f"  {r['item']:<52s} {r['n_segments']:>7,} {r['share']:6.1%}  |  "
              f"{r['n_in_sample']:>7,} {r['share_in_sample']:6.1%}")

    print("\n" + "=" * 86)
    print("DOES SLOPE PREDICT TARGET COUNT PER HOUSING UNIT?  (the artifact, stated directly)")
    print("=" * 86)
    dt = denominator_test(df)
    print(dt[["target", "n_seg", "pct", "lo", "hi", "z"]].round(2).to_string(index=False))
    dt.to_csv(f"{OUT}/target_exposure_denominator.csv", index=False)

    specs = [
        # (outcome, target denominator, family, human label)
        ("n_TFV", "expo_park", "vehicle", "on-street parking spaces"),
        ("n_MVT", "expo_park", "vehicle", "on-street parking spaces"),
        ("n_VEH", "expo_park", "vehicle", "on-street parking spaces"),
        ("n_VEH", "expo_park_all", "vehicle", "on-street + off-street parking"),
        ("n_MASS_2", "expo_park", "vehicle", "on-street parking spaces"),
        ("n_MASS_4", "expo_doors", "burglary", "base addresses (front doors)"),
        ("n_MASS_4", "expo_bldg", "burglary", "buildings within 15 m"),
        ("n_BURG_RES", "expo_doors", "burglary", "base addresses (front doors)"),
        ("n_BURG_ALL", "expo_doors", "burglary", "base addresses (front doors)"),
        ("n_BURG_RES", "expo_units", "burglary", "addresses incl. units"),
        ("n_BURG_RES", "expo_resunits", "burglary", "parcel residential units"),
        ("n_BURG_RES", "expo_bldg", "burglary", "buildings within 15 m"),
        ("n_NO_LOOT", "expo_park", "vandalism", "on-street parking spaces"),
        ("n_NO_LOOT", "expo_doors", "vandalism", "base addresses (front doors)"),
        ("n_NO_LOOT", "expo_both", "vandalism", "parking spaces + front doors"),
        ("n_total", "expo_both", "all property", "parking spaces + front doors"),
    ]
    # Robustness: the same decisive comparisons on the well-measured parking
    # subsample, and with zero-target segments retained rather than dropped.
    robust = [("n_VEH", "expo_park", "vehicle", "on-street parking spaces"),
              ("n_MASS_4", "expo_doors", "burglary", "base addresses (front doors)"),
              ("n_NO_LOOT", "expo_both", "vandalism", "parking spaces + front doors"),
              ("n_total", "expo_both", "all property", "parking spaces + front doors")]

    rows = []
    print("\n" + "=" * 86)
    print("SLOPE COEFFICIENT UNDER THE HOUSING OFFSET vs THE TARGET OFFSET")
    print("(% change in crime per +1 degree of street slope, block-group FE, clustered SEs)")
    print("=" * 86)
    print(f"  {'outcome':<12s} {'denominator':<30s} {'n':>7s} {'events':>8s} "
          f"{'%/deg':>8s} {'95% CI':>18s} {'z':>7s}")
    jobs = [(y, t, f, l, s) for y, t, f, l in specs for s in ("all",)]
    jobs += [(y, t, f, l, s) for y, t, f, l in robust for s in ("measured", "floored")]
    for y, tcol, fam, lab, samp in jobs:
        for controls, clabel in ((SES, "SES"),
                                 ([c for c in SES if c != "log_density"], "SES_no_density")):
            try:
                r = compare(df, y, tcol, fam, lab, controls=controls,
                            controls_label=clabel, sample=samp)
            except Exception as exc:
                print(f"  [fail] {y} / {tcol} / {clabel}: {type(exc).__name__}: {exc}")
                continue
            rows.extend(r)
            if clabel == "SES":
                sfx = "" if samp == "all" else f"  [{samp}]"
                for rr in r:
                    dn = ("housing units + pop" if rr["offset"] == "housing" else lab) + sfx
                    print(f"  {y:<12s} {dn:<30s} {rr['n_seg']:>7,} {rr['n_events']:>8,} "
                          f"{rr['pct']:>+8.2f} [{rr['lo']:>+7.2f},{rr['hi']:>+7.2f}] "
                          f"{rr['z']:>+7.2f}")
                print(f"  {'':<12s} {'-> shrinkage toward zero':<30s} "
                      f"{r[0]['shrinkage_vs_housing']:>+7.1%}")

    res = pd.DataFrame(rows)
    order = ["family", "outcome", "offset", "target", "controls", "sample", "n_seg",
             "n_bg", "n_events", "beta", "se", "pct", "lo", "hi", "z", "pct_per_sd",
             "shrinkage_vs_housing", "offset_col"]
    res = res[[c for c in order if c in res.columns]]
    os.makedirs(OUT, exist_ok=True)
    res.to_csv(out_csv, index=False)
    cov.to_csv(f"{OUT}/target_exposure_coverage.csv", index=False)
    print(f"\nwrote {out_csv}, {OUT}/target_exposure_coverage.csv, "
          f"{OUT}/target_exposure_denominator.csv")
    return res, cov, dt


if __name__ == "__main__":
    run_tests()
