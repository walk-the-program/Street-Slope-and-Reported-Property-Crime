"""Two-stage national analysis.

Stage one: estimate the terrain effect separately in each city, always with
block-group fixed effects, so identification is always within-neighbourhood.

Stage two: regress those city-level estimates on how strongly elevation tracks
income *in that city*.

    beta_c = b0 + lambda * rho_c + u_c

`lambda` is how much of the apparent terrain effect is really affluence sorting
uphill. `b0` -- the value at rho = 0 -- is the terrain effect with that confound
arithmetically removed. No single-city study can estimate b0 at any sample size,
which is the whole reason for building a panel.

Stage two is weighted by inverse variance and reports both a conventional and a
cluster-free bootstrap interval, because 16 cities is a small second-stage n.
"""
from __future__ import annotations

import glob
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from analyze import RADII, SES, coef, poisson

warnings.filterwarnings("ignore")
CELLS = "data/interim/cells/*.parquet"
OUT = "outputs"
MIN_CELLS = 300
MIN_EVENTS = 3000


def prep_city(df):
    df = df.copy()
    df["exposure"] = df["housing_units_cell"].fillna(0) + df["pop_cell"].fillna(0)
    df = df[df["exposure"] > 5]
    df["log_income"] = np.log(df["median_hh_income"].clip(lower=5000))
    df["log_value"] = np.log(df["median_home_value"].clip(lower=50000))
    df["log_density"] = np.log(df["exposure"])
    df["owner_share"] = df["owner_share"].astype(float)
    df["vacancy_rate"] = df["vacancy_rate"].astype(float)
    for r in RADII:
        c = f"tpi_{r}"
        s = df[c]
        df[f"{c}_z"] = (s - s.mean()) / s.std() if s.std() > 0 else 0.0
    # Restrict to the reporting agency's actual jurisdiction.
    #
    # The harvest clips to whole counties, which is right for a county police
    # department and badly wrong for a city one. The Marin County Sheriff
    # polices only unincorporated Marin, yet the county clip handed it 1,313
    # km2 in which 99% of cells held zero incidents; West Hollywood's grid came
    # out eight times the size of the city. Those empty cells are not
    # low-crime places, they are places this agency does not report on, and
    # they are not positioned randomly with respect to terrain.
    #
    # A block group with no recorded incident in seven years, inside an area an
    # agency actually covers, is very close to nonexistent -- which is why this
    # rule keeps 100% of incidents in every city while removing the padding,
    # and why it barely touches the cities that were already clipped correctly
    # (San Francisco 98% of block groups retained, Montgomery County 99.5%).
    covered = df.groupby("GEOID")["n_total"].transform("sum") > 0
    df = df[covered]

    # Drop geocoding sinks. Departments commonly geocode records with an
    # unusable address to a fixed point -- a precinct house, a records office,
    # the city centroid -- which produces one cell holding thousands of
    # incidents on a block with twenty residents. Montgomery County has a cell
    # with 3,545 incidents against an exposure of ~20. A rate above 50 incidents
    # per resident-or-unit over the period is not a real place; it is an
    # artifact, and it sits wherever the station happens to be, which is not
    # random with respect to terrain.
    df["_rate"] = df["n_total"] / df["exposure"].clip(lower=1)
    df = df[df["_rate"] < 50].drop(columns="_rate")

    need = SES + [f"tpi_{r}_z" for r in RADII] + ["exposure", "GEOID", "n_total"]
    df = df.dropna(subset=[c for c in need if c in df])
    keep = df.groupby("GEOID")["GEOID"].transform("size") >= 3
    return df[keep].reset_index(drop=True)


def city_estimates(path, radius=500):
    name = os.path.basename(path).replace(".parquet", "")
    raw = pd.read_parquet(path)
    df = prep_city(raw)
    if len(df) < MIN_CELLS or df["n_total"].sum() < MIN_EVENTS:
        return None

    t = f"tpi_{radius}_z"
    res, names = poisson(df, "n_total", [t] + SES, bg_fe=True)
    c = coef(res, names, t)

    out = {
        "city": name,
        "n_cells": len(df),
        "n_bg": df["GEOID"].nunique(),
        "n_events": int(df["n_total"].sum()),
        # how strongly elevation tracks money HERE -- the stage-two regressor
        "rho_income": df[f"tpi_{radius}"].corr(df["median_hh_income"]),
        "rho_value": df[f"tpi_{radius}"].corr(df["median_home_value"]),
        "rho_abs_income": df["elev"].corr(df["median_hh_income"]),
        # how hilly the city is at all -- flat cities are the placebo arm
        "relief_sd": float(df["elev"].std()),
        "relief_p99": float(np.nanpercentile(df["elev"], 99) - np.nanpercentile(df["elev"], 1)),
        "tpi_sd": float(df[f"tpi_{radius}"].std()),
        # How tight is the fixed effect? A block group in dense San Francisco is
        # a few blocks; one in a sprawling suburban county can span miles, so
        # "within block group" is a much weaker neighbourhood control there.
        "bg_area_km2": float(df.groupby("GEOID")["ALAND"].first().median() / 1e6),
        "exposure_median": float(df["exposure"].median()),
        "share_zero": float((df["n_total"] == 0).mean()),
        "beta": c["beta"], "se": c["se"], "pct": c["pct"],
        "lo": c["lo"], "hi": c["hi"], "z": c["z"],
    }
    # Effects above are per within-city SD, which is the right scale-free unit
    # for pooling but hides that one SD is ~19 m in San Francisco and ~1 m in
    # Chicago. Also carry a physical-units version so magnitudes stay readable.
    sd = out["tpi_sd"]
    out["pct_per_10m"] = 100 * (np.exp(c["beta"] * 10.0 / sd) - 1) if sd > 0.05 else np.nan
    # per-radius effects, for the pooled scale curve
    for r in RADII:
        try:
            rr, nn = poisson(df, "n_total", [f"tpi_{r}_z"] + SES, bg_fe=True)
            cc = coef(rr, nn, f"tpi_{r}_z")
            out[f"beta_{r}"], out[f"se_{r}"] = cc["beta"], cc["se"]
        except Exception:
            out[f"beta_{r}"], out[f"se_{r}"] = np.nan, np.nan
    return out


def wls(x, y, w):
    """Inverse-variance weighted least squares with an intercept."""
    X = np.column_stack([np.ones_like(x), x])
    W = np.diag(w)
    xtwx = X.T @ W @ X
    b = np.linalg.solve(xtwx, X.T @ W @ y)
    resid = y - X @ b
    dof = max(len(y) - 2, 1)
    s2 = (w * resid ** 2).sum() / dof
    cov = s2 * np.linalg.inv(xtwx)
    return b, np.sqrt(np.diag(cov))


def stage_two(df, rho_col="rho_abs_income"):
    """Regress city-level terrain effects on how much elevation tracks money there.

    The regressor is the correlation between *absolute* elevation and income,
    not between TPI and income. TPI is a deviation from a 500 m local mean while
    income varies over much larger areas, so TPI is close to orthogonal to
    income in every city -- there would be almost no variation left to regress
    on. Absolute elevation is what gets capitalised into land value, and "are
    this city's hills rich?" is the city-level trait the design needs.
    """
    d = df.dropna(subset=["beta", "se", rho_col])
    d = d[d["se"] > 0]
    x, y, w = d[rho_col].values, d["beta"].values, 1.0 / d["se"].values ** 2
    b, se = wls(x, y, w)

    rng = np.random.default_rng(7)
    boot = []
    for _ in range(4000):
        idx = rng.integers(0, len(d), len(d))
        try:
            bb, _ = wls(x[idx], y[idx], w[idx])
            boot.append(bb)
        except Exception:
            pass
    boot = np.array(boot)
    return {
        "n_cities": len(d),
        "rho_col": rho_col,
        "rho_min": float(x.min()), "rho_max": float(x.max()),
        "intercept_beta": b[0], "intercept_se": se[0],
        "intercept_pct": 100 * (np.exp(b[0]) - 1),
        "intercept_boot_lo": 100 * (np.exp(np.percentile(boot[:, 0], 2.5)) - 1),
        "intercept_boot_hi": 100 * (np.exp(np.percentile(boot[:, 0], 97.5)) - 1),
        "slope": b[1], "slope_se": se[1],
        "slope_boot_lo": np.percentile(boot[:, 1], 2.5),
        "slope_boot_hi": np.percentile(boot[:, 1], 97.5),
        "naive_mean_pct": 100 * (np.exp(np.average(y, weights=w)) - 1),
    }


def main():
    paths = sorted(glob.glob(CELLS))
    print(f"{len(paths)} city tables\n", flush=True)
    rows = []
    for p in paths:
        try:
            r = city_estimates(p)
            if r is None:
                print(f"  [skip] {os.path.basename(p):38s} too small", flush=True)
                continue
            rows.append(r)
            print(f"  {r['city']:38s} {r['pct']:+7.2f}%  (z={r['z']:+5.2f})  "
                  f"rho={r['rho_income']:+.3f}  relief={r['relief_p99']:6.1f}m  "
                  f"n={r['n_events']:,}", flush=True)
        except Exception as e:
            print(f"  [FAIL] {os.path.basename(p):38s} {type(e).__name__}: {e}", flush=True)

    df = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(f"{OUT}/city_estimates.csv", index=False)

    print("\n" + "=" * 78)
    print("STAGE TWO — decomposing the effect across cities")
    print("=" * 78)
    s = stage_two(df)
    for k, v in s.items():
        print(f"  {k:22s} {v:,.4f}" if isinstance(v, float) else f"  {k:22s} {v}")
    print("\n  (secondary, TPI-based rho)")
    s2 = stage_two(df, rho_col="rho_income")
    print(f"    intercept {s2['intercept_pct']:+.2f}%  "
          f"[{s2['intercept_boot_lo']:+.2f}, {s2['intercept_boot_hi']:+.2f}]  "
          f"slope {s2['slope']:+.3f}")
    pd.DataFrame([s]).to_csv(f"{OUT}/stage_two.csv", index=False)

    flat = df[df["relief_p99"] < 30]
    hilly = df[df["relief_p99"] >= 30]
    print(f"\n  placebo (flat, <30 m relief):  n={len(flat)}  "
          f"mean effect {flat['pct'].mean():+.2f}%")
    print(f"  hilly (>=30 m relief):         n={len(hilly)}  "
          f"mean effect {hilly['pct'].mean():+.2f}%")


if __name__ == "__main__":
    main()
