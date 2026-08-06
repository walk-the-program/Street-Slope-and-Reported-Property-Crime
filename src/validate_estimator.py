"""Re-estimate the headline numbers with somebody else's code.

The Poisson estimator in `analyze.py` is written from scratch: an absorbing
inner loop that demeans the design by fixed-effect group each iteration, plus a
hand-rolled cluster-robust sandwich. It converges, it reports its own
diagnostics, and it reproduces byte-for-byte. None of that rules out its being
consistently wrong, because every one of those checks runs through the same code.

So this fits the same models a completely different way: `statsmodels`' GLM with
the block-group fixed effects entered as explicit dummy columns and its own
cluster-robust covariance. Different algorithm, different sandwich, different
authors. If the two agree to several decimals, the absorbing loop is doing what
it claims.

Dummies are why this is not the primary estimator: the design matrix is dense
and grows with the number of block groups, so Chicago at 2,386 groups needs
about 1.2 GB where the absorbing version needs none of it. Cities are attempted
in size order and skipped when the matrix would be unreasonable, which still
leaves all four higher-gradient cities -- the ones carrying every mechanism test
in the paper.
"""
from __future__ import annotations

import glob
import os
import sys
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings("ignore")

from analyze import SES, coef, poisson
from regen_all import CELLS, prep_cells, slug
import vizstyle as vs

OUT = "outputs"
MAX_CELLS_X_GROUPS = 20_000_000     # ~160 MB of float64 design matrix


def identifying_sample(d, y):
    """Block groups that actually contribute to the likelihood.

    A group whose outcome is zero everywhere drives its own fixed effect to
    minus infinity. The absorbing estimator simply drops out of the likelihood
    there and carries on; explicit dummies send the IRLS weights to zero and
    statsmodels refuses to continue, which is the divergence the absorbing loop
    was written to avoid in the first place. Restricting both estimators to the
    same identifying sample makes the comparison like-for-like.
    """
    keep = d.groupby("GEOID")[y].transform("sum") > 0
    dd = d[keep].copy()
    dd = dd[dd.groupby("GEOID").GEOID.transform("size") >= 3]
    return dd.reset_index(drop=True)


def dummy_fit(d, y, xvar="slope_deg_raw"):
    """statsmodels GLM, fixed effects as explicit dummies, clustered SEs."""
    codes, uniq = pd.factorize(d.GEOID.values)
    ng = len(uniq)
    if len(d) * ng > MAX_CELLS_X_GROUPS:
        return None, ng
    D = np.zeros((len(d), ng), dtype=np.float64)
    D[np.arange(len(d)), codes] = 1.0
    X = np.column_stack([d[[xvar] + SES].astype(float).values, D[:, 1:]])
    X = sm.add_constant(X, has_constant="add")
    try:
        res = sm.GLM(d[y].astype(float).values, X, family=sm.families.Poisson(),
                     offset=np.log(d["exposure"].values)).fit(
            cov_type="cluster", cov_kwds={"groups": d.GEOID.values}, maxiter=300)
    except Exception as e:
        # Sparse outcomes plus hundreds of dummies still send the IRLS weights
        # to zero in some cities even after the all-zero groups are removed.
        # That failure is the point of the absorbing estimator, so it is
        # recorded rather than worked around.
        return {"failed": str(e).split(".")[0][:60]}, ng
    # column 0 is the constant, column 1 is the treatment
    return {"beta": float(res.params[1]), "se": float(res.bse[1]),
            "pct": 100 * (np.exp(res.params[1]) - 1), "failed": None}, ng


def run():
    rows, failed = [], []
    paths = sorted(glob.glob(CELLS), key=lambda p: os.path.getsize(p))
    for path in paths:
        s = slug(path)
        d = prep_cells(path)
        if len(d) < 500:
            continue
        for label, ycol in (("all property crime", "n_total"),
                            ("theft", "n_theft"),
                            ("no-loot", "n_NO_LOOT")):
            if ycol not in d.columns or d[ycol].sum() < 3000:
                continue
            dd = identifying_sample(d, ycol)
            if len(dd) < 500:
                continue
            mine, names = poisson(dd, ycol, ["slope_deg_raw"] + SES, bg_fe=True)
            a = coef(mine, names, "slope_deg_raw")
            theirs, ng = dummy_fit(dd, ycol)
            if theirs is None:
                print(f"{vs.city(s):22s} {label:20s} skipped "
                      f"({len(dd):,} cells x {ng:,} groups too large)", flush=True)
                continue
            if theirs.get("failed"):
                print(f"{vs.city(s):22s} {label:20s} dummy fit did not converge "
                      f"-- {theirs['failed']}", flush=True)
                failed.append({"city": vs.city(s), "outcome": label,
                               "n": len(dd), "block_groups": ng,
                               "reason": theirs["failed"]})
                continue
            rows.append({
                "city": vs.city(s), "slug": s, "outcome": label,
                "n": len(dd), "block_groups": ng,
                "beta_absorbed": a["beta"], "beta_dummies": theirs["beta"],
                "beta_diff": theirs["beta"] - a["beta"],
                "se_absorbed": a["se"], "se_dummies": theirs["se"],
                "se_ratio": theirs["se"] / a["se"],
                "pct_absorbed": a["pct"], "pct_dummies": theirs["pct"],
                "pct_diff": theirs["pct"] - a["pct"],
            })
            r = rows[-1]
            print(f"{vs.city(s):22s} {label:20s} "
                  f"beta {r['beta_absorbed']:+.6f} vs {r['beta_dummies']:+.6f}  "
                  f"diff {r['beta_diff']:+.2e}   "
                  f"se {r['se_absorbed']:.5f} vs {r['se_dummies']:.5f}  "
                  f"ratio {r['se_ratio']:.4f}", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/estimator_validation.csv", index=False)
    if failed:
        pd.DataFrame(failed).to_csv(f"{OUT}/estimator_validation_failed.csv",
                                    index=False)
        print(f"\ndummy-variable fits that would not converge: {len(failed)}")
    print("\n" + "=" * 74)
    print(f"models cross-checked: {len(df)}")
    print(f"largest absolute coefficient difference: {df.beta_diff.abs().max():.3e}")
    print(f"largest percentage-point difference:     {df.pct_diff.abs().max():.3e}")
    print(f"standard error ratio range: {df.se_ratio.min():.4f} to "
          f"{df.se_ratio.max():.4f}")
    print("wrote estimator_validation.csv")


if __name__ == "__main__":
    run()
