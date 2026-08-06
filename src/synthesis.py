"""Cross-city synthesis: the pool, its heterogeneity, and the moderator model.

This replaces two things the review objected to. The first is the fixed-effect
inverse-variance pool, whose interval assumes a common effect the cities do not
share. The second, and more serious, is the three-degree gradient floor: a
threshold picked after looking at the terrain data, which split the sample and
set the headline number. A cut like that cannot be defended as anything but a
researcher degree of freedom, however good the measurement argument behind it.

The replacement is a meta-regression of the city effect on the city's slope
standard deviation, which uses all nine cities and treats terrain measurability
as the continuous thing it is. The threshold split is retained below it as a
sensitivity analysis, which is the right rank for it.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import meta
import vizstyle as vs

OUT = "outputs"


def _pct(x):
    return 100 * (np.exp(x) - 1)


def run():
    d = pd.read_csv(f"{OUT}/slope_per_degree_full.csv")
    d["label"] = d.city.map(vs.city)
    y, s, lab = d.beta.values, d.se.values, d.label.values

    rows = []

    # ---------------------------------------------------------- the pools ---
    pools = {}
    for name, sub in [("all nine cities", d),
                      ("above 3 deg floor", d[d.qualifies]),
                      ("below 3 deg floor", d[~d.qualifies])]:
        fe = meta.fixed_effect(sub.beta.values, sub.se.values)
        re = meta.random_effects(sub.beta.values, sub.se.values)
        pools[name] = re
        rows.append({
            "sample": name, "k": re["k"],
            "fe_pct": fe["pct"], "fe_lo": fe["pct_lo"], "fe_hi": fe["pct_hi"],
            "re_pct": re["pct"], "re_lo": re["pct_lo"], "re_hi": re["pct_hi"],
            "re_lo_normal": re["pct_lo_normal"], "re_hi_normal": re["pct_hi_normal"],
            "tau2": re["tau2"], "tau2_dl": re["tau2_dl"], "tau2_pm": re["tau2_pm"],
            "tau2_lo": re["tau2_lo"], "tau2_hi": re["tau2_hi"],
            "tau_pct": _pct(re["tau"]),
            "I2": re["I2"], "I2_lo": re["I2_lo"], "I2_hi": re["I2_hi"],
            "Q": re["Q"], "Q_p": re["Q_p"],
            "pi_lo": re["pct_pi_lo"], "pi_hi": re["pct_pi_hi"],
            "method": re["method"],
        })
    pd.DataFrame(rows).to_csv(f"{OUT}/meta_pools.csv", index=False)

    # -------------------------------------------------------- leave-one-out --
    loo_all = pd.DataFrame(meta.leave_one_out(y, s, lab))
    loo_all["sample"] = "all nine cities"
    q = d[d.qualifies]
    loo_q = pd.DataFrame(meta.leave_one_out(q.beta.values, q.se.values,
                                            q.label.values))
    loo_q["sample"] = "above 3 deg floor"
    loo = pd.concat([loo_all, loo_q], ignore_index=True)
    loo.to_csv(f"{OUT}/meta_leave_one_out.csv", index=False)

    # ------------------------------------------------------ meta-regression --
    # Centred at three degrees so the intercept is the fitted effect exactly at
    # the old threshold, which makes the two analyses directly comparable
    # instead of merely adjacent.
    xc = d.slope_sd.values - 3.0
    mr = meta.meta_regression(y, s, [xc], ["slope_sd_minus_3"])
    terms = pd.DataFrame(mr["terms"])
    terms["pct"] = _pct(terms.beta)
    terms["pct_lo"] = _pct(terms.lo)
    terms["pct_hi"] = _pct(terms.hi)
    terms["tau2_resid"] = mr["tau2_resid"]
    terms["tau2_null"] = mr["tau2_null"]
    terms["R2"] = mr["R2"]
    terms["k"] = mr["k"]
    terms.to_csv(f"{OUT}/meta_regression.csv", index=False)

    # Fitted effect across the observed range of terrain, which is the figure
    # that replaces the floor plot.
    grid = np.linspace(d.slope_sd.min(), d.slope_sd.max(), 60)
    fitted = pd.DataFrame({
        "slope_sd": grid,
        "pct": [_pct(mr["predict"]([g - 3.0])) for g in grid],
    })
    fitted.to_csv(f"{OUT}/meta_regression_fit.csv", index=False)

    # ------------------------------------------------------------- report ----
    print("=" * 74)
    print("CROSS-CITY SYNTHESIS")
    print("=" * 74)
    for r in rows:
        print(f"\n{r['sample']}  (k={r['k']})")
        print(f"  fixed effect     {r['fe_pct']:+6.2f}%  "
              f"[{r['fe_lo']:+6.2f},{r['fe_hi']:+6.2f}]")
        print(f"  random effects   {r['re_pct']:+6.2f}%  "
              f"[{r['re_lo']:+6.2f},{r['re_hi']:+6.2f}]  ({r['method']})")
        print(f"    normal-theory  "
              f"[{r['re_lo_normal']:+6.2f},{r['re_hi_normal']:+6.2f}]")
        if np.isfinite(r["pi_lo"]):
            print(f"  prediction int.  [{r['pi_lo']:+6.2f},{r['pi_hi']:+6.2f}]"
                  "   <- where a new city would land")
        print(f"  tau^2 {r['tau2']:.5f} (REML)  DL {r['tau2_dl']:.5f}  "
              f"PM {r['tau2_pm']:.5f}")
        i2lo = r["I2_lo"] if np.isfinite(r["I2_lo"]) else float("nan")
        i2hi = r["I2_hi"] if np.isfinite(r["I2_hi"]) else float("nan")
        print(f"  I^2 {r['I2']:.2f}  [{i2lo:.2f},{i2hi:.2f}]   "
              f"Q={r['Q']:.1f} p={r['Q_p']:.4f}")

    print("\n" + "-" * 74)
    print("META-REGRESSION on within-city slope SD (all nine cities)")
    print("-" * 74)
    for t in mr["terms"]:
        print(f"  {t['term']:22s} {t['beta']:+8.4f}  se {t['se']:.4f}  "
              f"[{t['lo']:+.4f},{t['hi']:+.4f}]  p={t['p']:.4f}")
    print(f"  residual tau^2 {mr['tau2_resid']:.5f} vs {mr['tau2_null']:.5f} "
          f"unconditional   R^2 = {mr['R2']:.2f}")
    b1 = mr["terms"][1]
    print(f"\n  Each extra degree of within-city slope SD moves the per-degree")
    print(f"  effect by {_pct(b1['beta']):+.2f}%  "
          f"[{_pct(b1['lo']):+.2f},{_pct(b1['hi']):+.2f}] -- i.e. toward zero.")
    print(f"  Fitted effect at SD=3.0 deg: {_pct(mr['predict']([0.0])):+.2f}%")
    print(f"  Fitted at SD=4.5: {_pct(mr['predict']([1.5])):+.2f}%   "
          f"at SD=1.0: {_pct(mr['predict']([-2.0])):+.2f}%")

    print("\n" + "-" * 74)
    print("LEAVE ONE CITY OUT")
    print("-" * 74)
    for samp in loo["sample"].unique():
        print(f"  {samp}")
        for r in loo[loo["sample"] == samp].itertuples():
            print(f"    without {r.dropped:22s} {r.pct:+6.2f}%  "
                  f"[{r.lo:+6.2f},{r.hi:+6.2f}]  I2={r.I2:.2f}")
    print("\nwrote meta_pools.csv, meta_leave_one_out.csv, meta_regression.csv,"
          " meta_regression_fit.csv")


if __name__ == "__main__":
    run()
