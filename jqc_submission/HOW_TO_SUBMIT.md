# Submitting to the Journal of Quantitative Criminology

Springer Editorial Manager: https://www.editorialmanager.com/jqcr

## The thing that makes JQC different: double-blind review

JQC anonymises. The reviewers never see who wrote it, and it is the author's job
to make sure of that. So the manuscript in `manuscript/jqc_manuscript.tex` has
had removed:

- author name, affiliation and email
- the Zenodo DOI and the GitHub URL, both of which name you
- the Acknowledgments, which thanked named city open-data staff

All of that lives in `manuscript/jqc_title_page.tex`, which is uploaded as a
**separate file**. The generator refuses to write the manuscript if any
identifying string survives, so this is checked rather than assumed.

If you edit the manuscript by hand, do not paste the repository link back in.

## Step 1 — compile two PDFs

Upload `manuscript/` to Overleaf and compile **both** files:

- `jqc_manuscript.tex` -> the anonymised manuscript PDF
- `jqc_title_page.tex` -> a one-page title page PDF

## Step 2 — upload

| Editorial Manager item | File |
|---|---|
| Title Page | title page PDF |
| Manuscript | anonymised manuscript PDF |
| Figure 1–5 | `figures/Fig1.tif` … `Fig5.tif`, uploaded individually |
| Electronic Supplementary Material | `esm/ESM1_analysis_plan_and_deviations.pdf` |
| Electronic Supplementary Material | `esm/ESM2_reporting_checklist_and_tables.pdf` |
| Electronic Supplementary Material | `esm/ESM3_classifier_validation.csv` |

Springer calls supporting files Electronic Supplementary Material, not
Supporting Information. Same files, different label.

## Step 3 — the form

**Article type:** Original Paper.

**Abstract.** Structured, four labelled parts, 251 words. Paste it from the
compiled PDF or the `.tex`; it must match the manuscript.

**Keywords.** crime and place; environmental criminology; topography; street
slope; property crime; exposure measurement

**Funding.** No funding was received for conducting this study.

**Competing interests.** The author declares no competing interests.

**Data availability.** The manuscript's Declarations section explains that the
archive is withheld during blind review and will be cited on acceptance. If the
form demands a link, give the DOI — the form is not seen by reviewers:
https://doi.org/10.5281/zenodo.21855377

**Suggested reviewers.** JQC usually asks. Reasonable names, none of whom you
have worked with: Cory Haberman, James Kelsay, Young-An Kim, James Wo, Gregory
Breetzke, Shane Johnson, Wim Bernasco, David Weisburd.

## Cost

Nothing. JQC is subscription-based; you are never asked to pay at any stage. An
optional open-access fee exists on acceptance and can be declined.

## What is different from the PLOS version

| | PLOS ONE | JQC |
|---|---|---|
| Review | single-blind | **double-blind** |
| Abstract | 292 words, prose | **251 words, structured** |
| References | numbered Vancouver | **Springer author-year** |
| Statements | in the submission form | **Declarations section in the paper** |
| Supplements | S1/S2/S3 | **ESM1/ESM2/ESM3** |
| Cost | $2,477 on acceptance | **none** |
