"""Confirmatory tests, exactly as specified in PREREGISTRATION.md.

Nothing here chooses a specification after seeing a result. Inclusion is applied
first on terrain and volume, then the registered tests run.

The statistical care that matters is in `paired_coef_test`. H1 compares the
terrain coefficient for theft against the one for no-loot crime, both estimated
on the *same* segments with the *same* covariates. Those two estimates are
correlated, so comparing their confidence intervals for overlap would be wrong
in an unknown direction. The difference is therefore bootstrapped directly,
resampling whole block groups so the resampling unit matches the clustering
unit.
"""
from __future__ import annotations

import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from analyze import SES, coef, poisson

warnings.filterwarnings("ignore")

# PREREGISTRATION.md section 4
MIN_TPI_SD = 4.0
MIN_EVENTS = 20_000
MIN_EV_PER_UNIT = 1.0
MIN_NOLOOT = 3_000
# section 7
ATTENUATION_THRESHOLD = 0.40
SUBSTANTIVE_FLOOR_PCT = 5.0

MEDIATORS = ["betweenness_z", "intersection_density_z", "permeability_z",
             "egress_count_z", "visibility_z"]


def qualifies(df, radius=500):
    """Section 4 inclusion criteria. Terrain and volume only, never the outcome."""
    tpi_sd = df[f"tpi_{radius}"].std()
    ev = df["n_total"].sum()
    reasons = []
    if tpi_sd < MIN_TPI_SD:
        reasons.append(f"TPI SD {tpi_sd:.2f} m < {MIN_TPI_SD}")
    if ev < MIN_EVENTS:
        reasons.append(f"{ev:,} events < {MIN_EVENTS:,}")
    if ev / max(len(df), 1) < MIN_EV_PER_UNIT:
        reasons.append(f"{ev/max(len(df),1):.2f} events/unit < {MIN_EV_PER_UNIT}")
    return (not reasons), reasons


def theft_column(df):
    cols = [c for c in df.columns if c.startswith("n_MASS_")]
    if not cols:
        return None
    df["n_theft"] = df[cols].sum(axis=1)
    return "n_theft"


def paired_coef_test(df, col_a, col_b, xvar="tpi_500_z", n_boot=1000, seed=17):
    """Bootstrap the difference between two terrain coefficients on the same data.

    Resamples block groups with replacement -- the cluster, not the row, because
    that is the level the standard errors are clustered at and the level at which
    observations are dependent. Both models are refit inside every draw so the
    correlation between the two estimates is carried through automatically.
    """
    base = {}
    for lab, col in (("a", col_a), ("b", col_b)):
        res, names = poisson(df, col, [xvar] + SES, bg_fe=True)
        base[lab] = coef(res, names, xvar)

    groups = df["GEOID"].values
    uniq = np.unique(groups)
    idx_by_g = {g: np.flatnonzero(groups == g) for g in uniq}
    rng = np.random.default_rng(seed)

    diffs, ok = [], 0
    for _ in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        rows = np.concatenate([idx_by_g[g] for g in pick])
        d = df.iloc[rows].copy()
        # relabel so repeated block groups stay distinct fixed effects
        d["GEOID"] = np.repeat(np.arange(len(pick)).astype(str),
                               [len(idx_by_g[g]) for g in pick])
        try:
            ra, na = poisson(d, col_a, [xvar] + SES, bg_fe=True)
            rb, nb = poisson(d, col_b, [xvar] + SES, bg_fe=True)
            da = ra.params[na.index(xvar)]
            db = rb.params[nb.index(xvar)]
            if np.isfinite(da) and np.isfinite(db) and abs(da) < 5 and abs(db) < 5:
                diffs.append(da - db)
                ok += 1
        except Exception:
            pass

    diffs = np.array(diffs)
    d0 = base["a"]["beta"] - base["b"]["beta"]
    return {
        "beta_a": base["a"]["beta"], "pct_a": base["a"]["pct"],
        "beta_b": base["b"]["beta"], "pct_b": base["b"]["pct"],
        "diff_beta": d0,
        "diff_pct_pts": base["a"]["pct"] - base["b"]["pct"],
        "diff_lo": np.percentile(diffs, 2.5) if len(diffs) > 50 else np.nan,
        "diff_hi": np.percentile(diffs, 97.5) if len(diffs) > 50 else np.nan,
        "contains_zero": bool(np.percentile(diffs, 2.5) <= 0 <= np.percentile(diffs, 97.5))
        if len(diffs) > 50 else None,
        "n_boot_ok": ok,
    }


def mediation_test(df, xvar="tpi_500_z", outcome="n_total", mediators=None):
    """H3. How much of the terrain coefficient survives network and visibility controls?"""
    med = [m for m in (mediators or MEDIATORS) if m in df.columns]
    if not med:
        return None
    r0, n0 = poisson(df, outcome, [xvar] + SES, bg_fe=True)
    r1, n1 = poisson(df, outcome, [xvar] + SES + med, bg_fe=True)
    b0 = coef(r0, n0, xvar)
    b1 = coef(r1, n1, xvar)
    att = 1 - (abs(b1["beta"]) / abs(b0["beta"])) if abs(b0["beta"]) > 1e-9 else np.nan
    return {
        "mediators_used": ";".join(med),
        "pct_before": b0["pct"], "pct_after": b1["pct"],
        "attenuation": att,
        "supports_M2": bool(att >= ATTENUATION_THRESHOLD),
    }


def pooled(betas, ses):
    """Inverse-variance meta-analysis with a Q test for heterogeneity."""
    b, s = np.asarray(betas, float), np.asarray(ses, float)
    m = np.isfinite(b) & np.isfinite(s) & (s > 0)
    b, s = b[m], s[m]
    if len(b) == 0:
        return None
    w = 1 / s ** 2
    mu = np.sum(w * b) / np.sum(w)
    se = np.sqrt(1 / np.sum(w))
    Q = np.sum(w * (b - mu) ** 2)
    dfree = max(len(b) - 1, 1)
    I2 = max(0.0, (Q - dfree) / Q) if Q > 0 else 0.0
    return {
        "k": int(len(b)),
        "pooled_pct": 100 * (np.exp(mu) - 1),
        "lo": 100 * (np.exp(mu - 1.96 * se) - 1),
        "hi": 100 * (np.exp(mu + 1.96 * se) - 1),
        "z": mu / se,
        "Q": Q, "I2": I2,
        "substantively_negligible": bool(abs(100 * (np.exp(mu) - 1)) < SUBSTANTIVE_FLOOR_PCT),
    }
