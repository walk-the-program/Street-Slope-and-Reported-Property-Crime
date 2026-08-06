"""One shared visual style for every figure in this project.

Figures were previously written one at a time and drifted: three different teals,
raw database slugs where city names belong, legends floating inside the plot
body, and in one case an axis labelled "per +1 SD" on per-degree data. This
module exists so that none of that can happen again -- every figure imports its
colours, its label text and its legend placement from here.

The palette is the validated three-slot categorical set (blue, orange, aqua).
It clears the all-pairs colour-vision gates in both normal and simulated CVD
vision, which matters because several figures put two series side by side and
the reader has to tell them apart. Charts here use at most two of the three, so
the pair in play is always blue-orange, the widest-separated pair available.
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

# --- palette -------------------------------------------------------------
# Deep petrol and burnt rust. Chosen over the stock blue/orange for looks, then
# validated rather than trusted: all-pairs CVD dE 17.9, normal-vision dE 26.3,
# both clear of the floors, with every hue inside the lightness band and above
# the chroma floor. Several handsomer, more muted candidates were rejected --
# desaturating a blue far enough to look editorial drops it under the chroma
# floor, where it starts reading as grey and stops functioning as an identity.
SERIES_1 = "#0d7d9e"   # petrol -- the primary/"conventional" series
SERIES_2 = "#c04a1e"   # rust   -- the contrast/"treatment" series
SERIES_3 = "#1baf7a"   # aqua   -- third slot, rarely needed

MUTED = "#9a958d"      # de-emphasised marks (below-floor cities, excluded rows)
INK = "#1c1a17"        # primary text and the zero line
INK_2 = "#57534e"      # secondary text: point labels, annotations
INK_3 = "#8f8a83"      # muted text and leader lines
GRID = "#e7e5e0"
SURFACE = "#fcfcfa"
# Annotation ink. Deliberately neutral: the threshold line is not a series, and
# giving it a hue made it compete with the rust marks for attention.
ACCENT = "#6f6a62"

# --- marks ---------------------------------------------------------------
MARKER = 90            # >= 8px on screen at these figure sizes
LINE_W = 2.0
RING = 1.6             # surface-coloured ring so overlapping marks stay legible


def apply():
    """Global rcParams. Call once at import time in each figure module."""
    mpl.rcParams.update({
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        # PLOS accepts only Arial, Times or Symbol inside a figure, at 8-12pt.
        # DejaVu Sans is matplotlib's default and is not on that list.
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 9.5,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlepad": 12,
        "axes.labelsize": 9.5,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": GRID,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9.5,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "legend.fontsize": 9,
    })


# --- city names ----------------------------------------------------------
# Every slug the pipeline can emit. A missing entry used to fall through to
# .title() and print "Montgomerycountymd" on a manuscript figure.
CITY = {
    "sfgov": "San Francisco",
    "data_sfgov_org": "San Francisco",
    "cos-seattle": "Seattle",
    "cos-data_seattle_gov": "Seattle",
    "seattle": "Seattle",
    "cincinnati-oh": "Cincinnati",
    "data_cincinnati-oh_gov": "Cincinnati",
    "cincinnati": "Cincinnati",
    "pittsburgh": "Pittsburgh",
    "baltimore": "Baltimore",
    "charlotte": "Charlotte",
    "kcmo": "Kansas City",
    "data_kcmo_org": "Kansas City",
    "montgomerycountymd": "Montgomery Co., MD",
    "data_montgomerycountymd_gov": "Montgomery Co., MD",
    "chicago": "Chicago",
    "cityofchicago": "Chicago",
    "data_cityofchicago_org": "Chicago",
    "brla": "Baton Rouge",
    "data_brla_gov": "Baton Rouge",
    "buffalony": "Buffalo",
    "marincounty": "Marin County",
    "weho": "West Hollywood",
    "princegeorgescountymd": "Prince George's Co., MD",
    "lacity": "Los Angeles",
    "data_lacity_org": "Los Angeles",
    "fusioncenter_nhit": "NHIT Fusion Center",
}


def city(slug: str) -> str:
    s = str(slug)
    if s in CITY:
        return CITY[s]
    key = (s.replace("data_", "").replace("_gov", "").replace("_org", "")
            .replace("cityof", ""))
    return CITY.get(key, key.replace("_", " ").title())


# --- helpers -------------------------------------------------------------
def zero_line(ax, vertical=True):
    """The reference line at no effect. Ink, not a series colour."""
    (ax.axvline if vertical else ax.axhline)(0, color=INK, lw=1.0, zorder=2)


def legend_below(ax, ncol=2, y=-0.20, order=None):
    """Legends live outside the data area. Never floating over the marks.

    `order` re-sequences the entries, which matters when draw order is chosen
    for occlusion rather than for reading order -- the series drawn last so it
    stays visible is not necessarily the one to name first.
    """
    h, l = ax.get_legend_handles_labels()
    if order is not None:
        h = [h[i] for i in order]
        l = [l[i] for i in order]
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, y), ncol=ncol,
              frameon=False, fontsize=9, handletextpad=0.5, columnspacing=2.4,
              borderpad=0.0, borderaxespad=0.0)


def declutter(xs, ys, min_gap, lo=None, hi=None):
    """Nudge point labels apart vertically so they cannot collide.

    Greedy: sort by y, then push any label that sits within `min_gap` of the one
    below it upward. Returns label y-positions, leaving the marks where they
    are. Used by the scatter figures, where several cities share almost the same
    coefficient and their labels used to overprint each other.
    """
    order = np.argsort(ys)
    out = np.array(ys, dtype=float)
    for i in range(1, len(order)):
        prev, cur = order[i - 1], order[i]
        if out[cur] - out[prev] < min_gap:
            out[cur] = out[prev] + min_gap
    if hi is not None:
        over = out.max() - hi
        if over > 0:
            out -= over
    if lo is not None:
        under = lo - out.min()
        if under > 0:
            out += under
    return out


def save(fig, path):
    fig.savefig(path, bbox_inches="tight", facecolor=SURFACE, dpi=300)
    plt.close(fig)
    print(f"  {path.split('/')[-1]}")
