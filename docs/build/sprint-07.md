# Sprint 7: Dashboards and polish (FEATURE COMPLETE)

**Mon 30 Nov – Sun 6 Dec 2026** · Planned: 23 points (A 8 / B 8 / C 7) · Ends with tag `v0.7.0`

This is the sprint where POlaris becomes the product we demo. Everything Tier 1 that is still missing lands here:

- the head's dashboard gets its last two panels and its filters;
- every report can leave the system as a PDF or an Excel file;
- the student profile becomes the "radar + where does it come from + how has it moved" page from the wireframe;
- anyone allowed can see who changed what;
- three browser tests prove the main journeys work end to end;
- an accessibility and speed pass catches what we broke along the way.

Nothing here changes how a score is calculated. Every number still comes from `apps/scoring/engine.py`. This sprint only adds new ways to look at and export those numbers. If you find yourself writing arithmetic on scores outside the engine, stop and add a pure function to the engine instead (S7-04 shows how).

| ID | Story | Pts | Owner | Branch |
|---|---|---|---|---|
| S7-01 | Coverage heat map + under-covered flags | 3 | C | `feature/S7-01-coverage-heatmap` |
| S7-02 | Dashboard filters (term range, cohort, closed-only) + completion panel | 2 | C | `feature/S7-02-dashboard-filters` |
| S7-03 | Exports: course + department, PDF (WeasyPrint, Celery) + Excel, REPEATABLE READ | 5 | A | `feature/S7-03-exports` |
| S7-04 | Student profile v2: radar, per-course breakdown, trend, summary sentence | 5 | B | `feature/S7-04-profile-v2` |
| S7-05 | Audit history viewer (offering timeline, per-grade history, head view) | 3 | B | `feature/S7-05-audit-viewer` |
| S7-06 | Playwright smoke tests: 3 golden paths | 3 | A | `feature/S7-06-e2e` |
| S7-07 | Accessibility + Lighthouse pass on key pages | 2 | C | `feature/S7-07-a11y-perf` |

**Merge order.**

1. S7-01, then S7-02. They are both Person C's and both touch `reports/department.html`, so doing them in sequence avoids conflicts.
2. S7-04 and S7-05 are independent of everything else. Merge them whenever they're ready.
3. S7-03 needs S7-02's `DashboardFilters` for the department export. Person A starts with the course export, which has no dependency, and rebases on S7-02 once it lands (target: Wednesday).
4. S7-06 goes last because it drives the finished UI. Its step 1 (accessible names on grid cells) can be merged on Monday, since S7-07 relies on it too.
5. S7-07 merges on Saturday. Then run the full demo script (spec §13.3) on staging.

**What must work by Sunday (the sprint checkpoint).** Run the spec §13.3 demo script on production without opening Django admin. In particular:

- The department dashboard shows the heat map, with PO 11 flagged "Not covered by any course" and PO 9 flagged "Only 1 course". The seed data has both flaws on purpose.
- Changing the filters changes the numbers and the URL.
- "Export PDF" gives a PDF whose numbers match the screen.
- Elif's profile shows the radar, the per-course breakdown and a trend with one point per term.
- Changing a grade and publishing it shows two events in the history.
- The nightly e2e workflow has run green at least once.

Then tag `v0.7.0` on `main`.

---

## Interfaces this chapter relies on (built in earlier sprints)

The code below calls functions written in Sprints 1–6. The names come from spec §4.8. The **shapes** (attribute names on returned objects) are listed here so you can check them before you start. If an earlier sprint built something with different attribute names, change *this* chapter's code to match, not the other way round, and note it in your PR.

| From | Name | Shape this chapter assumes |
|---|---|---|
| S1-07 | `scoring.loaders.load_student_inputs(student, *, include_open_terms=True, up_to_term=None)` | `up_to_term` is a `Term`: only offerings whose `term.starts_on <= up_to_term.starts_on` are loaded. P4, P9, P10 and P13 are already applied |
| S1-08 | `core.tests.factories.*`, `core.tests.scenarios.elif_scenario()` | Factories accept every model field as a keyword. `elif_scenario()` returns a namespace with `offering, student, midterm, project, lo1, lo2, po1, po2` |
| S1-09 | `templates/base.html` | Has `{% block content %}`, `{% block scripts %}`, and one shared Bootstrap modal `#modal` whose `#modal-content` HTMX fills. Loads `vendor/chart.umd.min.js` (in `{% block chart_js %}`) and `js/polaris.js` |
| S1-09 | `includes/empty_state.html` | Takes `title` and `message` |
| S2-02 | permission matrix | `ROUTES` in `apps/accounts/tests/routes.py`: one `Route(name, expect, kwargs=…, method=…, story=…)` per URL, with presets `OFFERING_STAFF`, `HEAD`, `EXPORT_OWNER`… Rows for every §4.8 URL already exist and switch on when the URL resolves |
| S2-05 | `outcomes.selectors.mapping_grid(offering) -> MappingGrid` | `.assessments`, `.los`, `.pos` (lists of model objects); `.a_lo: dict[(assessment_id, lo_id), Decimal]`; `.lo_po: dict[(lo_id, po_id), int]` |
| S2-06 | `grading/sheet.html` | Has a `{% partialdef cell %}` that renders one `<td>` per grade cell with `assessment` and `enrollment` in context |
| B11 | `outcomes.lint.run_lint`, `outcomes.selectors.snapshot_mapping` | `LintIssue(code, severity, message, target)` |
| S3-03 | `scoring.aggregates.class_lo_summary(offering) -> ClassLOSummary` | `.los` (list of `LearningOutcome`); `.rows` (list with `.enrollment` and `.scores: dict[lo_id, NodeScore]`); `.class_mean: dict[lo_id, Decimal \| None]`; `.po_contribution: dict[po_id, Decimal \| None]` |
| S3-03 | `reports.selectors.course_results_context(offering) -> dict` | Contains `"summary"` (the `ClassLOSummary` above) and `"pos"` (the active set's POs) |
| S3-04 / S6-05 | `scoring.aggregates.program_po_summary(...)` | Returns a list of `POSummary(po, mean, n_with_evidence, attainment_rate)`. `attainment_rate` is a `Decimal` in 0..1 or `None` |
| S6-05 | `scoring.aggregates.attainment_matrix(program, *, by, terms, threshold)` | `AttainmentMatrix(columns: list[str], rows: list[AttainmentRow], target: Decimal)`. `AttainmentRow(po, cells: list[Decimal \| None])` is in column order, rates 0..1 |
| S6-05 | `reports/department.html` | Has `{% partialdef attainment %}`, which renders `attainment` from the context |

---

## S7-01 · Coverage heat map + under-covered flags

**Points:** 3 · **Owner:** Person C · **Branch:** `feature/S7-01-coverage-heatmap` · **Depends on:** S2-05 (LO→PO weights exist), S6-05 (department page)

### Goal

The head sees, in one table, how strongly each course feeds each PO. A cell is the sum of the course's LO→PO weights for that PO. The last row totals each PO across courses. POs that no course covers, that only one course covers, or whose total is low get a visible warning. That warning is the "our curriculum under-covers PO 11" moment in the demo. Delivers T1.6 heat map, AC 2.

### Design choices (read before coding)

- **One row per course, using its latest offering in the selected terms.** If CSE 311 ran in Fall 2025 and Fall 2026, adding both offerings' weights would count the course twice. The heat map answers "what does our curriculum cover?", and the latest offering is the curriculum as it stands now. When a course has two sections in the same term, we take the section that sorts first ("1"). Sections share a syllabus.
- **The cell is a plain sum of 1–5 weights, not a score.** This is mapping data, not student data, so it does not belong in the engine. That's why it lives in `scoring/aggregates.py` next to the other program-level summaries.
- **The "under-covered" threshold is `MIN_PO_COVERAGE = 6`.** Two courses each linking one LO at a medium strength (3) reach 6. Below that, the program's claim to teach the PO rests on very little. It's a constant, not a setting: nobody has asked to change it, and Getting Real's *Avoid Preferences* (Ch. 8) applies. If the head disagrees in a review, change the number.
- **Flags are text, not only colour.** Each flagged total gets a ⚠ and a sentence in a list under the table. Spec §8.2 says colour is never the only signal.
- **Colour levels are relative to the largest cell.** Level 0 means no link. Levels 1–4 are quarter steps up to the largest cell in the table. Absolute buckets would make every cell look the same in a program with uniformly light mappings.
- Spec T2.3 (S8-02) later swaps the source of these sums for the `mv_course_po_coverage` materialized view. The function's return type stays the same, so the template does not change.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/scoring/aggregates.py` | modify | `MIN_PO_COVERAGE`, `CoverageCell`, `CoverageTotal`, `CoverageRow`, `CoverageMatrix`, `coverage_matrix()` |
| `apps/reports/selectors.py` | modify | `department_context()` adds `coverage` (full replacement is in S7-02; here you add one key) |
| `apps/reports/templates/reports/department.html` | modify | new `{% partialdef coverage %}` and where it's rendered |
| `static/css/polaris.css` | modify | `.heat-0` … `.heat-4`, `.heat-flag` |
| `apps/scoring/tests/test_coverage.py` | create | unit tests |
| `apps/reports/tests/test_department_coverage.py` | create | view test |

### Steps

**1. Add the data classes and the function to `apps/scoring/aggregates.py`.**

Put the imports at the top of the file alongside the existing ones. Ruff's `I` rule sorts them for you.

```python
# apps/scoring/aggregates.py  (additions for S7-01)
from dataclasses import dataclass

from django.db.models import Sum

from apps.catalog.models import Course, CourseOffering, ProgramOutcome
from apps.catalog.selectors import active_po_set
from apps.outcomes.models import LOPOWeight

MIN_PO_COVERAGE = 6  # a PO whose column total is below this is "under-covered" (see S7-01 notes)


@dataclass(frozen=True)
class CoverageCell:
    po_id: int
    value: int   # Σ LO→PO weight of this course for this PO; 0 = no link
    level: int   # 0..4, colour step relative to the largest cell in the table


@dataclass(frozen=True)
class CoverageTotal:
    po: ProgramOutcome
    value: int
    course_count: int
    flags: tuple[str, ...]


@dataclass(frozen=True)
class CoverageRow:
    course: Course
    offering: CourseOffering
    cells: tuple[CoverageCell, ...]   # in PO order, one per PO
    total: int


@dataclass(frozen=True)
class CoverageMatrix:
    pos: tuple[ProgramOutcome, ...]
    rows: tuple[CoverageRow, ...]
    totals: tuple[CoverageTotal, ...]  # in PO order
    max_cell: int

    @property
    def flagged(self) -> list[CoverageTotal]:
        return [t for t in self.totals if t.flags]


def _level(value: int, max_cell: int) -> int:
    if value <= 0 or max_cell <= 0:
        return 0
    # ceil(value / max_cell * 4) with integers only: 1..4
    return min(4, (value * 4 + max_cell - 1) // max_cell)


def _flags(value: int, course_count: int) -> tuple[str, ...]:
    if course_count == 0:
        return ("Not covered by any course",)
    flags = []
    if course_count == 1:
        flags.append("Only 1 course")
    if value < MIN_PO_COVERAGE:
        flags.append(f"Under-covered (total {value}, below {MIN_PO_COVERAGE})")
    return tuple(flags)


def coverage_matrix(program, *, terms) -> CoverageMatrix:
    """Course × PO table of summed LO→PO weights, from the latest offering of each course
    within `terms`. Mapping data only: no grades, no engine."""
    po_set = active_po_set(program)
    pos = tuple(po_set.outcomes.all())

    offerings = (
        CourseOffering.objects.filter(course__program=program, term__in=terms)
        .select_related("course", "term")
        .order_by("course__code", "-term__starts_on", "section")
    )
    latest: dict[int, CourseOffering] = {}
    for off in offerings:
        latest.setdefault(off.course_id, off)   # first one per course = newest term, section "1"

    sums = (
        LOPOWeight.objects.filter(
            learning_outcome__offering__in=list(latest.values()),
            program_outcome__po_set=po_set,
        )
        .values("learning_outcome__offering_id", "program_outcome_id")
        .annotate(total=Sum("weight"))
        .order_by()
    )
    by_offering: dict[int, dict[int, int]] = {}
    for row in sums:
        by_offering.setdefault(row["learning_outcome__offering_id"], {})[row["program_outcome_id"]] = row["total"]

    max_cell = max((v for cells in by_offering.values() for v in cells.values()), default=0)

    rows = []
    for off in latest.values():
        cells = by_offering.get(off.id, {})
        rows.append(CoverageRow(
            course=off.course,
            offering=off,
            cells=tuple(CoverageCell(po.id, cells.get(po.id, 0), _level(cells.get(po.id, 0), max_cell))
                        for po in pos),
            total=sum(cells.values()),
        ))

    totals = []
    for po in pos:
        value = sum(by_offering.get(off.id, {}).get(po.id, 0) for off in latest.values())
        count = sum(1 for off in latest.values() if by_offering.get(off.id, {}).get(po.id, 0) > 0)
        totals.append(CoverageTotal(po=po, value=value, course_count=count, flags=_flags(value, count)))

    return CoverageMatrix(pos=pos, rows=tuple(rows), totals=tuple(totals), max_cell=max_cell)
```

Why `.order_by()` before `.values(...).annotate(...)`: Django adds a model's default ordering columns to `GROUP BY`. That would split the sums into one row per LO. An empty `order_by()` removes the default ordering. `LOPOWeight` has no default ordering today, but the empty call keeps the function correct if someone adds one later. This mistake bites in every aggregate query, so make it a habit.

The function makes three queries: the PO set with its outcomes (two, through `active_po_set` and `.outcomes.all()`), the offerings, and the sums. It never makes one query per course.

**2. Expose it on the department page.**

In `apps/reports/selectors.py`, inside `department_context(...)`, add one key to the returned dict. S7-02 rewrites this function in full and keeps the key.

```python
# apps/reports/selectors.py: inside department_context(...), add one key to the dict it returns
    return {
        # the keys S6-05 already returns stay as they are, then:
        "coverage": coverage_matrix(program, terms=terms),
    }
```

and import it at the top: `from apps.scoring.aggregates import coverage_matrix`.

**3. Add the partial to `apps/reports/templates/reports/department.html`.**

Put the `partialdef` at the bottom of the file, outside `{% block content %}`, the same way the S6-05 `attainment` partial is defined. Render it inside the page body right after the attainment section with `{% partial coverage %}`.

```django
{% partialdef coverage %}
<section class="card mb-4" aria-labelledby="coverage-title">
  <div class="card-body">
    <h2 id="coverage-title" class="h5 mb-1">Coverage heat map</h2>
    <p class="text-body-secondary small mb-3">
      Sum of LO→PO weights (1–5) per course, from the latest offering of each course in the selected terms.
      Darker = stronger link. Every cell also shows its number.
    </p>
    {% if not coverage.rows %}
      {% include "includes/empty_state.html" with title="No courses in these terms" message="Pick a wider term range, or ask instructors to set up their mappings." only %}
    {% else %}
      <div class="table-responsive">
        <table class="table table-sm align-middle heatmap mb-2">
          <caption class="visually-hidden">Sum of learning-outcome to program-outcome weights per course and program outcome</caption>
          <thead>
            <tr>
              <th scope="col">Course</th>
              {% for po in coverage.pos %}
                <th scope="col" class="text-center"><abbr title="{{ po.short_name }}: {{ po.description }}">PO&nbsp;{{ po.number }}</abbr></th>
              {% endfor %}
            </tr>
          </thead>
          <tbody>
            {% for row in coverage.rows %}
              <tr>
                <th scope="row" class="text-nowrap">{{ row.course.code }} <span class="text-body-secondary fw-normal">{{ row.course.title }}</span></th>
                {% for cell in row.cells %}
                  <td class="text-center num heat-{{ cell.level }}">{{ cell.value }}</td>
                {% endfor %}
              </tr>
            {% endfor %}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Total</th>
              {% for t in coverage.totals %}
                <td class="text-center num fw-semibold{% if t.flags %} heat-flag{% endif %}">
                  {{ t.value }}{% if t.flags %}<span aria-hidden="true"> ⚠</span><span class="visually-hidden"> (warning)</span>{% endif %}
                </td>
              {% endfor %}
            </tr>
          </tfoot>
        </table>
      </div>
      {% if coverage.flagged %}
        <ul class="list-unstyled small mb-0" aria-label="Under-covered program outcomes">
          {% for t in coverage.flagged %}
            <li><span aria-hidden="true">⚠</span> <strong>PO {{ t.po.number }}</strong> {{ t.po.short_name }}: {{ t.flags|join:"; " }}</li>
          {% endfor %}
        </ul>
      {% endif %}
    {% endif %}
  </div>
</section>
{% endpartialdef %}
```

**4. Add the colour steps to `static/css/polaris.css`.**

They're built from the existing `--pl-primary` token, so dark mode follows automatically. Levels 3 and 4 switch to white text to keep WCAG AA contrast. S7-07 verifies that.

```css
/* S7-01 coverage heat map */
.heatmap .num { font-variant-numeric: tabular-nums; min-width: 2.75rem; }
.heat-0 { background: transparent; color: var(--bs-secondary-color); }
.heat-1 { background: color-mix(in srgb, var(--pl-primary) 12%, transparent); }
.heat-2 { background: color-mix(in srgb, var(--pl-primary) 30%, transparent); }
.heat-3 { background: color-mix(in srgb, var(--pl-primary) 65%, transparent); color: #fff; }
.heat-4 { background: color-mix(in srgb, var(--pl-primary) 85%, transparent); color: #fff; }
.heat-flag { background: color-mix(in srgb, var(--bs-warning) 30%, transparent); }
```

### Tests

```python
# apps/scoring/tests/test_coverage.py
import datetime as dt

import pytest

from apps.catalog.models import Term
from apps.core.tests.factories import (
    CourseFactory,
    LearningOutcomeFactory,
    LOPOWeightFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
)
from apps.scoring.aggregates import MIN_PO_COVERAGE, _level, coverage_matrix

pytestmark = pytest.mark.django_db


@pytest.fixture
def program():
    program = ProgramFactory(code="TST")
    po_set = ProgramOutcomeSetFactory(program=program, label="2023", effective_from_year=2020, is_active=True)
    for n in (1, 2, 3):
        ProgramOutcomeFactory(po_set=po_set, number=n, short_name=f"Outcome {n}", description=f"PO {n} text")
    return program


def _po(program, number):
    return program.po_sets.get(is_active=True).outcomes.get(number=number)


def _term(code, year, status=Term.Status.CLOSED):
    return TermFactory(code=code, name=code, starts_on=dt.date(year, 9, 15),
                       ends_on=dt.date(year + 1, 1, 20), status=status)


def _link(offering, number, po, weight):
    lo = LearningOutcomeFactory(offering=offering, number=number, description=f"LO {number}")
    LOPOWeightFactory(learning_outcome=lo, program_outcome=po, weight=weight)
    return lo


def test_cells_sum_lo_weights_per_course_and_po(program):
    term = _term("2025F", 2025)
    a = OfferingFactory(course=CourseFactory(program=program, code="CSE 101"), term=term)
    b = OfferingFactory(course=CourseFactory(program=program, code="CSE 102"), term=term)
    _link(a, 1, _po(program, 1), 4)
    _link(a, 2, _po(program, 1), 3)
    _link(b, 1, _po(program, 2), 5)

    m = coverage_matrix(program, terms=[term])

    assert [r.course.code for r in m.rows] == ["CSE 101", "CSE 102"]
    assert [c.value for c in m.rows[0].cells] == [7, 0, 0]
    assert [c.value for c in m.rows[1].cells] == [0, 5, 0]
    assert [t.value for t in m.totals] == [7, 5, 0]
    assert m.max_cell == 7


def test_po_linked_by_no_course_is_flagged(program):  # T1.6 AC 2
    term = _term("2025F", 2025)
    off = OfferingFactory(course=CourseFactory(program=program, code="CSE 101"), term=term)
    _link(off, 1, _po(program, 1), 4)

    m = coverage_matrix(program, terms=[term])
    po3 = m.totals[2]

    assert po3.value == 0
    assert po3.flags == ("Not covered by any course",)
    assert po3 in m.flagged


def test_single_course_and_low_total_flags(program):
    term = _term("2025F", 2025)
    off = OfferingFactory(course=CourseFactory(program=program, code="CSE 101"), term=term)
    _link(off, 1, _po(program, 1), 2)

    flags = coverage_matrix(program, terms=[term]).totals[0].flags

    assert "Only 1 course" in flags
    assert f"Under-covered (total 2, below {MIN_PO_COVERAGE})" in flags


def test_well_covered_po_has_no_flags(program):
    term = _term("2025F", 2025)
    for code in ("CSE 101", "CSE 102"):
        off = OfferingFactory(course=CourseFactory(program=program, code=code), term=term)
        _link(off, 1, _po(program, 1), 3)

    assert coverage_matrix(program, terms=[term]).totals[0].flags == ()


def test_only_latest_offering_of_a_course_counts(program):
    old, new = _term("2024F", 2024), _term("2025F", 2025)
    course = CourseFactory(program=program, code="CSE 311")
    _link(OfferingFactory(course=course, term=old), 1, _po(program, 1), 5)
    _link(OfferingFactory(course=course, term=new), 1, _po(program, 1), 2)

    m = coverage_matrix(program, terms=[old, new])

    assert len(m.rows) == 1
    assert m.rows[0].offering.term == new
    assert m.totals[0].value == 2


def test_offerings_outside_the_terms_are_ignored(program):
    inside, outside = _term("2025F", 2025), _term("2023F", 2023)
    _link(OfferingFactory(course=CourseFactory(program=program, code="CSE 101"), term=outside),
          1, _po(program, 1), 5)

    m = coverage_matrix(program, terms=[inside])

    assert m.rows == ()
    assert all(t.flags == ("Not covered by any course",) for t in m.totals)


@pytest.mark.parametrize(("value", "max_cell", "level"),
                         [(0, 10, 0), (1, 10, 1), (3, 10, 2), (5, 10, 2), (6, 10, 3), (10, 10, 4), (4, 0, 0)])
def test_colour_level(value, max_cell, level):
    assert _level(value, max_cell) == level


def test_query_count_does_not_grow_with_courses(program, django_assert_max_num_queries):
    term = _term("2025F", 2025)
    for i in range(12):
        off = OfferingFactory(course=CourseFactory(program=program, code=f"CSE {100 + i}"), term=term)
        _link(off, 1, _po(program, 1 + i % 3), 3)

    with django_assert_max_num_queries(5):
        coverage_matrix(program, terms=[term])
```

```python
# apps/reports/tests/test_department_coverage.py
import datetime as dt

import pytest
from django.urls import reverse

from apps.catalog.models import Term
from apps.core.tests.factories import (
    CourseFactory,
    LearningOutcomeFactory,
    LOPOWeightFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def test_dashboard_shows_uncovered_po_flag(client):
    program = ProgramFactory(code="TST")
    po_set = ProgramOutcomeSetFactory(program=program, label="2023", effective_from_year=2020, is_active=True)
    po1 = ProgramOutcomeFactory(po_set=po_set, number=1, short_name="Maths", description="x")
    ProgramOutcomeFactory(po_set=po_set, number=2, short_name="Ethics", description="y")
    term = TermFactory(code="2025F", name="Fall 2025", starts_on=dt.date(2025, 9, 15),
                       ends_on=dt.date(2026, 1, 20), status=Term.Status.CLOSED)
    off = OfferingFactory(course=CourseFactory(program=program, code="CSE 101"), term=term)
    lo = LearningOutcomeFactory(offering=off, number=1, description="LO")
    LOPOWeightFactory(learning_outcome=lo, program_outcome=po1, weight=4)
    head = UserFactory()
    MembershipFactory(user=head, program=program, role="head")
    client.force_login(head)

    response = client.get(reverse("reports:department"))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Coverage heat map" in html
    assert "PO 2</strong> Ethics: Not covered by any course" in html
```

### Check it works

1. `uv run python manage.py seed_demo --reset`, then `uv run python manage.py runserver`.
2. Log in as the head (password printed by `seed_demo`) and open `/department/`.
3. The heat map lists 12 courses. The Total row shows **0 ⚠ under PO 11**. The list below the table says "PO 11 … Not covered by any course" and "PO 9 … Only 1 course". Those are the deliberate flaws from spec Appendix B.
4. Switch to dark mode (theme toggle). Cells are still readable, and the numbers are still visible on the darkest cells.
5. With the debug toolbar open, the SQL panel shows the heat map adding no more than 5 queries.

### Done when

- [ ] T1.6 AC 2 (PO with no course is flagged): `test_po_linked_by_no_course_is_flagged`, `test_dashboard_shows_uncovered_po_flag`
- [ ] Only the latest offering of each course counts: `test_only_latest_offering_of_a_course_counts`
- [ ] Query count is constant: `test_query_count_does_not_grow_with_courses`
- [ ] Colour is never the only signal: numbers in every cell, ⚠ plus text for flags (checked by eye in review)

### Commits and PR

```
Add coverage matrix aggregate with under-coverage flags (#S7-01)
Show coverage heat map on the department dashboard
Style heat map levels from the primary colour token
```
PR title: **S7-01 Coverage heat map with under-covered PO flags**

---

## S7-02 · Dashboard filters + completion panel

**Points:** 2 · **Owner:** Person C · **Branch:** `feature/S7-02-dashboard-filters` · **Depends on:** S7-01, S6-05, S3-04

### Goal

The head narrows the dashboard to a term range and a cohort, and switches "closed terms only" on and off (P10). The numbers update without a page reload, and the URL changes, so a filtered view can be bookmarked or pasted into a report. A completion panel shows the current term's offerings: how many assessments are published and whether the mapping is complete. The head can then see who still has work to do before reminder emails exist (T2.2). Delivers T1.6 "Filters" and "Completion panel", and B10 AC 2.

### Design choices

- **Filters live in the query string, not the session.** `?f=1&term_from=2025F&term_to=2026S&cohort=2023&closed_only=1` can be bookmarked, survives a reload, and the export button (S7-03) sends exactly the same parameters. The hidden `f=1` tells "the head submitted the form with the box unticked" apart from "first visit". HTML sends nothing at all for an unticked checkbox, so without `f` we couldn't tell the two apart.
- **Bad input falls back to the defaults instead of showing an error.** A stale bookmark naming a deleted term should still open the dashboard. The defaults are: earliest term → latest *closed* term, all cohorts, closed terms only. Accreditation numbers should only use final data (P10).
- **A reversed range is swapped.** "From 2026S to 2025F" means the same thing as the other order.
- **HTMX swaps one container.** The filter form has `hx-get` + `hx-trigger="change"` + `hx-push-url="true"`. The view returns the `dashboard_body` partial for HTMX requests and the whole page otherwise. This is the spec §8.5 "live validation" pattern applied to a GET. Without JavaScript the form still works, through its Apply button.
- **The completion panel always shows the current term** (the open term, or else the latest one), whatever the filters say. Its question is "who still has work to do now?", not a historical one.
- **The panel uses one annotated query, not `setup_status()` per offering.** `setup_status()` (S2-02) answers the same question for a single offering. Calling it 22 times would be 22 × 6 queries. `completion_rows()` gets the same facts in one query with subqueries, and a test proves the two agree.
- **The cohort filter needs one keyword added to two S6-05 functions** (step 4). That is the only change to earlier code.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/reports/filters.py` | create | `DashboardFilters`, `DashboardFilterForm` |
| `apps/reports/selectors.py` | modify | `completion_term()`, `CompletionRow`, `completion_rows()`, full `department_context()` |
| `apps/reports/views.py` | modify | full `department()` view |
| `apps/reports/templates/reports/department.html` | modify | full page: filter form, `dashboard_body`, `completion` partials |
| `apps/core/templatetags/polaris.py` | modify | `query_transform` (if S1-09 didn't already add it) |
| `apps/scoring/aggregates.py` | modify | `cohort=` keyword on `program_po_summary` and `attainment_matrix` |
| `apps/reports/tests/test_filters.py`, `test_completion.py`, `test_department_view.py` | create | tests |
| `apps/core/tests/test_query_transform.py` | create | tag test |

### Steps

**1. The filter object and form: `apps/reports/filters.py`.**

```python
# apps/reports/filters.py
"""Dashboard filters (T1.6). Parsed from the query string, never stored."""
from __future__ import annotations

from dataclasses import dataclass

from django import forms

from apps.accounts.models import ProgramMembership
from apps.catalog.models import Term


@dataclass(frozen=True)
class DashboardFilters:
    term_from: Term | None
    term_to: Term | None
    cohort: int | None
    closed_only: bool
    terms: tuple[Term, ...]   # the terms that pass every filter, oldest first

    def to_params(self) -> dict[str, str]:
        """The same filters as query-string / form values. Used by export buttons and stored on ExportJob."""
        return {
            "f": "1",
            "term_from": self.term_from.code if self.term_from else "",
            "term_to": self.term_to.code if self.term_to else "",
            "cohort": str(self.cohort) if self.cohort else "",
            "closed_only": "1" if self.closed_only else "",
        }

    @property
    def label(self) -> str:
        """Human description, printed on the page and on every export."""
        if self.term_from and self.term_to:
            span = (self.term_from.name if self.term_from == self.term_to
                    else f"{self.term_from.name} – {self.term_to.name}")
        elif self.term_from or self.term_to:
            span = f"from {self.term_from.name}" if self.term_from else f"up to {self.term_to.name}"
        else:
            span = "all terms"
        cohort = f"cohort {self.cohort}" if self.cohort else "all cohorts"
        closed = "closed terms only" if self.closed_only else "including open terms"
        return f"{span} · {cohort} · {closed}"

    @classmethod
    def from_params(cls, program, params) -> DashboardFilters:
        return DashboardFilterForm(params, program=program).filters()


class DashboardFilterForm(forms.Form):
    f = forms.CharField(widget=forms.HiddenInput, required=False, initial="1")
    term_from = forms.ChoiceField(label="From term", required=False)
    term_to = forms.ChoiceField(label="To term", required=False)
    cohort = forms.ChoiceField(label="Cohort", required=False)
    closed_only = forms.BooleanField(label="Closed terms only", required=False)

    def __init__(self, data=None, *, program):
        if data is not None and "f" not in data:
            data = None                      # first visit, or a link without filters: use defaults
        super().__init__(data)
        self.program = program
        self._terms = list(Term.objects.order_by("starts_on"))
        term_choices = [(t.code, t.name) for t in self._terms]
        self.fields["term_from"].choices = term_choices
        self.fields["term_to"].choices = term_choices
        cohorts = (ProgramMembership.objects
                   .filter(program=program, role=ProgramMembership.Role.STUDENT, cohort_year__isnull=False)
                   .values_list("cohort_year", flat=True).distinct().order_by("cohort_year"))
        self.fields["cohort"].choices = [("", "All cohorts")] + [(str(y), str(y)) for y in cohorts]
        for name, value in self._defaults().items():
            self.fields[name].initial = value
        for name in ("term_from", "term_to", "cohort"):
            self.fields[name].widget.attrs["class"] = "form-select form-select-sm"
        self.fields["closed_only"].widget.attrs["class"] = "form-check-input"

    def _defaults(self) -> dict:
        if not self._terms:
            return {"term_from": "", "term_to": "", "cohort": "", "closed_only": True}
        closed = [t for t in self._terms if t.status == Term.Status.CLOSED]
        return {
            "term_from": self._terms[0].code,
            "term_to": (closed or self._terms)[-1].code,
            "cohort": "",
            "closed_only": True,
        }

    def filters(self) -> DashboardFilters:
        values = self._defaults()
        if self.is_bound and self.is_valid():
            values.update({k: self.cleaned_data[k] for k in ("term_from", "term_to", "cohort", "closed_only")})
        by_code = {t.code: t for t in self._terms}
        start, end = by_code.get(values["term_from"]), by_code.get(values["term_to"])
        if start and end and start.starts_on > end.starts_on:
            start, end = end, start
        terms = [
            t for t in self._terms
            if (start is None or t.starts_on >= start.starts_on)
            and (end is None or t.starts_on <= end.starts_on)
            and (not values["closed_only"] or t.status == Term.Status.CLOSED)
        ]
        return DashboardFilters(
            term_from=start,
            term_to=end,
            cohort=int(values["cohort"]) if values["cohort"] else None,
            closed_only=bool(values["closed_only"]),
            terms=tuple(terms),
        )
```

A `ChoiceField` whose value is not in `choices` is invalid. An unknown term code therefore makes `is_valid()` false, and `filters()` quietly uses the defaults. That's the fallback described above, with no extra code.

**2. Selectors: `apps/reports/selectors.py`.**

Add these and replace `department_context` completely. The other functions in the file stay as they are.

```python
# apps/reports/selectors.py  (S7-02 additions; replaces department_context)
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Exists, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from apps.catalog.models import CourseOffering, Enrollment, Term
from apps.outcomes.models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight
from apps.scoring.aggregates import attainment_matrix, coverage_matrix, program_po_summary


def completion_term() -> Term | None:
    """The term instructors are working in now: the newest open term, else the newest term."""
    return (Term.objects.filter(status=Term.Status.OPEN).order_by("-starts_on").first()
            or Term.objects.order_by("-starts_on").first())


@dataclass(frozen=True)
class CompletionRow:
    offering: CourseOffering
    n_students: int
    n_assessments: int
    n_published: int
    has_los: bool
    has_assessment_lo: bool
    has_lo_po: bool

    @property
    def mapping_complete(self) -> bool:
        return self.has_los and self.has_assessment_lo and self.has_lo_po

    @property
    def fully_published(self) -> bool:
        return self.n_assessments > 0 and self.n_published == self.n_assessments

    @property
    def published_share(self) -> Decimal:
        if self.n_assessments == 0:
            return Decimal("0")
        return Decimal(self.n_published) / Decimal(self.n_assessments)


def _count(qs):
    """Correlated COUNT(*) subquery. `.order_by()` stops default ordering leaking into GROUP BY."""
    return Coalesce(
        Subquery(qs.order_by().values("offering").annotate(c=Count("id")).values("c"),
                 output_field=IntegerField()),
        Value(0),
    )


def completion_rows(program, term) -> list[CompletionRow]:
    """Setup and publishing status of every offering of `program` in `term`, in one query
    (plus one for instructors). Must agree with catalog.selectors.setup_status()."""
    assessments = Assessment.objects.filter(offering=OuterRef("pk"))
    offerings = (
        CourseOffering.objects.filter(course__program=program, term=term)
        .select_related("course", "term")
        .prefetch_related("instructors")
        .annotate(
            n_students=_count(Enrollment.objects.filter(offering=OuterRef("pk"),
                                                        status=Enrollment.Status.ENROLLED)),
            n_assessments=_count(assessments),
            n_published=_count(assessments.filter(published_at__isnull=False)),
            has_los=Exists(LearningOutcome.objects.filter(offering=OuterRef("pk"))),
            has_assessment_lo=Exists(AssessmentLOWeight.objects.filter(assessment__offering=OuterRef("pk"))),
            has_lo_po=Exists(LOPOWeight.objects.filter(learning_outcome__offering=OuterRef("pk"))),
        )
        .order_by("course__code", "section")
    )
    return [
        CompletionRow(
            offering=o, n_students=o.n_students, n_assessments=o.n_assessments, n_published=o.n_published,
            has_los=o.has_los, has_assessment_lo=o.has_assessment_lo, has_lo_po=o.has_lo_po,
        )
        for o in offerings
    ]


def department_context(program, *, terms, include_open_terms, cohort=None) -> dict:
    terms = list(terms)
    current = completion_term()
    completion = completion_rows(program, current) if current else []
    return {
        "program": program,
        "terms": terms,
        "po_summary": program_po_summary(program, terms=terms, include_open_terms=include_open_terms,
                                         cohort=cohort),
        "attainment": attainment_matrix(program, by="term" if cohort else "cohort", terms=terms,
                                        threshold=program.attainment_threshold, cohort=cohort),
        "coverage": coverage_matrix(program, terms=terms),
        "completion_term": current,
        "completion": completion,
        "completion_done": sum(1 for r in completion if r.fully_published),
    }
```

When a single cohort is chosen, the attainment table switches its columns from cohorts to terms (`by="term"`). A table with one cohort column would say nothing. Per term, it shows how that cohort's attainment moved.

**3. The view: `apps/reports/views.py`.**

```python
# apps/reports/views.py  (replaces department)
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.decorators import require_role

from .filters import DashboardFilterForm
from apps.accounts.permissions import head_program_or_404

from .selectors import department_context


@login_required
@require_role("head")
def department(request):
    program = head_program_or_404(request.user)
    form = DashboardFilterForm(request.GET, program=program)
    filters = form.filters()
    context = department_context(
        program,
        terms=filters.terms,
        include_open_terms=not filters.closed_only,
        cohort=filters.cohort,
    )
    context |= {"form": form, "filters": filters}
    template = "reports/department.html#dashboard_body" if request.htmx else "reports/department.html"
    return render(request, template, context)
```

**4. The cohort keyword in `apps/scoring/aggregates.py` (S6-05 functions).**

Add `cohort: int | None = None` as the last keyword-only parameter of both `program_po_summary` and `attainment_matrix`. In each function, find the queryset that selects the program's students (the S6-05 code filters `ProgramMembership` by `program` and `role="student"`) and add this right after it:

```python
    if cohort is not None:
        students = students.filter(cohort_year=cohort)
```

If your variable has a different name, filter that queryset instead. The rule is the same: when a cohort is chosen, only students whose `ProgramMembership.cohort_year` equals it count, in both the numerator and the denominator of every rate. Add one test per function in the S6-05 test file: two students in different cohorts, filter on one, assert that only that student's score is counted.

**5. `query_transform` in `apps/core/templatetags/polaris.py`.**

If S1-09 already added it, check that it behaves like this. Otherwise add it.

```python
# apps/core/templatetags/polaris.py  (addition)
@register.simple_tag(takes_context=True)
def query_transform(context, **changes):
    """Current query string with some keys changed. A value of None or "" removes the key.
    {% query_transform page=2 %} → "?f=1&term_from=2025F&page=2" """
    params = context["request"].GET.copy()
    for key, value in changes.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"
```

It returns `"?"` and never an empty string, because `href=""` would link to the current URL *with* its old query string.

**6. The template: `apps/reports/templates/reports/department.html`.**

This is the full file. The `attainment` partial from S6-05 and the `coverage` partial from S7-01 stay where they are, at the bottom, and are rendered by name. Section order follows the spec §8.4 wireframe.

```django
{% extends "base.html" %}
{% load polaris %}
{% block title %}Department · {{ program.code }}{% endblock %}

{% block content %}
<div class="d-flex flex-wrap justify-content-between align-items-end gap-2 mb-3">
  <h1 class="h3 mb-0">Department · {{ program.code }}</h1>
  <form method="get" action="{% url 'reports:department' %}" class="d-flex flex-wrap align-items-end gap-2"
        aria-label="Dashboard filters"
        hx-get="{% url 'reports:department' %}" hx-trigger="change" hx-target="#dashboard-body"
        hx-swap="outerHTML" hx-push-url="true">
    {{ form.f }}
    <div>
      <label for="{{ form.term_from.id_for_label }}" class="form-label small mb-0">{{ form.term_from.label }}</label>
      {{ form.term_from }}
    </div>
    <div>
      <label for="{{ form.term_to.id_for_label }}" class="form-label small mb-0">{{ form.term_to.label }}</label>
      {{ form.term_to }}
    </div>
    <div>
      <label for="{{ form.cohort.id_for_label }}" class="form-label small mb-0">{{ form.cohort.label }}</label>
      {{ form.cohort }}
    </div>
    <div class="form-check mb-1">
      {{ form.closed_only }}
      <label for="{{ form.closed_only.id_for_label }}" class="form-check-label small">{{ form.closed_only.label }}</label>
    </div>
    <button type="submit" class="btn btn-sm btn-outline-secondary">Apply</button>
  </form>
</div>

{% partial dashboard_body %}
{% endblock %}

{% partialdef dashboard_body %}
<div id="dashboard-body">
  <p class="small text-body-secondary mb-3" role="status">
    Showing {{ filters.label }}.
    {% if filters.closed_only %}
      <a href="{% query_transform f=1 closed_only='' %}">Include open terms</a>
    {% else %}
      <a href="{% query_transform f=1 closed_only=1 %}">Closed terms only</a>
    {% endif %}
    · <a href="{% url 'reports:department' %}">Reset filters</a>
  </p>

  {% partial attainment %}
  {% partial coverage %}
  {% partial completion %}

  <div class="d-flex gap-2 mb-4" id="export-area">
    {# S7-03 fills this with the export buttons #}
  </div>
</div>
{% endpartialdef %}

{% partialdef completion %}
<section class="card mb-4" aria-labelledby="completion-title">
  <div class="card-body">
    {% if completion_term %}
      <h2 id="completion-title" class="h5">
        {{ completion_term.name }} completion: {{ completion_done }}/{{ completion|length }} courses fully published
      </h2>
      {% if not completion %}
        {% include "includes/empty_state.html" with title="No offerings this term" message="Create offerings under Catalog → Offerings." only %}
      {% else %}
        <div class="table-responsive">
          <table class="table table-sm align-middle mb-0">
            <caption class="visually-hidden">Setup and publishing status of each offering in {{ completion_term.name }}</caption>
            <thead>
              <tr>
                <th scope="col">Course</th>
                <th scope="col">Instructors</th>
                <th scope="col" class="text-end">Students</th>
                <th scope="col">Published</th>
                <th scope="col">Mapping</th>
              </tr>
            </thead>
            <tbody>
              {% for row in completion %}
                <tr>
                  <th scope="row"><a href="{% url 'catalog:offering' row.offering.pk %}">{{ row.offering.course.code }}</a>
                    {% if row.offering.section != "1" %}<span class="text-body-secondary">§{{ row.offering.section }}</span>{% endif %}</th>
                  <td>{% for person in row.offering.instructors.all %}{{ person.get_full_name }}{% if not forloop.last %}, {% endif %}{% empty %}<span class="text-danger">None assigned</span>{% endfor %}</td>
                  <td class="text-end num">{{ row.n_students }}</td>
                  <td>
                    <div class="d-flex align-items-center gap-2">
                      <div class="progress flex-grow-1" style="height: .5rem" role="progressbar"
                           aria-label="Assessments published" aria-valuenow="{{ row.n_published }}" aria-valuemin="0" aria-valuemax="{{ row.n_assessments }}">
                        <div class="progress-bar{% if row.fully_published %} bg-success{% endif %}" style="width: {{ row.published_share|pct }}"></div>
                      </div>
                      <span class="small num text-nowrap">{{ row.n_published }}/{{ row.n_assessments }}</span>
                    </div>
                  </td>
                  <td>
                    {% if row.mapping_complete %}<span class="text-success">✓ Complete</span>
                    {% else %}<span class="text-danger">✗ Incomplete</span>{% endif %}
                  </td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      {% endif %}
    {% else %}
      <h2 id="completion-title" class="h5">Completion</h2>
      {% include "includes/empty_state.html" with title="No terms yet" message="Create a term under Catalog → Terms." only %}
    {% endif %}
  </div>
</section>
{% endpartialdef %}

{# partialdef attainment (S6-05) and partialdef coverage (S7-01) stay below, unchanged #}
```

`pct` is the existing filter from spec §4.8: 0..1 → "83%". It works as a CSS width because CSS accepts `83%`.

`{% partial name %}` renders a partial defined anywhere in the same file. The HTMX response for a filter change is only `#dashboard-body`, which includes all three panels, so every number changes together.

### Tests

```python
# apps/reports/tests/test_filters.py
import datetime as dt

import pytest
from django.http import QueryDict

from apps.catalog.models import Term
from apps.core.tests.factories import MembershipFactory, ProgramFactory, TermFactory
from apps.reports.filters import DashboardFilterForm, DashboardFilters

pytestmark = pytest.mark.django_db


@pytest.fixture
def terms():
    Term.objects.all().delete()   # the seed migration creates none, but be explicit
    def make(code, name, year, month, status):
        return TermFactory(code=code, name=name, starts_on=dt.date(year, month, 1),
                           ends_on=dt.date(year, month + 3, 28), status=status)
    return [
        make("2025F", "Fall 2025", 2025, 9, Term.Status.CLOSED),
        make("2026S", "Spring 2026", 2026, 2, Term.Status.CLOSED),
        make("2026F", "Fall 2026", 2026, 9, Term.Status.OPEN),
    ]


@pytest.fixture
def program():
    program = ProgramFactory(code="TST")
    for year in (2023, 2024):
        MembershipFactory(program=program, role="student", cohort_year=year)
    return program


def test_defaults_on_first_visit(terms, program):
    filters = DashboardFilterForm(QueryDict(""), program=program).filters()

    assert filters.term_from.code == "2025F"
    assert filters.term_to.code == "2026S"           # latest CLOSED term
    assert filters.closed_only is True
    assert filters.cohort is None
    assert [t.code for t in filters.terms] == ["2025F", "2026S"]


def test_unticked_closed_only_includes_open_terms(terms, program):
    qd = QueryDict("f=1&term_from=2025F&term_to=2026F&cohort=")
    filters = DashboardFilterForm(qd, program=program).filters()

    assert filters.closed_only is False
    assert [t.code for t in filters.terms] == ["2025F", "2026S", "2026F"]


def test_reversed_range_is_swapped(terms, program):
    qd = QueryDict("f=1&term_from=2026S&term_to=2025F&closed_only=1")
    filters = DashboardFilterForm(qd, program=program).filters()

    assert (filters.term_from.code, filters.term_to.code) == ("2025F", "2026S")


def test_unknown_term_falls_back_to_defaults(terms, program):
    qd = QueryDict("f=1&term_from=1999F&term_to=2026F")
    filters = DashboardFilterForm(qd, program=program).filters()

    assert filters.term_to.code == "2026S"
    assert filters.closed_only is True


def test_cohort_choices_and_parsing(terms, program):
    form = DashboardFilterForm(QueryDict("f=1&cohort=2024&closed_only=1"), program=program)

    assert [c[0] for c in form.fields["cohort"].choices] == ["", "2023", "2024"]
    assert form.filters().cohort == 2024


def test_params_round_trip(terms, program):
    original = DashboardFilterForm(QueryDict("f=1&term_from=2025F&term_to=2026F&cohort=2023"),
                                   program=program).filters()
    again = DashboardFilters.from_params(program, original.to_params())

    assert again == original
    assert "including open terms" in original.label
```

```python
# apps/reports/tests/test_completion.py
import datetime as dt

import pytest
from django.utils import timezone

from apps.catalog.models import Term
from apps.catalog.selectors import setup_status
from apps.core.tests.factories import (
    AssessmentFactory,
    AssessmentLOWeightFactory,
    CourseFactory,
    EnrollmentFactory,
    LearningOutcomeFactory,
    LOPOWeightFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
)
from apps.reports.selectors import completion_rows, completion_term

pytestmark = pytest.mark.django_db


@pytest.fixture
def setting():
    program = ProgramFactory(code="TST")
    po_set = ProgramOutcomeSetFactory(program=program, label="2023", effective_from_year=2020, is_active=True)
    po = ProgramOutcomeFactory(po_set=po_set, number=1, short_name="Maths", description="x")
    term = TermFactory(code="2026F", name="Fall 2026", starts_on=dt.date(2026, 9, 14),
                       ends_on=dt.date(2027, 1, 22), status=Term.Status.OPEN)
    complete = OfferingFactory(course=CourseFactory(program=program, code="CSE 101"), term=term)
    lo = LearningOutcomeFactory(offering=complete, number=1, description="LO 1")
    mid = AssessmentFactory(offering=complete, name="Midterm", kind="midterm", published_at=timezone.now())
    AssessmentFactory(offering=complete, name="Final", kind="final")
    AssessmentLOWeightFactory(assessment=mid, learning_outcome=lo, weight=100)
    LOPOWeightFactory(learning_outcome=lo, program_outcome=po, weight=3)
    for _ in range(3):
        EnrollmentFactory(offering=complete)
    EnrollmentFactory(offering=complete, status="dropped")
    empty = OfferingFactory(course=CourseFactory(program=program, code="CSE 102"), term=term)
    return program, term, complete, empty


def test_counts_and_flags(setting):
    program, term, complete, empty = setting
    rows = {r.offering.pk: r for r in completion_rows(program, term)}

    a = rows[complete.pk]
    assert (a.n_students, a.n_assessments, a.n_published) == (3, 2, 1)
    assert a.mapping_complete is True
    assert a.fully_published is False
    assert str(a.published_share) == "0.5"

    b = rows[empty.pk]
    assert (b.n_students, b.n_assessments, b.n_published) == (0, 0, 0)
    assert b.mapping_complete is False
    assert b.fully_published is False


def test_agrees_with_setup_status(setting):
    program, term, *_ = setting
    for row in completion_rows(program, term):
        status = setup_status(row.offering)
        assert row.has_los == status.has_los
        assert row.has_assessment_lo == status.has_assessment_lo
        assert row.has_lo_po == status.has_lo_po
        assert row.n_published == status.published_count
        assert row.n_assessments == status.assessment_count


def test_query_count_is_constant(setting, django_assert_max_num_queries):
    program, term, *_ = setting
    for i in range(10):
        OfferingFactory(course=CourseFactory(program=program, code=f"CSE {200 + i}"), term=term)

    with django_assert_max_num_queries(2):   # offerings + prefetched instructors
        rows = completion_rows(program, term)
        [list(r.offering.instructors.all()) for r in rows]


def test_completion_term_prefers_open_term(setting):
    TermFactory(code="2026S", name="Spring 2026", starts_on=dt.date(2026, 2, 9),
                ends_on=dt.date(2026, 6, 5), status=Term.Status.CLOSED)

    assert completion_term().code == "2026F"
```

```python
# apps/reports/tests/test_department_view.py
import datetime as dt

import pytest
from django.urls import reverse

from apps.catalog.models import Term
from apps.core.tests.factories import (
    MembershipFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def head_client(client):
    program = ProgramFactory(code="TST")
    po_set = ProgramOutcomeSetFactory(program=program, label="2023", effective_from_year=2020, is_active=True)
    ProgramOutcomeFactory(po_set=po_set, number=1, short_name="Maths", description="x")
    TermFactory(code="2025F", name="Fall 2025", starts_on=dt.date(2025, 9, 15),
                ends_on=dt.date(2026, 1, 20), status=Term.Status.CLOSED)
    TermFactory(code="2026F", name="Fall 2026", starts_on=dt.date(2026, 9, 14),
                ends_on=dt.date(2027, 1, 22), status=Term.Status.OPEN)
    head = UserFactory()
    MembershipFactory(user=head, program=program, role="head")
    client.force_login(head)
    return client


def test_full_page_shows_filters_and_default_label(head_client):
    html = head_client.get(reverse("reports:department")).content.decode()

    assert 'aria-label="Dashboard filters"' in html
    assert "Showing Fall 2025 · all cohorts · closed terms only." in html
    assert "Fall 2026 completion:" in html


def test_htmx_request_returns_only_the_body(head_client):
    response = head_client.get(reverse("reports:department"), {"f": "1", "term_from": "2025F",
                                                              "term_to": "2026F"},
                               headers={"HX-Request": "true"})
    html = response.content.decode()

    assert html.lstrip().startswith('<div id="dashboard-body">')
    assert "<html" not in html
    assert "including open terms" in html


def test_student_cannot_open_dashboard(client):
    student = UserFactory()
    MembershipFactory(user=student, role="student", cohort_year=2024)
    client.force_login(student)

    assert client.get(reverse("reports:department")).status_code == 404
```

```python
# apps/core/tests/test_query_transform.py
from django.template import Context, Template
from django.test import RequestFactory


def render(qs, tag):
    request = RequestFactory().get("/department/?" + qs)
    return Template("{% load polaris %}" + tag).render(Context({"request": request}))


def test_changes_one_key_and_keeps_the_rest():
    assert render("f=1&cohort=2023&page=3", "{% query_transform page=4 %}") == "?f=1&amp;cohort=2023&amp;page=4"


def test_empty_value_removes_key():
    assert render("f=1&closed_only=1", "{% query_transform closed_only='' %}") == "?f=1"


def test_never_returns_empty_string():
    assert render("page=2", "{% query_transform page=None %}") == "?"
```

(The `&amp;` in the first assertion is correct. A `simple_tag` result is auto-escaped, and `&amp;` inside an `href` is exactly what valid HTML needs. Browsers decode it.)

### Check it works

1. With `seed_demo` data, open `/department/` as the head. The label says "Fall 2025 – Spring 2026 · all cohorts · closed terms only".
2. Change *Cohort* to 2023. The body re-renders without a full reload: the network tab shows one request with an `HX-Request` header. The URL now ends in `&cohort=2023`, and the attainment table has term columns.
3. Click **Include open terms**. The label and the numbers change (B10 AC 2). Reload the page: the same filters are still applied.
4. Paste `/department/?f=1&term_from=1999X` into the address bar. The dashboard opens with the defaults and no error.
5. The completion panel reads "Fall 2026 completion: N/12 courses fully published". The offering seeded with no mapping shows "✗ Incomplete".

### Done when

- [ ] T1.6 filters (term range, cohort, closed-only): `test_filters.py`
- [ ] B10 AC 2 (toggle changes numbers and label): `test_unticked_closed_only_includes_open_terms`, `test_htmx_request_returns_only_the_body`
- [ ] Completion panel matches `setup_status`: `test_agrees_with_setup_status`
- [ ] Constant query count: `test_query_count_is_constant`
- [ ] Students get 404: `test_student_cannot_open_dashboard`
- [ ] Cohort filter tests added to the S6-05 aggregate tests (step 4)

### Commits and PR

```
Parse dashboard filters from the query string with safe defaults
Add one-query completion panel for the current term
Filter attainment and PO summary by cohort
Swap dashboard body with HTMX when filters change
```
PR title: **S7-02 Dashboard filters, bookmarkable URLs and completion panel**

---

## S7-03 · Exports: course and department reports as PDF and Excel

**Points:** 5 · **Owner:** Person A · **Branch:** `feature/S7-03-exports` · **Depends on:** S3-03 (course results), S7-02 (`DashboardFilters`), S5-02 (Celery worker)

### Goal

The head and instructors take numbers out of POlaris: a **course report** (instructor or head) and a **department report** (head), each as PDF or Excel. Building a PDF takes a few seconds, so it runs in the Celery worker. The page shows "Building…" and turns into a Download button when the file is ready. Every number in an export is produced by the same selector that draws the screen, so the two can't disagree. The department report reads the whole database from one consistent snapshot (REPEATABLE READ), which is a CSE 321 talking point. Delivers T1.7, AC 1 and 2, and the `ExportJob` model from spec §5.2.

### How it works

```
  [Export PDF] ──POST──► view ──► services.request_export() ──► ExportJob(PENDING)
                                        │ on_commit
                                        ▼
                              Celery: tasks.build_export(id)
                                        │  RUNNING
                                        ▼
                       repeatable_read_snapshot():           ◄── one consistent view of the DB
                         exports.render_*()  ── context from the SAME selector as the screen
                                        │
                                        ▼
                         file saved to media/exports/…, DONE
  browser: status partial polls every 2 s ──► "Download PDF"  ──GET ?download=1──► FileResponse
```

### Design choices

- **Same context, different template.** The course export calls `course_results_context(offering)`, the selector behind `/offerings/<id>/results/`. The department export calls `department_context(...)`, the selector behind `/department/`. Both print numbers through `|score` and `|pct`. AC 1 ("every number in the PDF equals the same number on screen") holds by construction, and a test checks it.
- **We test the HTML, not the PDF bytes.** WeasyPrint turns HTML into PDF. Pulling text back out of a PDF would need a library we don't otherwise use. So `render_course_html()` is separate from `html_to_pdf()`, the number test runs on the HTML, and one smaller test checks that real PDF bytes come out.
- **REPEATABLE READ for exports.** PostgreSQL's default, READ COMMITTED, gives each *statement* a fresh snapshot. A department export runs about 15 queries. If an instructor publishes grades between query 3 and query 9, the attainment table and the PO summary in the same PDF would describe different worlds. With REPEATABLE READ, every statement in the transaction sees the snapshot taken at the first query (spec §5.6). We use it for course exports too, because it costs nothing for a read-only transaction.
- **`SET TRANSACTION` must be the first statement of the transaction.** Inside an outer `atomic()` (for example a pytest-django test without `transaction=True`), the transaction has already started, so the level can't change. Our helper detects that, skips the `SET`, and leaves a comment saying why, rather than crashing the test suite. The isolation test uses `transaction=True` so it can check the real thing.
- **Excel cells are numbers, rounded like the screen.** Scores are written as `Decimal` values quantized to one decimal (half-up), with number format `0.0`. Rates are written as fractions with format `0%`. Excel then sorts and sums them as numbers (AC 2), and they read the same as the screen.
- **Only the creator can download, and files are deleted after 7 days.** An export can contain student scores. `export_for_user` returns 404 for anyone else. A Celery **beat** schedule runs `purge_old_exports` nightly. We add the beat container now, and T2.2's reminder emails reuse it in Sprint 8.
- **Fonts.** The slim Python image may not have any fonts, and WeasyPrint needs one that has Turkish letters (ğ, ş, ı, İ). We install `fonts-dejavu-core` explicitly.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/reports/models.py` | create | `ExportJob`, copied from spec §5.2, then `makemigrations reports` |
| `apps/reports/admin.py` | modify | register `ExportJob` (read-only list) |
| `apps/reports/snapshot.py` | create | `repeatable_read_snapshot()` |
| `apps/reports/exports.py` | create | contexts, HTML/PDF/XLSX renderers, `render_export(job)` |
| `apps/reports/services.py` | create | `request_export()` |
| `apps/reports/tasks.py` | create | `build_export`, `purge_old_exports` |
| `apps/reports/selectors.py` | modify | `export_for_user()` |
| `apps/reports/views.py` | modify | `course_export`, `department_export`, `export_status` |
| `apps/reports/urls.py` | modify | the three routes from §4.8 |
| `apps/reports/templates/reports/export_status.html` | create | page + `status` partial |
| `apps/reports/templates/reports/includes/export_buttons.html` | create | the two buttons |
| `apps/reports/templates/reports/pdf/_print.css` | create | print stylesheet (included inline) |
| `apps/reports/templates/reports/pdf/course.html`, `department.html` | create | PDF templates |
| `apps/reports/templates/reports/department.html`, `course_results.html` | modify | add the export buttons |
| `config/settings/base.py` | modify | `CELERY_BEAT_SCHEDULE` |
| `compose.prod.yml`, `Dockerfile` | modify | `beat` service; `fonts-dejavu-core` |
| `apps/reports/tests/test_exports.py`, `test_export_views.py`, `test_snapshot.py` | create | tests |
| `apps/accounts/tests/test_permission_matrix.py` | modify | three new URLs |

### Steps

**1. The model.** Copy `ExportJob` exactly as written in spec §5.2 into `apps/reports/models.py`, then:

```bash
uv run python manage.py makemigrations reports
uv run python manage.py migrate
```

Register it read-only in the admin, so we can see failures on staging:

```python
# apps/reports/admin.py
from django.contrib import admin

from .models import ExportJob


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "fmt", "status", "created_by", "created_at", "finished_at")
    list_filter = ("kind", "fmt", "status")
    readonly_fields = [f.name for f in ExportJob._meta.fields]

    def has_add_permission(self, request):
        return False
```

**2. The snapshot helper: `apps/reports/snapshot.py`.**

```python
# apps/reports/snapshot.py
"""One consistent view of the database for multi-query reads (spec §5.6)."""
from contextlib import contextmanager

from django.db import connection, transaction


@contextmanager
def repeatable_read_snapshot():
    """Run the block in a REPEATABLE READ transaction: every query sees the data as it was
    at the first query, whatever other users commit meanwhile.

    If we're already inside a transaction (a caller's atomic(), or a normal pytest-django
    test), PostgreSQL won't let us change the level any more. We then just run the block
    inside a savepoint, at the level that transaction already has."""
    if connection.in_atomic_block:
        with transaction.atomic():
            yield
        return
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        yield
```

The `SET` really is the first statement. When an outermost `atomic()` starts, Django turns autocommit off but sends no query. PostgreSQL starts the transaction at the next statement, which is our `SET`.

**3. Renderers: `apps/reports/exports.py`.**

```python
# apps/reports/exports.py
"""Course and department reports as HTML→PDF (WeasyPrint) and Excel (openpyxl).
Numbers come from the same selectors as the screens (T1.7 AC 1)."""
from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.styles import Font

from apps.catalog.models import ProgramOutcome
from apps.outcomes.lint import run_lint
from apps.outcomes.models import LearningOutcome
from apps.outcomes.selectors import mapping_grid, snapshot_mapping

from .filters import DashboardFilters
from .models import ExportJob
from .selectors import course_results_context, department_context
from .snapshot import repeatable_read_snapshot

ONE_DP = Decimal("0.1")
SCORE_FORMAT = "0.0"
RATE_FORMAT = "0%"


# ---------- contexts ----------

@dataclass(frozen=True)
class LOStat:
    lo: LearningOutcome
    mean: Decimal | None
    n_scored: int


@dataclass(frozen=True)
class POContribution:
    po: ProgramOutcome
    score: Decimal | None


def course_export_context(offering) -> dict:
    context = course_results_context(offering)          # the results page's own numbers
    summary = context["summary"]
    grid = mapping_grid(offering)
    lo_stats = [
        LOStat(
            lo=lo,
            mean=summary.class_mean.get(lo.id),
            n_scored=sum(1 for row in summary.rows
                         if (ns := row.scores.get(lo.id)) is not None and ns.score is not None),
        )
        for lo in summary.los
    ]
    context.update({
        "offering": offering,
        "instructors": list(offering.instructors.all()),
        "lo_stats": lo_stats,
        "po_contributions": [POContribution(po, summary.po_contribution.get(po.id)) for po in grid.pos],
        "grid": grid,
        "a_lo_rows": [(a, [grid.a_lo.get((a.id, lo.id)) for lo in grid.los]) for a in grid.assessments],
        "lo_po_rows": [(lo, [grid.lo_po.get((lo.id, po.id)) for po in grid.pos]) for lo in grid.los],
        "lint": run_lint(snapshot_mapping(offering)),
        "generated_at": timezone.localtime(),
    })
    return context


def department_export_context(program, filters: DashboardFilters) -> dict:
    context = department_context(program, terms=filters.terms,
                                 include_open_terms=not filters.closed_only, cohort=filters.cohort)
    context.update({"filters": filters, "generated_at": timezone.localtime()})
    return context


# ---------- HTML and PDF ----------

def render_course_html(offering) -> str:
    return render_to_string("reports/pdf/course.html", course_export_context(offering))


def render_department_html(program, filters: DashboardFilters) -> str:
    return render_to_string("reports/pdf/department.html", department_export_context(program, filters))


def html_to_pdf(html: str) -> bytes:
    # Imported here, not at module level: WeasyPrint needs Pango system libraries, which the
    # Docker image has but a teammate's laptop may not. Everything else in this module still imports.
    from weasyprint import HTML

    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()


def render_course_pdf(offering) -> bytes:
    return html_to_pdf(render_course_html(offering))


def render_department_pdf(program, filters: DashboardFilters) -> bytes:
    return html_to_pdf(render_department_html(program, filters))


# ---------- Excel ----------

def _num(value: Decimal | None) -> Decimal | None:
    """Same rounding as the |score filter, but kept numeric for Excel."""
    return None if value is None else value.quantize(ONE_DP, rounding=ROUND_HALF_UP)


def _sheet(wb: Workbook, title: str, header: list, rows: list[list], formats: dict[int, str] | None = None):
    ws = wb.create_sheet(title=title)
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append(row)
    for col_index, fmt in (formats or {}).items():
        for (cell,) in ws.iter_rows(min_row=2, min_col=col_index + 1, max_col=col_index + 1):
            if cell.value is not None:
                cell.number_format = fmt
    for column in ws.columns:
        width = max((len(str(c.value)) for c in column if c.value is not None), default=8)
        ws.column_dimensions[column[0].column_letter].width = min(60, max(8, width + 2))
    ws.freeze_panes = "A2"
    return ws


def _workbook_bytes(wb: Workbook) -> bytes:
    del wb[wb.sheetnames[0]]          # the empty default sheet openpyxl creates
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def render_course_xlsx(offering) -> bytes:
    c = course_export_context(offering)
    wb = Workbook()
    _sheet(wb, "Course", ["Field", "Value"], [
        ["Course", f"{offering.course.code} {offering.course.title}"],
        ["Term", offering.term.name],
        ["Section", offering.section],
        ["Instructors", ", ".join(u.get_full_name() for u in c["instructors"])],
        ["Mapping problems", len(c["lint"])],
        ["Generated", c["generated_at"].strftime("%Y-%m-%d %H:%M")],
    ])
    _sheet(wb, "LO statistics", ["LO", "Description", "Class average", "Students with a score"],
           [[f"LO {s.lo.number}", s.lo.description, _num(s.mean), s.n_scored] for s in c["lo_stats"]],
           {2: SCORE_FORMAT})
    _sheet(wb, "PO contribution", ["PO", "Outcome", "Course contribution score"],
           [[f"PO {p.po.number}", p.po.short_name, _num(p.score)] for p in c["po_contributions"]],
           {2: SCORE_FORMAT})
    grid = c["grid"]
    _sheet(wb, "Assessment-LO weights", ["Assessment"] + [f"LO {lo.number}" for lo in grid.los],
           [[a.name, *values] for a, values in c["a_lo_rows"]])
    _sheet(wb, "LO-PO weights", ["LO"] + [f"PO {po.number}" for po in grid.pos],
           [[f"LO {lo.number}", *values] for lo, values in c["lo_po_rows"]])
    _sheet(wb, "Mapping check", ["Code", "Severity", "Message"],
           [[i.code, i.severity, i.message] for i in c["lint"]])
    return _workbook_bytes(wb)


def render_department_xlsx(program, filters: DashboardFilters) -> bytes:
    c = department_export_context(program, filters)
    wb = Workbook()
    _sheet(wb, "About", ["Field", "Value"], [
        ["Program", f"{program.code} {program.name}"],
        ["Filters", filters.label],
        ["Attainment threshold", _num(program.attainment_threshold)],
        ["Generated", c["generated_at"].strftime("%Y-%m-%d %H:%M")],
    ])
    _sheet(wb, "PO summary", ["PO", "Outcome", "Average score", "Students with evidence", "Attainment rate"],
           [[f"PO {s.po.number}", s.po.short_name, _num(s.mean), s.n_with_evidence, s.attainment_rate]
            for s in c["po_summary"]],
           {2: SCORE_FORMAT, 4: RATE_FORMAT})
    attainment = c["attainment"]
    _sheet(wb, "Attainment", ["PO"] + list(attainment.columns),
           [[f"PO {row.po.number}", *row.cells] for row in attainment.rows],
           {i: RATE_FORMAT for i in range(1, len(attainment.columns) + 1)})
    coverage = c["coverage"]
    _sheet(wb, "Coverage", ["Course"] + [f"PO {po.number}" for po in coverage.pos],
           [[row.course.code, *[cell.value for cell in row.cells]] for row in coverage.rows]
           + [["Total", *[t.value for t in coverage.totals]],
              ["Flags", *["; ".join(t.flags) for t in coverage.totals]]])
    _sheet(wb, f"Completion {c['completion_term'].code}" if c["completion_term"] else "Completion",
           ["Course", "Section", "Students", "Assessments", "Published", "Mapping complete"],
           [[r.offering.course.code, r.offering.section, r.n_students, r.n_assessments, r.n_published,
             "yes" if r.mapping_complete else "no"] for r in c["completion"]])
    return _workbook_bytes(wb)


# ---------- dispatcher used by the Celery task ----------

def render_export(job: ExportJob) -> tuple[bytes, str]:
    """Build the file for `job`. Returns (content, filename). Runs inside one snapshot."""
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    with repeatable_read_snapshot():
        if job.kind == ExportJob.Kind.COURSE:
            offering = job.offering
            content = (render_course_pdf(offering) if job.fmt == ExportJob.Format.PDF
                       else render_course_xlsx(offering))
            name = f"{slugify(offering.course.code)}-{offering.term.code}-{stamp}.{job.fmt}"
        elif job.kind == ExportJob.Kind.DEPARTMENT:
            filters = DashboardFilters.from_params(job.program, job.params)
            content = (render_department_pdf(job.program, filters) if job.fmt == ExportJob.Format.PDF
                       else render_department_xlsx(job.program, filters))
            name = f"{slugify(job.program.code)}-department-{stamp}.{job.fmt}"
        else:
            raise ValueError(f"Export kind {job.kind!r} is built by its own story (T2.4)")
    return content, name
```

`openpyxl` stores a `Decimal` as a numeric cell. That's what AC 2 needs: Excel sees `86.0`, not the text `"86.0"`. Never write `str(value)` into a sheet.

**4. Service and task.**

```python
# apps/reports/services.py
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import ExportJob
from .tasks import build_export


def request_export(user, *, kind, fmt, offering=None, program=None, params=None) -> ExportJob:
    """Create an export job and queue it once the row is committed."""
    if fmt not in ExportJob.Format.values:
        raise ValidationError("Unknown export format.")
    if kind == ExportJob.Kind.COURSE and offering is None:
        raise ValidationError("A course export needs an offering.")
    if kind == ExportJob.Kind.DEPARTMENT and program is None:
        raise ValidationError("A department export needs a program.")
    with transaction.atomic():
        job = ExportJob.objects.create(kind=kind, fmt=fmt, offering=offering, program=program,
                                       params=params or {}, created_by=user)
        transaction.on_commit(lambda: build_export.delay(job.pk))
    return job
```

```python
# apps/reports/tasks.py
import logging
from datetime import timedelta

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import ExportJob

logger = logging.getLogger(__name__)


@shared_task
def build_export(export_id: int) -> str:
    """Render one ExportJob. Idempotent: a job that is already DONE is left alone, so a
    redelivered message (acks_late) does no harm."""
    from .exports import render_export   # avoid importing WeasyPrint/openpyxl when Celery autodiscovers tasks

    job = ExportJob.objects.select_related("offering__course", "offering__term", "program").get(pk=export_id)
    if job.status == ExportJob.Status.DONE:
        return job.status
    job.status = ExportJob.Status.RUNNING
    job.save(update_fields=["status"])
    try:
        content, filename = render_export(job)
    except Exception as exc:  # any failure must end in FAILED, never a job stuck in RUNNING
        logger.exception("Export %s failed", job.pk)
        job.status = ExportJob.Status.FAILED
        job.error = f"{type(exc).__name__}: {exc}"[:2000]
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at"])
        return job.status
    job.file.save(filename, ContentFile(content), save=False)
    job.status = ExportJob.Status.DONE
    job.finished_at = timezone.now()
    job.save(update_fields=["file", "status", "finished_at"])
    return job.status


@shared_task
def purge_old_exports(days: int = 7) -> int:
    """Delete export files and rows older than `days`. Scheduled nightly by Celery beat."""
    cutoff = timezone.now() - timedelta(days=days)
    old = ExportJob.objects.filter(created_at__lt=cutoff)
    count = 0
    for job in old.iterator():
        if job.file:
            job.file.delete(save=False)
        count += 1
    old.delete()
    return count
```

`job.error` holds the technical message for us (Django admin). The user only ever sees "We couldn't build this report" (step 7). Error details can leak internals, so they don't go on the page.

**5. Schedule and containers.**

Add `from celery.schedules import crontab` to the imports at the top of `config/settings/base.py`, then add this below the existing `CELERY_` settings (after `TIME_ZONE` is defined):

```python
# config/settings/base.py  (addition)
CELERY_TIMEZONE = "Europe/Istanbul"              # beat reads crontabs in Istanbul time
CELERY_BEAT_SCHEDULE = {   # T2.2 (Sprint 8) only adds an entry here; the beat service already runs
    "delete-old-exports": {
        "task": "apps.reports.tasks.purge_old_exports",
        "schedule": crontab(hour=3, minute=15),   # 03:15, after the 03:00 database backup
    },
}
```

Add the beat service to `compose.prod.yml`, below `worker`. It uses the same image. Run exactly **one** beat per stack (never scale it): two beats would send every scheduled task twice. Beat only *sends* the message at 03:15; the `worker` container runs the task.

```yaml
  beat:
    image: ${IMAGE}:${IMAGE_TAG}
    command: celery -A config beat -l info
    env_file: .env
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.prod
    depends_on:
      redis: {condition: service_healthy}
    restart: unless-stopped
```

In the `Dockerfile`, extend the WeasyPrint line:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
```

**Running beat locally.** You only need this to watch the schedule fire. Set `CELERY_EAGER=false` in `.env`, then run `uv run celery -A config worker -l info` in one terminal and `uv run celery -A config beat -l info` in another. Beat logs `Scheduler: Sending due task delete-old-exports` at 03:15. To test without waiting until 03:15, call the task directly: `uv run celery -A config call apps.reports.tasks.purge_old_exports`. Beat writes a small `celerybeat-schedule` file in the current directory; add `celerybeat-schedule*` to `.gitignore`.

Locally, in dev, Celery runs eagerly (`CELERY_TASK_ALWAYS_EAGER`), so an export finishes inside the request. To test the real flow, run `uv run celery -A config worker -l info` in a second terminal with `CELERY_EAGER=false` in `.env`. On macOS, WeasyPrint needs `brew install pango`.

**6. Selector, views and URLs.**

```python
# apps/reports/selectors.py  (addition)
from django.shortcuts import get_object_or_404

from .models import ExportJob


def export_for_user(user, export_id) -> ExportJob:
    """Only the person who asked for an export may see or download it (404 for anyone else)."""
    return get_object_or_404(ExportJob, pk=export_id, created_by=user)
```

```python
# apps/reports/views.py  (additions)
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import require_offering_access, require_role

from .filters import DashboardFilterForm
from .models import ExportJob
from apps.accounts.permissions import head_program_or_404

from .selectors import export_for_user
from .services import request_export


def _export_started(request, job):
    job.refresh_from_db()   # in eager mode (dev, tests) the task has already run
    if request.htmx:
        return render(request, "reports/export_status.html#status", {"export": job})
    return redirect("reports:export_status", export_id=job.pk)


@login_required
@require_offering_access()
@require_POST
def course_export(request, fmt, *, offering, perms_for, **_):
    if fmt not in ExportJob.Format.values:
        raise Http404
    job = request_export(request.user, kind=ExportJob.Kind.COURSE, fmt=fmt, offering=offering)
    return _export_started(request, job)


@login_required
@require_role("head")
@require_POST
def department_export(request, fmt):
    if fmt not in ExportJob.Format.values:
        raise Http404
    program = head_program_or_404(request.user)
    filters = DashboardFilterForm(request.POST, program=program).filters()
    job = request_export(request.user, kind=ExportJob.Kind.DEPARTMENT, fmt=fmt, program=program,
                         params=filters.to_params())
    return _export_started(request, job)


@login_required
@require_role("student", "instructor", "head")
def export_status(request, export_id):
    export = export_for_user(request.user, export_id)
    if request.GET.get("download") == "1":
        if export.status != ExportJob.Status.DONE or not export.file:
            raise Http404
        return FileResponse(export.file.open("rb"), as_attachment=True, filename=Path(export.file.name).name)
    template = "reports/export_status.html#status" if request.htmx else "reports/export_status.html"
    return render(request, template, {"export": export})
```

The `course_export` signature takes `**_` so it works whether or not `require_offering_access` (S2-02) removes `offering_id` from the URL kwargs. `export_status` allows students too, because T2.4's transcript uses the same status page. Ownership is the real check.

```python
# apps/reports/urls.py  (add to urlpatterns; app_name = "reports" is already set)
    path("offerings/<int:offering_id>/export/<str:fmt>/", views.course_export, name="course_export"),
    path("department/export/<str:fmt>/", views.department_export, name="department_export"),
    path("exports/<int:export_id>/", views.export_status, name="export_status"),
```

**7. Templates.**

```django
{# apps/reports/templates/reports/export_status.html #}
{% extends "base.html" %}
{% block title %}Export{% endblock %}
{% block content %}
  <h1 class="h4">{{ export.get_kind_display }} ({{ export.get_fmt_display }})</h1>
  {% partial status %}
{% endblock %}

{% partialdef status %}
<div class="export-status d-flex align-items-center gap-2" role="status" aria-live="polite"
     {% if export.status == "pending" or export.status == "running" %}
       hx-get="{% url 'reports:export_status' export.pk %}" hx-trigger="every 2s" hx-swap="outerHTML"
     {% endif %}>
  {% if export.status == "done" %}
    <a class="btn btn-sm btn-success" href="{% url 'reports:export_status' export.pk %}?download=1" download>
      Download {{ export.get_fmt_display }}
    </a>
    <span class="small text-body-secondary">{{ export.get_kind_display }}, ready {{ export.finished_at|time:"H:i" }}. Kept for 7 days.</span>
  {% elif export.status == "failed" %}
    <span class="text-danger">We couldn't build this report. Try again; if it fails twice, tell the team.</span>
  {% else %}
    <span class="spinner-border spinner-border-sm" aria-hidden="true"></span>
    <span>Building your {{ export.get_kind_display|lower }} ({{ export.get_fmt_display }})…</span>
  {% endif %}
</div>
{% endpartialdef %}
```

The polling stops by itself: once the job is `done` or `failed`, the server returns a `div` without `hx-trigger`, and HTMX swaps it in (spec §8.5 "Polling").

```django
{# apps/reports/templates/reports/includes/export_buttons.html #}
{# Use: {% include "reports/includes/export_buttons.html" with pdf_url=… xlsx_url=… params=… %}  (no "only": needs csrf_token) #}
<div class="d-flex flex-wrap align-items-start gap-2">
  <form method="post" action="{{ pdf_url }}" hx-post="{{ pdf_url }}" hx-target="#export-results" hx-swap="afterbegin">
    {% csrf_token %}
    {% for key, value in params.items %}<input type="hidden" name="{{ key }}" value="{{ value }}">{% endfor %}
    <button type="submit" class="btn btn-sm btn-outline-primary">Export PDF</button>
  </form>
  <form method="post" action="{{ xlsx_url }}" hx-post="{{ xlsx_url }}" hx-target="#export-results" hx-swap="afterbegin">
    {% csrf_token %}
    {% for key, value in params.items %}<input type="hidden" name="{{ key }}" value="{{ value }}">{% endfor %}
    <button type="submit" class="btn btn-sm btn-outline-primary">Export Excel</button>
  </form>
  <div id="export-results" class="d-flex flex-column gap-1"></div>
</div>
```

In `reports/department.html`, replace the `#export-area` placeholder from S7-02 with this. It sits inside `dashboard_body`, so the hidden fields always carry the filters currently on screen.

```django
  <div class="mb-4" id="export-area">
    {% url 'reports:department_export' fmt='pdf' as pdf_url %}
    {% url 'reports:department_export' fmt='xlsx' as xlsx_url %}
    {% include "reports/includes/export_buttons.html" with pdf_url=pdf_url xlsx_url=xlsx_url params=filters.to_params %}
  </div>
```

In `reports/course_results.html` (S3-03), add this under the page heading:

```django
{% url 'reports:course_export' offering_id=offering.pk fmt='pdf' as pdf_url %}
{% url 'reports:course_export' offering_id=offering.pk fmt='xlsx' as xlsx_url %}
{% include "reports/includes/export_buttons.html" with pdf_url=pdf_url xlsx_url=xlsx_url %}
```

The print stylesheet is a template, included inline. WeasyPrint then never has to fetch a file, and the PDF looks the same on every machine.

```css
/* apps/reports/templates/reports/pdf/_print.css */
@page {
  size: A4;
  margin: 18mm 15mm 20mm 15mm;
  @bottom-left { content: "POlaris"; font-size: 8pt; color: #666; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font-size: 8pt; color: #666; }
}
body { font-family: "DejaVu Sans", sans-serif; font-size: 9.5pt; color: #111; }
h1 { font-size: 16pt; margin: 0 0 2mm; }
h2 { font-size: 11.5pt; margin: 7mm 0 2mm; border-bottom: 0.4pt solid #999; padding-bottom: 1mm; break-after: avoid; }
.meta { color: #555; margin: 0 0 4mm; }
table { width: 100%; border-collapse: collapse; margin-bottom: 3mm; }
thead { display: table-header-group; }          /* repeat header rows on every page */
tr { break-inside: avoid; }
th, td { border: 0.4pt solid #bbb; padding: 1.2mm 1.6mm; text-align: left; vertical-align: top; }
th { background: #eef1f6; font-weight: bold; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.empty { color: #999; text-align: center; }
.flag { color: #8a5300; font-weight: bold; }
.ok { color: #1d6b2f; }
.bad { color: #a61b1b; }
.small { font-size: 8pt; color: #555; }
```

```django
{# apps/reports/templates/reports/pdf/course.html #}
{% load polaris %}<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ offering.course.code }} course report</title>
  <style>{% include "reports/pdf/_print.css" %}</style>
</head>
<body>
  <h1>{{ offering.course.code }} {{ offering.course.title }}</h1>
  <p class="meta">
    {{ offering.term.name }} · Section {{ offering.section }} ·
    Instructors: {% for u in instructors %}{{ u.get_full_name }}{% if not forloop.last %}, {% endif %}{% empty %}none{% endfor %} ·
    Generated {{ generated_at|date:"j M Y H:i" }}
  </p>

  <h2>Learning outcome results (class averages)</h2>
  <table>
    <thead><tr><th>LO</th><th>Description</th><th class="num">Class average</th><th class="num">Students with a score</th></tr></thead>
    <tbody>
      {% for s in lo_stats %}
        <tr><td>LO {{ s.lo.number }}</td><td>{{ s.lo.description }}</td><td class="num">{{ s.mean|score }}</td><td class="num">{{ s.n_scored }}</td></tr>
      {% empty %}
        <tr><td colspan="4" class="empty">No learning outcomes defined.</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <h2>Contribution to program outcomes (this course only)</h2>
  <table>
    <thead><tr><th>PO</th><th>Outcome</th><th class="num">Score</th></tr></thead>
    <tbody>
      {% for p in po_contributions %}
        <tr><td>PO {{ p.po.number }}</td><td>{{ p.po.short_name }}</td><td class="num">{{ p.score|score }}</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <h2>Assessment → LO weights (%)</h2>
  <table>
    <thead><tr><th>Assessment</th>{% for lo in grid.los %}<th class="num">LO {{ lo.number }}</th>{% endfor %}</tr></thead>
    <tbody>
      {% for assessment, values in a_lo_rows %}
        <tr><td>{{ assessment.name }}</td>{% for v in values %}<td class="num">{% if v is not None %}{{ v|weight }}{% endif %}</td>{% endfor %}</tr>
      {% endfor %}
    </tbody>
  </table>

  <h2>LO → PO weights (1–5)</h2>
  <table>
    <thead><tr><th>LO</th>{% for po in grid.pos %}<th class="num">PO {{ po.number }}</th>{% endfor %}</tr></thead>
    <tbody>
      {% for lo, values in lo_po_rows %}
        <tr><td>LO {{ lo.number }}</td>{% for v in values %}<td class="num">{% if v is not None %}{{ v }}{% endif %}</td>{% endfor %}</tr>
      {% endfor %}
    </tbody>
  </table>

  <h2>Mapping check</h2>
  {% if lint %}
    <table>
      <thead><tr><th>Code</th><th>Severity</th><th>Message</th></tr></thead>
      <tbody>{% for i in lint %}<tr><td>{{ i.code }}</td><td>{{ i.severity }}</td><td>{{ i.message }}</td></tr>{% endfor %}</tbody>
    </table>
  {% else %}
    <p class="ok">No problems found.</p>
  {% endif %}
  <p class="small">Scores use published grades only. Missing grades are skipped, not counted as zero. Rounded to one decimal for display only.</p>
</body>
</html>
```

```django
{# apps/reports/templates/reports/pdf/department.html #}
{% load polaris %}<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ program.code }} department report</title>
  <style>{% include "reports/pdf/_print.css" %}</style>
</head>
<body>
  <h1>{{ program.code }} · {{ program.name }}</h1>
  <p class="meta">Filters: {{ filters.label }} · Attainment threshold {{ program.attainment_threshold|score }} · Generated {{ generated_at|date:"j M Y H:i" }}</p>

  <h2>Program outcomes</h2>
  <table>
    <thead><tr><th>PO</th><th>Outcome</th><th class="num">Average</th><th class="num">Students with evidence</th><th class="num">Attainment rate</th></tr></thead>
    <tbody>
      {% for s in po_summary %}
        <tr><td>PO {{ s.po.number }}</td><td>{{ s.po.short_name }}</td><td class="num">{{ s.mean|score }}</td><td class="num">{{ s.n_with_evidence }}</td><td class="num">{% if s.attainment_rate is None %}—{% else %}{{ s.attainment_rate|pct }}{% endif %}</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <h2>Attainment rate (target {{ attainment.target|pct }})</h2>
  <table>
    <thead><tr><th>PO</th>{% for col in attainment.columns %}<th class="num">{{ col }}</th>{% endfor %}</tr></thead>
    <tbody>
      {% for row in attainment.rows %}
        <tr><td>PO {{ row.po.number }} {{ row.po.short_name }}</td>
          {% for rate in row.cells %}<td class="num{% if rate is not None and rate < attainment.target %} bad{% endif %}">{% if rate is None %}—{% else %}{{ rate|pct }}{% endif %}</td>{% endfor %}
        </tr>
      {% endfor %}
    </tbody>
  </table>

  <h2>Coverage (Σ LO→PO weight, latest offering per course)</h2>
  <table>
    <thead><tr><th>Course</th>{% for po in coverage.pos %}<th class="num">PO {{ po.number }}</th>{% endfor %}</tr></thead>
    <tbody>
      {% for row in coverage.rows %}
        <tr><td>{{ row.course.code }}</td>{% for cell in row.cells %}<td class="num">{{ cell.value }}</td>{% endfor %}</tr>
      {% endfor %}
      <tr><th>Total</th>{% for t in coverage.totals %}<th class="num{% if t.flags %} flag{% endif %}">{{ t.value }}{% if t.flags %} ⚠{% endif %}</th>{% endfor %}</tr>
    </tbody>
  </table>
  {% for t in coverage.flagged %}<p class="flag">⚠ PO {{ t.po.number }} {{ t.po.short_name }}: {{ t.flags|join:"; " }}</p>{% endfor %}

  {% if completion_term %}
    <h2>{{ completion_term.name }} completion: {{ completion_done }}/{{ completion|length }} courses fully published</h2>
    <table>
      <thead><tr><th>Course</th><th class="num">Students</th><th class="num">Published</th><th>Mapping</th></tr></thead>
      <tbody>
        {% for r in completion %}
          <tr><td>{{ r.offering.course.code }}{% if r.offering.section != "1" %} §{{ r.offering.section }}{% endif %}</td><td class="num">{{ r.n_students }}</td><td class="num">{{ r.n_published }}/{{ r.n_assessments }}</td><td class="{% if r.mapping_complete %}ok{% else %}bad{% endif %}">{% if r.mapping_complete %}Complete{% else %}Incomplete{% endif %}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}
  <p class="small">All numbers in this report come from one database snapshot taken at {{ generated_at|date:"H:i:s" }}.</p>
</body>
</html>
```

**8. Permission matrix.** `reports:course_export`, `reports:department_export` and `reports:export_status` already have rows in `ROUTES` (`apps/accounts/tests/routes.py`, S2-02, `story="S7-03"`). They switch on once the URLs exist. Check that the matrix world's `export_job()` creates an export owned by the world's *instructor*, which is what the `EXPORT_OWNER` preset expects (only the creator gets 200; everyone else 404). Nothing else to add.

### Tests

```python
# apps/reports/tests/test_snapshot.py
"""Proof for CSE 321 Section 4: inside the export snapshot, other people's commits are invisible."""
import psycopg
import pytest
from django.db import connection

from apps.core.models import AuditEvent
from apps.reports.snapshot import repeatable_read_snapshot

pytestmark = pytest.mark.django_db(transaction=True)


def _other_connection():
    sd = connection.settings_dict
    return psycopg.connect(dbname=sd["NAME"], user=sd["USER"], password=sd["PASSWORD"],
                           host=sd["HOST"] or "localhost", port=sd["PORT"] or 5432, autocommit=True)


def test_runs_at_repeatable_read():
    with repeatable_read_snapshot(), connection.cursor() as cursor:
        cursor.execute("SHOW transaction_isolation")
        assert cursor.fetchone()[0] == "repeatable read"


def test_commits_by_others_are_invisible_inside_the_snapshot():
    with repeatable_read_snapshot():
        before = AuditEvent.objects.count()          # first query: the snapshot is taken here
        with _other_connection() as other:
            other.execute("INSERT INTO core_auditevent (action, entity_type, entity_id, created_at) "
                          "VALUES ('test.insert', 'test', 1, now())")
        assert AuditEvent.objects.count() == before  # still the old world
    assert AuditEvent.objects.count() == before + 1  # a new transaction sees the insert


def test_default_level_would_have_seen_it():
    """The control case: READ COMMITTED takes a new snapshot per statement."""
    from django.db import transaction

    with transaction.atomic():
        before = AuditEvent.objects.count()
        with _other_connection() as other:
            other.execute("INSERT INTO core_auditevent (action, entity_type, entity_id, created_at) "
                          "VALUES ('test.insert', 'test', 2, now())")
        assert AuditEvent.objects.count() == before + 1
```

Paste the output of these three tests into the CSE 321 report. Together they are the whole argument for why the export uses a stronger level than the rest of the system.

```python
# apps/reports/tests/test_exports.py
import io

import pytest
from django.urls import reverse
from openpyxl import load_workbook

from apps.core.tests.factories import MembershipFactory, UserFactory
from apps.core.tests.scenarios import elif_scenario
from apps.reports import exports
from apps.reports.filters import DashboardFilters
from apps.scoring.engine import display

pytestmark = pytest.mark.django_db


@pytest.fixture
def elif_data():
    return elif_scenario(published=True)


@pytest.fixture
def instructor_client(client, elif_data):
    teacher = UserFactory()
    elif_data.offering.instructors.add(teacher)
    MembershipFactory(user=teacher, program=elif_data.offering.course.program, role="instructor")
    client.force_login(teacher)
    return client


def test_pdf_html_and_results_page_show_the_same_numbers(instructor_client, elif_data):  # T1.7 AC 1
    offering = elif_data.offering
    screen = instructor_client.get(reverse("reports:results", args=[offering.pk])).content.decode()
    printed = exports.render_course_html(offering)
    summary = exports.course_export_context(offering)["summary"]

    expected = [display(summary.class_mean[lo.id]) for lo in summary.los]
    expected += [display(v) for v in summary.po_contribution.values() if v is not None]
    assert {"86.0", "82.9", "85.0"} <= set(expected)       # the professor's numbers (spec §2.2)
    for value in expected:
        assert value in screen, f"{value} missing on screen"
        assert value in printed, f"{value} missing in PDF"


def test_course_workbook_cells_are_numbers(elif_data):  # T1.7 AC 2
    wb = load_workbook(io.BytesIO(exports.render_course_xlsx(elif_data.offering)))

    assert wb.sheetnames == ["Course", "LO statistics", "PO contribution", "Assessment-LO weights",
                             "LO-PO weights", "Mapping check"]
    stats = wb["LO statistics"]
    means = {stats.cell(row=r, column=1).value: stats.cell(row=r, column=3) for r in range(2, stats.max_row + 1)}
    assert means["LO 1"].data_type == "n" and means["LO 1"].value == pytest.approx(86.0)
    assert means["LO 2"].data_type == "n" and means["LO 2"].value == pytest.approx(82.9)
    assert means["LO 1"].number_format == "0.0"
    po = wb["PO contribution"]
    assert po.cell(row=2, column=3).data_type == "n"


def test_department_workbook_has_every_section(elif_data):
    program = elif_data.offering.course.program
    filters = DashboardFilters.from_params(program, {"f": "1"})   # include open terms: Elif's term may be open
    wb = load_workbook(io.BytesIO(exports.render_department_xlsx(program, filters)))

    assert wb.sheetnames[:4] == ["About", "PO summary", "Attainment", "Coverage"]
    assert wb["About"].cell(row=3, column=2).value == filters.label
    coverage = wb["Coverage"]
    assert coverage.cell(row=coverage.max_row - 1, column=1).value == "Total"


def test_department_html_prints_filters_and_flags(elif_data):
    program = elif_data.offering.course.program
    filters = DashboardFilters.from_params(program, {"f": "1"})
    html = exports.render_department_html(program, filters)

    assert filters.label in html
    assert "one database snapshot" in html


def test_real_pdf_bytes():
    try:
        pdf = exports.html_to_pdf("<html><body><p>İğüşçö ok</p></body></html>")
    except (ImportError, OSError) as exc:   # WeasyPrint raises OSError on import when Pango is missing
        pytest.skip(f"WeasyPrint or its system libraries missing: {exc}")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000
```

```python
# apps/reports/tests/test_export_views.py
from datetime import timedelta

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from apps.core.tests.factories import MembershipFactory, UserFactory
from apps.core.tests.scenarios import elif_scenario
from apps.reports import tasks
from apps.reports.models import ExportJob

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def setup(client):
    s = elif_scenario(published=True)
    teacher = UserFactory()
    s.offering.instructors.add(teacher)
    MembershipFactory(user=teacher, program=s.offering.course.program, role="instructor")
    client.force_login(teacher)
    s.teacher, s.client = teacher, client
    return s


def test_course_xlsx_export_end_to_end(setup, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = setup.client.post(reverse("reports:course_export", args=[setup.offering.pk, "xlsx"]),
                                     headers={"HX-Request": "true"})
    job = ExportJob.objects.get()

    assert response.status_code == 200
    assert job.status == ExportJob.Status.DONE
    assert job.created_by == setup.teacher
    assert "Download Excel" in response.content.decode()

    download = setup.client.get(reverse("reports:export_status", args=[job.pk]), {"download": "1"})
    assert download.status_code == 200
    assert download["Content-Disposition"].startswith("attachment")
    assert b"".join(download.streaming_content)[:2] == b"PK"      # .xlsx is a zip file


def test_non_htmx_post_redirects_to_status_page(setup, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = setup.client.post(reverse("reports:course_export", args=[setup.offering.pk, "xlsx"]))
    assert response.status_code == 302
    assert response["Location"] == reverse("reports:export_status", args=[ExportJob.objects.get().pk])


def test_unknown_format_is_404(setup):
    assert setup.client.post(reverse("reports:course_export", args=[setup.offering.pk, "docx"])).status_code == 404


def test_someone_elses_export_is_404(setup, client):
    job = ExportJob.objects.create(kind="course", fmt="pdf", offering=setup.offering, created_by=UserFactory())
    assert setup.client.get(reverse("reports:export_status", args=[job.pk])).status_code == 404


def test_pending_job_keeps_polling_and_done_job_stops(setup):
    job = ExportJob.objects.create(kind="course", fmt="pdf", offering=setup.offering, created_by=setup.teacher)
    url = reverse("reports:export_status", args=[job.pk])

    pending = setup.client.get(url, headers={"HX-Request": "true"}).content.decode()
    assert 'hx-trigger="every 2s"' in pending

    job.status = ExportJob.Status.DONE
    job.file.save("x.pdf", ContentFile(b"%PDF-1.7"), save=False)
    job.save()
    done = setup.client.get(url, headers={"HX-Request": "true"}).content.decode()
    assert "hx-trigger" not in done
    assert "Download PDF" in done


def test_failure_ends_in_failed_with_message(setup, monkeypatch):
    job = ExportJob.objects.create(kind="course", fmt="pdf", offering=setup.offering, created_by=setup.teacher)

    def boom(_job):
        raise RuntimeError("pango exploded")

    monkeypatch.setattr("apps.reports.exports.render_export", boom)
    tasks.build_export(job.pk)
    job.refresh_from_db()

    assert job.status == ExportJob.Status.FAILED
    assert "pango exploded" in job.error
    page = setup.client.get(reverse("reports:export_status", args=[job.pk])).content.decode()
    assert "couldn't build this report" in page
    assert "pango" not in page                      # technical detail stays in the admin


def test_build_is_idempotent(setup, monkeypatch):
    job = ExportJob.objects.create(kind="course", fmt="pdf", offering=setup.offering, created_by=setup.teacher,
                                   status=ExportJob.Status.DONE)
    monkeypatch.setattr("apps.reports.exports.render_export",
                        lambda _job: pytest.fail("a DONE job must not be rebuilt"))
    assert tasks.build_export(job.pk) == ExportJob.Status.DONE


def test_purge_deletes_old_files_only(setup, tmp_path):
    old = ExportJob.objects.create(kind="course", fmt="pdf", offering=setup.offering, created_by=setup.teacher)
    old.file.save("old.pdf", ContentFile(b"%PDF"), save=True)
    ExportJob.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=8))
    new = ExportJob.objects.create(kind="course", fmt="pdf", offering=setup.offering, created_by=setup.teacher)
    old_path = tmp_path / old.file.name

    assert tasks.purge_old_exports() == 1           # the beat entry calls it with the default 7 days
    assert not old_path.exists()
    assert list(ExportJob.objects.values_list("pk", flat=True)) == [new.pk]


def test_beat_schedule_runs_purge_nightly(settings):
    entry = settings.CELERY_BEAT_SCHEDULE["delete-old-exports"]
    assert entry["task"] == "apps.reports.tasks.purge_old_exports"
    assert (entry["schedule"].hour, entry["schedule"].minute) == ({3}, {15})
    assert settings.CELERY_TIMEZONE == "Europe/Istanbul"


def test_head_department_export_carries_filters(client, django_capture_on_commit_callbacks):
    s = elif_scenario(published=True)
    head = UserFactory()
    MembershipFactory(user=head, program=s.offering.course.program, role="head")
    client.force_login(head)

    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("reports:department_export", args=["xlsx"]), {"f": "1", "cohort": ""},
                    headers={"HX-Request": "true"})
    job = ExportJob.objects.get()

    assert job.kind == ExportJob.Kind.DEPARTMENT
    assert job.params["closed_only"] == ""          # unticked box was respected
    assert job.status == ExportJob.Status.DONE
```

The course PDF test runs only where WeasyPrint's libraries exist. CI's `ubuntu-latest` runner has Pango. On macOS, run `brew install pango` once.

### Check it works

1. Set `CELERY_EAGER=false` in `.env`. Start `docker compose up -d`, then `uv run celery -A config worker -l info` in a second terminal, and `runserver`.
2. As the head, filter the dashboard to cohort 2023 and click **Export PDF**. The worker log shows `build_export … succeeded`. The button area shows "Building…" and then **Download PDF**.
3. Open the PDF. The filter line says "cohort 2023". The attainment and coverage numbers match the screen. Turkish names render, including "İ" and "ş". Table headers repeat on page 2. The footer shows "Page 1 of N".
4. Click **Export Excel** and open the file in Excel or LibreOffice. Sort the *Average score* column: it sorts numerically, which proves the cells aren't text. Scores show one decimal and rates show percentages.
5. As an instructor, open your course results and export both formats.
6. Run `uv run celery -A config call apps.reports.tasks.purge_old_exports`. It returns `0` today.
7. On staging after deploy: `docker compose ps` shows `web`, `worker`, `beat`, `db` and `redis` all running.

### Done when

- [ ] T1.7 AC 1 (PDF numbers = screen numbers): `test_pdf_html_and_results_page_show_the_same_numbers`
- [ ] T1.7 AC 2 (Excel numbers are numbers): `test_course_workbook_cells_are_numbers`
- [ ] Department report in one REPEATABLE READ snapshot: `test_snapshot.py` (3 tests), `render_export` uses the helper
- [ ] Background build, polling, download, failure path: `test_export_views.py`
- [ ] Only the creator can download, and files are deleted after 7 days: `test_someone_elses_export_is_404`, `test_purge_deletes_old_files_only`
- [ ] Three new URLs in the permission matrix; `beat` runs on staging

### Commits and PR

```
Add ExportJob model and admin
Run exports inside a REPEATABLE READ snapshot
Render course and department reports as PDF and Excel
Build exports in Celery with polling status and owner-only download
Schedule nightly cleanup of old exports with Celery beat
```
PR title: **S7-03 Course and department exports (PDF + Excel) built in the background**

---

## S7-04 · Student profile v2: radar, per-course breakdown, trend, summary

**Points:** 5 · **Owner:** Person B · **Branch:** `feature/S7-04-profile-v2` · **Depends on:** S3-02 (profile v1), S1-06/S1-07 (engine, loaders)

### Goal

Elif opens `/me/` and, without help, understands three things:

1. **Where she stands.** A radar of her 11 PO scores, with the program's threshold drawn as a ring, next to the table from v1.
2. **Where each number comes from.** A stacked bar per PO shows how many score points each course contributed.
3. **How it moved.** A line per PO shows her cumulative score at the end of each term.

Two or three plain sentences at the top say the same in words. Delivers T1.5, AC 1 (radar = table) and AC 2 (trend = hand-checked cumulative values), and the "Elif" minute of the demo script.

### The maths of "per-course contribution", in plain words

A PO score is a weighted average over every LO→PO link that has an LO score:

`PO = Σ (w × LO score) ÷ Σ w`.

Split the top sum by course and keep the same bottom:

`share(course) = Σ over that course's links (w × LO score) ÷ Σ w (all courses)`.

Add the shares of all courses and you get exactly the PO score, because we only split a sum. So each bar in the stacked chart is exactly as tall as the PO score, and every coloured segment is "points this course earned you on this PO". This is arithmetic on scores, so it lives in `engine.py` as a pure function with a property test. No view or template computes it.

### Design choices

- **Trend = cumulative profile at the end of each term**, using `load_student_inputs(student, up_to_term=term)` and the same engine. "Fall 2025 → 80.0" means "if you had stopped after Fall 2025, your PO 1 would have been 80.0". This is what a student wants to know ("am I improving?"). A per-term-only score would jump around with each term's course mix.
- **Charts show exactly the table's rounded numbers.** Chart data goes through `chart_number()`, which is `float(display(value))`. A tooltip can never say 84.95 while the table says 85.0 (AC 1). Floats are fine here because these numbers are only drawn, never computed with again.
- **Per-course segments are rounded independently.** So their tooltips can add up to 0.1 more or less than the PO score. The bar's total height comes from the unrounded shares and matches the table. We say this in a note under the chart rather than hiding it.
- **The summary is template logic, not AI** (spec T1.5). The same profile always gives the same sentences. Each sentence is tested.
- **Every chart has a text version.** A `<details>` table under each chart, and `role="img"` with an `aria-label` on each canvas. Charts are for sighted mouse users; the tables are for everyone else (S7-07 checks this).
- **One template serves two views.** The head's `/department/students/<id>/` renders the same page through the same selector. The "where does this come from" drawer only shows for the student themselves (`can_drill`), because it uses the student-only URL `student:po_detail`.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/scoring/engine.py` | modify | `evidence_offerings()`, `contribution_by_offering()` |
| `apps/scoring/tests/test_engine_contributions.py` | create | unit + Hypothesis property tests |
| `apps/reports/summary.py` | create | `plain_language_summary()` |
| `apps/reports/charts.py` | create | `chart_number()`, `profile_payload()` |
| `apps/reports/selectors.py` | modify | `PORow`, `CourseRow`, `Trend`, `student_trend()`, full `student_profile_context()` |
| `apps/reports/templates/reports/profile.html` | modify (rewrite) | v2 page |
| `static/js/polaris.js` | modify | `PL.profileCharts()` |
| `apps/reports/tests/test_summary.py`, `test_trend.py`, `test_profile_v2.py` | create | tests |

### Steps

**1. Two pure functions in `apps/scoring/engine.py`.** Add them after `compute_student_profile`.

```python
# apps/scoring/engine.py  (additions for S7-04)

def evidence_offerings(profile: StudentProfile) -> dict[Hashable, set[int]]:
    """po_id -> the offerings that actually fed this PO (a linked LO with a score)."""
    result: dict[Hashable, set[int]] = defaultdict(set)
    for po_id, links in profile.po_contributors.items():
        for offering_id, lo_id, _weight in links:
            node = profile.lo_scores.get((offering_id, lo_id))
            if node is not None and node.score is not None:
                result[po_id].add(offering_id)
    return dict(result)


def contribution_by_offering(profile: StudentProfile) -> dict[Hashable, dict[int, Decimal]]:
    """po_id -> {offering_id: points that offering contributes to the PO score}.

    share(offering) = Σ_(links of that offering) w × LO score  ÷  Σ_(all links with a score) w.
    The shares of one PO add up to its score exactly (same denominator, split numerator).
    POs with no evidence are absent, exactly like a None score."""
    result: dict[Hashable, dict[int, Decimal]] = {}
    for po_id, links in profile.po_contributors.items():
        present = []
        for offering_id, lo_id, weight in links:
            node = profile.lo_scores.get((offering_id, lo_id))
            if node is not None and node.score is not None:
                present.append((offering_id, node.score, weight))
        denominator = sum((w for _, _, w in present), ZERO)
        if denominator == ZERO:
            continue
        shares: dict[int, Decimal] = defaultdict(lambda: ZERO)
        for offering_id, score, weight in present:
            shares[offering_id] += score * weight / denominator
        result[po_id] = dict(shares)
    return result
```

**2. Engine tests (test-first, as in §9.8: commit the red test, then the code).**

```python
# apps/scoring/tests/test_engine_contributions.py
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from apps.scoring.engine import (
    Edge,
    OfferingInputs,
    compute_student_profile,
    contribution_by_offering,
    display,
    evidence_offerings,
)

D = Decimal


def elif_inputs(offering_id=7):
    return OfferingInputs(
        offering_id=offering_id,
        grades={1: D(90), 2: D(80)},
        max_scores={1: D(100), 2: D(100)},
        assessment_lo_edges=(Edge(1, "lo1", D(60)), Edge(2, "lo1", D(40)),
                             Edge(1, "lo2", D(40)), Edge(2, "lo2", D(100))),
        lo_po_edges=(Edge("lo1", "po1", D(4)), Edge("lo2", "po1", D(2)), Edge("lo2", "po2", D(5))),
    )


def single_lo(offering_id, grade, po_weight):
    return OfferingInputs(
        offering_id=offering_id,
        grades={1: D(grade)},
        max_scores={1: D(100)},
        assessment_lo_edges=(Edge(1, "lo", D(100)),),
        lo_po_edges=(Edge("lo", "po1", D(po_weight)),),
    )


def test_single_course_gets_the_whole_score():
    profile = compute_student_profile([elif_inputs()])
    shares = contribution_by_offering(profile)

    assert display(shares["po1"][7]) == "85.0"
    assert display(shares["po2"][7]) == "82.9"


def test_two_courses_split_the_score_by_weighted_points():
    # A: LO 80 at weight 3, B: LO 60 at weight 1 → PO = (240 + 60) / 4 = 75 = 60 + 15
    profile = compute_student_profile([single_lo(1, 80, 3), single_lo(2, 60, 1)])
    shares = contribution_by_offering(profile)

    assert shares["po1"] == {1: D(60), 2: D(15)}
    assert profile.po_scores["po1"].score == D(75)


def test_links_without_lo_score_are_ignored():
    ungraded = OfferingInputs(offering_id=2, grades={}, max_scores={1: D(100)},
                              assessment_lo_edges=(Edge(1, "lo", D(100)),),
                              lo_po_edges=(Edge("lo", "po1", D(5)),))
    profile = compute_student_profile([single_lo(1, 70, 2), ungraded])

    assert contribution_by_offering(profile)["po1"] == {1: D(70)}
    assert evidence_offerings(profile) == {"po1": {1}}


def test_po_without_evidence_is_absent():
    ungraded = OfferingInputs(offering_id=1, grades={}, max_scores={1: D(100)},
                              assessment_lo_edges=(Edge(1, "lo", D(100)),),
                              lo_po_edges=(Edge("lo", "po1", D(5)),))
    profile = compute_student_profile([ungraded])

    assert contribution_by_offering(profile) == {}
    assert evidence_offerings(profile) == {}


@st.composite
def student_inputs(draw):
    offerings = []
    for offering_id in range(1, draw(st.integers(1, 4)) + 1):
        lo_ids = range(1, draw(st.integers(1, 3)) + 1)
        graded = draw(st.booleans())
        offerings.append(OfferingInputs(
            offering_id=offering_id,
            grades={1: draw(st.decimals(min_value=0, max_value=100, places=1))} if graded else {},
            max_scores={1: D(100)},
            assessment_lo_edges=tuple(Edge(1, lo, D(draw(st.integers(1, 100)))) for lo in lo_ids),
            lo_po_edges=tuple(
                Edge(lo, po, D(draw(st.integers(1, 5))))
                for lo in lo_ids
                for po in sorted(draw(st.sets(st.integers(1, 4), min_size=1, max_size=3)))
            ),
        ))
    return offerings


@settings(max_examples=300)
@given(student_inputs())
def test_shares_always_add_up_to_the_po_score(inputs):
    profile = compute_student_profile(inputs)
    shares = contribution_by_offering(profile)

    for po_id, node in profile.po_scores.items():
        if node.score is None:
            assert po_id not in shares
            continue
        total = sum(shares[po_id].values(), D(0))
        assert abs(total - node.score) < D("1e-20")        # same tolerance as the scale test (§2.6)
        assert all(v >= 0 for v in shares[po_id].values())
        assert set(shares[po_id]) == evidence_offerings(profile)[po_id]
```

**3. The summary sentences: `apps/reports/summary.py`.**

```python
# apps/reports/summary.py
"""Plain-language profile summary (T1.5). Template logic only: same profile → same sentences."""
from decimal import Decimal

from apps.scoring.engine import StudentProfile, display, evidence_offerings


def _po_names(pos) -> str:
    names = [f"PO {po.number}" for po in pos]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def plain_language_summary(profile: StudentProfile, pos, *, threshold: Decimal | None = None) -> list[str]:
    scored = [(po, profile.po_scores[po.id].score) for po in pos
              if po.id in profile.po_scores and profile.po_scores[po.id].score is not None]
    if not scored:
        return ["No published grades count towards your program outcomes yet. "
                "Your scores appear here as soon as your instructors publish grades."]

    best_po, best = max(scored, key=lambda pair: (pair[1], -pair[0].number))
    lines = [f"Your strongest outcome is PO {best_po.number} ({best_po.short_name}, {display(best)})."]

    evidence = evidence_offerings(profile)
    counts = {po.id: len(evidence.get(po.id, ())) for po in pos}
    missing = [po for po in pos if counts[po.id] == 0]
    if missing:
        verb = "has" if len(missing) == 1 else "have"
        lines.append(f"{_po_names(missing)} {verb} no evidence yet: none of your graded courses link to "
                     f"{'it' if len(missing) == 1 else 'them'} so far.")
    else:
        least = min(pos, key=lambda po: (counts[po.id], po.number))
        n = counts[least.id]
        lines.append(f"PO {least.number} ({least.short_name}) has the least evidence so far: "
                     f"{n} course{'' if n == 1 else 's'}.")

    if threshold is not None:
        below = [po for po, score in scored if score < threshold]
        if below:
            verb = "is" if len(below) == 1 else "are"
            lines.append(f"{_po_names(below)} {verb} below the program's threshold of {display(threshold)}.")
        else:
            lines.append(f"Every outcome with evidence is at or above the program's threshold of {display(threshold)}.")
    return lines
```

**4. Chart data: `apps/reports/charts.py`.**

```python
# apps/reports/charts.py
"""Turn engine results into JSON for Chart.js. Numbers are rounded exactly like |score."""
from decimal import Decimal

from apps.scoring.engine import display


def chart_number(value: Decimal | None) -> float | None:
    """The number the table shows, as a float for the chart (None → a gap)."""
    return None if value is None else float(display(value))


def profile_payload(*, pos, rows, shares, offerings, trend, threshold) -> dict:
    labels = [f"PO {po.number}" for po in pos]
    contributing = sorted(
        {offering_id for per_po in shares.values() for offering_id in per_po},
        key=lambda oid: (offerings[oid].term.starts_on, offerings[oid].course.code),
    )
    return {
        "labels": labels,
        "names": [po.short_name for po in pos],
        "threshold": chart_number(threshold),
        "scores": [chart_number(row.score) for row in rows],
        "contributions": [
            {
                "label": f"{offerings[oid].course.code} ({offerings[oid].term.code})",
                "data": [chart_number(shares.get(po.id, {}).get(oid)) for po in pos],
            }
            for oid in contributing
        ],
        "trend": {
            "labels": [term.name for term in trend.terms],
            "datasets": [
                {"label": f"PO {po.number}", "data": [chart_number(v) for v in trend.series[po.id]]}
                for po in pos
            ],
        },
    }
```

**5. Selectors: `apps/reports/selectors.py`.** Replace `student_profile_context` (S3-02) with this version, and add the data classes and `student_trend`.

```python
# apps/reports/selectors.py  (S7-04: replaces student_profile_context)
from dataclasses import dataclass
from decimal import Decimal

from django.http import Http404

from apps.accounts.models import ProgramMembership
from apps.accounts.permissions import can_view_student
from apps.catalog.models import CourseOffering, Enrollment, ProgramOutcome, Term
from apps.catalog.selectors import po_set_for_student
from apps.outcomes.models import LearningOutcome
from apps.scoring.engine import (
    NodeScore,
    compute_student_profile,
    contribution_by_offering,
    evidence_offerings,
)
from apps.scoring.loaders import load_student_inputs

from .charts import profile_payload
from .summary import plain_language_summary


@dataclass(frozen=True)
class PORow:
    po: ProgramOutcome
    node: NodeScore | None
    n_courses: int
    threshold: Decimal

    @property
    def score(self) -> Decimal | None:
        return None if self.node is None else self.node.score

    @property
    def coverage(self) -> Decimal | None:
        return None if self.node is None else self.node.coverage

    @property
    def attained(self) -> bool | None:
        return None if self.score is None else self.score >= self.threshold


@dataclass(frozen=True)
class CourseRow:
    offering: CourseOffering
    in_progress: bool
    lo_scores: list[tuple[LearningOutcome, NodeScore | None]]


@dataclass(frozen=True)
class Trend:
    terms: list[Term]
    series: dict[int, list[Decimal | None]]   # po_id -> one cumulative score per term


def student_trend(student, pos) -> Trend:
    """Cumulative PO scores at the end of each term the student was enrolled in (T1.5)."""
    terms = list(
        Term.objects.filter(offerings__enrollments__student=student,
                            offerings__enrollments__status=Enrollment.Status.ENROLLED)
        .distinct().order_by("starts_on")
    )
    series: dict[int, list[Decimal | None]] = {po.id: [] for po in pos}
    for term in terms:
        profile = compute_student_profile(load_student_inputs(student, include_open_terms=True, up_to_term=term))
        for po in pos:
            node = profile.po_scores.get(po.id)
            series[po.id].append(None if node is None else node.score)
    return Trend(terms=terms, series=series)


def student_profile_context(student, *, viewer) -> dict:
    if not can_view_student(viewer, student):
        raise Http404
    membership = (ProgramMembership.objects.select_related("program")
                  .filter(user=student, role=ProgramMembership.Role.STUDENT)
                  .order_by("program__code").first())
    if membership is None:
        raise Http404
    program = membership.program
    pos = list(po_set_for_student(student, program).outcomes.all())

    inputs = load_student_inputs(student, include_open_terms=True)
    profile = compute_student_profile(inputs)
    evidence = evidence_offerings(profile)
    shares = contribution_by_offering(profile)

    offerings = {
        o.pk: o for o in CourseOffering.objects.filter(pk__in=[i.offering_id for i in inputs])
        .select_related("course", "term")
    }
    los_by_offering: dict[int, list[LearningOutcome]] = {}
    for lo in LearningOutcome.objects.filter(offering_id__in=offerings).order_by("offering_id", "number"):
        los_by_offering.setdefault(lo.offering_id, []).append(lo)

    threshold = program.attainment_threshold
    rows = [PORow(po=po, node=profile.po_scores.get(po.id), n_courses=len(evidence.get(po.id, ())),
                  threshold=threshold) for po in pos]
    courses = [
        CourseRow(
            offering=o,
            in_progress=o.term.status != Term.Status.CLOSED,
            lo_scores=[(lo, profile.lo_scores.get((o.pk, lo.pk))) for lo in los_by_offering.get(o.pk, [])],
        )
        for o in sorted(offerings.values(), key=lambda o: (o.term.starts_on, o.course.code), reverse=True)
    ]
    trend = student_trend(student, pos)
    return {
        "student": student,
        "program": program,
        "threshold": threshold,
        "rows": rows,
        "courses": courses,
        "summary": plain_language_summary(profile, pos, threshold=threshold),
        "trend": trend,
        "trend_rows": [(po, trend.series[po.id]) for po in pos],
        "contribution_rows": [
            (offerings[oid], [shares.get(po.id, {}).get(oid) for po in pos])
            for oid in sorted({oid for per_po in shares.values() for oid in per_po},
                              key=lambda oid: (offerings[oid].term.starts_on, offerings[oid].course.code))
        ],
        "pos": pos,
        "chart": profile_payload(pos=pos, rows=rows, shares=shares, offerings=offerings,
                                 trend=trend, threshold=threshold),
        "can_drill": viewer.pk == student.pk,
    }
```

Query budget: membership (1), PO set and POs (2), loader for the whole profile (about 5), offerings (1), LOs (1), terms (1), plus one loader run per term (3 terms × about 5). That's roughly 26 for a third-year student, and it doesn't depend on how many students exist. S7-07 sets the budget at 35 to leave headroom. If the head's student page ever feels slow, T2.3's precomputed scores replace the per-term loader runs.

**6. The page: `apps/reports/templates/reports/profile.html`.** This is the full rewrite. `views_student.profile` and `reports.views.department_student` both render it, with `student_profile_context(...)` as the context.

```django
{% extends "base.html" %}
{% load polaris %}
{% block title %}{% if can_drill %}My profile{% else %}{{ student.get_full_name }}{% endif %}{% endblock %}

{% block content %}
<h1 class="h3 mb-3">{% if can_drill %}My program outcomes{% else %}{{ student.get_full_name }} · {{ student.student_number }}{% endif %}</h1>

<div class="card mb-4 border-0 bg-body-tertiary">
  <div class="card-body py-3">
    {% for line in summary %}<p class="mb-1">{{ line }}</p>{% endfor %}
  </div>
</div>

<div class="row g-4 mb-4">
  <div class="col-lg-5">
    <div class="ratio ratio-1x1">
      <canvas id="po-radar" role="img"
              aria-label="Radar chart of your scores on {{ rows|length }} program outcomes, with the threshold of {{ threshold|score }} as a ring. The same numbers are in the table."></canvas>
    </div>
  </div>
  <div class="col-lg-7">
    <div class="table-responsive">
      <table class="table table-sm align-middle">
        <caption class="visually-hidden">Your score, evidence and attainment for each program outcome</caption>
        <thead>
          <tr><th scope="col">PO</th><th scope="col">Outcome</th><th scope="col" class="text-end">Score</th>
              <th scope="col">Evidence</th><th scope="col">Status</th></tr>
        </thead>
        <tbody>
          {% for row in rows %}
            <tr data-po="{{ row.po.number }}">
              <th scope="row">
                {% if can_drill %}
                  <button type="button" class="btn btn-link p-0 align-baseline"
                          hx-get="{% url 'student:po_detail' row.po.pk %}" hx-target="#po-drawer-body"
                          data-bs-toggle="offcanvas" data-bs-target="#po-drawer"
                          aria-label="PO {{ row.po.number }}: where this number comes from">PO {{ row.po.number }}</button>
                {% else %}PO {{ row.po.number }}{% endif %}
              </th>
              <td><abbr title="{{ row.po.description }}" class="text-decoration-none">{{ row.po.short_name }}</abbr></td>
              <td class="text-end num" data-po-score="{{ row.po.number }}">{{ row.score|score }}</td>
              <td class="small text-body-secondary">
                {% if row.n_courses %}{{ row.n_courses }} course{{ row.n_courses|pluralize }}
                  {% if row.coverage is not None %}· {{ row.coverage|pct }} graded{% endif %}
                {% else %}No courses yet{% endif %}
              </td>
              <td>
                {% if row.attained is None %}<span class="badge text-bg-secondary">No evidence</span>
                {% elif row.attained %}<span class="badge text-bg-success">✓ Attained</span>
                {% else %}<span class="badge text-bg-danger">Below {{ threshold|score }}</span>{% endif %}
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% if can_drill %}<p class="small text-body-secondary">Select a PO number to see which courses and outcomes make up the score.</p>{% endif %}
  </div>
</div>

<section class="mb-4" aria-labelledby="contrib-title">
  <h2 id="contrib-title" class="h5">Where your scores come from</h2>
  {% if contribution_rows %}
    <div style="height: 320px"><canvas id="po-contributions" role="img"
      aria-label="Stacked bar chart: points each course contributes to each program outcome. Table version below."></canvas></div>
    <p class="small text-body-secondary mt-1">Each bar is your PO score; each colour is the points one course contributed. Segments are rounded separately, so they can differ from the total by 0.1.</p>
    <details>
      <summary class="small">Show as a table</summary>
      <div class="table-responsive">
        <table class="table table-sm small">
          <thead><tr><th scope="col">Course</th>{% for po in pos %}<th scope="col" class="text-end">PO {{ po.number }}</th>{% endfor %}</tr></thead>
          <tbody>
            {% for offering, values in contribution_rows %}
              <tr><th scope="row">{{ offering.course.code }} ({{ offering.term.code }})</th>
                {% for v in values %}<td class="text-end num">{{ v|score }}</td>{% endfor %}</tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </details>
  {% else %}
    {% include "includes/empty_state.html" with title="Nothing to show yet" message="Once an instructor publishes grades in a course linked to your program outcomes, you'll see its contribution here." only %}
  {% endif %}
</section>

<section class="mb-4" aria-labelledby="trend-title">
  <div class="d-flex flex-wrap justify-content-between align-items-end gap-2">
    <h2 id="trend-title" class="h5 mb-0">How your scores moved</h2>
    {% if trend.terms|length > 1 %}
      <div>
        <label for="trend-po" class="form-label small mb-0">Show</label>
        <select id="trend-po" class="form-select form-select-sm">
          <option value="all">All outcomes</option>
          {% for po in pos %}<option value="{{ forloop.counter0 }}">PO {{ po.number }} {{ po.short_name }}</option>{% endfor %}
        </select>
      </div>
    {% endif %}
  </div>
  {% if trend.terms|length > 1 %}
    <div style="height: 300px" class="mt-2"><canvas id="po-trend" role="img"
      aria-label="Line chart: your cumulative score per program outcome at the end of each term. Table version below."></canvas></div>
    <details>
      <summary class="small">Show as a table</summary>
      <div class="table-responsive">
        <table class="table table-sm small">
          <thead><tr><th scope="col">PO</th>{% for term in trend.terms %}<th scope="col" class="text-end">{{ term.name }}</th>{% endfor %}</tr></thead>
          <tbody>
            {% for po, values in trend_rows %}
              <tr><th scope="row">PO {{ po.number }}</th>{% for v in values %}<td class="text-end num">{{ v|score }}</td>{% endfor %}</tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </details>
  {% else %}
    <p class="text-body-secondary small mt-2">Your trend appears after your second term.</p>
  {% endif %}
</section>

<section class="mb-4" aria-labelledby="courses-title">
  <h2 id="courses-title" class="h5">Courses</h2>
  <ul class="list-group">
    {% for course in courses %}
      <li class="list-group-item">
        <div class="d-flex justify-content-between flex-wrap gap-2">
          <span>
            {% if can_drill %}<a href="{% url 'student:course' course.offering.pk %}">{{ course.offering.course.code }} {{ course.offering.course.title }}</a>
            {% else %}{{ course.offering.course.code }} {{ course.offering.course.title }}{% endif %}
            <span class="text-body-secondary">· {{ course.offering.term.name }}</span>
            {% if course.in_progress %}<span class="badge text-bg-warning ms-1">In progress</span>{% endif %}
          </span>
          <span class="small">
            {% for lo, node in course.lo_scores %}LO {{ lo.number }} <span class="num">{% if node %}{{ node.score|score }}{% else %}—{% endif %}</span>{% if not forloop.last %} · {% endif %}{% endfor %}
          </span>
        </div>
      </li>
    {% empty %}
      <li class="list-group-item text-body-secondary">You're not enrolled in any courses yet.</li>
    {% endfor %}
  </ul>
</section>

{% if can_drill %}
<div class="offcanvas offcanvas-end" tabindex="-1" id="po-drawer" aria-labelledby="po-drawer-title">
  <div class="offcanvas-header">
    <h2 class="offcanvas-title h5" id="po-drawer-title">Where this number comes from</h2>
    <button type="button" class="btn-close" data-bs-dismiss="offcanvas" aria-label="Close"></button>
  </div>
  <div class="offcanvas-body" id="po-drawer-body" aria-live="polite">Loading…</div>
</div>
{% endif %}

{{ chart|json_script:"profile-chart-data" }}
{% endblock %}

{% block scripts %}
<script>document.addEventListener("DOMContentLoaded", () => PL.profileCharts("profile-chart-data"));</script>
{% endblock %}
```

`json_script` writes the data into a `<script type="application/json">` tag, escaped safely. That is the Django way to hand data to JavaScript. Never write `{{ chart|safe }}` inside a `<script>`.

**7. Chart code: add to `static/js/polaris.js`.**

```javascript
/* ---- S7-04 student profile charts ---- */
window.PL = window.PL || {};

// Series colours, chosen to stay distinguishable for the common colour-vision deficiencies.
PL.palette = ["#1f4e9c", "#d08c00", "#2a9d8f", "#8e44ad", "#c0392b", "#16a085", "#6c757d", "#b5651d"];

PL.readJSON = function (id) {
  const el = document.getElementById(id);
  return el ? JSON.parse(el.textContent) : null;
};

PL.formatScore = function (value) {
  return value === null || value === undefined ? "—" : value.toFixed(1);
};

PL.profileCharts = function (dataId) {
  const data = PL.readJSON(dataId);
  if (!data || !window.Chart) return;
  const textColor = getComputedStyle(document.body).color;
  Chart.defaults.color = textColor;
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

  const radarEl = document.getElementById("po-radar");
  if (radarEl) {
    new Chart(radarEl, {
      type: "radar",
      data: {
        labels: data.labels,
        datasets: [
          { label: "Your score", data: data.scores, borderColor: PL.palette[0],
            backgroundColor: "rgba(31, 78, 156, 0.18)", pointRadius: 3, spanGaps: false },
          { label: "Threshold " + PL.formatScore(data.threshold), data: data.labels.map(() => data.threshold),
            borderColor: "#c0392b", borderDash: [6, 4], pointRadius: 0, fill: false },
        ],
      },
      options: {
        maintainAspectRatio: false,
        scales: { r: { min: 0, max: 100, ticks: { stepSize: 20, backdropColor: "transparent" } } },
        plugins: {
          tooltip: { callbacks: {
            title: (items) => items[0].label + " " + data.names[items[0].dataIndex],
            label: (ctx) => ctx.dataset.label + ": " + PL.formatScore(ctx.raw),
          } },
        },
      },
    });
  }

  const contribEl = document.getElementById("po-contributions");
  if (contribEl) {
    new Chart(contribEl, {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: data.contributions.map((ds, i) => ({
          label: ds.label, data: ds.data, backgroundColor: PL.palette[i % PL.palette.length], stack: "po",
        })),
      },
      options: {
        maintainAspectRatio: false,
        scales: { x: { stacked: true }, y: { stacked: true, min: 0, max: 100,
                  title: { display: true, text: "Score points" } } },
        plugins: { tooltip: { callbacks: { label: (ctx) => ctx.dataset.label + ": " + PL.formatScore(ctx.raw) } } },
      },
    });
  }

  const trendEl = document.getElementById("po-trend");
  if (trendEl) {
    const trend = new Chart(trendEl, {
      type: "line",
      data: {
        labels: data.trend.labels,
        datasets: data.trend.datasets.map((ds, i) => ({
          label: ds.label, data: ds.data, borderColor: PL.palette[i % PL.palette.length],
          backgroundColor: PL.palette[i % PL.palette.length], spanGaps: true, tension: 0,
          borderDash: i >= PL.palette.length ? [5, 3] : [],   // 9th line onwards: dashed, so colours never repeat alone
        })),
      },
      options: {
        maintainAspectRatio: false,
        scales: { y: { min: 0, max: 100 } },
        plugins: { tooltip: { callbacks: { label: (ctx) => ctx.dataset.label + ": " + PL.formatScore(ctx.raw) } } },
      },
    });
    const select = document.getElementById("trend-po");
    if (select) {
      select.addEventListener("change", () => {
        trend.data.datasets.forEach((_, i) => trend.setDatasetVisibility(i, select.value === "all" || String(i) === select.value));
        trend.update();
      });
    }
  }
};
```

### Tests

```python
# apps/reports/tests/test_summary.py
from decimal import Decimal
from types import SimpleNamespace

from apps.reports.summary import plain_language_summary
from apps.scoring.engine import Edge, OfferingInputs, compute_student_profile

D = Decimal
POS = [SimpleNamespace(id=f"po{n}", number=n, short_name=name)
       for n, name in [(1, "Maths"), (2, "Problem solving"), (3, "Communication")]]


def offering(offering_id, grade, links):
    return OfferingInputs(
        offering_id=offering_id, grades={1: D(grade)}, max_scores={1: D(100)},
        assessment_lo_edges=(Edge(1, "lo", D(100)),),
        lo_po_edges=tuple(Edge("lo", po, D(w)) for po, w in links),
    )


def test_no_published_grades():
    profile = compute_student_profile([])
    assert plain_language_summary(profile, POS)[0].startswith("No published grades count")


def test_strongest_and_missing_evidence():
    profile = compute_student_profile([offering(1, "88.44", [("po2", 5)]), offering(2, 70, [("po1", 3)])])
    lines = plain_language_summary(profile, POS, threshold=D(60))

    assert lines[0] == "Your strongest outcome is PO 2 (Problem solving, 88.4)."
    assert lines[1] == "PO 3 has no evidence yet: none of your graded courses link to it so far."
    assert lines[2] == "Every outcome with evidence is at or above the program's threshold of 60.0."


def test_least_evidence_and_below_threshold():
    profile = compute_student_profile([
        offering(1, 90, [("po1", 3), ("po2", 3), ("po3", 2)]),
        offering(2, 40, [("po1", 3), ("po2", 3)]),
    ])
    lines = plain_language_summary(profile, POS, threshold=D(70))

    assert lines[1] == "PO 3 (Communication) has the least evidence so far: 1 course."
    assert lines[2] == "PO 1 and PO 2 are below the program's threshold of 70.0."


def test_tie_on_score_picks_lowest_po_number():
    profile = compute_student_profile([offering(1, 75, [("po1", 2), ("po3", 2)])])
    assert "PO 1 (Maths, 75.0)" in plain_language_summary(profile, POS)[0]
```

```python
# apps/reports/tests/test_trend.py
"""T1.5 AC 2: three terms → three points per PO, each equal to a hand-computed cumulative value."""
import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.catalog.models import Term
from apps.core.tests.factories import (
    AssessmentFactory,
    AssessmentLOWeightFactory,
    CourseFactory,
    EnrollmentFactory,
    GradeFactory,
    LearningOutcomeFactory,
    LOPOWeightFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)
from apps.reports.selectors import student_trend

pytestmark = pytest.mark.django_db


def test_three_term_cumulative_trend():
    program = ProgramFactory(code="TST")
    po_set = ProgramOutcomeSetFactory(program=program, label="2023", effective_from_year=2020, is_active=True)
    po1 = ProgramOutcomeFactory(po_set=po_set, number=1, short_name="Maths", description="x")
    po2 = ProgramOutcomeFactory(po_set=po_set, number=2, short_name="Ethics", description="y")
    student = UserFactory()
    MembershipFactory(user=student, program=program, role="student", cohort_year=2023)
    now = timezone.now()

    # (term start, grade, LO→PO1 weight): hand calculation below
    plan = [(dt.date(2024, 9, 16), 80, 3), (dt.date(2025, 2, 10), 60, 1), (dt.date(2025, 9, 15), 90, 2)]
    for i, (start, grade, weight) in enumerate(plan):
        term = TermFactory(code=f"T{i}", name=f"Term {i}", starts_on=start,
                           ends_on=start + dt.timedelta(days=110), status=Term.Status.CLOSED)
        offering = OfferingFactory(course=CourseFactory(program=program, code=f"CSE 10{i}"), term=term)
        lo = LearningOutcomeFactory(offering=offering, number=1, description="LO 1")
        exam = AssessmentFactory(offering=offering, name="Final", kind="final", max_score=100, published_at=now)
        AssessmentLOWeightFactory(assessment=exam, learning_outcome=lo, weight=100)
        LOPOWeightFactory(learning_outcome=lo, program_outcome=po1, weight=weight)
        enrollment = EnrollmentFactory(offering=offering, student=student)
        GradeFactory(assessment=exam, enrollment=enrollment, score=grade, published_score=grade, published_at=now)

    trend = student_trend(student, [po1, po2])

    # Term 0: 80                          → 80
    # Term 1: (80×3 + 60×1) / 4 = 300/4   → 75
    # Term 2: (240 + 60 + 90×2) / 6 = 480/6 → 80
    assert [t.code for t in trend.terms] == ["T0", "T1", "T2"]
    assert trend.series[po1.id] == [Decimal(80), Decimal(75), Decimal(80)]
    assert trend.series[po2.id] == [None, None, None]        # no evidence is None, never 0 (P12)
```

```python
# apps/reports/tests/test_profile_v2.py
import json
import re

import pytest
from django.urls import reverse

from apps.core.tests.factories import MembershipFactory, UserFactory
from apps.core.tests.scenarios import elif_scenario

pytestmark = pytest.mark.django_db


def chart_data(html):
    match = re.search(r'<script id="profile-chart-data" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(match.group(1))


def table_scores(html):
    return dict(re.findall(r'data-po-score="(\d+)">([^<]*)<', html))


def test_radar_and_table_show_identical_numbers(client):  # T1.5 AC 1
    s = elif_scenario(published=True)
    client.force_login(s.student)
    html = client.get(reverse("student:profile")).content.decode()

    data, table = chart_data(html), table_scores(html)
    assert table["1"] == "85.0" and table["2"] == "82.9"         # the professor's numbers
    for label, value in zip(data["labels"], data["scores"], strict=True):
        number = label.removeprefix("PO ")
        assert table[number] == ("—" if value is None else f"{value:.1f}")


def test_contribution_segments_add_up_to_the_score(client):
    s = elif_scenario(published=True)
    client.force_login(s.student)
    data = chart_data(client.get(reverse("student:profile")).content.decode())

    po1 = data["labels"].index(f"PO {s.po1.number}")
    total = sum(ds["data"][po1] or 0 for ds in data["contributions"])
    assert total == pytest.approx(85.0, abs=0.1 * len(data["contributions"]))


def test_head_sees_same_page_without_drawer(client):
    s = elif_scenario(published=True)
    head = UserFactory()
    MembershipFactory(user=head, program=s.offering.course.program, role="head")
    client.force_login(head)
    html = client.get(reverse("reports:department_student", args=[s.student.pk])).content.decode()

    assert table_scores(html)["1"] == "85.0"
    assert 'id="po-drawer"' not in html


def test_other_student_gets_404(client):
    s = elif_scenario(published=True)
    other = UserFactory()
    MembershipFactory(user=other, program=s.offering.course.program, role="student", cohort_year=2024)
    client.force_login(other)

    assert client.get(reverse("reports:department_student", args=[s.student.pk])).status_code == 404
```

### Check it works

1. With the seed data, log in as Elif Yıldız. At the top: "Your strongest outcome is …" plus one or two more sentences.
2. Hover the radar: the tooltip for PO 1 says the same number as the table. The dashed red ring is at 60.
3. The stacked bars for PO 1 show CSE 311 (2026F) and her earlier courses. Expand "Show as a table" and check that one column adds up to the PO score, give or take 0.1.
4. The trend has three points per line: 2025F, 2026S, 2026F. Pick "PO 1" in *Show* and only that line remains.
5. Press **Tab** until the PO 1 button is focused and press Enter. The drawer opens and lists her contributing LOs (from S3-02).
6. On a phone-sized window (DevTools, 390 px wide), the radar sits above the table and nothing scrolls sideways except the tables.

### Done when

- [ ] T1.5 AC 1 (radar = table): `test_radar_and_table_show_identical_numbers`
- [ ] T1.5 AC 2 (trend = hand calculation): `test_three_term_cumulative_trend`
- [ ] Per-course shares add up to the PO score: `test_shares_always_add_up_to_the_po_score` (Hypothesis, 300 examples), `test_contribution_segments_add_up_to_the_score`
- [ ] Summary sentences: `test_summary.py`
- [ ] B8 AC 3 still holds (other student → 404): `test_other_student_gets_404`
- [ ] Engine coverage still 100% (`uv run pytest apps/scoring --cov=apps.scoring.engine --cov-branch`)

### Commits and PR

```
test: per-course contributions add up to the PO score (red)
engine: split PO scores into per-offering contributions (green)
Add plain-language summary sentences to the student profile
Build profile v2 with radar, contribution and trend charts
```
PR title: **S7-04 Student profile v2: radar, where-it-comes-from bars, trend and summary**

---

## S7-05 · Audit history viewer

**Points:** 3 · **Owner:** Person B · **Branch:** `feature/S7-05-audit-viewer` · **Depends on:** S1-04 (`AuditEvent`, `audit.record`), S2-06 (grade sheet), S3-01 (publish)

### Goal

Every grade change, weight change, setup change and publish has written an `AuditEvent` since Sprint 1 (spec §5.4). Until now, only Django admin could show them. This story adds three ways in:

- an **offering timeline** at `/offerings/<id>/history/`, filterable by type of change and by person;
- a **per-grade history**: right-click a cell on the grade sheet → modal;
- a **program-wide timeline** for the head at `/department/history/`.

Each entry answers *who, when, what, before → after*. Delivers T1.4, AC 1 (75 → 78 plus publish shows two events in order, with the right actor) and AC 2 (instructors only see their own offerings), and the "audit" minute of the demo.

### Design choices

- **Read-only, and built only on what services already record.** No new writes. If an entry looks poor (for example, a matrix save with no before/after), fix the *service* that records it, not the viewer.
- **"Type of change" is derived from the action name prefix.** Actions are dotted names (`grade.update`, `assessment.publish`, `lo_po.update`). A `KINDS` table maps each filter to prefixes, so a new action shows up under the right filter automatically.
- **Readable subjects in one extra query per page, not one per row.** A grade event only stores `entity_id`. `describe_events()` collects the IDs on the current page and loads those grades (with student and assessment) in one query, and the assessments in another. Rows whose object was since deleted fall back to "grade #123".
- **Large diffs are summarised.** A weight matrix save records the whole matrix as one event (spec §5.4). Listing 30 cells in a timeline is noise, so more than 6 changed keys show as "14 values changed". The full JSON stays in admin.
- **The per-grade history includes publish events of that assessment.** A grade's own events (`grade.*`) don't say when the student first saw it. Adding `assessment.publish` / `assessment.unpublish` of the same assessment, oldest first, tells the whole story. AC 1 is phrased exactly like that.
- **Program-wide view includes events with no offering** (term open/close, PO edits, course edits). With one program that is correct. T2.6 (multi-program) has to narrow this, and there's a comment in the code saying so.
- **Pagination: 50 per page**, newest first, links built with `query_transform` so the filters survive paging.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/reports/history.py` | create | `KINDS`, `ACTION_LABELS`, `Change`, `EventView`, `describe_events()` |
| `apps/reports/selectors.py` | modify | `history_events()`, `grade_history()` |
| `apps/reports/forms.py` | create (or modify) | `HistoryFilterForm` |
| `apps/reports/views.py` | modify | `offering_history`, `department_history` |
| `apps/reports/urls.py` | modify | `history`, `department_history` routes |
| `apps/grading/views.py`, `apps/grading/urls.py` | modify | `cell_history` |
| `apps/reports/templates/reports/history.html` | create | page + `timeline` partial |
| `apps/grading/templates/grading/cell_history.html` | create | modal content |
| `apps/grading/templates/grading/sheet.html` | modify | `data-history-url` on each cell, hint text |
| `static/js/polaris.js` | modify | right-click → history modal |
| `apps/reports/tests/test_history.py` | create | tests |
| `apps/accounts/tests/test_permission_matrix.py` | modify | three new URLs |

### Steps

**1. Turning events into readable rows: `apps/reports/history.py`.**

```python
# apps/reports/history.py
"""Readable audit timeline rows (T1.4). Read-only; never writes AuditEvent."""
from dataclasses import dataclass
from functools import reduce
from operator import or_

from django.db.models import Q

from apps.core.models import AuditEvent
from apps.grading.models import Grade
from apps.outcomes.models import Assessment

KINDS: dict[str, tuple[str, ...]] = {
    "grades": ("grade.",),
    "publish": ("assessment.publish", "assessment.unpublish"),
    "weights": ("assessment_lo.", "lo_po."),
    "setup": ("lo.", "assessment.create", "assessment.update", "assessment.delete", "syllabus.",
              "offering.", "enrollment.", "term.", "po.", "po_set.", "course."),
}
KIND_CHOICES = [("", "All changes"), ("grades", "Grades"), ("publish", "Publishing"),
                ("weights", "Weights"), ("setup", "Course setup")]

ACTION_LABELS = {
    "grade.create": "Grade entered",
    "grade.update": "Grade changed",
    "grade.upload": "Grade uploaded from file",
    "assessment.publish": "Assessment published",
    "assessment.unpublish": "Assessment unpublished",
    "assessment.create": "Assessment added",
    "assessment.update": "Assessment edited",
    "assessment.delete": "Assessment deleted",
    "lo.create": "Learning outcome added",
    "lo.update": "Learning outcome edited",
    "lo.delete": "Learning outcome deleted",
    "lo.reorder": "Learning outcomes reordered",
    "assessment_lo.update": "Assessment → LO weights saved",
    "lo_po.update": "LO → PO weights saved",
    "lo_po.accept": "AI-suggested PO weights accepted",
    "syllabus.apply": "Setup applied from syllabus",
    "term.status": "Term status changed",
}
MAX_LISTED_CHANGES = 6


def kind_filter(kind: str) -> Q:
    prefixes = KINDS[kind]
    return reduce(or_, (Q(action__startswith=p) for p in prefixes))


def label_for(action: str) -> str:
    return ACTION_LABELS.get(action) or action.replace(".", " ").replace("_", " ").capitalize()


@dataclass(frozen=True)
class Change:
    field: str
    before: str
    after: str


@dataclass(frozen=True)
class EventView:
    event: AuditEvent
    label: str
    subject: str
    changes: tuple[Change, ...]
    summary: str | None        # set instead of `changes` when too many values changed


def _show(value) -> str:
    if value is None or value == "":
        return "—"
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return str(value)


def _diff(before, after) -> tuple[tuple[Change, ...], str | None]:
    if not isinstance(before, dict) and not isinstance(after, dict):
        return (), None
    b, a = before or {}, after or {}
    keys = [k for k in dict.fromkeys([*b, *a]) if b.get(k) != a.get(k)]
    if len(keys) > MAX_LISTED_CHANGES:
        return (), f"{len(keys)} values changed"
    return tuple(Change(k.replace("_", " "), _show(b.get(k)), _show(a.get(k))) for k in keys), None


def describe_events(events) -> list[EventView]:
    """Rows for one page of events. Two extra queries at most, whatever the page size."""
    events = list(events)
    grade_ids = {e.entity_id for e in events if e.entity_type == "grade"}
    assessment_ids = {e.entity_id for e in events if e.entity_type == "assessment"}
    grades = {g.pk: g for g in Grade.objects.filter(pk__in=grade_ids)
              .select_related("assessment", "enrollment__student")} if grade_ids else {}
    assessments = dict(Assessment.objects.filter(pk__in=assessment_ids).values_list("pk", "name")) \
        if assessment_ids else {}

    rows = []
    for e in events:
        if e.entity_type == "grade" and e.entity_id in grades:
            g = grades[e.entity_id]
            subject = f"{g.enrollment.student.get_full_name()} · {g.assessment.name}"
        elif e.entity_type == "assessment" and e.entity_id in assessments:
            subject = assessments[e.entity_id]
        elif e.offering_id is not None:
            subject = e.offering.course.code
        else:
            subject = f"{e.entity_type.replace('_', ' ')} #{e.entity_id}"
        changes, summary = _diff(e.before, e.after)
        rows.append(EventView(event=e, label=label_for(e.action), subject=subject,
                              changes=changes, summary=summary))
    return rows
```

**2. Selectors: add to `apps/reports/selectors.py`.**

```python
# apps/reports/selectors.py  (S7-05 additions)
from django.db.models import Q

from apps.accounts.permissions import can_view_offering, is_head
from apps.core.models import AuditEvent
from apps.grading.models import Grade

from .history import kind_filter


def history_events(user, *, offering=None, program=None, kind=None, actor=None):
    """Audit events this user may see, newest first. Scoped to one offering or one program."""
    qs = (AuditEvent.objects.select_related("actor", "offering__course", "offering__term")
          .order_by("-created_at", "-id"))
    if offering is not None:
        if not can_view_offering(user, offering):
            return qs.none()
        qs = qs.filter(offering=offering)
    elif program is not None:
        if not (user.is_superuser or is_head(user, program)):
            return qs.none()
        # Events without an offering (terms, POs, catalog) belong to the program while there is
        # only one. T2.6 must narrow this when a second program arrives.
        qs = qs.filter(Q(offering__course__program=program) | Q(offering__isnull=True))
    else:
        return qs.none()
    if kind:
        qs = qs.filter(kind_filter(kind))
    if actor:
        qs = qs.filter(actor_id=actor)
    return qs


def grade_history(user, assessment, enrollment):
    """One grade cell's story, oldest first: its own events plus publishes of its assessment."""
    if not can_view_offering(user, assessment.offering):
        return AuditEvent.objects.none()
    q = Q(entity_type="assessment", entity_id=assessment.pk,
          action__in=["assessment.publish", "assessment.unpublish"])
    grade = Grade.objects.filter(assessment=assessment, enrollment=enrollment).only("pk").first()
    if grade is not None:
        q |= Q(entity_type="grade", entity_id=grade.pk)
    return AuditEvent.objects.filter(q).select_related("actor", "offering__course").order_by("created_at", "id")
```

**3. The filter form: `apps/reports/forms.py`.**

```python
# apps/reports/forms.py
from django import forms

from apps.accounts.models import User

from .history import KIND_CHOICES


class HistoryFilterForm(forms.Form):
    kind = forms.ChoiceField(label="Type", choices=KIND_CHOICES, required=False)
    actor = forms.ChoiceField(label="Person", required=False)

    def __init__(self, data=None, *, events):
        super().__init__(data)
        people = User.objects.filter(pk__in=events.order_by().values("actor_id")).order_by("last_name", "first_name")
        self.fields["actor"].choices = [("", "Everyone")] + [(str(u.pk), u.get_full_name() or u.email) for u in people]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select form-select-sm"

    def values(self) -> dict:
        """kind / actor for history_events(); invalid input means 'no filter'."""
        if self.is_bound and self.is_valid():
            return {"kind": self.cleaned_data["kind"] or None, "actor": self.cleaned_data["actor"] or None}
        return {"kind": None, "actor": None}
```

**4. Views.**

```python
# apps/reports/views.py  (S7-05 additions)
from django.core.paginator import Paginator

from .forms import HistoryFilterForm
from .history import describe_events
from .selectors import history_events

HISTORY_PAGE_SIZE = 50


def _history_response(request, context, scope_kwargs):
    base = history_events(request.user, **scope_kwargs)
    form = HistoryFilterForm(request.GET or None, events=base)
    events = history_events(request.user, **scope_kwargs, **form.values())
    page = Paginator(events, HISTORY_PAGE_SIZE).get_page(request.GET.get("page"))
    context |= {"form": form, "page": page, "rows": describe_events(page.object_list)}
    template = "reports/history.html#timeline" if request.htmx else "reports/history.html"
    return render(request, template, context)


@login_required
@require_offering_access()
def offering_history(request, *, offering, perms_for, **_):
    return _history_response(request, {"offering": offering, "perms_for": perms_for,
                                       "title": f"History · {offering.course.code} {offering.term.name}"},
                             {"offering": offering})


@login_required
@require_role("head")
def department_history(request):
    program = head_program_or_404(request.user)
    return _history_response(request, {"offering": None, "title": f"History · {program.code} department"},
                             {"program": program})
```

```python
# apps/reports/urls.py  (add)
    path("offerings/<int:offering_id>/history/", views.offering_history, name="history"),
    path("department/history/", views.department_history, name="department_history"),
```

```python
# apps/grading/views.py  (addition)
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.accounts.decorators import require_offering_access
from apps.catalog.models import Enrollment
from apps.outcomes.models import Assessment
from apps.reports.history import describe_events
from apps.reports.selectors import grade_history


@login_required
@require_offering_access()
def cell_history(request, assessment_id, enrollment_id, *, offering, perms_for, **_):
    assessment = get_object_or_404(Assessment, pk=assessment_id, offering=offering)
    enrollment = get_object_or_404(Enrollment.objects.select_related("student"), pk=enrollment_id, offering=offering)
    rows = describe_events(grade_history(request.user, assessment, enrollment))
    return render(request, "grading/cell_history.html",
                  {"assessment": assessment, "enrollment": enrollment, "rows": rows})
```

```python
# apps/grading/urls.py  (add)
    path("offerings/<int:offering_id>/grades/cell/<int:assessment_id>/<int:enrollment_id>/history/",
         views.cell_history, name="cell_history"),
```

**5. Templates.**

```django
{# apps/reports/templates/reports/history.html #}
{% extends "base.html" %}
{% load polaris %}
{% block title %}{{ title }}{% endblock %}
{% block content %}
<h1 class="h3 mb-3">{{ title }}</h1>
<form method="get" class="d-flex flex-wrap align-items-end gap-2 mb-3" aria-label="History filters"
      hx-get="" hx-trigger="change" hx-target="#timeline" hx-swap="outerHTML" hx-push-url="true">
  <div><label for="{{ form.kind.id_for_label }}" class="form-label small mb-0">{{ form.kind.label }}</label>{{ form.kind }}</div>
  <div><label for="{{ form.actor.id_for_label }}" class="form-label small mb-0">{{ form.actor.label }}</label>{{ form.actor }}</div>
  <button type="submit" class="btn btn-sm btn-outline-secondary">Apply</button>
</form>
{% partial timeline %}
{% endblock %}

{% partialdef timeline %}
<div id="timeline">
  {% if rows %}
    <ol class="list-group list-group-flush mb-3" aria-label="Changes, newest first">
      {% for row in rows %}
        <li class="list-group-item px-0">
          <div class="d-flex flex-wrap justify-content-between gap-2">
            <div>
              <strong>{{ row.label }}</strong> · {{ row.subject }}
              {% if not offering and row.event.offering %}<span class="text-body-secondary small">({{ row.event.offering.course.code }}, {{ row.event.offering.term.code }})</span>{% endif %}
            </div>
            <div class="small text-body-secondary text-nowrap">
              {{ row.event.actor.get_full_name|default:"System" }} ·
              <time datetime="{{ row.event.created_at|date:'c' }}">{{ row.event.created_at|date:"j M Y, H:i" }}</time>
            </div>
          </div>
          {% if row.changes %}
            <ul class="list-unstyled small mb-0 mt-1">
              {% for c in row.changes %}
                <li><span class="text-body-secondary">{{ c.field }}:</span> <del>{{ c.before }}</del> → <ins class="text-decoration-none fw-semibold">{{ c.after }}</ins></li>
              {% endfor %}
            </ul>
          {% elif row.summary %}
            <p class="small text-body-secondary mb-0 mt-1">{{ row.summary }}</p>
          {% endif %}
        </li>
      {% endfor %}
    </ol>
    {% if page.has_other_pages %}
      <nav aria-label="History pages">
        <ul class="pagination pagination-sm">
          {% if page.has_previous %}<li class="page-item"><a class="page-link" href="{% query_transform page=page.previous_page_number %}">Newer</a></li>{% endif %}
          <li class="page-item disabled"><span class="page-link">Page {{ page.number }} of {{ page.paginator.num_pages }}</span></li>
          {% if page.has_next %}<li class="page-item"><a class="page-link" href="{% query_transform page=page.next_page_number %}">Older</a></li>{% endif %}
        </ul>
      </nav>
    {% endif %}
  {% else %}
    {% include "includes/empty_state.html" with title="No changes recorded" message="Changes to grades, weights and course setup appear here as soon as someone makes them." only %}
  {% endif %}
</div>
{% endpartialdef %}
```

`hx-get=""` means "this page's URL". HTMX adds the form fields as query parameters, so the filters land in the URL (`hx-push-url`). Changing a filter starts again at page 1, because the form doesn't carry `page`.

```django
{# apps/grading/templates/grading/cell_history.html : rendered into the shared modal (#modal-content) #}
<div class="modal-header">
  <h2 class="modal-title h5">History · {{ enrollment.student.get_full_name }} · {{ assessment.name }}</h2>
  <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
</div>
<div class="modal-body">
  {% if rows %}
    <ol class="list-unstyled mb-0">
      {% for row in rows %}
        <li class="mb-2">
          <div><strong>{{ row.label }}</strong> <span class="small text-body-secondary">by {{ row.event.actor.get_full_name|default:"System" }}, {{ row.event.created_at|date:"j M Y H:i" }}</span></div>
          {% for c in row.changes %}<div class="small">{{ c.field }}: <del>{{ c.before }}</del> → <strong>{{ c.after }}</strong></div>{% endfor %}
          {% if row.summary %}<div class="small text-body-secondary">{{ row.summary }}</div>{% endif %}
        </li>
      {% endfor %}
    </ol>
  {% else %}
    <p class="mb-0 text-body-secondary">No changes recorded for this grade yet.</p>
  {% endif %}
</div>
<div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button></div>
```

In `grading/sheet.html`, inside `{% partialdef cell %}`, add one attribute to the cell's `<td>`. Everything else in the partial stays the same.

```django
<td ... data-history-url="{% url 'grading:cell_history' offering.pk assessment.pk enrollment.pk %}">
```

Under the sheet's heading, add the hint: `<p class="small text-body-secondary">Right-click a cell (or press Shift+F10) to see its history.</p>`

**6. Right-click → modal: add to `static/js/polaris.js`.**

```javascript
/* ---- S7-05 grade cell history ---- */
document.addEventListener("contextmenu", (event) => {
  const cell = event.target.closest("[data-history-url]");
  if (!cell || !window.htmx) return;
  event.preventDefault();
  htmx.ajax("GET", cell.dataset.historyUrl, { target: "#modal-content", swap: "innerHTML" })
    .then(() => bootstrap.Modal.getOrCreateInstance(document.getElementById("modal")).show());
});
```

The keyboard's context-menu key and Shift+F10 fire the same `contextmenu` event on the focused input. Keyboard users therefore get the history too (S7-07 checks this).

**7. Permission matrix.** `reports:history`, `reports:department_history` and `grading:cell_history` already have rows in `ROUTES` (S2-02, `story="S7-05"`): `OFFERING_STAFF`, `HEAD` and `OFFERING_STAFF` (HTMX) respectively. They switch on once the URLs exist; nothing to add.

### Tests

```python
# apps/reports/tests/test_history.py
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.core import audit
from apps.core.tests.factories import GradeFactory, MembershipFactory, UserFactory
from apps.core.tests.scenarios import elif_scenario
from apps.grading.services import publish_assessment, save_grade
from apps.reports.history import describe_events
from apps.reports.selectors import grade_history, history_events

pytestmark = pytest.mark.django_db


@pytest.fixture
def s():
    s = elif_scenario(published=False)
    s.teacher = UserFactory(first_name="Can", last_name="Aydın")
    s.offering.instructors.add(s.teacher)
    MembershipFactory(user=s.teacher, program=s.offering.course.program, role="instructor")
    s.enrollment = s.offering.enrollments.get(student=s.student)
    return s


def test_change_then_publish_shows_two_events_in_order(s, client):  # T1.4 AC 1
    grade = s.midterm.grades.get(enrollment=s.enrollment)
    grade.score = Decimal("75")
    grade.save()                                   # starting value: set directly, no audit event

    save_grade(s.teacher, s.midterm, s.enrollment, "78")
    publish_assessment(s.teacher, s.midterm)

    events = list(grade_history(s.teacher, s.midterm, s.enrollment))
    assert [e.action for e in events] == ["grade.update", "assessment.publish"]
    assert all(e.actor == s.teacher for e in events)

    row = describe_events(events)[0]
    assert row.subject == f"{s.student.get_full_name()} · {s.midterm.name}"
    score = next(c for c in row.changes if c.field == "score")
    assert Decimal(score.before) == 75 and Decimal(score.after) == 78

    client.force_login(s.teacher)
    url = reverse("grading:cell_history", args=[s.offering.pk, s.midterm.pk, s.enrollment.pk])
    html = client.get(url).content.decode()
    assert html.index("Grade changed") < html.index("Assessment published")
    assert "by Can Aydın" in html


def test_other_instructor_sees_nothing(s, client):  # T1.4 AC 2
    save_grade(s.teacher, s.midterm, s.enrollment, "70")
    stranger = UserFactory()
    MembershipFactory(user=stranger, program=s.offering.course.program, role="instructor")

    assert not history_events(stranger, offering=s.offering).exists()
    assert not grade_history(stranger, s.midterm, s.enrollment).exists()
    client.force_login(stranger)
    assert client.get(reverse("reports:history", args=[s.offering.pk])).status_code == 404


def test_kind_and_actor_filters(s):
    save_grade(s.teacher, s.midterm, s.enrollment, "70")
    publish_assessment(s.teacher, s.midterm)
    other = UserFactory()
    audit.record(other, "lo.update", s.lo1, before={"description": "a"}, after={"description": "b"},
                 offering=s.offering)

    grades = history_events(s.teacher, offering=s.offering, kind="grades")
    assert {e.action for e in grades} == {"grade.update"}
    publishes = history_events(s.teacher, offering=s.offering, kind="publish")
    assert {e.action for e in publishes} == {"assessment.publish"}
    by_other = history_events(s.teacher, offering=s.offering, actor=str(other.pk))
    assert [e.action for e in by_other] == ["lo.update"]


def test_big_diffs_are_summarised(s):
    before = {f"c{i}": "1" for i in range(10)}
    after = {f"c{i}": "2" for i in range(10)}
    audit.record(s.teacher, "lo_po.update", s.offering, before=before, after=after, offering=s.offering)

    row = describe_events(history_events(s.teacher, offering=s.offering))[0]
    assert row.label == "LO → PO weights saved"
    assert row.changes == ()
    assert row.summary == "10 values changed"


def test_department_history_for_head_only(s, client):
    save_grade(s.teacher, s.midterm, s.enrollment, "70")
    head = UserFactory()
    MembershipFactory(user=head, program=s.offering.course.program, role="head")

    client.force_login(head)
    page = client.get(reverse("reports:department_history")).content.decode()
    assert "Grade changed" in page
    assert s.offering.course.code in page

    client.force_login(s.teacher)
    assert client.get(reverse("reports:department_history")).status_code == 404


def test_htmx_filter_returns_timeline_only(s, client):
    save_grade(s.teacher, s.midterm, s.enrollment, "70")
    client.force_login(s.teacher)
    html = client.get(reverse("reports:history", args=[s.offering.pk]), {"kind": "publish"},
                      headers={"HX-Request": "true"}).content.decode()

    assert html.lstrip().startswith('<div id="timeline">')
    assert "No changes recorded" in html


def test_page_query_count_is_constant(s, client, django_assert_max_num_queries):
    for i in range(60):
        enrollment_grade = GradeFactory(assessment=s.project, score=i)
        audit.record(s.teacher, "grade.update", enrollment_grade, before={"score": None},
                     after={"score": str(i)}, offering=s.offering)
    client.force_login(s.teacher)

    with django_assert_max_num_queries(12):
        response = client.get(reverse("reports:history", args=[s.offering.pk]))
    assert response.status_code == 200
```

Two notes on the tests:

- `GradeFactory(assessment=s.project, …)` creates a grade with a new enrollment. Whether that enrollment's offering matches doesn't matter here: we're counting queries, not testing grading rules.
- The test sets 12 queries as the budget: session, user, membership, the offering lookup in the decorator, the actor dropdown, the count and the page of events, grades and assessments, plus a little headroom. Measure it once on your machine with `--ds config.settings.test -s` and lower the budget to what you see plus 2.

### Check it works

1. Seed, then log in as Dr. Can Aydın. On the CSE 311 grade sheet, change one grade and publish that assessment.
2. Right-click that cell: the modal shows "Grade changed old → new by Can Aydın" and then "Assessment published". Close it, focus another cell with the keyboard, press Shift+F10: the modal opens for that cell.
3. Open **History** on the offering. Filter *Type = Grades*: the URL gains `?kind=grades` and only grade entries remain. Click **Older**: page 2 keeps the filter.
4. Log in as Prof. Deniz Kara and open `/department/history/`: you see Can's changes, each tagged with its course.
5. As a different instructor, open `/offerings/<CSE 311 id>/history/`: you get the 404 page.

### Done when

- [ ] T1.4 AC 1 (75 → 78 + publish = two ordered events with the right actor): `test_change_then_publish_shows_two_events_in_order`
- [ ] T1.4 AC 2 (instructors see only their own offerings): `test_other_instructor_sees_nothing` + matrix rows
- [ ] Filters and pagination keep each other: `test_kind_and_actor_filters`, manual check 3
- [ ] Bounded queries per page: `test_page_query_count_is_constant`
- [ ] Head program view: `test_department_history_for_head_only`

### Commits and PR

```
Describe audit events as readable timeline rows
Add offering and department history pages with filters
Show a grade's history in a modal on right-click
```
PR title: **S7-05 Audit history: offering timeline, per-grade history, department view**

---

## S7-06 · Playwright smoke tests: three golden paths

**Points:** 3 · **Owner:** Person A · **Branch:** `feature/S7-06-e2e` · **Depends on:** everything above. Step 1 can merge on day 1.

### Goal

Three tests drive a real Chromium browser against a real Django server, the way the graders will use the product:

1. **Instructor** sets up an empty course, maps it, types grades and publishes; the student then sees the grade.
2. **Student** (Elif) sees PO 1 = 85.0 and PO 2 = 82.9 and opens the "where does this come from" drawer.
3. **Head** exports the department report and gets a real PDF.

They run nightly on GitHub Actions and before every release PR into `main`, not on every PR: they take about a minute and need a browser. Unit and view tests stay the fast safety net. These three catch what those can't: broken JavaScript, a missing CSRF header on an HTMX request, a template that renders but can't be clicked. Delivers the spec §9.8 "End-to-end" row.

### Design choices

- **pytest-playwright + pytest-django's `live_server`.** `live_server` starts Django in a background thread on a free port, against the test database. Playwright drives Chromium against it. Test data is created with our normal factories in the test itself, so each test reads top to bottom.
- **`transaction=True` databases.** The browser's requests run in the server thread on a different database connection. They can only see data the test has **committed**. A normal `django_db` test wraps everything in a transaction that is never committed, so the server would see an empty database.
- **`DJANGO_ALLOW_ASYNC_UNSAFE=true` in the e2e `conftest.py` only.** Playwright's sync API runs an asyncio event loop in the test thread. Django then refuses ORM calls from that thread ("You cannot call this from an async context"), even though they're perfectly safe here. The variable switches that check off for these tests only.
- **Find elements by accessible name, never by CSS class.** `get_by_label("Midterm I to LO 1")` survives a redesign. `.cell-input:nth-child(3)` does not. It also means the e2e tests fail when we break accessibility, which is what S7-07 wants. Step 1 gives every grid cell and button the name the tests use. This is a real fix: before it, a screen-reader user heard "edit text, blank" eighty times on the grade sheet.
- **Celery runs eagerly in tests** (`config/settings/test.py`). So the export is built inside the request, and the Download button is already there when the response arrives. No sleeping and no polling in tests.
- **Traces on failure.** `--tracing=retain-on-failure` saves a Playwright trace (screenshots, DOM snapshots, network) for every failed test. CI uploads it. Open it locally with `uv run playwright show-trace trace.zip` to see exactly what the browser saw.
- **Marker `e2e`, excluded by default.** `uv run pytest` stays fast. `uv run pytest -m e2e` runs only these.

### Files

| Path | Create / modify | What |
|---|---|---|
| `apps/outcomes/templates/outcomes/mapping.html` | modify | accessible names on grids and cells |
| `apps/grading/templates/grading/sheet.html` | modify | accessible names on cells and publish buttons |
| `pyproject.toml` | modify | `e2e` marker, default exclusion |
| `e2e/__init__.py`, `e2e/conftest.py` | create | fixtures, login helper |
| `e2e/test_golden_paths.py` | create | the three tests |
| `.github/workflows/e2e.yml` | create | nightly + manual + release PRs |

### Steps

**1. Accessible names (merge this first; S7-07 builds on it).**

Make these exact changes in the earlier templates. The names are the contract with the tests.

| Template | Element | Add |
|---|---|---|
| `outcomes/mapping.html` | the Assessment→LO `<form>` | `aria-label="Assessment to LO weights"` |
| `outcomes/mapping.html` | each Assessment→LO `<input>` | `aria-label="{{ assessment.name }} to LO {{ lo.number }}"` |
| `outcomes/mapping.html` | the LO→PO `<form>` | `aria-label="LO to PO weights"` |
| `outcomes/mapping.html` | each LO→PO `<input>` | `aria-label="LO {{ lo.number }} to PO {{ po.number }}"` |
| `outcomes/mapping.html` | each grid's submit button | visible text exactly `Save` |
| `grading/sheet.html` (`cell` partial) | the score `<input>` | `aria-label="{{ enrollment.student.get_full_name }}, {{ assessment.name }}"` |
| `grading/sheet.html` | each column's publish button | `aria-label="Publish {{ assessment.name }}"` (visible text can stay "Publish") |
| `grading/` publish confirm modal | confirm button | visible text exactly `Publish` |
| `outcomes/lo_form.html`, `outcomes/assessment_form.html` | submit button | visible text exactly `Save` |

Labels on ordinary form fields come from Django: `AssessmentForm` gives "Name", "Kind", "Max score", "Course weight" and "Due date", as long as the template renders `<label for=…>` (`{{ field.label_tag }}` does). The login template's button must read "Log in".

**2. Register the marker in `pyproject.toml`.**

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py"]
addopts = "-ra --strict-markers -m 'not e2e'"
markers = [
    "e2e: browser tests against a live server (run with: uv run pytest -m e2e)",
]
```

A later `-m` on the command line replaces the one in `addopts`, so `uv run pytest -m e2e` selects exactly the browser tests.

**3. Fixtures: `e2e/conftest.py`.** (Also create an empty `e2e/__init__.py`.)

```python
# e2e/conftest.py
import os
import re

import pytest

# Playwright's sync API runs an event loop in this thread; Django would otherwise refuse ORM calls.
# Safe here: tests and the live server use separate connections and never share a transaction.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

PASSWORD = "e2e-Password-123"  # noqa: S105  test-only credential


@pytest.fixture(autouse=True)
def _e2e_settings(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path          # exports and uploads never touch the repo
    settings.DEBUG = False


@pytest.fixture
def make_login(live_server):
    """login(page, user): sets a known password and logs in through the real form."""
    def login(page, user):
        user.set_password(PASSWORD)
        user.save(update_fields=["password"])
        page.goto(f"{live_server.url}/login/")
        page.get_by_label(re.compile("email", re.I)).fill(user.email)
        page.get_by_label("Password", exact=True).fill(PASSWORD)
        page.get_by_role("button", name=re.compile("log in", re.I)).click()
        page.wait_for_url(lambda url: "/login/" not in url)
    return login
```

**4. The tests: `e2e/test_golden_paths.py`.**

```python
# e2e/test_golden_paths.py
"""Three golden paths in a real browser (spec §9.8). Run: uv run pytest -m e2e [--headed]"""
import datetime as dt
import re

import pytest
from playwright.sync_api import Page, expect

from apps.catalog.models import Term
from apps.core.tests.factories import (
    CourseFactory,
    EnrollmentFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)
from apps.core.tests.scenarios import elif_scenario
from apps.grading.models import Grade

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def empty_course():
    program = ProgramFactory(code="E2E", name="End to end")
    po_set = ProgramOutcomeSetFactory(program=program, label="2023", effective_from_year=2020, is_active=True)
    for n, name in [(1, "Maths"), (2, "Problem solving")]:
        ProgramOutcomeFactory(po_set=po_set, number=n, short_name=name, description=f"{name} outcome")
    term = TermFactory(code="2026F", name="Fall 2026", starts_on=dt.date(2026, 9, 14),
                       ends_on=dt.date(2027, 1, 22), status=Term.Status.OPEN)
    offering = OfferingFactory(course=CourseFactory(program=program, code="CSE 311", title="Software"), term=term)
    teacher = UserFactory(first_name="Can", last_name="Aydın", email="can@e2e.test")
    offering.instructors.add(teacher)
    MembershipFactory(user=teacher, program=program, role="instructor")
    students = []
    for first, last, email in [("Elif", "Yıldız", "elif@e2e.test"), ("Mert", "Kaya", "mert@e2e.test")]:
        student = UserFactory(first_name=first, last_name=last, email=email)
        MembershipFactory(user=student, program=program, role="student", cohort_year=2024)
        EnrollmentFactory(offering=offering, student=student)
        students.append(student)
    return offering, teacher, students


def save_form(page: Page, form_name: str, url_part: str):
    form = page.get_by_role("form", name=form_name)
    with page.expect_response(lambda r: url_part in r.url and r.request.method == "POST") as response:
        form.get_by_role("button", name="Save").click()
    assert response.value.status < 400


def test_instructor_sets_up_maps_grades_and_publishes(page: Page, live_server, make_login, browser):
    offering, teacher, (elif_, mert) = empty_course()
    base = f"{live_server.url}/offerings/{offering.pk}"
    make_login(page, teacher)

    # Learning outcomes
    for text in ["Design software with patterns", "Work in an agile team"]:
        page.goto(f"{base}/setup/los/new/")
        page.get_by_label("Description").fill(text)
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text(text)).to_be_visible()

    # Assessments
    for name, kind, weight in [("Midterm I", "Midterm", "60"), ("Project", "Project", "40")]:
        page.goto(f"{base}/setup/assessments/new/")
        page.get_by_label("Name").fill(name)
        page.get_by_label("Kind").select_option(label=kind)
        page.get_by_label("Max score").fill("100")
        page.get_by_label("Course weight").fill(weight)
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_text(name).first).to_be_visible()

    # Both weight grids: the professor's example (spec §2.2)
    page.goto(f"{base}/mapping/")
    for label, value in [("Midterm I to LO 1", "60"), ("Project to LO 1", "40"),
                         ("Midterm I to LO 2", "40"), ("Project to LO 2", "100")]:
        page.get_by_label(label).fill(value)
    save_form(page, "Assessment to LO weights", "/mapping/assessment-lo/")
    for label, value in [("LO 1 to PO 1", "4"), ("LO 2 to PO 1", "2"), ("LO 2 to PO 2", "5")]:
        page.get_by_label(label).fill(value)
    save_form(page, "LO to PO weights", "/mapping/lo-po/")

    # Grades: each cell saves on change (HTMX); Tab triggers the change event
    page.goto(f"{base}/grades/")
    for student, assessment, value in [(elif_, "Midterm I", "90"), (elif_, "Project", "80"),
                                       (mert, "Midterm I", "70"), (mert, "Project", "65")]:
        cell = page.get_by_label(f"{student.get_full_name()}, {assessment}")
        with page.expect_response(lambda r: "/grades/cell/" in r.url) as response:
            cell.fill(value)
            cell.press("Tab")
        assert response.value.status == 200

    # Publish Midterm I through the confirmation modal
    page.get_by_role("button", name="Publish Midterm I").click()
    modal = page.locator(".modal.show")
    expect(modal).to_be_visible()
    modal.get_by_role("button", name="Publish").click()
    expect(page.get_by_text(re.compile(r"Midterm I published to 2 students"))).to_be_visible()

    published = Grade.objects.filter(assessment__offering=offering, assessment__name="Midterm I",
                                     published_score__isnull=False).count()
    assert published == 2

    # The student sees the midterm, but not the unpublished project grade
    student_page = browser.new_context().new_page()
    make_login(student_page, elif_)
    student_page.goto(f"{live_server.url}/me/courses/{offering.pk}/")
    midterm_row = student_page.get_by_role("row", name=re.compile("Midterm I"))
    expect(midterm_row).to_contain_text(re.compile(r"90(\.0)?"))
    expect(student_page.get_by_role("row", name=re.compile("Project"))).to_contain_text("Not published yet")


def test_student_sees_po_profile_and_where_it_comes_from(page: Page, live_server, make_login):
    s = elif_scenario(published=True)
    make_login(page, s.student)
    page.goto(f"{live_server.url}/me/")

    expect(page.locator('[data-po-score="1"]')).to_have_text("85.0")
    expect(page.locator('[data-po-score="2"]')).to_have_text("82.9")
    expect(page.get_by_role("img", name=re.compile("Radar chart"))).to_be_visible()

    page.get_by_role("button", name=re.compile(r"^PO 1: where this number comes from")).click()
    drawer = page.locator("#po-drawer")
    expect(drawer).to_be_visible()
    expect(drawer).to_contain_text(s.offering.course.code)


def test_head_exports_department_pdf(page: Page, live_server, make_login):
    s = elif_scenario(published=True)
    head = UserFactory(first_name="Deniz", last_name="Kara")
    MembershipFactory(user=head, program=s.offering.course.program, role="head")
    make_login(page, head)
    page.goto(f"{live_server.url}/department/")
    expect(page.get_by_role("heading", name=re.compile("Coverage heat map"))).to_be_visible()

    page.get_by_role("button", name="Export PDF").click()
    download_link = page.get_by_role("link", name="Download PDF")
    expect(download_link).to_be_visible(timeout=30_000)
    with page.expect_download() as info:
        download_link.click()

    download = info.value
    assert download.suggested_filename.endswith(".pdf")
    with open(download.path(), "rb") as fh:
        assert fh.read(5) == b"%PDF-"
```

A note on `get_by_role("form", name=…)`: a `<form>` only counts as a "form" landmark when it has an accessible name. That's why step 1 gives the grid forms an `aria-label`.

**5. Run locally.**

```bash
uv run playwright install chromium          # once per machine, ~150 MB
uv run pytest -m e2e                         # headless, ~60 s
uv run pytest -m e2e --headed --slowmo 300   # watch it click
uv run pytest -m e2e --tracing retain-on-failure && uv run playwright show-trace test-results/*/trace.zip
```

On macOS, the export test also needs `brew install pango` (WeasyPrint).

**6. Nightly CI: `.github/workflows/e2e.yml`.**

```yaml
name: E2E

on:
  schedule:
    - cron: "0 1 * * *"          # 04:00 Istanbul, every night
  workflow_dispatch:              # "Run workflow" button
  pull_request:
    branches: [main]              # every release PR (develop → main)

concurrency:
  group: e2e-${{ github.ref }}
  cancel-in-progress: true

jobs:
  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_USER: polaris
          POSTGRES_PASSWORD: polaris
          POSTGRES_DB: polaris
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U polaris"
          --health-interval 5s --health-timeout 5s --health-retries 10
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    env:
      DJANGO_SETTINGS_MODULE: config.settings.test
      DATABASE_URL: postgres://polaris:polaris@localhost:5432/polaris
      REDIS_URL: redis://localhost:6379/0
      SECRET_KEY: ci-not-a-secret
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10
      - run: uv sync --locked
      - name: WeasyPrint system libraries and fonts
        run: sudo apt-get update && sudo apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core
      - name: Chromium for Playwright
        run: uv run playwright install --with-deps chromium
      - name: Collect static files for the live server
        run: uv run python manage.py collectstatic --noinput
      - name: Browser tests
        run: uv run pytest -m e2e --tracing retain-on-failure --junitxml=e2e-junit.xml
      - uses: actions/upload-artifact@v7
        if: failure()
        with:
          name: playwright-traces
          path: test-results/
          retention-days: 7
      - uses: actions/upload-artifact@v7
        if: always()
        with:
          name: e2e-junit
          path: e2e-junit.xml
```

Add `E2E` as a **required check on `main` only** (Settings → Branches → rule for `main`). PRs into `develop` don't wait for it. A release can't go out with a broken golden path. Screenshot the first green nightly run for the CSE 311 report (Section 5, CI/CD run summaries).

### Check it works

1. `uv run pytest` (no marker) still runs the normal suite in the same time as before. The summary line shows "3 deselected".
2. `uv run pytest -m e2e --headed`: you watch Chromium log in, fill the grids, publish, log in as Elif and see 90, then the profile and the PDF download. 3 passed.
3. Break something on purpose: remove `aria-label` from one grade cell. The first test fails with "waiting for get_by_label(…)", and `test-results/` holds a trace showing the page. Put it back.
4. On GitHub: Actions → E2E → *Run workflow* on `develop`: green in about 4 minutes.

### Done when

- [ ] Three golden paths pass locally and in Actions: `e2e/test_golden_paths.py`
- [ ] Every grid cell, grade cell and publish button has an accessible name (step 1 table)
- [ ] `uv run pytest` excludes e2e; `-m e2e` selects only e2e
- [ ] Nightly workflow green at least once; trace artifact uploaded on failure; required on `main`

### Commits and PR

```
Give grid cells and publish buttons accessible names
Exclude browser tests from the default pytest run
Add Playwright golden-path tests for instructor, student and head
Run end-to-end tests nightly and on release PRs
```
PR title: **S7-06 End-to-end tests for the three golden paths**

---

## S7-07 · Accessibility and performance pass

**Points:** 2 · **Owner:** Person C · **Branch:** `feature/S7-07-a11y-perf` · **Depends on:** S7-01 to S7-06 merged (this audits the finished pages)

### Goal

Before we call the product feature complete, the five pages graders will see are checked against a written bar, the problems are fixed, and the results are recorded as evidence. Spec §8.2 promised WCAG AA contrast, full keyboard use, labelled fields and phone-friendly student pages. T1.6 AC 3 promised the dashboard in under 1.5 s. This story proves both and leaves three kinds of evidence behind:

1. an automated accessibility test (axe-core) in the nightly e2e run;
2. query-budget tests in the normal suite;
3. Lighthouse reports in `docs/process/sprint-07/`.

### The bar

| Page | URL | Lighthouse Accessibility | Lighthouse Performance | Query budget | Server time on staging |
|---|---|---|---|---|---|
| Login | `/login/` | ≥ 95 | ≥ 90 (mobile) | — | < 200 ms |
| Student profile | `/me/` | ≥ 95 | ≥ 85 (mobile) | ≤ 35 | < 800 ms |
| Grade sheet (80 × 6) | `/offerings/<id>/grades/` | ≥ 95 | ≥ 90 (desktop) | ≤ 12 | < 1 s (B6 AC 3) |
| Mapping | `/offerings/<id>/mapping/` | ≥ 95 | ≥ 90 (desktop) | ≤ 15 | < 500 ms |
| Department dashboard | `/department/` | ≥ 95 | ≥ 90 (desktop) | ≤ 40 | < 1.5 s (T1.6 AC 3) |

Why these numbers:

- **95 for accessibility.** It leaves room for one minor finding we decide to accept and write down. 100 often depends on third-party markup we don't control.
- **85 on mobile for the profile.** Chart.js on a throttled phone is the one heavy thing we ship on that page, and it's worth it.
- **Query budgets.** Measured on the S7-07 test dataset plus about 20% headroom. They exist to catch an N+1 query, not to squeeze out the last query.

### Steps

**1. Fixes in `templates/base.html`.**

Check each of these. Most were done in S1-09; add whatever is missing. **Don't paste this over the file.** It shows only the skeleton S7-07 checks. Keep everything else S1-09 and S2-01 put there: the theme script in `<head>`, `{% block head %}`, `{% block breadcrumbs %}`, and the shared `#modal`. The one real change is the `chart_js` block: its default becomes **empty** (S1-09 loaded Chart.js there on every page), and pages with charts fill it.

```django
<!doctype html>
<html lang="en" data-bs-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}POlaris{% endblock %} · POlaris</title>
  {% load static %}
  <link rel="stylesheet" href="{% static 'vendor/bootstrap.min.css' %}">
  <link rel="stylesheet" href="{% static 'css/polaris.css' %}">
</head>
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
  <a class="visually-hidden-focusable btn btn-primary position-absolute m-2" href="#main">Skip to content</a>
  {% include "includes/navbar.html" %}
  <main id="main" class="container-xl py-4" tabindex="-1">
    {% block content %}{% endblock %}
  </main>
  <div class="toast-container position-fixed bottom-0 end-0 p-3" aria-live="polite" aria-atomic="true">
    {% for message in messages %}{% include "includes/toast.html" with message=message only %}{% endfor %}
  </div>
  <div class="modal fade" id="modal" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-lg modal-dialog-scrollable"><div class="modal-content" id="modal-content"></div></div>
  </div>
  <script src="{% static 'vendor/bootstrap.bundle.min.js' %}" defer></script>
  <script src="{% static 'vendor/htmx.min.js' %}" defer></script>
  {% block chart_js %}{% endblock %}
  <script src="{% static 'js/polaris.js' %}" defer></script>
  {% block scripts %}{% endblock %}
</body>
</html>
```

What changed, and why:

- **Skip link and `<main id="main">`.** Keyboard users jump past the navbar.
- **`lang="en"`.** Screen readers pick the right voice. T2.5 switches it per request.
- **The toast container is `aria-live`.** "Midterm I published to 84 students" is read out.
- **`defer` on every script.** HTML renders before scripts run. This is the biggest Lighthouse performance win, and it is safe because our inline chart code runs on `DOMContentLoaded`, which fires after deferred scripts.
- **Chart.js loads only on pages with charts.** It's the heaviest file we ship, and the grade sheet doesn't need it. Pages with charts (profile, department, results) add this:

```django
{% block chart_js %}<script src="{% static 'vendor/chart.umd.min.js' %}" defer></script>{% endblock %}
```

**2. CSS fixes in `static/css/polaris.css`.**

```css
/* S7-07: visible focus everywhere (Bootstrap's is faint on table inputs) */
:focus-visible { outline: 3px solid var(--pl-accent); outline-offset: 2px; }
.table input:focus-visible { outline-offset: -2px; }

/* respect "reduce motion": no chart animations, no smooth scrolling */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
}
```

And in `polaris.js`, before any chart is created:

```javascript
/* ---- S7-07: charts honour "reduce motion" ---- */
if (window.Chart && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  Chart.defaults.animation = false;
}
```

`polaris.js` is deferred after Chart.js, so `window.Chart` exists when this runs on chart pages.

**3. The checklist: work through it page by page.** Record each finding and its fix in `docs/process/sprint-07/a11y.md`.

| # | Check | How | Typical fix |
|---|---|---|---|
| 1 | Every input has a name | axe (step 4), or DevTools → Accessibility pane | `<label for>` or `aria-label` (S7-06 step 1) |
| 2 | Keyboard only: reach and use everything | Unplug the mouse. Tab through each page. Enter/Space activate. Esc closes modals. Shift+F10 on a grade cell | `<button>` instead of clickable `<div>`; no `tabindex` > 0 |
| 3 | Focus is visible | Tab and watch | `:focus-visible` rule (step 2) |
| 4 | Contrast ≥ 4.5:1 text, ≥ 3:1 large text and UI | Lighthouse; DevTools colour picker shows the ratio | Darken the token in `polaris.css`; heat levels 3–4 use white text |
| 5 | Colour is never the only signal | Look at the page in DevTools → Rendering → "Emulate vision deficiencies: achromatopsia" | Add ✓ / ✗ / ⚠ / text labels |
| 6 | Charts have a text alternative | Every `<canvas>` has `role="img"` + `aria-label`, and a table version | S7-04 already did it; check results and dashboard charts too |
| 7 | Headings in order, one `<h1>` | axe `heading-order`; HeadingsMap extension | Fix levels, not font sizes |
| 8 | Tables have headers | `<th scope="col">` / `<th scope="row">`, `<caption>` | As in S7-01/S7-02 templates |
| 9 | HTMX updates are announced | Status partials have `role="status"` / `aria-live` | Export status, job status, dashboard label |
| 10 | Phone width works (student pages) | DevTools device toolbar at 390 px | `table-responsive`; stack columns with `col-lg-*` |
| 11 | Zoom 200% works | Ctrl/Cmd + until 200% | No fixed widths in px on containers |
| 12 | Page titles are unique | Look at the tab text | `{% block title %}` on every page |

**4. Automated accessibility test: `e2e/test_accessibility.py`.**

[axe-core](https://github.com/dequelabs/axe-core) is the engine behind Lighthouse's accessibility audit. We load it into the page and fail the nightly run on any **serious** or **critical** violation. Minor findings are written to the test output for us to triage.

```python
# e2e/test_accessibility.py
"""axe-core on the key pages (S7-07). Fails on serious/critical violations."""
import pytest
from playwright.sync_api import Page

from apps.core.tests.factories import MembershipFactory, UserFactory
from apps.core.tests.scenarios import elif_scenario

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

AXE_URL = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js"
RULESET = {"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}}


def axe_violations(page: Page) -> list[dict]:
    page.add_script_tag(url=AXE_URL)
    result = page.evaluate("async (options) => await axe.run(document, options)", RULESET)
    for v in result["violations"]:
        print(f"[{v['impact']}] {v['id']}: {v['help']} ({len(v['nodes'])} nodes) {v['helpUrl']}")
    return [v for v in result["violations"] if v["impact"] in ("serious", "critical")]


@pytest.fixture
def scenario():
    s = elif_scenario(published=True)
    s.teacher = UserFactory()
    s.offering.instructors.add(s.teacher)
    MembershipFactory(user=s.teacher, program=s.offering.course.program, role="instructor")
    s.head = UserFactory()
    MembershipFactory(user=s.head, program=s.offering.course.program, role="head")
    return s


def test_login_page(page: Page, live_server):
    page.goto(f"{live_server.url}/login/")
    assert axe_violations(page) == []


def test_student_profile(page: Page, live_server, make_login, scenario):
    make_login(page, scenario.student)
    page.goto(f"{live_server.url}/me/")
    assert axe_violations(page) == []


@pytest.mark.parametrize("path", ["grades", "mapping", "results", "history"])
def test_instructor_pages(page: Page, live_server, make_login, scenario, path):
    make_login(page, scenario.teacher)
    page.goto(f"{live_server.url}/offerings/{scenario.offering.pk}/{path}/")
    assert axe_violations(page) == []


def test_department_dashboard(page: Page, live_server, make_login, scenario):
    make_login(page, scenario.head)
    page.goto(f"{live_server.url}/department/")
    assert axe_violations(page) == []
```

The script comes from a CDN only inside this test, which needs network access in CI anyway. The product itself never loads anything from a CDN (spec §8.2).

**5. Query budgets in the normal suite: `apps/core/tests/test_query_budgets.py`.**

```python
# apps/core/tests/test_query_budgets.py
"""N+1 guard for the five heavy pages (S7-07). Budgets = measured + ~20 %. If a test fails,
look for a loop that queries per row before raising the number."""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.tests.factories import (
    EnrollmentFactory,
    GradeFactory,
    MembershipFactory,
    UserFactory,
)
from apps.core.tests.scenarios import elif_scenario

pytestmark = pytest.mark.django_db


@pytest.fixture
def class_of_40():
    s = elif_scenario(published=True)
    program = s.offering.course.program
    now = timezone.now()
    for i in range(39):
        student = UserFactory()
        MembershipFactory(user=student, program=program, role="student", cohort_year=2024)
        enrollment = EnrollmentFactory(offering=s.offering, student=student)
        for assessment in (s.midterm, s.project):
            value = Decimal(50 + i)
            GradeFactory(assessment=assessment, enrollment=enrollment, score=value,
                         published_score=value, published_at=now)
    s.teacher = UserFactory()
    s.offering.instructors.add(s.teacher)
    MembershipFactory(user=s.teacher, program=program, role="instructor")
    s.head = UserFactory()
    MembershipFactory(user=s.head, program=program, role="head")
    return s


@pytest.mark.parametrize(("url_name", "who", "budget"), [
    ("grading:sheet", "teacher", 12),
    ("outcomes:mapping", "teacher", 15),
    ("reports:results", "teacher", 20),
    ("reports:history", "teacher", 12),
])
def test_offering_pages(client, class_of_40, django_assert_max_num_queries, url_name, who, budget):
    client.force_login(getattr(class_of_40, who))
    url = reverse(url_name, args=[class_of_40.offering.pk])
    with django_assert_max_num_queries(budget):
        assert client.get(url).status_code == 200


def test_student_profile(client, class_of_40, django_assert_max_num_queries):
    client.force_login(class_of_40.student)
    with django_assert_max_num_queries(35):
        assert client.get(reverse("student:profile")).status_code == 200


def test_department_dashboard(client, class_of_40, django_assert_max_num_queries):
    client.force_login(class_of_40.head)
    with django_assert_max_num_queries(40):
        assert client.get(reverse("reports:department")).status_code == 200


def test_grade_sheet_does_not_grow_with_class_size(client, class_of_40, django_assert_num_queries):
    """The real N+1 check: the same number of queries for 40 and for 41 students."""
    client.force_login(class_of_40.teacher)
    url = reverse("grading:sheet", args=[class_of_40.offering.pk])
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as before:
        client.get(url)
    EnrollmentFactory(offering=class_of_40.offering)
    with django_assert_num_queries(len(before.captured_queries)):
        client.get(url)
```

When a budget fails, `pytest -x -k department --ds config.settings.test` prints every query. A run of nearly identical `SELECT … WHERE id = …` lines is the N+1. Fix it with `select_related` / `prefetch_related` or a bulk lookup like `describe_events()`, never by raising the budget.

**6. Lighthouse on staging** (logged-in pages need your session cookie).

1. Log in on staging in Chrome as the right persona. DevTools → Application → Cookies → copy the value of `sessionid`.
2. Run the following, one page at a time (Node 20+ needed, nothing gets installed in the repo):

```bash
SID="paste-sessionid-here"
OUT=docs/process/sprint-07/lighthouse
mkdir -p "$OUT"
npx --yes lighthouse@12.6.0 "https://staging.<host>/me/" \
  --only-categories=performance,accessibility,best-practices \
  --extra-headers="{\"Cookie\":\"sessionid=$SID\"}" \
  --output=html --output=json --output-path="$OUT/me" --quiet
# desktop pages: add --preset=desktop
npx --yes lighthouse@12.6.0 "https://staging.<host>/department/" --preset=desktop \
  --only-categories=performance,accessibility,best-practices \
  --extra-headers="{\"Cookie\":\"sessionid=$SID\"}" \
  --output=html --output=json --output-path="$OUT/department" --quiet
```

3. Never commit the session cookie. The JSON report doesn't contain it, but check with `grep -r sessionid docs/process/sprint-07/` before you push. Log out on staging afterwards, which invalidates the session.
4. Fill in `docs/process/sprint-07/lighthouse.md` with one row per page: the scores before your fixes, the scores after, and what you changed. That table goes straight into the CSE 311 report and the checkpoint slides.

The Chrome DevTools → Lighthouse tab gives the same result with clicks if `npx` is not an option.

**7. Server time on staging.** Use `curl` with the same cookie, five runs per page, and record the median in `lighthouse.md`:

```bash
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "%{time_starttransfer}\n" -b "sessionid=$SID" "https://staging.<host>/department/"
done
```

`time_starttransfer` is the time until the server sends its first byte, which is the server's part. If the dashboard is over 1.5 s (T1.6 AC 3), stop and tell the team at stand-up. The planned fix is T2.3 (precomputed scores), pulled forward from Sprint 8.

### Check it works

1. `uv run pytest apps/core/tests/test_query_budgets.py`: all pass.
2. `uv run pytest -m e2e -k accessibility -s`: no serious or critical violations. Minor ones are printed: triage them in `a11y.md`.
3. Tab from the address bar on `/me/`: the first stop is "Skip to content", Enter moves focus into the page, and every focused element has a visible amber ring.
4. macOS: System Settings → Accessibility → Display → Reduce motion. The profile charts appear without animation.
5. `docs/process/sprint-07/lighthouse/` has HTML and JSON reports for the five pages, and `lighthouse.md` shows every score at or above the bar.

### Done when

- [ ] Lighthouse bar met on the five pages; reports and the before/after table committed
- [ ] axe: no serious or critical violations: `e2e/test_accessibility.py` in the nightly run
- [ ] Query budgets and the N+1 growth test: `test_query_budgets.py`
- [ ] Dashboard server time < 1.5 s on staging (T1.6 AC 3), grade sheet < 1 s (B6 AC 3), recorded in `lighthouse.md`
- [ ] Checklist (step 3) worked through, findings in `a11y.md`

### Commits and PR

```
Add skip link, live regions and deferred scripts to the base layout
Load Chart.js only on pages that draw charts
Respect reduced motion in CSS and charts
Guard heavy pages with query budgets
Run axe-core on key pages in the nightly browser tests
Record Lighthouse results for Sprint 7
```
PR title: **S7-07 Accessibility and performance pass on the five key pages**

---

## Sprint 7 review: what to show on Sunday

1. Run spec §13.3's script end to end on production, with all three personas, without opening admin.
2. Open the latest green **E2E** run in Actions, and `docs/process/sprint-07/lighthouse.md`.
3. Update `velocity.md` with the points actually completed. Anything unfinished moves to the top of Sprint 8 (spec Part 11: carry-overs come before Tier 2).
4. Tag the release: open the `develop` → `main` PR (E2E must be green), merge with a merge commit, then:

```bash
git switch main && git pull
git tag -a v0.7.0 -m "Feature complete: baseline + Tier 1"
git push origin v0.7.0
```

---

## Code map additions

New public names introduced in this chapter. Copy them into spec §4.8 when the stories merge.

| Module | Name | Signature | Purpose |
|---|---|---|---|
| `apps/scoring/aggregates.py` | `MIN_PO_COVERAGE` | `int = 6` | Column total below which a PO is under-covered |
| `apps/scoring/aggregates.py` | `CoverageCell`, `CoverageTotal`, `CoverageRow`, `CoverageMatrix` | frozen dataclasses | Return type of `coverage_matrix` (fields in S7-01) |
| `apps/scoring/aggregates.py` | `program_po_summary`, `attainment_matrix` | add keyword `cohort: int \| None = None` | Cohort filter (S7-02) |
| `apps/scoring/engine.py` | `evidence_offerings` | `(profile) -> dict[po_id, set[offering_id]]` | Offerings that actually fed each PO |
| `apps/scoring/engine.py` | `contribution_by_offering` | `(profile) -> dict[po_id, dict[offering_id, Decimal]]` | Per-course share of a PO score; shares add up to the score |
| `apps/reports/filters.py` | `DashboardFilters`, `DashboardFilterForm` | `DashboardFilters.from_params(program, params)`, `.to_params()`, `.label`, `.terms`; `DashboardFilterForm(data, *, program).filters()` | Dashboard and department-export filters |
| `apps/reports/selectors.py` | `completion_term`, `CompletionRow`, `completion_rows` | `() -> Term \| None`; `(program, term) -> list[CompletionRow]` | Completion panel in one query |
| `apps/reports/selectors.py` | `PORow`, `CourseRow`, `Trend`, `student_trend` | `student_trend(student, pos) -> Trend` | Profile v2 rows and cumulative trend |
| `apps/reports/selectors.py` | `export_for_user` | `(user, export_id) -> ExportJob` (404 unless creator) | Export ownership |
| `apps/reports/selectors.py` | `grade_history` | `(user, assessment, enrollment) -> QuerySet[AuditEvent]` | Per-cell history, oldest first |
| `apps/reports/snapshot.py` | `repeatable_read_snapshot` | context manager | REPEATABLE READ transaction for multi-query reads |
| `apps/reports/exports.py` | `course_export_context`, `department_export_context`, `render_course_html`, `render_department_html`, `html_to_pdf`, `render_export` | see S7-03 | Split HTML/PDF so numbers are testable; dispatcher for the task |
| `apps/reports/services.py` | `request_export` | `(user, *, kind, fmt, offering=None, program=None, params=None) -> ExportJob` | Create a job and queue it on commit |
| `apps/reports/tasks.py` | `purge_old_exports` | `(days=7) -> int` | Nightly beat task |
| `apps/reports/charts.py` | `chart_number`, `profile_payload` | see S7-04 | Chart JSON rounded exactly like `\|score` |
| `apps/reports/summary.py` | `plain_language_summary` | add keyword `threshold: Decimal \| None = None` | Third sentence about the threshold |
| `apps/reports/history.py` | `KINDS`, `KIND_CHOICES`, `ACTION_LABELS`, `kind_filter`, `label_for`, `Change`, `EventView`, `describe_events` | see S7-05 | Audit timeline rows |
| `apps/reports/forms.py` | `HistoryFilterForm` | `(data=None, *, events)`, `.values()` | History filters |
| `templates` | `reports/includes/export_buttons.html`, `reports/pdf/_print.css`, `grading/cell_history.html` | — | New templates |
| `templates/base.html` | `{% block chart_js %}` | — | Chart.js only on chart pages |
| `e2e/` | `conftest.py` (`make_login`, `PASSWORD`), `test_golden_paths.py`, `test_accessibility.py` | — | Browser tests (marker `e2e`) |
| `.github/workflows/e2e.yml` | workflow `E2E` | nightly, manual, PRs into `main` | Browser tests in CI |
| `compose.prod.yml` | service `beat` | — | Celery beat (reused by T2.2) |
