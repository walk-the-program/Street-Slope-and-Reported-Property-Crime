# DEM resolution sensitivity of the per-degree slope coefficient

Numbers in `outputs/dem_resolution_sensitivity.csv`, code in `src/dem_resolution.py`.

## Design

A 1 m 3DEP DEM was fetched for a 6 km window of San Francisco
(EPSG:32610, origin 545500 E / 4178500 N, 36 km², nine ImageServer tiles, 100%
coverage, elevation −1.6 to 279.1 m) and **coarsened to 10 m and 30 m by block
mean from that same array**, so vintage, source and interpolation are held fixed
and only pixel size varies. Slope was computed at each pixel size with the
production `terrain.slope_degrees` and aggregated to the 100 m analysis cells
exactly as the pipeline does it — mean of the fine-resolution slopes inside the
cell. The window origin is pinned to the production 100 m lattice so a cell is a
whole number of pixels at every resolution.

The headline model was refitted with `analyze.poisson(df, "n_total",
[slope] + SES, bg_fe=True)` on `data/interim/cells_exposure/data_sfgov_org.parquet`
prepped by `spatial.prep` (the path that produced `outputs/slope_per_degree.csv`).
The estimator was not reimplemented and slope enters in raw degrees.

Two controls:

* The window was selected to match the citywide slope distribution — every
  decile within 0.22°, mean 5.76° against 5.84° citywide. 2,158 matched cells,
  75,798 incidents, 210 block groups.
* The **production 10 m raster** was carried through the identical aggregation,
  which separates "which product" from "which pixel size".

## Result

| slope source | mean° | sd° | vs 10 m: intercept, slope, R² | % per degree | 95% CI | % per SD |
|---|---:|---:|---|---:|---|---:|
| 1 m (3DEP, coarsened from) | 6.96 | 4.66 | +1.33, 0.990, 0.992 | **−11.09** | [−13.89, −8.20] | −42.1 |
| 10 m (coarsened from 1 m) | 5.68 | 4.68 | — | **−9.69** | [−12.33, −6.96] | −37.9 |
| 30 m (coarsened from 1 m) | 5.19 | 4.53 | −0.26, 0.960, 0.984 | **−8.33** | [−11.29, −5.28] | −32.6 |
| 10 m as harvested (production) | 5.76 | 4.68 | +0.09, 0.998, 0.996 | −9.60 | [−12.20, −6.92] | −37.7 |
| published, whole city | 5.84 | 4.54 | — | −7.02 | [−8.94, −5.06] | — |

The four window estimates come from the same cells, so their marginal intervals
are far too wide for comparing them to each other. A cluster bootstrap over
block groups (300 replicates, duplicated groups relabelled so the absorbed
fixed effect does not pool them) gives the gaps directly:

| comparison | difference | 95% CI |
|---|---:|---|
| 1 m vs 10 m | **−1.41 pct pts** | [−2.14, −0.62] |
| 30 m vs 10 m | **+1.38 pct pts** | [+0.44, +2.44] |
| production 10 m vs derived 10 m | +0.08 pct pts | [−0.64, +0.87] |

## What this says

**1. Coarsening does flatten the terrain, as expected.** Mean slope falls from
6.96° at 1 m to 5.68° at 10 m to 5.19° at 30 m. Horn's kernel differences across
three pixels, so a wider pixel averages over more ground.

**2. But the flattening is almost purely an additive offset, not a rescaling.**
Regressing slope-at-1 m on slope-at-10 m across matched cells gives
`slope_1m = 1.33 + 0.990 × slope_10m`, R² = 0.992; at 30 m the coefficient is
0.960. A degree of variation means very nearly the same physical thing at every
resolution — what changes is the level, and a level shift is absorbed by the
block-group fixed effects. So the mechanical units story a reviewer will
propose ("coarse pixels shrink the denominator, so the per-degree coefficient is
inflated") **does not describe what happens here**.

**3. The coefficient nevertheless moves with resolution, monotonically, and in
the opposite direction to that worry.** Finer DEM gives a *stronger* effect:
−11.09% at 1 m, −9.69% at 10 m, −8.33% at 30 m. The per-SD column moves the same
way (−42.1 / −37.9 / −32.6), which rules out units as the explanation, because
the per-SD estimate is unit-free by construction. What is left is classical
attenuation: a coarser raster is a noisier proxy for the gradient a person
actually walks, and measurement error in the regressor pulls the coefficient
toward zero. Going from 10 m to 30 m attenuates the effect by 14% of itself;
going from 10 m to 1 m strengthens it by 15%.

**4. It is pixel size, not the product.** The production 10 m raster and the
10 m array derived from the 1 m fetch give −9.60% and −9.69%, a gap of 0.08 pct
pts with a bootstrap interval straddling zero. Whatever is driving the
resolution pattern is the grid, not 3DEP's 1/3-arc-second product.

**5. The window is not the city.** On the production raster, the same
specification gives −9.60% inside the window and −7.02% citywide. That 2.6 pct
pt gap is a subsample effect and is larger than the entire resolution effect.
All resolution comparisons above are within-window and therefore unaffected by
it, but it is a reminder that the published number is a citywide average and the
resolution correction cannot simply be added to it.

## Is the headline robust?

**Yes in substance, with a caveat that should be stated rather than buried.**

* Sign, significance and order of magnitude are unchanged across a 30× range of
  pixel size. Nothing here threatens the finding.
* The direction of the resolution dependence is favourable. A referee raising
  "your per-degree number is an artefact of coarse pixels" is raising a concern
  that runs the wrong way: 10 m **under**states the effect relative to 1 m. The
  published −6.2% is conservative with respect to DEM resolution, not inflated.
* The number is not resolution-free. It moves roughly ±15% of itself between
  1 m and 30 m, and the bootstrap says that movement is real, not noise.

**Recommended wording.** State the resolution in the claim itself — "−6.2% per
degree of street slope measured on 10 m 3DEP" — and add one sentence: *slope is
resolution-dependent; recomputing on 1 m and 30 m DEMs for a matched San
Francisco subsample moves the per-degree coefficient by −15% and +14%
respectively, so the reported figure is conservative relative to finer terrain
data.* Ship `outputs/dem_resolution_sensitivity.csv` as a supplementary table.

## Caveats on this test

* One city, one 6 km window. San Francisco's terrain is unusually steep and its
  lidar unusually good; a flatter city with older lidar could behave
  differently, and the pooled three-city headline has not been re-tested.
* At 1 m a lidar-derived DEM resolves curbs, retaining walls, stair flights and
  residual vegetation artefacts. Some of the extra 1.33° is microtopography a
  pedestrian genuinely climbs and some is noise. Note that pure noise would
  attenuate the coefficient, and the 1 m coefficient is *stronger*, which is
  evidence that the added detail is mostly signal — but it is indirect evidence.
* Only the pooled `n_total` outcome was refitted. Whether the loot-mass ladder's
  *shape* is resolution-sensitive is a separate question and was not tested.
* The window analysis uses `classify_text`, the classifier version audited in
  `outputs/classifier_metrics.md`, not `classify_text_v2`.
