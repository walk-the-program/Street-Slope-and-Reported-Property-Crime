"""Random-effects synthesis, done properly.

The first version of this project pooled city estimates by inverse variance and
reported I^2 next to the result. That is a fixed-effect pool: it asks what the
common effect is on the assumption that one exists, and its confidence interval
narrows as cities are added even when the cities plainly disagree. Reporting a
high I^2 beside it does not repair the interval -- it only announces that the
model generating the interval is wrong.

What is here instead:

  tau^2      between-city variance, by REML, with DerSimonian-Laird and
             Paule-Mandel reported alongside so the choice is visible
  Hartung-Knapp
             a t-based interval that accounts for having estimated tau^2 from a
             handful of cities. With k=4 this matters enormously; the normal
             interval is far too narrow
  I^2 with an interval
             I^2 is a ratio, not a count, and at k=4 its point estimate is
             close to uninformative on its own
  prediction interval
             the interval a new city's true effect would fall in. This is the
             number a reader actually wants when asking whether the finding
             transports, and it is much wider than the confidence interval
  leave-one-out
             whether any single city is carrying the pool
  meta-regression
             effect against a city-level moderator, which is what replaces
             cutting the sample at a hand-picked threshold

Everything works in log-coefficient space and converts to percent only for
display, because the log scale is where the estimates are symmetric.

References for the estimators: DerSimonian & Laird (1986); Higgins & Thompson
(2002) for I^2 and the typical-variance formula; Viechtbauer (2007) for the
Q-profile interval on tau^2; Hartung & Knapp (2001) and IntHout et al. (2014)
for the small-k interval; Higgins, Thompson & Spiegelhalter (2009) for the
prediction interval.
"""
from __future__ import annotations

import numpy as np
from scipy import optimize, stats


def _clean(y, s):
    y, s = np.asarray(y, float), np.asarray(s, float)
    m = np.isfinite(y) & np.isfinite(s) & (s > 0)
    return y[m], s[m]


# ---------------------------------------------------------------- tau^2 ----
def tau2_dl(y, s):
    """DerSimonian-Laird moment estimator. Closed form, downward biased."""
    w = 1 / s ** 2
    mu = np.sum(w * y) / np.sum(w)
    Q = np.sum(w * (y - mu) ** 2)
    k = len(y)
    denom = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    return max(0.0, (Q - (k - 1)) / denom) if denom > 0 else 0.0


def tau2_pm(y, s):
    """Paule-Mandel: choose tau^2 so the weighted Q equals its expectation."""
    k = len(y)
    if k < 2:
        return 0.0

    def gap(t2):
        w = 1 / (s ** 2 + t2)
        mu = np.sum(w * y) / np.sum(w)
        return np.sum(w * (y - mu) ** 2) - (k - 1)

    if gap(0.0) <= 0:
        return 0.0
    hi = max(1.0, np.var(y) * 10)
    while gap(hi) > 0 and hi < 1e6:
        hi *= 4
    return float(optimize.brentq(gap, 0.0, hi))


def tau2_reml(y, s, tol=1e-12, it=500):
    """REML, by fixed-point iteration. The primary estimator here."""
    k = len(y)
    if k < 2:
        return 0.0
    t2 = tau2_dl(y, s)
    for _ in range(it):
        w = 1 / (s ** 2 + t2)
        mu = np.sum(w * y) / np.sum(w)
        num = np.sum(w ** 2 * ((y - mu) ** 2 - s ** 2)) / np.sum(w ** 2)
        new = max(0.0, num + 1 / np.sum(w))
        if abs(new - t2) < tol:
            return new
        t2 = new
    return t2


def tau2_qprofile(y, s, level=0.95):
    """Q-profile confidence interval for tau^2 (Viechtbauer 2007).

    Inverts the generalised Q statistic against its chi-square reference. The
    lower bound is often exactly zero, which is honest at this k rather than a
    failure.
    """
    k = len(y)
    if k < 3:
        return (0.0, np.nan)
    a = (1 - level) / 2

    def Qgen(t2):
        w = 1 / (s ** 2 + t2)
        mu = np.sum(w * y) / np.sum(w)
        return np.sum(w * (y - mu) ** 2)

    lo_t, hi_t = stats.chi2.ppf(1 - a, k - 1), stats.chi2.ppf(a, k - 1)

    def solve(target):
        if Qgen(0.0) <= target:
            return 0.0
        hi = max(1.0, np.var(y) * 20)
        while Qgen(hi) > target and hi < 1e6:
            hi *= 4
        try:
            return float(optimize.brentq(lambda t: Qgen(t) - target, 0.0, hi))
        except ValueError:
            return np.nan

    return solve(lo_t), solve(hi_t)


def _typical_var(s):
    """Higgins-Thompson 'typical' within-study variance, for I^2."""
    w = 1 / s ** 2
    k = len(s)
    return (k - 1) * np.sum(w) / (np.sum(w) ** 2 - np.sum(w ** 2))


# ------------------------------------------------------------- the pool ----
def random_effects(y, s, level=0.95, hk=True, as_pct=True):
    """Random-effects pool with everything a reader needs to judge it.

    `hk` applies the Hartung-Knapp variance and a t reference. It is the default
    because with four cities the normal-theory interval understates uncertainty
    badly. The unadjusted interval is returned too, so the difference is visible
    rather than buried in a choice.
    """
    y, s = _clean(y, s)
    k = len(y)
    if k == 0:
        return None
    if k == 1:
        pt = y[0]
        half = stats.norm.ppf(1 - (1 - level) / 2) * s[0]
        out = {"k": 1, "mu": pt, "se": s[0], "lo": pt - half, "hi": pt + half,
               "tau2": 0.0, "tau": 0.0, "I2": 0.0, "I2_lo": np.nan,
               "I2_hi": np.nan, "Q": 0.0, "Q_p": np.nan, "pi_lo": np.nan,
               "pi_hi": np.nan, "se_hk": s[0], "method": "single"}
        return _to_pct(out) if as_pct else out

    t2 = tau2_reml(y, s)
    w = 1 / (s ** 2 + t2)
    mu = np.sum(w * y) / np.sum(w)
    se = np.sqrt(1 / np.sum(w))

    # Fixed-effect Q, for the heterogeneity test and for I^2.
    wf = 1 / s ** 2
    muf = np.sum(wf * y) / np.sum(wf)
    Q = np.sum(wf * (y - muf) ** 2)
    Qp = 1 - stats.chi2.cdf(Q, k - 1)

    tv = _typical_var(s)
    I2 = t2 / (t2 + tv) if (t2 + tv) > 0 else 0.0
    t2lo, t2hi = tau2_qprofile(y, s, level)
    I2lo = t2lo / (t2lo + tv) if np.isfinite(t2lo) else np.nan
    I2hi = t2hi / (t2hi + tv) if np.isfinite(t2hi) else np.nan

    # Hartung-Knapp: rescale the variance by the observed weighted dispersion
    # and refer to t with k-1 df.
    q_hk = np.sum(w * (y - mu) ** 2) / (k - 1)
    se_hk = se * np.sqrt(max(q_hk, 1e-12))
    a = (1 - level) / 2
    if hk and k >= 2:
        crit = stats.t.ppf(1 - a, k - 1)
        use_se, method = se_hk, "REML + Hartung-Knapp"
    else:
        crit = stats.norm.ppf(1 - a)
        use_se, method = se, "REML"
    lo, hi = mu - crit * use_se, mu + crit * use_se

    # Prediction interval for a new city (t on k-2 df).
    if k >= 3:
        tcrit = stats.t.ppf(1 - a, k - 2)
        halfp = tcrit * np.sqrt(t2 + se ** 2)
        pi_lo, pi_hi = mu - halfp, mu + halfp
    else:
        pi_lo = pi_hi = np.nan

    out = {"k": k, "mu": mu, "se": se, "se_hk": se_hk, "lo": lo, "hi": hi,
           "lo_normal": mu - stats.norm.ppf(1 - a) * se,
           "hi_normal": mu + stats.norm.ppf(1 - a) * se,
           "tau2": t2, "tau": np.sqrt(t2),
           "tau2_dl": tau2_dl(y, s), "tau2_pm": tau2_pm(y, s),
           "tau2_lo": t2lo, "tau2_hi": t2hi,
           "I2": I2, "I2_lo": I2lo, "I2_hi": I2hi,
           "Q": Q, "Q_p": Qp, "pi_lo": pi_lo, "pi_hi": pi_hi,
           "method": method}
    return _to_pct(out) if as_pct else out


def fixed_effect(y, s, level=0.95, as_pct=True):
    """The old pool, kept so the two can be shown side by side."""
    y, s = _clean(y, s)
    w = 1 / s ** 2
    mu = np.sum(w * y) / np.sum(w)
    se = np.sqrt(1 / np.sum(w))
    z = stats.norm.ppf(1 - (1 - level) / 2)
    out = {"k": len(y), "mu": mu, "se": se, "lo": mu - z * se, "hi": mu + z * se,
           "tau2": 0.0, "method": "fixed effect"}
    return _to_pct(out) if as_pct else out


def _to_pct(d):
    """Attach percent-change versions of the log-scale quantities."""
    def p(v):
        return 100 * (np.exp(v) - 1) if np.isfinite(v) else np.nan
    d = dict(d)
    for src, dst in [("mu", "pct"), ("lo", "pct_lo"), ("hi", "pct_hi"),
                     ("lo_normal", "pct_lo_normal"),
                     ("hi_normal", "pct_hi_normal"),
                     ("pi_lo", "pct_pi_lo"), ("pi_hi", "pct_pi_hi")]:
        if src in d:
            d[dst] = p(d[src])
    return d


def leave_one_out(y, s, labels, level=0.95):
    """Refit the pool without each city in turn."""
    y, s = np.asarray(y, float), np.asarray(s, float)
    rows = []
    for i, lab in enumerate(labels):
        m = np.ones(len(y), bool)
        m[i] = False
        r = random_effects(y[m], s[m], level)
        rows.append({"dropped": lab, "k": r["k"], "pct": r["pct"],
                     "lo": r["pct_lo"], "hi": r["pct_hi"],
                     "tau2": r["tau2"], "I2": r["I2"]})
    return rows


# -------------------------------------------------------- meta-regression ---
def meta_regression(y, s, X, names, level=0.95, knapp=True):
    """Random-effects meta-regression by weighted least squares.

    Residual heterogeneity is estimated by the DerSimonian-Laird moment
    analogue for meta-regression, then the fit is reweighted. With the Knapp-
    Hartung adjustment the reference distribution is t on k-p df, which is the
    only defensible choice when k is single digits.

    `X` should NOT contain an intercept column; one is prepended.
    """
    y = np.asarray(y, float)
    s = np.asarray(s, float)
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in X])
    k, p = X.shape
    names = ["intercept"] + list(names)

    def fit(t2):
        w = 1 / (s ** 2 + t2)
        W = np.diag(w)
        XtWX = X.T @ W @ X
        inv = np.linalg.pinv(XtWX)
        b = inv @ (X.T @ W @ y)
        resid = y - X @ b
        Qe = float(resid @ W @ resid)
        return b, inv, Qe, w

    # Moment estimate of residual between-city variance.
    b0, inv0, Qe0, w0 = fit(0.0)
    P = np.diag(w0) - np.diag(w0) @ X @ inv0 @ X.T @ np.diag(w0)
    tr = float(np.trace(P @ np.diag(s ** 2)))
    t2 = max(0.0, (Qe0 - (k - p)) / (np.trace(P) - 0.0)) if k > p else 0.0
    if np.trace(P) > 0 and k > p:
        t2 = max(0.0, (Qe0 - tr) / float(np.trace(P)))

    b, inv, Qe, w = fit(t2)
    scale = Qe / (k - p) if (knapp and k > p) else 1.0
    cov = inv * max(scale, 1e-12)
    se = np.sqrt(np.diag(cov))
    if knapp and k > p:
        crit = stats.t.ppf(1 - (1 - level) / 2, k - p)
        pvals = 2 * (1 - stats.t.cdf(np.abs(b / se), k - p))
    else:
        crit = stats.norm.ppf(1 - (1 - level) / 2)
        pvals = 2 * (1 - stats.norm.cdf(np.abs(b / se)))

    # How much of the between-city variance the moderators account for.
    t2_null = tau2_reml(y, s)
    r2 = max(0.0, 1 - t2 / t2_null) if t2_null > 0 else np.nan

    rows = []
    for i, nm in enumerate(names):
        rows.append({"term": nm, "beta": b[i], "se": se[i],
                     "lo": b[i] - crit * se[i], "hi": b[i] + crit * se[i],
                     "t": b[i] / se[i], "p": pvals[i]})
    return {"terms": rows, "tau2_resid": t2, "tau2_null": t2_null, "R2": r2,
            "Qe": Qe, "k": k, "p": p,
            "Qe_p": 1 - stats.chi2.cdf(Qe, k - p) if k > p else np.nan,
            "predict": lambda xs: float(np.array([1.0] + list(xs)) @ b)}


# ------------------------------------------------------------ equivalence ---
def tost(diff, se, margin, level=0.90):
    """Two one-sided tests: is `diff` inside +/- `margin`?

    A confidence interval containing zero says the data are consistent with no
    difference. It does not say the difference is small. TOST asks the question
    that was actually meant -- whether a difference large enough to matter can
    be ruled out -- and it can fail even when the ordinary test is null, which
    is exactly the honest outcome when a study is underpowered.

    The conventional pairing is a 90% interval with alpha 0.05 on each side.
    """
    p_lo = 1 - stats.norm.cdf((diff + margin) / se)   # H0: diff <= -margin
    p_hi = stats.norm.cdf((diff - margin) / se)       # H0: diff >= +margin
    p = max(p_lo, p_hi)
    z = stats.norm.ppf(1 - (1 - level) / 2)
    return {"diff": diff, "se": se, "margin": margin,
            "lo": diff - z * se, "hi": diff + z * se,
            "p_lower": p_lo, "p_upper": p_hi, "p": p,
            "equivalent": bool(p < 0.05),
            "level": level}
