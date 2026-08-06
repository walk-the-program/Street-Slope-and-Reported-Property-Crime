"""Harvest incident-level crime from ArcGIS Feature Services (and CKAN).

Why this file exists: `discover.py` walks the Socrata catalog, and Socrata skews
flat. Most US cities with real topography -- Pittsburgh, Denver, Baltimore,
Chattanooga, Asheville -- publish crime on ArcGIS instead, so the terrain half of
this study was starved of variation until these portals were reachable.

Three stages, mirroring discover.py -> harvest.py:

  discover()      catalog sweep (ArcGIS Hub + ArcGIS Online) plus a directory
                  crawl of city-run REST servers, which Hub does not index
  build_registry()  probe every candidate layer live and keep the survivors
  fetch_city_arcgis(row)  download one city, same contract as harvest.fetch_crime

Two conventions worth knowing before reading further:

  * `url` in the registry may hold several layer URLs joined by "|". Several
    cities (Louisville, Baltimore, Syracuse) shard crime across one service per
    year, so a single city genuinely needs several endpoints. Keeping them in
    one field preserves "one row per city" for the caller.

  * `url` may instead be `ckan://<host>/<resource_id>`. Pittsburgh -- the single
    most useful city in the priority list, given its topography -- has no live
    ArcGIS incident layer, only a CKAN datastore. Supporting one extra protocol
    was cheaper than losing the city.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))
from crime_classes import PROPERTY_CLASSES, classify_text

OUT = "data/interim/registry_arcgis.csv"
START_DATE = "2018-01-01"
MAX_ROWS = 600_000
MIN_LAYER_ROWS = 6_000
TIMEOUT = 180

HUB = "https://hub.arcgis.com/api/v3/datasets"
AGO = "https://www.arcgis.com/sharing/rest/search"

_S = requests.Session()
_S.headers["User-Agent"] = "crime-altitude-research/1.0"


# ---------------------------------------------------------------- cities ----
# Approximate city centres. These are a sanity gate, not data: ArcGIS Hub search
# for "<city> crime" happily returns another state's police layer, and a service
# whose points sit 200 km away is the single most common false positive. Nothing
# downstream reads these numbers.
CITY_CENTERS = {
    "Pittsburgh": (40.44, -79.99), "Seattle": (47.61, -122.33),
    "Portland OR": (45.52, -122.68), "Baltimore": (39.29, -76.61),
    "Denver": (39.74, -104.99), "Tacoma": (47.25, -122.44),
    "Spokane": (47.66, -117.43), "Louisville": (38.25, -85.76),
    "Nashville": (36.16, -86.78), "Charlotte": (35.23, -80.84),
    "Knoxville": (35.96, -83.92), "Chattanooga": (35.05, -85.31),
    "Birmingham AL": (33.52, -86.80), "Syracuse": (43.05, -76.15),
    "Albany NY": (42.65, -73.76), "Worcester MA": (42.26, -71.80),
    "Providence": (41.82, -71.41), "New Haven": (41.31, -72.93),
    "Honolulu": (21.31, -157.86), "Anchorage": (61.22, -149.90),
    "Boise": (43.62, -116.20), "Salt Lake City": (40.76, -111.89),
    "Colorado Springs": (38.83, -104.82), "Albuquerque": (35.08, -106.65),
    "San Diego": (32.72, -117.16), "Oakland": (37.80, -122.27),
    "Berkeley": (37.87, -122.27), "Pasadena": (34.15, -118.14),
    "Glendale CA": (34.14, -118.25), "Long Beach": (33.77, -118.19),
    "Cincinnati": (39.10, -84.51), "Duluth": (46.79, -92.10),
    "Charleston WV": (38.35, -81.63), "Roanoke": (37.27, -79.94),
    "Asheville": (35.60, -82.55), "Santa Fe": (35.69, -105.94),
    "Reno": (39.53, -119.81), "Eugene": (44.05, -123.09),
}

# City-run ArcGIS servers. ArcGIS Hub only indexes ArcGIS Online, so a city that
# runs its own server (Charlotte, Asheville, Portland, Albuquerque) is invisible
# to catalogue search no matter how the query is worded -- it has to be crawled.
CRAWL_ROOTS = {
    "Charlotte": ["https://gis.charlottenc.gov/arcgis/rest/services"],
    "Asheville": ["https://gis.ashevillenc.gov/server/rest/services"],
    "Portland OR": ["https://www.portlandmaps.com/arcgis/rest/services"],
    "Albuquerque": ["https://coageo.cabq.gov/cabqgeo/rest/services",
                    "https://coagisweb.cabq.gov/arcgis/rest/services"],
    "Baltimore": ["https://services1.arcgis.com/UWYHeuuJISiGmgXx/arcgis/rest/services"],
    "Denver": ["https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services"],
    "Chattanooga": ["https://services2.arcgis.com/OIAIimblRxPs0xxc/arcgis/rest/services"],
    "Louisville": ["https://services1.arcgis.com/79kfd2K6fskCAkyg/arcgis/rest/services"],
    "Syracuse": ["https://services6.arcgis.com/bdPqSfflsdgFRVVM/arcgis/rest/services"],
    "Boise": ["https://services1.arcgis.com/WHM6qC35aMtyAAlN/arcgis/rest/services"],
    "Nashville": ["https://services1.arcgis.com/KUeKSLlMUcWvuPRM/arcgis/rest/services"],
    "Colorado Springs": ["https://gis.coloradosprings.gov/arcgis/rest/services"],
    "Knoxville": ["https://gis.knoxvilletn.gov/arcgis/rest/services"],
    "Seattle": ["https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services"],
    "Tacoma": ["https://services1.arcgis.com/WGzzp37bqYMLyzDR/arcgis/rest/services"],
    "Long Beach": ["https://services6.arcgis.com/yCArG7wGXGyWLqav/arcgis/rest/services"],
    "Duluth": ["https://services.arcgis.com/DgKyOSWnVuXUe0Jp/arcgis/rest/services"],
    "Honolulu": ["https://services.arcgis.com/tNJpAOha4mODLkXz/arcgis/rest/services"],
}

# CKAN datastores, added by hand because CKAN has no cross-portal catalogue to
# sweep. Only cities that ArcGIS discovery cannot reach are listed.
CKAN_SOURCES = {
    "Pittsburgh": ("data.wprdc.org", "044f2016-1dfd-4ab0-bc1e-065da05fca2e"),
}

_GOOD = re.compile(r"(crime|incident|offen[cs]e|police|arrest|theft|burglar|larceny|"
                   r"blotter|nibrs|ucr|part.?1)", re.I)
# Aggregated geographies and non-crime incident feeds. "fire" and "ems" matter:
# fire-incident layers are large, point-based and date-stamped, so they clear
# every structural test and are only excluded by name.
_BAD = re.compile(r"(density|kernel|heat|hot.?spot|per.?capita|neighborhood|block|tract|"
                  r"beat|district|boundar|zone|precinct|summar|aggregat|choropleth|"
                  r"buffer|parcel|school|centroid|station|office|camera|fire|ems|"
                  r"medical|weather|traffic|crash|accident|shooting|homicide)", re.I)

_DATE_RE = re.compile(r"(date|datetime|occur|report|time)", re.I)
# "INCIDENT_REPORT_ID" matches the date rule on "report", and Charlotte's report
# ids begin with the year, so a lexicographic >= '2018-01-01' test even returns a
# believable count. Identifier-looking names are excluded outright.
_NOT_DATE_RE = re.compile(r"(_id$|^id$|number|num$|code|zip|badge|case|report_?id)", re.I)
_DESC_RE = re.compile(r"(desc|offen|categ|type|crime|nibrs|ucr|charge|statute|text|"
                      r"narrat|classif|title|nature|hierarchy)", re.I)
_LAT_RE = re.compile(r"^((geo|map|pt|point|incident)_?)?(lat|latitude|y|ycoord|y_coord|lat_?y)"
                     r"(_?(public|wgs84|dd))?$", re.I)
_LON_RE = re.compile(r"^((geo|map|pt|point|incident)_?)?(lon|long|lng|longitude|x|xcoord|"
                     r"x_coord|lon_?x)(_?(public|wgs84|dd))?$", re.I)

# Widest plausible half-extent of a US city's incident cloud, in degrees.
LAT_PAD, LON_PAD = 1.0, 1.5


# ------------------------------------------------------------- transport ----
_SEP_RE = re.compile(r"[-_/|]+")


def norm_text(v):
    """Collapse separators to spaces before classification.

    Not a taxonomy change -- `classify_text` stays the only authority on what a
    description means. It matches on word boundaries, so a department that
    publishes slugs rather than prose is silently misread: Denver's
    "criminal-mischief-other" falls through to OTHER instead of NO_LOOT, and
    "theft-of-motor-vehicle" lands in MASS_3 instead of MVT. Since NO_LOOT is
    the study's control class, dropping it for every slug-publishing city would
    quietly gut the comparison that matters most.
    """
    return _SEP_RE.sub(" ", str(v or ""))


def clean_points(df):
    """Drop null-island sentinels and impossible dates.

    Portals encode "no geocode" as a value, not as a null, and the value is not
    always literal zero -- Baltimore and Pittsburgh both ship coordinates around
    5e-14, which survive a `!= 0` test and then drag a city's bounding box to the
    Gulf of Guinea. The DEM is fetched from that box, so one surviving sentinel
    ruins the whole city. Anchoring on the median is robust: real incidents are
    overwhelmingly in one metro, so the median is always inside it, and anything
    a degree away is a sentinel or a mis-geocode either way.

    Dates get the same treatment. Several services carry typo'd years (Baltimore
    has records stamped 1023, Charlotte 0200), and an epoch-millisecond column
    read as a string silently becomes a date in 1970.
    """
    df = df[df.lat.between(-90, 90) & df.lon.between(-180, 180)].copy()
    if df.empty:
        return df
    mla, mlo = float(df.lat.median()), float(df.lon.median())
    df = df[df.lat.sub(mla).abs().le(LAT_PAD) & df.lon.sub(mlo).abs().le(LON_PAD)]

    if getattr(df["date"].dtype, "tz", None) is not None:
        df["date"] = df["date"].dt.tz_localize(None)
    now = pd.Timestamp.now() + pd.Timedelta("2D")
    return df[df.date.between(pd.Timestamp("2000-01-01"), now)].copy()


def _get(url, params, tries=3, timeout=TIMEOUT, esri=True):
    """GET returning parsed JSON, retrying transient failures.

    ArcGIS servers return 200 with an `error` body as often as they return a
    real HTTP error, so both shapes are raised here and handled by the caller.
    """
    last = None
    for i in range(tries):
        try:
            p = dict(params)
            if esri:
                p.setdefault("f", "json")  # CKAN rejects an unknown `f` with a 409
            r = _S.get(url, params=p, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"http {r.status_code}")
            r.raise_for_status()
            d = r.json()
            if isinstance(d, dict) and "error" in d:
                raise RuntimeError(str(d["error"])[:150])
            return d
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{type(last).__name__}: {str(last)[:150]}")


def layer_info(url):
    return _get(url, {})


def _count(url, where):
    return _get(url + "/query", {"where": where, "returnCountOnly": "true"}).get("count")


# ------------------------------------------------------------ where-clause --
def date_where(url, field, is_epoch, iso, total=None):
    """Return a WHERE clause selecting rows on/after `iso`, or None.

    Date literal syntax is not portable across ArcGIS backends -- hosted feature
    services take `DATE 'x'`, some ArcGIS Server/SQL layers only take
    `TIMESTAMP 'x y'`, and string-typed date columns need a plain quoted
    comparison. Rather than guess from the field type, each form is tried
    against a live count and the first one that answers plausibly wins.
    """
    forms = ([f"{field} >= DATE '{iso}'", f"{field} >= TIMESTAMP '{iso} 00:00:00'",
              f"{field} >= '{iso}'"] if is_epoch
             else [f"{field} >= '{iso}'", f"{field} >= DATE '{iso}'",
                   f"{field} >= TIMESTAMP '{iso} 00:00:00'"])
    for w in forms:
        try:
            n = _count(url, w)
        except Exception:
            continue
        if n is None:
            continue
        # A form that matches every row is a sign the comparison degraded to a
        # no-op. Only the caller knows whether that is suspicious: it passes
        # `total` just when the layer really does hold records before `iso`.
        # Baltimore's NIBRS series starts in 2022, so matching all of it is
        # correct, and testing this unconditionally rejected the whole city.
        if total and n >= total:
            continue
        return w, n
    return None, None


# -------------------------------------------------------------- discovery ---
def _hub_search(q, n=40):
    try:
        d = _get(HUB, {"q": q, "page[size]": n,
                       "fields[datasets]": "name,url,owner,recordCount"}, tries=2, timeout=90)
        return [x["attributes"] for x in d.get("data", [])]
    except Exception:
        return []


def _ago_search(q, n=50):
    try:
        d = _get(AGO, {"q": q, "num": n}, tries=2, timeout=90)
        return [{"name": x.get("title"), "url": x.get("url"), "owner": x.get("owner")}
                for x in d.get("results", []) if x.get("type") in ("Feature Service", "Map Service")]
    except Exception:
        return []


def _crawl(root, depth=0):
    """Walk an ArcGIS REST service directory, returning crime-looking services."""
    hits = []
    try:
        d = _get(root, {}, tries=2, timeout=60)
    except Exception:
        return hits
    base = root.split("/rest/services")[0] + "/rest/services"
    for s in d.get("services") or []:
        name = s["name"].split("/")[-1]
        if s.get("type") in ("FeatureServer", "MapServer") and _GOOD.search(name) \
                and not _BAD.search(name):
            hits.append(f"{base}/{s['name']}/{s['type']}")
    if depth < 2:
        for f in d.get("folders") or []:
            hits += _crawl(root.rstrip("/") + "/" + f, depth + 1)
    return hits


def discover(city):
    """Candidate service URLs for one city, from catalogue search and crawling."""
    out, seen = [], set()

    def add(name, url, owner):
        url = (url or "").rstrip("/")
        if "/rest/services/" not in url or url.lower() in seen:
            return
        label = f"{name or ''} {url}"
        if not _GOOD.search(label) or _BAD.search(str(name or "")):
            return
        seen.add(url.lower())
        out.append({"city": city, "name": name, "url": url, "owner": owner})

    for q in (f"{city} crime incidents", f"{city} police incidents", f"{city} crime"):
        for a in _hub_search(q) + _ago_search(q):
            add(a.get("name"), a.get("url"), a.get("owner"))
    for root in CRAWL_ROOTS.get(city, []):
        for u in _crawl(root):
            add(u.split("/")[-2], u, "crawl")
    return out


def expand_service(cand):
    """Service URL -> its point layer URLs. A layer URL passes through."""
    u = cand["url"]
    if re.search(r"/(Feature|Map)Server/\d+$", u):
        return [dict(cand, url=u)]
    if not re.search(r"/(Feature|Map)Server$", u):
        return []
    try:
        d = _get(u, {}, tries=2, timeout=60)
    except Exception:
        return []
    ids = [l["id"] for l in (d.get("layers") or [])
           if l.get("geometryType") in (None, "esriGeometryPoint")]
    return [dict(cand, url=f"{u}/{i}") for i in ids[:8]]


# ------------------------------------------------------- field selection ----
def score_desc_fields(records, names):
    """Rank string fields by how often `classify_text` recognises their values.

    Field naming is not a reliable guide to which column holds the offense.
    Charlotte's incident layer offers ADDRESS_DESCRIPTION, LOCATION_TYPE_-
    DESCRIPTION, PLACE_TYPE_DESCRIPTION and HIGHEST_NIBRS_DESCRIPTION; only the
    last is an offense, and a name-based rule picks the first. So the choice is
    made from the data: sample rows and keep the columns whose values the
    project's own classifier actually resolves.

    The score is the share of values landing in any non-OTHER class, which is
    neutral across the loot-mass ladder -- it cannot tilt the taxonomy toward a
    particular class, only toward columns that describe offenses at all.
    """
    scored = []
    for n in names:
        vals = [str(r.get(n) or "") for r in records]
        vals = [v for v in vals if v and v.lower() not in ("none", "nan", "null")]
        if len(vals) < 20:
            continue
        uniq = len(set(vals)) / len(vals)
        hit = np.mean([classify_text(norm_text(v))[0] != "OTHER" for v in vals])
        # Near-unique columns are free text (addresses, narratives, case numbers):
        # they can score well by accident and add noise to the concatenation.
        if uniq > 0.6:
            hit *= 0.3
        scored.append((hit, n))
    scored.sort(reverse=True)
    return [(n, round(float(h), 3)) for h, n in scored if h > 0.15][:3]


def _pick_date_field(url, fields, ftypes, cands, total, sample=None):
    """Choose the date field with the widest sane, populated range.

    Occurrence beats report beats clearance when both are usable, because the
    study places incidents in space and time at the event, not at the paperwork.
    """
    best = None
    for f in cands[:8]:
        is_epoch = ftypes.get(f) == "esriFieldTypeDate"
        # A string column only counts as a date if its values really parse as
        # dates spanning more than a day -- the count test alone cannot tell a
        # date from a year-prefixed identifier.
        if not is_epoch:
            vals = [r.get(f) for r in (sample or []) if r.get(f) not in (None, "")]
            p = pd.to_datetime(pd.Series(vals, dtype="object"), errors="coerce", format="mixed")
            if len(p) < 20 or p.notna().mean() < 0.8 or p.dt.normalize().nunique() < 2:
                continue
        try:
            st = _get(url + "/query", {"where": "1=1", "outStatistics": json.dumps(
                [{"statisticType": "min", "onStatisticField": f, "outStatisticFieldName": "mn"},
                 {"statisticType": "max", "onStatisticField": f, "outStatisticFieldName": "mx"}])},
                tries=2)
            a = st["features"][0]["attributes"]
            unit = "ms" if is_epoch else None
            mn = pd.to_datetime(a.get("mn"), unit=unit, errors="coerce")
            mx = pd.to_datetime(a.get("mx"), unit=unit, errors="coerce")
        except Exception:
            continue
        mn = mn.tz_localize(None) if getattr(mn, "tzinfo", None) else mn
        mx = mx.tz_localize(None) if getattr(mx, "tzinfo", None) else mx
        if pd.isna(mx) or not (pd.Timestamp("1990") < mx < pd.Timestamp.now() + pd.Timedelta("400D")):
            continue
        has_older = bool(pd.notna(mn) and mn < pd.Timestamp(START_DATE))
        where, n = date_where(url, f, is_epoch, START_DATE, total if has_older else None)
        if not where or not n:
            continue
        # Occurrence beats report time, but only when the column is actually
        # filled: Denver offers LAST_OCCURRENCE_DATE, which is null for most
        # incidents and would silently discard them.
        cover = 1.0
        if sample:
            cover = np.mean([r.get(f) not in (None, "") for r in sample])
            if cover < 0.5:
                continue
        bonus = 1.15 if re.search(r"(occur|incident|began|start)", f, re.I) else 1.0
        score = n * bonus * cover
        if best is None or score > best["score"]:
            best = {"field": f, "epoch": is_epoch, "rows": n, "score": score,
                    "dmin": str(mn)[:10], "dmax": str(mx)[:10]}
    return best


def probe_layer(cand):
    """Verify one layer live and describe how to read it. Never raises."""
    url = cand["url"]
    out = dict(cand)
    try:
        m = layer_info(url)
    except Exception as e:
        out["err"] = f"meta {e}"
        return out
    if m.get("geometryType") not in (None, "esriGeometryPoint"):
        out["err"] = "not points"
        return out

    fields = m.get("fields") or []
    names = [f["name"] for f in fields]
    ftypes = {f["name"]: f["type"] for f in fields}
    out["layer_name"] = m.get("name")
    out["lat_field"] = next((n for n in names if _LAT_RE.match(n)), "")
    out["lon_field"] = next((n for n in names if _LON_RE.match(n)), "")
    # A Table has no shape, but several portals publish incidents as a table
    # carrying latitude/longitude columns, which is just as usable.
    if m.get("type") == "Table" and not (out["lat_field"] and out["lon_field"]):
        out["err"] = "table without coordinates"
        return out
    if m.get("type") not in (None, "Feature Layer", "Table"):
        out["err"] = "not a feature layer"
        return out
    date_c = [n for n in names if _DATE_RE.search(n)
              and ftypes[n] in ("esriFieldTypeDate", "esriFieldTypeString")]
    str_c = [n for n in names if ftypes[n] == "esriFieldTypeString"]
    desc_c = [n for n in names if _DESC_RE.search(n) and ftypes[n] == "esriFieldTypeString"]
    if not date_c or not str_c:
        out["err"] = "no date or text fields"
        return out

    try:
        total = _count(url, "1=1")
    except Exception as e:
        out["err"] = f"count {e}"
        return out
    out["total"] = total
    if not total or total < MIN_LAYER_ROWS:
        out["err"] = f"only {total} rows"
        return out

    # Sample from four points in the table, not one. Rows come back in object-id
    # order, which for most crime layers is load order, so a single page is one
    # contiguous slab -- Denver's first 600 rows are all the same offense code,
    # which makes every description field look worthless.
    feats = []
    for frac in (0.0, 0.25, 0.5, 0.75):
        q = {"where": "1=1", "outFields": "*", "resultRecordCount": 200,
             "outSR": 4326, "returnGeometry": "true"}
        if frac:
            q["resultOffset"] = int(total * frac)
        try:
            feats += (_get(url + "/query", q, tries=2).get("features") or [])
        except Exception as e:
            if not feats:
                out["err"] = f"sample {e}"
                return out
            break
    recs = [f.get("attributes") or {} for f in feats]
    xs = [f["geometry"]["x"] for f in feats
          if (f.get("geometry") or {}).get("x") is not None]
    ys = [f["geometry"]["y"] for f in feats
          if (f.get("geometry") or {}).get("y") is not None]

    if not xs and out["lat_field"] and out["lon_field"]:
        xs = [r.get(out["lon_field"]) for r in recs]
        ys = [r.get(out["lat_field"]) for r in recs]
    xs = [float(v) for v in xs if v not in (None, "") and -180 <= float(v) <= 180]
    ys = [float(v) for v in ys if v not in (None, "") and -90 <= float(v) <= 90]
    if len(xs) < 20 or len(ys) < 20:
        out["err"] = "no usable coordinates"
        return out
    # Strip null-island sentinels before they set the reported extent.
    cy, cx = float(np.median(ys)), float(np.median(xs))
    ys = [v for v in ys if abs(v - cy) <= LAT_PAD]
    xs = [v for v in xs if abs(v - cx) <= LON_PAD]

    clat, clon = CITY_CENTERS[cand["city"]]
    off = math.hypot(cy - clat, (cx - clon) * math.cos(math.radians(clat)))
    out["deg_off"] = round(off, 3)
    if off > 0.45:
        out["err"] = f"points at {cy:.2f},{cx:.2f}, not this city"
        return out
    out["mnla"], out["mxla"] = [float(v) for v in np.percentile(ys, [0.5, 99.5])]
    out["mnlo"], out["mxlo"] = [float(v) for v in np.percentile(xs, [0.5, 99.5])]

    picks = score_desc_fields(recs, desc_c or str_c)
    if not picks:
        out["err"] = "no field classifies as an offense"
        return out
    out["desc_fields"] = ";".join(n for n, _ in picks)
    out["desc_score"] = picks[0][1]

    # Whether the layer reports vandalism/criminal damage at all. Baltimore
    # offers a longer UCR Part 1 series and a shorter NIBRS Group A one, and only
    # NIBRS carries vandalism -- Part 1 is defined to exclude it. NO_LOOT is the
    # study's control class, so a layer that can never populate it is the wrong
    # choice however many rows it has.
    kl = [classify_text(norm_text(" ".join(str(r.get(n) or "") for n, _ in picks)))[0]
          for r in recs]
    prop = [k for k in kl if k in PROPERTY_CLASSES]
    # A share, not a count: Baltimore's Part 1 series does contain arson, so a
    # count test calls it NO_LOOT-bearing on a handful of rows, and the class
    # then lands at 0.5% of incidents -- far too thin to control anything.
    out["no_loot_share"] = round(sum(k == "NO_LOOT" for k in prop) / max(len(prop), 1), 3)
    out["no_loot"] = out["no_loot_share"] >= 0.03
    out["prop_share"] = round(float(np.mean([k in PROPERTY_CLASSES for k in kl])), 3)

    date_c = [n for n in date_c if not _NOT_DATE_RE.search(n)]
    d = _pick_date_field(url, fields, ftypes, date_c, total, recs)
    if not d:
        out["err"] = "no usable date field"
        return out
    # `rows` counts only the study window, so report the window's start, not the
    # layer's earliest record -- several services carry typo'd dates in year 1023.
    out.update({"date_field": d["field"], "rows": d["rows"],
                "date_min": max(d["dmin"], START_DATE), "date_max": d["dmax"]})
    if d["rows"] < MIN_LAYER_ROWS:
        out["err"] = f"only {d['rows']} rows since {START_DATE}"
        return out
    if d["dmax"] < "2019-01-01":
        out["err"] = f"stale, ends {d['dmax']}"
        return out
    # A rolling live feed (San Diego's is a single day) has no history to study.
    span = (pd.Timestamp(d["dmax"]) - pd.Timestamp(max(d["dmin"], START_DATE))).days
    if span < 180:
        out["err"] = f"only {span}d of history"
        return out
    return out


# --------------------------------------------------------------- registry ---
def _ckan_probe(city, host, rid):
    """Profile a CKAN datastore resource the same way as an ArcGIS layer."""
    base = f"https://{host}/api/3/action"
    out = {"city": city, "url": f"ckan://{host}/{rid}", "owner": "ckan"}
    try:
        d = _get(f"{base}/datastore_search", {"resource_id": rid, "limit": 800},
                 esri=False)["result"]
    except Exception as e:
        out["err"] = f"ckan {e}"
        return out
    recs = d["records"]
    names = [f["id"] for f in d["fields"] if f["type"] in ("text", "json")]
    lat = next((n for n in d["fields"] if _LAT_RE.match(n["id"])), None)
    lon = next((n for n in d["fields"] if _LON_RE.match(n["id"])), None)
    date = next((f["id"] for f in d["fields"] if _DATE_RE.search(f["id"])), None)
    if not (lat and lon and date):
        out["err"] = "ckan missing lat/lon/date"
        return out
    picks = score_desc_fields(recs, [n for n in names if _DESC_RE.search(n)] or names)
    if not picks:
        out["err"] = "ckan no offense field"
        return out
    pts = pd.DataFrame({"lat": pd.to_numeric([r.get(lat["id"]) for r in recs], errors="coerce"),
                        "lon": pd.to_numeric([r.get(lon["id"]) for r in recs], errors="coerce"),
                        "date": pd.Timestamp("2020-01-01")})
    pts = clean_points(pts)  # WPRDC stores un-geocoded incidents as ~5e-14, not null
    ys, xs = pts.lat.tolist(), pts.lon.tolist()
    if len(xs) < 20:
        out["err"] = "ckan no usable coordinates"
        return out
    sql = (f'SELECT count(*) n, min("{date}") a, max("{date}") b FROM "{rid}" '
           f"WHERE \"{date}\" >= '{START_DATE}'")
    try:
        r = _get(f"{base}/datastore_search_sql", {"sql": sql}, esri=False)["result"]["records"][0]
    except Exception as e:
        out["err"] = f"ckan sql {e}"
        return out
    kl = [classify_text(norm_text(" ".join(str(r.get(n) or "") for n, _ in picks)))[0]
          for r in recs]
    prop = [k for k in kl if k in PROPERTY_CLASSES]
    nl = round(sum(k == "NO_LOOT" for k in prop) / max(len(prop), 1), 3)
    out.update({"no_loot_share": nl, "no_loot": nl >= 0.03,
                "prop_share": round(float(np.mean([k in PROPERTY_CLASSES for k in kl])), 3)})
    out.update({"layer_name": rid[:8], "lat_field": lat["id"], "lon_field": lon["id"],
                "date_field": date, "desc_fields": ";".join(n for n, _ in picks),
                "desc_score": picks[0][1], "rows": int(r["n"]),
                "date_min": str(r["a"])[:10], "date_max": str(r["b"])[:10],
                "mnla": float(np.percentile(ys, 0.5)), "mxla": float(np.percentile(ys, 99.5)),
                "mnlo": float(np.percentile(xs, 0.5)), "mxlo": float(np.percentile(xs, 99.5)),
                "deg_off": 0.0, "total": int(r["n"])})
    return out


def _merge_city(city, layers):
    """Collapse a city's surviving layers into one registry row.

    A city is kept as several endpoints only when they are complementary rather
    than redundant -- Louisville and Syracuse publish one service per year, so
    the largest single layer covers a fraction of the study window. Layers are
    added newest-first while each one extends the date range already covered.
    """
    layers = sorted(layers, key=lambda r: (r.get("no_loot", False), r["date_max"], r["rows"]),
                    reverse=True)
    keep, covered = [], []

    def overlaps(a, b):
        return not (a["date_max"] < b["date_min"] or b["date_max"] < a["date_min"])

    for l in layers:
        if any(overlaps(l, k) for k in keep):
            continue
        # Only extend a city with shards from the same portal. A non-overlapping
        # date range from a stranger's org is far more often an abandoned student
        # copy than a genuine earlier shard -- Denver's gap before 2021 is filled
        # by exactly such a layer, and it is not the city's data.
        if keep and l["url"].split("/")[2] != keep[0]["url"].split("/")[2]:
            continue
        keep.append(l)
    # Redundant duplicates of the best layer are common (a FeatureServer and a
    # MapServer view of one table); the overlap rule above already drops them.
    keep = keep[:6]
    rows = sum(k["rows"] for k in keep)
    return {
        "city": city,
        "url": "|".join(k["url"] for k in keep),
        "date_field": ";".join(dict.fromkeys(k["date_field"] for k in keep)),
        "desc_fields": ";".join(dict.fromkeys(
            f for k in keep for f in k["desc_fields"].split(";"))),
        "lat_field": keep[0].get("lat_field") or "",
        "lon_field": keep[0].get("lon_field") or "",
        "rows": rows,
        "mnla": min(k["mnla"] for k in keep), "mxla": max(k["mxla"] for k in keep),
        "mnlo": min(k["mnlo"] for k in keep), "mxlo": max(k["mxlo"] for k in keep),
        "date_min": min(k["date_min"] for k in keep),
        "date_max": max(k["date_max"] for k in keep),
        "n_layers": len(keep),
        "desc_score": keep[0]["desc_score"],
    }


def build_registry(cities=None, workers=12, out=OUT):
    cities = list(cities or CITY_CENTERS)
    cands = []
    with ThreadPoolExecutor(workers) as ex:
        for c in ex.map(discover, cities):
            cands += c
    print(f"{len(cands)} candidate services", flush=True)

    layers, seen = [], set()
    with ThreadPoolExecutor(workers) as ex:
        for group in ex.map(expand_service, cands):
            for l in group:
                # Dedupe within a city, not globally: catalogue search for one
                # city routinely returns another city's layer, and a global key
                # lets the wrong city claim it and then fail the location test.
                key = (l["city"], l["url"].lower())
                if key in seen:
                    continue
                seen.add(key)
                layers.append(l)
    print(f"{len(layers)} layers to probe", flush=True)

    probed = []
    with ThreadPoolExecutor(workers) as ex:
        for i, r in enumerate(ex.map(probe_layer, layers), 1):
            probed.append(r)
            if i % 100 == 0:
                print(f"   probed {i}/{len(layers)}", flush=True)
    for city, (host, rid) in CKAN_SOURCES.items():
        if city in cities:
            probed.append(_ckan_probe(city, host, rid))

    ok = [r for r in probed if not r.get("err")]
    print(f"\n{len(ok)} layers verified", flush=True)
    by_city = {}
    for r in ok:
        by_city.setdefault(r["city"], []).append(r)
    reg = pd.DataFrame([_merge_city(c, v) for c, v in sorted(by_city.items())])
    reg = reg[reg.rows >= 10_000].sort_values("rows", ascending=False).reset_index(drop=True)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    reg.to_csv(out, index=False)
    print(f"{len(reg)} cities -> {out}")
    return reg, probed


# ------------------------------------------------------------------ fetch ---
def _page_layer(url, where, out_fields, cap):
    """Download matching rows, most recent first, honouring maxRecordCount.

    Offset paging needs a deterministic sort or the server may repeat and skip
    rows between pages, so results are ordered by object id -- the one field
    every service can sort on. Where the service declares no pagination support,
    the offset is replaced by an object-id window, which needs no support at all.
    """
    m = layer_info(url)
    oid = m.get("objectIdField") or "OBJECTID"
    page = min(int(m.get("maxRecordCount") or 1000), 2000)
    adv = m.get("advancedQueryCapabilities") or {}
    paged = adv.get("supportsPagination", m.get("supportsPagination", True))

    fields = {f["name"] for f in m.get("fields") or []}
    sel = [c for c in dict.fromkeys(out_fields) if c in fields]
    if oid in fields:
        sel = list(dict.fromkeys(sel + [oid]))

    base = {"where": where, "outFields": ",".join(sel) or "*", "outSR": 4326,
            "returnGeometry": "true", "orderByFields": f"{oid} ASC"}
    recs, last, offset = [], None, 0
    while len(recs) < cap:
        p = dict(base)
        p["resultRecordCount"] = page
        if paged:
            p["resultOffset"] = offset
        else:
            p["where"] = where if last is None else f"({where}) AND {oid} > {last}"
        try:
            d = _get(url + "/query", p)
        except Exception:
            if offset == 0 and last is None:
                raise
            break
        feats = d.get("features") or []
        if not feats:
            break
        for f in feats:
            a = dict(f.get("attributes") or {})
            g = f.get("geometry") or {}
            a["_x"], a["_y"] = g.get("x"), g.get("y")
            recs.append(a)
        last = feats[-1]["attributes"].get(oid, last)
        offset += len(feats)
        # exceededTransferLimit false with a short page means the cursor is done.
        if not d.get("exceededTransferLimit") and len(feats) < page:
            break
        time.sleep(0.1)
    return recs


def _narrow_start(url, field, epoch, target):
    """Find the latest start date whose row count still fits under `target`.

    Cities are capped at MAX_ROWS and the cap should bite at the old end, so the
    panel stays contemporaneous across cities -- the same reasoning as the
    ordered, capped pull in harvest.fetch_crime.
    """
    lo, hi = pd.Timestamp(START_DATE), pd.Timestamp.now().normalize()
    best = START_DATE
    for _ in range(12):
        mid = lo + (hi - lo) / 2
        iso = mid.strftime("%Y-%m-%d")
        w, n = date_where(url, field, epoch, iso)
        if n is None:
            break
        if n > target:
            lo = mid
        else:
            best, hi = iso, mid
        if (hi - lo).days < 20:
            break
    return best


def _to_datetime(s, epoch):
    """Parse a date column, recovering when the declared type is wrong.

    `esriFieldTypeDate` is epoch milliseconds, but string-typed columns holding
    epoch milliseconds are common enough to be worth catching: parsed as text
    they collapse to 1970 and every row then fails the study's date window.
    """
    if epoch:
        return pd.to_datetime(pd.to_numeric(s, errors="coerce"), unit="ms", errors="coerce")
    out = pd.to_datetime(s, errors="coerce", format="mixed", utc=False)
    if out.notna().any() and (out.dt.year < 1980).mean() > 0.5:
        alt = pd.to_datetime(pd.to_numeric(s, errors="coerce"), unit="ms", errors="coerce")
        if alt.notna().mean() >= out.notna().mean():
            return alt
    return out


def _fetch_ckan(url, date_field, desc_fields, lat_field, lon_field):
    host, rid = url[len("ckan://"):].split("/", 1)
    api = f"https://{host}/api/3/action/datastore_search"
    cols = list(dict.fromkeys([date_field, lat_field, lon_field] + desc_fields))

    # Plain offset paging over datastore_search, filtering by date afterwards,
    # rather than the SQL endpoint. datastore_search_sql looks like the better
    # tool -- it can push the date filter down -- but WPRDC returns a 500 on the
    # last ~13k rows of this resource at every page size, while the same rows
    # come back cleanly here. The resource is small enough to read whole.
    frames, offset, page = [], 0, 10_000
    while True:
        d = _get(api, {"resource_id": rid, "limit": page, "offset": offset,
                       "fields": ",".join(cols)}, esri=False)["result"]
        recs = d["records"]
        if not recs:
            break
        frames.append(pd.DataFrame(recs))
        offset += len(recs)
        if len(recs) < page or offset >= d.get("total", 0):
            break
    if not frames:
        raise RuntimeError("no rows")
    df = pd.concat(frames, ignore_index=True)
    df["lat"] = pd.to_numeric(df[lat_field], errors="coerce")
    df["lon"] = pd.to_numeric(df[lon_field], errors="coerce")
    df["date"] = _to_datetime(df[date_field], False)
    return df


def fetch_city_arcgis(row, property_only=True):
    """Download one registry city. Same output contract as harvest.fetch_crime.

    Returns lat, lon, klass, loot_mass and date, restricted to PROPERTY_CLASSES
    unless `property_only=False`, which keeps OTHER and ROBBERY as well (the
    segment tables report the full class distribution).
    """
    urls = str(row.url).split("|")
    desc_fields = [c for c in str(row.desc_fields).split(";") if c]
    date_fields = [c for c in str(row.date_field).split(";") if c]
    lat_f, lon_f = str(row.lat_field or ""), str(row.lon_field or "")

    frames = []
    for i, url in enumerate(urls):
        dfield = date_fields[i] if i < len(date_fields) else date_fields[0]
        if url.startswith("ckan://"):
            frames.append(_fetch_ckan(url, dfield, desc_fields, lat_f, lon_f))
            continue
        m = layer_info(url)
        ftypes = {f["name"]: f["type"] for f in m.get("fields") or []}
        if dfield not in ftypes:
            dfield = next((c for c in date_fields if c in ftypes), None)
            if dfield is None:
                continue
        epoch = ftypes[dfield] == "esriFieldTypeDate"

        where, n = date_where(url, dfield, epoch, START_DATE)
        if not where:
            continue
        if n and n > MAX_ROWS:
            iso = _narrow_start(url, dfield, epoch, MAX_ROWS)
            where = date_where(url, dfield, epoch, iso)[0] or where

        want = [dfield] + desc_fields + [c for c in (lat_f, lon_f) if c]
        recs = _page_layer(url, where, want, MAX_ROWS)
        if not recs:
            continue
        df = pd.DataFrame(recs)
        # Prefer returned geometry; fall back to lat/lon columns when a layer
        # ships coordinates as attributes and no shape (common on views).
        lat = pd.to_numeric(df.get("_y"), errors="coerce")
        lon = pd.to_numeric(df.get("_x"), errors="coerce")
        if lat.isna().all() or lat.notna().mean() < 0.5:
            # Fall back to coordinate columns, preferring the registry's pick but
            # accepting any pair the name rules recognise -- Denver ships shapes
            # plus GEO_LAT/GEO_LON, and some views drop the shape entirely.
            fa = lat_f if lat_f in df else next((c for c in df if _LAT_RE.match(c)), None)
            fo = lon_f if lon_f in df else next((c for c in df if _LON_RE.match(c)), None)
            if fa and fo:
                alt = pd.to_numeric(df[fa], errors="coerce")
                if alt.notna().mean() > lat.notna().mean():
                    lat, lon = alt, pd.to_numeric(df[fo], errors="coerce")
        df["lat"], df["lon"] = lat, lon
        df["date"] = _to_datetime(df[dfield], epoch)
        frames.append(df)

    if not frames:
        raise RuntimeError("no rows")
    df = clean_points(pd.concat(frames, ignore_index=True))
    df = df[df.date >= pd.Timestamp(START_DATE)]

    present = [c for c in desc_fields if c in df.columns]
    if not present:
        raise RuntimeError("no description column survived the download")
    # fillna before astype: see harvest.fetch_crime -- on pandas 3 a null in any
    # description column NaNs the concatenation and the row falls to OTHER.
    text = df[present[0]].fillna("").astype(str)
    for c in present[1:]:
        text = text + " " + df[c].fillna("").astype(str)
    kl = text.map(lambda t: classify_text(norm_text(t)))
    df["klass"] = [k[0] for k in kl]
    df["loot_mass"] = [k[1] for k in kl]

    if property_only:
        df = df[df.klass.isin(PROPERTY_CLASSES)]
    return df.sort_values("date", ascending=False).head(MAX_ROWS).reset_index(drop=True)


# ------------------------------------------------------------------ build ---
def slug(city):
    return re.sub(r"[^a-z0-9]+", "_", city.lower()).strip("_")


def run_one(row, min_rows=5000):
    """Take one registry city all the way to an analysis table.

    Deliberately delegates to harvest.build_city so ArcGIS cities land in exactly
    the schema the Socrata cities already use -- terrain metrics, the 100 m grid,
    per-class counts, block-group SES. Any divergence here would silently make
    the two halves of the panel non-comparable.
    """
    import harvest as HV

    s = slug(row.city)
    out = f"data/interim/cells/{s}.parquet"
    if os.path.exists(out):
        return row.city, "cached", 0

    crime = fetch_city_arcgis(row)
    if len(crime) < min_rows:
        raise RuntimeError(f"only {len(crime)} classified property crimes")
    bbox = HV.robust_bbox(crime)
    epsg = HV.utm_epsg((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    dem = HV.fetch_dem(bbox, epsg, f"data/raw/dem/{s}.tif")
    os.makedirs("data/interim/cells", exist_ok=True)
    df = HV.build_city(row.city, crime, dem, epsg, out)
    return row.city, "ok", len(df)


def build(cities=None, registry=OUT):
    reg = pd.read_csv(registry)
    if cities:
        reg = reg[reg.city.isin(cities)]
    log = []
    for r in reg.itertuples():
        t0 = time.time()
        try:
            city, status, n = run_one(r)
            print(f"  [{status:6s}] {city:18s} {n:7,} cells  ({time.time()-t0:.0f}s)", flush=True)
            log.append({"city": r.city, "status": status, "cells": n})
        except Exception as e:
            print(f"  [FAIL  ] {r.city:18s} {type(e).__name__}: {str(e)[:110]}", flush=True)
            log.append({"city": r.city, "status": f"fail: {type(e).__name__}", "cells": 0})
    pd.DataFrame(log).to_csv("data/interim/harvest_arcgis_log.csv", index=False)
    return log


def main():
    args = sys.argv[1:]
    if args and args[0] == "build":
        build(args[1:] or None)
        return
    reg, _ = build_registry()
    cols = ["city", "rows", "n_layers", "date_min", "date_max", "desc_score"]
    print(reg[cols].to_string(index=False))


if __name__ == "__main__":
    main()
