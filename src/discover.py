"""Find every open crime dataset that can actually feed this study.

Rather than hand-listing cities, this walks the Socrata catalog (which fronts
several hundred US government portals), then probes each candidate live to check
what the catalog metadata cannot tell us: how many rows there are, whether the
coordinates are really populated, and how big an area the incidents cover.

Two stages:
  search()  -- catalog sweep, cheap, metadata only
  probe()   -- one count query and one sample per dataset, concurrent

Output: data/interim/candidates.csv, ranked. `harvest.py` consumes it.
"""
from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

CATALOG = "https://api.us.socrata.com/api/catalog/v1"
QUERIES = [
    "crime incidents", "police incident reports", "crime reports",
    "police incidents", "crime data", "part 1 crimes", "offenses",
    "incident based reporting", "police reports", "burglary theft",
]
OUT = "data/interim/candidates.csv"

LAT_RE = re.compile(r"^(lat|latitude|y|point_y|lat_?y|ycoord|y_coord)$", re.I)
LON_RE = re.compile(r"^(lon|long|lng|longitude|x|point_x|lon_?x|xcoord|x_coord)$", re.I)
DATE_RE = re.compile(r"(date|datetime|occur|report|time)", re.I)
DESC_RE = re.compile(r"(desc|offense|offence|category|type|crime|nibrs|ucr|charge|statute)", re.I)
GEO_RE = re.compile(r"(location|geocoded|point|the_geom|shape|coordinates)", re.I)

# portals that are state- or agency-wide rather than a city
SKIP_DOMAIN = re.compile(r"(\.gov\.uk|data\.ny\.gov|data\.wa\.gov|catalog\.data\.gov|"
                         r"healthdata|cdc\.gov|census\.gov)", re.I)


def search(q, limit=100, cap=400):
    out, offset = [], 0
    while True:
        r = requests.get(CATALOG, params={"q": q, "only": "dataset",
                                          "limit": limit, "offset": offset}, timeout=90)
        r.raise_for_status()
        d = r.json()
        out += d["results"]
        offset += limit
        if offset >= min(d["resultSetSize"], cap):
            break
        time.sleep(0.15)
    return out


def profile(rec):
    res, meta = rec["resource"], rec["metadata"]
    names = [n or "" for n in (res.get("columns_field_name") or [])]
    return {
        "domain": meta["domain"],
        "id": res["id"],
        "name": res["name"],
        "updated": (res.get("data_updated_at") or "")[:10],
        "lat_col": next((n for n in names if LAT_RE.match(n)), None),
        "lon_col": next((n for n in names if LON_RE.match(n)), None),
        "geo_col": next((n for n in names if GEO_RE.search(n)), None),
        "date_col": next((n for n in names if DATE_RE.search(n)), None),
        "desc_cols": ";".join(n for n in names if DESC_RE.search(n))[:200],
        "cols": ";".join(names)[:800],
    }


def probe(row, timeout=45):
    """One count + one sample. Returns spatial extent and populated-coord share."""
    dom, ds = row["domain"], row["id"]
    base = f"https://{dom}/resource/{ds}.json"
    out = dict(row)
    try:
        c = requests.get(base, params={"$select": "count(1) as n"}, timeout=timeout)
        if c.status_code != 200:
            out["error"] = f"count {c.status_code}"
            return out
        out["rows"] = int(c.json()[0]["n"])
    except Exception as e:
        out["error"] = f"count {type(e).__name__}"
        return out

    if out["rows"] < 20000:
        out["error"] = "too few rows"
        return out

    lat, lon = row.get("lat_col"), row.get("lon_col")
    if not (lat and lon):
        out["error"] = "no lat/lon cols"
        return out
    try:
        # SoQL requires an explicit AS for aggregate aliases
        q = {"$select": f"min({lat}) AS mnla, max({lat}) AS mxla, "
                        f"min({lon}) AS mnlo, max({lon}) AS mxlo, "
                        f"count({lat}) AS ngeo"}
        s = requests.get(base, params=q, timeout=timeout)
        if s.status_code != 200 or not s.json():
            out["error"] = f"extent {s.status_code}"
            return out
        d = s.json()[0]
        for k in ("mnla", "mxla", "mnlo", "mxlo"):
            out[k] = float(d[k]) if d.get(k) not in (None, "") else None
        out["geo_share"] = int(d.get("ngeo", 0)) / max(out["rows"], 1)
    except Exception as e:
        out["error"] = f"extent {type(e).__name__}"
        return out
    return out


def main():
    seen, recs = set(), []
    for q in QUERIES:
        try:
            hits = search(q)
        except Exception as e:
            print(f"  ! {q}: {e}")
            continue
        new = 0
        for rec in hits:
            key = (rec["metadata"]["domain"], rec["resource"]["id"])
            if key in seen or SKIP_DOMAIN.search(rec["metadata"]["domain"]):
                continue
            seen.add(key)
            recs.append(profile(rec))
            new += 1
        print(f"  {q:30s} +{new:3d}  (total {len(recs)})", flush=True)

    df = pd.DataFrame(recs)
    df = df[df["lat_col"].notna() & df["lon_col"].notna()]
    df = df[df["date_col"].notna() & (df["desc_cols"].str.len() > 0)]
    print(f"\n{len(df)} have lat/lon + date + description; probing live ...\n", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(probe, r): r["id"] for r in df.to_dict("records")}
        for i, f in enumerate(as_completed(futs), 1):
            results.append(f.result())
            if i % 25 == 0:
                print(f"    probed {i}/{len(futs)}", flush=True)

    out = pd.DataFrame(results)
    out.to_csv("data/interim/probe_raw.csv", index=False)
    if "error" in out:
        print("\nprobe failures:")
        print(out["error"].value_counts().head(12).to_string())
        ok = out[out["error"].isna()].copy()
    else:
        ok = out.copy()
    for c in ("geo_share", "mnla", "mxla", "mnlo", "mxlo"):
        if c not in ok:
            ok[c] = pd.NA
    ok = ok[ok["geo_share"].fillna(0) > 0.5]
    # sanity on extent: a real city spans well under 2 degrees
    ok = ok[(ok.mxla - ok.mnla).between(0.02, 2.0) & (ok.mxlo - ok.mnlo).between(0.02, 2.0)]
    ok = ok[ok.mnla.between(18, 72) & ok.mxlo.between(-180, -65)]  # US incl. AK/HI
    ok = ok.sort_values("rows", ascending=False).reset_index(drop=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    ok.to_csv(OUT, index=False)
    print(f"\n{len(ok)} usable datasets across {ok.domain.nunique()} portals -> {OUT}")
    print(ok[["domain", "id", "rows", "geo_share", "updated"]].head(50).to_string())


if __name__ == "__main__":
    main()
