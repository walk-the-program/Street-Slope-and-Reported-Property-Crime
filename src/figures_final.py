"""Final figures for the manuscript."""
from __future__ import annotations

import os
import sys
import warnings

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings("ignore")

mpl.rcParams.update({
    "figure.dpi": 300, "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.18,
    "axes.titlesize": 11, "axes.titleweight": "bold",
})
OUT = "outputs"
INK, TEAL, RUST, GREY = "#1a1a1a", "#1c5f5b", "#b4472e", "#8d8d8d"

NICE = {"cos-seattle": "Seattle", "sfgov": "San Francisco", "kcmo": "Kansas City",
        "cincinnati-oh": "Cincinnati", "montgomerycountymd": "Montgomery Cty MD",
        "cityofchicago": "Chicago", "brla": "Baton Rouge", "buffalony": "Buffalo"}


def nm(c):
    return NICE.get(c, c.replace("_", " ").title())


def fig_slope_vs_tpi():
    """Headline: steepness is consistent, relative height is not."""
    d = pd.read_csv(f"{OUT}/slope_vs_tpi.csv")
    d = d[d.expo == "bldg"].copy()
    d["label"] = d.city.map(nm)
    d = d.sort_values("slope_deg_z")
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    ax.axvline(0, color=INK, lw=1)
    ax.scatter(d.slope_deg_z, y - 0.13, s=105, color=TEAL, zorder=3,
               label="slope (steepness)")
    ax.scatter(d["tpi_500_z"], y + 0.13, s=105, color=RUST, marker="D", zorder=3,
               label="relative height (TPI 500 m)")
    for yi, a, b in zip(y, d.slope_deg_z, d["tpi_500_z"]):
        ax.plot([a, b], [yi - 0.13, yi + 0.13], color=GREY, lw=1.2, zorder=1)
    ax.set_yticks(y); ax.set_yticklabels(d.label, fontsize=9.5)
    ax.set_xlabel("% change in property crime per +1 SD of the terrain measure\n"
                  "(within block group, SES-controlled, building-based exposure)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2,
              fontsize=9, frameon=False)
    ax.set_title("Steepness predicts less property crime in every city.\n"
                 "Relative height — the measure the literature emphasises — flips sign.",
                 loc="left")
    fig.savefig(f"{OUT}/30_slope_vs_tpi.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  30_slope_vs_tpi.png")


def fig_noloot(csv, fname, title, sub):
    d = pd.read_csv(csv)
    d["label"] = d.city.map(nm)
    d = d.sort_values("pct_a")
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(9.0, 0.62 * len(d) + 2.6))
    ax.axvline(0, color=INK, lw=1)
    for yi, r in zip(y, d.itertuples()):
        ax.plot([r.pct_a, r.pct_b], [yi, yi], color="#c9c9c9", lw=2.4, zorder=1)
    ax.scatter(d.pct_a, y, s=100, color=TEAL, zorder=3, label="theft  (goods carried away)")
    ax.scatter(d.pct_b, y, s=100, color=RUST, marker="D", zorder=3,
               label="vandalism / arson  (nothing carried)")
    ax.set_yticks(y); ax.set_yticklabels(d.label, fontsize=9.5)
    ax.set_xlabel("% change in crime per +1 SD  (within block group, SES-controlled)")
    ax.legend(loc="best", fontsize=8.8, frameon=False)
    ax.set_title(f"{title}\n{sub}", loc="left", fontsize=10.5)
    fig.savefig(f"{OUT}/{fname}", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  {fname}")


def fig_loot_ladder_slope():
    """Loot mass against the slope effect, San Francisco segments."""
    d = pd.read_csv(f"{OUT}/loot_ladder_slope.csv")
    colors = [RUST if pd.isna(k) or k == 0.0 else TEAL for k in d.loot_kg]
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    y = np.arange(len(d))[::-1]
    ax.axvline(0, color=INK, lw=1)
    ax.hlines(y, d.lo, d.hi, color=colors, lw=2.2, alpha=0.5)
    ax.scatter(d.pct, y, s=95, color=colors, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{l}  (n={n:,})" for l, n in zip(d.label, d.n)], fontsize=8.8)
    ax.set_xlabel("% change per +1 SD of slope  (San Francisco street segments, 95% CI)")
    ax.set_title("No gradient with the weight carried away\n"
                 "teal = goods removed, red = nothing removed; an effort account "
                 "requires the red markers near zero",
                 loc="left", fontsize=10.5)
    fig.savefig(f"{OUT}/32_loot_ladder_slope.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  32_loot_ladder_slope.png")


if __name__ == "__main__":
    print("final figures:")
    fig_slope_vs_tpi()
    fig_noloot(f"{OUT}/h1_slope.csv", "31_noloot_slope.png",
               "The effort mechanism fails: steepness deters theft and vandalism alike",
               "vandalism has nothing to carry, so an effort account requires the red diamonds to sit near zero")
    fig_loot_ladder_slope()
    print("done")


def fig_per_degree():
    """The headline: a replicated constant where terrain is real, noise where it is not."""
    d = pd.read_csv(f"{OUT}/slope_per_degree.csv").sort_values("slope_sd", ascending=False)
    d["label"] = d.city.map(nm)
    y = np.arange(len(d))[::-1]
    colors = [TEAL if q else GREY for q in d.qualifies]
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    ax.axvline(0, color=INK, lw=1)
    ax.hlines(y, d.lo, d.hi, color=colors, lw=2.6, alpha=0.55)
    ax.scatter(d.pct_per_deg, y, s=95, color=colors, zorder=3)
    ax.axvspan(-7.06, -5.28, color=TEAL, alpha=0.10, zorder=0)
    ax.axvline(-6.18, color=TEAL, ls="--", lw=1.6, zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{l}   ({s:.1f}° SD)" for l, s in zip(d.label, d.slope_sd)],
                       fontsize=9.3)
    ax.set_xlabel("% change in property crime per additional degree of slope   (95% CI)")
    ax.text(-6.18, -0.75,
            "pooled where terrain is real:  −6.18% per degree  (I² = 0.00)",
            fontsize=8.8, color=TEAL, ha="center", fontweight="bold")
    for yi, q in zip(y, d.qualifies):
        if not q:
            ax.annotate("too flat to measure", (2.0, yi), fontsize=7.6, color=GREY,
                        va="center", annotation_clip=False)
    ax.set_xlim(-27, 9)
    ax.set_ylim(-1.4, len(d) - 0.4)
    ax.set_title("Where there is real gradient, the effect is a tight constant.\n"
                 "Where there is not, the same model returns three times the effect and "
                 "disagrees with itself.", loc="left", fontsize=10.5)
    fig.savefig(f"{OUT}/33_per_degree.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  33_per_degree.png")


def fig_attenuation_by_gradient():
    """The per-degree effect scales inversely with how much gradient a city has.

    Cities with little true gradient have their slope measure dominated by
    embankments, crowned roadbeds and DEM noise, which correlate with land use
    and inflate the apparent per-degree coefficient. Note the relationship is a
    floor effect rather than a smooth trend: Pittsburgh has the most gradient of
    any city here *and* the largest above-floor effect, which argues against
    pure attenuation and for genuine between-city heterogeneity above the floor.
    """
    d = pd.read_csv(f"{OUT}/slope_per_degree_full.csv")
    r = np.corrcoef(d.slope_sd, d.pct_per_deg)[0, 1]
    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    ax.axhline(0, color=INK, lw=1)
    ax.axvline(3.0, color=RUST, ls="--", lw=1.4)
    ax.axvspan(0, 3.0, color=RUST, alpha=0.06)
    above = d.slope_sd >= 3
    ax.errorbar(d.slope_sd[above], d.pct_per_deg[above],
                yerr=[d.pct_per_deg[above] - d.lo[above], d.hi[above] - d.pct_per_deg[above]],
                fmt="o", ms=9, color=TEAL, ecolor=TEAL, elinewidth=1.6, capsize=3,
                label="above gradient floor")
    ax.errorbar(d.slope_sd[~above], d.pct_per_deg[~above],
                yerr=[d.pct_per_deg[~above] - d.lo[~above], d.hi[~above] - d.pct_per_deg[~above]],
                fmt="D", ms=8, color=GREY, ecolor=GREY, elinewidth=1.6, capsize=3,
                label="below floor (too flat to measure)")
    for x, y, c in zip(d.slope_sd, d.pct_per_deg, d.city):
        ax.annotate(c, (x, y), fontsize=7.6, xytext=(7, 5),
                    textcoords="offset points", color="#444")
    ax.set_xlabel("within-city SD of street slope (degrees) — how much gradient there is to measure")
    ax.set_ylabel("% change in property crime\nper additional degree of slope")
    ax.legend(loc="lower right", fontsize=8.6, frameon=False)
    ax.set_title("Below about 3° of gradient the estimate is inflated and unstable\n"
                 f"the two groups barely overlap (r = {r:+.2f}, n = 9); above the floor the "
                 "effect is heterogeneous but plausible",
                 loc="left", fontsize=10.5)
    fig.savefig(f"{OUT}/34_attenuation_by_gradient.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  34_attenuation_by_gradient.png")


def fig_target_denominator():
    """The strongest objection, refuted.

    If steep streets simply held fewer targets per unit of measured housing, then
    counting the targets directly should collapse the slope effect. It roughly
    doubles instead, which means the conventional housing denominator was
    attenuating the effect rather than manufacturing it.
    """
    t = pd.read_csv(f"{OUT}/target_exposure_tests.csv")
    t = t[t.controls == "SES"]
    keep = [("n_TFV", "on-street parking spaces", "theft from vehicle"),
            ("n_MVT", "on-street parking spaces", "motor vehicle theft"),
            ("n_VEH", "on-street + off-street parking", "all vehicle crime"),
            ("n_BURG_ALL", "base addresses (front doors)", "burglary"),
            ("n_BURG_RES", "base addresses (front doors)", "residential burglary"),
            ("n_NO_LOOT", "parking spaces + front doors", "vandalism / arson"),
            ("n_total", "parking spaces + front doors", "all property crime")]
    rows = []
    for out, tgt, lab in keep:
        g = t[(t.outcome == out) & (t.target == tgt)]
        if g.empty:
            continue
        rows.append({"label": lab,
                     "housing": g[g.offset == "housing"].pct.iloc[0],
                     "target": g[g.offset == "target"].pct.iloc[0]})
    d = pd.DataFrame(rows)
    y = np.arange(len(d))[::-1]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.axvline(0, color=INK, lw=1)
    for yi, r in zip(y, d.itertuples()):
        ax.annotate("", xy=(r.target, yi), xytext=(r.housing, yi),
                    arrowprops=dict(arrowstyle="->", color="#bbb", lw=1.8))
    ax.scatter(d.housing, y, s=92, color=GREY, zorder=3,
               label="housing units as denominator (conventional)")
    ax.scatter(d.target, y, s=92, color=TEAL, marker="D", zorder=3,
               label="actual targets as denominator (parking spaces, front doors)")
    ax.set_yticks(y); ax.set_yticklabels(d.label, fontsize=9.3)
    ax.set_xlabel("% change in crime per additional degree of slope  "
                  "(San Francisco street segments)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), fontsize=8.6,
              frameon=False)
    ax.set_title("The strongest objection, refuted\n"
                 "if steep streets merely held fewer targets, counting the targets would "
                 "push these to zero — instead the effect doubles",
                 loc="left", fontsize=10.5)
    fig.savefig(f"{OUT}/35_target_denominator.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  35_target_denominator.png")
