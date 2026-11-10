"""Mid-semester checkpoint deck, 12 Nov 2026 (CSE 311 + CSE 321, max 6 slides, no title slide).

Built on the TU Berlin deck system from the MSLesSeg preprocessing deck (same geometry, palette and
components). The deck is presented from Google Slides, which has no Avenir Next or DIN Alternate,
so the text uses their closest Google fonts: Nunito Sans and Barlow. The figures are images made
by docs/diagrams/source/build_figures.py with the original fonts.

Run from the repo root:  uv run --no-project --with python-pptx --with pillow python docs/checkpoint/build_deck.py
"""

import json
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
FIG = {
    "chain": ROOT / "docs/diagrams/chain.png",
    "architecture": ROOT / "docs/diagrams/architecture.png",
    "classes": ROOT / "docs/diagrams/classes.png",
    "velocity": ROOT / "docs/process/velocity.png",
}
OUT = ROOT / "docs/checkpoint/POlaris_checkpoint.pptx"

NAVY = RGBColor(0x10, 0x1E, 0x31)
BODY = RGBColor(0x2A, 0x36, 0x4A)
MUTED = RGBColor(0x85, 0x93, 0xA8)
AMBER = RGBColor(0xF9, 0xA2, 0x43)
PANEL = RGBColor(0xEE, 0xF1, 0xF5)
RULE = RGBColor(0xAE, 0xBA, 0xCA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SANS, LABEL = "Nunito Sans", "Barlow"
MX, CW = 0.60, 12.13
RM = MX + CW
FOOTER_TEXT = "POlaris  ·  Mid-semester update  ·  Acıbadem University  ·  November 2026"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
_N = [0]


def blank():
    _N[0] += 1
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = WHITE
    return s


def notes(s, t):
    s.notes_slide.notes_text_frame.text = t.strip()


def _run(p, t, size, color, bold=False, font=SANS, caps=False, track=None):
    r = p.add_run()
    r.text = t
    r.font.size, r.font.bold, r.font.name = Pt(size), bold, font
    r.font.color.rgb = color
    rpr = r._r.get_or_add_rPr()
    if caps:
        rpr.set("cap", "all")
    if track is not None:
        rpr.set("spc", str(int(track * 100)))
    return r


def text(
    s,
    t,
    x,
    y,
    w,
    h,
    size=13.5,
    color=BODY,
    bold=False,
    font=SANS,
    align=PP_ALIGN.LEFT,
    caps=False,
    track=None,
    anchor=None,
    line_spacing=None,
):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    if anchor:
        tf.vertical_anchor = anchor
    for i, para in enumerate(str(t).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if line_spacing:
            p.line_spacing = line_spacing
        _run(p, para, size, color, bold, font, caps, track)
    return tb


def rect(s, x, y, w, h, fill, stroke=None):
    sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.shadow.inherit = False
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if stroke:
        sh.line.color.rgb = stroke
        sh.line.width = Pt(0.75)
    else:
        sh.line.fill.background()
    return sh


def footer(s):
    text(s, FOOTER_TEXT, MX, 7.15, 9.5, 0.3, size=9, color=MUTED)
    text(s, str(_N[0]), RM - 1.0, 7.05, 1.0, 0.3, size=10, font=LABEL, color=NAVY, align=PP_ALIGN.RIGHT)


def header(s, kicker, title):
    tb = s.shapes.add_textbox(Inches(MX), Inches(0.42), Inches(9.0), Inches(0.3))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    _run(p, f"{_N[0]:02d}", 11, AMBER, font=LABEL, track=1.0)
    _run(p, "    " + kicker, 11, MUTED, font=LABEL, caps=True, track=1.6)
    text(s, title, MX, 0.72, CW, 0.8, size=27, color=NAVY, bold=True)
    footer(s)


def label(s, t, x, y, w):
    text(s, t, x, y, w, 0.24, size=10, font=LABEL, caps=True, track=1.4, color=MUTED)


def bullets(s, items, x, y, w, size=13.5, gap=13):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(4.5))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, (lead, rest) in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.3
        _run(p, lead + "   ", size, NAVY, bold=True)
        _run(p, rest, size, BODY)


def rows(s, headings, data, x, y, widths, rowh=0.86, size=12.5):
    cx = x
    for hd, w in zip(headings, widths, strict=True):
        label(s, hd, cx + 0.22, y, w - 0.3)
        cx += w
    y += 0.40
    total = sum(widths)
    for i, row in enumerate(data):
        on = i % 2 == 0
        rect(s, x, y, total, rowh, PANEL if on else WHITE, RULE)
        if on:
            rect(s, x, y, 0.055, rowh, AMBER)
        cx = x
        for j, cell in enumerate(row):
            text(
                s,
                cell,
                cx + 0.22,
                y,
                widths[j] - 0.34,
                rowh,
                size=size,
                color=NAVY if j == 0 else BODY,
                bold=j == 0,
                anchor=MSO_ANCHOR.MIDDLE,
                line_spacing=1.22,
            )
            cx += widths[j]
        y += rowh + 0.10
    return y


def stat(s, big, small, x, y, w, color=NAVY, h=1.35):
    rect(s, x, y, w, h, PANEL)
    rect(s, x, y, 0.055, h, AMBER)
    text(s, big, x + 0.3, y + 0.16, w - 0.5, 0.6, size=30, color=color, bold=True)
    text(s, small, x + 0.3, y + 0.78, w - 0.5, h - 0.86, size=10.5, color=MUTED, line_spacing=1.18)


def note(s, t, y, h=0.95, size=13, x=MX, w=CW):
    rect(s, x, y, w, h, PANEL)
    rect(s, x, y, 0.055, h, AMBER)
    text(s, t, x + 0.32, y, w - 0.6, h, size=size, color=BODY, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.3)


NO_IMAGES = "--no-images" in sys.argv  # for the Google Slides upload; figures go in through the Slides API
PLACEMENTS = []


def fig(s, key, x, y, w, h):
    iw, ih = Image.open(FIG[key]).size
    ar = iw / ih
    ww, hh = w, w / ar
    if hh > h:
        hh, ww = h, h * ar
    box = (x + (w - ww) / 2, y + (h - hh) / 2, ww, hh)
    PLACEMENTS.append({"slide": _N[0], "figure": key, "x": box[0], "y": box[1], "w": box[2], "h": box[3]})
    if not NO_IMAGES:
        s.shapes.add_picture(str(FIG[key]), *(Inches(v) for v in box))


# ------------------------------------------------------------------ 1  the idea
s = blank()
header(s, "The idea", "Publish a grade, and every student’s PO profile updates itself")
fig(s, "chain", MX, 1.72, CW, 3.55)
note(
    s,
    "The key ingredient is one small scoring engine that every number goes through. We wrote it "
    "test-first. It reproduces the worked example in the brief to the decimal, and 1,162 automated "
    "tests guard it.",
    5.55,
    h=1.05,
)
text(s, "Live:  web-production-153e9.up.railway.app", MX, 6.72, CW, 0.3, size=11, color=MUTED)
notes(
    s,
    """
About 75 seconds. This is the brief's own example, Elif. Her midterm is 90 and her project 80. The course says
the midterm counts 60 percent toward learning outcome 1 and the project 40, so LO 1 is 86.0. LO 2 works the
same way and comes out at 82.9. Then each learning outcome feeds the department's program outcomes with a
weight, and PO 1 lands on 85.0. Every arrow is a weighted average, and nothing else. POlaris does exactly this
for every student, every course and every PO, and the moment an instructor publishes a grade, the profile
updates. The engine was written test-first and reproduces this example exactly. It is live on Railway.
""",
)

# ------------------------------------------------------------------ 2  how we planned
s = blank()
header(s, "How we planned", "We turned the brief into 70 user stories and ten weekly sprints")
w, g = 2.86, 0.23
steps = [
    ("13", "design questions in the brief,\nanswered one by one"),
    ("1", "project specification,\nkept in our repository"),
    ("70", "user stories, baseline first,\neach with an owner and points"),
    ("10", "one-week sprints, one branch\nand pull request per story"),
]
for i, (big, small) in enumerate(steps):
    stat(s, big, small, MX + i * (w + g), 1.78, w, h=1.5)
rows(
    s,
    ["where we work", "what for"],
    [
        ("WhatsApp group", "day-to-day questions and decisions"),
        ("After lectures", "short in-person syncs"),
        ("Online calls", "planning and reviewing each sprint"),
        ("GitHub", "19 merged pull requests so far, CI on every one, and the project board from Sprint 4"),
    ],
    MX,
    3.62,
    [3.0, 9.13],
    rowh=0.56,
    size=12.5,
)
notes(
    s,
    """
About 80 seconds. We formed the backlog straight from the brief. It ends with thirteen design questions,
who enters grades, who sees what and so on, and we answered each one in a project specification that lives in
the repository. From that we wrote 70 user stories in the "As a ..., I want ..., so that ..." form, put the
baseline the brief asks for first, and spread them over ten one-week sprints. Every story has an owner and a
point estimate. We manage the work through GitHub: one branch and one pull request per story, nineteen merged
so far, and CI runs on every one. Day to day we use a WhatsApp group, we sync after lectures, and we plan and
review sprints on calls.
""",
)

# ------------------------------------------------------------------ 3  who did what
s = blank()
header(s, "Who did what", "Three people, three slices of the product")
rows(
    s,
    ["member", "what they have built so far"],
    [
        (
            "Onur Mohamed Haniffa",
            "Project specification and build guide, repository, CI and Docker, design system, login and "
            "navigation, department pages, course setup and both weight grids, grade sheet, "
            "deployment on Railway",
        ),
        (
            "Fatmanur Demir",
            "Roles and permissions, publishing grades, student PO profile, instructor course results, "
            "department overview, enrollment import from CSV, second version of the demo data",
        ),
        (
            "Zeynep Uygun",
            "Data model and migrations, the department’s 11 official program outcomes, scoring engine "
            "and data loaders, first demo data",
        ),
    ],
    MX,
    1.78,
    [3.0, 9.13],
    rowh=1.12,
    size=13,
)
text(s, "Each item is a user story with an owner. The report lists the story numbers.", MX, 6.05, CW, 0.3, size=11, color=MUTED)
notes(
    s,
    """
About 70 seconds. We split the product into three areas, so each of us owns a vertical slice with its own
screens. Onur set up the project and the platform and built most of the instructor side. Fatmanur built roles
and permissions, publishing and the views students and the department see. Zeynep built the domain core: the
data model, the official program outcomes and the scoring engine. Every item here is a story with an owner on
our backlog, and the report lists the story numbers.
""",
)

# ------------------------------------------------------------------ 4  how fast
s = blank()
header(s, "How fast", "About 22 points a week, once tests shipped with the code")
fig(s, "velocity", MX, 1.72, 8.25, 3.45)
sx, sw = 9.12, RM - 9.12
stat(s, "1 week", "sprint length,\nMonday to Sunday", sx, 1.78, sw, h=1.05)
stat(s, "4 done", "sprints completed,\nSprint 4 is running", sx, 2.98, sw, h=1.05)
stat(s, "89 of 99", "planned points\ncompleted", sx, 4.18, sw, h=1.05)
note(
    s,
    "We size stories with planning poker on a Fibonacci scale. Sprint 1 looks empty because its code was merged "
    "before its tests, so those points only counted in Sprint 2. Now tests go in the same pull request.",
    5.55,
    h=1.05,
)
notes(
    s,
    """
About 85 seconds. We estimate in story points, relative size not hours, using planning poker on 1, 2, 3, 5
and 8. Everyone shows a card at once, and if the votes are far apart the highest and lowest explain before we
vote again. Sprints are one week, Monday to Sunday, and we have finished four. A story only counts in the week
it was merged with its tests passing, and half-done work counts zero. That is why Sprint 1 looks empty and
Sprint 2 jumps to 65: the Sprint 1 code went in before its tests. The average is 22 points a week, and since
then tests ship in the same pull request as the code.
""",
)

# ------------------------------------------------------------------ 5  how it runs
s = blank()
header(s, "How it runs", "One Django app on Railway, with PostgreSQL and Redis behind it")
fig(s, "architecture", MX, 1.62, CW, 3.85)
note(
    s,
    "Publishing grades is one database transaction, so a student never sees half-published results. "
    "The dashed boxes are next: a background worker, the Claude API for reading syllabi, and email.",
    5.62,
    h=1.0,
)
notes(
    s,
    """
About 80 seconds. This is the CSE 321 side. The browser talks to one Django application that renders pages
on the server, and HTMX updates single parts of a page, like one cell of a weight grid, without a reload. It
runs on Railway, which also gives us HTTPS. PostgreSQL is the system of record and enforces our constraints;
publishing grades runs as one transaction, so students never see half the grades of an assessment. Redis is
the cache today and becomes the job queue when the worker arrives, so a slow call to the Claude API never holds
up a page. Code reaches Railway from GitHub, where CI runs our 1,162 tests.
""",
)

# ------------------------------------------------------------------ 6  the data underneath
s = blank()
header(s, "The data underneath", "Fifteen classes, and two of them carry every weight")
fig(s, "classes", MX, 1.6, 5.95, 5.3)
bullets(
    s,
    [
        ("AssessmentLOWeight", "links an assessment to a learning outcome with a percentage."),
        ("LOPOWeight", "links a learning outcome to a program outcome with a weight from 1 to 5."),
        ("Grade", "keeps a draft and a published score, so publishing never loses the draft."),
        ("AuditEvent", "records who changed what, before and after."),
    ],
    6.95,
    1.78,
    RM - 6.95,
    size=13,
    gap=11,
)
note(
    s,
    "Next: upload a syllabus and let the Claude API draft the course setup (Sprint 6), then bulk gradebook "
    "upload and PDF reports.",
    5.7,
    h=1.05,
    size=12.5,
    x=6.95,
    w=RM - 6.95,
)
notes(
    s,
    """
About 75 seconds. Underneath it all are fifteen classes. A program has versioned sets of its eleven program
outcomes. A course runs as an offering in a term, and the offering owns its learning outcomes, assessments
and enrollments. The two classes marked in amber carry every weight in the scoring chain you saw on the first
slide. A grade joins one assessment and one enrollment and keeps a draft and a published score, and every
change is recorded in the audit log. Next, in Sprint 6, an instructor will upload a syllabus and the Claude API
will draft the course setup for them to review. Then bulk gradebook upload and PDF reports. Thank you.
""",
)

out = OUT.with_name(OUT.stem + "_noimages.pptx") if NO_IMAGES else OUT
prs.save(out)
OUT.with_name("figure_placements.json").write_text(json.dumps(PLACEMENTS, indent=1))
print(f"wrote {out}  ({_N[0]} slides)")
