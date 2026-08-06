"""Regenerate every result table and figure from the current city tables.

The analysis was built incrementally, and tables written at different points had
drifted out of step with the data underneath them -- Chicago, for instance, was
rebuilt after the classifier repair but `slope_per_degree_full.csv` still held
its pre-repair coefficient. This script exists so that the whole output set can
be rebuilt in dependency order from one command, and so that a number in the
manuscript can always be traced to a file that was produced by the data now on
disk.

What it does NOT rebuild, and why: the spatial diagnostics, the target-exposure
tests, the DEM-resolution comparison and the classifier validation all depend on
inputs that have not changed (San Francisco segments, the SFMTA parking census,
a 1 m elevation fetch, and 511 hand-coded strings respectively). They are
expensive, several require network fetches, and re-running them would produce
identical numbers. They are listed at the end as untouched.
"""
from __future__ import annotations

import glob
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings("ignore")

from analyze import SES, coef, poisson
from confirmatory import paired_coef_test, pooled

CELLS = "data/interim/cells_exposure/*.parquet"
SEGS = "data/interim/seg_analysis"
OUT = "outputs"
FLOOR = 3.0
PANEL_SEGS = [("San Francisco", "sfgov"), ("Seattle", "seattle"),
              ("Cincinnati", "cincinnati"), ("Pittsburgh", "pittsburgh")]


def slug(path):
    return os.path.basename(path).replace(".parquet", "")


def prep_cells(path):
    """Estimation sample for one city. Mirrors the confirmatory specification."""
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
    for v in ("tpi_500", "slope_deg"):
        s = d[v].astype(float)
        d[v + "_z"] = (s - s.mean()) / (s.std() or 1)
    tc = [c for c in d.columns if c.startswith("n_MASS_")]
    d["n_theft"] = d[tc].sum(axis=1)
    clean = [c for c in ["n_MASS_1", "n_MASS_2", "n_MASS_4", "n_MASS_5",
                         "n_MVT", "n_NO_LOOT"] if c in d]
    d["n_clean"] = d[clean].sum(axis=1)
    need = SES + ["slope_deg_raw", "tpi_500_z", "exposure", "GEOID"]
    return d.dropna(subset=need).reset_index(drop=True)


def prep_segs(path):
    d = pd.read_parquet(path)
    if "seg_len_m" in d:
        d = d[d.seg_len_m >= 20]
    d["exposure"] = d.housing_units_cell.fillna(0) + d.pop_cell.fillna(0)
    d = d[d.exposure > 2]
    d["log_income"] = np.log(d.median_hh_income.clip(lower=5000))
    d["log_value"] = np.log(d.median_home_value.clip(lower=50000))
    d["log_density"] = np.log(d.exposure)
    d["owner_share"] = d.owner_share.astype(float)
    d["vacancy_rate"] = d.vacancy_rate.astype(float)
    prop = [c for c in d.columns if c.startswith("n_MASS_")] + \
           [c for c in ("n_MVT", "n_NO_LOOT") if c in d]
    d["n_prop"] = d[prop].sum(axis=1)
    d = d[d.n_prop / d.exposure.clip(lower=1) < 50]
    d = d[d.groupby("GEOID").GEOID.transform("size") >= 3]
    d["slope_deg_raw"] = d.slope_deg.astype(float)
    for v in ("betweenness", "intersection_density", "permeability",
              "egress_count", "walk_drive_ratio"):
        if v in d:
            s = d[v].astype(float)
            d[v + "_z"] = (s - s.mean()) / (s.std() or 1)
    return d.dropna(subset=SES + ["slope_deg_raw", "exposure", "GEOID"]).reset_index(drop=True)


def panel():
    """Per-degree slope effect and per-SD slope vs relative height, all cities."""
    rows, cmp_rows = [], []
    for f in sorted(glob.glob(CELLS)):
        d = prep_cells(f)
        if len(d) < 300 or d.n_total.sum() < 20000:
            continue
        sd = d.slope_deg.std()
        r, n = poisson(d, "n_total", ["slope_deg_raw"] + SES, bg_fe=True)
        k = coef(r, n, "slope_deg_raw")
        rows.append({"city": slug(f), "slope_sd": sd, "qualifies": sd >= FLOOR,
                     "beta": k["beta"], "se": k["se"], "pct_per_deg": k["pct"],
                     "lo": k["lo"], "hi": k["hi"], "z": k["z"],
                     "n": len(d), "events": int(d.n_total.sum())})
        o = {"city": slug(f), "expo": "bldg", "n": len(d),
             "events": int(d.n_total.sum()), "slope_sd": sd}
        for v in ("tpi_500_z", "slope_deg_z"):
            rr, nn = poisson(d, "n_total", [v] + SES, bg_fe=True)
            kk = coef(rr, nn, v)
            o[v], o[v + "_z"] = kk["pct"], kk["z"]
        cmp_rows.append(o)
        print(f"    {slug(f):28s} {k['pct']:+7.2f}%/deg  (SD {sd:.2f})", flush=True)

    p = pd.DataFrame(rows).sort_values("slope_sd", ascending=False)
    p.to_csv(f"{OUT}/slope_per_degree_full.csv", index=False)
    p.to_csv(f"{OUT}/slope_per_degree.csv", index=False)
    pd.DataFrame(cmp_rows).to_csv(f"{OUT}/slope_vs_tpi.csv", index=False)
    q, b = p[p.qualifies], p[~p.qualifies]
    return pooled(q.beta.values, q.se.values), pooled(b.beta.values, b.se.values), p


def noloot(n_boot=600):
    """H1: theft vs crimes that carry nothing, above the gradient floor."""
    rows = []
    for f in sorted(glob.glob(CELLS)):
        d = prep_cells(f)
        if d.slope_deg.std() < FLOOR:
            continue
        if "n_NO_LOOT" not in d or d.n_NO_LOOT.sum() < 3000:
            print(f"    [skip] {slug(f)} — too few no-loot incidents", flush=True)
            continue
        r = paired_coef_test(d, "n_theft", "n_NO_LOOT",
                             xvar="slope_deg_raw", n_boot=n_boot)
        r["city"] = slug(f)
        rows.append(r)
        print(f"    {slug(f):28s} theft {r['pct_a']:+6.2f}  no-loot {r['pct_b']:+6.2f}"
              f"  {'same' if r['contains_zero'] else 'DIFFERENT'}", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(f"{OUT}/h1_slope_floor.csv", index=False)
    se = (d.diff_hi - d.diff_lo) / (2 * 1.96)
    return pooled(d.diff_beta.values, se.values), d


def ladder():
    """Loot-mass ladder on San Francisco segments."""
    from crime_classes import MASS_LABEL
    d = prep_segs(f"{SEGS}/sfgov.parquet")
    s = d.slope_deg.astype(float)
    d["slope_deg_raw"] = s
    spec = [(f"n_MASS_{i}", MASS_LABEL[i].split(" ", 1)[1], kg)
            for i, kg in zip(range(1, 6), (0.3, 2, 7, 14, 25))]
    spec += [("n_MVT", "motor vehicle theft", np.nan),
             ("n_NO_LOOT", "vandalism / arson", 0.0)]
    rows = []
    for col, lab, kg in spec:
        if col not in d or d[col].sum() < 500:
            continue
        r, n = poisson(d, col, ["slope_deg_raw"] + SES, bg_fe=True)
        k = coef(r, n, "slope_deg_raw")
        rows.append({"label": lab, "loot_kg": kg, "n": int(d[col].sum()),
                     "pct": k["pct"], "lo": k["lo"], "hi": k["hi"], "z": k["z"]})
    pd.DataFrame(rows).to_csv(f"{OUT}/loot_ladder_slope.csv", index=False)
    print(f"    {len(rows)} crime classes", flush=True)


def mediation():
    """H3: does street-network structure absorb the slope effect?"""
    MED = ["betweenness_z", "intersection_density_z", "permeability_z",
           "egress_count_z", "walk_drive_ratio_z"]
    rows = []
    for name, sl in PANEL_SEGS:
        path = f"{SEGS}/{sl}.parquet"
        if not os.path.exists(path):
            continue
        d = prep_segs(path)
        med = [m for m in MED if m in d]
        r0, n0 = poisson(d, "n_prop", ["slope_deg_raw"] + SES, bg_fe=True)
        c0 = coef(r0, n0, "slope_deg_raw")
        r1, n1 = poisson(d, "n_prop", ["slope_deg_raw"] + SES + med, bg_fe=True)
        c1 = coef(r1, n1, "slope_deg_raw")
        rows.append({"city": name, "before": c0["pct"], "after": c1["pct"],
                     "att": 1 - abs(c1["beta"]) / abs(c0["beta"]),
                     "b0": c0["beta"], "s0": c0["se"],
                     "b1": c1["beta"], "s1": c1["se"], "n": len(d)})
        print(f"    {name:16s} {c0['pct']:+7.2f} -> {c1['pct']:+7.2f}", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(f"{OUT}/h3_mediation_multicity.csv", index=False)
    return pooled(d.b0.values, d.s0.values), pooled(d.b1.values, d.s1.values)


def drop_mass3():
    """Headline with the financially contaminated loot rung removed."""
    rows = []
    for f in sorted(glob.glob(CELLS)):
        d = prep_cells(f)
        if d.slope_deg.std() < FLOOR:
            continue
        o = {"city": slug(f)}
        for lab, y in (("all", "n_total"), ("excl MASS_3", "n_clean")):
            r, n = poisson(d, y, ["slope_deg_raw"] + SES, bg_fe=True)
            k = coef(r, n, "slope_deg_raw")
            o[lab], o[lab + "_b"], o[lab + "_se"] = k["pct"], k["beta"], k["se"]
        rows.append(o)
    d = pd.DataFrame(rows)
    d.to_csv(f"{OUT}/robustness_drop_mass3.csv", index=False)
    return (pooled(d["all_b"].values, d["all_se"].values),
            pooled(d["excl MASS_3_b"].values, d["excl MASS_3_se"].values))


def main():
    print("1/6  city panel (per-degree, and slope vs relative height)")
    above, below, panel_df = panel()
    print("\n2/6  no-loot control")
    h1, h1_df = noloot()
    print("\n3/6  loot-mass ladder")
    ladder()
    print("\n4/6  network mediation")
    m_before, m_after = mediation()
    print("\n5/6  drop-MASS_3 robustness")
    r_all, r_clean = drop_mass3()

    print("\n6/6  figures")
    import figures_paper as F
    F.fig_gradient_floor(); F.fig_noloot(); F.fig_target_denominator()
    F.fig_loot_ladder(); F.fig_slope_vs_height()

    # Cross-city synthesis has to run before the figures, because fig 1 now
    # draws the meta-regression fit rather than a threshold band.
    print("\n7/8  synthesis, diagnostics and the review-response analyses")
    import synthesis
    synthesis.run()
    import ppml_diagnostics
    ppml_diagnostics.run()
    F.fig_gradient_floor()

    # Submission TIFFs, so they can never drift behind the PNGs. Raises if any
    # figure falls outside PLOS's format limits.
    print("\n8/8  PLOS submission figures")
    import make_plos_figs
    make_plos_figs.convert()

    att = 1 - abs(np.log1p(m_after["pooled_pct"] / 100)) / \
              abs(np.log1p(m_before["pooled_pct"] / 100))
    print("\n" + "=" * 68)
    print("HEADLINE NUMBERS (regenerated)")
    print("=" * 68)
    # The fixed-effect pool is still computed because several like-for-like
    # robustness comparisons are made against it, but the paper's headline is
    # the random-effects pool with its prediction interval, so print that.
    import meta
    _q = panel_df[panel_df.qualifies]
    _re = meta.random_effects(_q.beta.values, _q.se.values)
    print(f"  above floor  {_re['pct']:+.2f}%/deg "
          f"[{_re['pct_lo']:+.2f},{_re['pct_hi']:+.2f}]  I2={_re['I2']:.2f}  "
          f"k={_re['k']}   (random effects, Hartung-Knapp)")
    print(f"    prediction interval for a new city "
          f"[{_re['pct_pi_lo']:+.2f},{_re['pct_pi_hi']:+.2f}]")
    print(f"    fixed-effect pool, for comparison only: "
          f"{above['pooled_pct']:+.2f}% [{above['lo']:+.2f},{above['hi']:+.2f}]")
    print(f"  below floor  {below['pooled_pct']:+.2f}%/deg  I2={below['I2']:.2f}  k={below['k']}")
    print(f"  H1 pooled    {h1['pooled_pct']:+.2f} pp/deg "
          f"[{h1['lo']:+.2f},{h1['hi']:+.2f}]  same in "
          f"{int(h1_df.contains_zero.sum())}/{len(h1_df)}")
    print(f"  mediation    {m_before['pooled_pct']:+.2f} -> {m_after['pooled_pct']:+.2f} "
          f"({att:+.1%} attenuation)")
    print(f"  drop MASS_3  {r_all['pooled_pct']:+.2f} -> {r_clean['pooled_pct']:+.2f}")
    print("\nNot rebuilt (inputs unchanged, several need the network):")
    print("  spatial_*, target_exposure_*, dem_resolution_*, exposure_diagnostics,")
    print("  classifier_validation, and the incident-level tests. Rebuild those with:")
    print("  incident_tests.py, classifier_uncertainty.py, target_multicity.py,")
    print("  spatial_bootstrap.py")


if __name__ == "__main__":
    main()
