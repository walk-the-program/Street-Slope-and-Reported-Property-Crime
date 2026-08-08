# Street slope and reported property crime in nine United States cities

[![DOI](https://zenodo.org/badge/1324652739.svg)](https://doi.org/10.5281/zenodo.21855376)

Replication materials for *Street slope and reported property crime in nine United
States cities: terrain measurement, target exposure, and tests of candidate
mechanisms.*

Across nine American cities, recorded property crime is negatively associated with
street slope within census block groups — roughly **−6.9% per degree** in the four
cities where terrain is well measured (95% CI [−9.51, −4.21]). The magnitude does not
transport: the prediction interval for a new city runs from −13.7% to +0.5%. None of
the four candidate mechanisms tested here fully accounts for the association, and the
paper declines to offer a fifth it cannot test.

---

## What is here

```
src/                analysis pipeline, ~8,000 lines of Python
outputs/            every result table (48 CSVs), the five figures, the
                    classifier validation set and its confusion matrices
data/interim/       the aggregated analytic panels and the harvest manifests
AI_DISCLOSURE.md    what is and is not automated, and how it was validated
requirements.txt    pinned versions
```

This is the replication package only — code, the panels it runs on, and the
tables it produces. The manuscript, its supplement and the analysis plan are not
here; they accompany the submission.

Every number in the paper traces to a named CSV in `outputs/`. Nothing is
hand-entered.

## Reproducing the results

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/regen_all.py
```

`regen_all.py` rebuilds every table and figure in dependency order from the panels in
`data/interim/cells_exposure/`, writes the submission TIFFs, and prints the headline
numbers. It needs no network access.

Verified: snapshotting all 48 output tables, re-running, and diffing gives
**byte-for-byte identical** results — including the bootstrapped ones, since the
paired bootstrap (seed 17), the spatial block bootstrap (seed 11) and the classifier
relabelling (seed 20260804) all use fixed seeds.

Analyses outside `regen_all.py`, because they need the network or the dated
re-download:

```bash
.venv/bin/python src/harvest_dated.py          # re-fetch 4 cities keeping timestamps
.venv/bin/python src/incident_tests.py         # arson split, time matching, temporal
.venv/bin/python src/classifier_uncertainty.py # label-error propagation
.venv/bin/python src/spatial_bootstrap.py      # 1 km spatial block bootstrap
.venv/bin/python src/target_multicity.py       # footprint denominator
.venv/bin/python src/validate_data.py          # independent data audit
```

## Rebuilding from scratch

```bash
.venv/bin/python src/registry.py        # discover Socrata crime datasets
.venv/bin/python src/harvest_arcgis.py  # discover ArcGIS and CKAN feeds
.venv/bin/python src/harvest.py         # crime, elevation, terrain, census
.venv/bin/python src/exposure.py        # building-footprint denominators
.venv/bin/python src/network.py         # street segments and network measures
```

**This will not reproduce the published numbers, and that is expected.** The crime
feeds are live: departments backfill and reclassify records, the harvest caps each
city at its 600,000 most recent incidents so the window slides forward on every run,
and Pittsburgh's feed is frozen at November 2023 while others run to August 2026. The
panels in `data/interim/cells_exposure/` are the harvested state the paper was written
against, which is why they are committed here rather than left to be re-fetched.

## What is deliberately not in this repository

**Raw incident downloads** (`data/raw/`, ~3.2 GB). These hold point-level coordinates.
The paper's ethics statement commits to distributing retrieval scripts and the
aggregated analytic units rather than republishing raw point records, and some
municipal portals restrict redistribution. They are fully re-derivable from
`data/interim/registry.csv` and `registry_arcgis.csv`, which record the portal, the
dataset id, the coordinate and date fields, and the description fields used for every
city.

**Elevation rasters** and the HTTP cache. Both are re-fetched from public endpoints by
`src/harvest.py`.

**Superseded panels.** `data/interim/cells/` predates the building-footprint exposure
rebuild; `cells_exposure/` is the version every reported result uses.

## Data sources

All public, none requiring an API key or credential.

| Source | Use |
|---|---|
| Municipal open-data portals (Socrata, ArcGIS, CKAN) | Incident-level property crime, 2018 onward |
| USGS 3D Elevation Program | 10 m bare-earth elevation, identical resolution for every city |
| US Census ACS block-group summary files | Income, home value, tenure, vacancy, population, housing units |
| US Census TIGER/Line | Block-group and county boundaries |
| Microsoft Building Footprints | Exposure apportionment and target counts |
| OpenStreetMap via osmnx | Street segments and network measures |
| SFMTA on-street parking census | Direct target denominator, San Francisco |
| San Francisco address points and land use | Front doors and residential units |

## Method in one paragraph

The unit of analysis is a 100 m grid cell, built by block-averaging a 10 m elevation
raster; slope is computed on the fine raster with Horn's method *before* being averaged
up. Models are Poisson pseudo-maximum-likelihood with a log exposure offset and
absorbed census block-group fixed effects, with standard errors clustered on block
group. Exposure is housing units plus population, apportioned within block group by
residential building footprint area rather than land area. Identification is therefore
*within neighbourhood*: everything constant across a block group is differenced away.
That does not make slope as-good-as-random inside one, and the paper is explicit that
what it reports is a conditional association rather than a demonstration of deterrence.

## Citing this archive

Archived on Zenodo. Cite the version that matches what you ran:

- **Version 1.0.0** — the state the manuscript was written against:
  https://doi.org/10.5281/zenodo.21855377
- **All versions** — always resolves to the latest release:
  https://doi.org/10.5281/zenodo.21855376

## Data availability statement

All source data are publicly available from the providers listed above. The aggregated
analytic panels, the complete analysis code, all result tables, and the classifier validation
set are in this repository. Raw
point-level incident downloads and elevation rasters are not redistributed, for the
reasons given above, and are re-derivable from the manifests in `data/interim/`.

## Errors and corrections

Thirteen deviations from the analysis plan are itemised in the deviations log
accompanying the manuscript, including four silent classifier defects, a post-hoc
terrain threshold demoted to a sensitivity analysis, a pooling method that was
replaced, and one analysis retracted and re-run after its models turned out not to
have converged.

They are recorded because the pattern matters: in every case, plausible aggregates
and stable regressions survived a real defect. That is also why this repository
carries `src/validate_data.py` and `src/ppml_diagnostics.py` — the analysis checks
itself rather than asking to be trusted. See `AI_DISCLOSURE.md`.

## Licence

Code is released under the MIT Licence. Derived data tables are released under
CC BY 4.0. Source data remain under the terms of their original providers.
