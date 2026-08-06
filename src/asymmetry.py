"""The sign-reversal test.

A property offender goes in empty-handed and comes out carrying. Metabolic cost
is asymmetric in gradient, so high ground is expensive to *approach* and cheap
to *leave loaded*. Those two terms have opposite signs and their balance is set
by how heavy the goods are. Hence the prediction this file exists to test:

    the terrain coefficient should become more positive as loot mass rises,
    and may cross zero.

Existing work assumes a single monotone deterrent effect of elevation, so it
predicts a flat line here. Three outcomes are distinguishable:

    rising trend      movement cost is real and directional  (new claim)
    flat and negative single monotone deterrent               (field's claim)
    flat and null     terrain is a proxy for something else

Two controls carry most of the weight:

    NO_LOOT  vandalism and arson. Nothing is carried out, so the escape term is
             zero by construction and these should sit at the light end
             regardless of anything else. If they track the heavy classes, the
             mechanism is not about carrying.

    MVT      motor vehicle theft. The "loot" drives itself, so its escape cost
             is unrelated to gradient. Should be off the line entirely.
"""
from __future__ import annotations

import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from analyze import SES, coef, poisson, prep
from crime_classes import MASS_LABEL

warnings.filterwarnings("ignore")
OUT = "outputs"

# Representative load per class, kg. Set from the taxonomy, before any fitting.
CLASS_KG = {"MASS_1": 0.3, "MASS_2": 2.0, "MASS_3": 7.0, "MASS_4": 14.0, "MASS_5": 25.0}


def prep_move(path="data/interim/sf_cells.parquet"):
    df = prep(path)
    for c in ("rtc_light", "rtc_mid", "rtc_heavy", "loot_penalty"):
        s = df[c]
        df[f"{c}_z"] = (s - s.mean()) / s.std()
    return df


def by_class(df, xvar="tpi_500_z"):
    """Estimate the terrain coefficient separately for each crime class."""
    rows = []
    specs = [(f"n_{k}", MASS_LABEL[int(k[-1])], CLASS_KG[k]) for k in CLASS_KG]
    specs += [("n_MVT", "motor vehicle theft (self-propelled)", None),
              ("n_NO_LOOT", "vandalism / arson (nothing carried)", 0.0)]
    for col, label, kg in specs:
        if col not in df or df[col].sum() < 500:
            continue
        res, names = poisson(df, col, [xvar] + SES, bg_fe=True)
        c = coef(res, names, xvar)
        c.update({"outcome": label, "loot_kg": kg, "n_events": int(df[col].sum()),
                  "col": col})
        rows.append(c)
    return pd.DataFrame(rows)


def trend_test(d, n_boot=8000, seed=11):
    """Is the terrain coefficient rising with loot mass?

    Weighted regression of each class's coefficient on its load. MVT is excluded
    (no gradient-dependent escape cost); vandalism is included at 0 kg, which is
    the honest place for it since nothing is carried.
    """
    m = d[d["loot_kg"].notna()].copy()
    x = m["loot_kg"].values.astype(float)
    y = m["beta"].values
    w = 1.0 / m["se"].values ** 2
    X = np.column_stack([np.ones_like(x), x])
    W = np.diag(w)
    b = np.linalg.solve(X.T @ W @ X, X.T @ W @ y)

    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        i = rng.integers(0, len(m), len(m))
        try:
            Xi = np.column_stack([np.ones(len(i)), x[i]])
            Wi = np.diag(w[i])
            boot.append(np.linalg.solve(Xi.T @ Wi @ Xi, Xi.T @ Wi @ y[i]))
        except Exception:
            pass
    boot = np.array(boot)
    return {
        "n_classes": len(m),
        "intercept_at_0kg_pct": 100 * (np.exp(b[0]) - 1),
        "slope_per_kg": b[1],
        "slope_lo": np.percentile(boot[:, 1], 2.5),
        "slope_hi": np.percentile(boot[:, 1], 97.5),
        "p_slope_le_0": float((boot[:, 1] <= 0).mean()),
        "pred_at_25kg_pct": 100 * (np.exp(b[0] + b[1] * 25) - 1),
    }


def main():
    df = prep_move()
    print(f"cells {len(df):,}   block groups {df.GEOID.nunique():,}   "
          f"incidents {df.n_total.sum():,}\n")

    print("=" * 84)
    print("Does the new variable differ from plain relative height?")
    print("=" * 84)
    for a, b in [("tpi_500", "loot_penalty"), ("tpi_500", "rtc_light"),
                 ("loot_penalty", "rtc_light")]:
        print(f"   corr({a:13s}, {b:13s}) = {df[a].corr(df[b]):+.3f}")

    print("\n" + "=" * 84)
    print("TERRAIN COEFFICIENT BY LOOT MASS   (% change per +1 SD of TPI 500 m)")
    print("=" * 84)
    d = by_class(df)
    print(d[["outcome", "loot_kg", "n_events", "pct", "lo", "hi", "z"]]
          .to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    d.to_csv(f"{OUT}/asymmetry_by_class.csv", index=False)

    print("\n" + "=" * 84)
    print("TREND TEST — does the coefficient rise with the weight carried out?")
    print("=" * 84)
    t = trend_test(d)
    for k, v in t.items():
        print(f"   {k:24s} {v:,.4f}" if isinstance(v, float) else f"   {k:24s} {v}")
    pd.DataFrame([t]).to_csv(f"{OUT}/asymmetry_trend.csv", index=False)

    print("\n" + "=" * 84)
    print("SAME TEST ON THE DIRECTIONAL COST VARIABLE (loot penalty)")
    print("=" * 84)
    d2 = by_class(df, xvar="loot_penalty_z")
    print(d2[["outcome", "loot_kg", "n_events", "pct", "lo", "hi", "z"]]
          .to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    d2.to_csv(f"{OUT}/asymmetry_by_class_penalty.csv", index=False)


if __name__ == "__main__":
    main()
