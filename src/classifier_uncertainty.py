"""Push the classifier's error rate through to the coefficients.

The audit hand-coded 511 offense description strings and reported 85.7% string
accuracy and 93.7% incident-weighted accuracy. The analysis then used the labels
as if they were correct. They are not, and the review is right that this matters
most for exactly the quantity the paper leans on hardest -- the theft against
no-loot contrast, which is a comparison *between* two classifier outputs.

The procedure: build P(true class | predicted class) from the audit, weighted by
how many incidents each string covers, then for every draw reassign each cell's
counts by a multinomial from that matrix and refit. The spread of the resulting
coefficients is the part of the uncertainty the standard errors never saw.

Two honest caveats about the matrix. It is pooled across cities, because the
audit is not large enough to condition per city. And a string never sampled
contributes nothing, so the rarest failure modes are underrepresented -- this is
a lower bound on label uncertainty, not a full accounting.
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
from regen_all import CELLS, prep_cells, slug
import meta
import vizstyle as vs

OUT = "outputs"
N_DRAW = 200
# Classes the grid panel carries. AMBIG/OTHER/ROBBERY are not property outcomes;
# mass flowing into them leaves the analysis, which is itself a source of
# variation the point estimate ignores.
PROPERTY = ["MASS_1", "MASS_2", "MASS_3", "MASS_4", "MASS_5", "MVT", "NO_LOOT"]
THEFT = ["MASS_1", "MASS_2", "MASS_3", "MASS_4", "MASS_5"]


def confusion():
    """P(true | predicted), incident-weighted, rows summing to one."""
    v = pd.read_csv(f"{OUT}/classifier_validation.csv")
    v = v[v.hand_code.notna() & v.classify_text_as_deployed.notna()]
    ct = pd.crosstab(v.classify_text_as_deployed, v.hand_code,
                     values=v.n_incidents, aggfunc="sum").fillna(0.0)
    for c in set(ct.index) | set(ct.columns):
        if c not in ct.columns:
            ct[c] = 0.0
        if c not in ct.index:
            ct.loc[c] = 0.0
    ct = ct.sort_index().sort_index(axis=1)
    return ct.div(ct.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)


def run(n_draw=N_DRAW):
    P = confusion()
    cols = list(P.columns)
    rng = np.random.default_rng(20260804)

    rows, per_city = [], []
    for path in sorted(glob_cells()):
        s = slug(path)
        d = prep_cells(path)
        if len(d) < 500:
            continue
        pred = [c for c in PROPERTY if f"n_{c}" in d.columns
                and d[f"n_{c}"].sum() > 0]
        base_counts = {c: d[f"n_{c}"].values.astype(np.int64) for c in pred}

        betas, difs = [], []
        for _ in range(n_draw):
            true = {c: np.zeros(len(d), dtype=np.int64) for c in cols}
            for c in pred:
                p = P.loc[c].values if c in P.index else None
                if p is None or p.sum() <= 0:
                    true[c] += base_counts[c]
                    continue
                draw = rng.multinomial(base_counts[c], p)
                for j, tgt in enumerate(cols):
                    true[tgt] += draw[:, j]
            d["_tot"] = sum(true[c] for c in PROPERTY if c in true).astype(float)
            d["_theft"] = sum(true[c] for c in THEFT if c in true).astype(float)
            d["_nl"] = true["NO_LOOT"].astype(float) if "NO_LOOT" in true else 0.0
            try:
                r, n = poisson(d, "_tot", ["slope_deg_raw"] + SES, bg_fe=True)
                betas.append(r.params[0])
                ra, _ = poisson(d, "_theft", ["slope_deg_raw"] + SES, bg_fe=True)
                rb, _ = poisson(d, "_nl", ["slope_deg_raw"] + SES, bg_fe=True)
                difs.append(ra.params[0] - rb.params[0])
            except Exception:
                pass

        res, names = poisson(d, "n_total", ["slope_deg_raw"] + SES, bg_fe=True)
        c0 = coef(res, names, "slope_deg_raw")
        b = np.array(betas)
        sd_label = float(b.std(ddof=1)) if len(b) > 2 else np.nan
        total_se = float(np.sqrt(c0["se"] ** 2 + sd_label ** 2))
        rows.append({
            "city": vs.city(s), "slug": s, "draws": len(b),
            "pct_point": c0["pct"], "se_sampling": c0["se"],
            "se_label": sd_label, "se_total": total_se,
            "pct_lo_total": 100 * (np.exp(c0["beta"] - 1.96 * total_se) - 1),
            "pct_hi_total": 100 * (np.exp(c0["beta"] + 1.96 * total_se) - 1),
            "label_share_of_var": sd_label ** 2 / (sd_label ** 2 + c0["se"] ** 2),
            "beta": c0["beta"],
            "diff_sd_label": float(np.std(difs, ddof=1)) if len(difs) > 2 else np.nan,
        })
        r = rows[-1]
        print(f"{r['city']:22s} {r['pct_point']:+6.2f}%  se(sampling) "
              f"{r['se_sampling']:.4f}  se(labels) {r['se_label']:.4f}  "
              f"-> total {r['se_total']:.4f}  "
              f"[{r['pct_lo_total']:+.2f},{r['pct_hi_total']:+.2f}]", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/classifier_uncertainty.csv", index=False)

    q = df[df.slug.isin(["pittsburgh", "data_sfgov_org",
                         "cos-data_seattle_gov", "data_cincinnati-oh_gov"])]
    p_sam = meta.random_effects(q.beta.values, q.se_sampling.values)
    p_tot = meta.random_effects(q.beta.values, q.se_total.values)
    print(f"\nAbove-floor pool, sampling error only: {p_sam['pct']:+.2f}% "
          f"[{p_sam['pct_lo']:+.2f},{p_sam['pct_hi']:+.2f}]")
    print(f"Above-floor pool, + label uncertainty : {p_tot['pct']:+.2f}% "
          f"[{p_tot['pct_lo']:+.2f},{p_tot['pct_hi']:+.2f}]")
    pd.DataFrame([
        {"pool": "sampling error only", **{k: p_sam[k] for k in
         ("k", "pct", "pct_lo", "pct_hi", "tau2", "I2")}},
        {"pool": "with label uncertainty", **{k: p_tot[k] for k in
         ("k", "pct", "pct_lo", "pct_hi", "tau2", "I2")}},
    ]).to_csv(f"{OUT}/classifier_uncertainty_pool.csv", index=False)
    print("wrote classifier_uncertainty.csv, classifier_uncertainty_pool.csv")


def glob_cells():
    import glob
    return glob.glob(CELLS)


if __name__ == "__main__":
    run()
