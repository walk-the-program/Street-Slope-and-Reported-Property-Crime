# Crime-type classifier validation

`src/crime_classes.py` at sha256 `a7add5321821`. Sample and codes in `outputs/classifier_validation.csv`. The hash covers the file as delivered, i.e. including the newly added `classify_text_v2`; `classify_text` itself is byte-identical to the version that produced every existing result.

## What was tested

The unit is the string the classifier is actually given, which is the concatenation of each registry's first three description fields, not a single raw field. The sampling frame is every distinct such string in all 31 registry cities, pulled by group-by count from each portal: 168,183 distinct strings covering 9,454,448 incidents.

Two samples were drawn and hand-coded against the class definitions in the module docstring:

* **primary**, 403 strings (6 ambiguous, 397 scored) -- one certainty draw per city, a PPS draw on sqrt(incidents), and equal-size strata over the classifier's own predicted label so every class has support.

* **holdout**, 108 strings (10 ambiguous, 98 scored), disjoint from the primary sample and drawn after it. `classify_text_v2` was written from the primary sample's errors, so only the holdout measures v2 honestly. Both numbers are reported.

Ambiguous strings are those where the concatenated fields name two unrelated offences and neither is clearly primary. They are excluded from the matrices and discussed under failure pattern 7.


## Headline accuracy

| classifier | sample | string-level | 95% CI | incident-weighted |
|---|---|---|---|---|
| classify_text (as deployed) | primary | 0.922 | 0.891-0.944 | 0.968 |
| classify_text (as deployed) | holdout | 0.857 | 0.774-0.913 | 0.937 |
| classify_text_v2 *(in-sample)* | primary | 0.997 | 0.986-1.000 | 1.000 |
| classify_text_v2 | holdout | 0.959 | 0.900-0.984 | 0.992 |

Incident-weighted accuracy is higher than string-level throughout because the errors concentrate in mid-frequency wording, not in the handful of strings that carry most of the volume.


## Confusion matrix, `classify_text` as deployed (both samples pooled)

Rows are the hand code, columns the classifier.

```
pred_deployed  MASS_1  MASS_2  MASS_3  MASS_4  MASS_5  MVT  NO_LOOT  ROBBERY  OTHER
truth                                                                              
MASS_1             32       0       2       0       0    0        0        0      0
MASS_2              0      40       2       2       0    1        0        0      0
MASS_3              0       0      35       0       0    0        0        0      0
MASS_4              0       0       0      35       0    0        0        0      0
MASS_5              0       0       0       6      33    1        0        0      0
MVT                 0       0       0       0       0   33        0        0      1
NO_LOOT             0       0       0       0       0    0       43        0      0
ROBBERY             4       0       0       0       0    0        0       42      0
OTHER               0       1      21       1       0    1        2        0    157
```

### Per-class, `classify_text`

```
  class  support_strings  support_incidents  precision  recall    f1
 MASS_1               34               7085      0.889   0.941 0.914
 MASS_2               45             626261      0.976   0.889 0.930
 MASS_3               35             762515      0.583   1.000 0.737
 MASS_4               35             285527      0.795   1.000 0.886
 MASS_5               40             137891      1.000   0.825 0.904
    MVT               34             379658      0.917   0.971 0.943
NO_LOOT               43             372970      0.956   1.000 0.977
ROBBERY               46             124376      1.000   0.913 0.955
  OTHER              183            1547245      0.994   0.858 0.921
```

### Per-class, `classify_text_v2`

```
  class  support_strings  support_incidents  precision  recall    f1
 MASS_1               34               7085      1.000   1.000 1.000
 MASS_2               45             626261      0.978   1.000 0.989
 MASS_3               35             762515      1.000   1.000 1.000
 MASS_4               35             285527      0.972   1.000 0.986
 MASS_5               40             137891      1.000   0.975 0.987
    MVT               34             379658      0.971   1.000 0.986
NO_LOOT               43             372970      0.956   1.000 0.977
ROBBERY               46             124376      1.000   1.000 1.000
  OTHER              183            1547245      1.000   0.978 0.989
```


## NO_LOOT, the control class

Precision 0.956, recall 1.000 over 43 hand-coded NO_LOOT strings carrying 372,970 incidents. **No systematic misclassification was found in NO_LOOT.** Recall is 1.000 in both samples: every string a coder called vandalism, criminal damage, malicious mischief, graffiti or arson was classified NO_LOOT.

The single false positive in each sample is the same kind of record: a multi-offence report whose primary offence is not property damage but whose charge list contains one that is (Pittsburgh `2701 Simple Assault. / 2706 Terroristic Threats. / 3304 Criminal Mischief. SIMPLE ASSAULT/INJURY`), and a negation the regex cannot see (Montgomery County `All Other Offenses 9104 FIRE (NOT ARSON)`). Neither is a NO_LOOT-specific defect and neither is directional with respect to terrain, so the central control survives this audit.

One caveat that is specific to NO_LOOT and is *not* visible in the matrix above: NO_LOOT recall depends entirely on separator normalisation, which lives in `harvest_arcgis.norm_text` and therefore protects only ArcGIS cities. On raw strings Denver's `criminal-mischief-mtr-veh public-disorder` (28,479 incidents) falls through to OTHER. Any future Socrata city that publishes slugs would lose its NO_LOOT counts silently. `classify_text_v2` moves the normalisation inside the classifier so the guarantee no longer depends on which harvester read the city.


## Failure patterns

Ordered by sampled incident volume.


**1. Financial offences on the loot ladder (largest error by volume).** The `MASS_3` rule matches the bare words `larceny|theft|stolen property|embezzle`, so identity theft, embezzlement, theft of services, unauthorised use of a financial device and receiving/possessing stolen property all land on rung 3 of a ladder whose entire content is the weight of goods carried away. MASS_3 precision is 0.625 in the primary sample. Examples: `Identity Theft EXTORTION/FRAUD/FORGERY/BRIBERY (INCLUDES BAD CHECKS) ALL OTHER` (Seattle, 15,063), `Identity Theft` (Charlotte, 9,184), `Stolen Property Offenses` (Charlotte, 6,394), `II Initial Stolen Property` (San Francisco, 3,433), `Embezzlement` (Charlotte, 2,743), `DECEPTIVE PRACTICE THEFT OF LABOR/SERVICES RESIDENCE` (Chicago). Possession offences are worse than merely weightless: the recorded location is where a possessor was stopped, not where anything was taken, so they carry no information about the terrain of a theft site at all.


**2. A regex match that exists only across a field seam.** Denver publishes offence and category as two slugs. After normalisation `theft-items-from-vehicle theft-from-motor-vehicle` reads `theft items from vehicle theft from motor vehicle`, and the join between the two fields spells `vehicle theft`, which the MVT rule matches. Either field on its own classifies correctly. This moved 37,916 theft-from-vehicle and 23,973 auto-parts incidents into MVT -- the one class where the effort and escape-route mechanisms make opposite predictions, and therefore the worst possible place to leak 62k incidents. No tightening of the MVT rule can fix this; only ordering the specific patterns ahead of it makes the seam unreachable.


**3. Vehicle burglary read as building burglary.** Nashville records theft from a car as `BURGLARY - MOTOR VEHICLE` (8,193) and Boise as `VEHICLE BURGLARY - THEFT FROM A VEHICLE` (1,155). The generic `burglar` alternative fires before the from-vehicle rule, so a rung-2 offence is counted as rung 4. Louisville's `CONTENTS FROM VEH` (2,011) and Cambridge's `Larceny from MV` miss the from-vehicle rule for a different reason: `from motor veh` is covered but bare `from veh` and `from MV` are not.


**4. The commercial/residential burglary boundary, and the NIBRS merge.** MASS_5 requires the literal wording `burglary-commercial`, `commercial burglary`, `burglary business` or `non-residential burglary`. It misses `B & E, COMMERCIAL` (Prince George's, 2,025), `Burglary - Non Resid` (Kansas City, 962), `BREAKING OR ENTERING - FELONY - BUSINESS` (Asheville, 736), `BURGLARY - FORCED ENTRY-NONRESIDENTIAL` (Montgomery, 3,049) and `BURGLARY (NON HABITATION)` (Nashville, 927), all of which fall to MASS_4. This compresses the top of the ladder, biasing the mass gradient toward zero.
Separately and not fixable in regex: NIBRS 220 is published by Charlotte, Seattle, Tacoma, Long Beach, Kansas City, Montgomery County and Asheville as a single `Burglary/Breaking & Entering` category that merges residential and commercial. Those incidents can only be coded MASS_4 (`Burglary - Other`), so for those cities the 4/5 contrast is not measured at all -- it is diluted, not wrong. That is a data limitation to state in the paper, not a classifier bug.


**5. Forcible purse-snatching classified as pocketable theft.** `purse.?snatch` is tested before the robbery rule, so `robbery-purse-snatch-w-force robbery` (Denver), `ROBBERY - FORCIBLE PURSE SNATCHING` (Montgomery) and `Robbery - Purse Snatching (Force)` (Tacoma) enter MASS_1. A forcible snatch is a robbery by definition. Related: `Larceny from Person` (NIBRS's parent of pocket-picking and purse-snatching) falls through to MASS_3 rather than joining its two children on rung 1.


**6. Words that look like offences but are not.** New York City's summons file contains `BICYCLE INFRACTION (COMMERCIAL)`, a traffic citation, which the bare `bicycle` alternative counts as a rung-4 property crime (411), and `UNREASONABLE NOISE; FROM CAR MUFFLER/EXHAUST` (927), which the from-vehicle rule counts as rung 2. Montgomery County's `FIRE (NOT ARSON)` (392) is read as arson. Prince George's `AUTO, STOLEN` (15,392) is the mirror image -- a real vehicle theft the MVT rule misses because it only knows `stolen vehicle`, not the inverted form.


**7. Multi-offence records, which are not a regex problem.** 16 of 511 sampled strings (3.1%) name two or more unrelated offences with no clear primary and were recorded ambiguous rather than forced. They cluster hard: 9 of the 16 are Boise, whose three fields (charge, incident type, crime code) frequently disagree outright -- `BURGLARY-COMMERCIAL UNDER $300 (M)- 1ST TIME OFFENSE Battery Shoplifting` names three different crimes. Pittsburgh concatenates every charge on a report and appends a UCR hierarchy field that is the authoritative primary offence; the classifier reads the whole string and can match a secondary charge instead. Any city where this is common should have its description fields narrowed at the registry level, not its regexes patched.


## Two problems found upstream of the classifier

Both are registry field-selection bugs, not `classify_text` defects, but both were surfaced by this audit and both are load-bearing.

* **Los Angeles has no offence text.** `registry.csv` sets `all_desc = weapon_desc;premis_desc;vict_descent;crm_cd_desc;...` and `harvest.fetch_crime` takes the first three, so the classifier is fed weapon, premise and victim descent while the actual offence field `crm_cd_desc` is truncated away. Sampled strings read `STRONG-ARM (HANDS, FIST, FEET OR BODILY FORCE) SINGLE FAMILY DWELLING H`. This is why Los Angeles fails harvest with 'only N classified property crimes'; the city is currently absent from the analysis for a fixable reason.

* **Gainesville has no offence text either**, and worse: its three fields are `offense_day_of_week;offense_date;offense_hour_of_day`, so every string is a weekday and a timestamp. It was excluded from the sampling frame because there is nothing to hand-code. Cambridge is a milder version -- `crime;crime_date_time` -- where the offence is present but every string carries a unique timestamp, which is why it shows 50,000 'distinct' descriptions. All three cities currently fail harvest, so no published result is affected, but the discovery step that chose these fields will make the same mistake on the next city.


## Proposed fix: `classify_text_v2`

Added to `src/crime_classes.py` as a separate function. Nothing imports it; `classify_text` is untouched and every existing result remains reproducible. Changes address patterns 1-6; pattern 7 is out of reach of any text rule.

| | primary (tuned on) | holdout (honest) |
|---|---|---|
| `classify_text` | 0.922 | 0.857 |
| `classify_text_v2` | 0.997 | 0.959 |
| errors removed | 30 of 31 | 10 of 14 |

Zero regressions in either sample: no string that `classify_text` got right is broken by v2. The honest figure is the holdout column -- **85.7% to 95.9% string-level, 93.7% to 99.2% incident-weighted**. The primary-sample figure is an in-sample fit and should not be quoted.

Four errors survive v2 on the holdout, all of them hard: `BURGLARY (NON HABITATION)` (unseen wording for non-residential), `FIRE (NOT ARSON)` (negation), `UNREASONABLE NOISE; FROM CAR MUFFLER` (offence-like words in a non-offence), and one Pittsburgh multi-charge record. They were deliberately left unfixed: patching them would tune on the holdout and destroy the only unbiased estimate available.


### What switching to v2 would do to the corpus

Applying both classifiers to every distinct string in the 15 cities that are actually built into `data/interim/cells`:

```
              v1       v2   delta   pct
MASS_1     22357    21885    -472  -2.1
MASS_2    526006   548343   22337   4.2
MASS_3   1217496  1084400 -133096 -10.9
MASS_4    352633   330328  -22305  -6.3
MASS_5     87258    98038   10780  12.4
MVT       409403   409644     241   0.1
NO_LOOT   588609   592542    3933   0.7
ROBBERY   179825   181574    1749   1.0
OTHER    3231883  3348716  116833   3.6
```

Largest reclassification flows:

```
v1       v2     
MASS_3   OTHER      132571
OTHER    MVT         16589
MVT      MASS_2      11559
MASS_4   MASS_2      11128
         MASS_5      10767
MVT      NO_LOOT      4314
MASS_3   ROBBERY       520
MASS_1   ROBBERY       470
MVT      OTHER         436
MASS_4   ROBBERY       300
NO_LOOT  ROBBERY       253
MASS_2   ROBBERY       179
         OTHER         171
NO_LOOT  OTHER         128
```

**NO_LOOT moves by +3,933 incidents (+0.7%)**, which is the number that matters most: the control class is essentially unchanged, so the central comparison does not rest on the classifier version. The large moves are MASS_3 shedding financial offences to OTHER and the MASS_4/MASS_5 boundary being drawn where the data says it should be.


## Recommendation

1. The headline NO_LOOT control is sound. Report NO_LOOT precision 0.96 / recall 1.00 in the paper's measurement section.

2. Re-estimate the loot-mass ladder under v2 before submission and report both. The MASS_3 and MASS_4/MASS_5 changes are large enough to move the ladder, and the Denver seam bug alone misroutes 62k incidents into MVT.

3. Fix the Los Angeles and Gainesville registry field selection, or state explicitly that those cities are excluded for a data-plumbing reason rather than a substantive one.

4. State the NIBRS 220 residential/commercial merge as a measurement limitation. Seven cities cannot distinguish rung 4 from rung 5 at all, which attenuates the top of the ladder toward the null.

