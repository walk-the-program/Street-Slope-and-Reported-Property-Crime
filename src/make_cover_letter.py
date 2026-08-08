"""Render the cover letter as a one-page PDF.

Deliberately plainer than the supporting-information renderer: a cover letter is
correspondence, not a document with structure, so it gets a date, body text at a
readable measure, and a signature block. No headings, no rules, no page
furniture.
"""
from __future__ import annotations

import datetime as dt
import html
import os
import re

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

SRC = "packages/submission/cover_letter.md"
DST = "paper/Cover_Letter.pdf"
INK = HexColor("#14181c")

BODY = ParagraphStyle("body", fontName="Times-Roman", fontSize=10.5, leading=13.6,
                      textColor=INK, alignment=TA_LEFT, spaceAfter=8)
META = ParagraphStyle("meta", parent=BODY, fontSize=10, textColor=HexColor("#555b61"),
                      spaceAfter=3)


# ReportLab's built-in fonts have no glyphs for the Unicode superscript block, so
# characters like the minus-seven in "8.3 x 10^-7" render as solid black boxes.
# They have to be converted to ReportLab's own <super> markup instead.
_SUP = {"\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3", "\u2074": "4",
        "\u2075": "5", "\u2076": "6", "\u2077": "7", "\u2078": "8", "\u2079": "9",
        "\u207b": "-", "\u207a": "+"}


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", t)
    # Collapse a run of Unicode superscripts into one <super> group.
    t = re.sub("[" + "".join(_SUP) + "]+",
               lambda m: "<super>" + "".join(_SUP[c] for c in m.group(0)) + "</super>",
               t)
    # Let a long bare URL wrap rather than run off the measure.
    t = t.replace("https://github.com/", "https://github.com/<wbr/>")
    return t


def build():
    raw = open(SRC).read().strip().split("\n")
    # The trailing signature block is set tighter than the body.
    sig_start = next(i for i, l in enumerate(raw) if l.startswith("Walker Tracy"))
    body_lines, sig_lines = raw[:sig_start], raw[sig_start:]

    paras, buf = [], []
    for line in body_lines:
        if line.strip():
            buf.append(line.strip())
        elif buf:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))

    doc = SimpleDocTemplate(DST, pagesize=letter,
                            leftMargin=1.0 * inch, rightMargin=1.0 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.75 * inch,
                            title="Cover letter", author="Walker Tracy")
    story = [Paragraph(dt.date.today().strftime("%B %-d, %Y"), META),
             Spacer(1, 13)]
    for p in paras:
        story.append(Paragraph(inline(p), BODY))
    story.append(Spacer(1, 6))
    for line in sig_lines:
        if line.strip():
            story.append(Paragraph(inline(line.strip()), META))
    doc.build(story)
    print(f"wrote {DST}")


if __name__ == "__main__":
    build()
