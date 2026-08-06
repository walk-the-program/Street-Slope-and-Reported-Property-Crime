# Direction: *Slope Deters Property Crime, But Not Because Climbing Is Hard*

**Target: PLOS ONE.**
Decided 2026-08-04, after three mechanism tests and one failed theory of my own.

---

## The paper in one paragraph

Steeper streets carry less crime. Haberman & Kelsay (2021) showed this for robbery in Cincinnati and named three possible reasons — physical cost, hard escape, low usage — without testing between them. We generalise the finding to property crime across nine cities and test all three. **All three fail.** The decisive test is a control the literature has never used: **vandalism and arson, crimes in which nothing is carried away.** They hold the cost of *approach* fixed and set the cost of *removal* to exactly zero, so an effort mechanism requires them to be markedly less deterred. They are not — and where a difference is detectable it runs the wrong way. Whatever slope is doing, it does not act through the work of removing goods.

---

## Why this is publishable, new, and not derivative

**Nobody has tested mechanism.** Breetzke (2012, Tshwane), Haberman & Kelsay (2021, Cincinnati) and Kim & Wo (2023, San Francisco) all report a terrain–crime association and attribute it to physical cost, escape difficulty or low usage in their discussions. None operationalises any of them, and none has a design that could distinguish between them. Haberman & Kelsay state all three explicitly as open questions — this paper answers them.

**The no-loot control is a genuinely novel identification device.** It is not a robustness check; it is a within-design placebo for one specific channel. Approach effort is held constant, removal effort is set to zero, and everything else about being in that place — visibility, escape routes, guardianship, land value — is held roughly fixed. That comparison isolates the carrying channel more cleanly than any covariate adjustment could, and it costs nothing but a crime-type split.

**It is a multi-city design in a literature with none.** Every prior result is a single city; ours is nine, with the slope finding generalised from robbery to property crime.

**PLOS ONE explicitly publishes rigorous negative results,** which is the right home for a well-powered refutation. The venue choice is a feature, not a fallback.

---

## Core result

![no-loot control](outputs/20_noloot_control.png)

Effect of +1 SD of relative height (TPI 500 m), within block group, SES-controlled:

| City | Theft (goods carried) | Vandalism / arson (nothing carried) | Gap |
|---|---:|---:|---:|
| San Francisco | −9.40% | −12.27% | +2.9 |
| Chicago | −0.14% | −6.86% | +6.7 |
| Kansas City | +1.40% | +1.86% | −0.5 |
| Montgomery County MD | +21.67% | +18.01% | +3.7 |

The two series track each other closely in every city, including the cities where the terrain effect runs the "wrong" way. **In three of four, the crime with nothing to carry is deterred *more*.** An effort mechanism cannot produce this.

## The three failed tests, together

| # | Prediction of the effort mechanism | Result |
|---|---|---|
| 1 | Deterrence should scale with loot mass | No gradient across a 5-level loot-mass ladder |
| 2 | The coefficient should rise, and may flip sign, with loot mass (heavy goods travel downhill) | Slope −0.0018/kg, CI [−0.010, +0.018] |
| 3 | **Crimes with nothing to carry should be unaffected** | **Deterred equally, or more, in 4/4 cities** |
| 4 | Motor vehicle theft, whose loot self-propels, should be least affected *because removal is free* | It is the least deterred category — but that also fits a denominator artifact |

Prediction 2 was my own — a directional round-trip model in which a hilltop is costly to approach but cheap to leave loaded, so the terrain coefficient should reverse sign for heavy goods. It is a better version of the effort theory than the field's, and it is also wrong.

---

## Secondary contributions (methodological, all needed anyway)

1. **Relative height is far less confounded than absolute elevation.** Correlation with median home value in San Francisco: absolute elevation **0.287**, TPI **0.047** — roughly a sixfold reduction. Elevation is capitalised into land value; *local* elevation deviation is close to orthogonal to it. Anyone studying terrain and crime should use the deviation, and no one has said so.

2. **Low-relief cities manufacture spurious terrain effects.** Baton Rouge spans 15.9 m of relief — one SD of TPI is **0.98 m** — and returns **+22.9% (z = 3.1)**. At that scale a bare-earth DEM is measuring levees, highway embankments, and fill, not terrain, and those track land use. **A relief floor is a necessary inclusion criterion**, and the field has none.

3. **Directional movement costs are not identifiable from a raster.** Approach cost and loaded-escape cost are both functions of the same gradient field and correlate at r = −0.80 with TPI. Separating them requires an asymmetric *network* — stairways, one-way access, walls — not a DEM. This is why test 2 above cannot be rescued with more data, and it is worth stating so others do not repeat it.

4. **Jurisdiction clipping.** Clipping crime data to counties gives a city police department vast areas it does not report on (Marin: 1,313 km², 99% of cells empty). Block-group fixed effects absorb most of it, but the diagnostic belongs in the record.

---

## What survives as the explanation

Presence and exposure were the leading candidates, and they were **measured and rejected**:
betweenness, intersection density, permeability, egress count and walk/drive ratio leave the
slope coefficient untouched.

What remains is that the effect may be **partly definitional**: steep streets hold fewer
parked vehicles, curb cuts and accessible frontages per unit of measured housing, so they
present fewer targets per unit of nominal exposure. Motor vehicle theft being the least
deterred category points this way, since vehicles are exactly what a housing denominator
misstates. This is the largest open question in the paper and is being tested with
target-level exposure (parking capacity, entrance counts).

---

## Build order

- [x] Multi-city pipeline, 11 cities
- [x] Loot-mass ladder and the three mechanism tests
- [x] No-loot control replicated in 4 cities
- [x] Pre-registration written before the confirmatory dataset existed, with deviations itemised
- [x] Street segments (San Francisco) with network measures
- [x] Building-footprint exposure denominators — halved Montgomery County's estimate
- [x] Network measures: betweenness, permeability, egress count — **mediation rejected**
- [x] Gradient floor, confirmed out-of-sample by Baltimore and Charlotte
- [x] Panel extended to nine cities incl. Pittsburgh, Seattle, Baltimore, Charlotte
- [ ] Spatial-lag / CAR specification for honest intervals
- [ ] Target-level exposure (parking capacity, entrance counts) — the open question
- [ ] Segments in Seattle, Cincinnati, Pittsburgh
- [ ] Classifier validation and DEM resolution sensitivity

**Scope discipline:** the panel got worse as it got wider. Five or six cities with genuine relief and clean jurisdictions beat eleven contaminated ones. Narrow and deep.


---

## Course corrections, recorded

Two claims in earlier drafts of this document were wrong and are retracted here.

**"Nobody has found a slope effect."** Wrong. Haberman & Kelsay (2021, *Journal of
Quantitative Criminology*) established slope→robbery in Cincinnati at roughly 7.9% per
degree, close to our property-crime estimate. Our literature scan was too narrow — it
searched on elevation and altitude, and missed the paper that used the word *topography*
with slope as the treatment. The contribution is generalisation plus mechanism, not
discovery. Usefully, Haberman and Kelsay name our exact three mechanisms in their conclusion
and test none of them, so the paper now answers a question posed explicitly in the prior
literature, which is a better position than claiming novelty.

**"The effect is a constant (I² = 0.00)."** Withdrawn. That rested on three cities and a Q
test with two degrees of freedom. Pittsburgh, arriving out-of-sample, moved heterogeneity to
I² = 0.86. We had flagged the k = 3 power problem for a different test and failed to apply
it to the headline.

Both corrections make the paper weaker and more defensible. Neither changes the mechanism
findings, which were always the point.
