"""Execute the registered tests in PREREGISTRATION.md and write the results.

Prefers street-segment tables when they exist and falls back to 100 m cells,
reporting which was used per city. Inclusion is applied before any outcome model
is fitted.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from analyze import RADII, SES, coef, poisson
from analyze_national import prep_city
from confirmatory import (MIN_NOLOOT, SUBSTANTIVE_FLOOR_PCT, mediation_test,
                          paired_coef_test, pooled, qualifies, theft_column)
from crime_classes import MASS_LABEL

warnings.filterwarnings("ignore")
OUT = "outputs"
CLASS_KG = {"MASS_1": 0.3, "MASS_2": 2.0, "MASS_3": 7.0, "MASS_4": 14.0, "MASS_5": 25.0}


def nice(p):
    return (os.path.basename(p).replace(".parquet", "").replace("data_", "")
            .replace("_gov", "").replace("_org", "").replace("cityof", ""))


def load_cities():
    """Segment tables where available, else grid cells."""
    out = []
    seg = {nice(p): p for p in glob.glob("data/interim/segments/*.parquet")}
    cell = {nice(p): p for p in glob.glob("data/interim/cells/*.parquet")}
    for name in sorted(set(seg) | set(cell)):
        path = seg.get(name, cell.get(name))
        unit = "segment" if name in seg else "cell"
        try:
            df = prep_city(pd.read_parquet(path))
        except Exception as e:
            print(f"  [load fail] {name}: {type(e).__name__}")
            continue
        out.append((name, unit, df))
    return out


def main(n_boot=1000):
    os.makedirs(OUT, exist_ok=True)
    cities = load_cities()
    print(f"{len(cities)} city tables found\n")

    print("=" * 88)
    print("INCLUSION  (PREREGISTRATION.md s4 — terrain and volume only)")
    print("=" * 88)
    panel, excluded = [], []
    for name, unit, df in cities:
        ok, why = qualifies(df)
        tag = "INCLUDE" if ok else "exclude"
        print(f"  [{tag}] {name:24s} {unit:8s} TPI SD {df.tpi_500.std():6.2f} m  "
              f"n={int(df.n_total.sum()):>8,}  {'; '.join(why)}")
        (panel if ok else excluded).append((name, unit, df))

    results = {"panel": [c[0] for c in panel], "excluded": [c[0] for c in excluded]}

    # ---- H1: the no-loot control -----------------------------------------
    print("\n" + "=" * 88)
    print("H1 — NO-LOOT CONTROL. Predicted: FALSIFIED (theft and no-loot indistinguishable)")
    print("=" * 88)
    h1 = []
    for name, unit, df in panel:
        tc = theft_column(df)
        if tc is None or "n_NO_LOOT" not in df or df.n_NO_LOOT.sum() < MIN_NOLOOT:
            print(f"  [skip] {name:24s} insufficient no-loot incidents")
            continue
        r = paired_coef_test(df, tc, "n_NO_LOOT", n_boot=n_boot)
        r.update({"city": name, "unit": unit,
                  "n_theft": int(df[tc].sum()), "n_noloot": int(df.n_NO_LOOT.sum())})
        h1.append(r)
        verdict = "indistinguishable" if r["contains_zero"] else "DIFFERENT"
        print(f"  {name:24s} theft {r['pct_a']:+7.2f}%  no-loot {r['pct_b']:+7.2f}%  "
              f"diff {r['diff_beta']:+.4f} [{r['diff_lo']:+.4f},{r['diff_hi']:+.4f}]  {verdict}")
    if h1:
        d = pd.DataFrame(h1)
        d.to_csv(f"{OUT}/h1_noloot.csv", index=False)
        n_same = int(d["contains_zero"].sum())
        se = (d.diff_hi - d.diff_lo) / (2 * 1.96)
        pd_ = pooled(d.diff_beta.values, se.values)
        results["H1"] = {"n_cities": len(d), "n_indistinguishable": n_same,
                         "pooled_diff": pd_}
        print(f"\n  indistinguishable in {n_same}/{len(d)} cities")
        if pd_:
            print(f"  pooled difference {pd_['pooled_pct']:+.2f} pct pts "
                  f"[{pd_['lo']:+.2f},{pd_['hi']:+.2f}]  I2={pd_['I2']:.2f}")
            falsified = n_same >= len(d) / 2 and pd_["lo"] <= 0 <= pd_["hi"]
            results["H1"]["falsified"] = bool(falsified)
            print(f"  >>> H1 {'FALSIFIED — effort mechanism rejected' if falsified else 'SUPPORTED'}")

    # ---- H2: loot-mass gradient -------------------------------------------
    print("\n" + "=" * 88)
    print("H2 — LOOT-MASS GRADIENT. Predicted: no monotone trend")
    print("=" * 88)
    h2 = []
    for name, unit, df in panel:
        for k, kg in CLASS_KG.items():
            col = f"n_{k}"
            if col not in df or df[col].sum() < 500:
                continue
            try:
                r, n = poisson(df, col, ["tpi_500_z"] + SES, bg_fe=True)
                c = coef(r, n, "tpi_500_z")
                h2.append({"city": name, "klass": k, "loot_kg": kg,
                           "n_events": int(df[col].sum()), **c})
            except Exception:
                pass
    if h2:
        d2 = pd.DataFrame(h2)
        d2.to_csv(f"{OUT}/h2_lootmass.csv", index=False)
        m = d2[d2.se > 0]
        x, y, w = m.loot_kg.values, m.beta.values, 1 / m.se.values ** 2
        X = np.column_stack([np.ones_like(x), x])
        b = np.linalg.solve(X.T @ (X * w[:, None]), X.T @ (w * y))
        rng = np.random.default_rng(3)
        bs = []
        for _ in range(4000):
            i = rng.integers(0, len(m), len(m))
            Xi = np.column_stack([np.ones(len(i)), x[i]])
            try:
                bs.append(np.linalg.solve(Xi.T @ (Xi * w[i, None]), Xi.T @ (w[i] * y[i]))[1])
            except Exception:
                pass
        lo, hi = np.percentile(bs, [2.5, 97.5])
        results["H2"] = {"slope_per_kg": b[1], "lo": lo, "hi": hi,
                         "falsified": bool(lo <= 0 <= hi), "n_estimates": len(m)}
        print(f"  slope {b[1]:+.5f} per kg  95% CI [{lo:+.5f}, {hi:+.5f}]   n={len(m)}")
        print(f"  >>> H2 {'FALSIFIED — no loot-mass gradient' if lo <= 0 <= hi else 'SUPPORTED'}")

    # ---- H3: mediation ----------------------------------------------------
    print("\n" + "=" * 88)
    print("H3 — MEDIATION by network and visibility. Predicted: >=40% attenuation")
    print("=" * 88)
    h3 = []
    for name, unit, df in panel:
        m = mediation_test(df)
        if m is None:
            print(f"  [skip] {name:24s} no network measures on this table")
            continue
        m["city"] = name
        h3.append(m)
        print(f"  {name:24s} {m['pct_before']:+7.2f}% -> {m['pct_after']:+7.2f}%  "
              f"attenuation {m['attenuation']:6.1%}")
    if h3:
        d3 = pd.DataFrame(h3)
        d3.to_csv(f"{OUT}/h3_mediation.csv", index=False)
        results["H3"] = {"mean_attenuation": float(d3.attenuation.mean()),
                         "supports_M2": bool(d3.supports_M2.mean() > 0.5)}
        print(f"\n  mean attenuation {d3.attenuation.mean():.1%}  "
              f">>> M2 {'SUPPORTED' if results['H3']['supports_M2'] else 'not supported'}")

    # ---- H4: motor vehicle theft -----------------------------------------
    print("\n" + "=" * 88)
    print("H4 — MOTOR VEHICLE THEFT. M1 says least deterred; M2 says most deterred")
    print("=" * 88)
    h4 = []
    for name, unit, df in panel:
        if "n_MVT" not in df or df.n_MVT.sum() < 2000:
            continue
        ranks = {}
        for col in [c for c in df.columns if c.startswith("n_MASS_")] + ["n_MVT"]:
            if df[col].sum() < 500:
                continue
            try:
                r, n = poisson(df, col, ["tpi_500_z"] + SES, bg_fe=True)
                ranks[col] = coef(r, n, "tpi_500_z")["beta"]
            except Exception:
                pass
        if "n_MVT" in ranks and len(ranks) >= 3:
            order = sorted(ranks, key=ranks.get)  # most deterred first
            pos = order.index("n_MVT")
            h4.append({"city": name, "mvt_rank": pos + 1, "n_classes": len(order),
                       "upper_half": pos < len(order) / 2})
            print(f"  {name:24s} MVT ranks {pos+1}/{len(order)} in deterrence "
                  f"({'more' if pos < len(order)/2 else 'less'} deterred than median)")
    if h4:
        pd.DataFrame(h4).to_csv(f"{OUT}/h4_mvt.csv", index=False)
        results["H4"] = {"n_cities": len(h4),
                         "n_upper_half": int(sum(r["upper_half"] for r in h4))}

    # ---- H5: placebo ------------------------------------------------------
    print("\n" + "=" * 88)
    print("H5 — PLACEBO. Sub-floor cities should show nothing")
    print("=" * 88)
    h5 = []
    for name, unit, df in excluded:
        if df.tpi_500.std() >= 4 or df.n_total.sum() < 5000:
            continue
        try:
            r, n = poisson(df, "n_total", ["tpi_500_z"] + SES, bg_fe=True)
            c = coef(r, n, "tpi_500_z")
            h5.append({"city": name, "tpi_sd": df.tpi_500.std(), **c})
            print(f"  {name:24s} TPI SD {df.tpi_500.std():5.2f} m  effect {c['pct']:+7.2f}%  z={c['z']:+5.2f}")
        except Exception:
            pass
    if h5:
        d5 = pd.DataFrame(h5)
        d5.to_csv(f"{OUT}/h5_placebo.csv", index=False)
        p5 = pooled(d5.beta.values, d5.se.values)
        results["H5"] = p5
        if p5:
            print(f"\n  pooled placebo {p5['pooled_pct']:+.2f}% [{p5['lo']:+.2f},{p5['hi']:+.2f}]")
            clean = p5["lo"] <= 0 <= p5["hi"]
            print(f"  >>> placebo {'clean' if clean else 'FAILS — residual confounding present'}")
            results["H5"]["clean"] = bool(clean)

    # ---- headline pooled effect ------------------------------------------
    print("\n" + "=" * 88)
    print("POOLED TERRAIN EFFECT across the qualifying panel")
    print("=" * 88)
    bs, ss = [], []
    for name, unit, df in panel:
        try:
            r, n = poisson(df, "n_total", ["tpi_500_z"] + SES, bg_fe=True)
            c = coef(r, n, "tpi_500_z")
            bs.append(c["beta"]); ss.append(c["se"])
        except Exception:
            pass
    p = pooled(bs, ss)
    results["pooled"] = p
    if p:
        print(f"  {p['pooled_pct']:+.2f}% per SD  [{p['lo']:+.2f}, {p['hi']:+.2f}]  "
              f"k={p['k']}  I2={p['I2']:.2f}")
        if p["substantively_negligible"]:
            print(f"  below the pre-registered {SUBSTANTIVE_FLOOR_PCT}% substantive floor")

    with open(f"{OUT}/confirmatory_results.json", "w") as fh:
        json.dump(results, fh, indent=2, default=float)
    print(f"\nwrote {OUT}/confirmatory_results.json")
    return results


if __name__ == "__main__":
    main(n_boot=int(sys.argv[1]) if len(sys.argv) > 1 else 1000)
