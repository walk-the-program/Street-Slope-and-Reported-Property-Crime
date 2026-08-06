"""Render the supporting information files PLOS expects.

The manuscript cites S1 Appendix, S2 Appendix and S3 Data. Those live in the
project as markdown and a CSV, which are not submittable as they stand -- PLOS
takes each supporting file as its own document, named S1_Appendix and so on, and
the reviewer opens it directly.

The renderer is the one from `make_guide.py`, so the three documents look like
one another rather than like three different projects.
"""
from __future__ import annotations

import os
import shutil
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer)

sys.path.insert(0, os.path.dirname(__file__))
from make_guide import INK2, RULE, TITLE, SUB, _s, parse

OUT = "submission/supporting_information"

DOCS = [
    ("PREREGISTRATION.md", "S1_Appendix.pdf", "S1 Appendix",
     "Analysis plan and deviations",
     "Hypotheses, inclusion rules and decision criteria fixed before the "
     "confirmatory dataset existed, followed by thirteen itemized deviations "
     "from that plan."),
    ("SUPPLEMENT.md", "S2_Appendix.pdf", "S2 Appendix",
     "Reporting checklist and table index",
     "STROBE checklist, an index of every result table, and the full "
     "specification history including the four abandoned analysis phases."),
]


def render(src, dst, label, title, blurb):
    md = open(src).read()
    # Drop a leading H1 if the file has one; the cover block replaces it.
    body = md.split("\n", 1)[1] if md.startswith("# ") else md

    doc = BaseDocTemplate(dst, pagesize=letter,
                          leftMargin=0.95 * inch, rightMargin=0.95 * inch,
                          topMargin=0.9 * inch, bottomMargin=0.85 * inch,
                          title=f"{label}. {title}", author="Walker Tracy")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")

    def deco(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.6)
        canvas.setFillColor(INK2)
        if canvas.getPageNumber() > 1:
            canvas.drawString(doc.leftMargin, letter[1] - 0.55 * inch,
                              f"{label}. {title}")
            canvas.drawRightString(letter[0] - doc.rightMargin, 0.55 * inch,
                                   str(canvas.getPageNumber()))
            canvas.setStrokeColor(RULE)
            canvas.setLineWidth(0.5)
            canvas.line(doc.leftMargin, letter[1] - 0.63 * inch,
                        letter[0] - doc.rightMargin, letter[1] - 0.63 * inch)
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=deco)])
    story = [
        Paragraph(label.upper(), _s("lab", fontName="Helvetica-Bold", fontSize=11,
                                    textColor=colors.HexColor("#0d7d9e"),
                                    spaceAfter=10)),
        Paragraph(title, TITLE),
        Paragraph(blurb, SUB),
        Spacer(1, 6),
        Paragraph("Supporting information for <i>Street slope and reported "
                  "property crime in nine United States cities: terrain "
                  "measurement, target exposure, and tests of candidate "
                  "mechanisms.</i>",
                  _s("cite", fontSize=10.5, textColor=INK2, spaceAfter=4)),
        Spacer(1, 14),
    ]
    story += parse(body)
    doc.build(story)
    print(f"  {dst}")


def main():
    os.makedirs(OUT, exist_ok=True)
    for src, dst, label, title, blurb in DOCS:
        render(src, f"{OUT}/{dst}", label, title, blurb)
    shutil.copy("outputs/classifier_validation.csv", f"{OUT}/S3_Data.csv")
    print(f"  {OUT}/S3_Data.csv")
    shutil.copy("outputs/classifier_metrics.md",
                f"{OUT}/S3_Data_confusion_matrices.md")
    print(f"  {OUT}/S3_Data_confusion_matrices.md")


if __name__ == "__main__":
    main()
