# Submitting to PLOS ONE

Everything in this folder is ready to upload. Two things still need you, and they
are listed at the bottom.

## Step 1 — produce the manuscript PDF

PLOS wants a PDF as the manuscript file, and it must **not contain the figures**.

1. Upload `manuscript/` to Overleaf (New Project → Upload Project).
2. Recompile. The `\embedfigsfalse` toggle in the preamble leaves the figures out
   and keeps their numbered captions in place, which is exactly what PLOS asks for.
3. Download the PDF. That is your manuscript file.

To read a copy with the figures in place, flip the toggle to `\embedfigstrue` and
recompile. Do not submit that version.

## Step 2 — upload, in this order

| Editorial Manager slot | File |
|---|---|
| Manuscript | the PDF you just compiled |
| Figure 1 | `figures/Fig1.tif` — city effects against terrain measurability |
| Figure 2 | `figures/Fig2.tif` — slope vs relative height |
| Figure 3 | `figures/Fig3.tif` — theft vs no-loot |
| Figure 4 | `figures/Fig4.tif` — loot-mass ladder |
| Figure 5 | `figures/Fig5.tif` — target denominators |
| Supporting information | `supporting_information/S1_Appendix.pdf` |
| Supporting information | `supporting_information/S2_Appendix.pdf` |
| Supporting information | `supporting_information/S3_Data.csv` |

Figure order follows citation order in the text, which is not the order the files
were originally created in. Upload them as numbered here.

All five TIFFs are inside PLOS's limits: 300 dpi, 6.55–7.08 inches wide (cap is
7.5), under 0.25 MB each (cap is 10), RGB, Arial 8–9.5 pt, no embedded titles.
`src/make_plos_figs.py` re-checks this on every rebuild and fails loudly.

## Step 3 — the submission form

**Data availability.** Choose "All relevant data are within the manuscript and its
Supporting Information files, and in a public repository", then paste:

> All source data are publicly available and require no credentials: USGS 3DEP
> elevation, municipal open data portals, US Census ACS and TIGER/Line,
> OpenStreetMap, Microsoft Building Footprints, and the City and County of San
> Francisco parking census and address points. Analysis code, the aggregated
> analytic panels, all result tables, the harvest manifests and the classifier
> validation set are archived at
> https://github.com/walk-the-program/Street-Slope-and-Reported-Property-Crime.
> Raw point-level incident downloads and elevation rasters are not redistributed,
> for the disclosure and licensing reasons given in the manuscript, and are
> re-derivable from the deposited manifests.

**Funding.** None. Declare no funding received.

**Competing interests.** None.

**Ethics.** No human subjects research; aggregate analysis of publicly released
incident data. No IRB approval was required. The manuscript carries an *Ethics and
responsible use* section covering disclosure risk, redistribution and interpretive
harm.

**AI disclosure.** Already declared in the Acknowledgments. If the form asks
separately, the tool was Anthropic's Claude, used for analysis code and manuscript
drafting; it labelled no incident, selected no specification, and generated no
reported number.

**CRediT contributions.** Single author — conceptualization, data curation, formal
analysis, investigation, methodology, software, validation, visualization, writing
(original draft), writing (review and editing).

## Still needs you

**Compile the PDF, then upload.** That is the whole list.

## A note on the affiliation

The title block reads **Independent Researcher, United States of America**. PLOS ONE
publishes unaffiliated authors routinely and this is the standard form; nothing about
it weakens the submission. Add a city if you want one — the field is free text and a
location is conventional but not required.

## Optional, not blocking

Depositing the analysis plan on OSF would give it a timestamp and a DOI. The
manuscript deliberately describes it as a *pre-specified analysis plan* rather than
a pre-registration, so nothing currently overclaims and this is no longer required
before submitting.
