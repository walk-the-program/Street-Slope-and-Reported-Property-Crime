"""Spatial dependence: the diagnostics and the sensitivity specification
PREREGISTRATION.md section 6 promises.

The pre-registration commits to two things that the confirmatory run does not
deliver: Moran's I on the residuals of every model, and a spatial specification
reported alongside the cluster-robust primary. This module supplies both. It
does not touch `src/analyze.py` and does not restate any primary result; every
number here is a sensitivity check sitting next to the headline, not a
replacement for it.

The question the sensitivity is built to answer is narrow and specific: block-
group clustering allows arbitrary correlation *inside* a block group and assumes
independence *across* block-group boundaries. Two cells 100 m apart on opposite
sides of a tract line are treated as independent, which they plainly are not.
So: does the slope coefficient survive once that is not assumed, and by how much
do the standard errors widen?

Three specifications, because no single one answers both halves of that question:

  1. Eigenvector spatial filtering (ESF). Moran eigenvectors of the k-nearest-
     neighbour graph enter the same absorbed-FE Poisson as covariates, so
     spatial structure is modelled in the *mean* rather than swept into the
     errors. This addresses "does the point estimate survive".

  2. Conley spatial HAC standard errors. A distance-decay kernel replaces the
     block-group cluster in the sandwich, so correlation is allowed to cross
     block-group boundaries out to a fixed cutoff. This addresses "how much do
     the SEs inflate", and it is the more targeted of the two for that purpose
     (see the note on scale in `moran_eigenvectors`).

  3. A Gaussian spatial-error model on the log crime rate (spreg). Explicitly a
     linear approximation, reported because it is the closest available analogue
     to the CAR error structure that was pre-registered.

**On the BYM promise.** The pre-registration named a conditional autoregressive
(BYM) specification. A BYM random effect needs an MCMC or INLA backend; this
environment has neither PyMC, Stan, nor R-INLA, and adding one is a heavier
dependency than the sensitivity warrants. Eigenvector spatial filtering is the
standard substitute in this situation and is defensible on its own terms -- it
targets the same object (latent spatially structured variation in the mean) by
a basis expansion rather than a hierarchical prior. This is a deviation from
the pre-registration and is recorded as one. The Gaussian spatial-error model
in (3) is included precisely because a CAR error and an SEM error have the same
qualitative form, so it gives a second reading on the same question.
"""
from __future__ import annotations

import glob
import os
import sys
import warnings

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import LinearOperator, eigsh
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(__file__))
from analyze import RADII, SES, coef, poisson  # noqa: E402

warnings.filterwarnings("ignore")

OUT = "outputs"
CELLS = "data/interim/cells_exposure/*.parquet"
SEGMENTS = "data/interim/seg_analysis/*.parquet"

# Section 4 floor, in the slope units the paper actually reports on. The panel
# is the cities with within-city slope SD >= 3 degrees.
MIN_SLOPE_SD = 3.0
MIN_NOLOOT = 3_000

K_NEIGHBOURS = 8
N_EIGENVECTORS = 50
EV_CANDIDATES = 200
CONLEY_CUTOFFS_M = [500, 1000, 2000, 4000]

NICE = {
    "data_sfgov_org": "sfgov",
    "cos-data_seattle_gov": "cos-seattle",
    "data_cincinnati-oh_gov": "cincinnati-oh",
    "data_kcmo_org": "kcmo",
    "data_montgomerycountymd_gov": "montgomerycountymd",
    "data_cityofchicago_org": "chicago",
}


# --- sample construction ---------------------------------------------------
# Mirrors `analyze_national.prep_city` exactly except that exposure comes from
# the building-footprint columns rather than the area-apportioned ones, which is
# what the headline slope table was estimated on (PREREGISTRATION.md section 5
# makes footprint exposure the primary and area-apportioned the robustness
# check). It is duplicated rather than imported because `prep_city` hardcodes
# the area columns and this module is not allowed to modify the primary path.
# `check_reproduces_headline` verifies that the duplication is faithful.

def prep(df: pd.DataFrame, xcol="x", ycol="y") -> pd.DataFrame:
    df = df.copy()
    if "housing_units_bldg" in df.columns:
        df["exposure"] = df["housing_units_bldg"].fillna(0) + df["pop_bldg"].fillna(0)
    else:
        df["exposure"] = df["housing_units_cell"].fillna(0) + df["pop_cell"].fillna(0)
    df = df[df["exposure"] > 5]
    df["log_income"] = np.log(df["median_hh_income"].clip(lower=5000))
    df["log_value"] = np.log(df["median_home_value"].clip(lower=50000))
    df["log_density"] = np.log(df["exposure"])
    df["owner_share"] = df["owner_share"].astype(float)
    df["vacancy_rate"] = df["vacancy_rate"].astype(float)
    for r in RADII:
        c = f"tpi_{r}"
        if c in df.columns:
            s = df[c]
            df[f"{c}_z"] = (s - s.mean()) / s.std() if s.std() > 0 else 0.0

    covered = df.groupby("GEOID")["n_total"].transform("sum") > 0
    df = df[covered]
    df["_rate"] = df["n_total"] / df["exposure"].clip(lower=1)
    df = df[df["_rate"] < 50].drop(columns="_rate")

    need = SES + ["exposure", "GEOID", "n_total", "slope_deg", xcol, ycol]
    df = df.dropna(subset=[c for c in need if c in df.columns])
    keep = df.groupby("GEOID")["GEOID"].transform("size") >= 3
    return df[keep].reset_index(drop=True)


def theft_column(df: pd.DataFrame):
    cols = [c for c in df.columns if c.startswith("n_MASS_")]
    if not cols:
        return None
    df["n_theft"] = df[cols].sum(axis=1)
    return "n_theft"


# --- weights ---------------------------------------------------------------

def knn_weights(df, k=K_NEIGHBOURS, xcol="x", ycol="y"):
    """Row-standardised k-nearest-neighbour weights on projected centroids.

    KNN rather than contiguity or a distance band because the analysis units are
    not a complete lattice -- cells with no exposure were dropped, so a fixed
    distance band leaves islands with no neighbours, which Moran's I is not
    defined on. KNN guarantees every unit has exactly k neighbours. At 100 m
    cells, k=8 is the immediate ring, which is the scale at which residual
    dependence would bite hardest.
    """
    from libpysal.weights import KNN

    coords = df[[xcol, ycol]].to_numpy(float)
    w = KNN.from_array(coords, k=k)
    w.transform = "r"
    return w


def _sparse_w(w) -> sp.csr_matrix:
    return w.sparse.tocsr().astype(float)


def cross_group_weights(df, k=K_NEIGHBOURS, group="GEOID", xcol="x", ycol="y"):
    """KNN weights with all within-block-group links deleted.

    This is the diagnostic that actually bears on the primary specification, and
    the plain Moran's I is close to uninformative without it.

    Two reasons. First, mechanically: an absorbed-FE Poisson satisfies
    sum_g (y_i - mu_i) = 0 exactly in every block group, so residuals inside a
    group are forced to sum to zero and neighbours inside a group are pushed
    into negative correlation by construction, whatever the data do. Most KNN
    links at 100 m sit inside one block group, so the plain statistic is
    dominated by that artifact. Second, substantively: cluster-robust SEs
    already permit arbitrary correlation within a block group. They are valid
    if and only if residuals are uncorrelated *across* block-group boundaries.
    Moran's I computed on cross-boundary links only is therefore the exact test
    of the assumption the primary specification is making.

    Deleting links creates islands, and deleting islands creates more, so the
    pruning iterates to a fixed point. Returns the weights and the row indices
    they are defined on.
    """
    from libpysal.weights import KNN, WSP

    coords = df[[xcol, ycol]].to_numpy(float)
    A = KNN.from_array(coords, k=k).sparse.tocoo()
    g = pd.factorize(df[group].to_numpy())[0]
    m = g[A.row] != g[A.col]
    A = sp.coo_matrix((np.ones(m.sum()), (A.row[m], A.col[m])),
                      shape=A.shape).tocsr()

    keep = np.arange(A.shape[0])
    for _ in range(20):
        deg = np.asarray(A.sum(axis=1)).ravel()
        alive = deg > 0
        if alive.all():
            break
        keep = keep[alive]
        A = A[alive][:, alive]

    w = WSP(sp.csr_matrix(A)).to_W(silence_warnings=True)
    w.transform = "r"
    return w, keep


# --- residuals from the absorbed-FE fit ------------------------------------

def absorbed_mu(df, beta, xcols, y, group="GEOID", offset="exposure"):
    """Fitted counts from an absorbed-FE Poisson fit, given only the slopes.

    `analyze.poisson` returns coefficients but not the absorbed group effects or
    the fitted values, and this module may not modify it. It does not need to:
    for Poisson with fixed effects the group intercept has an exact closed form
    at the optimum. The score for group g is sum_g (y_i - mu_i) = 0, so

        alpha_g = log( sum_g y_i / sum_g exp(x_i'beta + log E_i) )

    which recovers the same alpha the IRLS loop converged to, from beta alone.
    """
    y_v = df[y].astype(float).to_numpy()
    X = df[xcols].astype(float).to_numpy()
    off = np.log(df[offset].to_numpy(float))
    codes, _ = pd.factorize(df[group].to_numpy())
    ng = codes.max() + 1

    base = np.exp(np.clip(X @ np.asarray(beta, float) + off, -30, 30))
    num = np.bincount(codes, weights=y_v, minlength=ng)
    den = np.bincount(codes, weights=base, minlength=ng)
    alpha = np.log(np.maximum(num, 1e-12) / np.maximum(den, 1e-12))
    return base * np.exp(alpha[codes]), y_v


def pearson_residuals(df, beta, xcols, y, **kw):
    """(y - mu)/sqrt(mu). The variance-stabilised residual for a count model.

    Raw residuals would make Moran's I a map of where crime is common rather
    than a map of where the model is wrong, because the residual variance under
    Poisson scales with the fitted mean.
    """
    mu, y_v = absorbed_mu(df, beta, xcols, y, **kw)
    return (y_v - mu) / np.sqrt(np.maximum(mu, 1e-9))


def _moran(e, w, permutations):
    from esda.moran import Moran

    mi = Moran(np.asarray(e, float), w, permutations=permutations)
    return {"morans_I": float(mi.I), "expected_I": float(mi.EI),
            "z_norm": float(mi.z_norm), "p_norm": float(mi.p_norm),
            "p_sim": float(mi.p_sim) if permutations else np.nan}


def morans_i_residuals(df, beta, xcols, y, w, permutations=999,
                       w_cross=None, keep_cross=None, **kw):
    """Moran's I on Pearson residuals. Returns I, E[I], z and p.

    Reports both the normal-approximation p and a permutation p. At these sample
    sizes they agree; the permutation version is carried because the normal
    approximation for Moran's I assumes the underlying variate is roughly
    symmetric, and Pearson residuals from a count model with many zeros are not.

    When cross-block-group weights are supplied, the same statistic is also
    reported on cross-boundary links only. That version is the one to read --
    see `cross_group_weights` for why the all-links version is contaminated by
    the fixed-effect constraint.
    """
    e = pearson_residuals(df, beta, xcols, y, **kw)
    out = {**_moran(e, w, permutations), "n_units": int(len(e))}
    if w_cross is not None:
        c = _moran(e[keep_cross], w_cross, permutations)
        out.update({f"cross_bg_{k}": v for k, v in c.items()})
        out["cross_bg_n_units"] = int(len(keep_cross))
    return out


# --- Moran eigenvectors ----------------------------------------------------

def moran_eigenvectors(w, n_candidates=EV_CANDIDATES):
    """Leading eigenvectors of the doubly-centred connectivity MCM.

    M = I - 11'/n, C = (W + W')/2. The eigenvectors of MCM are mutually
    orthogonal synthetic map patterns whose eigenvalues are proportional to
    their Moran's I, so the leading ones are the smoothest large-scale patterns
    the graph can express. Adding them as covariates removes spatially
    structured variation from the residual, which is the same object a CAR
    random effect is meant to soak up.

    C is symmetrised because row-standardised KNN is not symmetric and the
    eigenproblem needs it to be; this is the usual construction.

    The decomposition is done with a sparse iterative solver against a
    LinearOperator, never a dense n x n matrix. A city like Cincinnati has
    ~25,000 units, and its dense MCM would be ~5 GB.

    Scale caveat, and it matters for reading the results: leading eigenvectors
    describe *city-scale* gradients. Block-group fixed effects already absorb
    variation at roughly that scale, so a filter of this size cannot remove
    residual dependence between adjacent cells inside one block group -- doing
    that would take thousands of eigenvectors. ESF here is therefore a test of
    whether the slope coefficient survives conditioning on broad spatial
    structure, not a complete whitening. The Conley SEs below are what handle
    the fine-scale part.
    """
    C = _sparse_w(w)
    C = ((C + C.T) * 0.5).tocsr()
    n = C.shape[0]

    def mv(v):
        v = np.asarray(v).ravel()
        v = v - v.mean()
        v = C @ v
        return v - v.mean()

    op = LinearOperator((n, n), matvec=mv, dtype=float)
    k = int(min(n_candidates, n - 2))
    vals, vecs = eigsh(op, k=k, which="LA")
    order = np.argsort(vals)[::-1]
    return vals[order], vecs[:, order]


def select_eigenvectors(vals, vecs, resid, codes, n_ev=N_EIGENVECTORS, min_ratio=0.25):
    """Pick the eigenvectors that actually explain this model's residual.

    Two filters. First Griffith's conventional candidate rule, lambda >=
    0.25 * lambda_max, which keeps only patterns carrying substantial positive
    autocorrelation. Then rank the survivors by their correlation with the
    residual *after within-block-group demeaning*, because anything the fixed
    effects already absorb cannot help and would only add collinear columns to
    an absorbed design.
    """
    keep = np.flatnonzero(vals >= min_ratio * vals.max())
    if len(keep) == 0:
        return np.zeros((len(resid), 0))
    V = vecs[:, keep]

    ng = codes.max() + 1
    cnt = np.bincount(codes, minlength=ng).astype(float)

    def demean(a):
        m = np.vstack([np.bincount(codes, weights=a[:, j], minlength=ng) / cnt
                       for j in range(a.shape[1])]).T
        return a - m[codes]

    Vd = demean(V)
    rd = demean(resid.reshape(-1, 1)).ravel()
    sd = Vd.std(axis=0)
    ok = sd > 1e-10
    score = np.zeros(V.shape[1])
    score[ok] = np.abs((Vd[:, ok] * rd[:, None]).mean(axis=0) / (sd[ok] * rd.std() + 1e-30))
    pick = np.argsort(score)[::-1][: min(n_ev, V.shape[1])]
    return V[:, np.sort(pick)]


# --- sandwich variants ------------------------------------------------------

def _bread_and_score(df, beta, xcols, y, group="GEOID", offset="exposure"):
    """Bread and per-unit scores of the absorbed design.

    Reproduces the weighted demeaning `analyze.poisson` applies before its own
    sandwich, so every variance estimate below differs from the primary only in
    the meat -- which is the whole point of the comparison.
    """
    y_v = df[y].astype(float).to_numpy()
    X = df[xcols].astype(float).to_numpy()
    codes, _ = pd.factorize(df[group].to_numpy())
    ng = codes.max() + 1
    mu, _ = absorbed_mu(df, beta, xcols, y, group=group, offset=offset)

    gw = np.bincount(codes, weights=mu, minlength=ng)
    Xd = np.empty_like(X)
    for j in range(X.shape[1]):
        gx = np.bincount(codes, weights=mu * X[:, j], minlength=ng) / np.maximum(gw, 1e-9)
        Xd[:, j] = X[:, j] - gx[codes]

    bread = np.linalg.inv(Xd.T @ (Xd * mu[:, None]) + 1e-10 * np.eye(X.shape[1]))
    return bread, Xd * (y_v - mu)[:, None], Xd, mu


def naive_se(df, beta, xcols, y, **kw):
    """Independence SEs: the model information matrix, no robustness at all.

    Reported only as the denominator that makes the other numbers legible. The
    ratio of any robust SE to this one is how much dependence the data actually
    contain, and without it a reader cannot tell whether clustering is doing a
    lot of work or none.
    """
    _, _, Xd, mu = _bread_and_score(df, beta, xcols, y, **kw)
    return np.sqrt(np.diag(np.linalg.inv(Xd.T @ (Xd * mu[:, None]))))


def conley_se(df, beta, xcols, y, cutoff_m, xcol="x", ycol="y",
              group="GEOID", offset="exposure"):
    """Spatial HAC standard errors for the absorbed-FE Poisson.

    Same sandwich as the cluster-robust version, with the cluster indicator
    replaced by a Bartlett kernel in distance: meat = S' K S, where S holds the
    within-group-demeaned scores and K_ij = max(0, 1 - d_ij/cutoff). Cluster-
    robust SEs assume independence the moment a block-group line is crossed;
    this assumes it only beyond `cutoff_m`, which is the weaker and more
    honest assumption for a 100 m grid.

    Read the cutoff against the median block-group diagonal reported in the
    diagnostics. Where a block group is physically larger than the cutoff --
    Cincinnati's median diagonal is ~1.3 km -- clustering is already the more
    permissive assumption of the two, and a Conley SE below the cluster-robust
    one means exactly that, not that dependence is absent.

    Conley SEs grow mechanically with the cutoff and stop being credible once
    it is an appreciable fraction of the study area, because too few
    effectively independent blocks remain. Cutoffs beyond ~2 km in cities this
    size are reported for shape, not for inference.

    Kernel pairs come from a KD-tree radius query, so the kernel is sparse and
    the meat is one sparse product. Materialising K densely at 25,000 units
    would be 5 GB.

    Not made positive-definite by construction -- a Bartlett kernel on an
    irregular point set can still yield a slightly indefinite meat. Negative
    variances are returned as NaN rather than silently square-rooted.
    """
    bread, S, _, _ = _bread_and_score(df, beta, xcols, y, group=group, offset=offset)

    coords = df[[xcol, ycol]].to_numpy(float)
    tree = cKDTree(coords)
    D = tree.sparse_distance_matrix(tree, cutoff_m, output_type="coo_matrix")
    kern = np.maximum(0.0, 1.0 - D.data / cutoff_m)
    K = sp.coo_matrix((kern, (D.row, D.col)), shape=(len(coords),) * 2).tocsr()
    K.setdiag(1.0)  # self-pairs have distance 0 and are dropped by the query

    cov = bread @ (S.T @ (K @ S)) @ bread
    v = np.diag(cov)
    return np.where(v > 0, np.sqrt(np.abs(v)), np.nan)


# --- spatial error model (Gaussian, linear approximation) -------------------

def gaussian_sem(df, y, xcols, w, group="GEOID", offset="exposure"):
    """Spatial-error model on the log crime rate, block-group effects demeaned out.

    Reported as a linear approximation and nothing more. The outcome is a count
    and the primary estimator is Poisson; this fits Gaussian OLS to
    log((y + 0.5)/exposure), which is a different estimand -- it weights a cell
    with 3 incidents the same as one with 300, and the +0.5 offset is arbitrary.
    It is here because an SEM error, u = lambda*Wu + e, has the same qualitative
    form as the CAR error the pre-registration named, so it is the closest
    linear reading available of "what happens when the dependence is in the
    error structure rather than the cluster".

    spreg has no fixed-effect absorption for cross-sections, so the block-group
    effects are removed by Frisch-Waugh demeaning before the model is fitted.
    That is exact for the coefficients under OLS; under the spatial error model
    it is an approximation, because demeaning does not commute with the spatial
    filter. Noted rather than hidden.
    """
    from spreg import GM_Error_Het

    codes, _ = pd.factorize(df[group].to_numpy())
    ng = codes.max() + 1
    cnt = np.bincount(codes, minlength=ng).astype(float)

    rate = np.log((df[y].astype(float).to_numpy() + 0.5) / df[offset].to_numpy(float))
    X = df[xcols].astype(float).to_numpy()

    def demean(a):
        m = np.vstack([np.bincount(codes, weights=a[:, j], minlength=ng) / cnt
                       for j in range(a.shape[1])]).T
        return a - m[codes]

    yd = demean(rate.reshape(-1, 1))
    Xd = demean(X)
    keep = Xd.std(axis=0) > 1e-12
    m = GM_Error_Het(yd, Xd[:, keep], w=w, name_x=[c for c, k in zip(xcols, keep) if k])
    names = ["CONSTANT"] + [c for c, k in zip(xcols, keep) if k]
    return m, names


# --- model runner ----------------------------------------------------------

def compare_one(df, y, target, w, label, city, unit, permutations=999,
                n_ev=N_EIGENVECTORS, ev_cache=None, do_sem=True,
                xcol="x", ycol="y", cross=None):
    """Cluster-robust vs spatial, for one outcome in one city.

    Returns (diagnostic row, list of model rows).
    """
    xcols = [target] + [c for c in SES if c in df.columns]
    res, names = poisson(df, y, xcols, bg_fe=True)
    base = coef(res, names, target)
    w_cross, keep_cross = cross if cross else (None, None)

    # The physical size of a cluster decides how to read a Conley cutoff
    # against it, so it travels with the diagnostics rather than being left for
    # the reader to guess.
    g = df.groupby("GEOID")
    bg_diag = float(np.median(np.hypot(g[xcol].max() - g[xcol].min(),
                                       g[ycol].max() - g[ycol].min())))

    diag = {"city": city, "unit": unit, "model": label, "outcome": y,
            "target": target, "n_events": int(df[y].sum()),
            "n_block_groups": int(df["GEOID"].nunique()),
            "median_bg_diagonal_m": bg_diag,
            **morans_i_residuals(df, res.params, xcols, y, w,
                                 permutations=permutations,
                                 w_cross=w_cross, keep_cross=keep_cross)}

    nse = naive_se(df, res.params, xcols, y)[0]
    rows = [
        {"city": city, "unit": unit, "model": label, "outcome": y,
         "target": target, "spec": "0. naive (independence)",
         "beta": base["beta"], "se": nse,
         "z": base["beta"] / nse if nse > 0 else np.nan,
         "pct": base["pct"],
         "lo": 100 * (np.exp(base["beta"] - 1.96 * nse) - 1),
         "hi": 100 * (np.exp(base["beta"] + 1.96 * nse) - 1),
         "n": int(len(df)), "se_ratio_vs_naive": 1.0,
         "note": "reference denominator only; assumes independence, not to be quoted"},
        {"city": city, "unit": unit, "model": label, "outcome": y,
         "target": target, "spec": "a. cluster-robust (primary)",
         "beta": base["beta"], "se": base["se"], "z": base["z"],
         "pct": base["pct"], "lo": base["lo"], "hi": base["hi"],
         "n": int(len(df)), "se_ratio_vs_naive": base["se"] / nse,
         "note": "SEs clustered on block group"},
    ]

    # (a) Conley spatial HAC on the same point estimate.
    for cut in CONLEY_CUTOFFS_M:
        try:
            se = conley_se(df, res.params, xcols, y, cut, xcol=xcol, ycol=ycol)[0]
        except Exception as exc:
            rows.append({"city": city, "unit": unit, "model": label, "outcome": y,
                         "target": target, "spec": f"b. Conley HAC {cut} m",
                         "beta": base["beta"], "se": np.nan, "note":
                         f"failed: {type(exc).__name__}"})
            continue
        z = base["beta"] / se if se and np.isfinite(se) and se > 0 else np.nan
        rows.append({"city": city, "unit": unit, "model": label, "outcome": y,
                     "target": target, "spec": f"b. Conley HAC {cut} m",
                     "beta": base["beta"], "se": se, "z": z,
                     "pct": base["pct"],
                     "lo": 100 * (np.exp(base["beta"] - 1.96 * se) - 1),
                     "hi": 100 * (np.exp(base["beta"] + 1.96 * se) - 1),
                     "n": int(len(df)),
                     "se_ratio_vs_cluster": se / base["se"],
                     "se_ratio_vs_naive": se / nse,
                     "note": "Bartlett kernel in distance; point estimate unchanged"})

    # (b) Eigenvector spatial filter, refit.
    esf_diag = None
    try:
        vals, vecs = ev_cache if ev_cache is not None else moran_eigenvectors(w)
        codes, _ = pd.factorize(df["GEOID"].to_numpy())
        resid = pearson_residuals(df, res.params, xcols, y)
        V = select_eigenvectors(vals, vecs, resid, codes, n_ev=n_ev)
        d2 = df.copy()
        evc = []
        for j in range(V.shape[1]):
            c = f"_ev{j}"
            d2[c] = V[:, j]
            evc.append(c)
        x2 = xcols + evc
        r2, n2 = poisson(d2, y, x2, bg_fe=True)
        c2 = coef(r2, n2, target)
        esf_diag = morans_i_residuals(d2, r2.params, x2, y, w,
                                      permutations=permutations,
                                      w_cross=w_cross, keep_cross=keep_cross)
        rows.append({"city": city, "unit": unit, "model": label, "outcome": y,
                     "target": target,
                     "spec": f"c. eigenvector spatial filter ({V.shape[1]} EVs)",
                     "beta": c2["beta"], "se": c2["se"], "z": c2["z"],
                     "pct": c2["pct"], "lo": c2["lo"], "hi": c2["hi"],
                     "n": int(len(d2)),
                     "se_ratio_vs_cluster": c2["se"] / base["se"],
                     "se_ratio_vs_naive": c2["se"] / nse,
                     "beta_shift_vs_cluster": c2["beta"] - base["beta"],
                     "pct_shift_vs_cluster": c2["pct"] - base["pct"],
                     "note": "Moran eigenvectors as covariates; SEs still clustered"})
    except Exception as exc:
        rows.append({"city": city, "unit": unit, "model": label, "outcome": y,
                     "target": target, "spec": "c. eigenvector spatial filter",
                     "note": f"failed: {type(exc).__name__}: {exc}"})

    # (c) Gaussian spatial error model, explicitly an approximation.
    if do_sem:
        try:
            m, nm = gaussian_sem(df, y, xcols, w)
            i = nm.index(target)
            b, se = float(m.betas[i][0]), float(np.sqrt(m.vm[i, i]))
            rows.append({"city": city, "unit": unit, "model": label, "outcome": y,
                         "target": target, "spec": "d. Gaussian SEM on log rate",
                         "beta": b, "se": se, "z": b / se if se > 0 else np.nan,
                         "pct": 100 * (np.exp(b) - 1),
                         "lo": 100 * (np.exp(b - 1.96 * se) - 1),
                         "hi": 100 * (np.exp(b + 1.96 * se) - 1),
                         "n": int(len(df)),
                         "lambda_spatial": float(m.betas[-1][0]),
                         "note": "LINEAR APPROXIMATION, not comparable to Poisson beta"})
        except Exception as exc:
            rows.append({"city": city, "unit": unit, "model": label, "outcome": y,
                         "target": target, "spec": "d. Gaussian SEM on log rate",
                         "note": f"failed: {type(exc).__name__}"})

    if esf_diag:
        diag.update({f"esf_{k}": v for k, v in esf_diag.items()
                     if k in ("morans_I", "z_norm", "p_norm",
                              "cross_bg_morans_I", "cross_bg_z_norm",
                              "cross_bg_p_norm")})
    return diag, rows


def check_reproduces_headline(city, df, target="slope_deg"):
    """Confirm this module's sample is the headline sample before trusting it.

    The prep above is a copy of the primary path, so it has to be shown to give
    the primary answer. Compared against outputs/slope_per_degree.csv.
    """
    path = f"{OUT}/slope_per_degree.csv"
    if not os.path.exists(path):
        return None
    ref = pd.read_csv(path)
    row = ref[ref.city == city]
    if row.empty:
        return None
    res, names = poisson(df, "n_total", [target] + SES, bg_fe=True)
    b = coef(res, names, target)["beta"]
    return {"city": city, "stored_beta": float(row.beta.iloc[0]),
            "recomputed_beta": float(b),
            "abs_diff": abs(float(row.beta.iloc[0]) - b)}


def main(permutations=999):
    os.makedirs(OUT, exist_ok=True)
    diags, models, checks = [], [], []

    for path in sorted(glob.glob(CELLS)):
        name = NICE.get(os.path.basename(path).replace(".parquet", ""),
                        os.path.basename(path).replace(".parquet", ""))
        df = prep(pd.read_parquet(path))
        sd = df["slope_deg"].std()
        if sd < MIN_SLOPE_SD:
            print(f"  [skip] {name:22s} slope SD {sd:.2f} deg < {MIN_SLOPE_SD}")
            continue
        print(f"\n=== {name}  (cells, n={len(df):,}, slope SD {sd:.2f} deg) ===")

        chk = check_reproduces_headline(name, df)
        if chk:
            checks.append(chk)
            print(f"  headline check: stored {chk['stored_beta']:+.6f}  "
                  f"recomputed {chk['recomputed_beta']:+.6f}  "
                  f"diff {chk['abs_diff']:.2e}")

        w = knn_weights(df)
        cross = cross_group_weights(df)
        print(f"  cross-block-group links retained on {len(cross[1]):,}/{len(df):,} cells")
        print(f"  building {EV_CANDIDATES} Moran eigenvectors ...", flush=True)
        ev = moran_eigenvectors(w)

        specs = [("pooled per-degree slope", "n_total", "slope_deg"),
                 ("relative height (TPI 500 m)", "n_total", "tpi_500_z")]
        tc = theft_column(df)
        if tc and df[tc].sum() >= 500:
            specs.append(("theft (all loot classes)", tc, "slope_deg"))
        if "n_NO_LOOT" in df.columns and df.n_NO_LOOT.sum() >= MIN_NOLOOT:
            specs.append(("no-loot (vandalism/arson)", "n_NO_LOOT", "slope_deg"))
        else:
            n = int(df.n_NO_LOOT.sum()) if "n_NO_LOOT" in df.columns else 0
            print(f"  [skip no-loot] {n:,} incidents < {MIN_NOLOOT:,}")

        for label, y, target in specs:
            if target not in df.columns:
                continue
            d, r = compare_one(df, y, target, w, label, name, "cell",
                               permutations=permutations, ev_cache=ev,
                               cross=cross)
            diags.append(d)
            models.extend(r)
            print(f"  {label:30s} I={d['morans_I']:+.4f} z={d['z_norm']:+8.1f}"
                  f"   cross-BG I={d['cross_bg_morans_I']:+.4f} "
                  f"z={d['cross_bg_z_norm']:+7.1f}")

    # San Francisco street segments. Different unit of analysis, same question;
    # PAPER.md reports that the unit changes the answer for relative height but
    # not for slope, so the spatial diagnostic is worth having on both.
    #
    # The directory accumulates enriched re-cuts of the same segment table
    # (`sfgov_targets` adds target-density columns to a byte-identical copy of
    # `sfgov`). Nothing here reads those extra columns, so they would enter the
    # output as a second identical city. Tables are deduplicated on a signature
    # of what this module actually models.
    seen = set()
    for path in sorted(glob.glob(SEGMENTS)):
        name = os.path.basename(path).replace(".parquet", "")
        raw = pd.read_parquet(path)
        df = prep(raw, xcol="mid_x", ycol="mid_y")
        if "slope_deg" not in df.columns or len(df) < 500:
            continue
        sig = (len(df), float(df.n_total.sum()), round(float(df.slope_deg.sum()), 6))
        if sig in seen:
            print(f"  [skip] {name:22s} duplicates an already-processed segment table")
            continue
        seen.add(sig)
        print(f"\n=== {name}  (segments, n={len(df):,}) ===")
        w = knn_weights(df, xcol="mid_x", ycol="mid_y")
        cross = cross_group_weights(df, xcol="mid_x", ycol="mid_y")
        ev = moran_eigenvectors(w)
        specs = [("pooled per-degree slope", "n_total", "slope_deg")]
        tc = theft_column(df)
        if tc and df[tc].sum() >= 500:
            specs.append(("theft (all loot classes)", tc, "slope_deg"))
        if "n_NO_LOOT" in df.columns and df.n_NO_LOOT.sum() >= MIN_NOLOOT:
            specs.append(("no-loot (vandalism/arson)", "n_NO_LOOT", "slope_deg"))
        for label, y, target in specs:
            d, r = compare_one(df, y, target, w, label, name, "segment",
                               permutations=permutations, ev_cache=ev,
                               xcol="mid_x", ycol="mid_y", cross=cross)
            diags.append(d)
            models.extend(r)
            print(f"  {label:30s} I={d['morans_I']:+.4f} z={d['z_norm']:+8.1f}"
                  f"   cross-BG I={d['cross_bg_morans_I']:+.4f} "
                  f"z={d['cross_bg_z_norm']:+7.1f}")

    pd.DataFrame(diags).to_csv(f"{OUT}/spatial_diagnostics.csv", index=False)
    pd.DataFrame(models).to_csv(f"{OUT}/spatial_models.csv", index=False)
    if checks:
        print("\nheadline reproduction check (max abs diff): "
              f"{max(c['abs_diff'] for c in checks):.2e}")
    print(f"\nwrote {OUT}/spatial_diagnostics.csv  ({len(diags)} models)")
    print(f"wrote {OUT}/spatial_models.csv  ({len(models)} rows)")
    return diags, models


if __name__ == "__main__":
    main(permutations=int(sys.argv[1]) if len(sys.argv) > 1 else 999)
