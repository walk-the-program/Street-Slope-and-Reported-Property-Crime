# Pilot results — San Francisco

**Status: first pass, one city. Directional, not conclusive.**
Run date: 2026-08-04 · Code in `src/` · Figures in `outputs/`

| | |
|---|---|
| Unit of analysis | 100 m grid cell |
| Cells in model | 8,178 (in 519 block groups) |
| Incidents | 323,765 property crimes, 2018 – mid-2025 |
| Elevation | USGS 3DEP, 10 m, resampled from 1 m lidar |
| Relief | −5 m to 285 m (Mt. Davidson) |
| Estimator | Poisson pseudo-ML, log-exposure offset, SEs clustered on block group |

---

## 1. Headline: the effect is real-ish, the *reason* you gave is not supported

Two findings, and they point in different directions.

**(a) Higher ground does have less property crime.** Consistently negative across every specification and every radius. Magnitude is modest: roughly a **6–11% reduction in property crime per standard deviation of relative height**.

**(b) The energy-expenditure mechanism failed its test.** The loot-mass ladder shows no gradient, and crimes with *nothing to carry* are deterred just as much as crimes with heavy loot. Details in §4. This is the most important result in the pilot and it is a negative one.

---

## 2. The attenuation path

Per +1 SD of TPI(500 m), on all property crime:

| Specification | % change | 95% CI | z |
|---|---:|---|---:|
| 1. Terrain only | **−11.3%** | −16.8 to −5.4 | −3.66 |
| 2. + SES controls (income, home value, owner share, vacancy, density) | **−10.0%** | −15.5 to −4.1 | −3.27 |
| 3. + block-group fixed effects | **−6.3%** | −12.8 to **+0.6** | −1.79 |

Read this as a robustness ladder. Row 3 is the demanding one: it compares cells *inside the same census block group*, so the comparison is the top of a hill against the bottom of the same hill — same neighbourhood, same demographics, same police beat. There is real variation to exploit (within-block-group SD of TPI is 0.47 against a citywide SD of 1.0).

The effect **survives at about half strength** and **loses conventional significance** at this radius. Honest reading: consistent with your hypothesis, not yet evidence for it.

![attenuation](outputs/04_attenuation.png)

---

## 3. ⭐ Your "relative height" instinct did something you didn't predict

Correlation with wealth, San Francisco:

| Terrain measure | vs median income | vs median home value |
|---|---:|---:|
| **Absolute elevation** | 0.107 | **0.287** |
| **Relative height (TPI 500 m)** | 0.057 | **0.047** |

Switching from absolute to relative height **cuts the wealth confound by roughly six times** on home value.

That's a bigger deal than it looks. §4.1 of the design doc flags elevation-is-priced as the study's fatal threat. It turns out that *the thing being priced is absolute elevation* — views, prestige, the address. Being locally raised relative to your immediate surroundings is nearly orthogonal to money.

So your instinct to use relative rather than absolute height isn't only a better operationalization of the concept. **It's also the single most effective confound control in the study**, and you arrived at it for unrelated reasons. Worth stating explicitly in any write-up.

Caveat: this is one city, and SF is unusual — its hills are *both* rich (Pacific Heights, Twin Peaks) and poor (Bernal, Potrero, Bayview slopes), which mutes the correlation. Other cities will differ, and that variation is exactly what §6 exploits.

---

## 4. ⭐ The falsification test — and it did not go your way

An effort mechanism predicts that elevation deters theft **in proportion to how heavy the loot is**. Estimated separately by crime class, per +1 SD TPI(500 m):

| Loot class | n | % change | 95% CI |
|---|---:|---:|---|
| 1 · pocketable (~0.3 kg) | 1,997 | −45.4% | −64.6 to −15.8 |
| 2 · light (~1–3 kg) | 112,624 | −1.0% | −11.1 to +10.1 |
| 3 · medium (~5–10 kg) | 54,979 | −14.5% | −21.2 to −7.2 |
| 4 · heavy (~10–20 kg) | 39,653 | −5.5% | −11.0 to +0.4 |
| 5 · very heavy / tools (20 kg+) | 7,929 | −18.0% | −26.4 to −8.6 |
| — motor vehicle theft *(loot self-propels)* | 41,395 | −6.4% | −12.5 to +0.1 |
| — **vandalism / arson *(nothing to carry)*** | 45,710 | **−9.7%** | −16.5 to −2.3 |

![loot ladder](outputs/03_loot_ladder.png)

**There is no gradient.** The ordering is essentially noise with respect to loot mass — the *lightest* category shows the largest effect (on few events and a very wide interval), and the second-lightest shows nothing at all.

The decisive row is the last one. **Vandalism and arson involve carrying nothing away, and they are deterred by −9.7% — squarely in the middle of the theft categories, and more strongly than heavy burglary.** If hauling goods uphill were driving this, crimes with no goods to haul should be largely unaffected. They aren't.

### What this rules out, and what it doesn't

**Weakened:** the specific "calories to carry the loot" story — that offenders decline hilltop targets because removing goods costs energy.

**Still standing:**
- **Approach cost.** Getting *there* is still work, whether or not you leave with anything. Vandalism requires the climb too. This is a version of your hypothesis, just not the carrying version.
- **Escape-route scarcity / apprehension risk** (M2). Hilltop streets have few exits and are conspicuous. This predicts deterrence of *all* crime types roughly equally — which is what we see.
- **Reduced through-traffic.** Hills carry less foot and vehicle flow, so fewer offenders pass by at all. Fewer passers-by, less crime, no decision-making required.

Note that this converges with Breetzke's Tshwane result, where **slope had no effect** — steepness is where metabolic cost lives, and it did nothing there either. Two independent studies now point away from the metabolic channel.

**The honest summary: the pattern you predicted is there. The reason you gave for it probably isn't.** That's a good outcome for a pilot — it kills one branch cheaply and redirects effort to the branches still alive.

---

## 5. At what scale does "higher" matter?

![radius sweep](outputs/02_radius_sweep.png)

| Radius | % change | 95% CI | z |
|---:|---:|---|---:|
| 50 m | −9.1% | −13.2 to −4.8 | **−4.04** |
| 100 m | −8.9% | −13.1 to −4.5 | **−3.89** |
| 250 m | −6.0% | −11.4 to −0.2 | −2.03 |
| 500 m | −6.3% | −12.8 to +0.6 | −1.79 |
| 1000 m | −7.9% | −16.0 to +0.9 | −1.76 |
| 2000 m | −10.4% | −20.5 to +1.1 | −1.79 |

The effect is **tightest and best-identified at 50–100 m** — the scale of a block or two. Point estimates rise again at 2 km but with intervals four times wider, so the apparent U-shape is not something to lean on yet.

Interpretation, tentatively: what matters is being raised relative to your **immediate block**, not sitting on a large regional plateau. That's closer to your original picture — the single house on the knoll — than to "this whole district is uphill."

⚠️ Caveat: with 100 m analysis cells, TPI at a 50 m radius is near the resolution floor. Some of the tightness at small radii may be a mechanical artifact of aligning terrain and crime at the same scale. **Rerun at parcel or street-segment level before believing the peak location.** SF publishes a `cnn` street-segment ID on every incident, so the segment version is straightforward.

---

## 6. The map

![bivariate](outputs/01_bivariate_map.png)

Teal = high ground / low crime and red = low ground / high crime are both hypothesis-consistent; the pattern is visible without squinting. The flats (SoMa, Mission, Tenderloin, the eastern waterfront) run red; the ridgelines (Twin Peaks, Mt. Davidson, Bernal, Potrero, Pacific Heights) run teal.

The **dark cells — high ground *with* high crime — are the ones worth chasing.** Those are where the hypothesis fails locally, and they should be inspected individually rather than averaged away.

---

## 7. Limitations of this pilot

Real ones, in rough order of how much they should temper the above:

1. **One city.** SF's terrain is unusual, and its elevation–wealth relationship is unusually muted. Nothing here generalizes yet.
2. **Crude exposure denominator.** Housing units and population apportioned from block groups by area. Theft from vehicle in particular wants parked-vehicle-nights, not dwellings. Building footprints would be a large improvement and are available from OSM.
3. **No street-network controls.** Betweenness and permeability are absent, and Kim & Wo found betweenness matters and interacts with hilliness. Until those are in, some of the "elevation" effect is probably connectivity.
4. **No spatial autocorrelation model.** SEs are clustered on block group, which helps, but a CAR/BYM or spatial-lag specification is the right treatment. Current intervals are likely still too narrow.
5. **Grid cells, not street segments.** Chosen for national portability; the segment version is more defensible and is available in SF.
6. **Reported crime only** — §4.4 of the design doc.
7. **Exploratory, not pre-registered.** Several specifications were run. Treat every p-value here as descriptive.

---

## 8. What the pilot proved about feasibility

Aside from the substance: **the pipeline works and it is city-agnostic.** From a bare directory to fitted models and figures took one session, and the only city-specific inputs are a bounding box, a crime feed, and a county FIPS code. Terrain, SES, and modelling code are already national.

Per-city marginal cost is a few minutes of compute plus whatever it takes to harmonize that city's crime taxonomy — which is the real bottleneck, and the reason §6 of `RESEARCH.md` leans on the Crime Open Database.
