"""Inference that does not assume block groups are independent of each other.

Clustering on block group allows anything to happen inside a block group and
nothing between them. That is the wrong shape for this problem: two cells either
side of a block-group boundary are metres apart and share whatever the estimator
cannot see -- the same street, the same lighting, the same parking regime. The
review's point stands, and comparing a block group's diameter with a Conley
bandwidth does not settle it, because the two estimators restrict different
things.

A spatial block bootstrap sidesteps the argument. Tile the city into square
blocks much larger than a block group, resample whole tiles with replacement,
and refit. Dependence of any form inside a tile is preserved by construction,
including dependence that crosses block-group lines. The only assumption left is
that tiles far apart are roughly independent, which is what the Moran plots
support.

Tiles are 1 km, about five block-group diameters in these cities.
"""
from __future__ import annotations

import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings("ignore")

from analyze import SES, coef, poisson
from regen_all import prep_cells
import vizstyle as vs

OUT = "outputs"
CITIES = ["pittsburgh", "data_sfgov_org", "cos-data_seattle_gov",
          "data_cincinnati-oh_gov"]
TILE_M = 1000
N_BOOT = 400


def run(n_boot=N_BOOT, tile_m=TILE_M):
    rows = []
    for s in CITIES:
        d = prep_cells(f"data/interim/cells_exposure/{s}.parquet")
        res, names = poisson(d, "n_total", ["slope_deg_raw"] + SES, bg_fe=True)
        base = coef(res, names, "slope_deg_raw")

        tx = (d.x.values // tile_m).astype(np.int64)
        ty = (d.y.values // tile_m).astype(np.int64)
        tile = tx * 100_000 + ty
        uniq = np.unique(tile)
        idx = {t: np.flatnonzero(tile == t) for t in uniq}

        rng = np.random.default_rng(11)
        draws = []
        for _ in range(n_boot):
            pick = rng.choice(uniq, size=len(uniq), replace=True)
            take = np.concatenate([idx[t] for t in pick])
            dd = d.iloc[take].copy()
            # Relabel block groups per draw so a tile sampled twice does not
            # have its two copies share one fixed effect.
            rep = np.repeat(np.arange(len(pick)), [len(idx[t]) for t in pick])
            dd["GEOID"] = dd.GEOID.astype(str) + "_" + rep.astype(str)
            dd = dd[dd.groupby("GEOID").GEOID.transform("size") >= 3]
            if len(dd) < 400:
                continue
            try:
                r, n = poisson(dd, "n_total", ["slope_deg_raw"] + SES, bg_fe=True)
                b = r.params[0]
                if np.isfinite(b) and abs(b) < 2:
                    draws.append(b)
            except Exception:
                pass

        b = np.array(draws)
        se_sb = float(b.std(ddof=1))
        lo, hi = np.percentile(b, [2.5, 97.5])
        rows.append({
            "city": vs.city(s), "slug": s, "n_tiles": len(uniq),
            "tile_m": tile_m, "draws_ok": len(b),
            "beta": base["beta"], "pct": base["pct"],
            "se_cluster": base["se"],
            "lo_cluster": base["lo"], "hi_cluster": base["hi"],
            "se_spatial_block": se_sb,
            "lo_spatial_block": 100 * (np.exp(lo) - 1),
            "hi_spatial_block": 100 * (np.exp(hi) - 1),
            "se_ratio": se_sb / base["se"],
        })
        r = rows[-1]
        print(f"{r['city']:22s} {r['pct']:+6.2f}%   cluster SE {r['se_cluster']:.4f} "
              f"[{r['lo_cluster']:+6.2f},{r['hi_cluster']:+6.2f}]   "
              f"block bootstrap SE {se_sb:.4f} "
              f"[{r['lo_spatial_block']:+6.2f},{r['hi_spatial_block']:+6.2f}]   "
              f"ratio {r['se_ratio']:.2f}x  ({len(uniq)} tiles)", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/spatial_block_bootstrap.csv", index=False)
    print(f"\nWorst inflation of the standard error: {df.se_ratio.max():.2f}x")
    print("wrote spatial_block_bootstrap.csv")


if __name__ == "__main__":
    run()
