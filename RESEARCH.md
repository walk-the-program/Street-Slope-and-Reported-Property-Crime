# Crime and Altitude

**A study of whether topographic elevation — measured *relative to surrounding terrain* — suppresses property crime, and if so, why.**

> **Superseded in part.** This document is the original study design, written when the
> hypothesis under test was *relative height* (TPI). The analysis has since moved to
> **slope**, which proved the robust predictor, and the effort mechanism this design was
> built to test has been rejected. For current findings read **`PAPER.md`**; for what
> changed and why, **`DIRECTION.md`**. The metric ladder (§5), data sources (§9), and
> threats to validity (§11) below remain accurate and useful.

Status: superseded by `PAPER.md` — retained for the metric ladder and data-source sections
Last updated: 2026-08-04

---

## 0. TL;DR for the impatient

- Your hypothesis is **real and already partially confirmed** by two published studies. One of them (San Francisco, 2023) independently invented your "relative height, not absolute height" idea and found it's the *stronger* predictor. See §2.
- The frontier is therefore **not** "does elevation matter." It's **"which mechanism?"** Effort? Escape routes? Visibility? Or is it just that hills are rich?
- The single biggest threat to this study is that **elevation is capitalized into land value**. In most US cities hills = wealthy. A naive elevation↔crime correlation will be strongly negative for reasons that have nothing to do with your hypothesis. §4.1.
- The best original contribution available to you is a **dose–response test by loot portability** (§6.2) and a **cross-city design using places where the elevation↔wealth correlation is inverted** (§7). Both are cheap. Both are decisive.
- "Higher" should be operationalized as a **ladder of ~9 metrics** running from naive elevation to metabolic cost-distance accessibility. §5. The radius at which the effect peaks is itself a finding.
- **Scaling to a national panel is not "more data" — it is the identification strategy.** The elevation–wealth correlation varies by city, so regressing city-level terrain effects on it recovers the effect purged of affluence. Unobtainable from one city at any sample size. §7.5.

**Pilot update (San Francisco, 2026-08-04):** the elevation effect shows up at −6% to −11% per SD, but **the loot-mass test does not support the energy mechanism** — vandalism, which involves carrying nothing, is deterred as much as theft. Meanwhile relative height turns out to be ~6× less wealth-confounded than absolute elevation, which vindicates the core design choice. Full numbers in `PILOT_RESULTS.md`.

---

## 1. The hypothesis as originally stated

> Places that are higher than the surrounding geography experience less property crime than places that are lower.

**Stated mechanism (the "energy budget" model):**

1. Offenders are effort-minimizing agents. They want to maximize criminal yield while minimizing energy expenditure and probability of apprehension.
2. Many offenders travel to crime scenes on foot.
3. Climbing costs energy. Climbing a lot costs a lot of energy.
4. Property crime targets are largely fungible — one car is much like another car.
5. Therefore, when a fungible target sits atop a hill and an equivalent target sits on flat ground nearby, the rational offender takes the flat one.
6. Therefore elevated places should show a property-crime deficit.

**Corollary offered:** there may also be a *psychological* component — elevated terrain simply *reads* as harder, remote, or fortified, and deters before any explicit cost calculation occurs.

**Scope:** primarily property crime (burglary, larceny, theft from vehicle, motor vehicle theft). Possibly extends to crime generally.

### 1.1 Restating it formally

Let $T$ be the set of candidate targets in an offender's awareness space. The offender selects target $i$ maximizing

$$U_i = R_i - C_i^{\text{effort}} - P_i^{\text{apprehension}} \cdot L$$

where $R_i$ is expected reward, $C^{\text{effort}}$ is the cost of reaching and leaving the target, $P^{\text{apprehension}}$ is capture probability, and $L$ is the loss on capture.

The hypothesis is that **relative elevation increases $C^{\text{effort}}$** and that this is large enough, relative to variation in $R_i$, to shift target selection measurably.

This formalization immediately generates the critique in §4: elevation plausibly *also* raises $R_i$ (hills are wealthy — richer targets) and *also* raises $P^{\text{apprehension}}$ (fewer escape routes, better sightlines). Three channels, different signs, one observable. Untangling them is the study.

---

## 2. Prior literature — what's already known

**This is not virgin territory, and that is good.** Two direct precedents:

### 2.1 Breetzke (2012) — Tshwane, South Africa
*"The effect of altitude and slope on the spatial patterning of burglary,"* Applied Geography 34: 66–75. Burglary incidents 2003–2006, OLS + geographically weighted regression.

- **Higher altitude → lower burglary victimization risk.** Confirms the core claim.
- **Slope steepness → no effect.** Notable. If the mechanism were pure metabolic cost, slope should matter a lot (steepness is what makes climbing expensive). It didn't. First hint that raw energy expenditure may not be the operative channel.

### 2.2 Kim & Wo (2023) — San Francisco
*"Topography and crime in place: The effects of elevation, slope, and betweenness in San Francisco street segments,"* Journal of Urban Affairs 45(6): 1120–1144. Unit of analysis: street segment.

- **Elevation *differences within the surrounding ¼ mile* ("hilliness") reduce crime risk more than the segment's own elevation or slope.**
- Network **betweenness increases** crime risk.
- Significant **interaction** between local hilliness and betweenness.

That first bullet is your relative-height intuition, arrived at independently, and it beat absolute elevation. You reasoned your way to the published state of the art without reading it. Take the win — and note that it means the "does it exist" question is spent.

### 2.3 Adjacent, useful
- **Journey-to-crime / distance decay.** Crime frequency falls with distance from the offender's anchor points. Property-crime medians are roughly 1–2 miles in older studies, with some recent estimates near 5.7 miles; violent crime is consistently shorter. Note this is *further than comfortable walking distance* — see §4.2.
- **Zipf's principle of least effort** → Brantingham & Brantingham's crime pattern theory: offenders offend inside their awareness space, along nodes and paths of routine activity.
- **Bernasco-style crime location choice models** (discrete choice over candidate targets) — the methodological state of the art for exactly this kind of question.
- **Permeability/connectivity and burglary** (Johnson & Bowers and successors): through-streets and high-permeability layouts carry more burglary than cul-de-sacs. Hills *produce* cul-de-sacs and switchbacks. Possible mediator, not just a confound.
- **Bicycle theft and topography** (Int. J. Sustainable Transportation, 2026) — a very fresh paper on topography, accessibility, and built environment for bike theft. Bikes are a near-ideal test case: the offender must *pedal the loot away*, so gradient enters both approach and escape cost. Get this one.

### 2.4 What this means for your positioning
Do **not** frame the project as "I wonder if elevation reduces crime." Frame it as:

> Elevation suppresses property crime. Three mechanisms could produce that: energy cost, escape-route scarcity, and confounded affluence. Here is a design that tells them apart.

That's a contribution. The first framing is a replication.

---

## 3. Research questions

**Primary**
- **RQ1.** Controlling for socioeconomic and built-environment confounders, does relative elevation predict lower property-crime rates?
- **RQ2.** At what **spatial scale** is the relationship strongest? (i.e., what neighborhood radius $R$ maximizes the TPI effect?)
- **RQ3.** Is the effect explained by **effort**, **escape-route scarcity/visibility**, or **residual affluence**?

**Secondary**
- **RQ4.** Does the effect vary by crime type in the pattern predicted by an effort model — strongest for bulky/heavy loot, weakest for pocketable loot? (§6.2 — the key test.)
- **RQ5.** Does the effect persist in cities where hills are *poor* (Medellín, La Paz, Valparaíso, parts of Pittsburgh/Cincinnati)? (§7 — the other key test.)
- **RQ6.** Does the effect survive controlling for **vehicle** accessibility, isolating the pedestrian-effort channel?
- **RQ7.** Is it elevation, or is it **isolation**? Does topographic *prominence* (an isolated knoll) matter more than being partway up a long grade at the same absolute height?
- **RQ8.** Placebo: does an apparent "elevation effect" appear in near-flat cities (Chicago, Phoenix, Houston)? If yes, the pipeline is broken.
- **RQ9.** Is there an analogous vertical effect *within* buildings (burglary rate by floor)? A cheap consistency check on the mechanism at a different scale.

---

## 4. Feedback: what's strong, what breaks

### 4.1 ⚠️ THE BIG ONE — elevation is priced

You wrote: *"This neighborhood is probably going to cost the same regardless of height. Let's just make that an assumption. It's probably not a true assumption."*

It is not merely untrue. **It is the entire problem.** Elevation is one of the most reliably capitalized amenities in urban real estate, for three independent reasons:

1. **Views.** Hilltops sell views. Views command enormous premiums.
2. **Flood risk.** Low ground floods. Flood plains got industry, rail yards, and — in the US — redlining.
3. **Air and nuisance.** Historically, smoke, smell, and noise settle low. Elite districts moved uphill in the 19th century almost universally.

Result: in the median US city, elevation correlates positively with income, owner-occupancy, and housing value — every one of which independently predicts lower property crime. SF's Pacific Heights, Pittsburgh's Mt. Washington, Cincinnati's Mt. Adams, LA's hills, Seattle's Queen Anne.

**So a naive elevation↔crime regression will "confirm" your hypothesis while telling you nothing.** Any version of this study that doesn't confront this head-on is unpublishable and, worse, uninformative. The three structural answers are matched-pairs designs (§8.3), slope-break discontinuities (§8.4), and inverted cities (§7). Covariate adjustment alone is *not* sufficient — income at the tract level is far coarser than the terrain variation you're studying, so residual confounding is guaranteed.

### 4.2 ⚠️ "Criminals walk" is carrying more weight than it can hold

Property-crime journey-to-crime distances center on 1–2 miles, and some estimates run substantially higher. That is not primarily a walking distribution. A large share of property offenders — especially for motor vehicle theft, commercial burglary, and anything involving fenceable volume — arrive in a vehicle.

**This matters because for a driver, your 1,000-foot hill costs approximately zero calories.** What it costs them instead is:
- fewer approach roads,
- fewer escape routes (often exactly one),
- more conspicuous presence (a strange car on a dead-end hill road is *noticed*),
- worse GPS-free navigability and more switchbacks under pursuit.

Those are all real deterrents. They are just **not your mechanism.** They're the "apprehension probability" term, not the "effort" term.

Two consequences:
- The metabolic story must be tested, not assumed. §6.2 and §6.3 are how.
- Breetzke's null on *slope* is corroborating evidence for this worry. Steepness is where metabolic cost lives, and it did nothing.

### 4.3 ⚠️ The thought experiment is not the study

The 1,000-foot unclimbable hill with one house on it is an excellent intuition pump and essentially does not exist. Real intra-urban relief within a ¼-mile radius is typically **20–200 feet**. You should mentally recalibrate: you're looking for a modest gradient across modest hills, detectable only with good controls and decent sample size — not a cliff-edge phenomenon you'll see by eye.

The corollary is that **effect size matters more than significance.** With ~10,000 street segments you will get $p < 0.001$ on noise. Pre-commit to reporting incidence-rate ratios and to treating anything below, say, a 5% rate difference per SD of TPI as substantively small.

### 4.4 ⚠️ Reported crime ≠ crime, and elevation predicts reporting

Higher-elevation → wealthier → more insured → more likely to report theft (insurance requires a police report) → **upward** bias on measured crime at elevation. This one runs *against* your hypothesis, which is mildly reassuring; if you find the effect anyway, it survived a headwind. But it also means the true effect may be larger than measured, and you should say so rather than pretending the measurement is clean.

Countervailing: wealthier → more alarms, cameras, gates, private security → genuinely less crime *and* possibly more detection. Target hardening is a real confound that travels with elevation and is not terrain.

### 4.5 ⚠️ Geocoding precision will silently destroy you

Many open crime portals **deliberately degrade coordinates for privacy**:
- Cincinnati: lat/lon "randomly skewed" within the block.
- Los Angeles: addresses to the nearest hundred block.
- Others snap to block centroid or street centerline.

On a 20% grade, **100 m of horizontal error is ~20 m of vertical error** — the same magnitude as the entire signal you're chasing. And the error is not random with respect to your predictor: snapping to a street centerline systematically moves incidents toward roads, which on hills are the *low-effort* paths.

**Implication: do not use parcel-level or point-level analysis as your primary specification.** Aggregate to street segment or ~100 m hexagon, which is almost certainly why the San Francisco paper used street segments. Verify each city's geocoding policy before ingesting and record it in the data dictionary.

### 4.6 ✅ What's genuinely strong

- The relative-vs-absolute insight is correct and is the published finding.
- Grounding target selection in effort-minimization is the mainstream theoretical frame (least effort → crime pattern theory), not a fringe idea.
- Target fungibility is exactly right and is the load-bearing assumption that makes substitution possible. Without it, no hypothesis.
- The instinct to worry about "what if everyone's on a hill" is the correct instinct and has a clean answer (§5.2, §5.4).
- The "psychological effect" hunch is defensible and testable — it maps onto **prospect–refuge** and legibility literature, and it's separable from metabolic cost by §6.3.

### 4.7 One reframe worth adopting

Stop saying **"high."** Start saying **"expensive to reach."** They are different variables and the second is the causal one.

A mesa with a four-lane arterial up it is high and cheap. A 40-foot ravine with no footbridge is low and expensive. If you build your independent variable as *effort-weighted accessibility* rather than *elevation*, you (a) test the actual mechanism, (b) automatically handle the "everyone's on a hill" problem, and (c) go beyond what's been published.

---

## 5. Defining "higher" — the metric ladder

This was your explicit question and it's the technical heart of the project. Build **all** of these; they're cheap once the DEM is loaded, and disagreement between them is informative.

Notation: $z(x)$ = elevation at location $x$; $N_R(x)$ = neighborhood of radius $R$ around $x$.

### Tier 1 — Naive

**1. Absolute elevation** $z(x)$.
Baseline only. Nearly meaningless alone — it mostly encodes which part of the city you're in, and so proxies for everything. Include it as a control, never as the treatment.

### Tier 2 — Relative (this is what you actually described)

**2. Topographic Position Index (TPI).** The standard, named, defensible version of your idea:

$$\text{TPI}_R(x) = z(x) - \overline{z}\left(N_R(x)\right)$$

Positive = higher than surroundings. Negative = a hollow. Developed by Weiss (2001); a completely standard GIS primitive with existing tooling. **You reinvented TPI.** Cite Weiss and move on.

**3. Multi-scale TPI.** Compute at $R \in \{50, 100, 250, 500, 1000, 2000\}$ m.
Small $R$ catches "my house is on a knoll." Large $R$ catches "my whole neighborhood is a plateau."

> **The best idea in this document:** *the radius at which the crime effect peaks is itself a substantive finding.* It estimates the **offender's opportunity-substitution radius** — the distance over which they treat targets as interchangeable. If the effect maximizes at $R \approx 400$ m, that says offenders are comparing your house to alternatives ~400 m away. That's a novel, quotable, theoretically meaningful number that nobody has published, and it falls out of the analysis for free.

**4. Standardized / percentile TPI.** Two variants:
- $z$-score of TPI within the city — makes cities comparable.
- **Local elevation percentile**: "this address is higher than 94% of addresses within 500 m." Scale-free, robust to outliers, and immediately intuitive to a non-technical reader.

This is the direct answer to your "what if everyone's on a hill" worry. TPI is already a *deviation* from the local mean, so a uniformly elevated city (Denver) has TPI ≈ 0 everywhere. Percentile-within-radius makes that even more explicit.

**5. Local relief / elevation range.** $\max(z, N_R) - \min(z, N_R)$. This is the "hilliness" variable that Kim & Wo found dominant. Note it measures *ruggedness of the area*, not the position of the point — different construct, include both.

**6. Topographic prominence.** The mountaineering definition (drop to the key col before reaching higher ground). Distinguishes **an isolated knoll** from **a point partway up a long grade at the same absolute height**. Your 1,000-foot-hill thought experiment is specifically a *high-prominence* feature, and prominence is the variable that captures what makes it feel special. Underused in this literature — likely a differentiator.

### Tier 3 — Effort (the flagship variables)

These replace geometric distance with **energy**, and this is where the study earns its keep.

**7. Slope-dependent cost surface.** Two well-established options:
- **Tobler's hiking function:** walking speed $v = 6\exp\left(-3.5\left|s + 0.05\right|\right)$ km/h, where $s = dh/dx$. Note the $+0.05$: it's asymmetric, and the fastest walking is on a slight *downhill*. Time-based.
- **Minetti et al. (2002) metabolic cost**, J·kg⁻¹·m⁻¹ as a function of gradient, commonly implemented via **Herzog's (2010) 6th-degree polynomial** which avoids Minetti's unphysical negative costs at steep downgrades. Energy-based — closer to your actual hypothesis.

Use Minetti/Herzog as primary (it *is* the calorie story) and Tobler as robustness.

**8. Effort-weighted accessibility (the flagship).**

$$A(x) = \sum_{j} O_j \cdot f\!\left(C(j \rightarrow x)\right)$$

where $O_j$ is offender-origin weight at $j$ (population, or better, a residential-population/known-offender-origin surface), $C$ is accumulated metabolic cost along the **least-cost path on the pedestrian network**, and $f$ is a distance-decay kernel calibrated from journey-to-crime literature.

Low $A(x)$ = "few offenders can cheaply reach you." This is your hypothesis, stated as a measurable quantity. It's a gravity model with joules where the miles usually go.

**9. Excess effort ratio.**

$$E(x) = \frac{C_{\text{least-cost}}(x)}{C_{\text{flat-equivalent}}(x)}$$

"How much harder is this place to reach than a flat place the same road-distance away?" Unitless, interpretable, and it cleanly separates *hard to reach because far* from *hard to reach because uphill*. If I could only have one variable, this is it.

**10. Net vertical work to reach.** $W = m g \Delta h$ along the least-cost approach path, in kJ, for a 75 kg offender. Not the most statistically powerful, but it converts the finding into a sentence a journalist can print: *"Each additional 40 kilojoules of climbing — about one flight of stairs — is associated with an X% reduction in burglary."*

### Tier 4 — Access and visibility (the rival mechanisms, measured explicitly)

You must measure these to *rule them out*, so build them as first-class variables:

**11. Vehicle accessibility.** Steepest grade on the approach road; number of distinct road entrances into the elevated area; cul-de-sac / dead-end status; road-network **betweenness centrality** (Kim & Wo found this positively predicts crime); **permeability** (through-street density).

**12. Escape-route count.** Number of independent egress paths within 200 m. This is the apprehension-probability channel, and on hills it is mechanically low.

**13. Viewshed / visibility.** How many other parcels can see this parcel (and vice versa). Prospect–refuge. Being high means being *seen* — a deterrent that has nothing to do with effort. Compute with a standard viewshed on the DSM.

### 5.1 DEM selection — don't get this wrong

- **Resolution:** USGS 3DEP **1 m** lidar-derived DEM where available (CONUS coverage now largely complete); fall back to 10 m NED. **30 m SRTM is unusable** — it will smooth away exactly the features you care about.
- **DTM vs DSM:** use **bare-earth DTM** for terrain/TPI. Use **DSM** for viewshed (buildings block sightlines) and for detecting retaining walls, cuts, and cliffs that affect real-world access.
- **Vertical datum:** NAVD88, meters. Record it. Mixing datums across cities silently corrupts cross-city comparison.
- **Reproject to a local projected CRS** (state plane / UTM) before computing anything neighborhood-based. Computing a 500 m radius in degrees is a classic and invisible bug.
- Terrain derived from lidar includes **built** topography: freeway cuts, embankments, retaining walls. That's a feature for accessibility, a nuisance for "natural terrain." Note which you want per-variable.

### 5.2 Handling "what if everyone's on a hill"

Three complementary answers, all already in the ladder:
1. **TPI is a deviation** — uniformly high cities are TPI≈0 everywhere. Solved by construction.
2. **Percentile-within-radius** (metric 4) is scale-free.
3. **City fixed effects** in cross-city models absorb the overall elevation level, so identification comes only from within-city variation.

### 5.3 Handling "1 ft vs 1,000 ft"

Do not force linearity. Model TPI with **splines or deciles**, and plot the dose–response curve. Theory predicts a nonlinearity: negligible effect below some threshold (a 3 m rise is nothing), rising effect through the middle, saturating at the top (once it's "a hill," more hill doesn't add much). **Finding that threshold is a result.** A linear coefficient would hide it.

---

## 6. Discriminating between mechanisms

This is the actual scientific content. Three candidate mechanisms produce the same headline correlation:

| # | Mechanism | Story |
|---|---|---|
| **M1** | **Effort** | Climbing costs calories/time; offenders substitute to flat targets. *(Your hypothesis.)* |
| **M2** | **Apprehension risk** | Hills have few escape routes, dead ends, and long sightlines. Riskier, not harder. |
| **M3** | **Confounded affluence** | Hills are rich; rich places have hardened targets, guardianship, and stable residents. Terrain is incidental. |

Plus a minor fourth: **M4 — psychological/legibility**, terrain *reads* as forbidding regardless of true cost.

### 6.1 The discriminating predictions

| Test | M1 (Effort) | M2 (Risk) | M3 (Affluence) |
|---|---|---|---|
| Effect stronger for **bulky** loot than pocketable | ✅ Yes, strongly | ➖ Weak | ❌ No |
| Effect survives in **inverted-SES cities** (poor hills) | ✅ Yes | ✅ Yes | ❌ Sign flips |
| Effect survives controlling for **escape routes/betweenness** | ✅ Yes | ❌ Attenuates to zero | ➖ Partly |
| Effect for **vehicle-borne** crime (motor vehicle theft) | ❌ Should weaken | ✅ Should strengthen | ➖ Flat |
| Effect stronger where **pedestrian** access dominates | ✅ Yes | ➖ Mixed | ❌ No |
| Effect for **perceived** vs **actual** climb (§6.3) | ❌ Actual wins | ❌ Actual wins | ➖ — |

### 6.2 ⭐ The loot-portability test (the strongest available, and nobody's done it)

If effort is real, elevation should deter theft **in proportion to how heavy the loot is**. Rank crime types by the physical work required to remove the goods:

| Rank | Crime type | Loot mass / awkwardness |
|---|---|---|
| 1 (lightest) | Theft from vehicle — phone, wallet, bag | ~0.3 kg, pocketable |
| 2 | Shoplifting / package theft | 0.5–5 kg |
| 3 | Residential burglary — jewelry, cash, small electronics | 1–10 kg |
| 4 | Bicycle theft | 10–15 kg, but *rideable downhill* — note the asymmetry |
| 5 | Catalytic converter theft | tools required, ~10 kg + jack |
| 6 (heaviest) | Burglary with large-appliance/TV/tool removal | 20–50 kg |
| — | Motor vehicle theft | loot mass irrelevant — *it drives itself away* |

**Prediction under M1:** monotonically increasing deterrent effect of TPI from rank 1 to rank 6, with motor vehicle theft as an outlier showing *little* effort penalty.
**Prediction under M3:** roughly flat across the ranking (affluence doesn't care what's heavy).

This is a clean, cheap, powerful falsification test. It requires only crime-type disaggregation you already have in the incident data. **Prioritize it.**

### 6.3 ⭐ The directional asymmetry test

Metabolic cost of ascent ≫ descent, and offenders carry loot *downhill*. So:

- Under **M1 (effort)**, the burden is on the *approach empty-handed* and the *departure loaded*. Total cost is asymmetric and depends on which end of the trip carries the mass.
- Under **M4 (psychological)**, what matters is the *visible* slope from the approach direction, not the true integrated cost.

Test: compute cost-distance **anisotropically** (separate ascent and descent cost functions), and compare model fit against a symmetric-cost specification. If asymmetric cost fits better, that's direct evidence for a genuine energetic mechanism rather than a visual/gestalt one.

Bonus: **bicycle theft is the perfect case** — the offender must pedal the loot away, so gradient enters the escape cost heavily and *positively* for an uphill escape but *negatively* downhill. Uphill neighborhoods should be safe for bikes; hilltop neighborhoods with a clean downhill run-out should be less protected than the model naively predicts.

### 6.4 The motor-vehicle-theft crux

MVT makes **opposite predictions** under M1 and M2:
- **M1:** the loot drives itself; the offender may arrive by vehicle; elevation costs nearly nothing → *weak or no deterrent effect*.
- **M2:** hilltop streets have one way out, are conspicuous, and are trivially blocked by responding units → *strong deterrent effect*.

A single crime type that cleanly separates two mechanisms is a gift. Report it prominently.

### 6.5 Mediation, not just control

Hills *cause* low street connectivity (switchbacks, dead ends, discontinuous grids). So betweenness/permeability is plausibly a **mediator**, not merely a confounder. Run a formal mediation decomposition: total effect of TPI → direct effect + effect through connectivity. Kim & Wo's significant hilliness × betweenness interaction suggests this structure is real.

---

## 7. ⭐ Study sites — a portfolio chosen to break the elevation–wealth link

The point of the city portfolio is **not** more data. It's **variation in the confound**.

### 7.1 Tier A — validation & high relief (US)
| City | Relief | Why |
|---|---|---|
| **San Francisco, CA** | ~280 m | Extreme relief, excellent open data, **replicates Kim & Wo** — validates the pipeline against a published result. Start here. |
| **Pittsburgh, PA** | ~250 m | Extreme relief, **both rich and poor hilltops**, 700+ public staircases, two funicular inclines. The best US site in the country for this question. |
| **Cincinnati, OH** | ~150 m | Basin-and-hills; Mt. Adams rich, other hillsides poor. Note: coordinates are privacy-skewed within block (§4.5). |
| **Seattle, WA** | ~160 m | Good data, strong relief, dense. |
| **Los Angeles, CA** | ~300 m+ | Huge relief range, strong SES variation across hillsides. Hundred-block geocoding. |
| **Portland, OR** | ~300 m | West Hills wealthy / east flats — a very clean SES gradient, useful as the *maximally confounded* case. |

### 7.2 Tier B — ⭐ inverted SES-elevation gradient (the decisive sites)
These are cities where **poor people live uphill**. If the effect survives here, effort/risk is real and affluence is dead as an explanation.

| City | Inversion |
|---|---|
| **La Paz / El Alto, Bolivia** | The cleanest inversion on Earth. Wealth is *low* (Zona Sur, ~3,200 m); poverty is *high* (El Alto, ~4,100 m). Elevation–income correlation is strongly **negative**. |
| **Medellín, Colombia** | Informal settlements on steep hillsides; wealthy in the valley floor (El Poblado). **Plus a natural experiment** — see §7.4. |
| **Rio de Janeiro, Brazil** | Favelas on morros, wealth on the flat coastal strip. |
| **Valparaíso, Chile** | Historic wealth low, cerros mixed; funiculars (*ascensores*) as effort-modifiers. |
| **Caracas, Venezuela** | Barrios on hillsides. Data quality is the constraint. |

Data availability is the binding limit here. Even one well-documented inverted city transforms the paper.

### 7.3 Tier C — ⭐ placebo cities (flat)
| City | Relief |
|---|---|
| **Chicago, IL** | ~20 m over the whole city |
| **Phoenix, AZ** | flat basin + isolated buttes (nice within-city contrast!) |
| **Houston, TX** | essentially flat |
| **Miami, FL** | flat, and **wealth is at low elevation** (waterfront) — a partial inversion too |

**A significant TPI effect in Chicago means your pipeline has a bug or a confound.** Run these *before* believing anything. This is a cheap, mandatory sanity gate that most spatial-crime papers skip.

Phoenix is a bonus: isolated buttes (Camelback, South Mountain) rising abruptly from a flat plain are close to your literal thought experiment.

### 7.4 ⭐ Natural experiments — the causal identification prize

Places where **effort cost changed at a known date, without terrain or wealth changing**:

1. **Medellín Metrocable (2004, 2008, …) and the Comuna 13 outdoor escalators (2011).** Gondola lifts and escalators dramatically cut the effort cost of reaching steep hillside barrios on known dates. There is already a published literature on Metrocable and violence; extending it to *property* crime with an explicit effort-cost framing is a strong, tractable paper. **Difference-in-differences.**
2. **Pittsburgh's public staircases.** 700+ city-maintained stairways, individually inventoried, with documented closures and repairs. They change *pedestrian* effort-access while leaving *vehicle* access, views, and property values untouched — near-perfect isolation of the M1 channel. Stairway closures are a natural instrument.
3. **Funiculars/inclines:** Pittsburgh's Duquesne and Monongahela Inclines; Valparaíso's ascensores (several closed and reopened over the last two decades); Los Angeles's Angels Flight (closed 2013, reopened 2017 — a clean on/off).
4. **New hillside road openings/closures**, landslide road closures, and bridge closures over ravines.
5. **Escalator/elevator installations** in hillside public housing.

If you want this to be more than correlational, item 1 or 2 is the path.

### 7.5 ⭐ Going national — the scale *is* the identification strategy

The instinct to scale this to the whole US is right, and for a better reason than "more data."

**The gap is real.** Both precedents are single-city — Breetzke has Tshwane, Kim & Wo have San Francisco. **Nobody has published a multi-city study of terrain and crime.** So a national design is not a replication with a bigger N; it is the first study of its kind, and that alone justifies it.

**But the real argument is identification.** The study's fatal threat (§4.1) is that hills are wealthy. Within a single city you can only ever *adjust* for that, and adjustment is never complete. Across cities you can **exploit** it, because the elevation–wealth correlation is not a constant — it's a city-level variable that swings from strongly positive (Portland, LA) through roughly zero (San Francisco, per the pilot) to negative (Miami, and every Tier B city in §7.2).

That gives a two-stage design that no single-city study can run:

1. **Stage one.** In each city $c$, estimate the terrain effect $\hat\beta_c$ with block-group fixed effects — exactly the pilot specification.
2. **Stage two.** Also compute $\rho_c$, the within-city correlation between relative height and income. Then regress the city-level estimates on it:

$$\hat\beta_c = \beta_0 + \lambda \rho_c + u_c$$

- $\lambda$ — the slope — is **how much of the apparent elevation effect is really affluence**. If terrain is just a proxy for money, cities where hills are richer show bigger "effects," and $\lambda$ absorbs the whole thing.
- $\beta_0$ — **the intercept — is the terrain effect at zero elevation–wealth correlation.** That is the effort/risk mechanism with the confound arithmetically removed.

Estimating $\beta_0$ requires cities spread across $\rho$. It is unobtainable from one city at any sample size. **This is the payoff, and it is what makes national scale worth the work.**

**Placebos come free.** A national sample automatically contains 20–30 near-flat cities (§7.3). No extra collection: the flat tail of the same panel is the null test.

**And a second free result.** Run the radius sweep (§5, metric 3) per city and regress the peak radius on city density, walkability, and transit share. If the offender substitution radius scales with urban form, that is a genuinely new empirical regularity about how far offenders shop for targets.

#### What "the whole US" realistically means

Be concrete about the ceiling, because it isn't 19,000 municipalities:

| Layer | Coverage | Status |
|---|---|---|
| **Elevation** | Every city. 3DEP is seamless nationally. | ✅ Solved |
| **SES controls** | All 242,296 US block groups, one keyless download. | ✅ Already downloaded |
| **Street network** | National via OSM. | ✅ Solved |
| **Crime** | ~50–100 cities publish incident-level data with coordinates. | ⚠️ **The binding constraint** |

So the honest target is a **40–80 city panel**, covering most large metros — effectively "the whole US" in every way that matters for the question, while not pretending to cover small towns that don't publish data.

**The bottleneck is not compute, it's taxonomy.** Every department names crimes differently, and the loot-mass ladder (§6.2) lives or dies on classifying them consistently. Two mitigations: lean on the **Crime Open Database**, which already harmonizes ~16 US cities into a common scheme, and hand-code the rest against the NIBRS offense codes.

⚠️ **One cross-city threat needs stating.** Reporting and recording practices differ enormously between departments, so raw crime *levels* are not comparable across cities. The design is largely immune to this: identification is **within** city (block-group FE), and stage two uses the within-city *slopes*. A department that under-records everything by 30% has its level absorbed and its slope essentially unaffected. Say this explicitly in any write-up, because it is the first objection a reviewer will raise.

#### Cost

The pilot establishes the marginal cost. Per city: a DEM pull (~10 MB, one API call), a crime pull, and roughly five minutes of compute — the terrain and modelling code is already city-agnostic and takes a bounding box, a crime feed, and a county FIPS list. **The per-city human cost is crime-taxonomy harmonization**, call it an hour or two for a city not in CODE. Sixty cities is therefore a few days of data wrangling, not months of engineering.

### 7.6 A within-building analogue (cheap consistency check)
Burglary risk by **floor number** in multi-story residential buildings is a known, documented gradient (ground floor most victimized). That is the same theory — vertical effort plus access — at a 3 m scale rather than a 300 m scale. If your estimated "cost of climbing" from terrain is wildly inconsistent with the per-floor gradient, something's wrong with the mechanism story.

---

## 8. Study design

### 8.1 Unit of analysis
**Primary: street segment** (block face between two intersections). Rationale: matches the micro-places literature (Weisburd's law of crime concentration), matches Kim & Wo for comparability, and — critically — is **robust to the geocoding degradation in §4.5**.

**Secondary/robustness:** 100 m hexagonal grid; parcel-level *only* in cities with true point geocoding.

### 8.2 Outcome and exposure
Counts of property crime by type per segment-year. Model as **negative binomial** (overdispersion is certain) with an **exposure offset** — and choose the offset carefully, because it's the difference between "risk" and "count":
- residential burglary → number of dwelling units
- theft from vehicle → estimated parked-vehicle-nights (proxy: on-street parking capacity × occupancy)
- MVT → registered vehicles
- commercial → number of business establishments

Getting the denominator wrong is the second-most-common way this study fails. Hilltops have fewer targets *because they have fewer houses per acre*, and if you don't offset, you'll "find" your effect trivially.

### 8.3 ⭐ Matched-pairs design (recommended primary specification)
More convincing than a regression coefficient, and doable entirely with public data.

Use **coarsened exact matching (CEM)** or propensity matching to pair street segments that are near-identical on:
- median household income, poverty rate, owner-occupancy, vacancy
- housing units per acre, median year built, median home value
- land-use mix, distance to CBD, distance to nearest transit stop
- road-network betweenness
- **same census block group where possible** (absorbs unobserved neighborhood effects)

…and differ **only** in TPI. Then compare crime rates within pairs.

The within-block-group variant is powerful: you're comparing the top of the hill to the bottom of the same hill, in the same neighborhood, same school district, same policing beat, same demographics. That's about as close to an experiment as terrain gets.

### 8.4 ⭐ Slope-break discontinuity design
At the **toe of a hill**, elevation changes abruptly over a short horizontal distance while neighborhood identity does not. Compare parcels/segments immediately above vs. immediately below the break in slope, within a narrow bandwidth. A regression discontinuity in TPI. Assumes no sorting exactly at the break — testable via a McCrary-style density test on housing values.

### 8.5 Regression specification
$$\log \mathbb{E}[Y_{is}] = \beta_1 \text{TPI}_{R,i} + \beta_2 \mathbf{X}^{\text{SES}}_i + \beta_3 \mathbf{X}^{\text{built}}_i + \beta_4 \mathbf{X}^{\text{access}}_i + \gamma_s + \log(\text{exposure}_i) + \epsilon_i$$

with $\gamma_s$ = block-group or neighborhood fixed effects.

**Spatial autocorrelation is not optional.** Crime clusters. Terrain clusters. Untreated, your standard errors are badly wrong and your $p$-values are fiction. Minimum acceptable: Moran's I on residuals + spatial HAC standard errors. Preferred: spatial lag/error models, or a **BYM/CAR Bayesian hierarchical model**, which handles the count structure and the spatial structure together and gives honest uncertainty.

### 8.6 Advanced: crime location choice
The methodologically strongest version is a **conditional logit / discrete choice model** over candidate targets, with effort-cost as a target attribute (Bernasco's framework). It directly models the substitution you hypothesize. **Constraint:** requires offender residence locations, which are rarely public. Flag as a stretch goal contingent on a data partnership.

### 8.7 Pre-registration
Because the confounding is severe and the temptation to garden fork is high, **pre-register** before touching outcome data: hypotheses, the metric ladder, the primary specification, the placebo cities, and the decision rule for what counts as support. OSF is free. This substantially raises the credibility of a result that will otherwise read as "guy finds correlation, tells just-so story."

---

## 9. Data sources

### 9.1 Elevation
| Source | Res. | Coverage | Notes |
|---|---|---|---|
| **USGS 3DEP 1 m DEM** | 1 m | CONUS (near-complete) | **Primary.** Lidar-derived bare earth, NAVD88 m. Via The National Map download API or the USGS AWS public bucket. |
| USGS 3DEP 10 m (NED) | 10 m | Full US | Fallback where 1 m is missing. |
| **OpenTopography** | varies | Global | Convenient API, hosts 3DEP + global DEMs. Good for international sites. |
| Copernicus DEM GLO-30 | 30 m | Global | **International sites.** Best available global option; coarse for this purpose — acknowledge as a limitation. |
| ALOS AW3D30 | 30 m | Global | Alternative global. |
| National/municipal lidar | 1 m or better | Varies | Medellín, Rio, and several Chilean cities have municipal lidar. Worth chasing for Tier B. |

⚠️ SRTM 30 m/90 m: **do not use** for the core analysis.

### 9.2 Crime
| Source | Notes |
|---|---|
| **DataSF** (San Francisco) | Incident-level, lat/lon, Socrata API. Best-in-class. |
| **Chicago Data Portal** | 2001–present, lat/lon, Socrata. Ideal placebo city. |
| **LA Open Data** | 2020–present. Hundred-block geocoding. |
| **Cincinnati (Tyler Data & Insights)** | Coordinates randomly skewed within block. |
| Seattle, Portland, Denver, Phoenix, Baltimore, NYC | All publish incident-level open data. |
| **Pittsburgh (WPRDC)** | Western PA Regional Data Center — police blotter data. **Priority site.** |
| **Crime Open Database (CODE)** | Harmonized incident data across ~10 US cities with a common category scheme. **Strongly consider — it solves the crime-type harmonization problem for you.** |
| FBI NIBRS | National, incident-level, but geography is agency-level — too coarse. |
| International | Medellín and Bogotá publish open crime data; Brazil via state SSP portals; Chile via CEAD. Quality and comparability vary — budget real time for this. |

⚠️ **Crime-type harmonization across cities is a genuine multi-week task.** Every city has its own taxonomy. The loot-portability test (§6.2) depends entirely on getting this right. CODE exists precisely for this.

### 9.3 Socioeconomic & built environment
- **ACS 5-year** (block group): income, poverty, tenure, vacancy, residential stability, age structure, education.
- **LEHD LODES**: workplace/residence employment — daytime population, a much better guardianship proxy than residential population.
- **OpenStreetMap** via `osmnx`: street network, footpaths, **stairways** (`highway=steps` — directly relevant), building footprints, land use, POIs.
- **Local parcel/assessor data**: land value, building value, year built, use code. Best single SES control available and far finer than ACS. Most large counties publish it.
- **NLCD / local land cover**: impervious surface, development intensity.
- **SafeGraph / Advan / Placer.ai** (if budget): foot-traffic — would let you *measure* pedestrian volume rather than model it. Expensive; note as an option.
- **GTFS transit feeds**: stop locations and service frequency — access channel + a strong crime correlate.

### 9.4 Terrain-modifier inventories (for §7.4)
- Pittsburgh **StepTrek / city stairway inventory** (the city maintains a formal inventory).
- OSM `highway=steps`, `aerialway=*` (gondolas), `railway=funicular`.
- Medellín Metro/Metrocable line opening dates; Comuna 13 escalator opening date.

---

## 10. Visualization plan

You asked specifically for a visual component. These are ordered by value.

### 10.1 ⭐ Bivariate choropleth — TPI × crime rate
The money visual. A 3×3 or 4×4 two-dimensional color legend where one axis is relative elevation and the other is crime rate. Reveals the four regimes at a glance:
- **high terrain / low crime** — the hypothesis
- **low terrain / high crime** — the hypothesis
- **high terrain / high crime** — the anomalies. *These are the most interesting places on the map* and worth investigating individually.
- **low terrain / low crime** — likewise

Rendered over a hillshade so the terrain is legible as terrain.

### 10.2 Hillshade + crime density overlay
Classic and immediately readable: a grayscale hillshade basemap with a semi-transparent crime KDE on top. This is the "picture that makes the argument" for a general audience.

### 10.3 ⭐ 2.5D extruded terrain, crime as color
Terrain rendered in 3D (deck.gl / kepler.gl / MapLibre terrain), with street segments extruded or colored by crime rate. Interactive tilt/rotate. This is the version that makes the hypothesis *feel* obvious to a viewer — you can literally see whether the peaks are cool-colored.

### 10.4 ⭐ The scale-sweep small multiple
A row of maps, one per TPI radius (50, 100, 250, 500, 1000, 2000 m), showing how "highness" changes meaning with scale. Pairs with:

### 10.5 ⭐ Effect size vs. radius curve
$\hat{\beta}_{\text{TPI}}$ with confidence bands, plotted against $R$. **The peak of this curve is your estimate of the offender substitution radius (§5, metric 3).** Single most novel chart in the project.

### 10.6 ⭐ The falsification plot
Dose–response: crime rate by TPI decile, one line per crime type, ordered by loot mass. Under M1 the lines fan out in mass order. Under M3 they're parallel. **This one chart is the whole §6.2 argument.**

### 10.7 Cross-city scatter
One point per city: x = within-city correlation(elevation, income), y = estimated TPI effect on crime. Under M3 (affluence), points fall on a line through the origin. Under M1/M2, the y-values cluster below zero *regardless of x*. Places the inverted cities where they can do maximum work.

### 10.8 Least-cost path visualization
Animate the accumulated metabolic cost along the cheapest walking route from a street to a hilltop parcel, annotated in kilojoules. Explanatory rather than analytic, but it makes "effort-weighted accessibility" concrete for a reader in about four seconds.

### 10.9 Matched-pair panel
For the §8.3 design: side-by-side pairs of matched segments (photo/streetview + stats), one uphill, one flat, with their crime counts. Humanizes the abstraction and is very persuasive in a talk.

**Tooling:** `matplotlib` + `rasterio` for static/publication; `folium`/`kepler.gl`/`deck.gl` for interactive; `xarray-spatial` or `richdem` for terrain derivatives; a self-contained HTML artifact for sharing.

---

## 11. Threats to validity — consolidated

| # | Threat | Severity | Mitigation |
|---|---|---|---|
| 1 | Elevation–wealth confounding | 🔴 Fatal if unaddressed | Matched pairs (§8.3), slope-break RD (§8.4), inverted cities (§7.2), parcel-level value controls |
| 2 | Coordinate degradation in open data | 🔴 High | Segment-level aggregation; audit each city's policy |
| 3 | Reporting differentials by SES | 🟠 Medium | Use crime types with high reporting rates (MVT ~ near-universal due to insurance); victimization surveys where available |
| 4 | Spatial autocorrelation → fake precision | 🟠 Medium | Spatial models / CAR-BYM, Moran's I on residuals |
| 5 | Wrong exposure denominator | 🟠 Medium | Explicit per-crime-type offsets (§8.2) |
| 6 | Target hardening co-varies with elevation | 🟠 Medium | Alarm-permit registries (many cities publish), gated-community indicators |
| 7 | MAUP (modifiable areal unit problem) | 🟡 Low-med | Report at multiple units; segment + hex + parcel |
| 8 | Edge effects at city boundary | 🟡 Low | Buffer DEM well beyond the study area before computing TPI |
| 9 | Terrain includes built features | 🟡 Low | Document DTM vs DSM choice per variable |
| 10 | Multiple comparisons across metric ladder | 🟠 Medium | Pre-register primary spec; treat the rest as exploratory and say so |
| 11 | Ecological fallacy | 🟡 Low | Frame conclusions about *places*, not *people* |

---

## 12. Roadmap

### Phase 0 — Setup ✅ done
- [x] Literature scan; identify precedents
- [x] Environment audit; geospatial stack in a project-local `.venv`
- [x] ACS block-group controls for all 242,296 US block groups, cached
- [ ] Obtain the precedent papers in full (Breetzke 2012; Kim & Wo 2023) and the 2026 bicycle-theft paper

### Phase 1 — San Francisco pilot ✅ done → see `PILOT_RESULTS.md`
- [x] DataSF incidents 2018–2025 (489k), property crime, classified by loot mass
- [x] 3DEP 10 m DEM; land mask; jurisdiction clip
- [x] Full metric ladder (§5) at six radii on a 100 m grid
- [x] ACS join; Poisson pseudo-ML with absorbed block-group FE, clustered SEs
- [x] Bivariate choropleth over hillshade, radius sweep, loot ladder, attenuation path
- **Result:** effect present at −6% to −11% per SD; **loot-mass test does not support the energy mechanism**; relative height is ~6× less wealth-confounded than absolute elevation

### Phase 1.5 — Harden the pilot ⬅ next
The pilot's limitations (`PILOT_RESULTS.md` §7) are what to fix before scaling, because every weakness gets multiplied by 60 cities.
- [ ] Redo at **street-segment** level using SF's `cnn` field — settles whether the 50 m radius peak is real or a grid artifact
- [ ] Building footprints (OSM/Microsoft) for a real exposure denominator
- [ ] Add network **betweenness + permeability**; re-test whether terrain survives (§6.5)
- [ ] Spatial-lag / BYM specification for honest intervals
- [ ] Escape-route count and viewshed — now the leading mechanisms (§6.1 M2)

### Phase 2 — Placebo & validation
- [ ] Chicago and Phoenix placebos (§7.3). **Gate: do not scale until placebos come back null.**
- [ ] Reproduce Kim & Wo's segment-level SF result as a pipeline check

### Phase 3 — Mechanism
- [x] Loot-portability dose–response (§6.2) — **run; energy mechanism not supported**
- [ ] Anisotropic cost surfaces; asymmetry test (§6.3)
- [ ] MVT crux test (§6.4) — pilot gives −6.4%, needs the escape-route control to interpret
- [ ] Mediation through connectivity (§6.5)

### Phase 4 — National panel (§7.5)
- [ ] Inventory US cities publishing incident-level data with coordinates; target 40–80
- [ ] Adopt Crime Open Database for the ~16 harmonized cities; hand-map the rest to NIBRS
- [ ] Batch DEM pulls; run the existing pipeline per city
- [ ] **Stage two: regress city-level $\hat\beta_c$ on city-level $\rho_c$.** The intercept is the headline number.

### Phase 5 — Causal identification
- [ ] Pittsburgh: stairway inventory; closures/openings as an instrument
- [ ] Medellín: Metrocable/escalator DiD
- [ ] Slope-break RD

### Phase 6 — Synthesis
- [ ] ≥1 inverted-SES city (§7.2)
- [ ] Cross-city scatter (§10.7)
- [ ] Write-up + interactive artifact

---

## 13. Open questions to resolve

1. **What's the deliverable?** Publishable paper, blog post with an interactive map, or a personal-curiosity answer? This changes how much of §8 is worth doing. (Pre-registration and spatial econometrics are essential for the first, overkill for the third.)
2. **Budget?** Zero-budget is entirely viable (everything in §9.1–9.3 is free except foot-traffic data). Confirm.
3. **Is the international arm in scope?** It's where the strongest identification lives (§7.2) and also where 80% of the data pain lives.
4. **Do you have any route to offender-residence data?** If yes, §8.6 discrete-choice becomes available and the project levels up substantially.
5. **Time horizon?** Phase 1 alone is a solid weekend-to-two-weeks. The full arc is a multi-month project.

---

## 14. References

**Direct precedents**
- Breetzke, G. D. (2012). The effect of altitude and slope on the spatial patterning of burglary. *Applied Geography*, 34, 66–75.
- Kim, Y. A., & Wo, J. C. (2023). Topography and crime in place: The effects of elevation, slope, and betweenness in San Francisco street segments. *Journal of Urban Affairs*, 45(6), 1120–1144.
- (2026). Topography, accessibility, and the built environment: Explaining spatial patterns of bicycle theft. *International Journal of Sustainable Transportation*.

**Theory**
- Brantingham, P. L., & Brantingham, P. J. (1993). Environment, routine, and situation: Toward a pattern theory of crime.
- Cohen, L. E., & Felson, M. (1979). Social change and crime rate trends: A routine activity approach. *ASR* 44(4).
- Zipf, G. K. (1949). *Human Behavior and the Principle of Least Effort.*
- Bernasco, W., & Nieuwbeerta, P. (2005). How do residential burglars select target areas? *British Journal of Criminology* 45(3).
- Weisburd, D. (2015). The law of crime concentration and the criminology of place. *Criminology* 53(2).
- Johnson, S. D., & Bowers, K. J. (2010). Permeability and burglary risk. *Journal of Quantitative Criminology* 26(1).

**Terrain & movement cost**
- Weiss, A. D. (2001). Topographic position and landforms analysis. ESRI User Conference poster. *(origin of TPI)*
- Jenness, J. (2006). Topographic Position Index extension for ArcView. *(implementation reference)*
- De Reu, J. et al. (2013). Application of the topographic position index to heterogeneous landscapes. *Geomorphology* 186.
- Tobler, W. (1993). Three presentations on geographical analysis and modeling. *(hiking function)*
- Minetti, A. E. et al. (2002). Energy cost of walking and running at extreme uphill and downhill slopes. *J. Appl. Physiol.* 93(3).
- Herzog, I. (2010/2013). Slope-dependent cost functions. *Internet Archaeology* 36.
- Looney, D. P. et al. (2023). It is not just the work you do, but how you do it: metabolic cost of walking uphill and downhill. *J. Appl. Physiol.*

**Journey to crime**
- Rengert, G. F., Piquero, A. R., & Jones, P. R. (1999). Distance decay reexamined. *Criminology* 37(2).
- Ackerman, J. M., & Rossmo, D. K. (2015). How far to travel? A multilevel analysis of the residence-to-crime distance. *JQC* 31(2).
