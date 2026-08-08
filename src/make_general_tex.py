r"""Derive a plain-article version of the manuscript from the PLOS one.

The PLOS file is the master. Keeping a second hand-edited copy of a 7,500 word
paper in sync is a losing game, so the general version is generated from it and
regenerated whenever the text changes. Everything below is either a preamble
swap or a mechanical substitution -- no sentence of the body is touched.

What changes and why:

    margins        PLOS pushes the text block 2.75in to the right, which is
                   correct for them and looks broken anywhere else. Normal
                   symmetric margins here.
    figures        embedded, because everywhere except PLOS wants to see them
    line numbers   dropped
    sections       numbered, since \section* is a PLOS house rule
    "Fig 1"        becomes "Figure 1"
    references     bracketed labels [8], matching what \cite prints, instead of
                   PLOS's unbracketed "8."
    abstract       a real abstract environment rather than a starred section
"""
from __future__ import annotations

import re

PAPER = "paper"
SRC = f"{PAPER}/plos_manuscript.tex"
DST = f"{PAPER}/manuscript_general.tex"

PREAMBLE = r"""% ---------------------------------------------------------------------------
% General-purpose version of the manuscript. Generated from plos_manuscript.tex
% by src/make_general_tex.py -- edit the PLOS file, not this one.
%
% Plain article class, symmetric margins, embedded figures, numbered sections.
% Use this for preprints, working-paper series, coauthors, and anywhere that is
% not PLOS.
% ---------------------------------------------------------------------------
\documentclass[11pt,letterpaper]{article}
\usepackage[margin=1.15in]{geometry}

\usepackage{amsmath,amssymb}
\usepackage[utf8]{inputenc}
\usepackage{textcomp}
\usepackage{cite}
\usepackage{microtype}
\usepackage[table]{xcolor}
\usepackage{array}
\usepackage{booktabs}
\usepackage{graphicx}
\usepackage{fancyhdr}
\usepackage{nameref}
\usepackage[colorlinks=true,linkcolor={black!70},citecolor={black!70},
            urlcolor={black!70}]{hyperref}

% Captions: bold "Figure N." run into the caption text, ragged right so a long
% caption does not open rivers of whitespace at this measure.
\usepackage[labelfont=bf,labelsep=period,justification=raggedright,
            singlelinecheck=off,font=small]{caption}

\usepackage{setspace}
\setstretch{1.08}
\setlength{\parskip}{0pt}
\setlength{\parindent}{1.5em}

\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\itshape __RUNNINGHEAD__}
\fancyhead[R]{\small\thepage}
\renewcommand{\headrulewidth}{0.4pt}

\title{\bfseries __TITLE__}
\author{Walker Tracy\thanks{__AFFIL__ \texttt{walkeratracy@gmail.com}}}
\date{}

\begin{document}
\maketitle
"""


def read_title(src):
    r"""Pull the title out of the PLOS \textbf\newline{...} block.

    It was hardcoded here at first, which meant the general version silently
    kept a title the PLOS file had already changed -- the exact drift this
    whole generator exists to prevent. Now there is one copy of the title and
    it lives in the master file.

    Returns (title for \title{}, short running head). The running head comes
    from a `% RUNNINGHEAD:` line in the master file when there is one, because
    a descriptive title's first clause is usually far too long to sit in a page
    header. It falls back to the part before the colon.
    """
    m = re.search(r"\\textbf\\newline\{(.+?)\}\s*\n\}", src, flags=re.S)
    if not m:
        raise SystemExit("could not find the title block in " + SRC)
    title = " ".join(m.group(1).split())
    h = re.search(r"%\s*RUNNINGHEAD:\s*(.+)", src)
    head = h.group(1).strip() if h else title.split(":")[0].strip()
    # Break the line at the colon so \maketitle does not set one long line.
    if ":" in title:
        title = title.replace(":", ":\\\\", 1)
    return title, head


def build():
    s = open(SRC).read()
    title, head = read_title(s)
    # The affiliation was hardcoded here too, which is the same drift that left a
    # stale title behind. Read it from the master instead.
    a = re.search(r"\\textbf\{1\}\s*(.+?)\s*\n", s)
    affil = (a.group(1).strip().rstrip(".") + ".") if a else ""
    preamble = (PREAMBLE.replace("__TITLE__", title)
                        .replace("__RUNNINGHEAD__", head)
                        .replace("__AFFIL__", affil))

    # --- body only: everything from \begin{document} onward ------------------
    body = s.split(r"\begin{document}", 1)[1]
    body = body.split("\n", 1)[1]

    # Drop the PLOS title block (flushleft ... end{flushleft}) and the \vspace
    # that precedes it; \maketitle replaces both.
    body = re.sub(r"\\vspace\*\{0\.2in\}\s*\\begin\{flushleft\}.*?\\end\{flushleft\}",
                  "", body, flags=re.S)

    # Abstract: starred section -> real environment, closed at the Introduction.
    body = body.replace(r"\section*{Abstract}", "\\begin{abstract}", 1)
    body = body.replace(r"\section*{Introduction}",
                        "\\end{abstract}\n\n\\section{Introduction}", 1)

    # Figures are embedded here, so unwrap the PLOS toggle.
    body = body.replace(r"\ifembedfigs", "").replace(
        r"}\fi", "}")
    body = re.sub(r"^\\linenumbers\s*$", "", body, flags=re.M)

    # Numbered sections.
    body = re.sub(r"\\(sub){0,2}section\*\{", lambda m: "\\" + (m.group(0)
                  .lstrip("\\").replace("*{", "{")), body)
    body = body.replace(r"\paragraph*{", r"\paragraph{")

    # "Fig 1" -> "Figure 1", in cross-references and in captions alike.
    body = body.replace(r"Fig~\ref{", r"Figure~\ref{")
    body = body.replace(r"Figs~\ref{", r"Figures~\ref{")

    out = preamble + body
    # The PLOS-only bits of the tail.
    out = out.replace(
        "% For submission, switch to: \\bibliographystyle{plos2015} "
        "\\bibliography{references}\n", "")
    open(DST, "w").write(out)

    checks = {
        "figure blocks": out.count(r"\begin{figure}"),
        "includegraphics": out.count(r"\includegraphics"),
        "tables": out.count(r"\begin{table}"),
        "bibitems": out.count(r"\bibitem"),
        "leftover starred sections": len(re.findall(r"\\(sub)*section\*", out)),
        "leftover ifembedfigs": out.count("ifembedfigs"),
        "leftover linenumbers": out.count(r"\linenumbers"),
        "leftover Fig~": out.count(r"Fig~\ref"),
        "stale title": int(read_title(open(SRC).read())[0].split(":")[0]
                           not in out.split(r"\begin{document}")[0]),
    }
    for k, v in checks.items():
        print(f"  {k:28s} {v}")
    bad = [k for k, v in checks.items()
           if v and (k.startswith("leftover") or k == "stale title")]
    if bad or checks["includegraphics"] != 5:
        raise SystemExit(f"transform incomplete: {bad or 'figure count'}")
    print(f"\nwrote {DST}")


if __name__ == "__main__":
    build()
