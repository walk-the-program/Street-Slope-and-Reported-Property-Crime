# Supporting information

Companion to `PAPER.md`. Every table below is a CSV in `outputs/`, produced by the scripts
named against it. Nothing here is hand-entered.

---

## S1. STROBE checklist (observational, cross-sectional)

| # | Item | Where |
|---|---|---|
| 1a | Study design in title/abstract | Title, Abstract |
| 1b | Balanced summary | Abstract |
| 2 | Scientific background and rationale | §1 — three mechanisms named but untested by Haberman & Kelsay (2021) |
| 3 | Objectives, prespecified hypotheses | §1; `PREREGISTRATION.md` §2 (H1–H5) |
| 4 | Study design | §3 |
| 5 | Setting, locations, periods | §3; nine US cities, incidents 2018 onward (Baltimore 2022+, Charlotte 2019-11+) |
| 6a | Eligibility criteria | §3 "Inclusion"; `PREREGISTRATION.md` §4 |
| 7 | Variables: outcomes, exposures, confounders, mediators | §3; `src/crime_classes.py`, `src/terrain.py`, `src/network.py` |
| 8 | Data sources and measurement | §3, §7; `SUBMISSION.md` §4 |
| 9 | Bias | §4.6–§4.10; §6 |
| 10 | Study size | Determined by data availability, not chosen — `PREREGISTRATION.md` §8 |
| 11 | Quantitative variable handling | §3; slope modelled in raw degrees, TPI standardised within city |
| 12a | Statistical methods and confounding control | §3 — Poisson PML, absorbed block-group FE, clustered SEs |
| 12b | Subgroup/interaction | §4.3 by crime class |
| 12c | Missing data | §4.7 coverage; exposure fallback flagged, never >0.2% of cells |
| 12d | Sampling strategy | Full population of geocoded incidents, capped at 600k most recent per city |
| 12e | Sensitivity analyses | §4.6 denominator, §4.7 target exposure, §4.8 spatial, §4.9 DEM resolution, §4.10 classifier |
| 13 | Participants / units | §4.1 tables; n per city in `outputs/slope_per_degree_full.csv` |
| 14 | Descriptive data | §4.1 |
| 15 | Outcome data | §4.1, §4.3 |
| 16 | Main results with precision | §4.1, §4.3, §4.5, §4.7 — all with 95% CIs |
| 17 | Other analyses | §4.2, §4.4 |
| 18 | Key results | §5 |
| 19 | Limitations | §6; `PREREGISTRATION.md` addendum D1–D11 |
| 20 | Interpretation | §5 |
| 21 | Generalisability | §4.1 — heterogeneity explicit, transportability disclaimed |
| 22 | Funding | None; §7 |
| — | Ethics and responsible use | Manuscript, *Ethics and responsible use* |
| — | Software and AI tooling disclosure | Manuscript, *Software, automation and AI tooling* |

## S2. Result tables

**Headline**
| Table | Contents | Produced by |
|---|---|---|
| `slope_per_degree_full.csv` | Per-degree slope effect, all 9 cities, with floor flag | `analyze.py` + panel script |
| `robustness_drop_mass3.csv` | Headline excluding the contaminated loot rung | §4.10 |
| `out_of_sample.csv` | Pittsburgh, Baltimore, Charlotte — cities that post-date variable selection | — |

**Mechanism tests**
| Table | Contents |
|---|---|
| `h1_slope_floor.csv` | Primary test: theft vs no-loot, paired cluster bootstrap, four cities |
| `h1_slope.csv`, `h1_noloot.csv` | Same test on wider panels and on relative height |
| `h2_lootmass.csv`, `loot_ladder_slope.csv` | Loot-mass ladder |
| `h3_mediation_multicity.csv` | Network mediation, four cities |
| `h4_mvt.csv` | Motor vehicle theft ranking |
| `h5_placebo.csv` | Sub-floor placebo cities |
| `asymmetry_by_class.csv`, `asymmetry_trend.csv` | Directional round-trip cost model (§4.4) |

**Synthesis and review-response analyses**
| Table | Contents |
|---|---|
| `meta_pools.csv` | Fixed-effect vs random-effects pools, τ², I² with Q-profile interval, prediction interval |
| `meta_regression.csv`, `meta_regression_fit.csv` | Effect on within-city slope SD — replaces the 3° threshold |
| `meta_leave_one_out.csv` | Pool refit without each city in turn |
| `ppml_diagnostics.csv` | Convergence, iterations, separated observations, singleton and all-zero block groups, sample reduction |
| `h1_vandalism_only.csv` | No-loot contrast with arson removed; arson estimated alone where n permits |
| `h1_time_matched.csv` | No-loot contrast reweighted to theft's hour × day-of-week distribution |
| `h1_equivalence.csv` | TOST against a margin of half the headline effect |
| `noloot_composition.csv` | Vandalism / arson split of the control group, by city |
| `temporal_split.csv` | Pre- and post-March-2020 estimates |
| `classifier_uncertainty.csv`, `classifier_uncertainty_pool.csv` | Label error propagated to coefficients by 200 relabelling draws |
| `target_multicity.csv`, `target_multicity_pool.csv`, `target_multicity_failed.csv` | Footprint target denominator; converged in 4 of 9 cities, failures recorded separately |
| `spatial_block_bootstrap.csv` | 1 km spatial block bootstrap vs block-group clustering |

**Robustness and measurement**
| Table | Contents |
|---|---|
| `spatial_diagnostics.csv` | Moran's I: all links, cross-block-group, post-filter — 14 models |
| `spatial_models.csv` | 7 specifications × 16 models: cluster, Conley at 3 bandwidths, ESF, SEM, naive |
| `target_exposure_denominator.csv` | Direct test: do steep streets hold fewer targets? (No.) |
| `target_exposure_tests.csv` | 96 rows: before/after × 2 control sets × 3 sample variants |
| `target_exposure_coverage.csv` | Parking-census and address coverage audit |
| `exposure_diagnostics.csv` | Building-footprint apportionment, 6 cities |
| `dem_resolution_sensitivity.csv` | 1 m / 10 m / 30 m from a common lidar source |
| `classifier_validation.csv` | 511 hand-coded offense strings |
| `classifier_metrics.md` | Confusion matrices, per-class precision/recall, failure patterns |
| `classifier_fix_impact.csv` | Class counts before and after the classifier repair |

**Superseded, retained for transparency**
`city_estimates.csv`, `stage_two.csv`, `slope_vs_tpi.csv`, `results_*.csv`, `noloot_control.csv`
— from the exploratory relative-height phase described in `DIRECTION.md`.

## S3. Specification history

This project ran an extended exploratory phase before the analysis plan was written, and the
treatment variable changed afterwards. Rather than present a curated path, the full sequence
is recorded:

1. **Relative height (TPI), San Francisco, 100 m cells** — `PILOT_RESULTS.md`
2. **Eleven-city panel, area-apportioned exposure** — found heterogeneous and contaminated;
   the diagnostic that killed it is `outputs/14_signal_diagnostic.png`
3. **Two-stage decomposition** on the elevation–income correlation — `stage_two.csv`
4. **Directional round-trip cost model** — our own theory, predicting sign reversal with loot
   mass; unsupported (`asymmetry_trend.csv`)
5. **Slope** identified as the robust predictor; analysis plan deviations recorded in
   `PREREGISTRATION.md` D1–D11
6. **Confirmatory phase** — the results in `PAPER.md` §4
7. **Revision in response to external review** — the fixed-effect pool replaced by a
   random-effects synthesis with a prediction interval; the 3° threshold demoted from
   sample rule to sensitivity analysis and replaced by a continuous moderator model;
   the no-loot contrast re-run without arson and with time matching, and evaluated by
   equivalence test rather than by a null; the target denominator extended to nine
   cities; classification error propagated to the coefficients; spatial block
   bootstrap added; estimator diagnostics reported; causal language removed
   throughout; two citation errors corrected and the missed literature added

Steps 1–4 are exploratory and every p-value in them is descriptive. Step 6 follows the
registered rules, with the one post-hoc inclusion criterion (the gradient floor) disclosed
and separately validated out-of-sample.

## S4. Figures

All manuscript figures are generated by `src/figures_paper.py` against a single shared
style module, `src/vizstyle.py`, which fixes the palette, the city-name mapping, legend
placement and label de-collision in one place. They were previously written one at a
time and had drifted apart: three different teals across figures, raw database slugs
where city names belong (`montgomerycountymd`), legends floating inside the plot body,
and one axis labelled "per +1 SD" on per-degree data.

The palette is a two-slot categorical set, deep petrol `#0d7d9e` against burnt rust
`#c04a1e`. It was chosen for looks and then validated rather than trusted: worst-pair
CVD ΔE 17.9 (protan), normal-vision ΔE 26.3, both hues inside the lightness band, above
the chroma floor, and clear of 3:1 contrast against the surface. Several more muted
candidates were rejected because desaturating a blue far enough to look editorial drops
it under the chroma floor, where it starts reading as grey. Two series are never
distinguished by colour alone: marker shape carries the same distinction, so the figures
survive greyscale printing.

Figures are set in Arial at 8–9.5 pt and exported at 300 dpi, within PLOS's stated
limits (Arial, Times or Symbol only, 8–12 pt, 300–600 dpi, 789–2250 px wide, ≤2625 px
tall, RGB, ≤10 MB). `src/make_plos_figs.py` writes the submission TIFFs to
`outputs/plos_figs/Fig1.tif`–`Fig5.tif` in citation order and fails loudly if any
figure breaches a limit; the loot-ladder figure had to be narrowed from 7.66 in to
7.07 in to pass.

Seventeen superseded figures from the exploratory phases are retained in
`outputs/archive/` rather than deleted, so the abandoned analyses in §S3 remain
inspectable.

## S5. Reproduction

```bash
python3 -m venv .venv && .venv/bin/pip install rasterio geopandas pyarrow osmnx libpysal esda spreg matplotlib statsmodels
.venv/bin/python src/registry.py        # discover crime datasets
.venv/bin/python src/harvest.py         # crime + DEM + terrain + census, per city
.venv/bin/python src/exposure.py        # building-footprint denominators
.venv/bin/python src/network.py         # street segments and network measures
.venv/bin/python src/run_confirmatory.py
```

No API keys. All sources public. Raw downloads are not redistributed but are fully
re-derivable from `data/interim/registry.csv` and `registry_arcgis.csv`.
