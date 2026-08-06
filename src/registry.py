"""Build the city registry: the best crime dataset per open-data portal.

Three stages.

1. Enumerate portals. The global catalog search ranks badly for picking a city's
   main crime file, but it is fine for discovering which domains exist. Union
   that with a curated list of known municipal portals.

2. Search each portal individually. This is what surfaces "Crimes - 2001 to
   Present" instead of a fire-dispatch feed.

3. Probe every candidate live, then keep the largest per city. The bounding box
   comes from sampled 1st/99th percentiles rather than min/max, because most
   police feeds contain a handful of junk coordinates -- Chicago's span 5.4
   degrees of latitude on min/max and 0.3 on percentiles.
"""
from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests

CATALOG = "https://api.us.socrata.com/api/catalog/v1"
OUT = "data/interim/registry.csv"

SWEEP_QUERIES = ["crime incidents", "police incidents", "crime reports",
                 "offenses", "police report", "part 1 crimes"]
PORTAL_QUERIES = ["crime", "incidents", "offenses"]

SEED_DOMAINS = """
data.sfgov.org data.cityofchicago.org data.lacity.org data.cityofnewyork.us
cos-data.seattle.gov data.austintexas.gov www.dallasopendata.com data.kcmo.org
data.nashville.gov data.nola.gov data.cincinnati-oh.gov data.baltimorecity.gov
data.montgomerycountymd.gov data.princegeorgescountymd.gov data.hartford.gov
data.buffalony.gov data.brla.gov data.norfolk.gov data.cambridgema.gov
citydata.mesaaz.gov data.sanjoseca.gov data.milwaukee.gov data.honolulu.gov
data.louisvilleky.gov data.bloomington.in.gov data.memphistn.gov
data.providenceri.gov data.somervillema.gov data.lincoln.ne.gov
data.cityofgainesville.org data.detroitmi.gov data.oaklandca.gov
data.chattanooga.gov data.tempe.gov data.tucsonaz.gov data.seattle.gov
""".split()

NAME_BAD = re.compile(
    r"(311|fire|ems|medical|dispatch|calls for service|traffic stop|citation|"
    r"parking|permit|inspection|budget|salary|shooting|use of force|resistance|"
    r"complaint against|internal affairs|by (year|month|beat|district|neighborhood)|"
    r"summary|statistic|clearance|stop and frisk|field interview|towed|"
    r"coalition|survey|health)", re.I)
NAME_GOOD = re.compile(r"(crime|incident|offense|offence|police report|complaint data|"
                       r"part 1|part i\b)", re.I)
# Allow prefixes and suffixes: portals ship latitude_x, reporting_area_lat, y_lat.
LAT_RE = re.compile(r"(^|_)lat(itude)?(_|$)|^(y|point_y|ycoord|y_coord)$", re.I)
LON_RE = re.compile(r"(^|_)(lon|lng|long)(gitude|itude)?(_|$)|^(x|point_x|xcoord|x_coord)$", re.I)
DATE_RE = re.compile(r"(date|datetime|occur|report)", re.I)
DESC_RE = re.compile(r"(desc|offense|offence|category|type|crime|nibrs|statute)", re.I)
# Description columns must be *ranked*, not taken in dataset order. Los Angeles
# lists weapon_desc, premis_desc and vict_descent before crm_cd_desc, so taking
# the first three matches fed the classifier a weapon, a premise and a victim's
# ethnicity while discarding the only field naming the offense -- which is why
# the city failed harvest with "too few classified property crimes". Rank by how
# offense-like the column name is, and demote fields that describe the victim,
# the weapon, the premises or the case status.
DESC_GOOD = re.compile(r"(crm_cd_desc|offense|offence|nibrs|ucr|charge|statute|"
                       r"crime|incident|violation)", re.I)
DESC_BAD = re.compile(r"(weapon|premis|vict|status|suspect|arrest|disposition|"
                      r"resolution|report_type|agency|beat|district|sector)", re.I)


def rank_desc(names):
    """Description columns, most offense-like first.

    A specific offense *description* beats a coarse *category*: Seattle publishes
    both `nibrs_crime_against_category` ("Property"/"Person"/"Society") and
    `nibrs_offense_code_description` ("Theft From Motor Vehicle"), and only the
    latter can drive a loot-mass ladder.
    """
    def score(n):
        s = 2 if DESC_GOOD.search(n) else 0
        s += 1 if re.search(r"desc", n, re.I) else 0
        s -= 1 if re.search(r"categor", n, re.I) else 0
        s -= 3 if DESC_BAD.search(n) else 0
        return s
    return sorted([n for n in names if DESC_RE.search(n)], key=score, reverse=True)
# "long_desc" matches the longitude pattern but is obviously not a coordinate.
NOT_COORD = re.compile(r"(desc|type|cat|name|code|text|note)", re.I)


def pick_coord(names, rx):
    return next((n for n in names if rx.search(n) and not NOT_COORD.search(n)), None)


def catalog_get(params, timeout=90):
    try:
        r = requests.get(CATALOG, params=params, timeout=timeout)
        return r.json().get("results", []) if r.status_code == 200 else []
    except Exception:
        return []


def sweep_domains():
    doms = set(SEED_DOMAINS)
    for q in SWEEP_QUERIES:
        for off in (0, 100, 200, 300):
            for rec in catalog_get({"q": q, "only": "dataset", "limit": 100, "offset": off}):
                doms.add(rec["metadata"]["domain"])
            time.sleep(0.1)
    return sorted(d for d in doms if not re.search(r"(\.uk|europa|canada|\.ca$)", d, re.I))


def candidates_for(domain):
    out, seen = [], set()
    for q in PORTAL_QUERIES:
        for rec in catalog_get({"domains": domain, "q": q, "only": "dataset", "limit": 25}, 60):
            res = rec["resource"]
            if res["id"] in seen:
                continue
            seen.add(res["id"])
            name = res["name"]
            if NAME_BAD.search(name) or not NAME_GOOD.search(name):
                continue
            names = [n or "" for n in (res.get("columns_field_name") or [])]
            lat, lon = pick_coord(names, LAT_RE), pick_coord(names, LON_RE)
            date = next((n for n in names if DATE_RE.search(n)), None)
            desc = rank_desc(names)
            if not (lat and lon and date and desc):
                continue
            out.append({"domain": rec["metadata"]["domain"], "id": res["id"], "name": name,
                        "lat_col": lat, "lon_col": lon, "date_col": date,
                        "desc_col": desc[0], "all_desc": ";".join(desc)[:200],
                        "updated": (res.get("data_updated_at") or "")[:10]})
    return out


# Datasets named directly. Some major portals are not indexed by the federated
# catalog at all (San Francisco), and for others the portal search does not rank
# the flagship file first. Columns are auto-detected from the dataset metadata.
FORCE = [
    ("data.sfgov.org", "wg3w-h783"),          # San Francisco
    ("data.cityofchicago.org", "ijzp-q8t2"),  # Chicago
    ("data.lacity.org", "2nrs-mtv8"),         # Los Angeles
    ("data.cityofnewyork.us", "qgea-i56i"),   # New York
    ("cos-data.seattle.gov", "tazs-3rd5"),    # Seattle
    ("data.austintexas.gov", "fdj4-gpfu"),    # Austin
    ("www.dallasopendata.com", "qv6i-rri7"),  # Dallas
    ("data.nashville.gov", "2u6v-ujjs"),      # Nashville
    ("data.cincinnati-oh.gov", "k59e-2pvf"),  # Cincinnati
    ("data.baltimorecity.gov", "wsfq-mvij"),  # Baltimore
    ("data.buffalony.gov", "d6g9-xbgu"),      # Buffalo
    ("data.cambridgema.gov", "xuad-73uj"),    # Cambridge
    ("cos-data.seattle.gov", "tazs-3rd5"),    # Seattle
    ("data.cincinnati-oh.gov", "k59e-2pvf"),  # Cincinnati
    ("data.princegeorgescountymd.gov", "xjru-idbe"),
    ("data.kcmo.org", "gqy2-yvmn"),           # Kansas City
    ("data.brla.gov", "6zc2-imdr"),           # Baton Rouge
    ("data.montgomerycountymd.gov", "icn6-v9z3"),
    ("performance.fultoncountyga.gov", "jgdb-bp9a"),  # Atlanta
]


def force_candidate(domain, ds, timeout=60):
    """Build a candidate from dataset metadata, detecting columns directly."""
    try:
        r = requests.get(f"https://{domain}/api/views/{ds}.json", timeout=timeout)
        if r.status_code != 200:
            return None
        v = r.json()
        names = [c.get("fieldName", "") for c in v.get("columns", [])]
        lat, lon = pick_coord(names, LAT_RE), pick_coord(names, LON_RE)
        date = next((n for n in names if DATE_RE.search(n)), None)
        desc = rank_desc(names)
        if not (lat and lon and date and desc):
            return None
        return {"domain": domain, "id": ds, "name": v.get("name", ds),
                "lat_col": lat, "lon_col": lon, "date_col": date,
                "desc_col": desc[0], "all_desc": ";".join(desc)[:200], "updated": ""}
    except Exception:
        return None


def probe(c, timeout=90):
    base = f"https://{c['domain']}/resource/{c['id']}.json"
    try:
        n = requests.get(base, params={"$select": "count(1) AS n"}, timeout=timeout)
        if n.status_code != 200:
            c["error"] = f"count {n.status_code}"; return c
        c["rows"] = int(n.json()[0]["n"])
        if c["rows"] < 15000:
            c["error"] = "too few rows"; return c

        la, lo = c["lat_col"], c["lon_col"]

        # Geocoded share must come from a count over the whole table, not from a
        # sample: police feeds are usually ordered by date, and the early years
        # often have no coordinates at all, which makes any head-of-table sample
        # wildly pessimistic.
        g = requests.get(base, params={"$select": f"count({la}) AS ngeo"}, timeout=timeout)
        c["geo_share"] = (int(g.json()[0]["ngeo"]) / max(c["rows"], 1)
                          if g.status_code == 200 else 0.0)

        s = requests.get(base, params={"$select": f"{la},{lo}",
                                       "$where": f"{la} IS NOT NULL AND {lo} IS NOT NULL",
                                       "$limit": 3000}, timeout=timeout)
        if s.status_code != 200:
            c["error"] = f"sample {s.status_code}"; return c
        d = pd.DataFrame(s.json())
        if la not in d or lo not in d:
            c["error"] = "sample missing cols"; return c
        y = pd.to_numeric(d[la], errors="coerce").dropna()
        x = pd.to_numeric(d[lo], errors="coerce").dropna()
        y, x = y[y.between(-90, 90) & (y != 0)], x[x.between(-180, 180) & (x != 0)]
        if len(y) < 200 or len(x) < 200:
            c["error"] = "too few valid coords"; return c
        c["mnla"], c["mxla"] = np.percentile(y, [0.5, 99.5])
        c["mnlo"], c["mxlo"] = np.percentile(x, [0.5, 99.5])
    except Exception as ex:
        c["error"] = type(ex).__name__
    return c


def main():
    print("stage 1: enumerating portals ...", flush=True)
    doms = sweep_domains()
    print(f"  {len(doms)} domains\n", flush=True)

    print("stage 2: searching each portal ...", flush=True)
    cands = []
    with ThreadPoolExecutor(max_workers=14) as ex:
        futs = {ex.submit(candidates_for, d): d for d in doms}
        for i, f in enumerate(as_completed(futs), 1):
            cands += f.result()
            if i % 40 == 0:
                print(f"  {i}/{len(doms)} portals, {len(cands)} candidates", flush=True)
    have = {(c["domain"], c["id"]) for c in cands}
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = [ex.submit(force_candidate, d, i) for d, i in FORCE if (d, i) not in have]
        for f in as_completed(futs):
            c = f.result()
            if c:
                cands.append(c)
                print(f"  forced {c['domain']:32s} {c['id']}", flush=True)
    print(f"  {len(cands)} candidate datasets\n", flush=True)

    print("stage 3: probing ...", flush=True)
    out = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = [ex.submit(probe, c) for c in cands]
        for i, f in enumerate(as_completed(futs), 1):
            out.append(f.result())
            if i % 40 == 0:
                print(f"  probed {i}/{len(futs)}", flush=True)

    df = pd.DataFrame(out)
    if "error" in df:
        print("\nfailures:"); print(df["error"].value_counts().head(10).to_string())
        df = df[df["error"].isna()].copy()
    df = df[df["geo_share"].fillna(0) > 0.5]
    span_la, span_lo = df.mxla - df.mnla, df.mxlo - df.mnlo
    df = df[span_la.between(0.01, 1.5) & span_lo.between(0.01, 1.5)]
    df = df[df.mnla.between(18, 72) & df.mxlo.between(-180, -65)]

    # Final name check. Forced entries bypass the stage-2 name screen, and a
    # mistyped four-by-four silently resolves to whatever else lives at that id
    # -- building permits, catch-basin inspections, traffic crashes.
    df = df[df["name"].str.contains(NAME_GOOD) & ~df["name"].str.contains(NAME_BAD)]
    df = df[~df["domain"].str.contains(r"(demo|test|staging)\.", case=False, regex=True)]

    # one dataset per city: the biggest
    df = df.sort_values("rows", ascending=False).drop_duplicates("domain").reset_index(drop=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"\n=== {len(df)} cities with usable incident data -> {OUT}")
    print(df[["domain", "id", "rows", "geo_share", "name"]].to_string(max_colwidth=40))


if __name__ == "__main__":
    main()
