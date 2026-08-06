"""Tests that need the incident date and the offense text, not just a class.

Three of the review's objections cannot be answered from the class-count panel,
because the original harvest discarded the date and the description once the
classifier had run. `harvest_dated.py` fetches them back for the four cities
above the gradient floor. This module uses them for:

  1. Splitting the no-loot control into vandalism and arson. The objection is
     fair: arson involves preparation, accelerant and acute escape risk, so
     lumping it with graffiti and broken windows makes the control group less
     homogeneous than the paper implied.

  2. Time-matching theft against no-loot. Vandalism concentrates at night, theft
     from vehicles does not, and steep streets are not necessarily equally lit
     or equally travelled at 3am. Comparing the two offense groups pooled across
     all hours therefore confounds offense type with time of day. The fix here
     reweights no-loot incidents so their hour-of-day by day-of-week
     distribution matches theft's, then re-runs the same contrast.

  3. Splitting the sample before and after March 2020. The incident windows
     straddle the pandemic and start in different years by city, so a "city
     effect" could partly be an observation-window effect.

Weighted counts are not integers. That is fine: Poisson pseudo-ML only requires
a correctly specified multiplicative mean, not a Poisson likelihood, which is
the whole reason it is the estimator here.
"""
from __future__ import annotations

import os
import re
import sys
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings("ignore")

from analyze import SES, coef, poisson
from confirmatory import paired_coef_test
import meta
import vizstyle as vs

OUT = "outputs"
CELL_M = 100
PANDEMIC = pd.Timestamp("2020-03-01", tz="UTC")

# dated slug -> (DEM/cells slug)
CITIES = {
    "pittsburgh": "pittsburgh",
    "sfgov": "data_sfgov_org",
    "seattle": "cos-data_seattle_gov",
    "cincinnati": "data_cincinnati-oh_gov",
}

_ARSON = re.compile(r"\barson\b|\bincendiar", re.I)
_VANDAL = re.compile(
    r"vandal|criminal damag|malicious mischief|criminal mischief|graffiti|"
    r"destruction/damage|destruction of property|damage to property", re.I)


def subclass_noloot(text):
    """Arson, vandalism, or neither. Arson wins when both words appear."""
    if _ARSON.search(text):
        return "ARSON"
    if _VANDAL.search(text):
        return "VANDALISM"
    return "OTHER_NOLOOT"


# ------------------------------------------------------------ cell join ----
def assign_cells(dated, dem_path):
    """Reproduce build_city's grid arithmetic exactly, so cell ids line up."""
    with rasterio.open(dem_path) as src:
        transform, cell, crs = src.transform, abs(src.transform.a), src.crs
        h, w = src.height, src.width
    f = int(round(CELL_M / cell))
    # Floor, not ceil: to_grid() trims the DEM to a whole number of blocks
    # before averaging, so the coarse grid is h//f by w//f. Rounding up instead
    # shifts every cell id by a row and silently scrambles the join -- which it
    # did, turning the slope coefficient positive before this was caught.
    gy, gx = h // f, w // f

    pts = gpd.GeoSeries(gpd.points_from_xy(dated.lon, dated.lat),
                        crs=4326).to_crs(crs)
    col = ((pts.x.values - transform.c) / (f * cell)).astype(int)
    row = ((transform.f - pts.y.values) / (f * cell)).astype(int)
    ok = (row >= 0) & (row < gy) & (col >= 0) & (col < gx)
    out = dated[ok].copy()
    out["cell"] = row[ok] * gx + col[ok]
    return out


def prep(path):
    """Estimation sample, mirroring regen_all.prep_cells."""
    d = pd.read_parquet(path)
    d["exposure"] = d.housing_units_bldg.fillna(0) + d.pop_bldg.fillna(0)
    d = d[d.exposure > 5]
    d["log_income"] = np.log(d.median_hh_income.clip(lower=5000))
    d["log_value"] = np.log(d.median_home_value.clip(lower=50000))
    d["log_density"] = np.log(d.exposure)
    d["owner_share"] = d.owner_share.astype(float)
    d["vacancy_rate"] = d.vacancy_rate.astype(float)
    d = d[d.n_total / d.exposure.clip(lower=1) < 50]
    d = d[d.groupby("GEOID").GEOID.transform("size") >= 3]
    d["slope_deg_raw"] = d.slope_deg.astype(float)
    need = SES + ["slope_deg_raw", "exposure", "GEOID"]
    return d.dropna(subset=need).reset_index(drop=True)


def build(slug_dated, slug_city):
    """Cell panel with dated, sub-classified counts attached."""
    inc = pd.read_parquet(f"data/raw/crime_dated/{slug_dated}.parquet")
    inc = assign_cells(inc, f"data/raw/dem/{slug_city}.tif")
    inc["date"] = pd.to_datetime(inc.date, utc=True, errors="coerce")
    inc = inc[inc.date.notna()]

    theft_klass = {"MASS_1", "MASS_2", "MASS_3", "MASS_4", "MASS_5"}
    inc["grp"] = np.where(inc.klass.isin(theft_klass), "THEFT",
                          np.where(inc.klass == "NO_LOOT",
                                   inc.text.map(subclass_noloot), "SKIP"))
    inc = inc[inc.grp != "SKIP"].copy()
    inc["hour"] = inc.date.dt.hour
    inc["dow"] = inc.date.dt.dayofweek
    inc["post"] = inc.date >= PANDEMIC

    # --- hour x day-of-week reweighting -------------------------------------
    # Give every no-loot incident the weight that makes the no-loot hour-by-day
    # distribution match theft's. Theft keeps weight 1. Strata theft never uses
    # get weight 0, which is correct -- there is no theft comparison there.
    th = inc[inc.grp == "THEFT"]
    nl = inc[inc.grp != "THEFT"]
    pt = th.groupby(["hour", "dow"]).size() / max(len(th), 1)
    pn = nl.groupby(["hour", "dow"]).size() / max(len(nl), 1)
    ratio = (pt / pn).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    key = list(zip(inc.hour, inc.dow))
    inc["w"] = np.where(inc.grp == "THEFT", 1.0,
                        [ratio.get(k, 0.0) for k in key])

    g = inc.groupby("cell")
    panel = pd.DataFrame({
        "n_theft_d": g.apply(lambda x: (x.grp == "THEFT").sum()),
        "n_vandal": g.apply(lambda x: (x.grp == "VANDALISM").sum()),
        "n_arson": g.apply(lambda x: (x.grp == "ARSON").sum()),
        "n_noloot_d": g.apply(lambda x: (x.grp != "THEFT").sum()),
        "n_noloot_w": g.apply(lambda x: x.w[x.grp != "THEFT"].sum()),
        "n_theft_pre": g.apply(lambda x: ((x.grp == "THEFT") & ~x.post).sum()),
        "n_theft_post": g.apply(lambda x: ((x.grp == "THEFT") & x.post).sum()),
        "n_all_pre": g.apply(lambda x: (~x.post).sum()),
        "n_all_post": g.apply(lambda x: (x.post).sum()),
    })

    cells = prep(f"data/interim/cells_exposure/{slug_city}.parquet")
    d = cells.merge(panel, left_on="cell", right_index=True, how="left")
    for c in panel.columns:
        d[c] = d[c].fillna(0.0)
    return d, inc


# ------------------------------------------------------------------ tests ---
def run():
    comp_rows, arson_rows, temporal_rows, matched_rows = [], [], [], []

    for sd, sc in CITIES.items():
        name = vs.city(sc)
        print(f"\n=== {name} ===", flush=True)
        d, inc = build(sd, sc)

        n_v = int(d.n_vandal.sum())
        n_a = int(d.n_arson.sum())
        n_o = int(d.n_noloot_d.sum()) - n_v - n_a
        comp_rows.append({"city": name, "vandalism": n_v, "arson": n_a,
                          "other_noloot": n_o,
                          "arson_share": n_a / max(n_v + n_a + n_o, 1)})
        print(f"  no-loot composition: vandalism {n_v:,}  arson {n_a:,} "
              f"({100 * n_a / max(n_v + n_a + n_o, 1):.2f}%)  other {n_o:,}")

        # 1. theft vs vandalism only (arson removed)
        r = paired_coef_test(d, "n_theft_d", "n_vandal",
                             xvar="slope_deg_raw", n_boot=300, seed=17)
        r["city"] = name
        r["control"] = "vandalism only"
        arson_rows.append(r)
        print(f"  theft {r['pct_a']:+.2f}%  vandalism {r['pct_b']:+.2f}%  "
              f"diff {r['diff_pct_pts']:+.2f}pp "
              f"[{100 * (np.exp(r['diff_lo']) - 1):+.2f},"
              f"{100 * (np.exp(r['diff_hi']) - 1):+.2f}]")

        # 1b. arson alone, where there is enough of it to estimate
        if n_a >= 400:
            res, names = poisson(d, "n_arson", ["slope_deg_raw"] + SES,
                                 bg_fe=True)
            c = coef(res, names, "slope_deg_raw")
            arson_rows.append({"city": name, "control": "arson only",
                               "pct_a": np.nan, "pct_b": c["pct"],
                               "beta_b": c["beta"], "se_b": c["se"],
                               "diff_pct_pts": np.nan, "n_boot_ok": 0})
            print(f"  arson alone: {c['pct']:+.2f}%  (n={n_a:,})")

        # 2. time-matched theft vs no-loot
        rm = paired_coef_test(d, "n_theft_d", "n_noloot_w",
                              xvar="slope_deg_raw", n_boot=300, seed=17)
        rm["city"] = name
        rm["control"] = "no-loot, hour x day matched"
        matched_rows.append(rm)
        print(f"  time-matched: theft {rm['pct_a']:+.2f}%  no-loot "
              f"{rm['pct_b']:+.2f}%  diff {rm['diff_pct_pts']:+.2f}pp")

        # 3. before and after March 2020
        pre_n, post_n = int(d.n_all_pre.sum()), int(d.n_all_post.sum())
        row = {"city": name, "n_pre": pre_n, "n_post": post_n,
               "window_start": str(inc.date.min().date()),
               "window_end": str(inc.date.max().date())}
        for lab, col, n in (("pre", "n_all_pre", pre_n),
                            ("post", "n_all_post", post_n)):
            if n < 5000:
                row[f"pct_{lab}"] = np.nan
                row[f"se_{lab}"] = np.nan
                continue
            res, names = poisson(d, col, ["slope_deg_raw"] + SES, bg_fe=True)
            c = coef(res, names, "slope_deg_raw")
            row[f"pct_{lab}"] = c["pct"]
            row[f"beta_{lab}"] = c["beta"]
            row[f"se_{lab}"] = c["se"]
        temporal_rows.append(row)
        print(f"  pre-2020 {row.get('pct_pre', float('nan')):+.2f}%  "
              f"post {row.get('pct_post', float('nan')):+.2f}%  "
              f"(n {pre_n:,} / {post_n:,})")

    pd.DataFrame(comp_rows).to_csv(f"{OUT}/noloot_composition.csv", index=False)
    pd.DataFrame(arson_rows).to_csv(f"{OUT}/h1_vandalism_only.csv", index=False)
    pd.DataFrame(matched_rows).to_csv(f"{OUT}/h1_time_matched.csv", index=False)
    pd.DataFrame(temporal_rows).to_csv(f"{OUT}/temporal_split.csv", index=False)

    # ------------------------------------------------- pooled + equivalence --
    summary = []
    for label, rows in (("vandalism only", [r for r in arson_rows
                                            if r.get("control") == "vandalism only"]),
                        ("hour x day matched", matched_rows)):
        diffs = np.array([r["diff_beta"] for r in rows])
        ses = np.array([(r["diff_hi"] - r["diff_lo"]) / (2 * 1.96) for r in rows])
        p = meta.random_effects(diffs, ses)
        # Equivalence margin: half the pooled slope effect itself. If carrying
        # the loot were the mechanism, removing the load should move the
        # coefficient by a large fraction of the whole effect, not a sliver of
        # it. Half is a deliberately generous bar for the effort account.
        margin = abs(np.log(1 - 0.0661)) / 2
        t = meta.tost(p["mu"], p["se_hk"], margin)
        summary.append({
            "contrast": label, "k": p["k"],
            "diff_pp": 100 * (np.exp(p["mu"]) - 1),
            "lo": p["pct_lo"], "hi": p["pct_hi"],
            "tau2": p["tau2"], "I2": p["I2"],
            "margin_log": margin,
            "margin_pct": 100 * (np.exp(margin) - 1),
            "tost_p": t["p"], "equivalent": t["equivalent"],
        })
        print(f"\npooled {label}: {summary[-1]['diff_pp']:+.2f}pp "
              f"[{p['pct_lo']:+.2f},{p['pct_hi']:+.2f}]  "
              f"TOST p={t['p']:.4f} -> "
              f"{'equivalent within margin' if t['equivalent'] else 'NOT shown equivalent'}")
    pd.DataFrame(summary).to_csv(f"{OUT}/h1_equivalence.csv", index=False)

    print("\nwrote noloot_composition.csv, h1_vandalism_only.csv, "
          "h1_time_matched.csv, temporal_split.csv, h1_equivalence.csv")


if __name__ == "__main__":
    run()
