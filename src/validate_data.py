"""Independent audit of the harvested data. Assumes nothing the pipeline says.

This exists because a row-count comparison against the live portals looked, for
about ten minutes, as though two cities had lost half their records. They had
not -- the registry stores an unfiltered total and the comparison was filtered
to 2018 onward. But the scare was a fair prompt to check the data properly
rather than to check one number badly.

Every check below is written to fail loudly and to be readable without knowing
the pipeline. Nothing here reads a result table; it goes to the panels and the
incident files and re-derives what it needs.
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import vizstyle as vs

PANEL = ["pittsburgh", "data_sfgov_org", "cos-data_seattle_gov",
         "data_cincinnati-oh_gov", "baltimore", "data_kcmo_org",
         "data_montgomerycountymd_gov", "charlotte", "data_cityofchicago_org"]
DATED = {"pittsburgh": "pittsburgh", "sfgov": "data_sfgov_org",
         "seattle": "cos-data_seattle_gov", "cincinnati": "data_cincinnati-oh_gov"}

fails, warns = [], []


def check(ok, msg, warn=False):
    (warns if warn else fails).append(msg) if not ok else None
    print(f"  {'ok  ' if ok else ('WARN' if warn else 'FAIL')}  {msg}")


def section(t):
    print(f"\n{'=' * 74}\n{t}\n{'=' * 74}")


def main():
    section("1. Panel integrity: counts, classes, and the exposure denominator")
    rows = []
    for s in PANEL:
        d = pd.read_parquet(f"data/interim/cells_exposure/{s}.parquet")
        ncls = [c for c in d.columns if c.startswith("n_") and c != "n_total"]
        cls_sum = d[ncls].sum(axis=1)
        expo = d.housing_units_bldg.fillna(0) + d.pop_bldg.fillna(0)
        rows.append({
            "city": vs.city(s), "cells": len(d),
            "incidents": int(d.n_total.sum()),
            "classes": len(ncls),
            "total_matches_classes": bool((cls_sum == d.n_total).all()),
            "neg_counts": int((d[ncls] < 0).sum().sum()),
            "neg_expo": int((expo < 0).sum()),
            "expo_zero": int((expo <= 0).sum()),
            "slope_min": float(d.slope_deg.min()),
            "slope_max": float(d.slope_deg.max()),
            "slope_nan": int(d.slope_deg.isna().sum()),
            "geoid_nan": int(d.GEOID.isna().sum()),
        })
    p = pd.DataFrame(rows)
    print(p[["city", "cells", "incidents", "classes", "slope_min", "slope_max"]]
          .to_string(index=False))
    check(p.total_matches_classes.all(),
          "n_total equals the sum of the class columns in every city")
    check((p.neg_counts == 0).all(), "no negative crime counts")
    check((p.neg_expo == 0).all(), "no negative exposure")
    check((p.slope_nan == 0).all(), "no NaN slope")
    check((p.slope_min >= 0).all(), "slope is non-negative everywhere")
    check((p.slope_max <= 90).all(), "slope never exceeds 90 degrees")
    check((p.geoid_nan == 0).all(), "every cell carries a block group id", warn=True)

    section("2. Do the dated re-downloads agree with the panel built months earlier?")
    # The strongest available check: two independent downloads of the same feed,
    # classified by the same rules, aggregated to the same grid. If the grid
    # join or the classifier had drifted, this correlation would break.
    import incident_tests as it
    for sd, sc in DATED.items():
        inc = pd.read_parquet(f"data/raw/crime_dated/{sd}.parquet")
        inc = it.assign_cells(inc, f"data/raw/dem/{sc}.tif")
        theft = {"MASS_1", "MASS_2", "MASS_3", "MASS_4", "MASS_5"}
        g = inc[inc.klass.isin(theft)].groupby("cell").size()
        d = pd.read_parquet(f"data/interim/cells_exposure/{sc}.parquet")
        mass = [c for c in d.columns if c.startswith("n_MASS_")]
        d["old"] = d[mass].sum(axis=1)
        d["new"] = d.cell.map(g).fillna(0)
        m = d[(d.old + d.new) > 0]
        r = float(np.corrcoef(m.old, m.new)[0, 1])
        ratio = m.new.sum() / max(m.old.sum(), 1)
        print(f"  {vs.city(sc):16s} cells {len(m):6,d}  r = {r:.6f}  "
              f"new/old volume = {ratio:.3f}")
        check(r > 0.99, f"{vs.city(sc)}: independent re-download correlates "
                        f"r={r:.4f} with the stored panel")

    section("3. Coordinates land where the city actually is")
    known = {"pittsburgh": (40.44, -79.99), "sfgov": (37.77, -122.42),
             "seattle": (47.61, -122.33), "cincinnati": (39.10, -84.51)}
    for sd, (la, lo) in known.items():
        inc = pd.read_parquet(f"data/raw/crime_dated/{sd}.parquet",
                              columns=["lat", "lon"])
        dla, dlo = abs(inc.lat.median() - la), abs(inc.lon.median() - lo)
        check(dla < 0.15 and dlo < 0.15,
              f"{sd}: median point {dla:.3f} lat / {dlo:.3f} lon from the "
              f"city centre")

    section("4. Time windows are what the paper says they are")
    for sd in DATED:
        inc = pd.read_parquet(f"data/raw/crime_dated/{sd}.parquet", columns=["date"])
        dt = pd.to_datetime(inc.date, utc=True, errors="coerce")
        span = (dt.max() - dt.min()).days / 365.25
        # A feed with a plausible window and no records from the future.
        fut = int((dt > pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)).sum())
        print(f"  {sd:12s} {dt.min().date()} .. {dt.max().date()}  "
              f"({span:.1f} years, {len(dt):,} rows)")
        check(fut == 0, f"{sd}: no incidents dated in the future")
        check(span > 1.5, f"{sd}: window spans more than 18 months")

    section("5. Class distribution is plausible in every city")
    # The classifier defects all showed up as a class being exactly zero where
    # it cannot be, so that is the shape of the test.
    for s in PANEL:
        d = pd.read_parquet(f"data/interim/cells_exposure/{s}.parquet")
        present = {c.replace("n_", ""): int(d[c].sum())
                   for c in d.columns if c.startswith("n_") and c != "n_total"}
        empty = [k for k, v in present.items() if v == 0]
        share_nl = present.get("NO_LOOT", 0) / max(sum(present.values()), 1)
        print(f"  {vs.city(s):22s} " +
              "  ".join(f"{k}={v:,}" for k, v in sorted(present.items())))
        check(not empty, f"{vs.city(s)}: no class is exactly zero "
                         f"({', '.join(empty) if empty else 'none'})", warn=True)
        check(0.02 < share_nl < 0.45,
              f"{vs.city(s)}: no-loot share {share_nl:.1%} is in a sane range",
              warn=True)

    section("6. Geocoding sinks and exposure outliers are actually filtered")
    # Use the pipeline's own definition of the estimation sample rather than a
    # hand-rolled approximation of it. The first version of this check applied
    # the exposure floor but not the sink filter, and duly reported five cities
    # as failures because it was measuring the data one step before the filter
    # that exists to fix exactly that.
    from regen_all import prep_cells
    for s in PANEL:
        raw = pd.read_parquet(f"data/interim/cells_exposure/{s}.parquet")
        expo_raw = (raw.housing_units_bldg.fillna(0)
                    + raw.pop_bldg.fillna(0)).clip(lower=1)
        pre = float((raw.n_total / expo_raw).max())
        d = prep_cells(f"data/interim/cells_exposure/{s}.parquet")
        post = float((d.n_total / d.exposure.clip(lower=1)).max())
        print(f"  {vs.city(s):22s} worst incidents-per-resident: "
              f"{pre:8.1f} raw -> {post:6.1f} in the estimation sample")
        check(post < 50, f"{vs.city(s)}: sink filter holds ({post:.1f} < 50)")

    section("VERDICT")
    print(f"  failures: {len(fails)}   warnings: {len(warns)}")
    for f in fails:
        print(f"    FAIL  {f}")
    for w in warns:
        print(f"    WARN  {w}")
    if fails:
        raise SystemExit(1)
    print("\n  All hard checks passed.")


if __name__ == "__main__":
    main()
