"""The three manuscript figures.

Deliberately close to wordless. In a journal the caption carries the argument, so
a title baked into the image is duplicated text the reader has to skip -- and it
cannot be edited without regenerating the figure. Titles are omitted, legend
entries are two or three words, and axis labels say what the number is and
nothing else.
"""
from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import vizstyle as vs

vs.apply()
OUT = "outputs"


def fig_gradient_floor():
    """Per-degree effect against how much gradient a city has to measure.

    Was a threshold plot with a shaded exclusion zone, which made a hand-picked
    cut look like a property of the data. It now shows the meta-regression fit
    across all nine cities, with the old threshold marked but no longer
    dividing anything.
    """
    d = pd.read_csv(f"{OUT}/slope_per_degree_full.csv").copy()
    d["label"] = d.city.map(vs.city)
    above = d.slope_sd >= 3.0
    fitted = pd.read_csv(f"{OUT}/meta_regression_fit.csv")

    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    ax.grid(axis="x", visible=False)
    ax.axvline(3.0, color=vs.ACCENT, lw=1.0, ls=(0, (4, 3)), zorder=1)
    vs.zero_line(ax, vertical=False)
    ax.plot(fitted.slope_sd, fitted.pct, color=vs.SERIES_2, lw=2.0, zorder=2,
            label="meta-regression fit")

    for m, colr, lab in [(above, vs.SERIES_1, "higher gradient"),
                         (~above, vs.MUTED, "lower gradient")]:
        ax.errorbar(d.slope_sd[m], d.pct_per_deg[m],
                    yerr=[d.pct_per_deg[m] - d.lo[m], d.hi[m] - d.pct_per_deg[m]],
                    fmt="o", ms=8, color=colr, ecolor=colr, elinewidth=1.6,
                    capsize=0, alpha=0.95, zorder=3,
                    markeredgecolor=vs.SURFACE, markeredgewidth=vs.RING, label=lab)

    # Labels sit beside their marker, nudged apart only as far as they must be,
    # with a hairline leader wherever a nudge moves a label off its point. Side
    # is chosen per point: a label goes left when a right-hand label would run
    # into the next city's marker or across the floor line, which is what used
    # to make "Cincinnati" overprint Seattle's interval.
    ys = vs.declutter(d.slope_sd.values, d.pct_per_deg.values, min_gap=1.35)
    xs = d.slope_sd.values
    for i, (x, y, ytxt, lab) in enumerate(zip(xs, d.pct_per_deg, ys, d.label)):
        width = 0.085 * len(lab)          # label width, data units
        right_clear = True
        for j, xo in enumerate(xs):
            if j == i or xo <= x:
                continue
            if xo < x + width + 0.25 and abs(ys[j] - ytxt) < 2.4:
                right_clear = False
        if x < 3.0 and x + width + 0.25 > 3.0:   # would cross the floor line
            right_clear = False
        dx, ha = (0.18, "left") if right_clear else (-0.18, "right")
        if abs(ytxt - y) > 0.35:
            ax.plot([x + np.sign(dx) * 0.07, x + np.sign(dx) * 0.15], [y, ytxt],
                    color=vs.INK_3, lw=0.7, zorder=2, solid_capstyle="butt")
        ax.annotate(lab, xy=(x + dx, ytxt), fontsize=8, color=vs.INK_2,
                    va="center", ha=ha)

    ax.text(3.12, 1.9, "earlier threshold", fontsize=8, color=vs.ACCENT,
            ha="left")
    ax.set_xlabel("within-city SD of street slope (degrees)")
    ax.set_ylabel("% change in property crime\nper degree of slope")
    ax.set_xlim(-0.15, 5.9)
    ax.set_ylim(-25.5, 3.5)
    vs.legend_below(ax, ncol=3, y=-0.17, order=[1, 2, 0])
    vs.save(fig, f"{OUT}/fig1_gradient_floor.png")


def fig_noloot():
    """Theft vs no-loot crime, per degree of slope, with intervals."""
    d = pd.read_csv(f"{OUT}/h1_slope_floor.csv").copy()
    d["label"] = d.city.map(vs.city)
    d = d.sort_values("pct_a").reset_index(drop=True)
    y = np.arange(len(d))

    fig, ax = plt.subplots(figsize=(7.2, 2.5))
    ax.grid(axis="y", visible=False)
    vs.zero_line(ax)

    for yi, r in zip(y, d.itertuples()):
        ax.plot([r.pct_a, r.pct_b], [yi, yi], color=vs.GRID, lw=2.4, zorder=1,
                solid_capstyle="round")
    # Diamond first, circle on top. In Pittsburgh and San Francisco the two
    # coefficients are nearly identical, which is the finding, so the marks
    # coincide; drawing the circle last with a surface ring leaves the diamond
    # visible around it rather than letting one series vanish under the other.
    ax.scatter(d.pct_b, y, s=vs.MARKER + 26, color=vs.SERIES_2, marker="D", zorder=3,
               edgecolor=vs.SURFACE, linewidth=vs.RING, label="vandalism & arson")
    ax.scatter(d.pct_a, y, s=vs.MARKER, color=vs.SERIES_1, zorder=4,
               edgecolor=vs.SURFACE, linewidth=vs.RING, label="theft")

    ax.set_yticks(y)
    ax.set_yticklabels(d.label)
    ax.set_xlabel("% change in crime per degree of slope")
    ax.set_xlim(-11.5, 1.0)
    ax.set_ylim(-0.55, len(d) - 0.45)
    vs.legend_below(ax, ncol=2, y=-0.26, order=[1, 0])
    vs.save(fig, f"{OUT}/fig2_noloot.png")


def fig_target_denominator():
    """Housing denominator vs counting the actual targets at risk."""
    t = pd.read_csv(f"{OUT}/target_exposure_tests.csv")
    t = t[t.controls == "SES"]
    keep = [("n_TFV", "on-street parking spaces", "theft from vehicle"),
            ("n_MVT", "on-street parking spaces", "motor vehicle theft"),
            ("n_VEH", "on-street + off-street parking", "all vehicle crime"),
            ("n_BURG_ALL", "base addresses (front doors)", "burglary"),
            ("n_BURG_RES", "base addresses (front doors)", "residential burglary"),
            ("n_NO_LOOT", "parking spaces + front doors", "vandalism & arson"),
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

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.grid(axis="y", visible=False)
    vs.zero_line(ax)

    for yi, r in zip(y, d.itertuples()):
        ax.annotate("", xy=(r.target, yi), xytext=(r.housing, yi),
                    arrowprops=dict(arrowstyle="-|>", color=vs.GRID, lw=2.2,
                                    shrinkA=5, shrinkB=7,
                                    mutation_scale=13))
    ax.scatter(d.housing, y, s=vs.MARKER, color=vs.MUTED, zorder=3,
               edgecolor=vs.SURFACE, linewidth=vs.RING, label="housing units")
    ax.scatter(d.target, y, s=vs.MARKER, color=vs.SERIES_2, marker="D", zorder=4,
               edgecolor=vs.SURFACE, linewidth=vs.RING, label="targets at risk")

    ax.set_yticks(y)
    ax.set_yticklabels(d.label)
    ax.set_xlabel("% change in crime per degree of slope")
    ax.set_xlim(-12.5, 1.0)
    ax.set_ylim(-0.55, len(d) - 0.45)
    vs.legend_below(ax, ncol=2, y=-0.19)
    vs.save(fig, f"{OUT}/fig3_target_denominator.png")


if __name__ == "__main__":
    print("manuscript figures:")
    fig_gradient_floor()
    fig_noloot()
    fig_target_denominator()


def fig_loot_ladder():
    """Slope effect by how heavy the stolen goods are."""
    d = pd.read_csv(f"{OUT}/loot_ladder_slope.csv").copy()
    d["carried"] = d.loot_kg.notna() & (d.loot_kg > 0)
    y = np.arange(len(d))[::-1]
    XLO, XHI = -34.0, 6.0

    # 6.8in rather than the 7.2in the others use: the row labels on this figure
    # are long, and with a tight bounding box 7.2 rendered out to 7.66in, past
    # PLOS's 7.5in / 2250px hard maximum for figure width.
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    ax.grid(axis="y", visible=False)
    vs.zero_line(ax)
    for carried, colr, lab in [(True, vs.SERIES_1, "goods carried away"),
                               (False, vs.SERIES_2, "nothing carried / self-propelled")]:
        m = d.carried.values == carried
        # Clip intervals to the axis and mark any truncated end with a caret.
        # The pocketable class rests on 1,848 incidents and its interval spans
        # nearly 90 points; drawn in full it compresses every other row into
        # illegibility, so it is clipped rather than allowed to set the scale.
        lo = np.clip(d.lo[m], XLO, XHI)
        hi = np.clip(d.hi[m], XLO, XHI)
        ax.hlines(y[m], lo, hi, color=colr, lw=2.0, alpha=0.45, zorder=2)
        for yy, l_raw, h_raw in zip(y[m], d.lo[m], d.hi[m]):
            if l_raw < XLO:
                ax.plot(XLO, yy, marker="<", ms=5, color=colr, alpha=0.7, zorder=2)
            if h_raw > XHI:
                ax.plot(XHI, yy, marker=">", ms=5, color=colr, alpha=0.7, zorder=2)
        ax.scatter(d.pct[m], y[m], s=vs.MARKER, color=colr, zorder=3,
                   marker="o" if carried else "D",
                   edgecolor=vs.SURFACE, linewidth=vs.RING, label=lab)
    ax.set_yticks(y)
    ax.set_yticklabels(d.label)
    ax.set_xlabel("% change in crime per degree of slope")
    ax.set_xlim(XLO - 1.5, XHI + 1.0)
    ax.set_ylim(-0.55, len(d) - 0.45)
    vs.legend_below(ax, ncol=2, y=-0.21)
    vs.save(fig, f"{OUT}/fig4_loot_ladder.png")


def fig_slope_vs_height():
    """Which terrain measure replicates: slope or relative height."""
    d = pd.read_csv(f"{OUT}/slope_vs_tpi.csv").copy()
    d["label"] = d.city.map(vs.city)
    d = d.sort_values("slope_deg_z").reset_index(drop=True)
    y = np.arange(len(d))

    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.grid(axis="y", visible=False)
    vs.zero_line(ax)
    for yi, r in zip(y, d.itertuples()):
        ax.plot([r.slope_deg_z, r.tpi_500_z], [yi, yi], color=vs.GRID, lw=2.2,
                zorder=1, solid_capstyle="round")
    ax.scatter(d.slope_deg_z, y, s=vs.MARKER, color=vs.SERIES_1, zorder=3,
               edgecolor=vs.SURFACE, linewidth=vs.RING, label="slope")
    ax.scatter(d["tpi_500_z"], y, s=vs.MARKER, color=vs.SERIES_2, marker="D", zorder=3,
               edgecolor=vs.SURFACE, linewidth=vs.RING, label="relative height")
    ax.set_yticks(y)
    ax.set_yticklabels(d.label)
    ax.set_xlabel("% change in property crime per +1 SD of the terrain measure")
    ax.set_ylim(-0.55, len(d) - 0.45)
    vs.legend_below(ax, ncol=2, y=-0.22)
    vs.save(fig, f"{OUT}/fig5_slope_vs_height.png")
