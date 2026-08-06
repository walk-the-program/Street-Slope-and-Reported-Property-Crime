"""Figures for the multi-city analysis."""
from __future__ import annotations

import os
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from analyze import RADII
from analyze_national import stage_two, wls

mpl.rcParams.update({
    "figure.dpi": 300, "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.18,
    "axes.titlesize": 11, "axes.titleweight": "bold",
})
OUT = "outputs"
INK = "#1a1a1a"
TEAL = "#1c5f5b"
RUST = "#b4472e"


def nice(c):
    return (c.replace("_gov", "").replace("_org", "").replace("_us", "")
            .replace("data_", "").replace("cityof", "").replace("_", " ").title())


def fig_forest(df):
    d = df.sort_values("pct").reset_index(drop=True)
    y = np.arange(len(d))
    colors = [RUST if p > 0 else TEAL for p in d.pct]
    fig, ax = plt.subplots(figsize=(8.4, 0.42 * len(d) + 2.2))
    ax.axvline(0, color=INK, lw=1)
    ax.hlines(y, d.lo, d.hi, color=colors, lw=2.2, alpha=0.5)
    ax.scatter(d.pct, y, color=colors, s=46, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{nice(c)}  ({n:,})" for c, n in zip(d.city, d.n_events)], fontsize=8.4)
    ax.set_xlabel("% change in property crime per +1 SD of relative height (TPI 500 m)")
    ax.set_title("Every city, estimated separately\n"
                 "within block group, SES-controlled; bars = 95% CI", loc="left")
    ax.set_xlim(min(-40, d.lo.min() - 5), max(25, d.hi.max() + 5))
    fig.savefig(f"{OUT}/10_forest.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  10_forest.png")


def fig_stage_two(df):
    d = df.dropna(subset=["beta", "se", "rho_abs_income"])
    s = stage_two(df)
    x, y, w = d.rho_abs_income.values, d.beta.values, 1 / d.se.values ** 2
    b, _ = wls(x, y, w)

    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    ax.axhline(0, color=INK, lw=1)
    ax.axvline(0, color="#999", lw=1, ls="--")
    sz = 40 + 900 * (w / w.max())
    ax.scatter(x, 100 * (np.exp(y) - 1), s=sz, color=TEAL, alpha=0.55,
               edgecolor=TEAL, linewidth=1.2, zorder=3)
    for xi, yi, c in zip(x, 100 * (np.exp(y) - 1), d.city):
        ax.annotate(nice(c), (xi, yi), fontsize=7.2, xytext=(5, 4),
                    textcoords="offset points", color="#444")
    xs = np.linspace(min(x.min(), -0.05) - 0.03, max(x.max(), 0.05) + 0.03, 60)
    ax.plot(xs, 100 * (np.exp(b[0] + b[1] * xs) - 1), color=RUST, lw=2)

    ip = s["intercept_pct"]
    ax.scatter([0], [ip], marker="D", s=110, color=RUST, zorder=5)
    ax.annotate(f"  intercept = {ip:+.1f}%\n  (effect with affluence removed)\n"
                f"  95% CI {s['intercept_boot_lo']:+.1f} to {s['intercept_boot_hi']:+.1f}",
                (0, ip), fontsize=8.6, color=RUST, xytext=(10, -26),
                textcoords="offset points", fontweight="bold")

    ax.set_xlabel("correlation between elevation and household income, within city  →\n"
                  "left = hills are poorer      right = hills are richer")
    ax.set_ylabel("% change in property crime\nper +1 SD of relative height")
    ax.set_title("Stage two: separating terrain from money\n"
                 "if the effect were only affluence, the line would pass through the origin",
                 loc="left")
    fig.savefig(f"{OUT}/11_stage_two.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  11_stage_two.png")


def fig_placebo(df):
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.axhline(0, color=INK, lw=1)
    ax.axvline(30, color="#999", lw=1, ls="--")
    ax.scatter(df.relief_p99, df.pct, s=60, color=TEAL, alpha=0.6, zorder=3)
    for xi, yi, c in zip(df.relief_p99, df.pct, df.city):
        ax.annotate(nice(c), (xi, yi), fontsize=7.2, xytext=(5, 4),
                    textcoords="offset points", color="#444")
    ax.set_xscale("log")
    ax.set_xlabel("city relief — 1st-to-99th percentile elevation range (m, log scale)")
    ax.set_ylabel("% change in property crime per +1 SD relative height")
    ax.set_title("Placebo check: flat cities should show nothing\n"
                 "left of the dashed line there is barely any terrain to measure", loc="left")
    fig.savefig(f"{OUT}/12_placebo.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  12_placebo.png")


def fig_radius_pooled(df):
    rows = []
    for r in RADII:
        b, s = df.get(f"beta_{r}"), df.get(f"se_{r}")
        if b is None:
            continue
        m = b.notna() & s.notna() & (s > 0)
        if m.sum() < 3:
            continue
        w = 1 / s[m] ** 2
        mu = np.average(b[m], weights=w)
        se = np.sqrt(1 / w.sum())
        rows.append({"r": r, "pct": 100 * (np.exp(mu) - 1),
                     "lo": 100 * (np.exp(mu - 1.96 * se) - 1),
                     "hi": 100 * (np.exp(mu + 1.96 * se) - 1)})
    if not rows:
        return
    d = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    ax.axhline(0, color=INK, lw=1)
    ax.fill_between(d.r, d.lo, d.hi, color=TEAL, alpha=0.16)
    ax.plot(d.r, d.pct, "o-", color=TEAL, lw=2, ms=6)
    ax.set_xscale("log"); ax.set_xticks(d.r); ax.set_xticklabels([str(int(v)) for v in d.r])
    ax.set_xlabel("radius defining “the surrounding area” (m, log scale)")
    ax.set_ylabel("% change per +1 SD relative height")
    ax.set_title("Pooled across all cities: at what scale does “higher” matter?\n"
                 "inverse-variance weighted; the peak estimates the substitution radius",
                 loc="left")
    fig.savefig(f"{OUT}/13_radius_pooled.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  13_radius_pooled.png")


if __name__ == "__main__":
    df = pd.read_csv(f"{OUT}/city_estimates.csv")
    print(f"figures for {len(df)} cities:")
    fig_forest(df)
    fig_stage_two(df)
    fig_placebo(df)
    fig_radius_pooled(df)
    print("done")


def fig_signal(df):
    """The diagnostic that invalidates the pooled estimate.

    Each city's estimated effect against how much relative-height variation the
    city actually has. If these estimates were measuring terrain there would be
    no relationship. Instead they slope: the cities with the least terrain
    return the largest positive "terrain effects".

    The fit is inverse-variance weighted rather than computed on a hand-picked
    subset. West Hollywood's interval runs from -42% to +557%, so it carries
    almost no weight; dropping it outright would move the correlation from
    -0.41 to -0.84, and quoting that number would be cherry-picking.
    """
    d = df.copy()
    w = 1.0 / d["se"].values ** 2
    x, y = d["tpi_sd"].values, d["pct"].values

    def wcorr(x, y, w):
        mx, my = np.average(x, weights=w), np.average(y, weights=w)
        cov = np.average((x - mx) * (y - my), weights=w)
        return cov / np.sqrt(np.average((x - mx) ** 2, weights=w)
                             * np.average((y - my) ** 2, weights=w))

    r = wcorr(x, d["beta"].values, w)
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    ax.axhline(0, color=INK, lw=1)
    ax.axvspan(0, 3, color=RUST, alpha=0.07)

    imprecise = (d["hi"] - d["lo"]) > 60
    ax.scatter(x[~imprecise], y[~imprecise], s=40 + 260 * (w / w.max())[~imprecise],
               color=TEAL, alpha=0.75, zorder=3)
    ax.scatter(x[imprecise], y[imprecise], s=55, facecolor="none",
               edgecolor="#999", linewidth=1.4, zorder=3)
    for xi, yi, c, imp in zip(x, y, d.city, imprecise):
        ax.annotate(nice(c) + (" (too noisy)" if imp else ""), (xi, yi), fontsize=7.4,
                    xytext=(7, 4), textcoords="offset points",
                    color="#999" if imp else "#444")

    b = np.polyfit(x, y, 1, w=np.sqrt(w))
    xs = np.linspace(0, x.max() * 1.05, 50)
    ax.plot(xs, np.polyval(b, xs), color=RUST, lw=2, ls="--")
    ax.text(0.6, ax.get_ylim()[0] * 0.55, "barely any\nterrain to\nmeasure",
            fontsize=8, color=RUST)
    ax.set_xlabel("SD of relative height within the city (m)  —  how much terrain there is to measure")
    ax.set_ylabel("% change in property crime\nper +1 SD of relative height")
    ax.set_title(f"Why the pooled estimate cannot be trusted   "
                 f"(inverse-variance weighted r = {r:+.2f})\n"
                 "the cities with almost no terrain return the largest positive "
                 "\u2018terrain effects\u2019", loc="left", fontsize=10.5)
    fig.savefig(f"{OUT}/14_signal_diagnostic.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  14_signal_diagnostic.png")
