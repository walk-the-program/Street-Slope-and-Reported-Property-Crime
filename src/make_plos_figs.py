"""Turn the manuscript PNGs into the files PLOS actually accepts, and check them.

PLOS will not take a figure embedded in the manuscript PDF and will not take a
PNG. Each figure has to arrive as its own TIFF or EPS, named Fig1, Fig2 and so
on in citation order, and it has to sit inside a set of hard limits. Those
limits are worth writing down because three of them are easy to breach without
noticing:

    format      TIFF or EPS only
    resolution  300-600 dpi
    width       789-2250 px  (2.63-7.5 in at 300 dpi)
    height      <= 2625 px   (8.75 in)
    colour      RGB 8 bit/channel, or greyscale
    size        <= 10 MB

The order below is citation order in the manuscript, which is not the order the
figures were written in -- Fig5 in the source is cited second.
"""
from __future__ import annotations

import os

from PIL import Image

OUT = "outputs"
DEST = f"{OUT}/plos_figs"

# (source PNG, PLOS figure number) -- in the order the manuscript cites them.
FIGURES = [
    ("fig1_gradient_floor.png", 1),
    ("fig5_slope_vs_height.png", 2),
    ("fig2_noloot.png", 3),
    ("fig4_loot_ladder.png", 4),
    ("fig3_target_denominator.png", 5),
]

DPI = 300
W_MIN, W_MAX, H_MAX = 789, 2250, 2625
MB = 1024 * 1024


def convert():
    os.makedirs(DEST, exist_ok=True)
    rows, failures = [], []
    for src, n in FIGURES:
        im = Image.open(f"{OUT}/{src}")
        # Flatten to RGB. The figures are saved on an opaque surface colour, so
        # there is nothing to lose, but savefig leaves an alpha channel behind
        # and PLOS wants 8 bit/channel RGB.
        if im.mode != "RGB":
            im = im.convert("RGB")
        path = f"{DEST}/Fig{n}.tif"
        # LZW is lossless and keeps every one of these comfortably under 10 MB.
        im.save(path, format="TIFF", compression="tiff_lzw", dpi=(DPI, DPI))

        w, h = im.size
        size = os.path.getsize(path)
        bad = []
        if not W_MIN <= w <= W_MAX:
            bad.append(f"width {w}px outside {W_MIN}-{W_MAX}")
        if h > H_MAX:
            bad.append(f"height {h}px over {H_MAX}")
        if size > 10 * MB:
            bad.append(f"{size / MB:.1f} MB over 10 MB")
        if bad:
            failures.append((f"Fig{n}", bad))
        rows.append((f"Fig{n}.tif", src, w, h, w / DPI, h / DPI, size / MB,
                     "ok" if not bad else "FAIL"))

    print(f"{'file':12s} {'from':30s} {'px':>12s} {'inches':>13s} {'MB':>6s}  status")
    for f, src, w, h, wi, hi, mb, st in rows:
        print(f"{f:12s} {src:30s} {w:5d}x{h:5d} {wi:5.2f}x{hi:5.2f} {mb:6.2f}  {st}")

    if failures:
        print("\nPLOS spec violations:")
        for name, bad in failures:
            for b in bad:
                print(f"  {name}: {b}")
        raise SystemExit(1)
    print(f"\nAll {len(rows)} figures within PLOS limits -> {DEST}/")


if __name__ == "__main__":
    convert()
