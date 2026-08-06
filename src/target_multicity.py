"""Does the result survive a direct target count outside San Francisco?

The strongest result in the paper -- replacing apportioned census housing with a
count of the things that actually get broken into -- rests on one city, because
the SFMTA parking census and San Francisco's address point file have no national
equivalent. The review is right that a single-city result cannot carry that much
weight.

Building footprints do have a national equivalent. Microsoft's release covers
every city in the panel, and a residential footprint is a reasonable stand-in for
a front door: it is a structure someone could enter, counted directly rather than
inferred by spreading a block-group housing total across cells. It is not as good
as San Francisco's address points -- an apartment block is one footprint and many
doors -- but it is a target count rather than a census allocation, and it fails in
a known direction.

The test is the same as San Francisco's. If steep cells merely hold fewer targets
per allocated housing unit, then dividing by the targets instead should pull the
coefficient toward zero. If it does not, the denominator is not the explanation.
"""
from __future__ import annotations

import glob
import os
import sys
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings("ignore")

from analyze import SES, coef, poisson
from regen_all import prep_cells, slug
import meta
import vizstyle as vs

OUT = "outputs"
CELL_M = 100


def building_cells(bpath, dem_path):
    """Residential and total footprint counts per 100 m cell."""
    with rasterio.open(dem_path) as src:
        transform, cell, crs = src.transform, abs(src.transform.a), src.crs
        h, w = src.height, src.width
    f = int(round(CELL_M / cell))
    gy, gx = h // f, w // f

    b = gpd.read_parquet(bpath, columns=["geometry", "bldg_class", "area_m2"])
    if b.crs is None or b.crs.to_string() != crs.to_string():
        b = b.to_crs(crs)
    c = b.geometry.representative_point()
    col = ((c.x.values - transform.c) / (f * cell)).astype(int)
    row = ((transform.f - c.y.values) / (f * cell)).astype(int)
    ok = (row >= 0) & (row < gy) & (col >= 0) & (col < gx)
    out = pd.DataFrame({
        "cell": row[ok] * gx + col[ok],
        "resid": (b.bldg_class.values[ok] == "residential").astype(int),
        "area": b.area_m2.values[ok],
    })
    g = out.groupby("cell")
    return pd.DataFrame({
        "n_doors": g.resid.sum(),
        "n_struct": g.size(),
        "resid_area": g.apply(lambda x: x.area[x.resid == 1].sum()),
    })


def fit(d, y, offset_col):
    """Same model, same controls, different denominator.

    Two things here were wrong in the first version and are worth recording,
    because both produced confident-looking output.

    The control `log_density` was being redefined as the log of whichever
    denominator was in play. That changes the control set at the same time as
    the offset, so the two specifications were no longer comparable -- and when
    the denominator is a small integer count of footprints, log_density becomes
    the log of the offset itself, which is badly enough scaled that the inner
    IRLS never converged. `log_density` now always means residential density on
    the original housing exposure, so only the offset changes.

    And the fit was reported whether or not it converged. Five of nine cities
    were stopping at the sixty iteration cap with a maximum score around 1.7e5
    and returning standard errors near 1e-11, which is what a degenerate
    sandwich looks like rather than a precise estimate. Non-convergence is now
    a refusal to report.
    """
    dd = d.copy()
    dd["exposure"] = dd[offset_col]
    dd = dd[dd.exposure > 0]
    dd = dd[dd.groupby("GEOID").GEOID.transform("size") >= 3]
    if len(dd) < 400:
        return None
    res, names = poisson(dd, y, ["slope_deg_raw"] + SES, bg_fe=True)
    # Judge on the first-order condition, not on the coefficient-change flag.
    # A fit that exhausts its iteration budget while sitting on a score of 1e-9
    # has solved the problem; one that stops with a score of 1e3 has not,
    # whatever its standard errors look like.
    scale = max(float(dd[y].sum()), 1.0)
    if res.max_abs_score / scale > 1e-8 or not np.isfinite(res.bse[0]) \
            or res.bse[0] < 1e-6:
        return {"failed": True, "n": int(res.nobs), "converged": bool(res.converged),
                "iters": res.iters, "max_abs_score": res.max_abs_score,
                "rel_score": res.max_abs_score / scale,
                "separated": res.n_separated}
    c = coef(res, names, "slope_deg_raw")
    c["n"] = int(res.nobs)
    c["failed"] = False
    c["separated"] = res.n_separated
    return c


def run():
    rows, failed = [], []
    for bpath in sorted(glob.glob("data/raw/buildings/*_epsg*.parquet")):
        s = os.path.basename(bpath).split("_epsg")[0]
        dem = f"data/raw/dem/{s}.tif"
        cells = f"data/interim/cells_exposure/{s}.parquet"
        if not (os.path.exists(dem) and os.path.exists(cells)):
            continue
        d = prep_cells(cells)
        if len(d) < 500:
            continue
        bc = building_cells(bpath, dem)
        d = d.merge(bc, left_on="cell", right_index=True, how="left")
        for c in ("n_doors", "n_struct", "resid_area"):
            d[c] = d[c].fillna(0.0)

        base = fit(d, "n_total", "exposure")
        doors = fit(d, "n_total", "n_doors")
        struct = fit(d, "n_total", "n_struct")
        if base is None or doors is None or base.get("failed"):
            continue
        if doors.get("failed"):
            print(f"{vs.city(s):22s} FAILED to converge on the footprint "
                  f"denominator (n={doors['n']}, {doors['iters']} iters, "
                  f"score {doors['max_abs_score']:.1e}) -- not reported",
                  flush=True)
            failed.append({"city": vs.city(s), "slug": s, **doors})
            continue
        rows.append({
            "city": vs.city(s), "slug": s,
            "pct_housing": base["pct"], "se_housing": base["se"],
            "beta_housing": base["beta"], "n_housing": base["n"],
            "pct_doors": doors["pct"], "se_doors": doors["se"],
            "beta_doors": doors["beta"], "n_doors_model": doors["n"],
            "pct_struct": struct["pct"] if struct and not struct.get("failed") else np.nan,
            "beta_struct": struct["beta"] if struct and not struct.get("failed") else np.nan,
            "se_struct": struct["se"] if struct and not struct.get("failed") else np.nan,
            "shift_pp": doors["pct"] - base["pct"],
            "toward_zero": bool(abs(doors["beta"]) < abs(base["beta"])),
            "doors_total": int(d.n_doors.sum()),
            "cells_with_doors": int((d.n_doors > 0).sum()),
        })
        r = rows[-1]
        print(f"{r['city']:22s} housing {r['pct_housing']:+6.2f}%  "
              f"front doors {r['pct_doors']:+6.2f}%  "
              f"structures {r['pct_struct']:+6.2f}%  "
              f"shift {r['shift_pp']:+5.2f}pp  "
              f"{'toward zero' if r['toward_zero'] else 'further from zero'}",
              flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/target_multicity.csv", index=False)
    if failed:
        pd.DataFrame(failed).to_csv(f"{OUT}/target_multicity_failed.csv", index=False)
        print(f"\n{len(failed)} cities dropped for non-convergence; see "
              "target_multicity_failed.csv")

    ph = meta.random_effects(df.beta_housing.values, df.se_housing.values)
    pd_ = meta.random_effects(df.beta_doors.values, df.se_doors.values)
    print(f"\npooled, housing denominator     {ph['pct']:+6.2f}%  "
          f"[{ph['pct_lo']:+.2f},{ph['pct_hi']:+.2f}]")
    print(f"pooled, front-door denominator  {pd_['pct']:+6.2f}%  "
          f"[{pd_['pct_lo']:+.2f},{pd_['pct_hi']:+.2f}]")
    n_away = int((~df.toward_zero).sum())
    print(f"\n{n_away} of {len(df)} cities move further from zero, "
          f"not toward it.")
    pd.DataFrame([
        {"denominator": "apportioned census housing", **{k: ph[k] for k in
         ("k", "pct", "pct_lo", "pct_hi", "tau2", "I2")}},
        {"denominator": "residential footprint count", **{k: pd_[k] for k in
         ("k", "pct", "pct_lo", "pct_hi", "tau2", "I2")}},
    ]).to_csv(f"{OUT}/target_multicity_pool.csv", index=False)
    print("wrote target_multicity.csv, target_multicity_pool.csv")


if __name__ == "__main__":
    run()
