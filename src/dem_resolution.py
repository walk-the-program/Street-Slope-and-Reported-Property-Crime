"""Is the per-degree slope coefficient an artefact of DEM pixel size?

The headline is expressed in physical units -- percent per degree of street
slope -- and slope is not a property of the ground, it is a property of the
ground *and the grid you measure it on*. Horn's kernel differences elevation
across three pixels, so a coarser grid averages over more terrain and returns a
flatter number. If mean slope falls with pixel size while the crime response is
unchanged, the fitted coefficient per degree must rise to compensate, and a
reviewer can dismiss "-6.2% per degree" as a statement about 10 m rasters
rather than about hills.

The test fetches a 1 m 3DEP DEM for a representative 6 km window of San
Francisco and coarsens *that same array* to 10 m and 30 m by block mean, so the
only thing varying is pixel size -- not vintage, not source, not interpolation.
Slope is then computed at each pixel size with the production
`terrain.slope_degrees`, aggregated to the 100 m analysis cells the way the
production pipeline does it (mean of fine-resolution slopes inside the cell),
and the headline Poisson model is re-fitted on each version with
`analyze.poisson`, unchanged.

Two controls make the comparison readable:

  * The window is chosen to match the citywide slope distribution (largest
    quantile deviation 0.22 degrees), so window-versus-city is not doing the
    work.

  * The production 10 m DEM is carried through the identical path. Its
    coefficient against the derived-10 m coefficient separates "which product"
    from "which pixel size", and its coefficient against the published
    citywide number separates "which subsample" from either.
"""
from __future__ import annotations

import io
import os
import sys
import time

import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.transform import from_origin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spatial
import terrain as T
from analyze import SES, coef, poisson

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELLS = os.path.join(ROOT, "data/interim/cells_exposure/data_sfgov_org.parquet")
PROD_DEM = os.path.join(ROOT, "data/raw/dem/data_sfgov_org.tif")
DEM_1M = os.path.join(ROOT, "data/raw/dem/sf_window_1m.tif")
OUT = os.path.join(ROOT, "outputs")
ELEV_URL = ("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation"
            "/ImageServer/exportImage")

EPSG = 32610
CELL_M = 100
# Chosen by scanning 500 m offsets for the 6 km window that holds the most
# analysis cells while keeping every slope decile within a quarter degree of
# the citywide value. Covers Twin Peaks, Bernal, Potrero, the Mission and SoMa,
# so it spans flat grid and steep grid rather than one or the other.
WIN_X0, WIN_Y0, WIN_M = 545500.0, 4178500.0, 6000
RESOLUTIONS = [1, 10, 30]
# The ImageServer advertises an 8000 px limit but returns "Error exporting
# image" above 2000 px for a float32 export, the same ceiling `harvest.py` uses.
TILE_PX = 2000


# ------------------------------------------------------------------ DEM ----
def fetch_dem_1m(path=DEM_1M):
    """Tiled 1 m export, same ImageServer pattern as `harvest.fetch_dem`.

    The window origin is pinned to the production 100 m cell lattice so that a
    100 m analysis cell is an exact whole number of 1 m pixels. Without that the
    aggregation would straddle cell boundaries and mix a resolution effect with
    a registration effect.
    """
    if os.path.exists(path):
        return path
    n = WIN_M
    mosaic = np.full((n, n), np.nan, dtype=np.float32)
    y1 = WIN_Y0 + WIN_M
    for r0 in range(0, n, TILE_PX):
        for c0 in range(0, n, TILE_PX):
            r1, c1 = min(r0 + TILE_PX, n), min(c0 + TILE_PX, n)
            bx0, bx1 = WIN_X0 + c0, WIN_X0 + c1
            by1, by0 = y1 - r0, y1 - r1
            params = {"bbox": f"{bx0},{by0},{bx1},{by1}", "bboxSR": EPSG,
                      "size": f"{c1-c0},{r1-r0}", "imageSR": EPSG, "format": "tiff",
                      "pixelType": "F32", "interpolation": "RSP_BilinearInterpolation",
                      "noDataInterpretation": "esriNoDataMatchAny", "f": "image"}
            for _ in range(4):
                try:
                    resp = requests.get(ELEV_URL, params=params, timeout=600)
                    if resp.status_code == 200 and resp.content[:2] in (b"II", b"MM"):
                        with rasterio.open(io.BytesIO(resp.content)) as s:
                            mosaic[r0:r1, c0:c1] = s.read(1)[: r1 - r0, : c1 - c0]
                        break
                except Exception:
                    pass
                time.sleep(4)
            print(f"    tile r{r0} c{c0}  valid {np.isfinite(mosaic[r0:r1, c0:c1]).mean():.3f}",
                  flush=True)
    if not np.isfinite(mosaic).any():
        raise RuntimeError("every tile failed; nothing written")
    prof = {"driver": "GTiff", "height": n, "width": n, "count": 1, "dtype": "float32",
            "crs": f"EPSG:{EPSG}", "transform": from_origin(WIN_X0, y1, 1.0, 1.0),
            "compress": "deflate"}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(mosaic, 1)
    return path


def block_mean(a, f):
    """Coarsen by an integer factor, ignoring NaN."""
    if f == 1:
        return a
    ny, nx = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    b = a[:ny, :nx].reshape(ny // f, f, nx // f, f)
    with np.errstate(invalid="ignore"):
        return np.nanmean(b, axis=(1, 3))


def aggregate_to_cells(field, x0, y1, px, cells):
    """Mean of a fine raster inside each 100 m analysis cell.

    Index arithmetic rather than a reshape because 30 does not divide 100; the
    same routine then handles every resolution identically, which matters more
    than speed here.
    """
    ny, nx = field.shape
    cx = x0 + (np.arange(nx) + 0.5) * px
    cy = y1 - (np.arange(ny) + 0.5) * px
    gx = np.floor((cx - (cells.x.min() - CELL_M / 2)) / CELL_M).astype(int)
    gy = np.floor(((cells.y.max() + CELL_M / 2) - cy) / CELL_M).astype(int)
    nxc = gx.max() + 1
    nyc = gy.max() + 1
    idx = gy[:, None] * nxc + gx[None, :]
    ok = np.isfinite(field)
    tot = np.zeros(nyc * nxc)
    cnt = np.zeros(nyc * nxc)
    np.add.at(tot, idx[ok], field[ok])
    np.add.at(cnt, idx[ok], 1.0)
    mean = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)
    ci = (np.floor(((cells.y.max() + CELL_M / 2) - cells.y) / CELL_M).astype(int) * nxc
          + np.floor((cells.x - (cells.x.min() - CELL_M / 2)) / CELL_M).astype(int))
    inb = (ci >= 0) & (ci < mean.size)
    out = np.full(len(cells), np.nan)
    out[inb.values] = mean[ci[inb]]
    return out


# ------------------------------------------------------------- analysis ----
def build_slopes(cells):
    """Return a frame of slope per analysis cell at each pixel size."""
    with rasterio.open(fetch_dem_1m()) as src:
        z1 = src.read(1).astype(np.float32)
        tr = src.transform
    x0, y1 = tr.c, tr.f
    print(f"  1 m DEM {z1.shape}, valid {np.isfinite(z1).mean():.3f}, "
          f"elev {np.nanmin(z1):.1f}-{np.nanmax(z1):.1f} m")

    out = pd.DataFrame({"cell": cells.cell.values})
    for r in RESOLUTIONS:
        z = block_mean(z1, r)
        s = T.slope_degrees(np.nan_to_num(z, nan=np.nanmean(z)), float(r))
        s = np.where(np.isfinite(z), s, np.nan)
        out[f"slope_{r}m"] = aggregate_to_cells(s, x0, y1, float(r), cells)

    # production 10 m product through the identical aggregation
    with rasterio.open(PROD_DEM) as src:
        zp = src.read(1).astype(np.float32)
        trp = src.transform
    valid = np.isfinite(zp) & (zp > -5) & (zp < 5000)
    sp = np.where(valid, T.slope_degrees(zp, abs(trp.a)), np.nan)
    out["slope_prod10m"] = aggregate_to_cells(sp, trp.c, trp.f, abs(trp.a), cells)
    return out


def fit(df, col):
    res, names = poisson(df, "n_total", [col] + SES, bg_fe=True)
    c = coef(res, names, col)
    c["n"] = int(len(df))
    c["events"] = int(df.n_total.sum())
    return c


def bootstrap_diff(win, cols, reps=300, seed=11):
    """Cluster bootstrap of the *difference* between per-degree coefficients.

    The four estimates come from the same cells, so their sampling errors are
    almost perfectly correlated and comparing the four marginal confidence
    intervals would badly overstate the uncertainty in the gap between them.
    Block groups are resampled with replacement -- the same unit the primary
    standard errors cluster on -- and all four models are refitted inside each
    replicate, so the difference is measured on a common draw.
    """
    rng = np.random.default_rng(seed)
    groups = win.GEOID.unique()
    idx = {g: np.flatnonzero(win.GEOID.values == g) for g in groups}
    out = []
    for _ in range(reps):
        draw = rng.choice(groups, len(groups), replace=True)
        parts = [idx[g] for g in draw]
        b = win.iloc[np.concatenate(parts)].copy()
        # A block group drawn twice must become two block groups, or the
        # absorbed fixed effect would pool two copies of the same cells and
        # understate the very variation being resampled.
        b["GEOID"] = np.repeat(np.arange(len(parts)), [len(p) for p in parts])
        try:
            row = {c: fit(b, c)["beta"] for c in cols}
        except Exception:
            continue
        out.append(row)
    d = pd.DataFrame(out)
    if d.empty:
        return {}
    res = {}
    for c in cols:
        if c == "slope_10m":
            continue
        gap = 100 * (np.exp(d[c]) - np.exp(d["slope_10m"]))
        res[c] = {"diff_pct_pts_vs_10m": float(gap.mean()),
                  "lo": float(np.percentile(gap, 2.5)),
                  "hi": float(np.percentile(gap, 97.5)),
                  "share_same_sign_as_point": float((gap < 0).mean()),
                  "reps": int(len(d))}
    return res


def main():
    cells = spatial.prep(pd.read_parquet(CELLS))
    win = cells[(cells.x >= WIN_X0) & (cells.x < WIN_X0 + WIN_M)
                & (cells.y >= WIN_Y0) & (cells.y < WIN_Y0 + WIN_M)].copy()
    print(f"window: {len(win):,} of {len(cells):,} analysis cells, "
          f"{int(win.n_total.sum()):,} incidents")

    sl = build_slopes(win)
    win = win.merge(sl, on="cell", how="left")
    cols = [f"slope_{r}m" for r in RESOLUTIONS] + ["slope_prod10m"]
    win = win.dropna(subset=cols)
    # A block group needs three cells to contribute within-group terrain
    # contrast, the same rule the primary path applies.
    win = win[win.groupby("GEOID")["GEOID"].transform("size") >= 3].reset_index(drop=True)
    print(f"matched on all resolutions: {len(win):,} cells, "
          f"{int(win.n_total.sum()):,} incidents, {win.GEOID.nunique()} block groups\n")

    rows = []
    ref = win["slope_10m"].to_numpy()
    for col in cols:
        v = win[col].to_numpy()
        c = fit(win, col)
        A = np.column_stack([np.ones_like(ref), ref])
        b, *_ = np.linalg.lstsq(A, v, rcond=None)
        r2 = 1 - ((v - A @ b) ** 2).sum() / ((v - v.mean()) ** 2).sum()
        rows.append({
            "slope_source": col,
            "dem_res_m": {"slope_1m": 1, "slope_10m": 10, "slope_30m": 30,
                          "slope_prod10m": 10}[col],
            "product": "3DEP 1m coarsened" if col != "slope_prod10m" else "3DEP 10m as harvested",
            "mean_deg": v.mean(), "sd_deg": v.std(ddof=1),
            "p10_deg": np.percentile(v, 10), "p50_deg": np.percentile(v, 50),
            "p90_deg": np.percentile(v, 90), "max_deg": v.max(),
            "vs_10m_intercept": b[0], "vs_10m_slope": b[1], "vs_10m_r2": r2,
            "corr_with_10m": np.corrcoef(v, ref)[0, 1],
            "beta_per_deg": c["beta"], "se": c["se"],
            "pct_per_deg": c["pct"], "lo": c["lo"], "hi": c["hi"], "z": c["z"],
            "n_cells": c["n"], "events": c["events"],
        })

    # Same model on a standardised regressor. If the per-degree coefficients
    # differ only because the units differ, the per-SD versions coincide, and
    # that is the cleanest way to say whether the *finding* is resolution
    # dependent or only its wording is.
    for row, col in zip(rows, cols):
        z = (win[col] - win[col].mean()) / win[col].std()
        w = win.assign(_z=z)
        cz = fit(w, "_z")
        row["pct_per_sd"] = cz["pct"]
        row["sd_lo"] = cz["lo"]
        row["sd_hi"] = cz["hi"]

    # How much of the window-versus-city difference is the subsample rather
    # than the DEM? Fit the published specification on the full city and on the
    # window using the same production raster.
    city = fit(cells, "slope_deg")
    rows.append({"slope_source": "slope_deg (published, whole city)", "dem_res_m": 10,
                 "product": "3DEP 10m as harvested",
                 "mean_deg": cells.slope_deg.mean(), "sd_deg": cells.slope_deg.std(ddof=1),
                 "p10_deg": np.percentile(cells.slope_deg, 10),
                 "p50_deg": np.percentile(cells.slope_deg, 50),
                 "p90_deg": np.percentile(cells.slope_deg, 90),
                 "max_deg": cells.slope_deg.max(),
                 "beta_per_deg": city["beta"], "se": city["se"], "pct_per_deg": city["pct"],
                 "lo": city["lo"], "hi": city["hi"], "z": city["z"],
                 "n_cells": city["n"], "events": city["events"]})

    boot = bootstrap_diff(win, cols)
    for row in rows:
        b = boot.get(row["slope_source"])
        if b:
            row.update({"boot_diff_vs_10m_pct_pts": b["diff_pct_pts_vs_10m"],
                        "boot_diff_lo": b["lo"], "boot_diff_hi": b["hi"],
                        "boot_reps": b["reps"]})

    res = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    res.to_csv(os.path.join(OUT, "dem_resolution_sensitivity.csv"), index=False)
    pd.set_option("display.width", 220)
    print(res[["slope_source", "mean_deg", "sd_deg", "p90_deg", "vs_10m_slope",
               "vs_10m_r2", "pct_per_deg", "lo", "hi", "pct_per_sd",
               "boot_diff_vs_10m_pct_pts", "boot_diff_lo", "boot_diff_hi"]]
          .round(3).to_string(index=False))
    return res


if __name__ == "__main__":
    main()
