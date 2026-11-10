"""Mid-semester report: CSE 311 sections 1-2 and CSE 321 sections 1-2, three printed pages.

Same visual system as the checkpoint deck (TU Berlin style): navy headings, a grey section number,
grey small-caps labels, one note bar per course, Nunito Sans for text and Barlow for labels (both on
Google Docs). Figures come from docs/diagrams/source/build_figures.py.

Run from the repo root:  uv run --no-project --with python-docx python docs/checkpoint/build_report.py OUT.docx
"""

import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1])
FIG = {
    "chain": ROOT / "docs/diagrams/chain.png",
    "architecture": ROOT / "docs/diagrams/architecture.png",
    "classes": ROOT / "docs/diagrams/classes.png",
    "velocity": ROOT / "docs/process/velocity.png",
    "rule": Path(sys.argv[2]) if len(sys.argv) > 2 else None,
}
NAVY, BODY, MUTED = RGBColor(0x10, 0x1E, 0x31), RGBColor(0x2A, 0x36, 0x4A), RGBColor(0x85, 0x93, 0xA8)
PANEL_HEX, RULE_HEX = "EEF1F5", "AEBACA"
SANS, LABEL = "Nunito Sans", "Barlow"
SIZE = 10.5

doc = Document()
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
sec.top_margin, sec.bottom_margin = Cm(1.4), Cm(1.4)
sec.left_margin = sec.right_margin = Cm(2.0)
st = doc.styles["Normal"]
st.font.name, st.font.size = SANS, Pt(SIZE)
st.element.rPr.rFonts.set(qn("w:eastAsia"), SANS)
st.font.color.rgb = BODY
st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(0), Pt(6)
st.paragraph_format.line_spacing = 1.2


def run(para, t, size=SIZE, color=BODY, bold=False, italic=False, font=SANS, caps=False, track=None):
    r = para.add_run(t)
    r.font.size, r.font.bold, r.font.italic, r.font.name = Pt(size), bold, italic, font
    r.font.color.rgb = color
    rpr = r._r.get_or_add_rPr()
    if caps:
        rpr.append(OxmlElement("w:caps"))
    if track:
        sp = OxmlElement("w:spacing")
        sp.set(qn("w:val"), str(int(track * 20)))
        rpr.append(sp)
    return r


def para(after=6, before=0, keep=False, align=None, line=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after, pf.space_before = Pt(after), Pt(before)
    if keep:
        pf.keep_with_next = True
    if align is not None:
        p.alignment = align
    if line:
        pf.line_spacing = line
    return p


def body(*parts, after=6):
    """parts: plain strings, or (text, 'b') for a bold run."""
    p = para(after=after)
    for part in parts:
        if isinstance(part, tuple):
            run(p, part[0], bold=True, color=NAVY)
        else:
            run(p, part)
    return p


def kicker(num, label, before=0, new_page=False):
    p = para(after=1, before=before, keep=True)
    p.paragraph_format.page_break_before = new_page
    run(p, num, 10, MUTED, font=LABEL, bold=True, track=1.0)
    run(p, "    " + label, 10, MUTED, font=LABEL, caps=True, track=1.6)


def heading(t, size=16, before=0, after=6):
    p = para(after=after, before=before, keep=True, line=1.05)
    run(p, t, size, NAVY, bold=True)


def section(t):
    p = para(after=3, before=7, keep=True, line=1.1)
    run(p, t, 11.5, NAVY, bold=True)


def shade(el, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    el.append(shd)


def note(t, before=4, after=8):
    """The deck's note bar: a shaded paragraph."""
    p = para(after=after, before=before, line=1.25)
    ppr = p._p.get_or_add_pPr()
    shade(ppr, PANEL_HEX)
    p.paragraph_format.left_indent = Cm(0.35)
    run(p, t, 10, BODY)


def figure(key, width_cm, caption, before=4):
    p = para(after=2, before=before, keep=True, align=WD_ALIGN_PARAGRAPH.CENTER, line=1.0)
    p.add_run().add_picture(str(FIG[key]), width=Cm(width_cm))
    c = para(after=8, align=WD_ALIGN_PARAGRAPH.CENTER, line=1.1)
    run(c, caption, 8.5, MUTED, italic=True)


def cell_style(cell, fill=None, left=None):
    tcpr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "bottom", "right", "left"):
        e = OxmlElement(f"w:{edge}")
        if edge == "left" and left:
            e.set(qn("w:val"), "single")
            e.set(qn("w:sz"), "24")
            e.set(qn("w:color"), left)
        elif edge in ("top", "bottom"):
            e.set(qn("w:val"), "single")
            e.set(qn("w:sz"), "4")
            e.set(qn("w:color"), RULE_HEX)
        else:
            e.set(qn("w:val"), "nil")
        borders.append(e)
    tcpr.append(borders)
    if fill:
        shade(tcpr, fill)
    mar = OxmlElement("w:tcMar")
    for edge, v in (("top", 45), ("bottom", 45), ("left", 140), ("right", 100)):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:w"), str(v))
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    tcpr.append(mar)


def card_rows(headings, data, widths_cm):
    t = doc.add_table(rows=len(data) + 1, cols=len(widths_cm))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for gc, w in zip(t._tbl.tblGrid.findall(qn("w:gridCol")), widths_cm, strict=True):
        gc.set(qn("w:w"), str(int(w * 567)))
    for j, hd in enumerate(headings):
        c = t.cell(0, j)
        c.width = Cm(widths_cm[j])
        c.text = ""
        tcpr = c._tc.get_or_add_tcPr()
        b = OxmlElement("w:tcBorders")
        for edge in ("top", "left", "right", "bottom"):
            e = OxmlElement(f"w:{edge}")
            e.set(qn("w:val"), "nil")
            b.append(e)
        tcpr.append(b)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        run(p, hd, 8.5, MUTED, font=LABEL, caps=True, track=1.4)
    for i, row in enumerate(data, start=1):
        on = i % 2 == 1
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.width = Cm(widths_cm[j])
            cell_style(c, PANEL_HEX if on else None, None)
            c.text = ""
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            run(p, val, 9.5, NAVY if j == 0 else BODY, bold=j == 0)
    spacer = para(after=4)
    spacer.paragraph_format.line_spacing = 0.8


# ------------------------------------------------------------------ header
p = para(after=0, line=1.0)
run(p, "POlaris", 26, NAVY, bold=True)
p = para(after=4, line=1.1)
run(p, "Mid-semester report, CSE 311 Software and CSE 321 Data Systems, November 2026", 12.5, BODY)
if FIG["rule"]:
    r = para(after=6, line=1.0)
    r.add_run().add_picture(str(FIG["rule"]), width=Cm(2.6))
p = para(after=0, line=1.15)
run(p, "Team POlaris:  ", 10, NAVY, bold=True)
run(p, "Onur Mohamed Haniffa, Fatmanur Demir, Zeynep Uygun", 10)
p = para(after=12, line=1.15)
run(p, "GitHub:  ", 10, NAVY, bold=True)
run(p, "https://github.com/OnurHaniffa/polaris", 10)
run(p, "      Live demo:  ", 10, NAVY, bold=True)
run(p, "web-production-153e9.up.railway.app", 10)

# ------------------------------------------------------------------ CSE 311
kicker("01", "CSE 311 Software")
heading("Tooling and tasking")
section("Section 1. Punchline, key ingredient and backlog tool")
body(
    ("Punchline. ", "b"),
    "Publish a grade, and every student’s Program Outcome profile updates itself. Next, an "
    "instructor will upload a syllabus and get the course set up for them, planned for Sprint 6.",
)
body(
    ("Key ingredient. ", "b"),
    "One small scoring engine that every number goes through (Figure 2, page 2). We wrote "
    "it test-first, it reproduces the worked example in the brief exactly, and the project has 1,162 automated tests.",
)
body(
    ("Backlog tool. ", "b"),
    "We formed the backlog by answering the brief’s thirteen design questions in a project "
    "specification in our repository, then writing 70 user stories, baseline first, "
    "over ten one-week sprints, each with an owner and a point estimate. We manage it through GitHub: one branch and "
    "pull request per story (19 merged, CI on every one) and, from Sprint 4, a Projects board. We talk in a WhatsApp "
    "group, meet briefly after lectures, and plan and review sprints on online calls.",
)
section("Section 2. Who did what, difficulty, sprints and velocity")
body(
    "Three areas, each a slice with its own screens: engine and data, the instructor side, and the platform with "
    "its overviews. What each of us carried out so far:",
    after=4,
)
card_rows(
    ["member", "what they carried out"],
    [
        (
            "Onur Mohamed Haniffa",
            "Project specification and build guide, repository, CI and Docker, tests and admin for "
            "the Sprint 1 domain, design system, login and navigation, department pages, course setup, both weight grids, "
            "grade sheet, mapping checks, password reset, deployment on Railway, diagrams",
        ),
        (
            "Fatmanur Demir",
            "Roles and permissions, publishing grades, student PO profile, instructor course results, "
            "department overview, enrollment import from CSV, second version of the demo data, gradebook file research",
        ),
        (
            "Zeynep Uygun",
            "Data model and migrations, the department’s 11 official program outcomes, scoring engine and "
            "data loaders, first demo data",
        ),
    ],
    [3.9, 13.1],
)
body(
    ("Difficulty. ", "b"),
    "We play planning poker with story points on a Fibonacci scale (1, 2, 3, 5, 8; anything "
    "bigger gets split). Everyone shows a card at once; when votes are far apart, the highest and lowest explain "
    "before a second vote. Reference stories keep the scale honest: an admin page is a 1, a simple form a 2, an "
    "interactive grid a 5. We did not record first-round votes in the early sprints; we do now.",
)
body(
    ("Sprints and velocity. ", "b"),
    "One week, Monday to Sunday; four finished so far (Sprint 0 was a three-day "
    "setup sprint). A story counts in the week it was merged with its tests passing, and half-done work counts zero: "
    "on average 22 points a week, 89 of the 99 we planned (Figure 1, page 3).",
)

# ------------------------------------------------------------------ CSE 321
kicker("02", "CSE 321 Data Systems", new_page=True)
heading("Data and system architecture")
section("Section 1. Introduction: key features")
body(
    "POlaris keeps every student’s Program Outcome (PO) scores for the department. Grades feed a course’s learning "
    "outcomes through percentage weights, and learning outcomes feed the department’s POs through weights, each "
    "step a weighted average (Figure 2). Only published grades count, and a missing grade is skipped rather than "
    "treated as zero."
)
figure("chain", 15.0, "Figure 2. The scoring chain, using the worked example from the project brief.", before=2)
body(
    ("Department heads ", "b"),
    "set up terms, courses and offerings, assign instructors, enrol students (also from a "
    "CSV file, with a preview first) and see an overview of the department. ",
    ("Instructors ", "b"),
    "define learning outcomes and assessments, fill in the two weight grids, enter grades in a spreadsheet-style "
    "sheet and publish them; every change is recorded. ",
    ("Students ", "b"),
    "see their score for each PO and the "
    "courses behind it. Next come reading syllabi with the Claude API, uploading whole gradebooks, and PDF reports.",
)
section("Section 2. System design")
body(
    "The browser talks to one Django 6.1 application that renders pages on the server; HTMX updates small parts of "
    "a page, such as one cell of a weight grid, without a reload. The app runs on Railway, which also handles HTTPS. "
    "PostgreSQL 18 is the system of record and enforces our constraints. Redis 8.2 is the cache today and will be "
    "the job queue for a background worker, so slow work such as calling the Claude API never holds up a page."
)
figure("architecture", 15.6, "Figure 3. System architecture. Solid boxes run today; dashed boxes are planned.")
note("Publishing grades is one database transaction, so a student never sees half-published results.", before=0, after=6)

# ------------------------------------------------------------------ page 3
kicker("01", "CSE 311 Software, section 2 continued", new_page=True)
figure("velocity", 13.0, "Figure 1. Planned and completed story points per sprint.", before=2)
note(
    "Sprint 1 looks empty because its code was merged before its tests, so those points only counted in Sprint 2. "
    "Since then, tests go in the same pull request as the code.",
    before=0,
    after=14,
)
kicker("02", "CSE 321 Data Systems, section 2 continued")
heading("Classes and relationships", size=14, after=4)
body(
    "The class diagram (Figure 4) has 15 core classes. A Program has versioned sets of its 11 POs. A Course "
    "runs as a CourseOffering in a Term, and each offering owns its learning outcomes, assessments and enrollments. "
    "Two classes hold the weights: AssessmentLOWeight links an assessment to a learning outcome with a percentage, "
    "and LOPOWeight links a learning outcome to a PO with a value from 1 to 5. A Grade joins one assessment with one "
    "enrollment and keeps a draft and a published score; AuditEvent records who changed what."
)

figure(
    "classes",
    13.6,
    "Figure 4. The 15 core classes with key attributes and multiplicities. A filled diamond means "
    "the part cannot exist without its owner; the two classes with a dark edge carry the weights.",
)
doc.save(OUT)
print("wrote", OUT)
