"""Street segments as the unit of analysis, plus the network measures that test
the surviving mechanisms.

The effort mechanism is dead (see DIRECTION.md): crimes with nothing to carry
are deterred by terrain as much as theft. What is left is *presence and
exposure* -- through-traffic, escape routes, visibility -- and none of those
exist on a raster grid. They are properties of a network, so the unit has to
become a block face.

The block face is also what Kim & Wo (2023) used in San Francisco and what the
micro-places literature uses generally, so moving to it makes the comparison
direct rather than approximate.

Everything here is city-agnostic: a lat-lon bounding box, a projected CRS, and
a DEM in that projection (or any projection -- coordinates are transformed).

Two conventions worth stating up front.

*Buffered graph, core segments.* The network is downloaded on a bbox padded by
`BUFFER_M`, every measure is computed on that padded network, and only segments
whose midpoint falls inside the original bbox are returned. Betweenness, egress
and permeability are all sensitive to where the network is cut off; padding
moves the artefact outside the analysis sample instead of into it.

*One row per undirected block face.* OSM gives a two-way street as two directed
edges. They are the same physical place, so they are collapsed, and directed
quantities (betweenness) are summed over both directions.

Two things to know before joining crime to this table. `network_type="drive"`
excludes alleys and service roads, so San Francisco comes out at 15,709 faces
against roughly 27,000 records in the DataSF centreline file -- the difference
is alleys, driveways and centreline records split for non-topological reasons,
not missing streets. And osmnx simplification leaves ~1,600 faces under 20 m
(80 under 5 m) as connectors inside complex junctions; they are real places but
carry almost no exposure, and a length floor is worth applying at analysis time.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
import rasterio
import shapely
from pyproj import Transformer
from scipy.signal import fftconvolve
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(__file__))
import terrain as T

OSM_DIR = "data/raw/osm"
BUFFER_M = 1500.0     # graph padding, discarded before returning segments
SAMPLE_M = 20.0       # spacing of sample points along a segment / an edge
LOCAL_R = 400.0       # neighbourhood radius for density-style measures
EGRESS_R = 200.0      # network distance for the escape-route count
VIEW_R = 500.0        # radius for the visibility proxy
TPI_RADII = (100, 250, 500, 1000)
WATER_CUTOFF = -5.0   # matches build_city: below this the DEM is bay, not land
BOUNDARY_TOL_M = 100.0

# Betweenness on every source node is O(nm) and a US city graph runs to ~10^4
# nodes. Brandes' pivot sampling with k sources is unbiased and the *ranking*
# of arterials -- which is all this variable is used for -- stabilises long
# before the values do. Exact below K_EXACT_MAX nodes, k = K_SAMPLE above it.
K_EXACT_MAX = 4000
K_SAMPLE = 2000
BC_SEED = 0

ox.settings.use_cache = True
ox.settings.cache_folder = os.path.join(OSM_DIR, "cache")
ox.settings.log_console = False
ox.settings.requests_timeout = 300


# ------------------------------------------------------------------ OSM ----
def _slug(bbox) -> str:
    return "_".join(f"{v:.4f}".replace("-", "m").replace(".", "p") for v in bbox)


def _pad_bbox(bbox, metres=BUFFER_M):
    """Grow a lat-lon bbox by roughly `metres` on every side."""
    w, s, e, n = bbox
    dlat = metres / 111_000.0
    dlon = metres / (111_000.0 * np.cos(np.radians((s + n) / 2)))
    return (w - dlon, s - dlat, e + dlon, n + dlat)


@lru_cache(maxsize=8)
def load_graph(bbox, epsg, network_type="drive", buffer_m=BUFFER_M):
    """Padded, simplified, projected OSM graph. Cached on disk and in process.

    The raw graph is cached unprojected, because that is the expensive part
    (Overpass plus topology simplification) and reprojection is seconds.
    """
    os.makedirs(OSM_DIR, exist_ok=True)
    padded = _pad_bbox(bbox, buffer_m)
    path = os.path.join(OSM_DIR, f"{_slug(bbox)}_{network_type}.graphml")
    if os.path.exists(path):
        G = ox.load_graphml(path)
    else:
        print(f"  downloading {network_type} network from OSM", flush=True)
        G = ox.graph_from_bbox(padded, network_type=network_type,
                               simplify=True, retain_all=True, truncate_by_edge=True)
        ox.save_graphml(G, path)
    return ox.project_graph(G, to_crs=f"EPSG:{epsg}")


def _flat(v):
    """OSM list-valued tags (a way merged during simplification) -> a string."""
    if isinstance(v, (list, tuple, set)):
        return ";".join(str(x) for x in v)
    return v


def street_segments(bbox, epsg, buffer_m=BUFFER_M):
    """Block faces between intersections, one row per undirected segment.

    `seg_id` is built from the two OSM node ids and the parallel-edge key, so it
    is stable across reruns and across the drive/walk graphs, and it survives a
    re-download as long as OSM has not re-nodded the street.
    """
    G = load_graph(tuple(bbox), epsg, "drive", buffer_m)
    e = ox.graph_to_gdfs(G, nodes=False).reset_index()

    lo = np.minimum(e["u"].values, e["v"].values)
    hi = np.maximum(e["u"].values, e["v"].values)
    e["seg_id"] = [f"{a}_{b}_{k}" for a, b, k in zip(lo, hi, e["key"].values)]

    # simplification merges ways, so tags arrive as lists; parquet needs one type
    for c in ("name", "highway", "osmid", "ref", "junction"):
        if c in e.columns:
            e[c] = e[c].map(_flat).astype("string")

    keep = [c for c in ("seg_id", "u", "v", "key", "osmid", "name", "highway",
                        "ref", "junction", "length", "geometry") if c in e.columns]
    segs = e[keep].drop_duplicates(subset="seg_id").reset_index(drop=True)
    segs = gpd.GeoDataFrame(segs, geometry="geometry", crs=G.graph["crs"])

    mid = segs.geometry.interpolate(0.5, normalized=True)
    segs["mid_x"], segs["mid_y"] = mid.x.values, mid.y.values

    # drop the padding: measures were computed with it, the sample excludes it
    core = gpd.GeoSeries(shapely.box(*bbox), crs=4326).to_crs(epsg).iloc[0]
    inside = shapely.intersects(core, shapely.points(segs["mid_x"], segs["mid_y"]))
    return segs[inside].reset_index(drop=True)


# ------------------------------------------------------------ topology ----
def _edge_geoms(G):
    """Edge geometries with reciprocal directed pairs collapsed.

    OSM stores a two-way street twice and a one-way street once. Counting or
    summing over the raw directed edges would therefore double every two-way
    link, which would make a one-way grid look half as dense as it is -- fatal
    for the walk/drive ratio, since walk networks are bidirectional throughout.
    """
    e = ox.graph_to_gdfs(G, nodes=False).reset_index()
    lo = np.minimum(e["u"].values, e["v"].values)
    hi = np.maximum(e["u"].values, e["v"].values)
    e["_key"] = [f"{a}_{b}_{k}" for a, b, k in zip(lo, hi, e["key"].values)]
    return e.drop_duplicates("_key").geometry.reset_index(drop=True)


def _undirected(G):
    """Simple undirected graph keeping the shortest of any parallel edges."""
    U = nx.Graph()
    for u, v, d in G.edges(data=True):
        if u == v:
            continue
        L = float(d.get("length", 0.0))
        if not U.has_edge(u, v) or U[u][v]["length"] > L:
            U.add_edge(u, v, length=L)
    return U


def _boundary_nodes(G, bbox, epsg, tol=BOUNDARY_TOL_M):
    """Nodes sitting on the cut edge of the padded download.

    Truncating a network manufactures degree-1 nodes that are not real dead
    ends. They are excluded from the dead-end and cul-de-sac logic so the
    artefact cannot propagate inward.
    """
    pad = _pad_bbox(bbox)
    rect = gpd.GeoSeries(shapely.box(*pad), crs=4326).to_crs(epsg).iloc[0]
    ring = shapely.get_exterior_ring(rect)
    ids = np.array(list(G.nodes))
    xy = np.array([[G.nodes[n]["x"], G.nodes[n]["y"]] for n in ids])
    d = shapely.distance(ring, shapely.points(xy[:, 0], xy[:, 1]))
    return set(ids[d < tol].tolist())


def _bc_one(segs, G, weight, k, seed):
    D = nx.DiGraph()
    for u, v, d in G.edges(data=True):
        w = float(d[weight])
        if not D.has_edge(u, v) or D[u][v]["w"] > w:
            D.add_edge(u, v, w=w)
    n = D.number_of_nodes()
    if k is None:
        k = None if n <= K_EXACT_MAX else min(K_SAMPLE, n)
    print(f"  edge betweenness by {weight} on {n:,} nodes"
          f" ({'exact' if k is None else f'k={k} sampled sources'})", flush=True)
    bc = nx.edge_betweenness_centrality(D, k=k, weight="w", seed=seed)
    return np.array([bc.get((u, v), 0.0) + bc.get((v, u), 0.0)
                     for u, v in zip(segs["u"], segs["v"])], dtype=np.float64)


def betweenness(segs, G, k=None, seed=BC_SEED):
    """Edge betweenness on the drive network: the proxy for through-traffic.

    Computed on a DiGraph, because one-ways are a real constraint on through-
    movement, then summed over both directions of each block face.

    Returned twice, under two path costs, and the difference is not cosmetic.

    `betweenness_len` uses metres. In San Francisco it does not find arterials:
    the top streets are Eureka, Clipper, Grand View and Congdon -- residential
    lanes over the Twin Peaks ridge. That is not a bug, it is what distance-
    shortest paths do in a city with a ridge through the middle. Every crossing
    of the ridge is forced through the handful of streets that go over it, while
    Van Ness and Geary sit in a grid where a dozen parallel routes substitute
    for each other and split the flow. Under this weighting Van Ness and Geary
    rank in the top 12-13% of named streets and Pine in the top 35%.

    `betweenness` uses travel time from OSM speed limits, with osmnx imputing a
    class mean where `maxspeed` is absent (in SF, 7,337 of 29,066 edges carry a
    mapped limit). Because speed tracks road class, time-shortest paths funnel
    onto arterials the way traffic actually does. The same streets then rank:
    19th Avenue top 1.7%, Oak 1.5%, Bush 1.9%, Fell 2.1%, Market 2.5%, Van Ness
    2.9%, Geary 4.7%, and the highest-scoring named roads are the Central
    Freeway, James Lick Freeway and Octavia Boulevard. The two orderings
    correlate at only rho = 0.68, so the choice matters.

    Travel time is the default because the variable under test is *exposure to
    passing offenders*, which is a claim about traffic, not about geometry. The
    distance version is kept because it is the literature's convention and
    because on this network it is close to a measure of terrain-forced routing
    -- interesting in its own right here, but confounded with the treatment.

    Sampling: k = K_SAMPLE pivot sources above K_EXACT_MAX nodes. Across seeds
    the segment ranking reproduces at rho = 0.96-0.98, which is ample given the
    variable enters as a covariate.
    """
    if "travel_time" not in next(iter(G.edges(data=True)))[2]:
        G = ox.add_edge_travel_times(ox.add_edge_speeds(G))
    return pd.DataFrame(
        {"betweenness": _bc_one(segs, G, "travel_time", k, seed),
         "betweenness_len": _bc_one(segs, G, "length", k, seed)},
        index=segs.index)


def dead_ends(segs, G, bbox, epsg):
    """`is_deadend` (a stub) and `cul_de_sac` (anywhere on a dead-end system).

    The distinction matters. A stub is the last block face; a cul-de-sac branch
    is every face you must traverse to reach it, all of which share the property
    the escape-route argument is about -- exactly one way out.

    Found by iteratively stripping degree-1 nodes: whatever falls off is a tree
    hanging from the through-network, i.e. a dead-end system.
    """
    U = _undirected(G)
    frozen = _boundary_nodes(G, bbox, epsg)

    deg = dict(U.degree())
    alive = {n: True for n in U}
    pruned = set()
    stack = [n for n, d in deg.items() if d <= 1 and n not in frozen]
    while stack:
        n = stack.pop()
        if not alive[n] or deg[n] > 1 or n in frozen:
            continue
        alive[n] = False
        for nb in U[n]:
            if not alive[nb]:
                continue
            pruned.add(frozenset((n, nb)))
            deg[nb] -= 1
            if deg[nb] <= 1 and nb not in frozen:
                stack.append(nb)

    def is_leaf(n):
        return n in U and U.degree(n) == 1 and n not in frozen

    stub = np.array([is_leaf(u) or is_leaf(v) for u, v in zip(segs["u"], segs["v"])], bool)
    cds = np.array([frozenset((u, v)) in pruned for u, v in zip(segs["u"], segs["v"])], bool)
    return stub, cds


def egress_count(segs, G, radius_m=EGRESS_R):
    """Independent ways out of the immediate vicinity, on the drive network.

    Counts the distinct nodes on the `radius_m` network-distance frontier: nodes
    reachable within the radius that have a neighbour beyond it. Each is a
    separate direction in which movement can continue, so 1 means trapped and 6
    means porous. Taken as the union over the segment's two endpoints, because
    either end is a way in.

    Computed on the drive network to keep it in the same family as betweenness
    and permeability. Foot-only escape is carried separately by
    `walk_drive_ratio` and `stairs_within_100m`.
    """
    U = _undirected(G)
    frontier = {}
    for n in U:
        seen = nx.single_source_dijkstra_path_length(U, n, cutoff=radius_m, weight="length")
        frontier[n] = {m for m in seen if any(nb not in seen for nb in U[m])}
    return np.array([len(frontier.get(u, set()) | frontier.get(v, set()))
                     for u, v in zip(segs["u"], segs["v"])], dtype=np.int32)


# -------------------------------------------------------- local density ----
def _edge_points(gdf, spacing=SAMPLE_M):
    """Points along every line, `spacing` apart, each carrying its share of the
    line's length.

    Turns "street length within r" into a weighted point sum. The alternative --
    clipping tens of thousands of buffers against tens of thousands of
    linestrings -- is two orders of magnitude slower for an answer that differs
    by less than the sampling interval.
    """
    geoms = gdf.values
    lens = gdf.length.values
    n = np.maximum(1, np.round(lens / spacing).astype(int))
    owner = np.repeat(np.arange(len(geoms)), n)
    pos = np.arange(len(owner)) - np.concatenate([[0], np.cumsum(n)])[owner]
    dist = (pos + 0.5) / n[owner] * lens[owner]
    xy = shapely.get_coordinates(shapely.line_interpolate_point(geoms[owner], dist))
    return xy[:, 0], xy[:, 1], lens[owner] / n[owner]


def _disk_sum(x, y, w, qx, qy, radius_m, cell=25.0):
    """Sum of point weights within `radius_m` of each query point.

    Accumulates the weights onto a helper grid and convolves with the same disk
    kernel `terrain.py` uses, which costs one FFT regardless of how many query
    points there are. Gridding at `cell` blurs the disk edge by half a cell; at
    a 400 m radius that is under a percent of the area.
    """
    ax = np.concatenate([x, qx])
    ay = np.concatenate([y, qy])
    pad = radius_m + 2 * cell
    x0, y0 = ax.min() - pad, ay.min() - pad
    nx = int((ax.max() + pad - x0) / cell) + 1
    ny = int((ay.max() + pad - y0) / cell) + 1
    grid = np.zeros((ny, nx), np.float32)
    np.add.at(grid, (((y - y0) / cell).astype(int), ((x - x0) / cell).astype(int)),
              w.astype(np.float32))
    dens = fftconvolve(grid, T.disk_kernel(radius_m / cell), mode="same")
    return dens[((qy - y0) / cell).astype(int), ((qx - x0) / cell).astype(int)]


def local_form(segs, Gd, Gw, radius_m=LOCAL_R):
    """Intersection density, permeability, and the walk/drive length ratio.

    All measured on a disk of `radius_m` around the segment midpoint.

    `permeability` counts street links crossing the disk boundary -- how many
    ways traffic can enter or leave the neighbourhood, which is the through-
    street idea without the arbitrariness of a "through street" definition.

    `walk_drive_ratio` is walk-network metres over drive-network metres in the
    same disk. Above 1 means places reachable on foot but not by car: paths,
    alleys, and in San Francisco, stairways.
    """
    mid = shapely.points(segs["mid_x"].values, segs["mid_y"].values)
    out = pd.DataFrame(index=segs.index)

    # intersections: OSM nodes where three or more streets meet
    sc = nx.get_node_attributes(Gd, "street_count")
    U = _undirected(Gd)
    xs, ys = [], []
    for n in Gd.nodes:
        if int(sc.get(n, U.degree(n) if n in U else 0)) >= 3:
            xs.append(Gd.nodes[n]["x"])
            ys.append(Gd.nodes[n]["y"])
    tree = cKDTree(np.column_stack([xs, ys]))
    npts = np.column_stack([segs["mid_x"].values, segs["mid_y"].values])
    n_int = tree.query_ball_point(npts, radius_m, return_length=True)
    out["intersection_density"] = n_int / (np.pi * (radius_m / 1000.0) ** 2)

    # permeability: links crossing the disk boundary
    rings = gpd.GeoSeries(shapely.get_exterior_ring(shapely.buffer(mid, radius_m)),
                          crs=segs.crs)
    de = _edge_geoms(Gd)
    hits = de.sindex.query(rings, predicate="intersects")
    out["permeability"] = np.bincount(hits[0], minlength=len(segs))

    # walk vs drive street length in the disk
    qx, qy = segs["mid_x"].values, segs["mid_y"].values
    for label, G in (("drive", Gd), ("walk", Gw)):
        x, y, w = _edge_points(_edge_geoms(G))
        out[f"{label}_len_400m"] = _disk_sum(x, y, w, qx, qy, radius_m)
    out["walk_drive_ratio"] = out["walk_len_400m"] / out["drive_len_400m"].replace(0, np.nan)
    return out


# --------------------------------------------------------------- stairs ----
def stairs(segs, bbox, epsg, radius_m=100.0, buffer_m=BUFFER_M):
    """Public staircases near the segment.

    The key asymmetric-access variable. A stairway changes pedestrian
    permeability without changing vehicle permeability at all, which is the one
    place a raster DEM can never see and the reason DIRECTION.md item 3 said
    directional cost needs a network. San Francisco has several hundred.

    `stairs_within_100m` is the requested count of `highway=steps` ways. Way
    counts are sensitive to how OSM has split a flight, so
    `stairs_len_100m` (metres of steps) is carried alongside as the robust form.
    """
    os.makedirs(OSM_DIR, exist_ok=True)
    path = os.path.join(OSM_DIR, f"{_slug(bbox)}_steps.parquet")
    if os.path.exists(path):
        st = gpd.read_parquet(path)
    else:
        print("  downloading highway=steps from OSM", flush=True)
        st = ox.features_from_bbox(_pad_bbox(bbox, buffer_m), tags={"highway": "steps"})
        st = st[["geometry"]].reset_index(drop=True)
        st.to_parquet(path)
    st = st.to_crs(segs.crs)
    st = st[st.geometry.notna() & ~st.geometry.is_empty].reset_index(drop=True)

    near = gpd.GeoSeries(segs.geometry.buffer(radius_m), crs=segs.crs)
    hits = st.geometry.sindex.query(near, predicate="intersects")
    count = np.bincount(hits[0], minlength=len(segs))
    length = np.bincount(hits[0], weights=st.geometry.length.values[hits[1]],
                         minlength=len(segs))
    return pd.DataFrame({"stairs_within_100m": count.astype(np.int32),
                         "stairs_len_100m": length}, index=segs.index)


# -------------------------------------------------------------- terrain ----
@dataclass
class Dem:
    z: np.ndarray
    valid: np.ndarray
    transform: object
    crs: object
    cell: float


def load_dem(path) -> Dem:
    if isinstance(path, Dem):
        return path
    with rasterio.open(path) as src:
        z = src.read(1).astype(np.float32)
        if src.nodata is not None:
            z[z == src.nodata] = np.nan
        valid = np.isfinite(z) & (z > WATER_CUTOFF)
        return Dem(z, valid, src.transform, src.crs, abs(src.transform.a))


def _raster_index(dem, x, y, crs):
    """Row/col of projected points in the DEM grid, plus an in-bounds mask."""
    if crs is not None and dem.crs is not None and str(crs) != str(dem.crs):
        tr = Transformer.from_crs(crs, dem.crs, always_xy=True)
        x, y = tr.transform(x, y)
    col = np.floor((x - dem.transform.c) / dem.transform.a).astype(np.int64)
    row = np.floor((y - dem.transform.f) / dem.transform.e).astype(np.int64)
    ok = (row >= 0) & (row < dem.z.shape[0]) & (col >= 0) & (col < dem.z.shape[1])
    return row, col, ok


def sample_points(segs, spacing=SAMPLE_M):
    """Points along every segment, `spacing` apart, with their owning segment.

    Terrain is sampled along the whole block face rather than at its midpoint: a
    segment can be 300 m long and climb 30 m, and the midpoint value would
    represent neither end.
    """
    geoms = segs.geometry.values
    lens = segs.geometry.length.values
    n = np.maximum(2, np.round(lens / spacing).astype(int) + 1)
    owner = np.repeat(np.arange(len(segs)), n)
    pos = np.arange(len(owner)) - np.concatenate([[0], np.cumsum(n)])[owner]
    frac = pos / (n[owner] - 1)
    pts = shapely.line_interpolate_point(geoms[owner], frac * lens[owner])
    xy = shapely.get_coordinates(pts)
    return xy[:, 0], xy[:, 1], owner


def sample_onto_segments(dem, segs, arrays, spacing=SAMPLE_M):
    """Segment means of raster fields, averaged over points along the face."""
    x, y, owner = sample_points(segs, spacing)
    row, col, ok = _raster_index(dem, x, y, segs.crs)
    row, col, owner = row[ok], col[ok], owner[ok]
    out = pd.DataFrame(index=segs.index)
    for name, a in arrays.items():
        v = a[row, col].astype(np.float64)
        good = np.isfinite(v)
        s = np.bincount(owner[good], weights=v[good], minlength=len(segs))
        n = np.bincount(owner[good], minlength=len(segs))
        out[name] = np.where(n > 0, s / np.maximum(n, 1), np.nan)
    return out


def terrain_stack(dem):
    """Elevation, slope and relative height, from src/terrain.py throughout."""
    z, valid, cell = dem.z, dem.valid, dem.cell
    out = {"elev": np.where(valid, z, np.nan).astype(np.float32),
           "slope_deg": np.where(valid, T.slope_degrees(z, cell), np.nan).astype(np.float32)}
    for r in TPI_RADII:
        out[f"tpi_{r}"] = T.tpi(z, valid, r, cell)
        out[f"tpiz_{r}"] = T.tpi_standardized(z, valid, r, cell)
    return out


def terrain_on_segments(dem, segs):
    dem = load_dem(dem)
    return sample_onto_segments(dem, segs, terrain_stack(dem))


def viewshed_proxy(dem, segments, radius_m=VIEW_R, n_dirs=36, n_rings=10):
    """Fraction of surrounding ground within `radius_m` that lies lower.

    A cheap stand-in for prospect: high values mean the place looks down on its
    surroundings and, symmetrically, is overlooked from nowhere nearby.

    Deliberately not a viewshed. A true ray-traced viewshed needs a line-of-
    sight march per cell per direction and, more importantly, would be measuring
    something the bare-earth DEM cannot support -- in a dense city, buildings,
    not terrain, decide what is visible, and this DEM has none. What this
    computes is the terrain-only, obstruction-free upper bound, and it should be
    read as relative height expressed as a share rather than as visibility.

    The disk is integrated on the same ring-and-spoke quadrature `terrain.py`
    uses for round-trip cost: 36 directions x 10 rings = 360 offsets, against
    ~7,900 pixels in a 500 m disk at 10 m. Offsets whose neighbour is water or
    off-raster are dropped from both numerator and denominator, so a clifftop
    above the Pacific is compared against the land beside it.

    Warning for the confirmatory arm: in San Francisco this correlates with
    tpi_500 at r = 0.80 and with `terrain.elevation_percentile(500 m)` at
    r = 0.91. It is close to a monotone transform of the treatment, so it cannot
    be entered as a mediator alongside TPI and read as "visibility net of
    height". Testing the visibility channel separately needs something with
    independent variation -- building heights, or a viewshed on a surface model
    rather than a bare-earth one.
    """
    dem = load_dem(dem)
    zf = np.where(dem.valid, dem.z, np.nan).astype(np.float32)
    lower = np.zeros(zf.shape, np.float32)
    total = np.zeros(zf.shape, np.float32)

    for ring in range(1, n_rings + 1):
        R = radius_m * ring / n_rings
        for k in range(n_dirs):
            th = 2 * np.pi * k / n_dirs
            dx = int(round(R * np.cos(th) / dem.cell))
            dy = int(round(R * np.sin(th) / dem.cell))
            if dx == 0 and dy == 0:
                continue
            zj = T._shift(zf, dy, dx)
            ok = np.isfinite(zj) & np.isfinite(zf)
            lower += (ok & (zf > zj)).astype(np.float32)
            total += ok.astype(np.float32)

    frac = np.where(dem.valid & (total > 0), lower / np.maximum(total, 1), np.nan)
    return sample_onto_segments(dem, segments,
                                {"viewshed_proxy": frac.astype(np.float32)})["viewshed_proxy"]


# ---------------------------------------------------------------- build ----
def build_segments(city, dem_path, bbox, epsg, out_path):
    """Segment table for one city, keyed by seg_id, ready to join crime to.

    Written as GeoParquet so the geometry survives: joining incidents to
    segments is a nearest-line operation, not a point-in-polygon, and needs the
    line.
    """
    print(f"[{city}] street segments", flush=True)
    segs = street_segments(bbox, epsg)
    Gd = load_graph(tuple(bbox), epsg, "drive")
    Gw = load_graph(tuple(bbox), epsg, "walk")
    print(f"  {len(segs):,} block faces"
          f" ({Gd.number_of_nodes():,} drive nodes in the padded graph)", flush=True)

    print(f"[{city}] network measures", flush=True)
    segs = segs.join(betweenness(segs, Gd))
    segs["egress_count"] = egress_count(segs, Gd)
    segs["is_deadend"], segs["cul_de_sac"] = dead_ends(segs, Gd, bbox, epsg)
    segs = segs.join(local_form(segs, Gd, Gw))
    segs = segs.join(stairs(segs, bbox, epsg))

    print(f"[{city}] terrain", flush=True)
    dem = load_dem(dem_path)
    if str(dem.crs) != f"EPSG:{epsg}":
        print(f"  note: DEM is {dem.crs}, segments are EPSG:{epsg};"
              " sample points are transformed", flush=True)
    segs = segs.join(terrain_on_segments(dem, segs))
    segs["viewshed_proxy"] = viewshed_proxy(dem, segs)

    segs["seg_len_m"] = segs.geometry.length
    segs["city"] = city
    segs = segs.drop(columns=["u", "v", "key"])

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    segs.to_parquet(out_path, index=False)
    print(f"[{city}] wrote {out_path}  ({len(segs):,} segments)", flush=True)
    return segs


if __name__ == "__main__":
    build_segments(
        city="San Francisco",
        dem_path="data/raw/dem/data_sfgov_org.tif",
        # the SFPD incident bbox from data/interim/registry.csv, robust percentiles
        bbox=(-122.502975, 37.709541, -122.379507, 37.806864),
        epsg=32610,
        out_path="data/interim/segments/sf_segments.parquet",
    )
