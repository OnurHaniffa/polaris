"""Hand-placed figures for the checkpoint report and slides, in the TU Berlin deck style.

Every box, line and label sits on a fixed grid, so nothing overlaps. Each figure is its own
one-slide .pptx sized to the figure; PowerPoint exports them to PDF (real Avenir Next and
DIN Alternate) and pdftoppm turns the PDFs into the PNGs in docs/diagrams and docs/process.

Run from the repo root:  uv run --no-project --with python-pptx python docs/diagrams/source/build_figures.py OUTDIR
"""

import sys
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

NAVY = RGBColor(0x10, 0x1E, 0x31)
BODY = RGBColor(0x2A, 0x36, 0x4A)
MUTED = RGBColor(0x85, 0x93, 0xA8)
PANEL = RGBColor(0xEE, 0xF1, 0xF5)
RULE = RGBColor(0xAE, 0xBA, 0xCA)
LINE = RGBColor(0x5B, 0x6B, 0x82)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SANS, LABEL = "Avenir Next", "DIN Alternate"


def canvas(w, h):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(w), Inches(h)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = WHITE
    return prs, s


def text(
    s,
    t,
    x,
    y,
    w,
    h,
    size=9,
    color=BODY,
    font=SANS,
    bold=False,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    caps=False,
    track=None,
    line_spacing=None,
    backing=None,
):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if backing is not None:
        tb.fill.solid()
        tb.fill.fore_color.rgb = backing
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, para in enumerate(str(t).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if line_spacing:
            p.line_spacing = line_spacing
        r = p.add_run()
        r.text = para
        r.font.size, r.font.bold, r.font.name = Pt(size), bold, font
        r.font.color.rgb = color
        rpr = r._r.get_or_add_rPr()
        if caps:
            rpr.set("cap", "all")
        if track is not None:
            rpr.set("spc", str(int(track * 100)))
    return tb


def rect(s, x, y, w, h, fill=PANEL, stroke=None, dash=False, radius=None, weight=0.75):
    shape = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.shadow.inherit = False
    if radius:
        sh.adjustments[0] = radius
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if stroke is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = stroke
        sh.line.width = Pt(weight)
        if dash:
            ln = sh.line._get_or_add_ln()
            d = etree.SubElement(ln, qn("a:prstDash"))
            d.set("val", "dash")
    return sh


def seg(s, x1, y1, x2, y2, color=LINE, weight=1.0, dash=False, head=None, tail=None):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(weight)
    etree.SubElement(c._element.spPr, qn("a:effectLst"))
    ln = c.line._get_or_add_ln()
    if dash:
        etree.SubElement(ln, qn("a:prstDash")).set("val", "dash")
    for tag, kind in (("a:headEnd", head), ("a:tailEnd", tail)):
        if kind:
            e = etree.SubElement(ln, qn(tag))
            e.set("type", kind)
            e.set("w", "lg" if kind == "diamond" else "med")
            e.set("len", "lg" if kind == "diamond" else "med")
    return c


def path(s, pts, color=LINE, weight=1.0, dash=False, start=None, end="triangle"):
    """Polyline through pts; start marker on the first point, end marker on the last."""
    n = len(pts) - 1
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        seg(s, x1, y1, x2, y2, color, weight, dash, head=start if i == 0 else None, tail=end if i == n - 1 else None)


def save(prs, name):
    prs.save(OUT / f"{name}.pptx")
    print("wrote", OUT / f"{name}.pptx")


# ------------------------------------------------------------------ the scoring chain
def chain():
    prs, s = canvas(6.7, 2.32)
    cols = [0.05, 2.6, 5.15]
    nw, nh = 1.5, 0.62
    rows = [0.42, 1.55]
    heads = ["Grades", "Learning outcomes", "Program outcomes"]
    for x, hd in zip(cols, heads, strict=True):
        text(s, hd, x, 0.05, 2.0, 0.22, size=8.5, color=MUTED, font=LABEL, caps=True, track=1.4)
    nodes = {
        "mid": (0, 0, "Midterm", "90"),
        "prj": (0, 1, "Project", "80"),
        "lo1": (1, 0, "LO 1", "86.0"),
        "lo2": (1, 1, "LO 2", "82.9"),
        "po1": (2, 0, "PO 1", "85.0"),
        "po2": (2, 1, "PO 2", "82.9"),
    }
    for c, r, name, val in nodes.values():
        x, y = cols[c], rows[r]
        rect(s, x, y, nw, nh, PANEL)
        text(s, name, x + 0.18, y + 0.08, nw - 0.3, 0.2, size=8.5, color=MUTED)
        text(s, val, x + 0.18, y + 0.24, nw - 0.3, 0.34, size=20, color=NAVY, font=LABEL)

    def pill(x, y, t):
        w = 0.42 if len(t) <= 3 else 0.5
        rect(s, x - w / 2, y - 0.1, w, 0.2, WHITE, RULE, radius=0.5)
        text(s, t, x - w / 2, y - 0.1, w, 0.2, size=8.5, color=BODY, font=LABEL, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    r0, r1 = rows[0], rows[1]
    out_a, out_b = 0.24, 0.44  # where lines leave and enter a node, from its top
    gap0, gap1 = cols[0] + nw, cols[1]
    gap2, gap3 = cols[1] + nw, cols[2]

    def edge(x1, y1, x2, y2, label):
        seg(s, x1, y1, x2, y2, tail="triangle")
        f = 0.3
        pill(x1 + (x2 - x1) * f, y1 + (y2 - y1) * f, label)

    edge(gap0, r0 + out_a, gap1, r0 + out_a, "60%")
    edge(gap0, r0 + out_b, gap1, r1 + out_a, "40%")
    edge(gap0, r1 + out_a, gap1, r0 + out_b, "40%")
    edge(gap0, r1 + out_b, gap1, r1 + out_b, "100%")
    edge(gap2, r0 + 0.31, gap3, r0 + 0.31, "1.0")
    edge(gap2, r1 + out_a, gap3, r0 + out_b, "0.5")
    edge(gap2, r1 + out_b, gap3, r1 + out_b, "1.0")
    save(prs, "chain")


# ------------------------------------------------------------------ velocity
def velocity():
    prs, s = canvas(6.7, 2.55)
    planned, done = [12, 28, 31, 28], [0, 6, 65, 18]
    labels = ["Sprint 0\n16–18 Oct", "Sprint 1\n19–25 Oct", "Sprint 2\n26 Oct–1 Nov", "Sprint 3\n2–8 Nov"]
    left, right, top, base = 0.45, 6.6, 0.42, 1.92
    scale = (base - top) / 70
    for v in (0, 20, 40, 60):
        y = base - v * scale
        seg(s, left, y, right, y, color=RGBColor(0xE3, 0xE8, 0xEE), weight=0.6)
        text(s, str(v), 0.05, y - 0.08, 0.3, 0.16, size=8, color=MUTED, font=LABEL, align=PP_ALIGN.RIGHT)
    gw = (right - left) / 4
    bw, gap = 0.44, 0.06
    avg = sum(done) / 4
    ya = base - avg * scale
    seg(s, left, ya, right, ya, color=NAVY, weight=1.75, dash=True)
    text(s, "average 22", left + 0.03, ya - 0.2, 1.0, 0.18, size=8.5, color=NAVY, font=LABEL, caps=True, track=1.0)
    for i in range(4):
        cx = left + gw * i + gw / 2
        for j, (val, fill, col) in enumerate(((planned[i], RGBColor(0xD5, 0xDC, 0xE5), MUTED), (done[i], NAVY, NAVY))):
            x = cx - bw - gap / 2 if j == 0 else cx + gap / 2
            h = max(val * scale, 0.0)
            if h:
                rect(s, x, base - h, bw, h, fill)
            lw = 0.3
            text(
                s,
                str(val),
                x + (bw - lw) / 2,
                base - h - 0.2,
                lw,
                0.18,
                size=9,
                color=col,
                font=LABEL,
                align=PP_ALIGN.CENTER,
                anchor=MSO_ANCHOR.MIDDLE,
                backing=WHITE,
            )
        text(s, labels[i], cx - gw / 2, base + 0.07, gw, 0.4, size=8.5, color=BODY, align=PP_ALIGN.CENTER, line_spacing=1.05)
    # legend, one line each
    rect(s, 3.55, 0.07, 0.16, 0.12, RGBColor(0xD5, 0xDC, 0xE5))
    text(s, "Planned", 3.76, 0.04, 0.8, 0.18, size=8.5, color=BODY)
    rect(s, 4.55, 0.07, 0.16, 0.12, NAVY)
    text(s, "Completed, merged with tests", 4.76, 0.04, 1.9, 0.18, size=8.5, color=BODY)
    text(s, "Story points", 0.05, 0.04, 1.5, 0.18, size=8.5, color=MUTED)
    save(prs, "velocity")


# ------------------------------------------------------------------ architecture
def node(s, x, y, w, h, title, sub, planned=False):
    if planned:
        rect(s, x, y, w, h, WHITE, MUTED, dash=True)
    else:
        rect(s, x, y, w, h, PANEL)
    text(s, title, x + 0.14, y + 0.08, w - 0.2, 0.2, size=9, bold=True, color=MUTED if planned else NAVY)
    text(s, sub, x + 0.14, y + 0.28, w - 0.2, h - 0.3, size=8, color=MUTED if planned else BODY, line_spacing=1.05)


def tag(s, t, x, y, w=0.9, align=PP_ALIGN.LEFT):
    text(s, t, x, y, w, 0.16, size=7.5, color=MUTED, font=LABEL, caps=True, track=0.6, align=align)


def architecture():
    # Strict grid: four equal columns, three rows, no labels on arrows. Each box's subtitle says
    # what flows through it; solid = running today, dashed = planned.
    prs, s = canvas(6.7, 2.75)
    bw, bh = 1.15, 0.5
    ca, cb, cc, cd = 0.05, 2.05, 3.55, 5.5  # column left edges
    r1, r2, r3 = 0.42, 1.12, 2.02  # row top edges
    mid = bh / 2
    rect(s, 1.65, 0.08, 3.35, 2.59, None, RULE, radius=0.03)
    tag(s, "Railway", 1.77, 0.14, 1.2)
    node(s, ca, r1, bw, bh, "Browser", "pages over HTTPS")
    node(s, ca, r2, bw, bh, "GitHub", "code, CI, deploys")
    node(s, ca, r3, bw, bh, "Email (SMTP)", "password resets", planned=True)
    # the app spans the first two rows so both inputs arrive straight
    node(s, cb, r1, bw, r2 + bh - r1, "Django app", "Django 6.1\non gunicorn")
    node(s, cc, r1, bw, bh, "PostgreSQL 18", "system of record")
    node(s, cc, r2, bw, bh, "Redis 8.2", "cache, job queue")
    node(s, cc, r3, bw, bh, "Celery worker", "background jobs", planned=True)
    node(s, cd, r3, bw, bh, "Claude API", "reads syllabi", planned=True)
    # key
    rect(s, cd, r1 + 0.08, 0.22, 0.14, PANEL)
    text(s, "running today", cd + 0.3, r1 + 0.05, 0.9, 0.2, size=8, color=BODY)
    rect(s, cd, r1 + 0.36, 0.22, 0.14, WHITE, MUTED, dash=True)
    text(s, "planned", cd + 0.3, r1 + 0.33, 0.9, 0.2, size=8, color=BODY)
    # flows: every one straight or a single right angle
    seg(s, ca + bw, r1 + mid, cb, r1 + mid, tail="triangle")
    seg(s, ca + bw, r2 + mid, cb, r2 + mid, tail="triangle")
    seg(s, cb + bw, r1 + mid, cc, r1 + mid, tail="triangle")
    seg(s, cb + bw, r2 + mid, cc, r2 + mid, tail="triangle")
    seg(s, cc + bw / 2, r2 + bh, cc + bw / 2, r3, color=MUTED, dash=True, tail="triangle")
    seg(s, cc + bw, r3 + mid, cd, r3 + mid, color=MUTED, dash=True, tail="triangle")
    path(s, [(cb + bw / 2, r2 + bh), (cb + bw / 2, r3 + mid), (ca + bw, r3 + mid)], color=MUTED, dash=True)
    save(prs, "architecture")


# ------------------------------------------------------------------ class diagram
def classes():
    prs, s = canvas(6.72, 6.0)
    cx = [0.04, 1.78, 3.52, 5.26]
    cw = 1.42
    ry = [0.05, 1.28, 2.51, 3.74, 4.97]
    rh = [0.81, 0.81, 0.81, 0.81, 0.96]
    spec = {
        "User": (0, 0, ["email", "student_number"]),
        "ProgramMembership": (1, 0, ["role", "cohort_year"]),
        "Program": (2, 0, ["code", "name", "attainment_threshold"]),
        "ProgramOutcomeSet": (3, 0, ["label", "effective_from_year", "is_active"]),
        "Course": (2, 1, ["code", "title", "credits"]),
        "ProgramOutcome": (3, 1, ["number", "short_name"]),
        "Term": (1, 2, ["code", "starts_on", "status"]),
        "CourseOffering": (2, 2, ["section", "syllabus"]),
        "LOPOWeight": (3, 2, ["weight: 1 to 5", "source"]),
        "Enrollment": (1, 3, ["status"]),
        "LearningOutcome": (3, 3, ["number", "description"]),
        "AuditEvent": (0, 4, ["action", "before", "after"]),
        "Grade": (1, 4, ["score", "published_score", "is_excused"]),
        "Assessment": (2, 4, ["name", "kind", "max_score", "published_at"]),
        "AssessmentLOWeight": (3, 4, ["weight: 1 to 100%"]),
    }
    for name, (c, r, attrs) in spec.items():
        x, y, h = cx[c], ry[r], rh[r]
        rect(s, x, y, cw, h, WHITE, RULE)
        rect(s, x, y, cw, 0.27, PANEL, RULE)
        pad = 0.04
        text(
            s,
            name,
            x + pad,
            y,
            cw - 2 * pad,
            0.27,
            size=8.5 if len(name) <= 15 else 8,
            bold=True,
            color=NAVY,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
        )
        text(s, "\n".join(attrs), x + 0.12, y + 0.33, cw - 0.18, h - 0.36, size=7.5, color=BODY, line_spacing=1.12)

    def L(name):  # left, right, top, bottom, x-centre, y-centre of a class box
        c, r, _ = spec[name]
        x, y, h = cx[c], ry[r], rh[r]
        return {"l": x, "r": x + cw, "t": y, "b": y + h, "xc": x + cw / 2, "yc": y + h / 2}

    def m(t, x, y, w=0.25, align=PP_ALIGN.LEFT):
        text(s, t, x, y, w, 0.15, size=7.5, color=MUTED, font=LABEL, align=align)

    U, PM, P, PS = L("User"), L("ProgramMembership"), L("Program"), L("ProgramOutcomeSet")
    C, PO, T, CO = L("Course"), L("ProgramOutcome"), L("Term"), L("CourseOffering")
    LP, E, LO = L("LOPOWeight"), L("Enrollment"), L("LearningOutcome")
    A, G, AS, AW = L("AuditEvent"), L("Grade"), L("Assessment"), L("AssessmentLOWeight")
    none = None
    # row 0, left to right
    path(s, [(U["r"], U["yc"]), (PM["l"], PM["yc"])], end=none)
    m("1", U["r"] + 0.03, U["yc"] - 0.17)
    m("*", PM["l"] - 0.1, PM["yc"] - 0.17)
    path(s, [(P["l"], P["yc"]), (PM["r"], PM["yc"])], end=none)
    m("1", P["l"] - 0.1, P["yc"] - 0.17)
    m("*", PM["r"] + 0.03, PM["yc"] - 0.17)
    path(s, [(P["r"], P["yc"]), (PS["l"], PS["yc"])], start="diamond", end=none)
    m("*", PS["l"] - 0.1, PS["yc"] - 0.17)
    # column 3, top to bottom
    path(s, [(PS["xc"], PS["b"]), (PO["xc"], PO["t"])], start="diamond", end=none)
    m("11", PO["xc"] + 0.05, PO["t"] - 0.17)
    path(s, [(PO["xc"], PO["b"]), (LP["xc"], LP["t"])], end=none)
    m("1", PO["xc"] + 0.05, PO["b"] + 0.02)
    m("*", LP["xc"] + 0.05, LP["t"] - 0.17)
    path(s, [(LO["xc"], LO["t"]), (LP["xc"], LP["b"])], end=none)
    m("1", LO["xc"] + 0.05, LO["t"] - 0.17)
    m("*", LP["xc"] + 0.05, LP["b"] + 0.02)
    path(s, [(LO["xc"], LO["b"]), (AW["xc"], AW["t"])], end=none)
    m("1", LO["xc"] + 0.05, LO["b"] + 0.02)
    m("*", AW["xc"] + 0.05, AW["t"] - 0.17)
    # column 2: program, course, offering
    path(s, [(P["xc"], P["b"]), (C["xc"], C["t"])], start="diamond", end=none)
    m("*", C["xc"] + 0.05, C["t"] - 0.17)
    path(s, [(C["xc"], C["b"]), (CO["xc"], CO["t"])], end=none)
    m("1", C["xc"] + 0.05, C["b"] + 0.02)
    m("*", CO["xc"] + 0.05, CO["t"] - 0.17)
    path(s, [(T["r"], T["yc"]), (CO["l"], CO["yc"])], end=none)
    m("1", T["r"] + 0.03, T["yc"] - 0.17)
    m("*", CO["l"] - 0.1, CO["yc"] - 0.17)
    # offering owns enrollments, learning outcomes and assessments
    xe = CO["l"] + 0.3
    path(s, [(xe, CO["b"]), (xe, E["yc"]), (E["r"], E["yc"])], start="diamond", end=none)
    m("*", E["r"] + 0.03, E["yc"] - 0.17)
    xs = (CO["r"] + LO["l"]) / 2
    yo = CO["t"] + 0.6
    path(s, [(CO["r"], yo), (xs, yo), (xs, LO["yc"]), (LO["l"], LO["yc"])], start="diamond", end=none)
    m("*", LO["l"] - 0.1, LO["yc"] - 0.17)
    xa = CO["l"] + 1.1
    path(s, [(xa, CO["b"]), (xa, AS["t"])], start="diamond", end=none)
    m("*", xa + 0.05, AS["t"] - 0.17)
    # bottom row
    path(s, [(AS["r"], AS["yc"]), (AW["l"], AW["yc"])], end=none)
    m("1", AS["r"] + 0.03, AS["yc"] - 0.17)
    m("*", AW["l"] - 0.1, AW["yc"] - 0.17)
    path(s, [(AS["l"], AS["yc"]), (G["r"], G["yc"])], end=none)
    m("1", AS["l"] - 0.1, AS["yc"] - 0.17)
    m("*", G["r"] + 0.03, G["yc"] - 0.17)
    path(s, [(E["xc"], E["b"]), (G["xc"], G["t"])], end=none)
    m("1", E["xc"] + 0.05, E["b"] + 0.02)
    m("*", G["xc"] + 0.05, G["t"] - 0.17)
    # the User's three links, leaving its bottom edge at three different points
    xa_ = U["l"] + 0.2
    path(s, [(xa_, U["b"]), (xa_, A["t"])], end=none)
    m("1", xa_ + 0.05, U["b"] + 0.02)
    m("*", xa_ + 0.05, A["t"] - 0.17)
    tag(s, "actor", xa_ + 0.06, A["t"] - 0.55, 0.5)
    xs_ = U["l"] + 0.45
    path(s, [(xs_, U["b"]), (xs_, E["yc"]), (E["l"], E["yc"])], end=none)
    m("*", E["l"] - 0.1, E["yc"] - 0.17)
    tag(s, "student", xs_ + 0.06, 3.0, 0.6)
    xi = U["l"] + 1.12
    yav = (C["b"] + T["t"]) / 2
    xi2 = CO["l"] + 0.3 - 0.0
    path(s, [(xi, U["b"]), (xi, yav), (CO["l"] + 0.15, yav), (CO["l"] + 0.15, CO["t"])], end=none)
    m("*", xi + 0.05, U["b"] + 0.02)
    m("*", CO["l"] + 0.2, CO["t"] - 0.17)
    tag(s, "instructors", 1.95, yav - 0.18, 0.9)
    del xi2
    save(prs, "classes")


chain()
velocity()
architecture()
classes()
