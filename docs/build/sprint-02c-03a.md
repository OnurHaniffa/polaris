# Sprint 2 (continued)

This file covers two Sprint 2 stories, **S2-06** (the grade sheet) and **S2-08** (staging deployment), and the first stories of Sprint 3. The rest of Sprint 2 is in its own chapters.

S2-06 needs S1-04 (`Grade`, `AuditEvent`) and S2-02 (decorators, permission matrix) merged first. S2-08 needs nothing except a green CI. Start it on **Monday**: it is the riskiest story of the sprint because it involves a server, DNS and secrets, and those fail in ways you can't predict.

---

## S2-06 · Grade sheet with HTMX inline save and keyboard navigation

**Points:** 5 · **Owner:** Person A · **Branch:** `feature/S2-06-grade-sheet` · **Depends on:** S1-04, S1-08, S1-09, S2-02

### Goal

An instructor opens `/offerings/<id>/grades/` and sees a spreadsheet: one row per enrolled student and one column per assessment. They type a score, press Enter, and the value saves straight away as a **draft**, with a green tick or a red error message, and the cursor moves to the next row. Students never see drafts; publishing is S3-01. This story delivers Part 6 **B6 AC 1–4**, and the draft half of **B7 AC 3**.

How a cell save works, in one picture:

```
type "85,5" ─► change event ─► HTMX POST /offerings/7/grades/cell/3/41/  (value=85,5)
                                   │
                                   ▼
                        grading.views.cell
                           └─ services.save_grade(user, assessment, enrollment, "85,5")
                                 ├─ parse_score_input  → (Decimal("85.5"), False)
                                 ├─ lock term row, check it is open
                                 ├─ UPDATE/INSERT grade (score only, never published_score)
                                 └─ audit.record("grade.update", before, after)
                                   │
                                   ▼
        response = <td> cell partial (✓ or error)  +  out-of-band <span> with the column's
                   new "unpublished changes" count
                                   │
                                   ▼
             HTMX swaps the <td> in place; the OOB span replaces the header badge
```

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/grading/services.py` | create | `parse_score_input`, `save_grade`, `_lock_open_term` (publish functions are added in S3-01) |
| `apps/grading/selectors.py` | create | `SheetCell`, `SheetRow`, `SheetColumn`, `GradeSheet`, `grade_sheet`, `unpublished_changes` |
| `apps/grading/views.py` | create | `sheet`, `cell` |
| `apps/grading/urls.py` | create | `grading:sheet`, `grading:cell` |
| `config/urls.py` | modify | include `apps.grading.urls` |
| `apps/grading/templates/grading/sheet.html` | create | Page plus three partials: `cell`, `col_head`, `col_status` |
| `static/js/polaris.js` | modify | Grid keyboard navigation |
| `static/css/polaris.css` | modify | Sticky header and column, draft dot, excused style |
| `apps/grading/tests/test_parse_score_input.py` | create | Parser rules, including a Hypothesis round-trip test |
| `apps/grading/tests/test_save_grade.py` | create | Service rules, audit, closed term, cross-offering |
| `apps/grading/tests/test_sheet_views.py` | create | Views, HTMX partial, query counts for 80 × 6 |
| `apps/accounts/tests/test_permission_matrix.py` | modify | Two new URLs |

### Steps

**1. The input parser.**

Every way a score enters the system (a typed cell now, and an uploaded file in T1.1) goes through one function, so `85,5` means the same thing everywhere. The rules:

- Blank means "no grade".
- `EX`, `M` (muaf), `EXC` or `excused` mean excused (policy P6).
- A number may use a dot or a Turkish decimal comma and may have at most 2 decimals, because `Grade.score` has `decimal_places=2`.
- Negative numbers and values above `max_score` are rejected.

We match the text with a regular expression instead of calling `Decimal(text)` directly. `Decimal` happily accepts `"NaN"`, `"Infinity"` and `"1e2"`, and none of those should ever be a grade.

```python
# apps/grading/services.py
"""Writes for the grading app: draft grades (S2-06), publish and unpublish (S3-01)."""
from __future__ import annotations

import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.catalog.models import Enrollment, Term
from apps.catalog.services import ensure_term_open
from apps.core import audit

from .models import Grade

EXCUSED_WORDS = frozenset({"EX", "EXC", "EXCUSED", "M", "MUAF"})
_NUMBER = re.compile(r"^\d{1,5}(?:[.,]\d{1,2})?$")
GRADE_AUDIT_FIELDS = ("score", "is_excused")


def _plain(value: Decimal) -> str:
    """100.00 -> '100', 85.50 -> '85.5'. For messages only."""
    return format(value.normalize(), "f")


def parse_score_input(raw: str | None, max_score: Decimal, *,
                      label: str = "this assessment") -> tuple[Decimal | None, bool]:
    """Turn what an instructor typed into (score, is_excused).

    ""          -> (None, False)   no grade
    "EX", "m"   -> (None, True)    excused (P6)
    "85,5"      -> (Decimal("85.5"), False)
    Raises ValidationError with a message a person can act on.
    """
    text = (raw or "").strip()
    if not text:
        return None, False
    if text.upper() in EXCUSED_WORDS:
        return None, True
    if text.startswith("-"):
        raise ValidationError("Scores can't be negative.", code="negative")
    if not _NUMBER.match(text):
        raise ValidationError(
            "Enter a number like 85 or 85,5 (at most 2 decimals), or EX for excused.",
            code="invalid",
        )
    value = Decimal(text.replace(",", "."))
    if value > max_score:
        raise ValidationError(f"Max for {label} is {_plain(max_score)}", code="over_max")
    return value, False
```

The regular expression allows up to 5 digits before the decimal point. `max_digits=7` with 2 decimals means the database can't hold more than 99999.99. A value that big is already rejected by the max-score check anyway, but the regex stops a 40-digit paste before it reaches `Decimal`.

**2. Lock the term, then save the draft grade.**

§5.6 says closing a term takes `FOR UPDATE` on the term row "so no grade save can sneak in mid-close". That only works if a grade save also touches the term row's lock. We take `FOR NO KEY UPDATE` (Django: `select_for_update(no_key=True)`), the weakest row lock that still conflicts with the close's `FOR UPDATE`.

The cost: two grade saves in the same term queue behind each other for the few milliseconds each one takes. At department scale nobody will notice. Say this trade-off out loud in the CSE 321 report: we picked correctness over a throughput we don't need.

```python
# apps/grading/services.py (continued)

def _lock_open_term(offering) -> None:
    """Lock the offering's term row and refuse if it is closed.
    Must be called inside transaction.atomic()."""
    term = Term.objects.select_for_update(no_key=True).get(pk=offering.term_id)
    offering.term = term          # ensure_term_open reads offering.term.status
    ensure_term_open(offering)


def save_grade(user, assessment, enrollment, raw: str | None) -> Grade | None:
    """Save one draft grade from the grade sheet (B6).

    Writes Grade.score / Grade.is_excused only. Never touches published_score: students
    and every score calculation keep seeing the published value until the next publish (D2).
    Returns the grade, or None when the cell was blank and no grade existed (nothing to do).
    """
    if enrollment.offering_id != assessment.offering_id:
        raise ValidationError("This student is not enrolled in this course.", code="wrong_offering")
    if enrollment.status != Enrollment.Status.ENROLLED:
        raise ValidationError("This student has dropped the course.", code="dropped")
    score, is_excused = parse_score_input(raw, assessment.max_score, label=assessment.name)
    offering = assessment.offering

    with transaction.atomic():
        _lock_open_term(offering)
        grade = (Grade.objects.select_for_update()
                 .filter(assessment=assessment, enrollment=enrollment).first())
        if grade is None:
            if score is None and not is_excused:
                return None                       # blank cell, no grade: nothing to write
            grade = Grade(assessment=assessment, enrollment=enrollment)
            before = None
        else:
            if (grade.score, grade.is_excused) == (score, is_excused):
                return grade                      # unchanged: no write, no audit noise
            before = audit.snapshot(grade, GRADE_AUDIT_FIELDS)

        grade.score = score
        grade.is_excused = is_excused
        grade.updated_by = user
        grade.save()
        audit.record(user, "grade.update", grade,
                     before=before, after=audit.snapshot(grade, GRADE_AUDIT_FIELDS),
                     offering=offering)
    return grade
```

Three details worth defending:

- **`(grade.score, grade.is_excused) == (score, is_excused)`** compares `Decimal("85.00")` from the database with `Decimal("85")` from the parser. `Decimal` compares by value, so they're equal. Retyping the same number writes nothing, which keeps the audit trail readable.
- **Blank on an existing grade** sets `score = None`. We keep the row instead of deleting it, because the row may hold a `published_score` students can still see until the next publish.
- **Two people creating the same grade at the same moment.** One of them gets an `IntegrityError` from `uniq_grade`. That's possible only if an instructor and the head type into the same empty cell in the same second. We accept it: the loser sees a 500 in development and a "Something went wrong, try again" toast in production. Don't build a retry loop for it.

**3. The selector: the whole sheet in three queries.**

A naive template that calls `grade_for(student, assessment)` per cell makes 80 × 6 = 480 queries. Instead we load:

1. the enrolled students,
2. the assessments,
3. every grade of the offering,

then build the grid in Python with a dictionary keyed by `(assessment_id, enrollment_id)`. Django templates can't look up tuple keys, so the selector hands the template ready-made rows of cells.

```python
# apps/grading/selectors.py
"""Reads for the grading app."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from apps.catalog.models import Enrollment
from apps.outcomes.models import Assessment

from .models import Grade


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")


@dataclass(frozen=True)
class SheetCell:
    assessment: Assessment
    enrollment: Enrollment
    grade: Grade | None

    @property
    def input_value(self) -> str:
        """What the <input> shows: '85.5', 'EX' or ''."""
        if self.grade is None:
            return ""
        if self.grade.is_excused:
            return "EX"
        return "" if self.grade.score is None else _plain(self.grade.score)

    @property
    def is_excused(self) -> bool:
        return self.grade is not None and self.grade.is_excused

    @property
    def has_unpublished_change(self) -> bool:
        return self.grade is not None and self.grade.has_unpublished_change


@dataclass(frozen=True)
class SheetRow:
    enrollment: Enrollment
    cells: tuple[SheetCell, ...]


@dataclass(frozen=True)
class SheetColumn:
    assessment: Assessment
    unpublished: int          # grades whose draft differs from what students see
    graded: int               # grades with a score or excused

    @property
    def is_published(self) -> bool:
        return self.assessment.published_at is not None


@dataclass(frozen=True)
class GradeSheet:
    offering: object
    columns: tuple[SheetColumn, ...]
    rows: tuple[SheetRow, ...]
    grades: dict[tuple[int, int], Grade] = field(default_factory=dict)

    @property
    def assessments(self) -> list[Assessment]:
        return [c.assessment for c in self.columns]

    @property
    def students(self) -> list:
        return [r.enrollment.student for r in self.rows]

    @property
    def unpublished_counts(self) -> dict[int, int]:
        return {c.assessment.id: c.unpublished for c in self.columns}


def grade_sheet(offering) -> GradeSheet:
    """Everything the grade sheet shows, in exactly three queries."""
    enrollments = list(
        Enrollment.objects.filter(offering=offering, status=Enrollment.Status.ENROLLED)
        .select_related("student")
        .order_by("student__last_name", "student__first_name", "student__student_number")
    )                                                                         # query 1
    assessments = list(Assessment.objects.filter(offering=offering))          # query 2 (Meta ordering)
    grades = {
        (g.assessment_id, g.enrollment_id): g
        for g in Grade.objects.filter(assessment__offering=offering,
                                      enrollment__status=Enrollment.Status.ENROLLED)
    }                                                                         # query 3

    columns = []
    for a in assessments:
        col = [grades.get((a.id, e.id)) for e in enrollments]
        columns.append(SheetColumn(
            assessment=a,
            unpublished=sum(1 for g in col if g is not None and g.has_unpublished_change),
            graded=sum(1 for g in col if g is not None and (g.score is not None or g.is_excused)),
        ))
    rows = tuple(
        SheetRow(enrollment=e,
                 cells=tuple(SheetCell(a, e, grades.get((a.id, e.id))) for a in assessments))
        for e in enrollments
    )
    return GradeSheet(offering=offering, columns=tuple(columns), rows=rows, grades=grades)


def unpublished_changes(assessment) -> int:
    """How many enrolled students' grades on this assessment differ from the published value.
    One query. Used to refresh the column badge after a single cell save."""
    qs = Grade.objects.filter(assessment=assessment, enrollment__status=Enrollment.Status.ENROLLED)
    return sum(1 for g in qs.only("score", "is_excused", "published_score", "published_is_excused")
               if g.has_unpublished_change)


def column_for(assessment) -> SheetColumn:
    """One column's header numbers (two counts, one query)."""
    qs = Grade.objects.filter(assessment=assessment, enrollment__status=Enrollment.Status.ENROLLED)
    grades = list(qs.only("score", "is_excused", "published_score", "published_is_excused"))
    return SheetColumn(
        assessment=assessment,
        unpublished=sum(1 for g in grades if g.has_unpublished_change),
        graded=sum(1 for g in grades if g.score is not None or g.is_excused),
    )
```

Why count unpublished changes in Python instead of SQL? The comparison involves NULLs: `score IS DISTINCT FROM published_score`. Django can express that, but the Python version reuses `Grade.has_unpublished_change`, which is the single definition of "unpublished change". For 80 rows the cost is nothing.

Dropped students disappear from the sheet. Their grades stay in the database (enrollment history) but are filtered out everywhere by `enrollment__status=ENROLLED`.

**4. Views.**

The decorator from S2-02 loads the offering and checks access. It passes `offering=` and `perms_for=` as keyword arguments. Our views take path arguments as keyword-only parameters and swallow `offering_id` with `**_`, so they work whether or not the decorator keeps `offering_id` in kwargs.

The sheet is **view** access (`edit=False`). An instructor of a closed term can still read their grades; the inputs render disabled. The cell save is **edit** access (`edit=True`).

```python
# apps/grading/views.py
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.decorators import require_offering_access
from apps.catalog.models import Enrollment
from apps.outcomes.models import Assessment

from . import selectors, services
from .selectors import SheetCell


@login_required
@require_GET
@require_offering_access(edit=False)
def sheet(request, *, offering, perms_for, **_):
    data = selectors.grade_sheet(offering)
    return render(request, "grading/sheet.html", {
        "offering": offering,
        "perms_for": perms_for,
        "sheet": data,
    })


@login_required
@require_POST
@require_offering_access(edit=True)
def cell(request, *, offering, perms_for, assessment_id, enrollment_id, **_):
    assessment = get_object_or_404(Assessment, pk=assessment_id, offering=offering)
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("student"),
        pk=enrollment_id, offering=offering, status=Enrollment.Status.ENROLLED,
    )
    raw = request.POST.get("value", "")
    ctx = {"offering": offering, "perms_for": perms_for}
    try:
        grade = services.save_grade(request.user, assessment, enrollment, raw)
    except ValidationError as exc:
        current = assessment.grades.filter(enrollment=enrollment).first()
        ctx |= {"cell": SheetCell(assessment, enrollment, current),
                "error": " ".join(exc.messages), "raw": raw}
        # 200, not 422: HTMX 2 does not swap 4xx responses by default, and we want the red cell shown.
        return HttpResponse(render_to_string("grading/sheet.html#cell", ctx, request))

    ctx |= {"cell": SheetCell(assessment, enrollment, grade), "saved": True}
    html = render_to_string("grading/sheet.html#cell", ctx, request)
    html += render_to_string("grading/sheet.html#col_status", {
        "column": selectors.column_for(assessment), "oob": True,
        "offering": offering, "perms_for": perms_for,      # S3-01 puts the Publish button in this partial
    }, request)
    return HttpResponse(html)
```

`render_to_string("grading/sheet.html#cell", …)` renders only the `cell` partial: Django 6's template partials, see §8.5. The second partial carries `hx-swap-oob="true"`. HTMX finds the element with the same `id` anywhere on the page and replaces it, so the column header's "3 unpublished" badge updates without a second request.

```python
# apps/grading/urls.py
from django.urls import path

from . import views

app_name = "grading"

urlpatterns = [
    path("offerings/<int:offering_id>/grades/", views.sheet, name="sheet"),
    path("offerings/<int:offering_id>/grades/cell/<int:assessment_id>/<int:enrollment_id>/",
         views.cell, name="cell"),
]
```

In `config/urls.py`, add the include next to the other apps:

```python
path("", include("apps.grading.urls")),
```

**5. The template.**

Partials are defined once at the top with `{% partialdef %}` (not `inline`) and used with `{% partial %}` inside the loops, which is the pattern in the Django docs.

- `col_status` is the badge in each column header.
- `col_head` is the whole header cell. S3-01 adds the Publish button here.
- `cell` is one `<td>`.

```django
{# apps/grading/templates/grading/sheet.html #}
{% extends "base.html" %}
{% load polaris %}

{% block title %}Grades · {{ offering.course.code }}{% endblock %}

{% partialdef col_status %}
<span id="col-status-{{ column.assessment.id }}" class="small d-block"
      {% if oob %}hx-swap-oob="true"{% endif %}>
  {% if column.is_published %}
    <span class="badge text-bg-success">Published</span>
  {% else %}
    <span class="badge text-bg-secondary">Draft</span>
  {% endif %}
  {% if column.unpublished %}
    <span class="badge text-bg-warning" title="Changes students can't see yet">
      {{ column.unpublished }} unpublished
    </span>
  {% endif %}
</span>
{% endpartialdef %}

{% partialdef col_head %}
<th scope="col" class="text-end align-bottom">
  <div class="fw-semibold">{{ column.assessment.name }}</div>
  <div class="text-body-secondary small">max {{ column.assessment.max_score|weight }}</div>
  {% partial col_status %}
</th>
{% endpartialdef %}

{% partialdef cell %}
<td id="cell-{{ cell.assessment.id }}-{{ cell.enrollment.id }}"
    class="grade-cell{% if cell.has_unpublished_change %} has-draft{% endif %}{% if cell.is_excused %} is-excused{% endif %}">
  <input type="text" inputmode="decimal" autocomplete="off" spellcheck="false"
         id="g-{{ cell.assessment.id }}-{{ cell.enrollment.id }}"
         name="value"
         class="form-control form-control-sm grade-input{% if error %} is-invalid{% elif saved %} is-valid{% endif %}"
         value="{% if error %}{{ raw }}{% else %}{{ cell.input_value }}{% endif %}"
         aria-label="{{ cell.assessment.name }}, {{ cell.enrollment.student.get_full_name }}"
         {% if error %}aria-invalid="true" aria-describedby="err-{{ cell.assessment.id }}-{{ cell.enrollment.id }}"{% endif %}
         {% if not perms_for.can_edit %}disabled{% endif %}
         hx-post="{% url 'grading:cell' offering_id=offering.id assessment_id=cell.assessment.id enrollment_id=cell.enrollment.id %}"
         hx-trigger="change"
         hx-target="closest td"
         hx-swap="outerHTML">
  {% if error %}
    <div class="invalid-feedback" id="err-{{ cell.assessment.id }}-{{ cell.enrollment.id }}">{{ error }}</div>
  {% endif %}
  {% if cell.has_unpublished_change %}<span class="visually-hidden">Unpublished change</span>{% endif %}
</td>
{% endpartialdef %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h3 mb-0">Grades · {{ offering.course.code }} {{ offering.course.title }}</h1>
  <span class="text-body-secondary">{{ offering.term.name }} · {{ sheet.rows|length }} students</span>
</div>

{% if perms_for.is_closed %}
  <div class="alert alert-secondary">This term is closed. Grades are read-only.</div>
{% endif %}

{% if not sheet.columns %}
  {% url 'outcomes:setup' offering_id=offering.id as setup_url %}
  {% include "includes/empty_state.html" with title="No assessments yet" message="Add your midterm, final and other assessments first. Then come back here to enter grades." action_url=setup_url action_label="Set up assessments" only %}
{% elif not sheet.rows %}
  {% include "includes/empty_state.html" with title="No students enrolled" message="The department head adds students to this course. Ask them, or check back later." only %}
{% else %}
  <p class="text-body-secondary small mb-2">
    Type a score and press <kbd>Enter</kbd>. Use <kbd>EX</kbd> for excused. Arrow keys move between cells.
    Saved values are <strong>drafts</strong>: students see them only after you publish the column.
  </p>
  <div class="grade-sheet-wrap border rounded">
    <table class="table table-sm align-middle mb-0 grade-sheet">
      <thead>
        <tr>
          <th scope="col">Student</th>
          {% for column in sheet.columns %}{% partial col_head %}{% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for row in sheet.rows %}
          <tr>
            <th scope="row" class="text-nowrap">
              <span class="font-monospace small text-body-secondary">{{ row.enrollment.student.student_number }}</span>
              {{ row.enrollment.student.last_name }}, {{ row.enrollment.student.first_name }}
            </th>
            {% for cell in row.cells %}{% partial cell %}{% endfor %}
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
{% endif %}
{% endblock %}
```

`|weight` is the filter from §4.8 that drops trailing zeros (`100.00` → `100`). The `includes/empty_state.html` parameters (`title`, `text`, `action_url`, `action_label`) are the ones S1-09 defined. If S1-09 named them differently, use those names.

**6. Keyboard navigation.**

Spreadsheet people expect four things:

- Enter goes down, and Shift+Enter goes up.
- Arrows move between cells.
- Esc undoes the cell you're in.
- Focusing a cell selects its text, so typing replaces the value.

The listener is attached once to `document` (event delegation). It keeps working after HTMX swaps a `<td>`, because it never holds a reference to a specific input.

When you press Enter, focus moves to the next row first. The browser then fires `change` on the cell you left, HTMX posts it, and the response replaces only that old `<td>`. You keep typing in the new cell while the old one saves.

```javascript
// static/js/polaris.js  (add below the existing code)
(function gradeGrid() {
  "use strict";

  function inputAt(table, rowIndex, colIndex) {
    const row = table.tBodies[0] && table.tBodies[0].rows[rowIndex];
    if (!row) return null;
    const cell = row.cells[colIndex];
    return cell ? cell.querySelector("input.grade-input:not([disabled])") : null;
  }

  function moveTo(input) {
    if (!input) return false;
    input.focus();
    input.select();
    return true;
  }

  document.addEventListener("focusin", function (event) {
    if (event.target.matches && event.target.matches("input.grade-input")) {
      event.target.select();
    }
  });

  document.addEventListener("keydown", function (event) {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.classList.contains("grade-input")) return;

    const td = input.closest("td");
    const tr = td.closest("tr");
    const table = tr.closest("table");
    const row = tr.sectionRowIndex;
    const col = td.cellIndex;
    const len = input.value.length;
    const allSelected = input.selectionStart === 0 && input.selectionEnd === len;

    let target = null;
    switch (event.key) {
      case "Enter":
        target = inputAt(table, event.shiftKey ? row - 1 : row + 1, col);
        event.preventDefault();
        if (!target) input.blur();          // last row: still save the cell
        break;
      case "ArrowDown":
        target = inputAt(table, row + 1, col);
        break;
      case "ArrowUp":
        target = inputAt(table, row - 1, col);
        break;
      case "ArrowLeft":
        if (allSelected || input.selectionStart === 0) target = inputAt(table, row, col - 1);
        break;
      case "ArrowRight":
        if (allSelected || input.selectionEnd === len) target = inputAt(table, row, col + 1);
        break;
      case "Escape":
        input.value = input.defaultValue;   // undo typing in this cell, nothing is sent
        input.select();
        return;
      default:
        return;
    }
    if (moveTo(target)) event.preventDefault();
  });
})();
```

`input.defaultValue` is the `value` attribute the server rendered, so Escape always returns to the last saved value.

`td.cellIndex` counts the student-name `<th>` too. That's fine, because every row has the same structure.

**7. CSS: a sticky header and first column, and the draft dot.**

`position: sticky` only works inside a scrolling container. That is why the table lives in `.grade-sheet-wrap`, which has a maximum height and scrolls in both directions. The header cells need a background colour, or rows show through them while scrolling.

The draft dot is never colour alone: every dotted cell also contains the visually-hidden text "Unpublished change" for screen readers (§8.2 accessibility rule).

```css
/* static/css/polaris.css  (add) */
.grade-sheet-wrap { max-height: 75vh; overflow: auto; }
.grade-sheet { border-collapse: separate; border-spacing: 0; }
.grade-sheet thead th {
  position: sticky; top: 0; z-index: 2;
  background: var(--bs-body-bg);
  box-shadow: inset 0 -1px 0 var(--bs-border-color);
}
.grade-sheet tbody th {
  position: sticky; left: 0; z-index: 1;
  background: var(--bs-body-bg);
  box-shadow: inset -1px 0 0 var(--bs-border-color);
}
.grade-sheet thead th:first-child { left: 0; z-index: 3; }
.grade-cell { position: relative; min-width: 6.5rem; padding: .25rem .35rem; }
.grade-cell .grade-input { text-align: right; font-variant-numeric: tabular-nums; }
.grade-cell .invalid-feedback { white-space: normal; font-size: .75rem; }
.grade-cell.has-draft::after {
  content: ""; position: absolute; top: .4rem; right: .4rem;
  width: .45rem; height: .45rem; border-radius: 50%;
  background: var(--pl-draft, #f59f00);
}
.grade-cell.is-excused .grade-input { font-style: italic; color: var(--bs-secondary-color); }
```

`--pl-draft` is the amber draft token from §8.2. If S1-09 named it differently, use that name; the `#f59f00` fallback keeps the dot visible either way.

**8. The permission matrix.**

Each URL already has a row in `ROUTES` (`apps/accounts/tests/routes.py`, written in S2-02). A row switches on by itself once its URL resolves, so there is nothing to add; run the matrix test and check it gives these results:

| URL name | kwargs | Method | anonymous | student | instructor (other course) | instructor (own) | head | admin |
|---|---|---|---|---|---|---|---|---|
| `grading:sheet` | `offering_id` | GET | 302 | 404 | 404 | 200 | 200 | 200 |
| `grading:cell` | `offering_id`, `assessment_id`, `enrollment_id` | POST `value=50` | 302 | 404 | 404 | 200 | 200 | 200 |

### Tests

```python
# apps/grading/tests/test_parse_score_input.py
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from hypothesis import given
from hypothesis import strategies as st

from apps.grading.services import parse_score_input

MAX = Decimal("100")


@pytest.mark.parametrize(("raw", "expected"), [
    ("85", (Decimal("85"), False)),
    ("85,5", (Decimal("85.5"), False)),        # Turkish decimal comma
    (" 85.50 ", (Decimal("85.50"), False)),
    ("0", (Decimal("0"), False)),               # a real zero is a grade, not "missing"
    ("100", (Decimal("100"), False)),           # exactly max is fine
    ("", (None, False)),
    ("   ", (None, False)),
    (None, (None, False)),
    ("EX", (None, True)),
    ("ex", (None, True)),
    ("M", (None, True)),
    ("excused", (None, True)),
])
def test_accepted_inputs(raw, expected):
    assert parse_score_input(raw, MAX) == expected


@pytest.mark.parametrize(("raw", "code"), [
    ("105", "over_max"),
    ("100.01", "over_max"),
    ("-1", "negative"),
    ("abc", "invalid"),
    ("NaN", "invalid"),
    ("Infinity", "invalid"),
    ("1e2", "invalid"),
    ("85.555", "invalid"),       # 3 decimals don't fit decimal_places=2
    ("8 5", "invalid"),
    ("85,5,1", "invalid"),
])
def test_rejected_inputs(raw, code):
    with pytest.raises(ValidationError) as exc:
        parse_score_input(raw, MAX)
    assert exc.value.code == code


def test_over_max_message_names_the_assessment():
    with pytest.raises(ValidationError) as exc:
        parse_score_input("105", Decimal("100.00"), label="Midterm I")
    assert exc.value.messages == ["Max for Midterm I is 100"]


@given(st.integers(min_value=0, max_value=10_000).map(lambda cents: Decimal(cents) / 100))
def test_round_trip_any_valid_score(value):
    """Whatever Decimal we print with a dot or a comma comes back unchanged."""
    text = format(value, "f")
    assert parse_score_input(text, MAX) == (value, False)
    assert parse_score_input(text.replace(".", ","), MAX) == (value, False)
```

```python
# apps/grading/tests/test_save_grade.py
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.models import Enrollment, Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import (
    AssessmentFactory, EnrollmentFactory, GradeFactory, OfferingFactory, UserFactory,
)
from apps.grading.models import Grade
from apps.grading.services import save_grade

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    offering = OfferingFactory(term__status=Term.Status.OPEN)
    assessment = AssessmentFactory(offering=offering, name="Midterm I", max_score=Decimal("100"))
    enrollment = EnrollmentFactory(offering=offering)
    return offering, assessment, enrollment, UserFactory()


def test_creates_draft_grade_and_audits(setup):
    offering, assessment, enrollment, user = setup
    grade = save_grade(user, assessment, enrollment, "85,5")
    grade.refresh_from_db()
    assert grade.score == Decimal("85.5")
    assert grade.published_score is None            # draft only (D2)
    assert grade.updated_by == user
    event = AuditEvent.objects.get(action="grade.update", entity_id=grade.pk)
    assert event.before is None
    assert event.after == {"score": "85.50", "is_excused": False}
    assert event.offering == offering
    assert event.actor == user


def test_update_records_before_and_after(setup):
    _, assessment, enrollment, user = setup
    save_grade(user, assessment, enrollment, "75")
    save_grade(user, assessment, enrollment, "78")
    events = list(AuditEvent.objects.filter(action="grade.update").order_by("created_at", "id"))
    assert [e.after["score"] for e in events] == ["75.00", "78.00"]
    assert events[1].before["score"] == "75.00"


def test_same_value_writes_nothing(setup):
    _, assessment, enrollment, user = setup
    save_grade(user, assessment, enrollment, "80")
    save_grade(user, assessment, enrollment, "80.00")
    assert AuditEvent.objects.filter(action="grade.update").count() == 1


def test_blank_cell_without_grade_is_a_no_op(setup):
    _, assessment, enrollment, user = setup
    assert save_grade(user, assessment, enrollment, "") is None
    assert not Grade.objects.exists()
    assert not AuditEvent.objects.exists()


def test_blank_on_existing_grade_clears_draft_but_keeps_published(setup):
    _, assessment, enrollment, user = setup
    GradeFactory(assessment=assessment, enrollment=enrollment, score=Decimal("70"),
                 published_score=Decimal("70"))
    grade = save_grade(user, assessment, enrollment, "")
    grade.refresh_from_db()
    assert grade.score is None
    assert grade.published_score == Decimal("70")   # students still see 70 until the next publish
    assert grade.has_unpublished_change


def test_excused(setup):
    _, assessment, enrollment, user = setup
    grade = save_grade(user, assessment, enrollment, "EX")
    assert grade.is_excused and grade.score is None


def test_over_max_is_rejected_and_nothing_saved(setup):
    _, assessment, enrollment, user = setup
    with pytest.raises(ValidationError, match="Max for Midterm I is 100"):
        save_grade(user, assessment, enrollment, "105")
    assert not Grade.objects.exists()


def test_enrollment_from_another_offering_is_rejected(setup):
    _, assessment, _, user = setup
    stranger = EnrollmentFactory()                   # different offering
    with pytest.raises(ValidationError):
        save_grade(user, assessment, stranger, "50")


def test_dropped_student_is_rejected(setup):
    offering, assessment, _, user = setup
    dropped = EnrollmentFactory(offering=offering, status=Enrollment.Status.DROPPED)
    with pytest.raises(ValidationError):
        save_grade(user, assessment, dropped, "50")


def test_closed_term_is_read_only(setup):
    offering, assessment, enrollment, user = setup
    Term.objects.filter(pk=offering.term_id).update(status=Term.Status.CLOSED)
    with pytest.raises(ValidationError):
        save_grade(user, assessment, enrollment, "50")
    assert not Grade.objects.exists()
```

The audit assertions expect `"85.50"`, because `audit.snapshot` turns `Decimal` into `str` and the value has been read back from a `decimal_places=2` column. If S1-04's `snapshot` reads the in-memory instance before refresh, the string is `"85.5"`. Check what `snapshot` does and keep the test consistent with it. The rule that matters is "a string, never a float".

```python
# apps/grading/tests/test_sheet_views.py
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import ProgramMembership
from apps.catalog.models import Term
from apps.core.tests.factories import (
    AssessmentFactory, EnrollmentFactory, GradeFactory, MembershipFactory, OfferingFactory,
    UserFactory,
)
from apps.grading.models import Grade
from apps.grading.selectors import grade_sheet

pytestmark = pytest.mark.django_db


@pytest.fixture
def course():
    offering = OfferingFactory(term__status=Term.Status.OPEN)
    instructor = UserFactory()
    MembershipFactory(user=instructor, program=offering.course.program,
                      role=ProgramMembership.Role.INSTRUCTOR)
    offering.instructors.add(instructor)
    return offering, instructor


def _big_class(offering, students=80, assessments=6):
    tests = [AssessmentFactory(offering=offering, name=f"A{i}", position=i) for i in range(assessments)]
    for _ in range(students):
        e = EnrollmentFactory(offering=offering)
        for a in tests:
            GradeFactory(assessment=a, enrollment=e, score=Decimal("70"))
    return tests


def test_selector_uses_three_queries(course, django_assert_num_queries):
    offering, _ = course
    _big_class(offering)
    with django_assert_num_queries(3):
        sheet = grade_sheet(offering)
        # touching every cell must not trigger lazy loads
        values = [c.input_value for r in sheet.rows for c in r.cells]
        names = [r.enrollment.student.last_name for r in sheet.rows]
    assert len(values) == 480 and len(names) == 80


def test_sheet_page_80_by_6_has_no_n_plus_one(course, client, django_assert_max_num_queries):
    offering, instructor = course
    _big_class(offering)
    client.force_login(instructor)
    # 3 sheet queries + session, user, offering, memberships and navigation; never 480
    with django_assert_max_num_queries(12):
        response = client.get(reverse("grading:sheet", kwargs={"offering_id": offering.id}))
    assert response.status_code == 200
    assert response.content.count(b'class="form-control form-control-sm grade-input') == 480


def test_htmx_cell_save_returns_only_the_cell(course, client):
    offering, instructor = course
    a = AssessmentFactory(offering=offering, name="Midterm I", max_score=Decimal("100"))
    e = EnrollmentFactory(offering=offering)
    client.force_login(instructor)
    url = reverse("grading:cell", kwargs={"offering_id": offering.id,
                                          "assessment_id": a.id, "enrollment_id": e.id})
    response = client.post(url, {"value": "85,5"}, headers={"HX-Request": "true"})
    body = response.content.decode()
    assert response.status_code == 200
    assert body.lstrip().startswith(f'<td id="cell-{a.id}-{e.id}"')
    assert "is-valid" in body and 'value="85.5"' in body
    assert f'id="col-status-{a.id}"' in body and 'hx-swap-oob="true"' in body
    assert "<html" not in body                                   # partial, not the page
    assert Grade.objects.get().score == Decimal("85.5")


def test_htmx_cell_error_shows_message_and_saves_nothing(course, client):
    offering, instructor = course
    a = AssessmentFactory(offering=offering, name="Midterm I", max_score=Decimal("100"))
    e = EnrollmentFactory(offering=offering)
    client.force_login(instructor)
    url = reverse("grading:cell", kwargs={"offering_id": offering.id,
                                          "assessment_id": a.id, "enrollment_id": e.id})
    response = client.post(url, {"value": "105"}, headers={"HX-Request": "true"})
    body = response.content.decode()
    assert response.status_code == 200
    assert "Max for Midterm I is 100" in body
    assert 'value="105"' in body and "is-invalid" in body       # what they typed stays visible
    assert not Grade.objects.exists()


def test_draft_grade_is_invisible_to_scores(course, client):
    """B6 AC 2: a saved draft does not change what students or scores see."""
    offering, instructor = course
    a = AssessmentFactory(offering=offering, max_score=Decimal("100"))
    e = EnrollmentFactory(offering=offering)
    client.force_login(instructor)
    client.post(reverse("grading:cell", kwargs={"offering_id": offering.id,
                                                "assessment_id": a.id, "enrollment_id": e.id}),
                {"value": "90"})
    grade = Grade.objects.get()
    assert grade.score == Decimal("90") and grade.published_score is None


def test_cell_in_another_offering_is_404(course, client):
    offering, instructor = course
    a = AssessmentFactory(offering=offering)
    other_enrollment = EnrollmentFactory()          # student of a different offering
    client.force_login(instructor)
    url = reverse("grading:cell", kwargs={"offering_id": offering.id,
                                          "assessment_id": a.id, "enrollment_id": other_enrollment.id})
    assert client.post(url, {"value": "50"}).status_code == 404


def test_closed_term_renders_disabled_inputs(course, client):
    offering, instructor = course
    AssessmentFactory(offering=offering)
    EnrollmentFactory(offering=offering)
    Term.objects.filter(pk=offering.term_id).update(status=Term.Status.CLOSED)
    client.force_login(instructor)
    response = client.get(reverse("grading:sheet", kwargs={"offering_id": offering.id}))
    assert b"Grades are read-only" in response.content
    assert b"disabled" in response.content
```

`OfferingFactory(term__status=…)` assumes `OfferingFactory.term` is a `SubFactory(TermFactory)`, which is what S1-08 builds. The `headers=` argument of the test client sends `HX-Request: true`, so `request.htmx` is truthy, exactly as when HTMX posts.

### Check it works

1. `uv run python manage.py seed_demo --reset`. Log in as Dr. Can Aydın (the password is printed by the command) and open CSE 311 → **Grades**.
2. Click the first cell and type `85,5`, then press Enter.
   - **Expected:** the cell shows `85.5` with a green border, the cursor is now one row down, and the column header shows "1 unpublished".
3. Type `105` and press Enter.
   - **Expected:** the cell turns red with the message "Max for Midterm I is 100" and keeps `105`. Press Esc: the old value comes back.
4. Type `ex` and press Enter.
   - **Expected:** the cell shows `EX` in grey italics.
5. Scroll down and right.
   - **Expected:** the header row and the student-name column stay in place.
6. Open the Django debug toolbar → SQL panel.
   - **Expected:** about 10 queries for the whole page, and no query repeated 480 times.
7. Log in as Elif in a private window and open her profile.
   - **Expected:** none of the draft values appear.
8. Django admin → Audit events.
   - **Expected:** one `grade.update` per actual change, with before and after.

### Done when

| AC (Part 6) | Proved by |
|---|---|
| B6 AC 1: 105 over max shows "Max for Midterm I is 100", nothing saved | `test_over_max_is_rejected_and_nothing_saved`, `test_htmx_cell_error_shows_message_and_saves_nothing` |
| B6 AC 2: draft not visible, no effect on scores | `test_draft_grade_is_invisible_to_scores`; scores read `published_score` only (S1-07 loader tests) |
| B6 AC 3: 80 × 6 with no N+1 | `test_selector_uses_three_queries`, `test_sheet_page_80_by_6_has_no_n_plus_one` |
| B6 AC 4: keyboard-only entry | Manual check steps 2–4. The Playwright journey in S7-06 automates it |
| B7 AC 3 (draft half): editing a published grade doesn't change what students see | `test_blank_on_existing_grade_clears_draft_but_keeps_published` (more in S3-01) |
| B7 AC 4 (grade part): every grade change audited | `test_creates_draft_grade_and_audits`, `test_update_records_before_and_after` |
| Permissions | Matrix rows for `grading:sheet` and `grading:cell` |

### Commits and PR

```
Add score input parser with Turkish decimal comma and EX (#S2-06)
Add save_grade service with term lock and audit (#S2-06)
Add grade sheet selector that loads in three queries (#S2-06)
Add grade sheet page with HTMX cell saves and keyboard navigation (#S2-06)
```

PR title: **Grade sheet with inline saving and keyboard navigation (S2-06)**. Replace `S2-06` in the commit messages with the real GitHub issue number.

---

## S2-08 · Dockerfile, production compose, VPS and CD to staging

**Points:** 5 · **Owner:** Person C · **Branch:** `feature/S2-08-staging-cd` · **Depends on:** S0-03, S0-05 (green CI)

### Goal

Every merge into `develop` builds a Docker image, pushes it to GitHub's container registry, and deploys it to `https://staging-polaris-cse.duckdns.org` with migrations and a smoke test, and nobody types a command. After this story the team reviews every sprint on staging instead of on one person's laptop (*Test in the Wild*, Getting Real Ch. 6).

The YAML and Docker files are already written in the spec. This story is the **runbook**: the exact order of clicks and commands to make them work. It doesn't repeat them:

| File | Where it is in the spec |
|---|---|
| `Dockerfile` | §10.5 |
| `compose.prod.yml` | §10.5 |
| `.github/workflows/cd.yml` | §9.10 |
| `/srv/edge/Caddyfile` | §9.10 |
| Server checklist (short form) | §10.6 |

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `Dockerfile` | create | Copy from §10.5 |
| `.dockerignore` | create | Keeps secrets and junk out of the image (below) |
| `compose.prod.yml` | create | Copy from §10.5 |
| `.github/workflows/cd.yml` | create | Copy from §9.10 |
| `deploy/edge/compose.yml` | create | The Caddy stack (below). Kept in the repo so the server setup is reproducible |
| `deploy/edge/Caddyfile` | create | Copy from §9.10 |
| `deploy/env.staging.example` | create | Every variable the server's `.env` needs, with dummy values |
| `docs/process/deployment.md` | create | Server IP, hostnames, who has SSH access, how to roll back. **No secrets** |

### Steps

**1. Add `.dockerignore`.**

`COPY . .` in the Dockerfile copies the whole build context into the image. Without this file, your local `.env` (with your Anthropic key), your `.venv` and your `media/` uploads would end up inside a public image.

```gitignore
# .dockerignore
.git
.github
.venv
.env
.env.*
!.env.example
media/
staticfiles/
**/__pycache__
**/*.pyc
.pytest_cache
.ruff_cache
.coverage
htmlcov/
docs/
seed/grades/
node_modules/
*.sqlite3
.DS_Store
.idea/
.vscode/
```

`seed/syllabi/` stays in the image because the demo uses it. `seed/grades/` is excluded because it holds the deliberately messy test files, which only tests need.

**2. Build and run the image locally before touching a server.**

Most deploy failures are image failures, and they're much faster to debug on your laptop.

```bash
docker build -t polaris:local .
docker run --rm -e DJANGO_SETTINGS_MODULE=config.settings.prod \
  -e SECRET_KEY=x -e DATABASE_URL=sqlite:////tmp/x.db -e REDIS_URL=redis://localhost:6379/0 \
  -e ALLOWED_HOSTS=localhost -e CSRF_TRUSTED_ORIGINS=https://localhost -e EMAIL_URL=consolemail:// \
  polaris:local python manage.py check --deploy --fail-level WARNING
```

**Expected:** `System check identified no issues (1 silenced).` The one silenced check is `security.W021`; see §10.3.

If `collectstatic` fails during the build, the cause is almost always a template referencing a static file that doesn't exist. WhiteNoise's manifest storage refuses missing files. Fix the path; don't switch the storage.

**3. Get a server.**

You need Ubuntu 24.04 LTS, 2 vCPU, 2–4 GB RAM and about 40 GB of disk. Two options, both fine:

| Option | Cost | Notes |
|---|---|---|
| Hetzner Cloud CX22 (or the current equivalent) | about €4–5 per month | EU data centres, so low latency from Istanbul. Needs a card |
| DigitalOcean Basic Droplet, 2 GB | about $12 per month, **free with the GitHub Student Developer Pack credit** | Check the Pack's current offer at education.github.com/pack. The credit lasts well beyond December |

When creating the server:

1. **Add your SSH public key.** If you don't have one, run `ssh-keygen -t ed25519 -C "you@acibadem.edu.tr"`. The public key is `~/.ssh/id_ed25519.pub`.
2. Pick the region closest to Istanbul (Frankfurt, Nuremberg, Helsinki or Amsterdam).
3. Name the server `polaris`.

Write the IPv4 address in `docs/process/deployment.md`.

**4. Point two hostnames at it with DuckDNS (free).**

1. Go to duckdns.org, log in with GitHub, and create two subdomains: `polaris-cse` and `staging-polaris-cse`. If those are taken, pick other names and use them everywhere below, including the Caddyfile and the GitHub `SITE_HOST` variables.
2. Set both to the server's IPv4 address and click **update ip**.
3. Check from your laptop: `dig +short staging-polaris-cse.duckdns.org` should print the IP. DNS can take a few minutes.

The IP of a cloud server never changes, so you don't need the DuckDNS update cron that home users run.

**5. First login and hardening (as root, about 10 minutes).**

```bash
ssh root@<ip>

apt update && apt -y upgrade
timedatectl set-timezone Europe/Istanbul          # cron backups at 03:00 Istanbul time

# a normal user that deploys; root login is switched off below
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys     # your laptop key
chown -R deploy:deploy /home/deploy/.ssh && chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
passwd deploy                                     # a password for sudo only; SSH stays key-only

# firewall: SSH, HTTP, HTTPS (and HTTP/3 over UDP for Caddy)
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp
ufw --force enable

# swap: a 2 GB box can run out of memory during migrations + WeasyPrint
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# security updates install themselves
apt -y install unattended-upgrades && dpkg-reconfigure -f noninteractive unattended-upgrades
```

**Before** you disable root login, open a **second terminal** and check that `ssh deploy@<ip>` works and that `sudo -v` accepts the password. Then:

```bash
sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin no/; s/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl reload ssh
```

From now on, always log in as `deploy`.

> **Docker and UFW.** Docker publishes container ports by writing its own iptables rules, and those **bypass UFW**. A `ports: ["5432:5432"]` on the database would expose Postgres to the internet even with UFW on. That's why `compose.prod.yml` publishes no ports at all; only the Caddy container publishes 80 and 443. Never add `ports:` to `db`, `redis`, `web` or `worker`.

**6. Install Docker Engine.**

These are the official apt-repository instructions for Ubuntu. If they've changed, follow docs.docker.com → Install → Ubuntu instead.

```bash
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker deploy
exit                                 # log out and back in so the group applies
ssh deploy@<ip>
docker run --rm hello-world          # must work without sudo
```

**7. The edge stack (Caddy, HTTPS for both sites).**

```bash
sudo mkdir -p /srv/edge /srv/polaris/staging /srv/polaris/production /srv/backups
sudo chown -R deploy:deploy /srv/edge /srv/polaris /srv/backups
docker network create edge
```

Copy `deploy/edge/compose.yml` and `deploy/edge/Caddyfile` from the repo to `/srv/edge/`, from your laptop:

```bash
scp deploy/edge/compose.yml deploy/edge/Caddyfile deploy@<ip>:/srv/edge/
```

```yaml
# deploy/edge/compose.yml
services:
  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data          # certificates: losing this volume means re-issuing them
      - caddy_config:/config
    networks: [edge]

volumes:
  caddy_data:
  caddy_config:

networks:
  edge:
    external: true
```

```bash
cd /srv/edge && docker compose up -d && docker compose logs -f caddy
```

**Expected:** after a few seconds, log lines saying `certificate obtained successfully` for both hostnames. Visiting the staging URL now gives **502 Bad Gateway**. That's correct: Caddy works, but `staging-web` doesn't exist yet.

If certificates fail, either DNS doesn't point at the server yet (step 4) or port 80 is blocked (step 5). Let's Encrypt has rate limits, so don't restart Caddy in a loop; fix the cause, then restart it once.

**8. The staging folder and its `.env`.**

```bash
scp compose.prod.yml deploy@<ip>:/srv/polaris/staging/
```

On the server, generate the secrets:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # SECRET_KEY
openssl rand -hex 24                                             # POSTGRES_PASSWORD (hex: safe inside a URL)
```

Create `/srv/polaris/staging/.env` with `nano`, then lock it down:

```bash
chmod 600 /srv/polaris/staging/.env
```

```bash
# /srv/polaris/staging/.env   (deploy/env.staging.example in the repo has the same keys, dummy values)
STACK=staging
COMPOSE_PROJECT_NAME=polaris-staging
IMAGE=ghcr.io/onurhaniffa/polaris
IMAGE_TAG=develop

SECRET_KEY=<token_urlsafe output>
DEBUG=False
ALLOWED_HOSTS=staging-polaris-cse.duckdns.org
CSRF_TRUSTED_ORIGINS=https://staging-polaris-cse.duckdns.org

POSTGRES_USER=polaris
POSTGRES_PASSWORD=<hex output>
POSTGRES_DB=polaris
DATABASE_URL=postgres://polaris:<hex output>@db:5432/polaris
REDIS_URL=redis://redis:6379/0

ANTHROPIC_API_KEY=<the team's key; staging may share it with production>
ANTHROPIC_MODEL=claude-opus-5-5
EMAIL_URL=consolemail://
DEFAULT_FROM_EMAIL=POlaris staging <noreply@staging-polaris-cse.duckdns.org>
```

Notes:

- **`IMAGE` must be lowercase.** GHCR rejects capital letters, and the CD workflow lowercases `github.repository` for the same reason (`${GITHUB_REPOSITORY,,}`). The first deploy overwrites `IMAGE` and `IMAGE_TAG` anyway.
- **Hostnames inside `DATABASE_URL` and `REDIS_URL` are `db` and `redis`**: the service names on the stack's private network. Never `localhost`.
- **`EMAIL_URL=consolemail://`** means password-reset emails appear in `docker compose logs web` on staging. Production gets real SMTP in S3-06.

**9. A deploy key for GitHub Actions.**

Use a separate key made only for CI. If it ever leaks, you delete one line on the server and nothing else is affected.

On your **laptop**:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/polaris_deploy -N "" -C "github-actions-deploy"
ssh-copy-id -i ~/.ssh/polaris_deploy.pub deploy@<ip>
ssh -i ~/.ssh/polaris_deploy deploy@<ip> 'echo ok'     # must print ok without a prompt
cat ~/.ssh/polaris_deploy                               # the PRIVATE key; goes into GitHub, nowhere else
```

**10. A token so the server can pull the image.**

GitHub's container registry accepts only **classic** personal access tokens. Fine-grained tokens don't work with GitHub Packages yet.

1. Go to GitHub → Settings → Developer settings → Personal access tokens → **Tokens (classic)** → Generate.
2. Name it `polaris-ghcr-read`. Tick **only** `read:packages`. Set an expiry after the demo (31 Jan 2027).
3. This is the `GHCR_READ_TOKEN` secret. `GHCR_USER` is the GitHub username of whoever made the token.

Alternatively, once the first image has been pushed, you can make the package public. Go to the repo → Packages → `polaris` → Package settings → Change visibility → **Public**. Then the server pulls without logging in. Keep the token setup anyway, because `cd.yml` runs `docker login`.

**11. GitHub environments, variables and secrets.**

Repo → **Settings → Environments**:

| Environment | Deployment branches | Variables | Secrets |
|---|---|---|---|
| `staging` | Selected branches: `develop` | `STACK=staging`, `SITE_HOST=staging-polaris-cse.duckdns.org` | `SSH_HOST` (the IP), `SSH_USER=deploy`, `SSH_KEY` (whole private key file, including the `-----BEGIN` and `END` lines), `GHCR_USER`, `GHCR_READ_TOKEN` |
| `production` | Selected branches: `main` | `STACK=production`, `SITE_HOST=polaris-cse.duckdns.org` | Same five secrets (S3-06 adds the required reviewer) |

The "deployment branches" rule matters: it stops a feature branch from ever deploying, even if someone edits `cd.yml` in a PR.

**12. Merge, watch, verify.**

Open the PR with the files from this story. When CI is green and it's approved, squash-merge into `develop`, then go to the **Actions** tab:

1. `CD` starts and calls `CI` first (lint, test).
2. `build` pushes `ghcr.io/onurhaniffa/polaris:<sha>` and `:develop`.
3. `deploy` runs over SSH: pull, migrate, `up -d`.
4. `Smoke test` curls `/healthz` until it returns 200.

Then, on the server, load the demo data and create your own admin account:

```bash
cd /srv/polaris/staging
docker compose -f compose.prod.yml ps                       # web, worker, db, redis: all "running (healthy)"
docker compose -f compose.prod.yml exec web python manage.py seed_demo --allow-production
docker compose -f compose.prod.yml exec web python manage.py createsuperuser
docker compose -f compose.prod.yml exec web python manage.py check --deploy --fail-level WARNING
```

`--allow-production` is required because staging runs with `DEBUG=False`, and `seed_demo` refuses to run there otherwise (Appendix B). On staging that's what we want: demo personas with known passwords. **Never** pass it on production after the final data is in.

**13. Write it down.**

In `docs/process/deployment.md`, record:

- the IP and both hostnames;
- who has SSH access (each person's laptop key: add teammates with `ssh-copy-id`);
- where the `.env` files live;
- how to see logs: `docker compose -f compose.prod.yml logs -f web worker`;
- the rollback procedure from §9.10.

**Never** write passwords or keys in this file. It's in a public repo.

### Keeping the server in sync with the repo

`cd.yml` deploys new **images**. It does **not** copy `compose.prod.yml` or the Caddyfile. When a PR changes either file, the person merging it copies the file to the server by hand, in the same hour:

```bash
scp compose.prod.yml deploy@<ip>:/srv/polaris/staging/
ssh deploy@<ip> 'cd /srv/polaris/staging && docker compose -f compose.prod.yml up -d'
```

Put this in the PR description so it isn't forgotten. T2.2 is the first story that will need it, because it adds the Celery beat service.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Caddy 502 after a deploy | `web` not on the `edge` network, or its alias isn't `staging-web` | `docker network inspect edge` must list `polaris-staging-web-1` with alias `staging-web`. Check `STACK=staging` in `.env` |
| `Bad Request (400)` | `DisallowedHost` | `ALLOWED_HOSTS` must be the exact hostname, without `https://` |
| `CSRF verification failed` on login | Missing or wrong `CSRF_TRUSTED_ORIGINS` | It needs the scheme: `https://staging-polaris-cse.duckdns.org` |
| Redirect loop | Missing `SECURE_PROXY_SSL_HEADER`, or Caddy not sending `X-Forwarded-Proto` | `prod.py` sets the header (§10.3). Caddy sends it by default. Don't put another proxy in front |
| `unauthorized` on `docker compose pull` | The token isn't classic, lacks `read:packages`, or has expired | Make a new classic token (step 10) |
| `permission denied … docker.sock` in the deploy job | `deploy` isn't in the `docker` group | `sudo usermod -aG docker deploy`, then log out and back in |
| Deploy hangs at `migrate` | A migration waits for a lock held by a long query, or the DB isn't healthy | `docker compose -f compose.prod.yml logs db`. Never cancel a migration half-way without reading the log |
| Smoke test fails but the site works in a browser | `/healthz` reports `cache: down` because Redis isn't healthy yet | `docker compose ps`. The smoke test retries for 2 minutes; if Redis keeps failing, look at its logs |
| Worker container keeps restarting | Celery can't import the app because an env var is missing | `docker compose -f compose.prod.yml logs worker`. The first error line names the missing variable |

### Tests

There's no pytest for infrastructure. Evidence comes from runs and checks:

1. **CI proves the image builds.** The `docker-build` job in `ci.yml` (§9.9) builds the image on every PR without pushing it.
2. **The smoke test in `cd.yml` is the deployment test.** A deploy that doesn't answer `/healthz` with 200 within 2 minutes marks the run red.
3. **Prove the check catches failure, once, on purpose.** Run `docker compose -f compose.prod.yml stop redis` on staging, then trigger the CD workflow with **Run workflow** (`workflow_dispatch`, `develop`). The smoke test must fail red. Start Redis again and re-run it: green. Screenshot both runs into `docs/process/sprint-02/runs.md`. Report Section 5 asks for "a summary of particular runs", and a failed run you caused, explained and fixed is the best one you can show.

### Check it works

1. `https://staging-polaris-cse.duckdns.org/healthz` → `{"db": "ok", "cache": "ok"}`, with a valid padlock in the browser.
2. Log in as Dr. Can Aydın on staging → set up a course → type grades. This is the Sprint 2 checkpoint (Part 11).
3. Merge any small PR into `develop`. Within about 5 minutes the change is live on staging, and nobody touched the server.
4. `ssh root@<ip>` is refused, and so is `ssh deploy@<ip>` from a machine whose key isn't authorised.
5. `nmap -Pn -p 5432,6379,8000 <ip>` from your laptop shows all three ports **filtered** or **closed**.

### Done when

- [ ] A merge into `develop` deploys staging automatically, with migrate and a smoke test.
- [ ] HTTPS is valid on the staging hostname.
- [ ] `check --deploy --fail-level WARNING` passes inside the running container.
- [ ] One deliberately failed CD run and its fix are recorded in `docs/process/sprint-02/runs.md`.
- [ ] `docs/process/deployment.md` exists, and the server holds both stack folders and the edge stack.
- [ ] Root SSH and password SSH are disabled; Postgres and Redis aren't reachable from outside.

### Commits and PR

```
Add Dockerfile, dockerignore and production compose file (#S2-08)
Add CD workflow that deploys develop to staging (#S2-08)
Add Caddy edge stack and staging env example (#S2-08)
Document the staging server and rollback steps (#S2-08)
```

PR title: **Deploy develop to staging automatically (S2-08)**.

---

# Sprint 3 — Baseline complete (Mon 2 – Sun 8 Nov)

**Goal:** every Baseline feature works end to end on staging **and production**. By Sunday 8 November the full loop runs on the production URL:

1. The head creates an offering.
2. The instructor sets it up, enters grades and **publishes**.
3. The student sees their PO profile.
4. The head sees the department overview.

We record that loop as a 3-minute video. It's the fallback demo if anything breaks later, and it goes into both checkpoint presentations.

| ID | Story | Pts | Owner |
|---|---|---|---|
| S3-01 | Publish / unpublish service, confirmation modal, audit | 5 | B |
| S3-02 | Student PO profile v1 (table, bar chart, contributors drawer) | 5 | C |
| S3-03 | Instructor course results | 3 | A |
| S3-04 | Department overview v1 | 3 | C |
| S3-05 | Enrollment CSV import with dry run | 5 | A |
| S3-06 | Production stack, first release `v0.3.0`, nightly backup cron | 2 | C |
| S3-07 | `seed_demo` v2: 3 terms, 12 courses, 120 students, realistic distributions (Appendix B) | 2 | B |
| S3-08 | Bulk upload spike: parse CSV/XLSX, Turkish decimals and encodings, column matching | 3 | B |

**Merge order**

| When | What | Why this order |
|---|---|---|
| Mon–Tue | **S3-06** server side (production folder, `.env`, backups) | Infrastructure work needs no code from anyone. Doing it first leaves the release PR on Sunday as the only production step |
| Mon–Wed | **S3-01** publish | S3-02, S3-03 and S3-04 show *published* numbers. They can be built against seed data (which writes `published_score` directly), but their tests and demos need the real publish button |
| Mon–Thu | **S3-05** enrollment import | Independent of everything else this sprint |
| By Wed | **S3-07** seed v2 | The three report pages need a believable department to look right and to test query counts |
| Wed–Sat | **S3-02**, **S3-03**, **S3-04** | Each needs S3-01's semantics and S3-07's data |
| Any time | **S3-08** spike | Throwaway branch `spike/S3-08-upload`. The deliverable is `docs/process/spikes/S3-08-grade-files.md`, not merged code |
| **Sun morning** | Release PR `develop` → `main`, tag `v0.3.0` (S3-06) | Production gets exactly what was reviewed on staging all week |

**What must work by Sunday:** the baseline loop above, on `https://polaris-cse.duckdns.org`. The first nightly backup file exists in `/srv/backups/`. The permission matrix covers every URL. CI is green on `main`.

---

## S3-01 · Publish and unpublish grades, with confirmation and audit

**Points:** 5 · **Owner:** Person B · **Branch:** `feature/S3-01-publish` · **Depends on:** S2-06

### Goal

Grades stay drafts until the instructor clicks **Publish** on an assessment's column. Publishing copies `score → published_score` for every grade of that assessment in **one transaction**: students see all of a midterm or none of it, never half. Later edits are drafts again ("3 unpublished changes") until the next publish. **Unpublish** exists for mistakes (the wrong file was uploaded), needs a written reason, and is audited.

This delivers Part 6 **B7 AC 1–4**. It's also the transaction-and-locking example for the CSE 321 report (§5.6 table, first row).

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/grading/services.py` | modify | `PublishResult`, `publish_assessment`, `unpublish_assessment` |
| `apps/grading/selectors.py` | modify | `PublishPreview`, `publish_preview` |
| `apps/grading/forms.py` | create | `PublishForm`, `UnpublishForm` |
| `apps/grading/views.py` | modify | `publish`, `unpublish` |
| `apps/grading/urls.py` | modify | `grading:publish`, `grading:unpublish` |
| `apps/grading/templates/grading/sheet.html` | modify | Publish / Unpublish buttons in `col_head`, the modal shell |
| `apps/grading/templates/grading/publish_modal.html` | create | Confirmation body |
| `apps/grading/templates/grading/unpublish_modal.html` | create | Reason form |
| `apps/grading/tests/test_publish.py` | create | Service, atomicity, locking, visibility |
| `apps/grading/tests/test_publish_views.py` | create | Modal, POST, messages |
| `apps/accounts/tests/test_permission_matrix.py` | modify | Two new URLs |

### Steps

**1. The preview: what the modal says before anyone clicks.**

The confirmation must say exactly what will happen: "Publish Midterm I to 84 students? 3 students have no grade (they will be skipped, not counted as zero)". We count only **enrolled** students. A dropped student's grade is published along with the others (harmless), but never counted or shown.

```python
# apps/grading/selectors.py  (add)

@dataclass(frozen=True)
class PublishPreview:
    assessment: Assessment
    enrolled: int        # students currently enrolled
    graded: int          # have a numeric score
    excused: int         # marked EX
    missing: int         # no value at all: skipped, NOT zero (policy P5)
    changes: int         # grades that differ from what students see now

    @property
    def is_first_publish(self) -> bool:
        return self.assessment.published_at is None

    @property
    def can_publish(self) -> bool:
        return self.changes > 0


def publish_preview(assessment) -> PublishPreview:
    """Counts for the publish modal and the publish service. Two queries."""
    enrolled = Enrollment.objects.filter(
        offering_id=assessment.offering_id, status=Enrollment.Status.ENROLLED,
    ).count()
    grades = list(
        Grade.objects.filter(assessment=assessment, enrollment__status=Enrollment.Status.ENROLLED)
        .only("score", "is_excused", "published_score", "published_is_excused")
    )
    graded = sum(1 for g in grades if g.score is not None and not g.is_excused)
    excused = sum(1 for g in grades if g.is_excused)
    return PublishPreview(
        assessment=assessment,
        enrolled=enrolled,
        graded=graded,
        excused=excused,
        missing=enrolled - graded - excused,
        changes=sum(1 for g in grades if g.has_unpublished_change),
    )
```

**2. The publish service.**

Here is what happens, in order, inside one `transaction.atomic()`:

1. **Lock the assessment row** with `SELECT … FOR UPDATE`. If the instructor double-clicks, or the instructor and the head publish at the same moment, the second transaction waits until the first commits. It then sees `changes == 0` and stops with "Nothing new to publish". Without the lock, both could interleave their UPDATEs.
2. **Lock the term row and check the term is open** (`_lock_open_term`, from S2-06). Publishing is a write; closed terms are read-only.
3. **Re-count inside the lock.** The modal's numbers may be stale: a teammate may have typed a grade after the modal opened. The view sends the count the user saw (`expected_changes`). If it differs, we refuse and ask them to look again. Publishing numbers the instructor didn't see breaks the promise of the confirmation.
4. **One `UPDATE` statement** copies draft to published for every grade of the assessment: `published_score = score`, `published_is_excused = is_excused`, `published_at = now()`. `F("score")` makes the copy happen inside PostgreSQL in a single statement. Nothing goes through Python per row.
5. **Stamp the assessment** with `published_at` and `published_by`.
6. **Write one audit event** with the counts. The individual grade values were already audited when they were typed (S2-06), so the publish event records *that* they became visible, *when*, and *how many*.

If anything raises at step 4, 5 or 6, PostgreSQL rolls the whole transaction back: zero grades become visible. The test in step 8 proves this by making the audit write in step 6 crash.

**Why `select_for_update(of=("self",))`?** We also `select_related("offering")` so we don't need a second query for the offering. In PostgreSQL, `FOR UPDATE` on a join locks the rows of **every** joined table, which would lock the offering row too. That would block anything else touching the offering (for example a mapping save, which takes `FOR UPDATE` on the offering, §5.6) for no reason. `of=("self",)` limits the lock to the assessment row.

```python
# apps/grading/services.py  (add; extend the imports at the top of the file)
from dataclasses import dataclass

from django.db.models import F
from django.utils import timezone

from apps.outcomes.models import Assessment

from .selectors import publish_preview


@dataclass(frozen=True)
class PublishResult:
    published: int          # students who now see a numeric score
    excused: int            # students who now see "excused"
    skipped_missing: int    # enrolled students with no grade: skipped, not zero (P5)
    changed: int            # grades whose visible value changed with this publish


def _iso(value):
    return value.isoformat() if value is not None else None


def publish_assessment(user, assessment, *, expected_changes: int | None = None) -> PublishResult:
    """Make the current draft grades of one assessment visible to students, all at once (B7).

    expected_changes: the number of changes the confirmation modal showed. If grades changed
    after the modal opened, we refuse instead of publishing numbers the instructor didn't see.
    """
    with transaction.atomic():
        locked = (Assessment.objects.select_for_update(of=("self",))
                  .select_related("offering")
                  .get(pk=assessment.pk))
        offering = locked.offering
        _lock_open_term(offering)

        preview = publish_preview(locked)
        if preview.graded + preview.excused == 0:
            raise ValidationError(f"{locked.name} has no grades to publish yet.", code="empty")
        if preview.changes == 0:
            raise ValidationError(f"Nothing new to publish for {locked.name}.", code="no_changes")
        if expected_changes is not None and expected_changes != preview.changes:
            raise ValidationError(
                f"Grades for {locked.name} changed while the confirmation was open "
                f"({expected_changes} → {preview.changes} changes). Please review and publish again.",
                code="stale",
            )

        now = timezone.now()
        Grade.objects.filter(assessment=locked).update(
            published_score=F("score"),
            published_is_excused=F("is_excused"),
            published_at=now,
        )
        before = {"published_at": _iso(locked.published_at),
                  "published_by": locked.published_by_id}
        locked.published_at = now
        locked.published_by = user
        locked.save(update_fields=["published_at", "published_by"])

        result = PublishResult(
            published=preview.graded,
            excused=preview.excused,
            skipped_missing=preview.missing,
            changed=preview.changes,
        )
        audit.record(user, "assessment.publish", locked,
                     before=before,
                     after={"published_at": now.isoformat(), "published_by": user.pk,
                            "published": result.published, "excused": result.excused,
                            "skipped_missing": result.skipped_missing, "changed": result.changed},
                     offering=offering)
        # T2.3 adds: transaction.on_commit(lambda: refresh_scores.delay(offering.id))
    assessment.published_at = locked.published_at       # keep the caller's object in sync
    assessment.published_by = locked.published_by
    return result
```

Grade-level `published_at` is set on **every** grade of the assessment, including unchanged ones. It means "the last time this grade's visible value was confirmed", which is what the history view (T1.4) shows.

The import line `from .selectors import publish_preview` is safe: `selectors.py` never imports `services.py`, so there's no circular import. Keep it that way. Selectors read and services write.

**3. Unpublish.**

Unpublishing hides **every** grade of the assessment again: `published_score = NULL`, `published_is_excused = False`, `published_at = NULL`. Draft values stay untouched, so the instructor can fix the mistake and publish again.

A reason of at least 5 characters is required. It goes into the audit event, because "why did my midterm grade disappear yesterday?" is exactly the question the history view must answer.

```python
# apps/grading/services.py  (add)

def unpublish_assessment(user, assessment, *, reason: str) -> int:
    """Hide all published grades of one assessment again (rare; e.g. the wrong file was uploaded).
    Returns how many grades were hidden."""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError("Say briefly why you are unpublishing (at least 5 characters).",
                              code="reason")
    with transaction.atomic():
        locked = (Assessment.objects.select_for_update(of=("self",))
                  .select_related("offering")
                  .get(pk=assessment.pk))
        offering = locked.offering
        _lock_open_term(offering)
        if locked.published_at is None:
            raise ValidationError(f"{locked.name} is not published.", code="not_published")

        hidden = (Grade.objects.filter(assessment=locked)
                  .exclude(published_at=None)
                  .update(published_score=None, published_is_excused=False, published_at=None))
        before = {"published_at": _iso(locked.published_at),
                  "published_by": locked.published_by_id}
        locked.published_at = None
        locked.published_by = None
        locked.save(update_fields=["published_at", "published_by"])
        audit.record(user, "assessment.unpublish", locked,
                     before=before,
                     after={"published_at": None, "hidden": hidden, "reason": reason},
                     offering=offering)
    assessment.published_at = None
    assessment.published_by = None
    return hidden
```

**4. Forms.**

`expected_changes` is a hidden field holding the count shown in the modal. The reason field has `min_length=5` so the browser and the form agree with the service. The service checks again anyway, because services are callable from places without a form (the admin, a shell, a test).

```python
# apps/grading/forms.py
from django import forms


class PublishForm(forms.Form):
    expected_changes = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class UnpublishForm(forms.Form):
    reason = forms.CharField(
        min_length=5, max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Students will no longer see these grades. This reason is kept in the history.",
    )
```

T1.1 adds `GradeUploadForm` and `ColumnMappingForm` to this file.

**5. Views.**

Both views follow one pattern:

- **GET** returns the modal's content (a partial). HTMX loads it into the modal shell.
- **POST** comes from a form inside the modal, sent with `hx-post`. If the form is invalid, the modal content is re-rendered with errors and the modal stays open. If it succeeds, the server answers with django-htmx's `HttpResponseClientRedirect`. That sets the `HX-Redirect` header, and HTMX reloads the grade sheet, where the success message from `messages` appears as a toast. Without HTMX (a plain form post) we fall back to a normal redirect.

`perms_for.can_publish` is checked in addition to the decorator. Today it equals `can_edit`. In T2.8 a TA can edit drafts but must not publish, and this one line already enforces that.

```python
# apps/grading/views.py  (add; extend the imports)
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django_htmx.http import HttpResponseClientRedirect

from .forms import PublishForm, UnpublishForm


def _back_to_sheet(request, offering):
    url = reverse("grading:sheet", kwargs={"offering_id": offering.id})
    return HttpResponseClientRedirect(url) if request.htmx else redirect(url)


def _publish_message(assessment, result) -> str:
    parts = [f"{assessment.name} published to {result.published + result.excused} students."]
    if result.excused:
        parts.append(f"{result.excused} excused.")
    if result.skipped_missing:
        parts.append(f"{result.skipped_missing} had no grade and were skipped (not counted as zero).")
    return " ".join(parts)


@login_required
@require_http_methods(["GET", "POST"])
@require_offering_access(edit=True)
def publish(request, *, offering, perms_for, assessment_id, **_):
    if not perms_for.can_publish:
        raise Http404
    assessment = get_object_or_404(Assessment, pk=assessment_id, offering=offering)

    if request.method == "POST":
        form = PublishForm(request.POST)
        if form.is_valid():
            try:
                result = services.publish_assessment(
                    request.user, assessment,
                    expected_changes=form.cleaned_data["expected_changes"],
                )
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
            else:
                messages.success(request, _publish_message(assessment, result))
        else:
            messages.error(request, "The publish form was incomplete. Please try again.")
        return _back_to_sheet(request, offering)

    preview = selectors.publish_preview(assessment)
    return render(request, "grading/publish_modal.html", {
        "offering": offering,
        "preview": preview,
        "form": PublishForm(initial={"expected_changes": preview.changes}),
    })


@login_required
@require_http_methods(["GET", "POST"])
@require_offering_access(edit=True)
def unpublish(request, *, offering, perms_for, assessment_id, **_):
    if not perms_for.can_publish:
        raise Http404
    assessment = get_object_or_404(Assessment, pk=assessment_id, offering=offering)
    form = UnpublishForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            hidden = services.unpublish_assessment(request.user, assessment,
                                                   reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.warning(request, f"{assessment.name} unpublished. "
                                      f"{hidden} grades are hidden from students again.")
            return _back_to_sheet(request, offering)

    return render(request, "grading/unpublish_modal.html", {
        "offering": offering, "assessment": assessment, "form": form,
    })
```

Publish errors become a toast on the sheet rather than a red modal: the likely errors ("nothing new", "changed while open") are about the sheet's state, and the sheet is what the user needs to look at. Unpublish errors stay in the modal, because the fix is in the modal (write a longer reason).

```python
# apps/grading/urls.py  (add to urlpatterns)
    path("offerings/<int:offering_id>/grades/<int:assessment_id>/publish/",
         views.publish, name="publish"),
    path("offerings/<int:offering_id>/grades/<int:assessment_id>/unpublish/",
         views.unpublish, name="unpublish"),
```

**6. Templates.**

The buttons live inside the `col_status` partial, not `col_head`. When a cell save refreshes the badge out-of-band (S2-06), the button refreshes with it. For example, "Publish changes" appears the moment the first draft differs from the published value.

Replace the `col_status` partial in `sheet.html` with:

```django
{% partialdef col_status %}
<span id="col-status-{{ column.assessment.id }}" class="d-block small"
      {% if oob %}hx-swap-oob="true"{% endif %}>
  {% if column.is_published %}
    <span class="badge text-bg-success">Published</span>
  {% else %}
    <span class="badge text-bg-secondary">Draft</span>
  {% endif %}
  {% if column.unpublished %}
    <span class="badge text-bg-warning" title="Changes students can't see yet">
      {{ column.unpublished }} unpublished
    </span>
  {% endif %}
  {% if perms_for.can_publish %}
    <span class="d-block mt-1">
      {% if column.unpublished %}
        <button type="button" class="btn btn-sm btn-primary"
                data-bs-toggle="modal" data-bs-target="#sheet-modal"
                hx-get="{% url 'grading:publish' offering_id=offering.id assessment_id=column.assessment.id %}"
                hx-target="#sheet-modal-content">
          {% if column.is_published %}Publish changes{% else %}Publish{% endif %}
        </button>
      {% endif %}
      {% if column.is_published %}
        <button type="button" class="btn btn-sm btn-link text-danger p-0 ms-1"
                data-bs-toggle="modal" data-bs-target="#sheet-modal"
                hx-get="{% url 'grading:unpublish' offering_id=offering.id assessment_id=column.assessment.id %}"
                hx-target="#sheet-modal-content">Unpublish</button>
      {% endif %}
    </span>
  {% endif %}
</span>
{% endpartialdef %}
```

At the end of `{% block content %}` in `sheet.html`, add the modal shell. Bootstrap opens it on click (`data-bs-toggle`), while HTMX fills `#sheet-modal-content` from the server. The "Loading…" text is what shows for the fraction of a second in between.

```django
<div class="modal fade" id="sheet-modal" tabindex="-1" aria-labelledby="sheet-modal-title" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content" id="sheet-modal-content">
      <div class="modal-body text-body-secondary">Loading…</div>
    </div>
  </div>
</div>
```

```django
{# apps/grading/templates/grading/publish_modal.html #}
<div class="modal-header">
  <h2 class="modal-title h5" id="sheet-modal-title">
    {% if preview.is_first_publish %}Publish {{ preview.assessment.name }}?{% else %}Publish changes to {{ preview.assessment.name }}?{% endif %}
  </h2>
  <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
</div>
<div class="modal-body">
  {% if preview.can_publish %}
    <p>
      Students will see these grades immediately, all at once.
      {% if not preview.is_first_publish %}{{ preview.changes }} grade{{ preview.changes|pluralize }} changed since the last publish.{% endif %}
    </p>
    <ul class="list-unstyled mb-0">
      <li>✓ <strong>{{ preview.graded }}</strong> of {{ preview.enrolled }} students have a score</li>
      {% if preview.excused %}<li>◌ <strong>{{ preview.excused }}</strong> excused</li>{% endif %}
      {% if preview.missing %}
        <li class="text-warning-emphasis">⚠ <strong>{{ preview.missing }}</strong> student{{ preview.missing|pluralize }} have no grade.
          They will be <strong>skipped, not counted as zero</strong>. Enter 0 if you mean zero.</li>
      {% endif %}
    </ul>
  {% else %}
    <p class="mb-0">Nothing new to publish: students already see every grade in this column.</p>
  {% endif %}
</div>
<div class="modal-footer">
  <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
  {% if preview.can_publish %}
    <form hx-post="{% url 'grading:publish' offering_id=offering.id assessment_id=preview.assessment.id %}"
          hx-disabled-elt="find button">
      {{ form.expected_changes }}
      <button type="submit" class="btn btn-primary">
        Publish to {{ preview.graded|add:preview.excused }} students
      </button>
    </form>
  {% endif %}
</div>
```

`hx-disabled-elt="find button"` disables the submit button while the request is in flight. That's the first defence against a double-click. The row lock is the real one.

```django
{# apps/grading/templates/grading/unpublish_modal.html #}
<form hx-post="{% url 'grading:unpublish' offering_id=offering.id assessment_id=assessment.id %}"
      hx-target="#sheet-modal-content" hx-disabled-elt="find button[type=submit]">
  <div class="modal-header">
    <h2 class="modal-title h5" id="sheet-modal-title">Unpublish {{ assessment.name }}?</h2>
    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
  </div>
  <div class="modal-body">
    <p>Students will stop seeing every grade in this column, and their PO scores will be recalculated
       without it. Your draft values are kept so you can fix them and publish again.</p>
    {% if form.non_field_errors %}<div class="alert alert-danger">{{ form.non_field_errors|join:" " }}</div>{% endif %}
    <label for="{{ form.reason.id_for_label }}" class="form-label">Why? (kept in the history)</label>
    <textarea name="{{ form.reason.html_name }}" id="{{ form.reason.id_for_label }}" rows="3"
              class="form-control{% if form.reason.errors %} is-invalid{% endif %}"
              minlength="5" maxlength="500" required>{{ form.reason.value|default_if_none:"" }}</textarea>
    {% for error in form.reason.errors %}<div class="invalid-feedback">{{ error }}</div>{% endfor %}
  </div>
  <div class="modal-footer">
    <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
    <button type="submit" class="btn btn-danger">Unpublish</button>
  </div>
</form>
```

**7. The permission matrix.** Each URL already has a row in `ROUTES` (`apps/accounts/tests/routes.py`, written in S2-02). A row switches on by itself once its URL resolves, so there is nothing to add; run the matrix test and check it gives these results:

| URL name | kwargs | Method | anonymous | student | instructor (other) | instructor (own) | head | admin |
|---|---|---|---|---|---|---|---|---|
| `grading:publish` | `offering_id`, `assessment_id` | GET | 302 | 404 | 404 | 200 | 200 | 200 |
| `grading:unpublish` | `offering_id`, `assessment_id` | GET | 302 | 404 | 404 | 200 | 200 | 200 |

The matrix only checks GET, which is enough because the decorator runs before the method matters. The POST behaviour is covered by the view tests below.

**8. Explain it in the report.**

This story is the cleanest example of transactions for CSE 321 Section 4 ("operations in your system that require transaction support"). Copy this summary into `docs/reports/cse321-notes.md` now, while it's fresh:

> *Publishing an assessment runs in one transaction at PostgreSQL's default READ COMMITTED level. It first locks the assessment row (`SELECT … FOR UPDATE OF outcomes_assessment`) and the term row (`FOR NO KEY UPDATE`). It then copies every draft score to the published column with a single `UPDATE grading_grade SET published_score = score …`, stamps the assessment and writes an audit row. Concurrent publishes of the same assessment serialise on the row lock. A failure at any step rolls back every change, so students never see a partly published assessment. The test `test_crash_after_update_publishes_nothing` proves this by making the audit write fail after the UPDATE has already run.*

### Tests

```python
# apps/grading/tests/test_publish.py
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Enrollment, Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import (
    AssessmentFactory, EnrollmentFactory, GradeFactory, OfferingFactory, UserFactory,
)
from apps.core.tests.scenarios import elif_scenario
from apps.grading.models import Grade
from apps.grading.selectors import publish_preview
from apps.grading.services import publish_assessment, save_grade, unpublish_assessment
from apps.scoring.engine import compute_student_profile, display
from apps.scoring.loaders import load_student_inputs

pytestmark = pytest.mark.django_db


@pytest.fixture
def midterm():
    """4 enrolled students: two scores, one excused, one missing. Plus a dropped student."""
    offering = OfferingFactory(term__status=Term.Status.OPEN)
    a = AssessmentFactory(offering=offering, name="Midterm I", max_score=Decimal("100"))
    e1, e2, e3, _e4 = (EnrollmentFactory(offering=offering) for _ in range(4))
    GradeFactory(assessment=a, enrollment=e1, score=Decimal("90"))
    GradeFactory(assessment=a, enrollment=e2, score=Decimal("80"))
    GradeFactory(assessment=a, enrollment=e3, score=None, is_excused=True)
    dropped = EnrollmentFactory(offering=offering, status=Enrollment.Status.DROPPED)
    GradeFactory(assessment=a, enrollment=dropped, score=Decimal("10"))
    return a


def test_preview_counts_only_enrolled_students(midterm):
    p = publish_preview(midterm)
    assert (p.enrolled, p.graded, p.excused, p.missing, p.changes) == (4, 2, 1, 1, 3)
    assert p.is_first_publish and p.can_publish


def test_publish_copies_drafts_and_audits(midterm):
    user = UserFactory()
    result = publish_assessment(user, midterm, expected_changes=3)

    assert (result.published, result.excused, result.skipped_missing, result.changed) == (2, 1, 1, 3)
    for g in Grade.objects.filter(assessment=midterm):
        assert g.published_score == g.score
        assert g.published_is_excused == g.is_excused
        assert g.published_at is not None
        assert not g.has_unpublished_change
    midterm.refresh_from_db()
    assert midterm.published_at is not None and midterm.published_by == user

    event = AuditEvent.objects.get(action="assessment.publish")
    assert event.actor == user and event.entity_id == midterm.pk
    assert event.before["published_at"] is None
    assert event.after["published"] == 2 and event.after["skipped_missing"] == 1


def test_crash_after_update_publishes_nothing(midterm, monkeypatch):
    """B7 AC 2: a failure half-way leaves zero grades published."""
    def boom(*args, **kwargs):
        raise RuntimeError("audit table is on fire")

    monkeypatch.setattr("apps.core.audit.record", boom)    # runs AFTER the UPDATE in the service
    with pytest.raises(RuntimeError):
        publish_assessment(UserFactory(), midterm)

    assert not Grade.objects.filter(assessment=midterm, published_score__isnull=False).exists()
    assert not Grade.objects.filter(assessment=midterm, published_at__isnull=False).exists()
    midterm.refresh_from_db()
    assert midterm.published_at is None


def test_publish_locks_assessment_and_term_rows(midterm):
    with CaptureQueriesContext(connection) as ctx:
        publish_assessment(UserFactory(), midterm)
    sql = "\n".join(q["sql"] for q in ctx.captured_queries)
    assert 'FOR UPDATE OF "outcomes_assessment"' in sql
    assert "FOR NO KEY UPDATE" in sql


def test_edit_after_publish_is_a_draft_again(midterm):
    """B7 AC 3: editing a published grade changes nothing students see until re-publish."""
    user = UserFactory()
    publish_assessment(user, midterm)
    grade = Grade.objects.get(assessment=midterm, score=Decimal("90"))
    save_grade(user, midterm, grade.enrollment, "95")

    grade.refresh_from_db()
    assert grade.score == Decimal("95") and grade.published_score == Decimal("90")
    assert publish_preview(midterm).changes == 1

    publish_assessment(user, midterm, expected_changes=1)
    grade.refresh_from_db()
    assert grade.published_score == Decimal("95")


def test_nothing_new_to_publish(midterm):
    user = UserFactory()
    publish_assessment(user, midterm)
    with pytest.raises(ValidationError, match="Nothing new to publish"):
        publish_assessment(user, midterm)


def test_assessment_without_grades_cannot_be_published():
    offering = OfferingFactory(term__status=Term.Status.OPEN)
    a = AssessmentFactory(offering=offering)
    EnrollmentFactory(offering=offering)
    with pytest.raises(ValidationError, match="no grades to publish"):
        publish_assessment(UserFactory(), a)


def test_stale_confirmation_is_refused(midterm):
    """The modal showed 3 changes; someone typed another grade before Confirm."""
    user = UserFactory()
    missing = Enrollment.objects.filter(offering=midterm.offering, status=Enrollment.Status.ENROLLED,
                                        grades__isnull=True).get()
    save_grade(user, midterm, missing, "70")
    with pytest.raises(ValidationError, match="changed while the confirmation was open"):
        publish_assessment(user, midterm, expected_changes=3)
    assert not Grade.objects.filter(published_score__isnull=False).exists()


def test_closed_term_cannot_publish(midterm):
    Term.objects.filter(pk=midterm.offering.term_id).update(status=Term.Status.CLOSED)
    with pytest.raises(ValidationError):
        publish_assessment(UserFactory(), midterm)


def test_unpublish_hides_grades_keeps_drafts_and_records_reason(midterm):
    user = UserFactory()
    publish_assessment(user, midterm)
    hidden = unpublish_assessment(user, midterm, reason="Uploaded the wrong section's file")

    assert hidden == 4                         # every published row, including the dropped student
    for g in Grade.objects.filter(assessment=midterm):
        assert g.published_score is None and g.published_at is None
    assert Grade.objects.filter(assessment=midterm, score=Decimal("90")).exists()   # drafts kept
    event = AuditEvent.objects.get(action="assessment.unpublish")
    assert event.after["reason"] == "Uploaded the wrong section's file"
    midterm.refresh_from_db()
    assert midterm.published_at is None


@pytest.mark.parametrize("reason", ["", "   ", "oops"])
def test_unpublish_needs_a_reason(midterm, reason):
    user = UserFactory()
    publish_assessment(user, midterm)
    with pytest.raises(ValidationError):
        unpublish_assessment(user, midterm, reason=reason)


def test_unpublish_of_draft_assessment_is_refused(midterm):
    with pytest.raises(ValidationError, match="not published"):
        unpublish_assessment(UserFactory(), midterm, reason="Testing the guard")


# ---- what students and the engine see (policy P4) --------------------------------------

def _po(profile, po):
    return display(profile.po_scores[po.id].score) if po.id in profile.po_scores else "—"


def test_scores_follow_publish_not_drafts():
    """The professor's example end to end: drafts invisible, publish shows 85.0 / 82.9,
    a later draft edit changes nothing, re-publishing changes everything at once."""
    s = elif_scenario(published=False)
    user = UserFactory()

    before = compute_student_profile(load_student_inputs(s.student))
    assert (_po(before, s.po1), _po(before, s.po2)) == ("—", "—")        # B7 AC 1: nothing visible yet

    publish_assessment(user, s.midterm)
    publish_assessment(user, s.project)
    after = compute_student_profile(load_student_inputs(s.student))
    assert (_po(after, s.po1), _po(after, s.po2)) == ("85.0", "82.9")

    enrollment = Enrollment.objects.get(offering=s.offering, student=s.student)
    save_grade(user, s.midterm, enrollment, "50")                      # draft only
    unchanged = compute_student_profile(load_student_inputs(s.student))
    assert (_po(unchanged, s.po1), _po(unchanged, s.po2)) == ("85.0", "82.9")

    publish_assessment(user, s.midterm)
    # LO1 = (50·60 + 80·40)/100 = 62; LO2 = (50·40 + 80·100)/140 = 71.43
    # PO1 = (62·4 + 71.43·2)/6 = 65.14; PO2 = 71.43
    republished = compute_student_profile(load_student_inputs(s.student))
    assert (_po(republished, s.po1), _po(republished, s.po2)) == ("65.1", "71.4")


def test_unpublished_midterm_drops_out_of_scores():
    s = elif_scenario(published=False)
    user = UserFactory()
    publish_assessment(user, s.midterm)
    publish_assessment(user, s.project)
    unpublish_assessment(user, s.midterm, reason="Wrong answer key used")
    # Only the project (80) remains: LO1 = 80, LO2 = 80, so PO1 = PO2 = 80.0
    profile = compute_student_profile(load_student_inputs(s.student))
    assert (_po(profile, s.po1), _po(profile, s.po2)) == ("80.0", "80.0")
```

`elif_scenario(published=False)` creates the slide's grades as drafts (90 and 80) with nothing published. That's the keyword argument S1-08 defined for exactly this test.

```python
# apps/grading/tests/test_publish_views.py
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.accounts.models import ProgramMembership
from apps.catalog.models import Term
from apps.core.tests.factories import (
    AssessmentFactory, EnrollmentFactory, GradeFactory, MembershipFactory, OfferingFactory,
    UserFactory,
)
from apps.grading.models import Grade

pytestmark = pytest.mark.django_db


@pytest.fixture
def course(client):
    offering = OfferingFactory(term__status=Term.Status.OPEN)
    instructor = UserFactory()
    MembershipFactory(user=instructor, program=offering.course.program,
                      role=ProgramMembership.Role.INSTRUCTOR)
    offering.instructors.add(instructor)
    a = AssessmentFactory(offering=offering, name="Midterm I", max_score=Decimal("100"))
    for score in ("90", "80", None):
        e = EnrollmentFactory(offering=offering)
        if score:
            GradeFactory(assessment=a, enrollment=e, score=Decimal(score))
    client.force_login(instructor)
    return offering, a


def _url(name, offering, a):
    return reverse(name, kwargs={"offering_id": offering.id, "assessment_id": a.id})


def test_modal_shows_counts_and_zero_warning(course, client):
    offering, a = course
    response = client.get(_url("grading:publish", offering, a), headers={"HX-Request": "true"})
    body = response.content.decode()
    assert response.status_code == 200
    assert "Publish Midterm I?" in body
    assert "<strong>2</strong> of 3 students have a score" in body
    assert "skipped, not counted as zero" in body
    assert 'name="expected_changes"' in body and 'value="2"' in body


def test_htmx_publish_redirects_client_and_reports(course, client):
    offering, a = course
    response = client.post(_url("grading:publish", offering, a), {"expected_changes": "2"},
                           headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response["HX-Redirect"] == reverse("grading:sheet", kwargs={"offering_id": offering.id})
    text = [str(m) for m in get_messages(response.wsgi_request)]
    assert text == ["Midterm I published to 2 students. "
                    "1 had no grade and were skipped (not counted as zero)."]
    assert Grade.objects.filter(published_score__isnull=False).count() == 2


def test_plain_post_falls_back_to_normal_redirect(course, client):
    offering, a = course
    response = client.post(_url("grading:publish", offering, a), {"expected_changes": "2"})
    assert response.status_code == 302


def test_stale_count_shows_error_and_publishes_nothing(course, client):
    offering, a = course
    response = client.post(_url("grading:publish", offering, a), {"expected_changes": "5"},
                           headers={"HX-Request": "true"})
    text = " ".join(str(m) for m in get_messages(response.wsgi_request))
    assert "changed while the confirmation was open" in text
    assert not Grade.objects.filter(published_score__isnull=False).exists()


def test_unpublish_short_reason_keeps_modal_open(course, client):
    offering, a = course
    client.post(_url("grading:publish", offering, a), {"expected_changes": "2"})
    response = client.post(_url("grading:unpublish", offering, a), {"reason": "no"},
                           headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert "HX-Redirect" not in response
    assert "is-invalid" in response.content.decode()
    assert Grade.objects.filter(published_score__isnull=False).count() == 2


def test_unpublish_with_reason(course, client):
    offering, a = course
    client.post(_url("grading:publish", offering, a), {"expected_changes": "2"})
    response = client.post(_url("grading:unpublish", offering, a),
                           {"reason": "Wrong answer key"}, headers={"HX-Request": "true"})
    assert "HX-Redirect" in response
    assert not Grade.objects.filter(published_score__isnull=False).exists()


def test_student_cannot_open_publish(course, client):
    offering, a = course
    student = EnrollmentFactory(offering=offering).student
    client.force_login(student)
    assert client.get(_url("grading:publish", offering, a)).status_code == 404
    assert client.post(_url("grading:publish", offering, a), {"expected_changes": "2"}).status_code == 404
    assert not Grade.objects.filter(published_score__isnull=False).exists()
```

### Check it works

1. Run `seed_demo --reset` and log in as Dr. Can Aydın. Open a 2026F course's grades and type three scores.
   - **Expected:** the column shows "3 unpublished" and a **Publish** button.
2. Click **Publish**.
   - **Expected:** the modal says how many students have a score and warns about the students with no grade ("skipped, not counted as zero").
3. Confirm.
   - **Expected:** the sheet reloads with a green toast, the badge says **Published**, and the button disappears.
4. In a private window, log in as one of those students.
   - **Expected:** their course page (S3-02) now shows the score. Before step 3 it showed "Not published yet".
5. Change one grade.
   - **Expected:** the column shows "1 unpublished" and **Publish changes**, and the student still sees the old value.
6. Open the publish modal, then type another grade in a second tab, then confirm in the first tab.
   - **Expected:** a red toast says the grades changed while the confirmation was open, and nothing was published.
7. Click **Unpublish**, type "ok", and submit.
   - **Expected:** an error under the field.
8. Type a real reason.
   - **Expected:** the grades are hidden, and Django admin → Audit events shows the reason.

### Done when

| AC (Part 6) | Proved by |
|---|---|
| B7 AC 1: "Not published yet" before, the score after | `test_scores_follow_publish_not_drafts` (engine side). The label itself is rendered by S3-02's course page and tested there |
| B7 AC 2: a crash half-way leaves zero grades published | `test_crash_after_update_publishes_nothing` |
| B7 AC 3: editing a published grade doesn't change what the student sees until re-publish | `test_edit_after_publish_is_a_draft_again`, `test_scores_follow_publish_not_drafts` |
| B7 AC 4: grade changes, publish and unpublish all audited with actor, before and after | `test_publish_copies_drafts_and_audits`, `test_unpublish_hides_grades_keeps_drafts_and_records_reason`, S2-06's audit tests |
| Modal text: "N students have no grade, skipped not zero" | `test_modal_shows_counts_and_zero_warning` |
| Locking per §5.6 | `test_publish_locks_assessment_and_term_rows` |
| Permissions | Matrix rows plus `test_student_cannot_open_publish` |

### Commits and PR

```
Add publish preview counts for the confirmation modal (#S3-01)
Publish an assessment's grades in one locked transaction (#S3-01)
Add unpublish with a required reason (#S3-01)
Add publish and unpublish modals to the grade sheet (#S3-01)
```

PR title: **Publish and unpublish grades per assessment (S3-01)**. In the PR description, paste the paragraph from step 8. The reviewer should check that it matches the code.

---

## S3-06 · Production stack, first release v0.3.0, nightly backups

**Points:** 2 · **Owner:** Person C · **Branch:** `feature/S3-06-production` (scripts and docs), then the release PR `develop` → `main` · **Depends on:** S2-08

### Goal

Production runs next to staging on the same server, deployed from `main` only after a teammate approves. The first release, `v0.3.0` ("baseline complete"), goes out on Sunday 8 November. The production database and uploaded files are backed up every night at 03:00 and kept for 14 days. We **prove** the backups work by restoring one into staging and timing it. An untested backup is a hope, not a backup.

The restore drill also gives CSE 321 its fault-tolerance numbers:

- **RPO** (recovery point objective: how much data we can lose) is at most 24 hours, because backups are nightly.
- **RTO** (recovery time objective: how long recovery takes) is whatever the drill measures.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `deploy/backup.sh` | create | Nightly database and media backup, with rotation |
| `deploy/restore-into-staging.sh` | create | The restore drill as a script, so it's repeatable |
| `deploy/env.production.example` | create | Production `.env` keys with dummy values |
| `docs/process/deployment.md` | modify | Production section, the release procedure, where the backups are |
| `docs/process/restore-drill.md` | create | Results of each drill (template below) |
| `.github/pull_request_template.md` | no change | The release PR uses the body template in step 5 |

### Steps

**1. The production folder and `.env`.**

On the server, as `deploy`:

```bash
cp /srv/polaris/staging/compose.prod.yml /srv/polaris/production/
nano /srv/polaris/production/.env && chmod 600 /srv/polaris/production/.env
```

Production uses the same keys as staging (S2-08 step 8), with these differences:

| Key | Production value | Why it differs |
|---|---|---|
| `STACK` | `production` | Caddy routes `polaris-cse.duckdns.org` to the alias `production-web` |
| `COMPOSE_PROJECT_NAME` | `polaris-production` | Separate containers **and separate volumes** (`polaris-production_pgdata`). Get this wrong and production shares staging's database |
| `IMAGE_TAG` | `main` | The first deploy overwrites it with a commit SHA |
| `SECRET_KEY`, `POSTGRES_PASSWORD` | **new** random values | Never reuse staging's: a leaked staging secret must not open production |
| `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` | `polaris-cse.duckdns.org` / `https://polaris-cse.duckdns.org` | |
| `EMAIL_URL` | real SMTP, e.g. `smtp+tls://apikey-user:<url-encoded-password>@smtp-relay.brevo.com:587` | Password-reset emails must actually arrive (B1 AC 3). Any free transactional provider works. A Gmail **app password** (`smtp+tls://you%40gmail.com:<app-password>@smtp.gmail.com:587`) is fine for a course project |
| `DEFAULT_FROM_EMAIL` | `POlaris <the address your provider verified>` | Providers reject mail from unverified senders |

In `EMAIL_URL`, any `@`, `:` or `/` inside the user name or password must be **percent-encoded** (`@` → `%40`). Otherwise django-environ splits the URL in the wrong place and Django fails at startup with a confusing error.

**2. Protect the production environment in GitHub.**

Go to Repo → Settings → Environments → `production`:

- **Required reviewers:** the other two teammates. Tick **Prevent self-review**, so whoever merged the release can't also approve the deploy alone. The repo is public, so this feature is available on a free plan.
- **Deployment branches:** `main` only (set in S2-08).

Then go to Repo → Settings → General → Pull Requests:

- Allow **squash merging**, used for feature PRs into `develop`.
- Allow **merge commits**, used for release PRs into `main`.
- Disallow rebase merging.

This matches §9.6, and it means nobody has to remember which button to press: there are only two.

**3. The backup script.**

Three design choices:

- **The dump runs inside the `db` container** (`docker compose exec -T db`), so the server needs no PostgreSQL client and the `pg_dump` version always matches the server. `-T` turns off the pseudo-terminal, which cron doesn't have.
- **The file is written as `.part` and renamed only after `gzip -t` succeeds.** A half-written dump (disk full, crash) never looks like a good backup.
- **Uploaded files are backed up too.** Syllabi, grade files and exports live in the `media` volume. A database whose `IngestionJob.file` points at missing files is only half restored.

```bash
#!/usr/bin/env bash
# deploy/backup.sh  →  copy to /srv/backups/backup.sh on the server, chmod +x
# Nightly production backup: database (plain SQL, gzipped) + uploaded files. Keeps 14 days.
set -euo pipefail

STACK_DIR=/srv/polaris/production
OUT=/srv/backups
STAMP=$(date +%F)
KEEP_DAYS=14
MEDIA_VOLUME=polaris-production_media      # <COMPOSE_PROJECT_NAME>_media

cd "$STACK_DIR"

# 1. Database. The single quotes matter: $POSTGRES_USER / $POSTGRES_DB expand INSIDE the container.
docker compose -f compose.prod.yml exec -T db \
  sh -c 'pg_dump --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > "$OUT/polaris-$STAMP.sql.gz.part"
gzip -t "$OUT/polaris-$STAMP.sql.gz.part"
mv "$OUT/polaris-$STAMP.sql.gz.part" "$OUT/polaris-$STAMP.sql.gz"

# 2. Uploaded files (read-only mount of the media volume).
docker run --rm -v "$MEDIA_VOLUME":/media:ro -v "$OUT":/out alpine:3 \
  tar czf "/out/media-$STAMP.tgz" -C /media .

# 3. Rotation.
find "$OUT" -maxdepth 1 -name 'polaris-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
find "$OUT" -maxdepth 1 -name 'media-*.tgz' -mtime +"$KEEP_DAYS" -delete
find "$OUT" -maxdepth 1 -name '*.part' -mtime +1 -delete

echo "$(date -Is) backup ok: db $(du -h "$OUT/polaris-$STAMP.sql.gz" | cut -f1), media $(du -h "$OUT/media-$STAMP.tgz" | cut -f1)"
```

`set -o pipefail` is what makes a failed `pg_dump` fail the script. Without it, the pipeline's exit status would be `gzip`'s, which succeeds happily on empty input.

This is the §10.6 one-liner turned into a script, with three additions:

- the integrity check;
- the media backup;
- reading the user and database names from the container instead of hard-coding them.

Install it and schedule it:

```bash
scp deploy/backup.sh deploy@<ip>:/srv/backups/backup.sh
ssh deploy@<ip>
chmod +x /srv/backups/backup.sh
/srv/backups/backup.sh                       # run once by hand: must print "backup ok"
ls -lh /srv/backups/
crontab -e                                   # as deploy, add the line below
```

```
0 3 * * * /srv/backups/backup.sh >> /srv/backups/backup.log 2>&1
```

The server's time zone is `Europe/Istanbul` (S2-08 step 5), so this runs at 03:00 local time. Check `backup.log` on Monday morning.

**4. Keep a copy off the server.**

Backups on the same VPS don't survive the VPS being deleted, hacked or out of disk. Pick at least one:

- Turn on the hosting provider's **automatic server backups**. On Hetzner it's a checkbox, about 20% of the server price.
- Have one teammate pull the backups to their laptop every Sunday after the sprint review. This takes 10 seconds:

```bash
rsync -avz deploy@<ip>:/srv/backups/ ~/polaris-backups/
```

Write in `docs/process/deployment.md` which one we chose and who does it.

**5. The release PR (Sunday morning).**

Every commit on `main` is a release (§9.6). Open the PR from GitHub, or with:

```bash
gh pr create --base main --head develop --title "Release v0.3.0: baseline complete" --body-file - <<'MD'
## Release v0.3.0 — baseline complete

**Stories:** S3-01 publish · S3-02 student profile · S3-03 course results · S3-04 department overview ·
S3-05 enrollment import · S3-06 production · S3-07 seed v2

**Migrations in this release:** (list the new migration files; each must be backwards-compatible, §9.10)

**Manual server steps after deploy:** none (or: copy compose.prod.yml, run a command…)

**Verified on staging:** the baseline loop (head → instructor → publish → student → head), by @… on …
MD
```

Then:

1. A teammate reviews it, mostly checking that staging really was verified.
2. **Merge with "Create a merge commit"**, not squash. The merge commit marks the release point in history.
3. The `CD` workflow runs CI, builds the image, and then **waits** at the `deploy` job: "Waiting for review". One of the required reviewers clicks **Review deployments → production → Approve**.
4. The deploy runs: pull, migrate, up, smoke test.

**6. First production data.**

The first deploy creates empty tables. Production holds the **curated demo data**, which is the same `seed_demo`, because that's what the checkpoints and the final demo show:

```bash
cd /srv/polaris/production
docker compose -f compose.prod.yml exec web python manage.py seed_demo --allow-production
docker compose -f compose.prod.yml exec web python manage.py createsuperuser
docker compose -f compose.prod.yml exec web python manage.py check --deploy --fail-level WARNING
```

Save the printed persona passwords in the team's password manager, not in the repo. Once we start curating production data by hand for the demo (Sprint 9), **stop** running `seed_demo` on production: `--reset` would wipe the curated data.

**7. Tag the release.**

Tag only after the smoke test is green, so a tag always means "this is running in production":

```bash
gh release create v0.3.0 --target main --title "v0.3.0 — Baseline complete" --generate-notes
```

`--generate-notes` lists every PR merged since the previous tag. That's free material for report Section 2 ("number of sprints carried out").

**8. The restore drill (before the CSE 321 checkpoint on 12 November).**

We restore last night's **production** backup into **staging** and time every step. Staging is the safe place to try it: if the drill goes wrong, a re-seed fixes staging in a minute.

```bash
#!/usr/bin/env bash
# deploy/restore-into-staging.sh  →  /srv/backups/restore-into-staging.sh on the server
# Restore the newest production backup into STAGING. Never point this at production.
set -euo pipefail

DUMP=${1:-$(ls -t /srv/backups/polaris-*.sql.gz | head -1)}
cd /srv/polaris/staging
grep -q '^STACK=staging$' .env || { echo "Refusing: this is not the staging folder"; exit 1; }
echo "Restoring $DUMP into staging…"
START=$(date +%s)

docker compose -f compose.prod.yml stop web worker
docker compose -f compose.prod.yml exec -T db \
  psql -U polaris -d postgres -v ON_ERROR_STOP=1 \
  -c 'DROP DATABASE polaris WITH (FORCE);' \
  -c 'CREATE DATABASE polaris OWNER polaris;'
gunzip -c "$DUMP" | docker compose -f compose.prod.yml exec -T db \
  psql -U polaris -d polaris -v ON_ERROR_STOP=1 -q
docker compose -f compose.prod.yml run --rm web python manage.py migrate --noinput
docker compose -f compose.prod.yml start web worker

echo "Restore finished in $(( $(date +%s) - START )) seconds"
```

`DROP DATABASE … WITH (FORCE)` (PostgreSQL 13+) disconnects any remaining sessions first. `ON_ERROR_STOP=1` makes `psql` stop at the first error instead of printing 400 errors and reporting success. The `migrate` step covers the normal case where staging's code is ahead of production's backup.

The script names `polaris` as the user and database because both stacks use those values (S2-08 step 8). If you ever change `POSTGRES_USER` or `POSTGRES_DB`, change the script too.

Run it and verify:

```bash
/srv/backups/restore-into-staging.sh
curl -fsS https://staging-polaris-cse.duckdns.org/healthz
# same counts on both stacks?
for s in production staging; do
  (cd /srv/polaris/$s && docker compose -f compose.prod.yml exec -T web python manage.py shell -c \
    "from apps.accounts.models import User; from apps.grading.models import Grade; print('$s', User.objects.count(), Grade.objects.count())")
done
```

Then log in to **staging** as Elif. Her profile must show PO 1 = 85.0 and PO 2 = 82.9: the restored data is not just present but correct.

Record the result in `docs/process/restore-drill.md`:

```markdown
# Restore drill

| Date | Dump | Dump size | Restore time | Users / grades (prod → staging) | Elif's PO1/PO2 after | Problems | By |
|---|---|---|---|---|---|---|---|
| 2026-11-10 | polaris-2026-11-10.sql.gz | … MB | … s | … / … → … / … | 85.0 / 82.9 | … | … |

**RPO** (max data loss): 24 h — nightly backups at 03:00.
**RTO** (time to restore the database): the restore time above, plus about 5 minutes to notice and start.
```

Restoring the **media** archive is the same idea: `docker run --rm -v polaris-staging_media:/media -v /srv/backups:/in alpine:3 sh -c 'rm -rf /media/* && tar xzf /in/media-<date>.tgz -C /media'`. Do it once in the drill too, and note whether an uploaded syllabus opens afterwards.

### Rollback (when a release is bad)

The procedure is in §9.10. In practice:

1. Find the previous release's SHA: `gh release view v0.2.x --json targetCommitish` or the Actions history.
2. On the server, set `IMAGE_TAG=<that SHA>` in `/srv/polaris/production/.env`.
3. Run `docker compose -f compose.prod.yml up -d`.
4. Fix forward on `develop` and cut `v0.3.1`.

Don't roll back migrations by hand. That's why migrations must stay backwards-compatible for one release.

### Tests

As with S2-08, the evidence is runs and records rather than pytest:

1. **The CD run of the release:** CI green, image built, "Waiting for review", approved by a teammate, deploy, smoke test green. Screenshot the run summary into `docs/process/sprint-03/runs.md`. The approval step is good report Section 5 material, because it shows a human gate before production.
2. **`backup.log`** shows at least two consecutive nights with "backup ok".
3. **`restore-drill.md`** has one completed row, with matching counts and Elif's numbers.
4. **Try to break the script once:** run `backup.sh` with production's `db` container stopped. It must exit non-zero, leave only a `.part` file, and not log "backup ok". Write down what happened.

### Check it works

1. `https://polaris-cse.duckdns.org/healthz` → `{"db": "ok", "cache": "ok"}`.
2. Production and staging are different databases: create a test term on staging, and it doesn't appear on production.
3. Request a password reset on production for your own account. The email arrives in a real inbox, and the link works once.
4. The full baseline loop on production, recorded as the 3-minute video for both checkpoints (Sprint 3 goal).
5. `ls /srv/backups` on Monday morning shows `polaris-2026-11-09.sql.gz` and `media-2026-11-09.tgz`.

### Done when

- [ ] `main` deploys to production only after a teammate approves, and `v0.3.0` is tagged on the deployed commit.
- [ ] Production has its own secrets, database and media volume, and working email.
- [ ] Nightly backups of the database and media, with 14-day rotation, run from cron. There's one off-server copy method in place.
- [ ] Restore drill done, timed and recorded, with RPO/RTO written down for CSE 321.
- [ ] `docs/process/deployment.md` covers production, releases, backups and rollback.

### Commits and PR

```
Add nightly database and media backup script (#S3-06)
Add restore-into-staging script for backup drills (#S3-06)
Document production deployment, releases and rollback (#S3-06)
Record first restore drill results (#S3-06)
```

PR titles:

- **Production stack, backups and restore drill (S3-06)**, into `develop`.
- **Release v0.3.0: baseline complete**, `develop` → `main`.

---

## Code map additions

Add these lines to §4.8 in the PR that introduces them:

| Module | Name | Signature | Purpose |
|---|---|---|---|
| `apps/grading/services.py` | `parse_score_input` | `(raw, max_score, *, label="this assessment") -> tuple[Decimal \| None, bool]` | Adds the keyword `label`, so the over-max message can name the assessment (B6 AC 1) |
| `apps/grading/services.py` | `save_grade` | `(user, assessment, enrollment, raw) -> Grade \| None` | Returns `None` when a blank cell had no grade (nothing written) |
| `apps/grading/services.py` | `_lock_open_term` | `(offering) -> None` | Private. Locks the term row `FOR NO KEY UPDATE` and calls `ensure_term_open`, inside `atomic()` |
| `apps/grading/services.py` | `PublishResult` | dataclass `published, excused, skipped_missing, changed` | Code map listed `published, skipped_missing`; adds `excused` and `changed` |
| `apps/grading/services.py` | `publish_assessment` | `(user, assessment, *, expected_changes=None) -> PublishResult` | Adds `expected_changes` (stale-confirmation guard) |
| `apps/grading/services.py` | `unpublish_assessment` | `(user, assessment, *, reason) -> int` | Returns the number of grades hidden |
| `apps/grading/selectors.py` | `SheetCell`, `SheetRow`, `SheetColumn` | dataclasses | The rows, cells and columns of `GradeSheet` (`GradeSheet` keeps `assessments`, `students`, `grades` and `unpublished_counts` as in §4.8) |
| `apps/grading/selectors.py` | `unpublished_changes` | `(assessment) -> int` | One-query count of drafts that differ from the published value |
| `apps/grading/selectors.py` | `column_for` | `(assessment) -> SheetColumn` | Header numbers for the out-of-band refresh after a cell save |
| `apps/grading/selectors.py` | `PublishPreview`, `publish_preview` | `(assessment) -> PublishPreview` | Counts for the publish modal and the service |
| `apps/grading/templates/grading/` | `publish_modal.html`, `unpublish_modal.html` | templates | Modal bodies loaded with `hx-get` |
| `deploy/` | `edge/compose.yml`, `edge/Caddyfile`, `env.staging.example`, `env.production.example`, `backup.sh`, `restore-into-staging.sh` | files | Server configuration kept in the repo (add `deploy/` to the §4.3 layout) |
