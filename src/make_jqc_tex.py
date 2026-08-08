r"""Derive the Journal of Quantitative Criminology version from the PLOS master.

JQC differs from PLOS in four ways that matter, and one of them changes the shape
of the submission rather than just its formatting.

  double-blind    JQC anonymises. The manuscript carries no author name, no
                  affiliation, no email -- and, less obviously, no repository
                  URL and no DOI, since both name the author. Those go on a
                  separate title page file, and the data statement points at an
                  anonymised placeholder until acceptance.
  abstract        structured, four labelled parts, 250 words rather than 300.
  references      Springer Basic author-year, not numbered Vancouver. The
                  bibliography is reparsed into `Author (Year) Title. Venue`
                  form and every \cite becomes a \citep.
  declarations    Springer wants a Declarations section covering funding,
                  competing interests, data availability and ethics.

The PLOS file stays the master. Everything here is derived, so a change to the
science only has to be made once.
"""
from __future__ import annotations

import os
import re

SRC = "plos_manuscript.tex"
DST = "jqc_manuscript.tex"
TITLE_PAGE = "jqc_title_page.tex"

PREAMBLE = r"""% ---------------------------------------------------------------------------
% Journal of Quantitative Criminology submission -- ANONYMISED MANUSCRIPT.
% Generated from plos_manuscript.tex by src/make_jqc_tex.py; edit the master.
%
% JQC uses double-blind review, so this file carries no identifying information.
% Author, affiliation and corresponding-author details are in jqc_title_page.tex,
% which is uploaded as a separate file.
%
% At initial submission Springer accepts a clean, readable manuscript in any
% reasonable format. On acceptance they ask for their own class (sn-jnl.cls,
% available from Springer or as an Overleaf template); the content transfers
% without change.
% ---------------------------------------------------------------------------
\documentclass[12pt,letterpaper]{article}
\usepackage[margin=1in]{geometry}

\usepackage{amsmath,amssymb}
\usepackage[utf8]{inputenc}
\usepackage{textcomp}
\usepackage[round,authoryear]{natbib}
\usepackage{microtype}
\usepackage[table]{xcolor}
\usepackage{array}
\usepackage{booktabs}
\usepackage{graphicx}
\usepackage{setspace}
\usepackage[right]{lineno}
\usepackage{fancyhdr}
\usepackage[colorlinks=false,hidelinks]{hyperref}

\usepackage[labelfont=bf,labelsep=period,justification=raggedright,
            singlelinecheck=off,font=small]{caption}

\doublespacing
\setlength{\parindent}{1.5em}

\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\itshape __RUNNINGHEAD__}
\fancyhead[R]{\small\thepage}
\renewcommand{\headrulewidth}{0.4pt}

\title{\bfseries __TITLE__}
\author{}
\date{}

\begin{document}
\maketitle
\thispagestyle{fancy}

\begin{abstract}
\noindent
__ABSTRACT__
\end{abstract}

\vspace{6pt}
\noindent\textbf{Keywords:} crime and place; environmental criminology;
topography; street slope; property crime; exposure measurement

\linenumbers
"""

# --- the structured abstract JQC asks for, four labelled parts -----------------
ABSTRACT = r"""\textbf{Objectives.} \citet{haberman2021} reported that robbery falls as street
grade rises and closed by naming three explanations -- physical cost, difficulty of
escape, and lower street usage -- without testing between them. This paper extends the
outcome to property crime and the setting to nine cities, building a design in which
those explanations make different predictions.

\textbf{Methods.} Incident level property crime from nine United States cities was
harmonised through a single pipeline and aggregated to 100~m cells. Slope was computed
by Horn's method on a 10~m lidar elevation model held at identical resolution across
cities, and exposure is housing units plus population apportioned within census block
groups by residential building footprint area. Estimation is Poisson
pseudo-maximum-likelihood with absorbed block group fixed effects and cluster-robust
standard errors, pooled by random-effects meta-analysis.

\textbf{Results.} All nine cities show significantly less recorded property crime on
steeper streets. A random-effects pool over the four cities with the most measurable
gradient gives $-6.89\%$ per degree (95\% CI $-9.51$ to $-4.21$), with a prediction
interval for a new city of $-13.7\%$ to $+0.5\%$. Terrain measurability explains 59\% of the
between-city variance. Crimes in which nothing is removed track slope as
closely as theft, and an equivalence test rejects a difference as large as half the
headline effect. Network measures absorb about a quarter, and replacing housing
denominators with counted targets makes the estimate more negative rather than less.

\textbf{Conclusions.} Street gradient is robustly associated with lower recorded
property crime within neighbourhoods, but the magnitude does not transport and no
tested mechanism fully accounts for it."""

DECLARATIONS = r"""
% ---------------------------------------------------------------------------
\section*{Declarations}

\textbf{Funding.} No funding was received for conducting this study.

\textbf{Competing interests.} The author declares no competing interests.

\textbf{Ethics approval.} This study did not involve human participants or animals.
It analyses aggregate counts derived from incident records already released publicly
by municipal governments, and no institutional review board approval was required.
Considerations of disclosure risk and responsible use are set out in the Ethics and
responsible use section.

\textbf{Data and code availability.} All source data are public and require no
credentials: elevation from the United States Geological Survey 3D Elevation
Program, incidents from municipal open data portals, demographic and geographic data
from the United States Census Bureau, street networks from OpenStreetMap, building
footprints from Microsoft, and the parking census and address points from the City
and County of San Francisco. The analysis code, the aggregated 100~m analytic panels
the models are estimated on, every result table, the harvest manifests that make each
city's extraction reproducible, and the hand coded classifier validation set are
deposited in a public archive with a permanent identifier. The archive is
author-identifying and is therefore withheld during double-blind review; the
identifier is given on the title page and will be cited in the published article.
Raw point level incident downloads and elevation rasters are not redistributed, for
the disclosure and licensing reasons given in the text, and are re-derivable from the
deposited manifests.

\textbf{Use of AI tools.} Analysis code and manuscript drafting were assisted by a
large language model. The offense classifier is a deterministic rule set rather than
a model; no AI system labelled an incident, selected a specification, or generated
any figure reported here, and every analytic decision, the hand coding, and all
conclusions are the author's.
"""


def parse_bib(block):
    """Turn the Vancouver entries into Springer author-year form.

    Entries in the master are uniform: a key, an authors line, then one or more
    \newblock segments for title and venue. That regularity is the only reason
    this is safe to do mechanically; anything it cannot read is reported rather
    than silently mangled.
    """
    out, problems = [], []
    for raw in re.split(r"\\bibitem\{", block)[1:]:
        key, _, rest = raw.partition("}")
        parts = [p.strip() for p in rest.split(r"\newblock")]
        authors = " ".join(parts[0].split()).rstrip(".")
        tail = [" ".join(p.split()) for p in parts[1:]]

        # Pull the DOI out before anything else touches the text. A DOI like
        # 10.1080/15568318.2026.2659601 contains the publication year, and the
        # year-stripping below happily ate it out of the middle -- producing a
        # DOI that resolves to nothing.
        doi = ""
        kept = []
        for t in tail:
            m = re.search(r"doi:\s*(\S+)", t, re.I)
            if m:
                doi = m.group(1).rstrip(".")
                t = t[:m.start()].strip()
            if t:
                kept.append(t)
        tail = kept
        body = " ".join(tail)

        m = re.search(r"\b(19|20)\d{2}\b", body)
        if not m:
            problems.append(key)
            continue
        year = m.group(0)

        title = tail[0].strip() if tail else ""
        venue = " ".join(tail[1:]) if len(tail) > 1 else ""
        venue = re.sub(r"\.?\s*" + year + r"[;,]?\s*", " ", venue).strip()
        venue = venue.strip(" .;,")

        # A title that already ends in ? or ! keeps its own punctuation rather
        # than collecting a second mark.
        if title and title[-1] not in ".?!":
            title += "."
        elif title.endswith("."):
            pass

        surnames = [a.strip().split()[0] for a in authors.split(",") if a.strip()]
        if len(surnames) == 1:
            label = surnames[0]
        elif len(surnames) == 2:
            label = f"{surnames[0]} and {surnames[1]}"
        else:
            label = f"{surnames[0]} et al."

        entry = f"{authors} ({year}) {title}"
        if venue:
            entry += f" {venue}."
        if doi:
            entry += f" \\url{{https://doi.org/{doi}}}"
        out.append(f"\\bibitem[{label}({year})]{{{key}}}\n{entry}\n")

    if problems:
        raise SystemExit("could not find a year for: " + ", ".join(problems))
    return out


def build():
    s = open(SRC).read()
    title = " ".join(re.search(r"\\textbf\\newline\{(.+?)\}\s*\n\}", s,
                               flags=re.S).group(1).split())
    head = re.search(r"%\s*RUNNINGHEAD:\s*(.+)", s).group(1).strip()

    body = s.split(r"\begin{document}", 1)[1].split("\n", 1)[1]

    # --- strip everything that names the author -------------------------------
    body = re.sub(r"\\vspace\*\{0\.2in\}\s*\\begin\{flushleft\}.*?\\end\{flushleft\}",
                  "", body, flags=re.S)
    body = body[body.index(r"\section*{Introduction}"):]

    # Acknowledgments thank named city staff and sign the AI disclosure; both go.
    for sec in (r"\section*{Data and code availability}", r"\section*{Acknowledgments}"):
        if sec in body:
            start = body.index(sec)
            nxt = [body.index(m, start + 1) for m in
                   (r"\section*", r"\begin{thebibliography}") if m in body[start + 1:]]
            body = body[:start] + body[min(nxt):]

    # --- figures are supplied separately, as at PLOS --------------------------
    body = body.replace(r"\ifembedfigs", "").replace(r"}\fi", "}")
    body = re.sub(r"^\\linenumbers\s*$", "", body, flags=re.M)

    # --- headings and cross-references ---------------------------------------
    body = re.sub(r"\\(sub){0,2}section\*\{",
                  lambda m: "\\" + m.group(0).lstrip("\\").replace("*{", "{"), body)
    body = body.replace(r"\paragraph*{", r"\paragraph{")
    body = body.replace(r"Fig~\ref{", r"Figure~\ref{")

    # --- citations: numbered -> author-year ----------------------------------
    body = re.sub(r"\\cite\{", r"\\citep{", body)

    # --- bibliography ---------------------------------------------------------
    bib_start = body.index(r"\begin{thebibliography}")
    bib_end = body.index(r"\end{thebibliography}")
    entries = parse_bib(body[bib_start:bib_end])
    si_after = body[bib_end + len(r"\end{thebibliography}"):]
    new_bib = ("\\begin{thebibliography}{99}\n\n" + "\n".join(entries) +
               "\n\\end{thebibliography}\n")
    body = body[:bib_start] + new_bib + DECLARATIONS + si_after

    out = (PREAMBLE.replace("__TITLE__", title)
                   .replace("__RUNNINGHEAD__", head)
                   .replace("__ABSTRACT__", ABSTRACT) + body)
    open(DST, "w").write(out)

    # --- the separate, non-anonymous title page -------------------------------
    tp = r"""% Title page for the Journal of Quantitative Criminology submission.
% Uploaded as a separate file; the manuscript itself is anonymised for
% double-blind review.
\documentclass[12pt,letterpaper]{article}
\usepackage[margin=1in]{geometry}
\usepackage[utf8]{inputenc}
\usepackage[colorlinks=false,hidelinks]{hyperref}
\pagestyle{empty}
\begin{document}

\begin{flushleft}
{\Large\bfseries """ + title.replace(":", ":\\\\[4pt]") + r"""}

\vspace{20pt}
Walker Tracy\footnote{Independent Researcher, Salt Lake City, Utah, United States
of America. ORCID 0009-0004-0283-2318.}

\vspace{16pt}
\textbf{Running head:} """ + head + r"""

\vspace{16pt}
\textbf{Corresponding author}\\
Walker Tracy\\
Independent Researcher\\
Salt Lake City, Utah, United States of America\\
\texttt{walkeratracy@gmail.com}\\
ORCID 0009-0004-0283-2318

\vspace{16pt}
\textbf{Data and code archive}\\
\texttt{https://doi.org/10.5281/zenodo.21855377} (version 1.0.0)\\
\texttt{https://github.com/walk-the-program/Street-Slope-and-Reported-Property-Crime}

\vspace{16pt}
\textbf{Funding.} No funding was received for conducting this study.

\textbf{Competing interests.} The author declares no competing interests.
\end{flushleft}

\end{document}
"""
    open(TITLE_PAGE, "w").write(tp)

    ident = [t for t in ("Walker Tracy", "walkeratracy", "Salt Lake",
                         "walk-the-program", "zenodo", "Independent Researcher")
             if t in out]
    checks = {
        "figure blocks": out.count(r"\begin{figure}"),
        "tables": out.count(r"\begin{table}"),
        "bibitems": out.count(r"\bibitem"),
        "citep calls": out.count(r"\citep{") + out.count(r"\citet{"),
        "identifying strings left": len(ident),
    }
    for k, v in checks.items():
        print(f"  {k:28s} {v}")
    if ident:
        raise SystemExit("NOT ANONYMOUS -- found: " + ", ".join(ident))
    print(f"\nwrote {DST} and {TITLE_PAGE}")


if __name__ == "__main__":
    build()
