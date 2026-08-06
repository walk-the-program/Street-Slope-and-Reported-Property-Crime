# Tooling and AI disclosure

This file covers how the code in this repository was produced and what is and is
not automated inside the pipeline. It is here so that anyone auditing the
analysis knows what to check and where the failure modes are.

## Nothing in the analysis is a model

Two components could plausibly be mistaken for machine learning. Neither is.

**The offense classifier** (`src/crime_classes.py`) is a deterministic, ordered
cascade of regular expressions over the concatenated offense description fields
of each city's feed, with a fixed loot-mass ladder attached to its classes. It
does not learn from the data it labels. The same input string always produces the
same class. The complete rule set is in this repository, along with the 511
hand-coded validation strings (`outputs/classifier_validation.csv`), the
confusion matrices and the documented failure patterns
(`outputs/classifier_metrics.md`). The hand coding was done by the author.

**The derived exposure variables** — building-footprint apportionment, on-street
parking apportionment, front-door counts, street network measures, and every
terrain surface — are deterministic geometry over public inputs. No inference
step, no fitted model.

The label masses on the loot ladder are **assumptions attached to offense
categories, not measurements**. No source feed reports what was actually taken.
Any analysis resting on the ladder is exploratory for that reason.

## Generative AI was used to write this code

Anthropic's Claude was used as a coding assistant across this pipeline: writing
and revising the harvesting, terrain, exposure, estimation, synthesis, robustness
and figure code, and checking arguments and searching for objections.

It was **not** used to label any incident, to select any specification on the
basis of results, or to generate any reported number. Every figure in every table
comes from code executing over the data, and the analytic decisions are the
author's.

Both directions of that assistance are visible in the record. Several defects
were found through it, and several were introduced by it — including four silent
classifier defects and one analysis that had to be retracted and re-run after its
models turned out never to have converged. All are itemised in the deviations log
that accompanies the manuscript.

## How the outputs were validated

Because the tooling above can produce plausible-looking output from broken code,
the repository carries its own checks rather than asking for trust:

- `src/validate_data.py` — an independent audit that re-derives everything it
  checks from the panels and incident files, reading no result table. Panel
  integrity, coordinate sanity, time windows, class distributions, and the
  geocoding-sink filter. It also compares the stored panels against a second,
  independent re-download of four cities: correlation 1.000000.
- `src/ppml_diagnostics.py` — convergence, iteration counts, separated
  observations, singleton and all-zero fixed-effect groups, and how far the
  estimation sample was reduced from the raw cell table.
- `src/regen_all.py` — rebuilds every table and figure in dependency order.
  Snapshotting all 48 outputs, re-running and diffing gives byte-for-byte
  identical results; the three bootstrapped analyses use fixed seeds.

No records were transmitted to a third-party service for labelling or inference.
All data came from public government endpoints and every model fit ran locally.
