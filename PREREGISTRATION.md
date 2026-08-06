# Pre-registration — *Nothing to Carry*

**Topography and property crime: testing the offender-effort mechanism**

Written 2026-08-04, **before** the confirmatory dataset (street segments, building-based
exposure, expanded city panel) exists. Analyses run prior to this date are labelled
EXPLORATORY throughout and are reported as such. This document fixes the confirmatory
tests, the inclusion rules, and the decision criteria in advance.

Intended registry: OSF. Format follows AsPredicted's nine questions, expanded.

---

## 1. Background and what is already known

Two published studies report that property crime is lower at higher elevation:

- Breetzke (2012), *Applied Geography* 34:66–75. Tshwane, South Africa. Burglary 2003–2006.
  Higher altitude → lower burglary risk. **Slope had no effect.**
- Kim & Wo (2023), *Journal of Urban Affairs* 45(6):1120–1144. San Francisco street segments.
  Elevation *differences within the surrounding ¼ mile* reduced crime risk more than a
  segment's own elevation or slope. Network betweenness increased risk.

Both attribute the association to **offender effort** — climbing costs energy, so offenders
substitute toward flatter targets — and **neither tests that attribution.** No multi-city
study exists. No study in this literature has attempted to discriminate between candidate
mechanisms.

## 2. Hypotheses

We treat the *existence* of a terrain–crime association as established and test the
**mechanism**. Three candidates make different predictions:

| | Mechanism | Prediction |
|---|---|---|
| **M1** | **Effort** — climbing and hauling cost energy | Deterrence scales with the physical work of the crime, especially the mass removed |
| **M2** | **Exposure/risk** — hills carry less through-traffic, have fewer escape routes, and are overlooked | Deterrence is roughly equal across crime types, and is mediated by network and visibility measures |
| **M3** | **Confounded affluence** — hills are wealthy | Association vanishes under within-neighbourhood comparison and tracks the city's elevation–income gradient |

**Primary hypothesis (H1, the no-loot control).** If M1 holds, crimes in which nothing is
carried away — vandalism and arson — must be substantially less deterred by relative
height than theft, because their removal cost is zero by construction while their approach
cost is unchanged.

> **H1:** the terrain coefficient for no-loot crime is *closer to zero* than the terrain
> coefficient for theft, in most cities.

**We predict H1 will be FALSIFIED** — that the two coefficients will be statistically
indistinguishable. Exploratory work in four cities is consistent with that, and this
registration exists to test it confirmatorily on new units, new denominators, and new cities.

**H2 (loot-mass gradient).** Under M1, the terrain coefficient varies monotonically with
the mass removed, across the ordered ladder pocketable → light → medium → heavy → very
heavy. Predicted: no monotone trend.

**H3 (mediation).** Under M2, controlling for network betweenness, permeability, egress
count, and the visibility proxy substantially attenuates the terrain coefficient.
Predicted: substantial attenuation (see §7 for the threshold).

**H4 (motor vehicle theft).** MVT's "loot" self-propels, so its removal cost is independent
of gradient. Under M1 it should be among the least deterred; under M2 it should be among
the most deterred, since hilltop streets are conspicuous with few exits.

**H5 (relief floor / placebo).** Cities below the relief floor (§4) show terrain
coefficients indistinguishable from zero. A non-zero effect in a flat city indicates
residual confounding rather than terrain.

## 3. Design

Observational. Unit of analysis: **street segment** (block face between intersections),
matching Kim & Wo. Grid cells at 100 m are retained only as a robustness check.

Identification is **within census block group** throughout: block-group fixed effects are
absorbed, so every comparison is between segments in the same neighbourhood — the top of
a hill against the bottom of the same hill, same demographics, same police beat.

## 4. Inclusion criteria (fixed now, applied before outcome analysis)

A city enters the confirmatory panel only if:

1. **TPI SD ≥ 4 m** at the 500 m radius. Below this, a bare-earth DEM is dominated by
   levees, highway embankments, and fill rather than terrain. *(Motivating example: Baton
   Rouge spans 15.9 m of relief, 1 SD of TPI = 0.98 m, and returns +22.9%, z = 3.1.)*
2. **≥ 20,000 classified property-crime incidents** since 2018-01-01.
3. **≥ 1.0 incident per analysis unit**, ensuring the crime feed actually covers the
   geography assigned to it. *(Marin County: 1,313 km², 99% of cells empty, because the
   Sheriff polices only unincorporated areas.)*
4. **Point-level geocoding**, not block-face or centroid-snapped only.
5. For H1 specifically: **≥ 3,000 no-loot incidents** (vandalism, criminal damage, arson).

Cities are screened on these criteria using terrain and volume only — **never on the
outcome coefficient.**

## 5. Variables

**Exposure (independent).** Relative height = Topographic Position Index, elevation minus
the mean elevation within radius R, from USGS 3DEP 10 m DEM. Primary R = 500 m; the full
sweep R ∈ {50, 100, 250, 500, 1000, 2000} is reported. Standardised within city.

**Outcome.** Counts of property crime per segment since 2018-01-01, split into:
`MASS_1` pocketable, `MASS_2` light, `MASS_3` medium, `MASS_4` heavy, `MASS_5` very
heavy/tools, `MVT`, `NO_LOOT`. The loot-mass ordering is fixed in `src/crime_classes.py`
and **was set before any outcome analysis**.

**Offset.** Building-footprint-apportioned housing units and population. Area-apportioned
exposure is a robustness check, not the primary.

**Controls.** Median household income, median home value, owner-occupancy share, vacancy
rate, log exposure density; block-group fixed effects.

**Mediators (H3).** Betweenness, intersection density, permeability, egress count,
dead-end status, stairs within 100 m, walk/drive network ratio, visibility proxy.

## 6. Statistical model

Poisson pseudo-maximum-likelihood with a log-exposure offset and absorbed block-group
fixed effects; standard errors clustered on block group. Poisson rather than OLS on rates
because the outcome is an overdispersed count with many zeros; PPML rather than dummy
variables because ~500–2,500 fixed effects make IRLS diverge.

Spatial autocorrelation: primary specification uses cluster-robust SEs; a conditional
autoregressive (BYM) specification is reported as the sensitivity analysis. Moran's I on
residuals is reported for every model.

## 7. Decision rules (set in advance)

- **H1 falsified** if the 95% CI for the *difference* between the theft and no-loot terrain
  coefficients contains zero in ≥ half the qualifying cities, with a pooled difference
  whose CI contains zero. Difference tested by seemingly-unrelated estimation with
  city-clustered bootstrap (2,000 draws).
- **H2 falsified** if the inverse-variance-weighted slope of the coefficient on loot mass
  has a 95% CI containing zero.
- **H3 supported** if adding mediators attenuates the pooled terrain coefficient by ≥ 40%.
- **H4** resolved by whether MVT ranks in the upper or lower half of deterrence.
- **H5 supported** if the pooled coefficient among sub-floor cities has a CI containing zero.
- **Substantive-size floor:** any effect smaller than **5% per SD** is reported as
  substantively negligible regardless of p-value. With tens of thousands of units,
  significance is cheap and this floor keeps the discussion honest.

## 8. Sample size and power

Determined by data availability, not by choice. Expected 6–12 qualifying cities and
15,000–30,000 segments per large city. We do not stop collection based on results, and we
do not add or drop cities after seeing coefficients. The panel is frozen once §4 is applied.

## 9. What would change our conclusion

Stated explicitly to preclude post-hoc reinterpretation:

- If no-loot crime is clearly **less** deterred than theft (pooled difference CI excluding
  zero, in the predicted direction), **M1 survives and our thesis is wrong.**
- If mediators do not attenuate the terrain coefficient, **M2 is not the answer either**,
  and the association is left unexplained — which we will report as such rather than
  fitting a third story to the residual.
- If the terrain coefficient does not survive block-group fixed effects and
  building-based exposure, **M3 wins** and the published finding is confounding.

## 10. Known limitations, acknowledged in advance

1. **Reported crime only.** Reporting rates rise with income, which correlates with
   elevation. This biases *against* finding a negative terrain effect.
2. **Crime-type harmonisation across cities is imperfect.** Departments use different
   taxonomies; the text classifier in `src/crime_classes.py` is coarse in cities that
   publish only a top-level offense category.
3. **Bare-earth DEMs still contain built terrain** — embankments, retaining walls, cuts.
   This motivates the relief floor but does not eliminate the problem.
4. **No offender residence data**, so crime-location-choice models (Bernasco) are out of
   reach and the substitution radius is inferred rather than observed.
5. **Directional movement costs are not identifiable from a raster.** Approach and
   loaded-escape cost are both functions of the same gradient field (r = −0.80 with TPI in
   San Francisco). Separating them requires an asymmetric network. We report this as a
   methodological finding rather than attempting the decomposition.
6. **Ecological inference.** Conclusions concern places, not people.

## 11. Exploratory work already conducted (full disclosure)

Conducted before this registration and reported as exploratory:
San Francisco pilot at 100 m cells (attenuation path, radius sweep, loot-mass ladder);
an 11-city panel with area-apportioned exposure; a two-stage decomposition of city-level
coefficients on the elevation–income correlation; and a directional round-trip cost model
of our own predicting sign reversal with loot mass, which was **not supported** (slope
−0.0018/kg, CI [−0.010, +0.018]). All p-values from that work are descriptive. The
confirmatory tests above are run on new units, new denominators, and an expanded panel.

---

## Addendum — deviations from this pre-registration

Recorded 2026-08-04, after the confirmatory analysis. Listed so that readers can discount
them appropriately rather than discover them.

### D1. The treatment variable changed, and this was not anticipated

This document registers **relative height (TPI)** as the exposure, following the published
literature. The confirmatory analysis found relative height to be inconsistent in sign
across cities, while **slope** was strongly and consistently negative everywhere. The
headline analysis therefore reports slope.

This was **not** pre-specified and must be read as exploratory. In mitigation: slope was
always in the variable set as a control, it was not selected from a large pool (there are
two candidate terrain measures, not twenty), and the selection was made on *consistency
across cities*, not on statistical significance in a single one. The registered hypotheses
H1–H4 were then re-run on slope and are reported for both variables in the manuscript.

### D2. A slope floor was added post hoc

Section 4 registers a relief floor of TPI SD ≥ 4 m. Applying the analysis to slope revealed
the same pathology in a different variable: cities with almost no gradient (Chicago, mean
slope 0.96°) return implausibly large per-degree effects. We therefore added a **slope floor
of within-city slope SD ≥ 3°**, which retains San Francisco, Seattle, and Cincinnati.

This threshold was chosen **after seeing the estimates** and is therefore post hoc. Two
things argue it is not merely a device for producing a clean result:

1. It is the direct analogue of a criterion registered in advance for the other terrain
   variable, applied for the identical reason.
2. It is validated by a statistic that was not used to choose it: heterogeneity. Above the
   floor, I² = 0.00 (Q = 1.28, 2 df). Below it, I² = 0.88. A threshold chosen to flatter a
   result would not be expected to produce perfect agreement on one side and violent
   disagreement on the other.

Readers who reject the floor should read the six-city result: the per-degree effect remains
negative and significant in every city, but ranges from −5.7% to −21.6% and is decisively
heterogeneous.

### D3. Mediator set reduced

The registered mediator list included a visibility proxy. On construction it proved
near-collinear with relative height (r = 0.80) — it is close to a monotone transform of the
treatment rather than a mediator of it — and was dropped. Testing the visibility channel
requires building heights, not a bare-earth surface. Reported in the manuscript.

Additionally, betweenness is computed with **travel-time** rather than distance weighting.
On San Francisco's network, distance-weighted betweenness is confounded with the treatment:
its top-ranked streets are residential lanes over the Twin Peaks ridge, because terrain
forces cross-town paths through them. The two orderings correlate at only ρ = 0.68.

### D4. Panel smaller than anticipated

Section 8 anticipated 6–12 qualifying cities. After the slope floor, three cities carry the
headline estimate and six carry the no-loot control. This is the principal limitation of the
study and is stated as such.

### D5. Out-of-sample test, and a claim withdrawn

After the addendum above was written, three further cities (Pittsburgh, Baltimore,
Charlotte) were harvested from ArcGIS sources. They played no part in selecting slope as the
treatment or in setting the 3° gradient floor, so they function as an out-of-sample test of
both. Two results:

**The gradient floor is confirmed.** Baltimore (2.86°) and Charlotte (2.10°) fall below it
and return −14.1% and −20.7% per degree, squarely in the inflated band occupied by the other
sub-floor cities and far outside the above-floor range. This was predicted before the models
were run.

**The homogeneity claim is withdrawn.** With three qualifying cities the pooled per-degree
effect showed I² = 0.00 and an earlier draft described it as a constant. Adding Pittsburgh
moves this to **I² = 0.86 (Q = 21.1 on 3 df, p = 1×10⁻⁴)**. The original figure was an
artifact of a Q test with two degrees of freedom, which has almost no power — a limitation
we had flagged for the H1 test and failed to apply to the headline. The manuscript now
reports the pooled estimate with heterogeneity attached and explicitly warns against
treating it as transportable.

We record this because it is the clearest illustration in the project of why the k = 3
caveat mattered, and because the corrected claim is weaker than the one it replaces.

### D6. Positioning corrected

An earlier draft framed the slope finding as novel and as reversing Breetzke (2012). This
was wrong. **Haberman & Kelsay (2021, *Journal of Quantitative Criminology*)** had already
established a slope–crime association for robbery in Cincinnati, at a magnitude (~7.9% per
degree) close to ours. The contribution is therefore generalisation from robbery to property
crime across cities, plus the mechanism tests — which address the three explanations
Haberman and Kelsay explicitly named and left untested. The manuscript has been repositioned
accordingly.


### D7. Defects found by audit, and what they cost

Four coding defects were found by validation rather than by inspection. All were silent —
totals looked plausible, models converged, coefficients were stable — and all are recorded
here because each one changed which analyses were possible.

1. **`Series.astype(str)` preserves NaN on pandas 3.0.5.** Both harvesters concatenate up to
   three description columns; a single null column turned the whole string to NaN and sent
   the row to the unclassified bucket. This emptied every non-theft class in Cincinnati.
2. **NIBRS 23G/24I parts and plate thefts matched the motor-vehicle-theft rule.** In Seattle
   that merged 32,501 parts thefts into 50,824 real vehicle thefts — a 49% inflation of the
   one class where the candidate mechanisms make opposite predictions — while leaving the
   heaviest loot rung empty.
3. **"criminal damage" does not match Ohio's "CRIMINAL DAMAGING/ENDANGERING."** Cincinnati's
   28,513 no-loot records fell to the unclassified bucket, and the city was excluded from
   this study's primary test for apparently lacking vandalism data.
4. **Cincinnati's registry row read only `offense`**, a UCR top-level field, omitting the
   NIBRS sub-code the loot ladder needs. Without it the city had zero MVT, MASS_1, MASS_2
   and MASS_5.

All four are fixed and the panel was rebuilt. The headline moved from −6.61% to −6.61%; the
primary test gained a city.

**Process note, recorded against ourselves.** The panel rebuild was started while the
classifier was still being edited, and Cincinnati was consequently built against a
half-applied rule set. It was caught by comparing class counts before and after
(`outputs/classifier_fix_impact.csv`) and rebuilt. Had that comparison not been run, the
error would have shipped.


### D8. Los Angeles recovered; two further classifier gaps closed

Los Angeles had been absent from the analysis. The cause was a field-selection defect, not a
data limitation: the registry ranked description columns in dataset order, and Los Angeles
lists `weapon_desc`, `premis_desc` and `vict_descent` before `crm_cd_desc`. Since the
harvester concatenates the first three, the classifier was reading a weapon, a premise and a
victim's ethnicity while the only field naming the offense was discarded. `registry.py` now
*ranks* description columns, promoting offense-like names and demoting victim, weapon,
premises and case-status fields.

Recovering the city exposed two further gaps in the classifier, both fixed:

* **Inverted motor-vehicle-theft wording.** Los Angeles publishes vehicle theft as
  "VEHICLE - STOLEN" (115,184 records) and Prince George's County as "AUTO, STOLEN". Neither
  contains "stolen vehicle" in that order, so both fell to the unclassified bucket and the
  city lost its MVT class entirely.
* **Vehicle burglary read as building burglary.** Los Angeles records theft from a car as
  "BURGLARY FROM VEHICLE" (63,515 records) and Nashville as "BURGLARY - MOTOR VEHICLE". The
  generic burglary rule fired first, moving a rung-2 offense to rung 4. The vehicle-burglary
  pattern is now tested ahead of both the burglary and motor-vehicle-theft rules.

A third repair followed: separator normalisation collapses the slash in "THEFT F/AUTO", so
the literal pattern `f/auto` stopped matching and a theft-from-vehicle fell to the generic
rung. The pattern is now `\bf[\s/]*auto\b`.

**Impact on existing results was checked before each change was adopted, not after.** Every
new pattern was run against the description vocabulary of all built cities. They match
**nothing** in San Francisco, Seattle, Cincinnati, Kansas City, Montgomery County, Pittsburgh
or Los Angeles, and 9,036 records in Chicago. All cities above the gradient floor are
therefore unaffected and **the headline estimate does not change**; only Chicago, which is
below the floor, was rebuilt (−19.76% to −19.76% per degree).

Re-scored against the hand-coded validation sample using the pipeline's own normalisation,
the repairs fix four strings and break none: primary-sample accuracy rises from 0.922 to
0.932 string-level and 0.968 to 0.974 incident-weighted, the holdout is unchanged, and
NO_LOOT precision and recall are untouched at 0.956 and 1.000. The holdout being flat is the
honest reading — these repairs help specific cities rather than raising accuracy in general.

### D9. Prior-estimate conversion corrected

An earlier draft converted Haberman and Kelsay's coefficient to −7.9% per degree using a
linear shortcut (4.5 ÷ 0.573). Under a log link the conversion compounds:
β = ln(0.955) × tan(1°) × 100 = −0.0804, giving **−7.72% per degree**. The manuscript now
carries the compounded figure.

We were unable to obtain the full text of Haberman and Kelsay — the journal is paywalled and
the repository copy returns HTTP 403 — so the effect size, the percent-grade units and the
three proposed mechanisms are drawn from the published abstract and secondary summaries.
This is flagged in the manuscript and should be confirmed against the original before
submission.

### D10. The gradient floor was demoted from a sample rule to a sensitivity analysis

The plan set no terrain threshold. D2 recorded that a 3° within-city slope standard
deviation floor was added after seeing terrain data, and defended it on measurement
grounds. The defence is still the one I would give, but the objection stands: a
threshold chosen after inspecting the data is a researcher degree of freedom no matter
how good the argument attached to it, and this one set the headline number.

The primary analysis is now a random-effects meta-regression of the city coefficient on
that city's slope standard deviation, centred at 3°, using all nine cities. The
moderator is significant (+4.06% per degree of slope SD, 95% CI [+0.84, +7.38],
p = 0.020) and accounts for 59% of the between-city variance. The threshold split is
retained below it as a sensitivity analysis. This says everything the floor said, uses
every city, and does not require anything to be cut.

The pooling method also changed. The plan and every draft through the first submission
version used a fixed-effect inverse-variance pool, which assumes a common effect and
narrows as cities are added even when they disagree. The pools are now random effects
with REML τ² and a Hartung–Knapp interval. For the four higher-gradient cities this
moves the headline from −6.61% [−7.39, −5.82] to **−6.89% [−9.51, −4.21]**, and the
prediction interval for a new city is [−13.71, +0.46]. The point estimate barely moved;
the honest uncertainty around it roughly doubled.

### D11. The no-loot test was re-specified after external review

Three changes, all of which make the test harder to pass rather than easier.

**Equivalence testing replaced the null.** The plan's decision rule was "indistinguishable
in at least half the cities plus a pooled interval spanning zero." A null result is also
what an underpowered study produces, so that rule cannot support the claim it was being
used for. The contrast is now evaluated by two one-sided tests against a margin of half
the headline effect (0.0342 on the log scale, 3.48 pp per degree), fixed before the
tests were run. Pooled difference +0.55 pp/degree, TOST p < 10⁻⁵.

**Arson was separated from vandalism.** Arson involves preparation and acute escape risk;
grouping it with graffiti made the control less homogeneous than the paper implied. It is
1.6–3.9% of no-loot incidents in three cities and 0.02% in Cincinnati. Dropping it moves
the pooled difference from +0.55 to **+0.09 pp/degree** [−2.28, +2.52].

**The two offense groups were matched on time.** Vandalism concentrates at night and theft
does not. Reweighting no-loot incidents to theft's hour-of-day × day-of-week distribution
gives **+0.10 pp/degree** [−2.25, +2.50].

Both variants required re-downloading the four higher-gradient cities with the incident
timestamp and offense text retained, which the original harvest discarded
(`src/harvest_dated.py`). I no longer describe the comparison as a placebo. It is a
bounded falsification of a loaded-haul mechanism and nothing wider.

### D12. Reporting added that the plan did not require

Estimator diagnostics (convergence, iterations, separation, singleton and all-zero
fixed-effect groups, sample reduction); a 1 km spatial block bootstrap alongside the
cluster-robust errors, which shows block-group clustering was mildly *anti*conservative,
up to 1.30× in Seattle, reversing a claim made in an earlier draft; classification error
propagated to the coefficients through 200 relabelling draws from the audit confusion
matrix (it contributes 2–3% of the sampling standard error); pre- and post-March-2020
estimates; and the target-count denominator extended from San Francisco to all nine
cities, where it gives a mixed result rather than the clean San Francisco one.

Two citation errors were also corrected: reference 4 conflated a San Francisco bicycle
theft paper with a separate Toronto paper, and Herzog was dated 2013 rather than 2014.
The Ye and Becker multi-city elevation literature and the offender location-choice
literature were missed entirely in the original scan and are now cited.

### D13. The multi-city target-denominator extension was retracted and re-run

The first version of D12's footprint-denominator extension reported estimates for all
nine cities, including a −48.5% per degree figure for San Francisco and a −16.3% for
Seattle. Those were not estimates. Five of the nine fits had stopped at the iteration
cap with a maximum remaining score in the thousands and were returning standard errors
around 1e-11, which is a degenerate sandwich rather than a precise coefficient. The
estimator's own convergence diagnostics — added in D12 — would have caught it, but
`target_multicity.py` never checked them.

Two defects, both fixed. The control `log_density` was being redefined as the log of
whichever denominator was in play, so the control set changed along with the offset and
became the log of the offset itself; it is now always residential density on the
original housing exposure, and only the offset changes. And convergence is now judged on
the first-order condition (max absolute score, scaled by total events) rather than on a
coefficient-change flag, with the iteration cap raised from 60 to 200.

After the fix, five cities (Charlotte, Seattle, Cincinnati, Chicago, Montgomery County)
still fail to converge and are not reported. In the four that do, the denominator shifts
the estimate by +0.99, −1.49, −0.57 and +0.17 percentage points — two each way, all
small. The extension neither supports nor contradicts the San Francisco result; it is
uninformative, and the manuscript now says so.

The iteration-cap change is inert for every other model in the paper: all nine headline
coefficients are identical to machine precision before and after, since they converge in
eight to eleven iterations.
