"""Models for the San Francisco pilot.

Three things get estimated:

  1. The attenuation path. The same coefficient under no controls, then SES
     controls, then block-group fixed effects. How far it falls is the headline:
     it measures how much of the raw elevation-crime association is just
     affluence sorting uphill.

  2. The radius sweep. The effect at each TPI radius. The peak locates the
     spatial scale over which offenders appear to treat targets as substitutes.

  3. The loot-mass ladder. The effect estimated separately by how heavy the
     stolen goods are. An effort mechanism predicts a gradient; an affluence
     confound predicts flat lines.

Estimation is Poisson with an exposure offset and standard errors clustered on
block group. Poisson (not OLS on rates) because the outcome is a count with many
zeros; cluster-robust SEs because crime and terrain are both spatially
autocorrelated and the naive SEs would be far too small.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

warnings.filterwarnings("ignore")

RADII = [50, 100, 250, 500, 1000, 2000]
SES = ["log_income", "log_value", "owner_share", "vacancy_rate", "log_density"]


def prep(path="data/interim/sf_cells.parquet") -> pd.DataFrame:
    df = pd.read_parquet(path)

    # Exposure. Residential units plus population catches both dwellings and the
    # street activity that drives theft-from-vehicle. Cells with essentially no
    # exposure (open water margin, parkland) are dropped rather than modelled,
    # since a rate is not defined there.
    df["exposure"] = df["housing_units_cell"].fillna(0) + df["pop_cell"].fillna(0)
    df = df[df["exposure"] > 5].copy()

    df["log_income"] = np.log(df["median_hh_income"].clip(lower=5000))
    df["log_value"] = np.log(df["median_home_value"].clip(lower=50000))
    df["log_density"] = np.log(df["exposure"])
    df["owner_share"] = df["owner_share"].astype(float)
    df["vacancy_rate"] = df["vacancy_rate"].astype(float)

    for r in RADII:
        for m in ("tpi", "tpiz", "pctl", "relief"):
            c = f"{m}_{r}"
            s = df[c]
            df[f"{c}_z"] = (s - s.mean()) / s.std()

    need = SES + [f"tpi_{r}_z" for r in RADII] + ["exposure", "GEOID"]
    df = df.dropna(subset=need)

    # A block group with one or two cells contributes no within-group terrain
    # contrast, only its own intercept, so it is dropped from the FE sample.
    keep = df.groupby("GEOID")["GEOID"].transform("size") >= 3
    df = df[keep]
    return df.reset_index(drop=True)


def poisson(df, y, xcols, bg_fe=False, maxiter=200):
    """Poisson pseudo-ML with a log-exposure offset, SEs clustered on block group.

    With fixed effects this is `ppmlhdfe`-style: the block-group effects are
    absorbed by an inner weighted-demeaning loop rather than entered as ~500
    dummy columns. Dummies make IRLS diverge here, because the outcome is very
    overdispersed (cell counts run from 0 to ~1800) and a handful of block
    groups have too few cells to identify their own intercept.

    Absorbing also makes the estimand explicit: identification comes only from
    terrain differences *within* a block group. That removes everything constant
    across a block group -- its demographics, its beat, its zoning, its reporting
    regime. It does not make slope as-good-as-random inside one: a steep street
    and a flat street in the same block group can still differ in density,
    building form, frontage, parking rules and foot traffic, and the estimator
    has no way to tell those apart from gradient.

    Convergence and identification diagnostics are attached to the returned
    object (`converged`, `iters`, `n_singleton_groups`, `n_allzero_groups`,
    `n_separated`, `max_abs_score`), because a high-dimensional sparse count
    model can quietly fail to have a maximum likelihood at all.

    `converged` is the coefficient-change tolerance. The first-order condition
    is `max_abs_score`, and it is the one to trust: a fit can run out of
    iterations while sitting on a score of 1e-9, which is converged in every
    sense that matters. The cap is 200 rather than 60 because the headline
    models finish in eight to eleven iterations while a target-count
    denominator can need well over sixty.
    """
    y_v = df[y].astype(float).values
    X = df[xcols].astype(float).values
    off = np.log(df["exposure"].values)
    groups = df["GEOID"].values

    if not bg_fe:
        X1 = sm.add_constant(X, has_constant="add")
        res = sm.GLM(y_v, X1, family=sm.families.Poisson(), offset=off).fit(
            cov_type="cluster", cov_kwds={"groups": groups}, maxiter=200
        )
        return res, ["const"] + list(xcols)

    codes, _ = pd.factorize(groups)
    ng = codes.max() + 1
    beta = np.zeros(X.shape[1])
    alpha = np.zeros(ng)  # absorbed group effects
    converged, iters = False, 0
    for _it in range(maxiter):
        iters = _it + 1
        eta = X @ beta + alpha[codes] + off
        mu = np.exp(np.clip(eta, -30, 30))
        # IRLS working response and weights
        w = mu
        zed = (y_v - mu) / np.maximum(mu, 1e-9) + X @ beta + alpha[codes]
        # absorb group effects by weighted demeaning
        gw = np.bincount(codes, weights=w, minlength=ng)
        gz = np.bincount(codes, weights=w * zed, minlength=ng) / np.maximum(gw, 1e-9)
        Xd = np.empty_like(X)
        for j in range(X.shape[1]):
            gx = np.bincount(codes, weights=w * X[:, j], minlength=ng) / np.maximum(gw, 1e-9)
            Xd[:, j] = X[:, j] - gx[codes]
        zd = zed - gz[codes]
        WX = Xd * w[:, None]
        new_beta = np.linalg.solve(Xd.T @ WX + 1e-10 * np.eye(X.shape[1]), WX.T @ zd)
        alpha = gz - (np.array([
            np.bincount(codes, weights=w * X[:, j], minlength=ng) / np.maximum(gw, 1e-9)
            for j in range(X.shape[1])
        ]).T @ new_beta)
        if np.max(np.abs(new_beta - beta)) < 1e-9:
            beta = new_beta
            converged = True
            break
        beta = new_beta

    # cluster-robust sandwich on the absorbed design
    eta = X @ beta + alpha[codes] + off
    mu = np.exp(np.clip(eta, -30, 30))
    gw = np.bincount(codes, weights=mu, minlength=ng)
    Xd = np.empty_like(X)
    for j in range(X.shape[1]):
        gx = np.bincount(codes, weights=mu * X[:, j], minlength=ng) / np.maximum(gw, 1e-9)
        Xd[:, j] = X[:, j] - gx[codes]
    bread = np.linalg.inv(Xd.T @ (Xd * mu[:, None]) + 1e-10 * np.eye(X.shape[1]))
    score = Xd * (y_v - mu)[:, None]
    # Sum scores within cluster by scatter-add, then meat = S'S. The obvious
    # loop over groups rescans the whole score matrix once per cluster, which is
    # O(groups x rows) -- ~230M operations for a city like Chicago.
    S = np.zeros((ng, X.shape[1]))
    np.add.at(S, codes, score)
    meat = S.T @ S
    cov = bread @ meat @ bread * (ng / max(ng - 1, 1))

    # --- identification diagnostics ------------------------------------------
    # Three ways a block group can contribute nothing, all of which leave the
    # coefficient looking perfectly healthy:
    #   singleton   one cell, so its fixed effect fits that cell exactly
    #   all zero    no incidents anywhere in the group; the absorbed effect runs
    #               to -inf and the group drops out of the likelihood
    #   separated   a zero-count cell whose fitted mean has collapsed to
    #               numerical zero, the signature of a perfect prediction
    gsize = np.bincount(codes, minlength=ng)
    gsum = np.bincount(codes, weights=y_v, minlength=ng)
    n_singleton = int((gsize == 1).sum())
    n_allzero = int((gsum == 0).sum())
    n_sep = int(((y_v == 0) & (mu < 1e-10)).sum())
    max_score = float(np.max(np.abs(Xd.T @ (y_v - mu)))) if len(y_v) else 0.0
    did_converge, n_iters = bool(converged), int(iters)

    class _Res:
        params = beta
        bse = np.sqrt(np.diag(cov))
        nobs = len(y_v)
        n_groups = int(ng)
        n_singleton_groups = int(n_singleton)
        n_allzero_groups = int(n_allzero)
        n_separated = n_sep
        max_abs_score = max_score
        converged = did_converge
        iters = n_iters

    return _Res(), list(xcols)


def coef(res, names, target):
    i = names.index(target)
    b, se = res.params[i], res.bse[i]
    return {
        "beta": b,
        "se": se,
        "irr": np.exp(b),
        "pct": 100 * (np.exp(b) - 1),
        "lo": 100 * (np.exp(b - 1.96 * se) - 1),
        "hi": 100 * (np.exp(b + 1.96 * se) - 1),
        "z": b / se if se > 0 else np.nan,
    }


def attenuation_path(df, y="n_total", radius=500):
    """Naive -> +SES -> +block-group FE, for one radius."""
    t = f"tpi_{radius}_z"
    rows = []
    for label, xs, fe in [
        ("1. terrain only", [t], False),
        ("2. + SES controls", [t] + SES, False),
        ("3. + block-group FE", [t] + SES, True),
    ]:
        res, names = poisson(df, y, xs, bg_fe=fe)
        c = coef(res, names, t)
        c["spec"] = label
        c["n"] = int(res.nobs)
        rows.append(c)
    return pd.DataFrame(rows)[["spec", "n", "pct", "lo", "hi", "z"]]


def radius_sweep(df, y="n_total", metric="tpi"):
    rows = []
    for r in RADII:
        t = f"{metric}_{r}_z"
        res, names = poisson(df, y, [t] + SES, bg_fe=True)
        c = coef(res, names, t)
        c["radius_m"] = r
        rows.append(c)
    return pd.DataFrame(rows)[["radius_m", "pct", "lo", "hi", "z"]]


def loot_ladder(df, radius=500):
    """Effect by loot mass. The falsification test."""
    from crime_classes import MASS_LABEL

    t = f"tpi_{radius}_z"
    rows = []
    specs = [(f"n_MASS_{m}", MASS_LABEL[m], m) for m in sorted(MASS_LABEL)]
    specs += [
        ("n_MVT", "motor vehicle theft (self-propelled)", None),
        ("n_NO_LOOT", "vandalism / arson (nothing to carry)", None),
    ]
    for col, label, mass in specs:
        if col not in df.columns or df[col].sum() < 200:
            continue
        res, names = poisson(df, col, [t] + SES, bg_fe=True)
        c = coef(res, names, t)
        c.update({"outcome": label, "mass": mass, "n_events": int(df[col].sum())})
        rows.append(c)
    return pd.DataFrame(rows)[["outcome", "mass", "n_events", "pct", "lo", "hi", "z"]]


def confound_check(df):
    """How strongly does elevation track money in this city?

    This single number is what the multi-city design is built to exploit.
    """
    out = {}
    for r in RADII:
        out[r] = {
            "corr_income": df[f"tpi_{r}"].corr(df["median_hh_income"]),
            "corr_value": df[f"tpi_{r}"].corr(df["median_home_value"]),
        }
    return pd.DataFrame(out).T


if __name__ == "__main__":
    df = prep()
    print(f"analysis cells: {len(df):,}   block groups: {df.GEOID.nunique():,}")
    print(f"total incidents: {df.n_total.sum():,}\n")

    print("=" * 74)
    print("ELEVATION vs MONEY  (the confound, San Francisco)")
    print("=" * 74)
    print(confound_check(df).round(3).to_string(), "\n")

    print("=" * 74)
    print("ATTENUATION PATH  — % change in property crime per +1 SD of TPI(500m)")
    print("=" * 74)
    print(attenuation_path(df).round(2).to_string(index=False), "\n")

    print("=" * 74)
    print("RADIUS SWEEP  — which spatial scale of 'higher' matters?")
    print("=" * 74)
    print(radius_sweep(df).round(2).to_string(index=False), "\n")

    print("=" * 74)
    print("LOOT-MASS LADDER  — the falsification test")
    print("=" * 74)
    print(loot_ladder(df).round(2).to_string(index=False))
