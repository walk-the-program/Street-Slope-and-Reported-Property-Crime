"""Crime taxonomy for the mechanism tests.

The point of this file is the `loot_mass` ordering. An effort mechanism should
deter theft in proportion to the physical work of removing the goods; an
affluence confound should not care what the goods weigh. So the ordering below
is the study's main falsification test, and it has to be defined before looking
at any outcome.

Two classes sit outside the ordering deliberately:

  MVT       motor vehicle theft. The loot drives itself away, so the removal
            cost of a hill is nil. Effort predicts a weak elevation effect;
            escape-route scarcity predicts a strong one. The two mechanisms
            disagree on this single crime type, which is what makes it useful.

  NO_LOOT   vandalism and arson. Property crime with nothing to carry. Isolates
            the cost of *approach* from the cost of *removal*: if elevation
            deters these as much as it deters theft, the carrying story is
            wrong and something else (risk, affluence) is doing the work.
"""

# rank 1 = pocketable ... 5 = heavy/awkward
LOOT_MASS = {
    "Larceny Theft - Pickpocket": 1,
    "Larceny Theft - Purse Snatch": 1,
    "Larceny - From Vehicle": 2,
    "Theft From Vehicle": 2,
    "Larceny Theft - Shoplifting": 2,
    "Larceny Theft - From Building": 3,
    "Larceny Theft - Other": 3,
    "Burglary - Residential": 4,
    "Burglary - Hot Prowl": 4,
    "Burglary - Other": 4,
    "Larceny Theft - Bicycle": 4,
    "Larceny - Auto Parts": 5,
    "Burglary - Commercial": 5,
}

MASS_LABEL = {
    1: "1 pocketable (~0.3 kg)",
    2: "2 light (~1-3 kg)",
    3: "3 medium (~5-10 kg)",
    4: "4 heavy (~10-20 kg)",
    5: "5 very heavy / tools (20 kg+)",
}

SPECIAL = {
    "Motor Vehicle Theft": "MVT",
    "Motor Vehicle Theft (Attempted)": "MVT",
    "Vandalism": "NO_LOOT",
    "Arson": "NO_LOOT",
}

# Robbery is person-directed and confounded with street activity; kept in the
# data as a contrast class but excluded from the loot-mass ladder.
CONTRAST = {
    "Robbery - Street": "ROBBERY",
    "Robbery - Other": "ROBBERY",
    "Robbery - Commercial": "ROBBERY",
    "Robbery - Residential": "ROBBERY",
    "Robbery - Carjacking": "ROBBERY",
}


def classify(subcategory: str):
    """Return (analysis_class, loot_mass_rank or None)."""
    if subcategory in LOOT_MASS:
        return f"MASS_{LOOT_MASS[subcategory]}", LOOT_MASS[subcategory]
    if subcategory in SPECIAL:
        return SPECIAL[subcategory], None
    if subcategory in CONTRAST:
        return CONTRAST[subcategory], None
    return "OTHER", None


# --- generic cross-city classifier ---------------------------------------
# Every department names offenses differently ("LARCENY - FROM MOTOR VEHICLE",
# "THEFT F/AUTO", "BURGLARY/BREAKING & ENTERING"), so the multi-city pipeline
# matches on text rather than on an exact code table. Rules are ordered: the
# first match wins, most specific first.
import re as _re

# `_NOT_WHOLE_CAR` is why the MVT rule is not simply "theft of motor vehicle".
# NIBRS 23G is "Theft of Motor Vehicle Parts or Accessories" and 24I is "Theft
# of Motor Vehicle License Plate"; both begin with the same words as 24O "Motor
# Vehicle Theft" and both were landing in MVT. That silently merged the one
# class where the two mechanisms make opposite predictions (the loot drives
# itself away) with the heaviest rung of the loot ladder -- in Seattle, 32,501
# parts thefts against 50,824 real vehicle thefts, and MASS_5 came out empty.
_NOT_WHOLE_CAR = r"(?!\s*(part|accessor|licen|plate|tag))"

_RULES = [
    # Vehicle burglary is a rung-2 theft from a car, not a rung-4 building
    # burglary, and it has to be tested before both the MVT and the burglary
    # rules: Los Angeles calls it "BURGLARY FROM VEHICLE" (63,515 records) and
    # Nashville "BURGLARY - MOTOR VEHICLE".
    ("MASS_2",  r"(burglary[\s,\-]*(from|of)?[\s,\-]*(a )?(motor )?vehicle|"
                r"vehicle burglary|burglary\s*-\s*motor vehicle)"),
    # `_INVERTED_MVT` catches departments that write the noun first: Los Angeles
    # publishes motor vehicle theft as "VEHICLE - STOLEN" (115,184 records) and
    # Prince George's as "AUTO, STOLEN". Neither contains "stolen vehicle" in
    # that order, so both fell to OTHER and the city lost its MVT class
    # entirely. The separator class is deliberately narrow so that a sentence
    # merely containing both words cannot match across a field seam.
    ("MVT",     r"(motor vehicle theft|auto theft|vehicle theft|stolen (motor )?vehicle|"
                r"(motor ?)?(vehicle|auto)[\s,\-]+(attempt )?stolen|"
                r"theft of (a )?(motor )?vehicle" + _NOT_WHOLE_CAR + r"|gta\b|veh theft|"
                r"larceny of motor vehicle" + _NOT_WHOLE_CAR + r")"),
    # "criminal damag" not "criminal damage": Ohio charges the offense as
    # CRIMINAL DAMAGING/ENDANGERING, which is 33,149 of Cincinnati's records and
    # was falling through to OTHER. NO_LOOT is the study's control class, so
    # losing it in a city is worse than losing any single loot rung.
    ("NO_LOOT", r"(vandal|criminal damag|malicious mischief|arson|graffiti|"
                r"destruction of property|damage to property|criminal mischief)"),
    # NIBRS 23A is worded "Pocket-picking", not "pickpocket"
    ("MASS_1",  r"(pickpocket|pick-pocket|pocket.?pick|purse.?snatch)"),
    ("MASS_5",  r"(catalytic|auto part|vehicle part|burglary.?-?\s*commercial|"
                r"commercial burglary|burglary business|non.?residential burglary)"),
    ("MASS_4",  r"(burglar|breaking and entering|b\s*&\s*e\b|bicycle|bike theft)"),
    # `f[\s/]*auto` rather than the literal `f/auto`: separator normalisation
    # collapses the slash, so "THEFT F/AUTO" arrives as "THEFT F AUTO" and the
    # literal stops matching, dropping a theft-from-vehicle to the generic rung.
    ("MASS_2",  r"(from (a )?(motor )?vehicle|from auto|\bf[\s/]*auto\b|from car|shoplift|"
                r"retail theft|theft from (a )?person|from motor veh|larceny from mv\b)"),
    ("MASS_3",  r"(larceny|theft|stolen property|embezzle)"),
    ("ROBBERY", r"(robbery|carjack)"),
]
_COMPILED = [(k, _re.compile(p, _re.I)) for k, p in _RULES]
_MASS_OF = {f"MASS_{i}": i for i in range(1, 6)}


def classify_text(text: str):
    """Classify a free-text offense description from any city."""
    t = str(text or "")
    for klass, rx in _COMPILED:
        if rx.search(t):
            return klass, _MASS_OF.get(klass)
    return "OTHER", None


# --- candidate replacement, not yet used by the pipeline -------------------
# `classify_text_v2` exists because a 403-string hand-coded audit (see
# outputs/classifier_metrics.md) found five systematic errors in the cascade
# above. It is kept separate so that every result already produced remains
# reproducible from `classify_text`; nothing imports v2 until the ladder is
# re-estimated under both.
#
# What changed, and why each change is a correction rather than a preference:
#
#  1. Separator normalisation moved inside the classifier. `harvest_arcgis`
#     already does this on its own path, so ArcGIS cities are protected and
#     Socrata cities are not -- the same string classifies differently
#     depending on which harvester read it. Doing it here makes the function
#     total. The `f/auto` alternative has to gain a spaceless twin, because
#     normalising is what breaks it: Washington DC's "THEFT F/AUTO" becomes
#     "THEFT F AUTO" and stops matching.
#
#  2. Fraud, forgery, identity theft, embezzlement, theft of services and
#     receiving/possessing stolen property are routed to OTHER ahead of
#     everything else. They were landing in MASS_3 on the bare word "theft",
#     which put 33k sampled incidents with no physical goods on the middle rung
#     of a ladder whose whole content is the weight of goods carried away.
#     Possession offences are worse than merely weightless: the recorded
#     location is where a possessor was stopped, not where anything was taken,
#     so they carry no information about the terrain of the theft site.
#
#  3. The from-vehicle and vehicle-parts rules now run *before* MVT. Denver
#     publishes offence and category as two slugs that concatenate into
#     "theft items from vehicle theft from motor vehicle", and the seam between
#     the fields spells "vehicle theft", which the MVT rule matched. Either
#     field alone classifies correctly; only the join was wrong. Ordering the
#     specific patterns first makes the seam unreachable, which no amount of
#     tightening the MVT rule would do.
#
#  4. Vehicle burglary is MASS_2, not MASS_4. Nashville records theft from a
#     car as "BURGLARY - MOTOR VEHICLE" and Boise as "VEHICLE BURGLARY"; the
#     generic `burglar` rule claimed both for the heavy rung.
#
#  5. Robbery outranks purse-snatching, and larceny-from-person joins
#     pickpocketing on rung 1. A forcible purse snatch is a robbery by
#     definition, and NIBRS 23A/23B (pocket-picking, purse-snatching) are the
#     two children of larceny-from-person, so the parent belongs with them.
#
# Also widened: commercial burglary (was missing "B & E, COMMERCIAL",
# "BURGLARY - NON RESID", "BREAKING OR ENTERING ... BUSINESS"), and MVT (was
# missing Prince George's County's "AUTO, STOLEN").

_SEP_V2 = _re.compile(r"[-_/|]+")

# Bicycle wording alone is not theft. New York City's summons file contains
# "BICYCLE INFRACTION (COMMERCIAL)", a traffic citation, which the bare
# `bicycle` alternative was counting as a rung-4 property crime.
_THEFT_CTX = _re.compile(r"(theft|larceny|stolen|steal|tbut|burglar|taking)", _re.I)

_FINANCIAL = (r"(identity theft|ident theft|theft of (labor|service)|embezzle|"
              r"forgery|counterfeit|credit card|wire fraud|bank fraud|"
              r"false pretens|swindle|confidence game|white.collar|"
              r"unauth\w*\s+use\s+of\s+(a\s+)?(credit|debit|financial|access|card|"
              r"device|ftd)|"
              r"stolen property\s*(offense|buy|sell|rec|possess)|"
              r"(receiv|possess|buy|sell)\w*\s+stolen property)")

_RULES_V2 = [
    ("OTHER",   _FINANCIAL, None),
    ("ROBBERY", r"(robbery|carjack)", None),
    ("NO_LOOT", r"(vandal|criminal damag|malicious mischief|arson|graffiti|"
                r"destruction of property|damage to property|criminal mischief)", None),
    ("MASS_1",  r"(pickpocket|pick-pocket|pocket.?pick|purse.?snatch|"
                r"(larceny|theft)\s+from\s+(a\s+)?person)", None),
    ("MASS_5",  r"(catalytic|auto part|vehicle part|"
                r"part\w*\s+from\s+(a\s+)?(motor\s+)?(vehicle|auto|car)|"
                r"(burglar\w*|b\s*&\s*e|breaking\s+(or|and)\s+entering)"
                r"[^.]{0,40}(commercial|business|non.?resid|nonresid)|"
                r"(commercial|business|non.?resid|nonresid)"
                r"[^.]{0,25}(burglar\w*|b\s*&\s*e|breaking\s+(or|and)\s+entering))", None),
    ("MASS_2",  r"(from\s+(a\s+)?(motor\s+)?(vehicle|veh\b|auto|car\b|mv\b)|"
                r"\bf\s*/?\s*auto\b|shoplift|retail theft|"
                r"(vehicle|auto|car)\s+burglar|"
                r"burglar\w*\W{0,4}(of\s+|from\s+|to\s+)?(a\s+)?(motor\s+)?"
                r"(vehicle|veh\b|auto|car\b))", None),
    ("MVT",     r"(motor vehicle theft|auto theft|vehicle theft|"
                r"stolen\s*[,;]?\s*(motor\s+)?(vehicle|auto|car)\b|"
                r"\bauto\b\s*[,;]\s*stolen|"
                r"theft of (a )?(motor )?vehicle" + _NOT_WHOLE_CAR + r"|gta\b|veh theft|"
                r"larceny of motor vehicle" + _NOT_WHOLE_CAR + r")", None),
    ("MASS_4",  r"(burglar|breaking and entering|b\s*&\s*e\b)", None),
    ("MASS_4",  r"(bicycle|bike)", _THEFT_CTX),
    ("MASS_3",  r"(larceny|theft)", None),
]
_COMPILED_V2 = [(k, _re.compile(p, _re.I), g) for k, p, g in _RULES_V2]


def classify_text_v2(text: str):
    """Audited replacement for `classify_text`. Same contract, same classes."""
    t = _SEP_V2.sub(" ", str(text or ""))
    for klass, rx, guard in _COMPILED_V2:
        if rx.search(t) and (guard is None or guard.search(t)):
            return klass, _MASS_OF.get(klass)
    return "OTHER", None


# Classes that count as property crime for the pooled outcome.
PROPERTY_CLASSES = [f"MASS_{i}" for i in range(1, 6)] + ["MVT", "NO_LOOT"]
