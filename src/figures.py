"""Figures for the San Francisco pilot."""
from __future__ import annotations

import os
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, os.path.dirname(__file__))
import terrain as T
from analyze import RADII, attenuation_path, loot_ladder, prep, radius_sweep

mpl.rcParams.update({
    "figure.dpi": 300,
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.18,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
})
OUT = "outputs"
INK = "#1a1a1a"

# 3x3 bivariate ramp: x = relative height, y = crime rate
BIVAR = np.array([
    [[0.91, 0.91, 0.89], [0.60, 0.79, 0.75], [0.22, 0.66, 0.62]],
    [[0.92, 0.66, 0.62], [0.63, 0.61, 0.60], [0.24, 0.55, 0.52]],
    [[0.93, 0.36, 0.32], [0.65, 0.36, 0.36], [0.27, 0.34, 0.38]],
])


def _tercile(s):
    q = s.rank(pct=True)
    return np.clip((q * 3).astype(int), 0, 2)


def fig_bivariate(df, radius=500):
    """The money map: relative height x crime rate, over a hillshade."""
    with rasterio.open("data/raw/sf_dem_10m.tif") as src:
        z = src.read(1).astype(np.float32)
        tr = src.transform
    valid = np.isfinite(z) & (z > -5)
    hs = T.hillshade(np.where(valid, z, 0), 10.0)

    d = df.copy()
    d["rate"] = d["n_total"] / d["exposure"]
    xi = _tercile(d[f"tpi_{radius}"])
    yi = _tercile(d["rate"])

    fig = plt.figure(figsize=(11.5, 7.4))
    ax = fig.add_axes([0.02, 0.06, 0.66, 0.86])
    ext = [tr.c, tr.c + z.shape[1] * 10, tr.f - z.shape[0] * 10, tr.f]
    ax.imshow(np.where(valid, hs, np.nan), cmap="Greys_r", extent=ext,
              vmin=-0.1, vmax=1.25, interpolation="bilinear")

    cols = BIVAR[yi, xi]
    ax.scatter(d["x"], d["y"], c=cols, s=7.0, marker="s", linewidths=0)
    ax.set_xlim(d["x"].min() - 400, d["x"].max() + 400)
    ax.set_ylim(d["y"].min() - 400, d["y"].max() + 400)
    ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    ax.set_title("San Francisco — relative height vs property-crime rate\n"
                 f"100 m cells, TPI at {radius} m, 2018–2025 (n = {d.n_total.sum():,} incidents)",
                 loc="left", fontsize=12)

    # legend
    lg = fig.add_axes([0.735, 0.50, 0.20, 0.29])
    lg.imshow(BIVAR, origin="lower", interpolation="nearest")
    lg.set_xticks([0, 1, 2]); lg.set_xticklabels(["low", "mid", "high"], fontsize=8)
    lg.set_yticks([0, 1, 2]); lg.set_yticklabels(["low", "mid", "high"], fontsize=8)
    lg.set_xlabel("relative height (TPI) →", fontsize=8.5)
    lg.set_ylabel("crime rate →", fontsize=8.5)
    lg.grid(False)
    lg.set_title("legend", fontsize=9, loc="left")

    note = fig.add_axes([0.71, 0.08, 0.27, 0.34]); note.axis("off")
    note.text(0, 1,
              "Reading the map\n\n"
              "Teal  = high ground, low crime\n"
              "          (the hypothesis)\n\n"
              "Red   = low ground, high crime\n"
              "          (the hypothesis)\n\n"
              "Dark  = high ground, high crime\n"
              "          (the anomalies — these\n"
              "          are the interesting ones)\n\n"
              "Grey  = low ground, low crime",
              va="top", fontsize=8.6, color=INK, linespacing=1.45)
    fig.savefig(f"{OUT}/01_bivariate_map.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  01_bivariate_map.png")


def fig_radius(sweep):
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    ax.axhline(0, color=INK, lw=1)
    ax.fill_between(sweep.radius_m, sweep.lo, sweep.hi, color="#2a7f7a", alpha=0.16)
    ax.plot(sweep.radius_m, sweep.pct, "o-", color="#1c5f5b", lw=2, ms=6)
    ax.set_xscale("log")
    ax.set_xticks(RADII); ax.set_xticklabels([str(r) for r in RADII])
    ax.set_xlabel("radius defining “the surrounding area”  (metres, log scale)")
    ax.set_ylabel("% change in property crime\nper +1 SD of relative height")
    ax.set_title("At what scale does “higher than its surroundings” matter?\n"
                 "within block group, SES-controlled; shaded band = 95% CI", loc="left")
    fig.savefig(f"{OUT}/02_radius_sweep.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  02_radius_sweep.png")


def fig_loot(ladder):
    d = ladder.iloc[::-1].reset_index(drop=True)
    colors = ["#b4472e" if pd.isna(m) else "#1c5f5b" for m in d["mass"]]
    fig, ax = plt.subplots(figsize=(8.6, 4.9))
    y = np.arange(len(d))
    ax.axvline(0, color=INK, lw=1)
    ax.hlines(y, d.lo, d.hi, color=colors, lw=2.4, alpha=0.55)
    ax.scatter(d.pct, y, color=colors, s=52, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{o}  (n={n:,})" for o, n in zip(d.outcome, d.n_events)], fontsize=8.6)
    ax.set_xlabel("% change in crime per +1 SD of relative height (TPI 500 m)")
    ax.set_title("The falsification test: does elevation deter heavy loot more than light loot?\n"
                 "an effort mechanism predicts a clean top-to-bottom gradient — teal = theft, red = no-loot controls",
                 loc="left", fontsize=10)
    fig.savefig(f"{OUT}/03_loot_ladder.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  03_loot_ladder.png")


def fig_attenuation(path):
    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    y = np.arange(len(path))[::-1]
    ax.axvline(0, color=INK, lw=1)
    ax.hlines(y, path.lo, path.hi, color="#42566b", lw=2.6, alpha=0.6)
    ax.scatter(path.pct, y, color="#22384d", s=62, zorder=3)
    for yy, p in zip(y, path.pct):
        ax.annotate(f"{p:.1f}%", (p, yy), textcoords="offset points",
                    xytext=(0, 11), ha="center", fontsize=9, color=INK)
    ax.set_yticks(y); ax.set_yticklabels(path.spec, fontsize=9.5)
    ax.set_xlabel("% change in property crime per +1 SD of relative height")
    ax.set_title("How much of the elevation effect survives controls?\n"
                 "each step strips out more of the “hills are just wealthy” explanation", loc="left")
    fig.savefig(f"{OUT}/04_attenuation.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  04_attenuation.png")


def fig_dose(df, radius=500):
    d = df.copy()
    d["rate"] = 1000 * d["n_total"] / d["exposure"]
    d["dec"] = pd.qcut(d[f"tpi_{radius}"], 10, labels=False, duplicates="drop")
    g = d.groupby("dec").agg(rate=("rate", "mean"), tpi=(f"tpi_{radius}", "mean"),
                             n=("rate", "size"))
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    ax.plot(g.tpi, g.rate, "o-", color="#8c4a2f", lw=2, ms=6)
    ax.set_xlabel(f"relative height — metres above the mean within {radius} m")
    ax.set_ylabel("property crimes per 1,000 residents+units")
    ax.set_title("Dose–response, raw (no controls)\n"
                 "the shape is why a linear coefficient would mislead", loc="left")
    fig.savefig(f"{OUT}/05_dose_response.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  05_dose_response.png")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    df = prep()
    print("figures:")
    fig_bivariate(df)
    fig_dose(df)
    fig_attenuation(attenuation_path(df))
    fig_radius(radius_sweep(df))
    fig_loot(loot_ladder(df))
    print("done")
