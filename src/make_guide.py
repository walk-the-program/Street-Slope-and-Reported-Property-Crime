"""Render GUIDE.md into a PDF reference document.

A small markdown subset is enough here: headings, paragraphs, bullets, pipe
tables, blockquote callouts, and inline bold/code. Anything fancier would be
more renderer than document.
"""
from __future__ import annotations

import html
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

SRC, DST = "GUIDE.md", "Crime_and_Slope_Project_Guide.pdf"

INK = colors.HexColor("#1c1a17")
INK2 = colors.HexColor("#57534e")
RULE = colors.HexColor("#d8d5cf")
PETROL = colors.HexColor("#0d7d9e")
RUST = colors.HexColor("#c04a1e")
SURF = colors.HexColor("#f4f2ed")

ss = getSampleStyleSheet()


def _s(name, **kw):
    base = dict(fontName="Helvetica", fontSize=9.6, leading=14.2, textColor=INK,
                alignment=TA_LEFT, spaceAfter=7)
    base.update(kw)
    return ParagraphStyle(name, **base)


BODY = _s("body")
H1 = _s("h1", fontName="Helvetica-Bold", fontSize=19, leading=23,
        textColor=PETROL, spaceBefore=0, spaceAfter=13)
H2 = _s("h2", fontName="Helvetica-Bold", fontSize=13.5, leading=17,
        spaceBefore=17, spaceAfter=7)
H3 = _s("h3", fontName="Helvetica-Bold", fontSize=10.6, leading=14,
        textColor=INK2, spaceBefore=12, spaceAfter=5)
BULLET = _s("bullet", leftIndent=13, bulletIndent=3, spaceAfter=3.5)
CALLOUT = _s("callout", fontSize=9.3, leading=13.6, leftIndent=9, rightIndent=8,
             spaceBefore=5, spaceAfter=5, textColor=INK)
CELL = _s("cell", fontSize=8.3, leading=11, spaceAfter=0)
CELLH = _s("cellh", fontSize=8.3, leading=11, spaceAfter=0,
           fontName="Helvetica-Bold")
TITLE = _s("title", fontName="Helvetica-Bold", fontSize=26, leading=31,
           textColor=INK, spaceAfter=10)
SUB = _s("sub", fontSize=12, leading=17, textColor=INK2, spaceAfter=5)


def inline(t):
    """Escape, then apply the three inline markups we allow."""
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r'<font face="Courier" size="8.7">\1</font>', t)
    t = re.sub(r"\*(?!\s)(.+?)(?<!\s)\*", r"<i>\1</i>", t)
    return t


def make_table(rows):
    head, body = rows[0], rows[1:]
    ncol = len(head)
    data = [[Paragraph(inline(c), CELLH) for c in head]]
    for r in body:
        data.append([Paragraph(inline(c), CELL) for c in r])
    avail = 6.7 * inch
    # First column carries labels and gets the slack; the rest share evenly.
    if ncol > 1:
        first = min(2.5 * inch, avail * 0.42)
        widths = [first] + [(avail - first) / (ncol - 1)] * (ncol - 1)
    else:
        widths = [avail]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, INK2),
        ("LINEBELOW", (0, 1), (-1, -2), 0.35, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def parse(md):
    story, i = [], 0
    lines = md.split("\n")
    while i < len(lines):
        ln = lines[i]
        if ln.strip() == "<<PAGEBREAK>>":
            story.append(PageBreak())
        elif ln.startswith("# "):
            story.append(PageBreak())
            story.append(Paragraph(inline(ln[2:]), H1))
            story.append(Spacer(1, 2))
        elif ln.startswith("## "):
            story.append(Paragraph(inline(ln[3:]), H2))
        elif ln.startswith("### "):
            story.append(Paragraph(inline(ln[4:]), H3))
        elif ln.startswith("- "):
            story.append(Paragraph(inline(ln[2:]), BULLET, bulletText="•"))
        elif ln.startswith("> "):
            buf = []
            while i < len(lines) and lines[i].startswith("> "):
                buf.append(lines[i][2:])
                i += 1
            i -= 1
            inner = Paragraph(inline(" ".join(buf)), CALLOUT)
            box = Table([[inner]], colWidths=[6.7 * inch], hAlign="LEFT")
            box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), SURF),
                ("LINEBEFORE", (0, 0), (0, -1), 2.2, RUST),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))
            story.append(Spacer(1, 3))
            story.append(box)
            story.append(Spacer(1, 7))
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            i -= 1
            story.append(Spacer(1, 3))
            story.append(make_table(rows))
            story.append(Spacer(1, 9))
        elif ln.strip():
            story.append(Paragraph(inline(ln), BODY))
        i += 1
    return story


def build():
    md = open(SRC).read()
    body = md.split("<<START>>", 1)[1]

    doc = BaseDocTemplate(DST, pagesize=letter,
                          leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                          topMargin=0.85 * inch, bottomMargin=0.8 * inch,
                          title="Crime and Slope — Project Reference",
                          author="Walker Tracy")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")

    def deco(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.6)
        canvas.setFillColor(INK2)
        if canvas.getPageNumber() > 1:
            canvas.drawString(doc.leftMargin, letter[1] - 0.55 * inch,
                              "Crime and Slope — project reference")
            canvas.drawRightString(letter[0] - doc.rightMargin, 0.52 * inch,
                                   str(canvas.getPageNumber()))
            canvas.setStrokeColor(RULE)
            canvas.setLineWidth(0.5)
            canvas.line(doc.leftMargin, letter[1] - 0.63 * inch,
                        letter[0] - doc.rightMargin, letter[1] - 0.63 * inch)
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=deco)])

    story = [Spacer(1, 1.5 * inch),
             Paragraph("Street Slope and<br/>Property Crime", TITLE),
             Paragraph("A complete reference to the study: where the question came "
                       "from, every dataset and decision, what was found, what "
                       "broke, and what it does and does not support.", SUB),
             Spacer(1, 0.28 * inch),
             Paragraph("Walker Tracy &nbsp;·&nbsp; internal reference, not for "
                       "circulation", _s("byline", textColor=INK2, fontSize=9.6)),
             ]
    story += parse(body)
    doc.build(story)
    print(f"wrote {DST}")


if __name__ == "__main__":
    build()
