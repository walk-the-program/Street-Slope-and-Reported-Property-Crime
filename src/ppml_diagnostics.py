"""What the estimator actually did, city by city.

A Poisson model with several hundred absorbed fixed effects and a sparse count
outcome can fail in ways that leave the printed coefficient looking entirely
ordinary. The maximum likelihood may not exist; whole fixed-effect groups may
carry no identifying variation and silently drop out; the solver may stop on
its iteration cap rather than on its tolerance. None of that was reported.

This records, per city: the estimation sample and how it was reduced from the
raw cell table, the number of block groups, how many were singletons, how many
contained no incidents at all, how many observations show the numerical
signature of separation, whether the inner loop converged and in how many
iterations, and the largest remaining score.
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

from analyze import SES, poisson
from regen_all import CELLS, prep_cells, slug
import vizstyle as vs

OUT = "outputs"


def run():
    rows = []
    for path in sorted(glob.glob(CELLS)):
        s = slug(path)
        raw = pd.read_parquet(path)
        d = prep_cells(path)
        if len(d) < 500:
            continue
        res, names = poisson(d, "n_total", ["slope_deg_raw"] + SES, bg_fe=True)
        rows.append({
            "city": s,
            "cells_raw": len(raw),
            "cells_estimated": int(res.nobs),
            "dropped_pct": 100 * (1 - res.nobs / len(raw)),
            "block_groups": res.n_groups,
            "singleton_groups": res.n_singleton_groups,
            "allzero_groups": res.n_allzero_groups,
            "separated_obs": res.n_separated,
            "converged": bool(res.converged),
            "iterations": res.iters,
            "max_abs_score": res.max_abs_score,
            "beta_slope": res.params[0],
            "se_slope": res.bse[0],
        })
        r = rows[-1]
        print(f"{vs.city(s):22s} n={r['cells_estimated']:6,d} "
              f"({r['dropped_pct']:5.1f}% dropped)  bg={r['block_groups']:4d} "
              f"single={r['singleton_groups']:3d} zero={r['allzero_groups']:3d} "
              f"sep={r['separated_obs']:3d}  "
              f"{'conv' if r['converged'] else 'NO CONV'} in {r['iterations']:2d} "
              f"score={r['max_abs_score']:.2e}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/ppml_diagnostics.csv", index=False)
    print(f"\nAll converged: {bool(df.converged.all())}")
    print(f"Separated observations, all cities: {int(df.separated_obs.sum())}")
    print(f"Singleton block groups, all cities: {int(df.singleton_groups.sum())}")
    print(f"Block groups with no incidents:     {int(df.allzero_groups.sum())}")
    print("wrote ppml_diagnostics.csv")


if __name__ == "__main__":
    run()
