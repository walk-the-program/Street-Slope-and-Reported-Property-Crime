# Submission checklist — PLOS ONE

Working document. Tracks what PLOS ONE requires against what exists.

PLOS ONE's criteria are **technical soundness** and **conclusions supported by the data** —
not novelty or perceived impact. That shapes what matters below: rigour and completeness
carry the weight, and the fact that this paper's headline is largely a replication of
Haberman & Kelsay (2021) is not a barrier provided we say so plainly.

---

## 1. Publication criteria

| Criterion | Status | Note |
|---|---|---|
| Original primary research | ✅ | Nine-city analysis, new mechanism tests |
| Results not previously published | ✅ | |
| Experiments/statistics performed to a high technical standard | ✅ | Spatial dependence, target-level denominators, classifier validation against hand-coded holdout, DEM resolution, jurisdiction-padding, and four-city segment mediation all completed |
| Conclusions presented appropriately | ✅ | Revised after external review: causal language removed throughout, the post-hoc terrain threshold replaced by a continuous moderator model, the pool made random-effects with a prediction interval, and the no-loot test bounded by an equivalence margin rather than a null. Four candidate mechanisms tested, none accounts for the association, no fifth story asserted |
| Data fully available without restriction | ✅ | All sources public; see §4 |
| Standard English | ✅ | |
| Ethics | ✅ | No human subjects; aggregate public incident data only. No IRB required — state this explicitly in the cover letter. Manuscript now carries an *Ethics and responsible use* section covering disclosure risk, redistribution policy and interpretive harm |
| AI and tooling disclosure | ✅ | Manuscript carries a *Software, automation and AI tooling* section stating that the classifier is deterministic and rule-based, and that generative AI was used for code and drafting but not for labelling, specification selection or any reported number |

## 2. Required statements

**Data availability.** To be published as a versioned archive (Zenodo or OSF) with a DOI,
containing: all `src/` code, `outputs/` results tables and figures, the pre-registration and
its addendum, and the harvest manifests (`data/interim/registry.csv`,
`registry_arcgis.csv`) that make the crime pulls reproducible. Raw crime downloads and DEM
tiles are **not** redistributed — they are large, they are re-derivable from the manifests,
and some municipal portals restrict redistribution. State this reasoning in the statement
rather than only asserting availability.

**Funding.** None. Declare.

**Competing interests.** None. Declare.

**Author contributions.** CRediT taxonomy — complete at submission.

**Ethics.** No human subjects research. All crime data are aggregate, publicly released
incident records with coordinates already degraded for privacy by the publishing agencies.

## 3. Open items before submission

### Blocking

**One item remains: registration.** Everything else on this list is complete.

- [x] Reposition against Haberman & Kelsay (2021) — done; the paper now answers the three
      mechanisms they name and leave untested
- [x] Withdraw the "constant effect" claim; report I² = 0.86 with the pooled estimate
- [x] Out-of-sample cities (Pittsburgh, Baltimore, Charlotte)
- [x] Spatial autocorrelation: Moran's I (all links, cross-block-group, post-filter),
      Conley HAC at three bandwidths, eigenvector spatial filtering, Gaussian SEM.
      Point estimates stable across all specifications. SEs do **not** widen, because
      cluster-robust errors are already 4.7–13.7× naive and block groups span the dependence.
      Caveat retained: Cincinnati's residual Moran's I = +0.34 is not removable by filtering.
      **Deviation to disclose:** no CAR/BYM sampler in the environment; ESF used as substitute
- [x] **Target-availability test** — done, and it refutes the objection. Replacing the
      housing denominator with on-street parking capacity and front-door counts roughly
      *doubles* the slope effect rather than shrinking it. The conventional denominator was
      attenuating the effect, not manufacturing it.
- [x] **Segment-level analysis in four cities.** San Francisco, Seattle, Cincinnati and
      Pittsburgh. Mediation now pooled across all four: 24% attenuation, short of the
      pre-registered 40% threshold, reported as partial rather than null.
- [x] **Classifier validation.** Done against a hand-coded holdout: 85.7% string-level and
      93.7% incident-weighted as deployed. The control class (NO_LOOT) is clean —
      precision 0.956, recall 1.000. Two bugs found and fixed, requiring a full panel
      rebuild. The headline survives dropping the one contaminated class
      (−6.61% → −6.47%). Loot-ladder compression in NIBRS cities is disclosed as a
      limitation on H2.
- [x] **DEM resolution sensitivity.** Done at 1/10/30 m from a common lidar source. The
      per-degree coefficient is resolution-dependent (~14% larger at 1 m than 10 m); sign,
      significance and ordering are unaffected. Reported as a caveat on cross-study
      comparison, §4.9.
- [ ] **Register the pre-registration** on OSF with a timestamp and DOI. Until then the
      document has no external verification and should not be described as pre-registered
      in the manuscript — describe it as an analysis plan written before the confirmatory
      dataset existed, and let the registration date speak once it exists.

### Worth doing before submission, not blocking

- [x] **Los Angeles recovered.** Root cause fixed in `registry.py` (description columns are
      now ranked, not taken in dataset order). 387,457 classified property incidents with all
      classes populated. Two further classifier gaps closed along the way; impact on the
      existing panel verified as nil before adopting them.
- [~] **Haberman & Kelsay (2021), JQC 37:625–645.** Units confirmed as percent grade and the
      conversion redone properly (−7.72%/degree, not the −7.9% linear shortcut). **Full text
      still not obtained** — Springer paywalled, repository 403. The manuscript now states
      explicitly that the effect size and units come from the abstract and secondary sources
      and must be verified against the original. Needs institutional access or an ILL
      request.

### Non-blocking but expected

- [x] STROBE checklist — `SUPPLEMENT.md` §S1
- [x] Figures regenerated at 300 dpi (PNG). TIFF/EPS conversion still needed at submission
- [x] Supporting information: every result table indexed in `SUPPLEMENT.md` §S2
- [x] Specification history — `SUPPLEMENT.md` §S3, recording all six phases including the
      four abandoned ones, so the forking paths are visible rather than inferred

## 4. Data sources, for the availability statement

| Source | Access | Licence |
|---|---|---|
| USGS 3DEP elevation | `elevation.nationalmap.gov` ImageServer | Public domain |
| Municipal crime portals | Socrata (`data.*.gov`) and ArcGIS Feature Services | Open, varies by city |
| US Census ACS 5-year | `www2.census.gov` summary files | Public domain |
| US Census TIGER/cartographic boundaries | `www2.census.gov` | Public domain |
| OpenStreetMap | via `osmnx` | ODbL — attribution required |
| Microsoft Building Footprints | Azure open data | ODbL |

No API keys are required for any source, which is worth stating: it means a reviewer can
reproduce the pipeline end to end without credentials.

## 5. Reviewer objections to pre-empt in the cover letter

1. **"This replicates Haberman & Kelsay."** Yes, partly, and we say so in the abstract. The
   contribution is generalisation from robbery to property crime across nine cities plus the
   first test of the three mechanisms they proposed.
2. **"Your effect is a denominator artifact."** The most serious objection, and now tested
   head-on in §4.7 with target-level exposure. Counting actual parking spaces and front
   doors *strengthens* the effect. §4.6 separately shows the theft/no-loot contrast survives
   a denominator change that halves the level.
3. **"Three or four cities is not a panel."** Nine cities enter; four clear the gradient
   floor. The floor is justified, pre-specified in analogous form, and confirmed
   out-of-sample by two cities that arrived after it was set.
6. **"Your pooled estimate hides heterogeneity."** Stated explicitly: I² = 0.86, rising to
   0.485 even under spatial filtering. We report the pooled figure with its heterogeneity
   attached and warn against treating it as transportable.
4. **"You changed your treatment variable mid-study."** Disclosed in the pre-registration
   addendum (D1) and labelled exploratory in the manuscript.
5. **"Slope is confounded with street function."** Addressed by the network mediators in
   §4.5, which do not attenuate it.
7. **"Your crime classes are regex guesses."** Validated against a hand-coded holdout
   (§4.9), with the control class at recall 1.000 and the headline shown robust to dropping
   the one class with meaningful contamination.
