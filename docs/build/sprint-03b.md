<!-- Sprint 3, part B: stories S3-02, S3-03, S3-04, S3-05, S3-07, S3-08.
     Part A (S3-01 publish, S3-06 production) lives in sprint-03a.md. -->

## Assumptions shared by every story in this file

These stories sit on top of Sprints 1 and 2. They use the following, exactly as named in spec §4.8. If one of them turned out differently when it was built, fix the call site here rather than the earlier code.

| Thing | Where it comes from | What this file assumes |
|---|---|---|
| `templates/base.html` | S1-09 | Blocks `title`, `content`, `chart_js` and `scripts`. `static/js/polaris.js` and the vendored Chart.js (`vendor/chart.umd.min.js`, in the `chart_js` block) load on every page before `{% block scripts %}` until S7-07 makes Chart.js opt-in |
| `includes/score_badge.html` | S1-09 | Context `value` (Decimal or None) and `threshold`. Prints `value|score` with a ✓ or ↓ icon |
| `includes/coverage_bar.html` | S1-09 | Context `coverage` (Decimal 0..1). A thin progress bar with the percentage as text |
| `includes/empty_state.html` | S1-09 | Context `title` (required), `message` and an optional `action_url` / `action_label` |
| `includes/setup_checklist.html` | S2-04 | Context `status` (a `SetupStatus`), `offering`, `can_manage_enrollment` (bool) |
| `|score`, `|pct`, `|weight` filters | S1-09 (`core/templatetags/polaris.py`) | Loaded with `{% load polaris %}` |
| `require_role(*roles)` | S2-02 | Denies anyone without one of the roles, with the status S2-02 standardised (404) |
| `require_offering_access(edit=False)` | S2-02 | Passes `offering=` and `perms_for=` into the view as keyword arguments. The URL's `offering_id` is passed through too |
| `can_view_student(user, student)` | S2-02 | True for the student themself, the head of the student's program, and superusers |
| `load_student_inputs`, `load_offering_inputs` | S1-07 | Already apply P4 (published only), P9 (latest attempt), P10 (open terms) and P13 (PO set) |
| `elif_scenario(published=True)` | S1-08 | Returns `offering, student, midterm, project, lo1, lo2, po1, po2`. Also creates the student's `ProgramMembership` (cohort 2024) and puts `po1` and `po2` in an **active** PO set of the offering's program |
| `catalog.selectors.setup_status(offering)` | S2-04 | Returns the `SetupStatus` dataclass from §4.8 |
| `catalog.services.ensure_term_open(offering)` | S2-03 | Raises `ValidationError("Fall 2025 is closed. Nothing in it can change.")` |

Every §4.8 URL in this file already has a row in `ROUTES` (`apps/accounts/tests/routes.py`, S2-02); it switches on when the URL exists. A URL that is **not** in §4.8 gets a new `Route(...)` line in that list, shown where it's introduced. Each story's **Done when** lists the results to check.

---

## S3-02 · Student PO profile v1

**Points:** 5 · **Owner:** Person C · **Branch:** `feature/S3-02-student-profile` · **Depends on:** S1-06, S1-07, S1-09, S2-02, S3-01 (publish, so there is something to show)

### Goal

A student opens `/me/` and sees one row per program outcome. Each row shows the score, a coverage bar, and whether they reached the threshold. A bar chart shows the same numbers. Clicking a PO opens a drawer that explains where the number comes from: every course and LO that feeds it, with its score and weight. A second page, `/me/courses/<offering_id>/`, shows the student's published grades and LO scores for one course. The head sees the same profile for any student in their program. This delivers B8 AC 1–4 and the "why is my PO 3 only 61?" question from the brief.

Three rules decide everything on these pages, and you should be able to say them out loud at the demo:

1. **The numbers come from the engine, through the loader.** The page never computes anything. It calls `load_student_inputs`, which applies P4 (published only), P9 (latest attempt), P10 (in-progress courses included) and P13 (the student's PO set), then `compute_student_profile`.
2. **"No evidence" is never zero.** A PO that no graded LO feeds shows "—" and an explanation (P12).
3. **The chart shows the table's numbers, rounded the same way.** We send the chart the display-rounded value (`display()`), so a hover tooltip can never disagree with the table.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/reports/selectors.py` | create | `student_program`, `student_profile_context`, `po_contributions`, `student_course_context` and their dataclasses |
| `apps/reports/views_student.py` | create | `profile`, `po_detail`, `course` |
| `apps/reports/views.py` | create (S3-03 and S3-04 add to it) | `department_student`, `department_student_po` |
| `apps/reports/urls_student.py` | create | the `student:` namespace |
| `apps/reports/urls.py` | create (S3-03 and S3-04 add to it) | the `reports:` namespace |
| `config/urls.py` | modify | include both |
| `apps/reports/templates/reports/student_profile.html` | create | profile page |
| `apps/reports/templates/reports/po_detail.html` | create | drawer partial + no-JavaScript full page |
| `apps/reports/templates/reports/student_course.html` | create | one course |
| `static/js/polaris.js` | modify | `Polaris.poBarChart` |
| `apps/reports/tests/test_student_profile.py` | create | tests |

### Steps

**1. The selectors.** All reading happens here. Views stay one call long.

`student_program` finds the program a user studies in. A student could in principle hold two student memberships. We take the one with the newest cohort, which is the program they are in now. T2.6 adds a switcher when it matters.

`PORow` is what one table row needs. `course_count` counts distinct *offerings* that feed the PO, not LOs, because "1 course" is what the student understands. We keep `attained = None` for "no evidence", so the template can tell "below threshold" apart from "no data".

For the course list, `superseded` marks an earlier attempt of a course the student later retook. P9 means those grades are still visible but no longer count. We compute it here from enrollment terms, because the loader only returns what counts.

```python
# apps/reports/selectors.py
"""Read-side helpers for report pages. Each returns plain data for one template."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.http import Http404

from apps.accounts.models import ProgramMembership, User
from apps.catalog.models import CourseOffering, Enrollment, Program, ProgramOutcome, Term
from apps.catalog.selectors import po_set_for_student
from apps.grading.models import Grade
from apps.outcomes.models import Assessment, LearningOutcome
from apps.scoring.engine import ZERO, NodeScore, compute_student_profile, display, normalise
from apps.scoring.loaders import load_offering_inputs, load_student_inputs

NO_EVIDENCE = NodeScore(score=None, coverage=ZERO)


# ---------- the student's program ----------

def student_program(student: User) -> Program | None:
    membership = (
        ProgramMembership.objects.select_related("program")
        .filter(user=student, role=ProgramMembership.Role.STUDENT)
        .order_by("-cohort_year")
        .first()
    )
    return membership.program if membership else None


# ---------- profile page ----------

@dataclass(frozen=True)
class PORow:
    po: ProgramOutcome
    score: Decimal | None
    coverage: Decimal
    attained: bool | None          # None = no evidence at all
    course_count: int              # distinct offerings feeding this PO


@dataclass(frozen=True)
class CourseRow:
    offering: CourseOffering
    in_progress: bool              # term not closed yet (P10)
    superseded: bool               # an earlier attempt of a course retaken later (P9)


def _course_rows(student: User) -> list[CourseRow]:
    enrollments = list(
        Enrollment.objects.filter(student=student, status=Enrollment.Status.ENROLLED)
        .select_related("offering__course", "offering__term")
        .order_by("-offering__term__starts_on", "offering__course__code")
    )
    latest_start: dict[int, object] = {}
    for e in enrollments:
        course_id = e.offering.course_id
        start = e.offering.term.starts_on
        if course_id not in latest_start or start > latest_start[course_id]:
            latest_start[course_id] = start
    return [
        CourseRow(
            offering=e.offering,
            in_progress=e.offering.term.status != Term.Status.CLOSED,
            superseded=e.offering.term.starts_on < latest_start[e.offering.course_id],
        )
        for e in enrollments
    ]


def _chart_data(rows: list[PORow], threshold: Decimal) -> dict:
    """JSON-safe data for Polaris.poBarChart. Values are the *display* values (P7),
    so the chart can never show a number the table doesn't."""
    return {
        "labels": [f"PO {r.po.number}" for r in rows],
        "names": [r.po.short_name for r in rows],
        "values": [None if r.score is None else float(display(r.score)) for r in rows],
        "states": [
            "none" if r.attained is None else ("attained" if r.attained else "below")
            for r in rows
        ],
        "threshold": float(threshold),
    }


def student_profile_context(student: User, *, viewer: User) -> dict:
    """Everything /me/ (and the head's view of a student) needs.
    `viewer` only changes wording ("Your" vs the student's name); permission is the view's job."""
    program = student_program(student)
    if program is None:
        return {"student": student, "program": None, "rows": [], "courses": [],
                "is_self": viewer == student, "has_any_score": False}

    po_set = po_set_for_student(student, program)
    pos = list(po_set.outcomes.all())
    profile = compute_student_profile(load_student_inputs(student, include_open_terms=True))
    threshold = program.attainment_threshold

    rows: list[PORow] = []
    for po in pos:
        ns = profile.po_scores.get(po.id, NO_EVIDENCE)
        offerings = {off_id for off_id, _lo, _w in profile.po_contributors.get(po.id, [])}
        rows.append(PORow(
            po=po,
            score=ns.score,
            coverage=ns.coverage,
            attained=None if ns.score is None else ns.score >= threshold,
            course_count=len(offerings),
        ))

    return {
        "student": student,
        "program": program,
        "po_set": po_set,
        "threshold": threshold,
        "rows": rows,
        "chart": _chart_data(rows, threshold),
        "courses": _course_rows(student),
        "has_any_score": any(r.score is not None for r in rows),
        "is_self": viewer == student,
    }


# ---------- "where does this number come from?" drawer ----------

@dataclass(frozen=True)
class ContributionRow:
    offering: CourseOffering
    lo: LearningOutcome
    weight: int                    # LO→PO weight, 1..5
    lo_score: Decimal | None       # None = LO has no published grades yet (skipped, P5)
    share: Decimal | None          # weight ÷ sum of weights that had a score; None if skipped


def po_contributions(student: User, po_id: int) -> dict:
    """Rows behind one PO score. Raises Http404 if the PO isn't in the student's PO set
    (so a crafted URL can't probe other programs)."""
    program = student_program(student)
    if program is None:
        raise Http404
    po_set = po_set_for_student(student, program)
    try:
        po = po_set.outcomes.get(pk=po_id)
    except ProgramOutcome.DoesNotExist as exc:
        raise Http404 from exc

    profile = compute_student_profile(load_student_inputs(student, include_open_terms=True))
    triples = profile.po_contributors.get(po.id, [])
    los = {
        lo.id: lo
        for lo in LearningOutcome.objects.filter(id__in={lo_id for _o, lo_id, _w in triples})
        .select_related("offering__course", "offering__term")
    }

    present_weight = sum(
        (Decimal(w) for off, lo_id, w in triples
         if profile.lo_scores.get((off, lo_id), NO_EVIDENCE).score is not None),
        ZERO,
    )
    rows = []
    for off_id, lo_id, weight in triples:
        lo_score = profile.lo_scores.get((off_id, lo_id), NO_EVIDENCE).score
        rows.append(ContributionRow(
            offering=los[lo_id].offering,
            lo=los[lo_id],
            weight=int(weight),
            lo_score=lo_score,
            share=None if lo_score is None or present_weight == ZERO
            else Decimal(weight) / present_weight,
        ))
    rows.sort(key=lambda r: (r.lo_score is None, -r.weight, r.offering.course.code, r.lo.number))

    ns = profile.po_scores.get(po.id, NO_EVIDENCE)
    return {"student": student, "po": po, "score": ns.score, "coverage": ns.coverage,
            "rows": rows, "threshold": program.attainment_threshold}


# ---------- one course, from the student's side ----------

@dataclass(frozen=True)
class AssessmentRow:
    assessment: Assessment
    state: str                     # "not_published" | "missing" | "excused" | "scored"
    raw: Decimal | None            # published mark, e.g. 17.5
    normalised: Decimal | None     # 0..100 (P3)


def student_course_context(enrollment: Enrollment) -> dict:
    offering = enrollment.offering
    assessments = list(offering.assessments.all())
    grades = {g.assessment_id: g for g in Grade.objects.filter(enrollment=enrollment)}

    rows = []
    for a in assessments:
        g = grades.get(a.id)
        if a.published_at is None:
            rows.append(AssessmentRow(a, "not_published", None, None))
        elif g is not None and g.published_is_excused:
            rows.append(AssessmentRow(a, "excused", None, None))
        elif g is None or g.published_score is None:
            rows.append(AssessmentRow(a, "missing", None, None))
        else:
            rows.append(AssessmentRow(a, "scored", g.published_score,
                                      normalise(g.published_score, a.max_score)))

    # LO scores for this offering alone. We don't go through load_student_inputs because
    # P9 would hide a superseded attempt, and the student still wants to see it here.
    inputs = load_offering_inputs(offering).get(enrollment.id)
    lo_scores = compute_student_profile([inputs]).lo_scores if inputs else {}
    lo_rows = [
        (lo, lo_scores.get((offering.id, lo.id), NO_EVIDENCE))
        for lo in offering.learning_outcomes.all()
    ]

    superseded = Enrollment.objects.filter(
        student=enrollment.student,
        offering__course_id=offering.course_id,
        offering__term__starts_on__gt=offering.term.starts_on,
        status=Enrollment.Status.ENROLLED,
    ).exists()

    return {
        "offering": offering,
        "enrollment": enrollment,
        "assessment_rows": rows,
        "lo_rows": lo_rows,
        "in_progress": offering.term.status != Term.Status.CLOSED,
        "superseded": superseded,
    }


# S3-03 and S3-04 append their selectors below this line.
```

**2. Student views.** Three views, each one call long. `course` is the only one that loads an object from the URL. It looks the enrollment up *by the logged-in student*, so another student's offering simply doesn't match and Django returns 404 (spec §3.4 rule 3). There is no "is this yours?" check that someone could forget to write.

The drawer uses Django 6 template partials. With HTMX (`request.htmx` is set by django-htmx), we render only the `drawer` partial. Without JavaScript, the same URL renders the whole page, because the partial is marked `inline` and also renders inside the page.

```python
# apps/reports/views_student.py
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.accounts.decorators import require_role
from apps.catalog.models import Enrollment

from . import selectors


@login_required
@require_role("student")
def profile(request):
    ctx = selectors.student_profile_context(request.user, viewer=request.user)
    return render(request, "reports/student_profile.html", ctx)


@login_required
@require_role("student")
def po_detail(request, po_id):
    ctx = selectors.po_contributions(request.user, po_id)
    ctx["back_url_name"] = "student:profile"
    template = "reports/po_detail.html#drawer" if request.htmx else "reports/po_detail.html"
    return render(request, template, ctx)


@login_required
@require_role("student")
def course(request, offering_id):
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("offering__course", "offering__term", "student"),
        offering_id=offering_id,
        student=request.user,
    )
    return render(request, "reports/student_course.html",
                  selectors.student_course_context(enrollment))


def transcript(request):
    """T2.4 (Sprint 8). Placeholder so the URL table in §4.8 resolves; returns 404 until then."""
    raise Http404
```

`transcript` exists only so `{% url 'student:transcript' %}` doesn't crash a template written early. S8-04 replaces it. Leave it out of the permission matrix until then.

**3. The head's view of one student.** Same template, same selector, `viewer` is the head. The permission rule is "head of the student's program", which `can_view_student` already encodes (S2-02). We call it and raise 404, because no decorator knows about a student in the URL.

```python
# apps/reports/views.py
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.accounts.decorators import require_role
from apps.accounts.models import User
from apps.accounts.permissions import can_view_student

from . import selectors


def _student_for_head(request, user_id) -> User:
    student = get_object_or_404(User, pk=user_id)
    if not can_view_student(request.user, student):
        raise Http404
    return student


@login_required
@require_role("head")
def department_student(request, user_id):
    student = _student_for_head(request, user_id)
    ctx = selectors.student_profile_context(student, viewer=request.user)
    return render(request, "reports/student_profile.html", ctx)


@login_required
@require_role("head")
def department_student_po(request, user_id, po_id):
    student = _student_for_head(request, user_id)
    ctx = selectors.po_contributions(student, po_id)
    template = "reports/po_detail.html#drawer" if request.htmx else "reports/po_detail.html"
    return render(request, template, ctx)
```

**4. URLs.**

```python
# apps/reports/urls_student.py
from django.urls import path

from . import views_student

app_name = "student"

urlpatterns = [
    path("", views_student.profile, name="profile"),
    path("po/<int:po_id>/", views_student.po_detail, name="po_detail"),
    path("courses/<int:offering_id>/", views_student.course, name="course"),
    path("transcript.pdf", views_student.transcript, name="transcript"),
]
```

```python
# apps/reports/urls.py
from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("department/students/<int:user_id>/", views.department_student,
         name="department_student"),
    path("department/students/<int:user_id>/po/<int:po_id>/", views.department_student_po,
         name="department_student_po"),
    # S3-03 and S3-04 add their paths here.
]
```

In `config/urls.py`, add the two includes next to the others:

```python
    path("me/", include("apps.reports.urls_student")),
    path("", include("apps.reports.urls")),
```

`apps.reports.urls` is mounted at the root because its paths start with different prefixes (`offerings/…`, `department/…`, `exports/…`). Django tries includes in order, so put it **after** `catalog` and `outcomes`. None of the paths overlap, but the order makes debugging easier.

**5. The profile template.** The table is the source of truth. The chart is a picture of it, so the canvas gets `role="img"` and an `aria-label`, and screen readers use the table. Each PO row is a link. With JavaScript it opens the Bootstrap offcanvas drawer and HTMX fills its body. Without JavaScript it goes to the full page. Bootstrap's offcanvas toggle calls `preventDefault()` on `<a>` elements, so the browser doesn't also navigate.

```django
{# apps/reports/templates/reports/student_profile.html #}
{% extends "base.html" %}
{% load polaris %}

{% block title %}{% if is_self %}My PO profile{% else %}{{ student.get_full_name }}: PO profile{% endif %}{% endblock %}

{% block content %}
<div class="d-flex flex-wrap align-items-baseline justify-content-between mb-3 gap-2">
  <h1 class="h3 mb-0">
    {% if is_self %}My program outcomes{% else %}{{ student.get_full_name }}{% endif %}
  </h1>
  {% if program %}
    <span class="text-body-secondary">
      {{ program.code }} · {{ po_set.label }} · threshold {{ threshold|score }}
      {% if student.student_number %} · {{ student.student_number }}{% endif %}
    </span>
  {% endif %}
</div>

{% if not program %}
  {% include "includes/empty_state.html" with title="No program yet" message="This account isn't registered as a student in any program. Ask the department office to add you." only %}
{% elif not has_any_score %}
  {% include "includes/empty_state.html" with title="No published grades yet" message="Your scores appear here as soon as an instructor publishes the first assessment of one of your courses. Nothing you see here is ever a draft." only %}
{% endif %}

{% if program %}
<div class="row g-4">
  <div class="col-lg-7 order-lg-2">
    <div class="table-responsive">
      <table class="table table-hover align-middle pl-scores" aria-describedby="po-table-help">
        <thead>
          <tr>
            <th scope="col">PO</th>
            <th scope="col">Outcome</th>
            <th scope="col" class="text-end">Score</th>
            <th scope="col" class="w-25">Evidence</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
            {% if is_self %}
              {% url "student:po_detail" row.po.id as detail_url %}
            {% else %}
              {% url "reports:department_student_po" student.id row.po.id as detail_url %}
            {% endif %}
            <tr>
              <td class="fw-semibold">{{ row.po.number }}</td>
              <td>
                <a href="{{ detail_url }}"
                   hx-get="{{ detail_url }}" hx-target="#po-drawer-body" hx-swap="innerHTML"
                   data-bs-toggle="offcanvas" data-bs-target="#po-drawer"
                   title="{{ row.po.description }}">{{ row.po.short_name }}</a>
              </td>
              <td class="text-end">
                {% include "includes/score_badge.html" with value=row.score threshold=threshold only %}
              </td>
              <td>
                {% if row.score is None %}
                  <span class="text-body-secondary small">No courses have contributed to this outcome yet</span>
                {% else %}
                  {% include "includes/coverage_bar.html" with coverage=row.coverage only %}
                  <span class="small text-body-secondary">{{ row.course_count }} course{{ row.course_count|pluralize }}</span>
                {% endif %}
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    <p id="po-table-help" class="small text-body-secondary">
      Click an outcome to see which courses and learning outcomes produce its score.
      "Evidence" is the share of the planned weight that already has published grades.
    </p>
  </div>

  <div class="col-lg-5 order-lg-1">
    <div class="pl-chart-box" style="height: 420px">
      <canvas id="po-chart" role="img"
              aria-label="Bar chart of the {{ rows|length }} program outcome scores. The same numbers are in the table."></canvas>
    </div>
    {{ chart|json_script:"po-chart-data" }}
  </div>
</div>

<h2 class="h5 mt-4">Courses</h2>
{% if courses %}
  <ul class="list-group mb-4">
    {% for c in courses %}
      <li class="list-group-item d-flex justify-content-between align-items-center">
        <span>
          {% if is_self %}<a href="{% url 'student:course' c.offering.id %}">{% endif %}
            {{ c.offering.course.code }} {{ c.offering.course.title }}
          {% if is_self %}</a>{% endif %}
          <span class="text-body-secondary">· {{ c.offering.term.name }}</span>
        </span>
        <span>
          {% if c.in_progress %}<span class="badge text-bg-warning">In progress</span>{% endif %}
          {% if c.superseded %}<span class="badge text-bg-secondary" title="You retook this course later. Only the latest attempt counts toward PO scores.">Retaken</span>{% endif %}
        </span>
      </li>
    {% endfor %}
  </ul>
{% else %}
  <p class="text-body-secondary">You're not enrolled in any course yet.</p>
{% endif %}

<div class="offcanvas offcanvas-end" tabindex="-1" id="po-drawer" aria-labelledby="po-drawer-title">
  <div class="offcanvas-header">
    <h2 class="offcanvas-title h5" id="po-drawer-title">Where this number comes from</h2>
    <button type="button" class="btn-close" data-bs-dismiss="offcanvas" aria-label="Close"></button>
  </div>
  <div class="offcanvas-body" id="po-drawer-body">
    <p class="text-body-secondary">Loading…</p>
  </div>
</div>
{% endif %}
{% endblock %}

{% block scripts %}
{% if program %}
<script>
  document.addEventListener("DOMContentLoaded", () => Polaris.poBarChart("po-chart", "po-chart-data"));
</script>
{% endif %}
{% endblock %}
```

**6. The drawer template.** One file serves both cases. HTMX renders `po_detail.html#drawer`. A normal request renders the page, and `inline` makes the partial render in place.

The "share" column answers the real question: "how much of PO 3 is CSE 211?" Share is the LO→PO weight divided by the weights that currently have a score, which is exactly what the weighted average uses.

```django
{# apps/reports/templates/reports/po_detail.html #}
{% extends "base.html" %}
{% load polaris %}

{% block title %}PO {{ po.number }}: where the score comes from{% endblock %}

{% block content %}
<a href="{% url 'student:profile' %}" class="d-inline-block mb-3">&larr; Back to my profile</a>
{% partialdef drawer inline %}
<div class="pl-po-detail">
  <h3 class="h5">PO {{ po.number }} · {{ po.short_name }}</h3>
  <p class="small text-body-secondary">{{ po.description }}</p>
  <p class="fs-4 mb-1">{% include "includes/score_badge.html" with value=score threshold=threshold only %}</p>
  {% if score is not None %}
    {% include "includes/coverage_bar.html" with coverage=coverage only %}
  {% endif %}

  {% if rows %}
    <p class="small mt-3">
      Your PO {{ po.number }} score is the weighted average of these learning-outcome scores.
      Each weight (1–5) says how strongly that outcome supports PO {{ po.number }}.
    </p>
    <table class="table table-sm align-middle pl-scores">
      <thead>
        <tr><th scope="col">Course · LO</th><th scope="col" class="text-end">LO score</th>
            <th scope="col" class="text-end">Weight</th><th scope="col" class="text-end">Share</th></tr>
      </thead>
      <tbody>
        {% for r in rows %}
          <tr{% if r.lo_score is None %} class="text-body-secondary"{% endif %}>
            <td>
              <span class="fw-semibold">{{ r.offering.course.code }}</span> LO {{ r.lo.number }}
              <span class="d-block small">{{ r.lo.description|truncatechars:90 }}</span>
              <span class="d-block small">{{ r.offering.term.name }}</span>
            </td>
            <td class="text-end">{% if r.lo_score is None %}no grades yet{% else %}{{ r.lo_score|score }}{% endif %}</td>
            <td class="text-end">{{ r.weight }}</td>
            <td class="text-end">{% if r.share is None %}—{% else %}{{ r.share|pct }}{% endif %}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    <p class="small text-body-secondary">
      Rows marked "no grades yet" are skipped, not counted as zero. They start counting
      when their assessments are published.
    </p>
  {% else %}
    <p class="mt-3">No course you've taken links a learning outcome to PO {{ po.number }} yet,
      so there is nothing to average. This is "no evidence", not a failing score.</p>
  {% endif %}
</div>
{% endpartialdef %}
{% endblock %}
```

**7. One course page.**

```django
{# apps/reports/templates/reports/student_course.html #}
{% extends "base.html" %}
{% load polaris %}

{% block title %}{{ offering.course.code }} · my grades{% endblock %}

{% block content %}
<a href="{% url 'student:profile' %}" class="d-inline-block mb-3">&larr; My profile</a>
<h1 class="h3">{{ offering.course.code }} {{ offering.course.title }}
  <small class="text-body-secondary">{{ offering.term.name }}</small></h1>

{% if in_progress %}
  <div class="alert alert-warning py-2">This course is in progress. Scores change as more assessments are published.</div>
{% endif %}
{% if superseded %}
  <div class="alert alert-secondary py-2">You retook this course later. These grades stay visible, but only the latest attempt counts toward your PO scores.</div>
{% endif %}

<div class="row g-4">
  <div class="col-md-6">
    <h2 class="h5">Assessments</h2>
    <table class="table align-middle pl-scores">
      <thead><tr><th scope="col">Assessment</th><th scope="col" class="text-end">Mark</th><th scope="col" class="text-end">Out of 100</th></tr></thead>
      <tbody>
        {% for r in assessment_rows %}
          <tr>
            <td>{{ r.assessment.name }} <span class="small text-body-secondary">{{ r.assessment.get_kind_display }}</span></td>
            {% if r.state == "scored" %}
              <td class="text-end">{{ r.raw|weight }} / {{ r.assessment.max_score|weight }}</td>
              <td class="text-end">{{ r.normalised|score }}</td>
            {% elif r.state == "excused" %}
              <td class="text-end" colspan="2"><span class="badge text-bg-info">Excused</span></td>
            {% elif r.state == "missing" %}
              <td class="text-end" colspan="2"><span class="text-body-secondary">No grade</span></td>
            {% else %}
              <td class="text-end" colspan="2"><span class="text-body-secondary">Not published yet</span></td>
            {% endif %}
          </tr>
        {% empty %}
          <tr><td colspan="3" class="text-body-secondary">The instructor hasn't set up assessments yet.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <div class="col-md-6">
    <h2 class="h5">Learning outcomes</h2>
    <table class="table align-middle pl-scores">
      <thead><tr><th scope="col">LO</th><th scope="col" class="text-end">Score</th><th scope="col" class="w-25">Evidence</th></tr></thead>
      <tbody>
        {% for lo, ns in lo_rows %}
          <tr>
            <td><span class="fw-semibold">LO {{ lo.number }}</span> <span class="small">{{ lo.description }}</span></td>
            <td class="text-end">{{ ns.score|score }}</td>
            <td>{% if ns.score is not None %}{% include "includes/coverage_bar.html" with coverage=ns.coverage only %}{% endif %}</td>
          </tr>
        {% empty %}
          <tr><td colspan="3" class="text-body-secondary">No learning outcomes defined yet.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

**8. The chart helper.** Chart.js has no built-in reference line, and we don't want a plugin dependency for one dashed line. So we write a ten-line inline plugin that draws a vertical line at the threshold after the bars. Colours come from the design tokens in `polaris.css`, with fallbacks so the chart still works if a token is missing. `null` values are simply not drawn, which is what "no evidence" should look like.

Add to `static/js/polaris.js`:

```javascript
// ---------- PO bar chart (S3-02) ----------
window.Polaris = window.Polaris || {};

Polaris.cssVar = function (name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
};

Polaris.poBarChart = function (canvasId, dataId) {
  const canvas = document.getElementById(canvasId);
  const source = document.getElementById(dataId);
  if (!canvas || !source || typeof Chart === "undefined") return null;
  const data = JSON.parse(source.textContent);

  const colourFor = {
    attained: Polaris.cssVar("--pl-attained", "#198754"),
    below: Polaris.cssVar("--pl-below", "#dc3545"),
    none: Polaris.cssVar("--pl-none", "#adb5bd"),
  };

  const thresholdLine = {
    id: "thresholdLine",
    afterDatasetsDraw(chart) {
      const x = chart.scales.x.getPixelForValue(data.threshold);
      const { top, bottom } = chart.chartArea;
      const ctx = chart.ctx;
      ctx.save();
      ctx.strokeStyle = Polaris.cssVar("--pl-accent", "#d97706");
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(x, top);
      ctx.lineTo(x, bottom);
      ctx.stroke();
      ctx.restore();
    },
  };

  return new Chart(canvas, {
    type: "bar",
    data: {
      labels: data.labels,
      datasets: [{
        label: "Score",
        data: data.values,
        backgroundColor: data.states.map((s) => colourFor[s]),
        borderRadius: 3,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: { x: { min: 0, max: 100, ticks: { stepSize: 20 } } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => `${items[0].label} · ${data.names[items[0].dataIndex]}`,
            label: (item) => (item.raw === null ? "No evidence yet" : item.raw.toFixed(1)),
          },
        },
      },
    },
    plugins: [thresholdLine],
  });
};
```

`animation: false` is deliberate. Playwright screenshots in S7-06 and the PDF exports should never catch a half-drawn bar.

### Tests

```python
# apps/reports/tests/test_student_profile.py
from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog.models import Term
from apps.core.tests.factories import (
    EnrollmentFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    UserFactory,
)
from apps.core.tests.scenarios import elif_scenario
from apps.grading.models import Grade
from apps.reports import selectors
from apps.scoring.engine import display

pytestmark = pytest.mark.django_db


def _row(ctx, po):
    return next(r for r in ctx["rows"] if r.po.id == po.id)


def test_elif_sees_the_slide_numbers(client):
    """B8 AC1."""
    data = elif_scenario()
    client.force_login(data.student)

    resp = client.get(reverse("student:profile"))

    assert resp.status_code == 200
    assert display(_row(resp.context, data.po1).score) == "85.0"
    assert display(_row(resp.context, data.po2).score) == "82.9"
    assert b"85.0" in resp.content and b"82.9" in resp.content


def test_chart_uses_the_same_rounded_numbers_as_the_table():
    data = elif_scenario()
    ctx = selectors.student_profile_context(data.student, viewer=data.student)
    i = ctx["chart"]["labels"].index(f"PO {data.po1.number}")
    assert ctx["chart"]["values"][i] == 85.0
    assert ctx["chart"]["states"][i] == "attained"


def test_po_without_evidence_shows_dash_not_zero(client):
    """B8 AC2."""
    data = elif_scenario()
    po3 = ProgramOutcomeFactory(po_set=data.po1.po_set, number=3, short_name="System design")
    client.force_login(data.student)

    resp = client.get(reverse("student:profile"))

    row = _row(resp.context, po3)
    assert row.score is None
    assert row.attained is None
    assert row.course_count == 0
    assert b"No courses have contributed to this outcome yet" in resp.content


def test_draft_grades_never_appear():
    """B8 AC4: unpublished data gives no score; a draft edit after publishing changes nothing."""
    unpublished = elif_scenario(published=False)
    ctx = selectors.student_profile_context(unpublished.student, viewer=unpublished.student)
    assert all(r.score is None for r in ctx["rows"])
    assert ctx["has_any_score"] is False

    data = elif_scenario()
    Grade.objects.filter(assessment=data.midterm, enrollment__student=data.student).update(score=Decimal("10"))
    ctx = selectors.student_profile_context(data.student, viewer=data.student)
    assert display(_row(ctx, data.po1).score) == "85.0"


def test_drawer_lists_every_contributor_with_weight_and_share(client):
    data = elif_scenario()
    client.force_login(data.student)

    resp = client.get(reverse("student:po_detail", args=[data.po1.id]), HTTP_HX_REQUEST="true")

    assert resp.status_code == 200
    rows = resp.context["rows"]
    assert [(r.lo.id, r.weight) for r in rows] == [(data.lo1.id, 4), (data.lo2.id, 2)]
    assert rows[0].share == Decimal(4) / Decimal(6)
    assert b"<html" not in resp.content            # partial only


def test_drawer_without_htmx_renders_full_page(client):
    data = elif_scenario()
    client.force_login(data.student)
    resp = client.get(reverse("student:po_detail", args=[data.po1.id]))
    assert b"<html" in resp.content
    assert b"Back to my profile" in resp.content


def test_drawer_for_po_of_another_program_is_404(client):
    data = elif_scenario()
    other_program_po = ProgramOutcomeFactory()   # its own program and PO set
    client.force_login(data.student)
    resp = client.get(reverse("student:po_detail", args=[other_program_po.id]))
    assert resp.status_code == 404


def test_course_page_shows_published_marks_and_lo_scores(client):
    data = elif_scenario()
    client.force_login(data.student)

    resp = client.get(reverse("student:course", args=[data.offering.id]))

    assert resp.status_code == 200
    states = {r.assessment.id: r.state for r in resp.context["assessment_rows"]}
    assert states[data.midterm.id] == "scored"
    lo_scores = {lo.id: ns.score for lo, ns in resp.context["lo_rows"]}
    assert display(lo_scores[data.lo1.id]) == "86.0"
    assert resp.context["in_progress"] == (data.offering.term.status != Term.Status.CLOSED)


def test_unpublished_assessment_says_not_published(client):
    data = elif_scenario(published=False)
    client.force_login(data.student)
    resp = client.get(reverse("student:course", args=[data.offering.id]))
    assert {r.state for r in resp.context["assessment_rows"]} == {"not_published"}
    assert b"Not published yet" in resp.content


def test_another_students_course_page_is_404(client):
    """B8 AC3, at object level. Role-level denials are in the permission matrix."""
    data = elif_scenario()
    classmate = UserFactory()
    MembershipFactory(user=classmate, program=data.offering.course.program,
                      role="student", cohort_year=2024)
    client.force_login(classmate)
    resp = client.get(reverse("student:course", args=[data.offering.id]))
    assert resp.status_code == 404


def test_head_sees_student_of_own_program_only(client):
    data = elif_scenario()
    head = UserFactory()
    MembershipFactory(user=head, program=data.offering.course.program, role="head")
    other_head = UserFactory()
    MembershipFactory(user=other_head, program=ProgramFactory(), role="head")

    client.force_login(head)
    resp = client.get(reverse("reports:department_student", args=[data.student.id]))
    assert resp.status_code == 200
    assert resp.context["is_self"] is False
    assert b"85.0" in resp.content

    client.force_login(other_head)
    resp = client.get(reverse("reports:department_student", args=[data.student.id]))
    assert resp.status_code == 404


def test_retaken_course_is_marked_superseded():
    data = elif_scenario()
    later_term = Term.objects.create(code="2030S", name="Spring 2030",
                                     starts_on=date(2030, 2, 1), ends_on=date(2030, 6, 30))
    retake = OfferingFactory(course=data.offering.course, term=later_term)
    EnrollmentFactory(offering=retake, student=data.student)

    rows = selectors._course_rows(data.student)
    by_offering = {r.offering.id: r for r in rows}
    assert by_offering[data.offering.id].superseded is True
    assert by_offering[retake.id].superseded is False


def test_profile_query_count_is_bounded(client, django_assert_max_num_queries):
    data = elif_scenario()
    client.force_login(data.student)
    with django_assert_max_num_queries(25):
        client.get(reverse("student:profile"))
```

`test_retaken_course_is_marked_superseded` creates its later term in 2030 by hand, so it doesn't depend on the dates `elif_scenario` picked.

### Check it works

1. `uv run python manage.py seed_demo --reset`. After S3-07 this prints the logins.
2. Log in as Elif (`elif.yildiz@polaris.test`). You land on `/me/`. PO 1 shows **85.0** and PO 2 shows **82.9**. PO 11 shows "—" with "No courses have contributed to this outcome yet".
3. Hover a bar: the tooltip says "PO 1 · Math, science & engineering knowledge" and "85.0". The dashed amber line sits at 60.
4. Click "Math, science & engineering knowledge". The drawer opens with two rows, CSE 311 LO 1 (weight 4, share 67%) and LO 2 (weight 2, share 33%).
5. Open `/me/po/1/` with JavaScript disabled (DevTools → Command menu → "Disable JavaScript"). You get a full page with the same table.
6. Click the CSE 311 course. Midterm I shows 90 / 100. The Final exam shows "Not published yet". The course is labelled "In progress".
7. Log in as another student and paste Elif's course URL `/me/courses/<id>/`. You get 404.
8. Log in as the head (Deniz Kara) and open `/department/students/<Elif's id>/`. You see the same numbers with her name in the title.

### Done when

| Acceptance criterion | Proved by |
|---|---|
| B8 AC1: Elif sees PO1 85.0, PO2 82.9 | `test_elif_sees_the_slide_numbers` |
| B8 AC2: no evidence shows "—" and the message, never 0 | `test_po_without_evidence_shows_dash_not_zero` |
| B8 AC3: another student's URL gives 404 | `test_another_students_course_page_is_404`, `test_drawer_for_po_of_another_program_is_404`, permission matrix rows below |
| B8 AC4: drafts never appear | `test_draft_grades_never_appear`, `test_unpublished_assessment_says_not_published` |
| Drawer explains the number | `test_drawer_lists_every_contributor_with_weight_and_share` |
| Chart and table agree | `test_chart_uses_the_same_rounded_numbers_as_the_table` |
| Head sees own program's students only | `test_head_sees_student_of_own_program_only` |

Permission matrix. The first four rows already exist in `ROUTES`. Add one line for the new URL:

```python
    Route("reports:department_student_po", HEAD,
          kwargs=lambda w: {"user_id": w.users["student"].pk, "po_id": w.po.pk}, story="S3-02"),
```

Expected results (✓ = 200, ✗ = denied with 404):

| URL name | student (self) | student (other) | instructor | head (same program) | head (other program) | anonymous |
|---|---|---|---|---|---|---|
| `student:profile` | ✓ | n/a | ✗ | ✗ | ✗ | 302 to login |
| `student:po_detail` | ✓ | n/a | ✗ | ✗ | ✗ | 302 |
| `student:course` | ✓ (enrolled) | ✗ | ✗ | ✗ | ✗ | 302 |
| `reports:department_student` | ✗ | ✗ | ✗ | ✓ | ✗ | 302 |
| `reports:department_student_po` | ✗ | ✗ | ✗ | ✓ | ✗ | 302 |

### Commits and PR

```
Add student profile selectors with PO rows and contributors (#S3-02)
Add /me/ profile page with PO table and bar chart (#S3-02)
Add PO contributors drawer with HTMX and no-JS fallback (#S3-02)
Add student course page and head's view of a student (#S3-02)
Add student profile tests and permission matrix rows (#S3-02)
```

PR title: **Student PO profile v1: table, chart, "where this comes from" drawer (S3-02)**

---
## S3-03 · Instructor course results

**Points:** 3 · **Owner:** Person A · **Branch:** `feature/S3-03-course-results` · **Depends on:** S1-06, S1-07, S2-02, S2-04 (`setup_status`), S3-01

### Goal

An instructor opens `/offerings/<id>/results/` and sees their class. There is one row per enrolled student and one column per LO, plus a class-average row and a small histogram per LO. A side panel shows what this course contributes to each PO, averaged over the class. This delivers B9 AC 1 and 2.

Two choices to be able to defend:

- **The class average is the mean of the students' LO scores, not a formula run on pooled grades** (spec §2.5). Students with no score for an LO are left out of that LO's average and counted separately ("n = 27 of 30"). Pooling grades would weight students with more graded work more heavily, and would disagree with what each student sees.
- **Only published grades are used**, as everywhere else. The instructor's drafts are on the grade sheet, and this page answers "what do students see?". The page says so in one line, so nobody wonders why last night's edits don't show.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/scoring/aggregates.py` | create | `ClassLOSummary` and friends, `class_lo_summary` |
| `apps/reports/selectors.py` | modify | `course_results_context` |
| `apps/reports/views.py` | modify | `course_results` |
| `apps/reports/urls.py` | modify | `offerings/<offering_id>/results/` |
| `apps/reports/templates/reports/course_results.html` | create | the page |
| `static/css/polaris.css` | modify | `.pl-histogram` |
| `apps/core/tests/scenarios.py` | modify | `one_lo_class` helper (also used by S3-04) |
| `apps/scoring/tests/test_aggregates_class.py` | create | aggregate tests |
| `apps/reports/tests/test_course_results.py` | create | view tests |

### Steps

**1. A small test scenario.** Most aggregate tests need the same shape: one offering, one published assessment out of 100, feeding one LO at weight 100, which maps to one PO. With that shape a student's grade *is* their LO score *and* their PO score, so the expected numbers are easy to work out by hand. Add this to the scenarios module from S1-08:

```python
# apps/core/tests/scenarios.py  (add below elif_scenario)
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.utils import timezone

from apps.accounts.models import ProgramMembership
from apps.core.tests.factories import (
    AssessmentFactory,
    AssessmentLOWeightFactory,
    CourseFactory,
    EnrollmentFactory,
    GradeFactory,
    LearningOutcomeFactory,
    LOPOWeightFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)


def one_lo_class(*, students_scores=(), term=None, program=None, po=None, lo_po_weight=3):
    """One offering whose single published assessment (max 100) feeds one LO (weight 100),
    which maps to one PO. A student's grade is therefore also their LO and PO score.

    students_scores: iterable of (student_or_None, score_or_None). None as student creates
    a new one (cohort 2024); None as score enrolls the student without a grade.
    """
    if po is None:
        program = program or ProgramFactory()
        po_set = ProgramOutcomeSetFactory(program=program, is_active=True, effective_from_year=2000)
        po = ProgramOutcomeFactory(po_set=po_set, number=1)
    program = po.po_set.program
    term = term or TermFactory(code="2026S", name="Spring 2026", starts_on=date(2026, 2, 9),
                               ends_on=date(2026, 6, 15), status="closed")
    offering = OfferingFactory(course=CourseFactory(program=program), term=term)
    published_at = timezone.now()
    assessment = AssessmentFactory(offering=offering, name="Exam", max_score=Decimal("100"),
                                   published_at=published_at)
    lo = LearningOutcomeFactory(offering=offering, number=1)
    AssessmentLOWeightFactory(assessment=assessment, learning_outcome=lo, weight=Decimal("100"))
    LOPOWeightFactory(learning_outcome=lo, program_outcome=po, weight=lo_po_weight)

    students, enrollments = [], []
    for student, score in students_scores:
        if student is None:
            student = UserFactory()
        ProgramMembership.objects.get_or_create(
            user=student, program=program, role=ProgramMembership.Role.STUDENT,
            defaults={"cohort_year": 2024},
        )
        enrollment = EnrollmentFactory(offering=offering, student=student)
        if score is not None:
            value = Decimal(str(score))
            GradeFactory(assessment=assessment, enrollment=enrollment, score=value,
                         published_score=value, published_at=published_at)
        students.append(student)
        enrollments.append(enrollment)

    return SimpleNamespace(offering=offering, assessment=assessment, lo=lo, po=po,
                           program=program, term=term, students=students,
                           enrollments=enrollments)
```

Move the imports to the top of the file and merge them with the ones `elif_scenario` already has. Don't paste a second import block halfway down.

**2. The aggregate.** `aggregates.py` lives in `scoring` because it is about numbers. Unlike `engine.py`, it may touch the database through the loaders. It calls the engine once per student. That is fine at class size (80 students take a few milliseconds of Python). The loader reads the whole class in one pass (`load_offering_inputs`), so the query count doesn't grow with the number of students.

The histogram has ten buckets: 0–9.99, 10–19.99, …, 90–100. 100 goes into the last bucket rather than an eleventh one. `histogram_heights` turns counts into 0–100 percentages of the tallest bucket so the template can draw bars with plain CSS.

"Course contribution to POs" is the mean, over students, of each student's PO score computed **from this offering alone**. It's what a department reviewer means by "how well does CSE 311 deliver PO 2?".

```python
# apps/scoring/aggregates.py
"""Class- and program-level numbers. Always averages of per-student engine results,
never a separate formula on pooled grades (spec §2.5)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from apps.catalog.models import Enrollment, ProgramOutcome

from .engine import ZERO, NodeScore, compute_student_profile
from .loaders import load_offering_inputs

BUCKETS = 10
NO_EVIDENCE = NodeScore(score=None, coverage=ZERO)


def mean(values: list[Decimal]) -> Decimal | None:
    return None if not values else sum(values, ZERO) / Decimal(len(values))


def bucket_of(score: Decimal) -> int:
    """0..9. 100 belongs to the top bucket."""
    return min(int(score // 10), BUCKETS - 1)


@dataclass(frozen=True)
class StudentLORow:
    enrollment_id: int
    student_id: int
    student_number: str | None
    name: str
    scores: dict[int, NodeScore]             # lo_id -> NodeScore


@dataclass(frozen=True)
class LOStats:
    lo_id: int
    number: int
    description: str
    mean: Decimal | None
    n: int                                   # students with a score for this LO
    histogram: tuple[int, ...] = field(default=(0,) * BUCKETS)

    @property
    def histogram_heights(self) -> list[int]:
        top = max(self.histogram) or 1
        return [round(100 * c / top) for c in self.histogram]


@dataclass(frozen=True)
class POContribution:
    po_id: int
    number: int
    short_name: str
    mean: Decimal | None
    n: int


@dataclass(frozen=True)
class ClassLOSummary:
    los: list[LOStats]
    rows: list[StudentLORow]
    po_contribution: list[POContribution]
    enrolled: int


def class_lo_summary(offering) -> ClassLOSummary:
    los = list(offering.learning_outcomes.order_by("number"))
    enrollments = list(
        offering.enrollments.filter(status=Enrollment.Status.ENROLLED)
        .select_related("student")
        .order_by("student__student_number", "student__last_name", "student__first_name")
    )
    inputs = load_offering_inputs(offering)

    rows: list[StudentLORow] = []
    lo_values: dict[int, list[Decimal]] = {lo.id: [] for lo in los}
    po_values: dict[int, list[Decimal]] = defaultdict(list)

    for enr in enrollments:
        off_inputs = inputs.get(enr.id)
        profile = compute_student_profile([off_inputs]) if off_inputs else None
        scores: dict[int, NodeScore] = {}
        for lo in los:
            ns = profile.lo_scores.get((offering.id, lo.id), NO_EVIDENCE) if profile else NO_EVIDENCE
            scores[lo.id] = ns
            if ns.score is not None:
                lo_values[lo.id].append(ns.score)
        if profile:
            for po_id, ns in profile.po_scores.items():
                if ns.score is not None:
                    po_values[po_id].append(ns.score)
        rows.append(StudentLORow(
            enrollment_id=enr.id,
            student_id=enr.student_id,
            student_number=enr.student.student_number,
            name=enr.student.get_full_name(),
            scores=scores,
        ))

    stats = []
    for lo in los:
        values = lo_values[lo.id]
        counts = [0] * BUCKETS
        for v in values:
            counts[bucket_of(v)] += 1
        stats.append(LOStats(lo_id=lo.id, number=lo.number, description=lo.description,
                             mean=mean(values), n=len(values), histogram=tuple(counts)))

    pos = (ProgramOutcome.objects
           .filter(lo_weights__learning_outcome__offering=offering)
           .distinct().order_by("number"))
    contribution = [
        POContribution(po_id=po.id, number=po.number, short_name=po.short_name,
                       mean=mean(po_values.get(po.id, [])), n=len(po_values.get(po.id, [])))
        for po in pos
    ]
    return ClassLOSummary(los=stats, rows=rows, po_contribution=contribution,
                          enrolled=len(enrollments))
```

**3. The selector and view.** The view is decorated with `require_offering_access()` (view access, not edit). The decorator lets in the offering's instructors, the head of its program and admins, and returns 404 for everyone else (B9 AC2). Closed terms stay viewable, because results are read-only.

```python
# apps/reports/selectors.py  (append)
from apps.catalog.selectors import setup_status
from apps.scoring.aggregates import class_lo_summary


def course_results_context(offering: CourseOffering) -> dict:
    summary = class_lo_summary(offering)
    return {
        "offering": offering,
        "summary": summary,
        "status": setup_status(offering),
        "threshold": offering.course.program.attainment_threshold,
        "in_progress": offering.term.status != Term.Status.CLOSED,
    }
```

Move these two imports to the top of `selectors.py` with the others.

```python
# apps/reports/views.py  (append; add the import at the top)
from apps.accounts.decorators import require_offering_access


@login_required
@require_offering_access()
def course_results(request, offering_id, *, offering, perms_for):
    ctx = selectors.course_results_context(offering)
    ctx["perms_for"] = perms_for
    return render(request, "reports/course_results.html", ctx)
```

```python
# apps/reports/urls.py  (add to urlpatterns)
    path("offerings/<int:offering_id>/results/", views.course_results, name="results"),
```

**4. Template.** The table can be 80 × 6. It gets a sticky header and a sticky first column, the same CSS classes the grade sheet uses (S2-06: `.pl-sticky-head`, `.pl-sticky-col`). Each score cell gets `title="coverage 67%"` so the instructor can hover to see how complete it is, without another column per LO.

```django
{# apps/reports/templates/reports/course_results.html #}
{% extends "base.html" %}
{% load polaris %}

{% block title %}{{ offering.course.code }} · results{% endblock %}

{% block content %}
<nav aria-label="breadcrumb">
  <ol class="breadcrumb">
    <li class="breadcrumb-item"><a href="{% url 'catalog:teaching' %}">My courses</a></li>
    <li class="breadcrumb-item"><a href="{% url 'catalog:offering' offering.id %}">{{ offering.course.code }} · {{ offering.term.name }}</a></li>
    <li class="breadcrumb-item active" aria-current="page">Results</li>
  </ol>
</nav>

<h1 class="h3">Results <small class="text-body-secondary">{{ summary.enrolled }} student{{ summary.enrolled|pluralize }}</small></h1>
<p class="small text-body-secondary">Published grades only. Drafts on the grade sheet appear here after you publish them.
  {% if in_progress %}The term is still open, so these numbers will change.{% endif %}</p>

{% if not status.is_complete %}
  {% include "includes/setup_checklist.html" with status=status offering=offering can_manage_enrollment=False only %}
{% endif %}

{% if not summary.los %}
  {% url 'outcomes:setup' offering.id as setup_url %}
  {% include "includes/empty_state.html" with title="No learning outcomes yet" message="Results are shown per learning outcome. Define them on the setup page first." action_label="Go to setup" action_url=setup_url only %}
{% elif not summary.rows %}
  {% include "includes/empty_state.html" with title="No students enrolled" message="The department adds students to this course. Ask the head if the list is missing." only %}
{% else %}
<div class="row g-4">
  <div class="col-xl-9">
    <div class="table-responsive pl-sticky-wrap" style="max-height: 70vh">
      <table class="table table-sm table-hover align-middle pl-scores">
        <thead class="pl-sticky-head">
          <tr>
            <th scope="col" class="pl-sticky-col">Student</th>
            {% for lo in summary.los %}
              <th scope="col" class="text-end" title="{{ lo.description }}">LO {{ lo.number }}</th>
            {% endfor %}
          </tr>
        </thead>
        <tbody>
          {% for row in summary.rows %}
            <tr>
              <th scope="row" class="pl-sticky-col fw-normal">
                <span class="font-monospace small">{{ row.student_number|default:"" }}</span> {{ row.name }}
              </th>
              {% for lo in summary.los %}
                {% with ns=row.scores|get_item:lo.lo_id %}
                  <td class="text-end{% if ns.score is not None and ns.score < threshold %} text-danger{% endif %}"
                      title="evidence {{ ns.coverage|pct }}">{{ ns.score|score }}</td>
                {% endwith %}
              {% endfor %}
            </tr>
          {% endfor %}
        </tbody>
        <tfoot class="table-group-divider">
          <tr class="fw-semibold">
            <th scope="row" class="pl-sticky-col">Class average</th>
            {% for lo in summary.los %}
              <td class="text-end">{{ lo.mean|score }}<span class="d-block small fw-normal text-body-secondary">n = {{ lo.n }}</span></td>
            {% endfor %}
          </tr>
          <tr>
            <th scope="row" class="pl-sticky-col small fw-normal">Distribution 0 → 100</th>
            {% for lo in summary.los %}
              <td>
                <div class="pl-histogram" role="img"
                     aria-label="LO {{ lo.number }} distribution: {% for c in lo.histogram %}{{ c }}{% if not forloop.last %}, {% endif %}{% endfor %} students per 10-point band">
                  {% for h in lo.histogram_heights %}<span style="height: {{ h }}%"></span>{% endfor %}
                </div>
              </td>
            {% endfor %}
          </tr>
        </tfoot>
      </table>
    </div>
  </div>

  <aside class="col-xl-3">
    <h2 class="h5">This course's contribution to POs</h2>
    <p class="small text-body-secondary">Class average of each student's PO score, computed from this course alone.</p>
    <ul class="list-group">
      {% for c in summary.po_contribution %}
        <li class="list-group-item d-flex justify-content-between">
          <span>PO {{ c.number }} <span class="small text-body-secondary">{{ c.short_name }}</span></span>
          <span>{% include "includes/score_badge.html" with value=c.mean threshold=threshold only %}</span>
        </li>
      {% empty %}
        <li class="list-group-item text-body-secondary">No LO is linked to a PO yet. <a href="{% url 'outcomes:mapping' offering.id %}">Open the mapping</a>.</li>
      {% endfor %}
    </ul>
  </aside>
</div>
{% endif %}
{% endblock %}
```

Two details in that template. `{% url … as setup_url %}` stores the URL in a variable first, because an `{% include … with … only %}` can't call `{% url %}` inline. And `get_item` is a new filter that reads a dict by key, because Django templates can't write `row.scores[lo.lo_id]`. Add it to `apps/core/templatetags/polaris.py`:

```python
@register.filter
def get_item(mapping, key):
    """{{ some_dict|get_item:key }}. Returns None for a missing key."""
    return mapping.get(key) if mapping is not None else None
```

**5. Histogram CSS.** Ten flex children with a percentage height. No JavaScript, and it prints.

```css
/* static/css/polaris.css — mini histogram (S3-03) */
.pl-histogram {
  display: flex;
  align-items: flex-end;
  gap: 1px;
  height: 28px;
  min-width: 60px;
}
.pl-histogram > span {
  flex: 1;
  min-height: 1px;
  background: var(--pl-primary, #1f3a5f);
  opacity: 0.75;
}
```

### Tests

```python
# apps/scoring/tests/test_aggregates_class.py
from decimal import Decimal

import pytest

from apps.core.tests.scenarios import elif_scenario, one_lo_class
from apps.scoring.aggregates import bucket_of, class_lo_summary, mean
from apps.scoring.engine import display

pytestmark = pytest.mark.django_db


def test_class_average_is_mean_of_non_none_scores():
    """B9 AC1: (80 + 60) / 2 = 70; the ungraded student is left out, not counted as 0."""
    data = one_lo_class(students_scores=[(None, 80), (None, 60), (None, None)])
    summary = class_lo_summary(data.offering)

    (lo,) = summary.los
    assert lo.mean == Decimal("70")
    assert lo.n == 2
    assert summary.enrolled == 3
    missing_row = next(r for r in summary.rows if r.student_id == data.students[2].id)
    assert missing_row.scores[data.lo.id].score is None


def test_po_contribution_is_mean_of_per_student_po_scores():
    data = one_lo_class(students_scores=[(None, 90), (None, 50)])
    (contrib,) = class_lo_summary(data.offering).po_contribution
    assert contrib.po_id == data.po.id
    assert contrib.mean == Decimal("70")
    assert contrib.n == 2


def test_elif_row_in_her_class():
    data = elif_scenario()
    summary = class_lo_summary(data.offering)
    row = next(r for r in summary.rows if r.student_id == data.student.id)
    assert display(row.scores[data.lo1.id].score) == "86.0"
    assert display(row.scores[data.lo2.id].score) == "82.9"
    po1 = next(c for c in summary.po_contribution if c.po_id == data.po1.id)
    assert display(po1.mean) == "85.0"           # she is the only student


def test_dropped_students_are_not_listed():
    data = one_lo_class(students_scores=[(None, 80), (None, 40)])
    data.enrollments[1].status = "dropped"
    data.enrollments[1].save()
    summary = class_lo_summary(data.offering)
    assert summary.enrolled == 1
    assert summary.los[0].mean == Decimal("80")


@pytest.mark.parametrize(("score", "bucket"), [
    ("0", 0), ("9.99", 0), ("10", 1), ("59.5", 5), ("99.9", 9), ("100", 9),
])
def test_bucket_edges(score, bucket):
    assert bucket_of(Decimal(score)) == bucket


def test_histogram_counts_and_heights():
    data = one_lo_class(students_scores=[(None, 95), (None, 100), (None, 55)])
    (lo,) = class_lo_summary(data.offering).los
    assert lo.histogram[9] == 2 and lo.histogram[5] == 1
    assert lo.histogram_heights[9] == 100 and lo.histogram_heights[5] == 50


def test_mean_of_nothing_is_none():
    assert mean([]) is None


def test_offering_without_los_gives_empty_summary():
    data = one_lo_class(students_scores=[(None, 70)])
    data.lo.delete()
    summary = class_lo_summary(data.offering)
    assert summary.los == []
    assert summary.po_contribution == []
```

```python
# apps/reports/tests/test_course_results.py
import pytest
from django.urls import reverse

from apps.core.tests.factories import MembershipFactory, UserFactory
from apps.core.tests.scenarios import one_lo_class

pytestmark = pytest.mark.django_db


@pytest.fixture
def klass():
    data = one_lo_class(students_scores=[(None, 80), (None, 60), (None, None)])
    instructor = UserFactory()
    MembershipFactory(user=instructor, program=data.program, role="instructor")
    data.offering.instructors.add(instructor)
    data.instructor = instructor
    return data


def test_instructor_of_offering_sees_results(client, klass):
    client.force_login(klass.instructor)
    resp = client.get(reverse("reports:results", args=[klass.offering.id]))
    assert resp.status_code == 200
    assert b"Class average" in resp.content
    assert b"70.0" in resp.content
    assert b"n = 2" in resp.content


def test_head_of_program_sees_results(client, klass):
    head = UserFactory()
    MembershipFactory(user=head, program=klass.program, role="head")
    client.force_login(head)
    assert client.get(reverse("reports:results", args=[klass.offering.id])).status_code == 200


def test_other_instructor_gets_404(client, klass):
    """B9 AC2."""
    stranger = UserFactory()
    MembershipFactory(user=stranger, program=klass.program, role="instructor")
    client.force_login(stranger)
    assert client.get(reverse("reports:results", args=[klass.offering.id])).status_code == 404


def test_student_in_the_class_gets_404(client, klass):
    client.force_login(klass.students[0])
    assert client.get(reverse("reports:results", args=[klass.offering.id])).status_code == 404


def test_results_page_query_count_does_not_grow_with_class_size(client, klass,
                                                               django_assert_max_num_queries):
    client.force_login(klass.instructor)
    with django_assert_max_num_queries(30):
        client.get(reverse("reports:results", args=[klass.offering.id]))
```

The query-count test is a guard against N+1 queries. If it fails after a teammate's change, run the page with django-debug-toolbar and look for a query repeated once per student.

### Check it works

1. Seed, then log in as Dr. Can Aydın. Open CSE 321 (Fall 2026) → Results.
2. You see about 40 rows. Midterm-only LOs have scores. LOs fed only by the project and final show "—", because those aren't published yet.
3. The class average row shows n = the number of students with a midterm grade. Excused and missing students are not counted.
4. Hover a score: "evidence 40%" or similar.
5. Log in as Dr. Ayşe Demir (who doesn't teach CSE 321) and paste the same URL: 404.
6. As the head, open the same URL: 200.

### Done when

| Acceptance criterion | Proved by |
|---|---|
| B9 AC1: class average = mean of non-None student LO scores | `test_class_average_is_mean_of_non_none_scores`, `test_elif_row_in_her_class` |
| B9 AC2: only the offering's instructors and the head | `test_other_instructor_gets_404`, `test_student_in_the_class_gets_404`, `test_head_of_program_sees_results`, matrix row below |
| No N+1 queries | `test_results_page_query_count_does_not_grow_with_class_size` |

Matrix row: `reports:results`: instructor (own) ✓, instructor (other) ✗ 404, head (same program) ✓, head (other program) ✗ 404, student ✗ 404, anonymous 302.

### Commits and PR

```
Add class_lo_summary aggregate with histograms (#S3-03)
Add one_lo_class test scenario (#S3-03)
Add course results page for instructors (#S3-03)
Test course results permissions and query count (#S3-03)
```

PR title: **Course results: students × LOs, class averages, PO contribution (S3-03)**

---
## S3-04 · Department overview v1

**Points:** 3 · **Owner:** Person C · **Branch:** `feature/S3-04-department-overview` · **Depends on:** S1-07, S2-02, S2-04 (`setup_status`), S3-03 (`aggregates.py`, `one_lo_class`)

### Goal

The head opens `/department/` and sees, for each PO: the average score across students, how many students have any evidence, and the attainment rate (P11). A term selector and an "include open terms" toggle (P10) control which data counts. Below that is the list of the selected term's offerings, with each one's setup-checklist status, so the head can see which courses are not mapped or not published. This delivers B10 AC 1 and 2. T1.6 (Sprint 6–7) grows this page into the full dashboard, so it is kept deliberately plain.

The rules on this page, in the order you'll be asked about them:

- **Cumulative up to the selected term.** Picking "Spring 2026" means "everything up to and including Spring 2026". That's what an accreditation reviewer asks: where do students stand at this point? Per-term slices come with T1.6's cohort/term table.
- **Closed terms only, by default** (P10). Accreditation numbers should use final grades. With the toggle on, open-term courses count with whatever is published, and the page says so in words, not just with the checkbox.
- **Attainment rate = students at or above the threshold ÷ students with any score for that PO** (P11). Students with no evidence are not counted as failing, the same rule as for one student (P12).
- **A student counts once per PO.** We average the students' cumulative PO scores. We do not average course scores. This is the same flat rule (P8) the student sees, aggregated over students.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/scoring/aggregates.py` | modify | `POSummary`, `program_po_summary` |
| `apps/catalog/selectors.py` | modify | `default_report_term` |
| `apps/reports/selectors.py` | modify | `department_context` |
| `apps/reports/forms.py` | create | `DepartmentFilterForm` |
| `apps/reports/views.py` | modify | `department` |
| `apps/reports/urls.py` | modify | `department/` |
| `apps/reports/templates/reports/department.html` | create | the page |
| `apps/scoring/tests/test_aggregates_program.py` | create | hand-computed fixture tests |
| `apps/reports/tests/test_department.py` | create | view tests |

### Steps

**1. Which program, which term.** The program comes from `head_program_or_404(request.user)` (S2-02, `apps/accounts/permissions.py`); every head page uses it, so don't write another helper. The term needs one small selector:

```python
# apps/catalog/selectors.py  (append)
from .models import Term


def default_report_term() -> Term | None:
    """Latest closed term (P10); if nothing is closed yet, the latest started term."""
    return (
        Term.objects.filter(status=Term.Status.CLOSED).order_by("-starts_on").first()
        or Term.objects.exclude(status=Term.Status.PLANNED).order_by("-starts_on").first()
    )
```

Merge the imports with the ones already at the top of the file.

**2. The aggregate.** It loops over the program's students and runs the same loader and engine the student's own page uses. That's the whole point: the head's average for PO 3 is literally the average of the numbers the students see.

The cost is one loader call per student (a handful of queries each). On the full seed (121 students) that's a few hundred queries and well under a second locally. That is acceptable for v1 and for B10. T2.3 (Sprint 8) replaces it with precomputed tables. If staging is slower than 1.5 s before then, pull T2.3 forward (spec T1.6 AC3).

```python
# apps/scoring/aggregates.py  (append; add the imports at the top of the file)
from apps.accounts.models import ProgramMembership, User
from apps.catalog.selectors import active_po_set

from .loaders import load_student_inputs


@dataclass(frozen=True)
class POSummary:
    po: ProgramOutcome
    mean: Decimal | None
    n_evidence: int                          # students with any score for this PO
    n_attaining: int                         # of those, score >= threshold

    @property
    def rate(self) -> Decimal | None:
        """Attainment rate (P11), 0..1. None when nobody has evidence."""
        if self.n_evidence == 0:
            return None
        return Decimal(self.n_attaining) / Decimal(self.n_evidence)


def program_po_summary(program, *, terms, include_open_terms, cohort=None) -> list[POSummary]:
    """Per PO of the program's active set: mean of students' cumulative PO scores up to the
    latest term in `terms`. `terms` is every term to consider; the latest one is the cut-off."""
    terms = list(terms)
    pos = list(active_po_set(program).outcomes.all())
    if not terms:
        return [POSummary(po=po, mean=None, n_evidence=0, n_attaining=0) for po in pos]
    up_to_term = max(terms, key=lambda t: t.starts_on)
    threshold = program.attainment_threshold

    students = User.objects.filter(
        memberships__program=program, memberships__role=ProgramMembership.Role.STUDENT,
    )
    if cohort is not None:
        students = students.filter(memberships__cohort_year=cohort)

    values: dict[int, list[Decimal]] = {po.id: [] for po in pos}
    for student in students.distinct().order_by("pk").iterator():
        inputs = load_student_inputs(student, include_open_terms=include_open_terms,
                                     up_to_term=up_to_term)
        if not inputs:
            continue
        profile = compute_student_profile(inputs)
        for po in pos:
            ns = profile.po_scores.get(po.id)
            if ns is not None and ns.score is not None:
                values[po.id].append(ns.score)

    return [
        POSummary(
            po=po,
            mean=mean(values[po.id]),
            n_evidence=len(values[po.id]),
            n_attaining=sum(1 for v in values[po.id] if v >= threshold),
        )
        for po in pos
    ]
```

We summarise over the **active** PO set. A student measured against an older set (P13) has no scores on the new set's POs and so doesn't appear in its numbers. With one PO set (our seed) this never happens. When the department really switches curricula, T1.6's cohort filter is how the head compares old and new.

**3. Selector for the whole page.**

```python
# apps/reports/selectors.py  (append)
from apps.catalog.selectors import setup_status
from apps.scoring.aggregates import program_po_summary


def department_context(program: Program, *, terms, include_open_terms: bool, cohort=None) -> dict:
    terms = list(terms)
    selected = max(terms, key=lambda t: t.starts_on) if terms else None
    summaries = program_po_summary(program, terms=terms, include_open_terms=include_open_terms,
                                   cohort=cohort)

    offerings = []
    if selected is not None:
        qs = (CourseOffering.objects
              .filter(term=selected, course__program=program)
              .select_related("course", "term")
              .prefetch_related("instructors")
              .order_by("course__code", "section"))
        offerings = [(o, setup_status(o)) for o in qs]

    open_terms_in_range = [t for t in terms if t.status != Term.Status.CLOSED]
    if selected is None:
        scope = "No terms yet."
    elif include_open_terms:
        scope = f"All terms up to {selected.name}, including courses still in progress."
    elif open_terms_in_range:
        names = ", ".join(t.name for t in open_terms_in_range)
        scope = (f"Closed terms up to {selected.name}. {names} "
                 f"{'is' if len(open_terms_in_range) == 1 else 'are'} still open and not counted.")
    else:
        scope = f"Closed terms up to {selected.name}."

    return {
        "program": program,
        "threshold": program.attainment_threshold,
        "summaries": summaries,
        "selected_term": selected,
        "include_open_terms": include_open_terms,
        "scope_label": scope,
        "offerings": offerings,
        "complete_count": sum(1 for _o, s in offerings if s.is_complete),
    }
```

`setup_status` may already be imported from S3-03. Keep one import line.

**4. The filter form.** A plain GET form, so a filtered view is a URL the head can bookmark or paste into an email.

```python
# apps/reports/forms.py
from django import forms

from apps.catalog.models import Term


class DepartmentFilterForm(forms.Form):
    term = forms.ModelChoiceField(
        queryset=Term.objects.exclude(status=Term.Status.PLANNED).order_by("-starts_on"),
        required=False, empty_label=None, label="Up to term",
    )
    include_open = forms.BooleanField(required=False, label="Include open terms")
```

**5. View and URL.** No form data means the defaults: latest closed term, closed only. The form is re-created with those values as `initial` so the dropdown shows what is actually being displayed.

```python
# apps/reports/views.py  (append; imports at the top)
from apps.catalog.models import Term
from apps.accounts.permissions import head_program_or_404
from apps.catalog.selectors import default_report_term

from .forms import DepartmentFilterForm


def _selected_terms(request, program):
    """Read the term filter from the query string. Returns (terms, include_open, form).
    Shared by the dashboard and every drill-down (S6-05), so they always agree."""
    form = DepartmentFilterForm(request.GET or None)
    if form.is_bound and form.is_valid():
        term = form.cleaned_data["term"] or default_report_term()
        include_open = form.cleaned_data["include_open"]
    else:
        term = default_report_term()
        include_open = False
        form = DepartmentFilterForm(initial={"term": term, "include_open": False})
    terms = Term.objects.filter(starts_on__lte=term.starts_on) if term else Term.objects.none()
    return terms, include_open, form


@login_required
@require_role("head")
def department(request):
    program = head_program_or_404(request.user)
    terms, include_open, form = _selected_terms(request, program)
    ctx = selectors.department_context(program, terms=terms, include_open_terms=include_open)
    ctx["form"] = form
    return render(request, "reports/department.html", ctx)
```

```python
# apps/reports/urls.py  (add)
    path("department/", views.department, name="department"),
```

**6. Template.** The attainment rate is the number the head cares about, so it gets a bar. The bar is coloured by the program threshold *on the average*, not by a target rate. The target rate (default 70% of students) arrives with T1.6.

```django
{# apps/reports/templates/reports/department.html #}
{% extends "base.html" %}
{% load polaris %}

{% block title %}Department · {{ program.code }}{% endblock %}

{% block content %}
<div class="d-flex flex-wrap justify-content-between align-items-end gap-3 mb-3">
  <h1 class="h3 mb-0">Department · {{ program.code }}</h1>
  <form method="get" class="d-flex flex-wrap align-items-end gap-2" aria-label="Filters">
    <div>
      <label for="{{ form.term.id_for_label }}" class="form-label small mb-0">{{ form.term.label }}</label>
      {{ form.term }}
    </div>
    <div class="form-check mb-1">
      {{ form.include_open }}
      <label for="{{ form.include_open.id_for_label }}" class="form-check-label">{{ form.include_open.label }}</label>
    </div>
    <button type="submit" class="btn btn-outline-primary btn-sm mb-1">Apply</button>
  </form>
</div>

<p class="text-body-secondary">{{ scope_label }} Threshold {{ threshold|score }}.</p>

{% if not selected_term %}
  {% include "includes/empty_state.html" with title="No terms yet" message="Create a term and its course offerings first. Scores appear once instructors publish grades." only %}
{% else %}
<div class="table-responsive mb-4">
  <table class="table align-middle pl-scores">
    <caption class="visually-hidden">Program outcome averages and attainment</caption>
    <thead>
      <tr>
        <th scope="col">PO</th><th scope="col">Outcome</th>
        <th scope="col" class="text-end">Average</th>
        <th scope="col" class="text-end">Students with evidence</th>
        <th scope="col" class="w-25">Attaining (≥ {{ threshold|score }})</th>
      </tr>
    </thead>
    <tbody>
      {% for s in summaries %}
        <tr>
          <td class="fw-semibold">{{ s.po.number }}</td>
          <td title="{{ s.po.description }}">{{ s.po.short_name }}</td>
          <td class="text-end">{% include "includes/score_badge.html" with value=s.mean threshold=threshold only %}</td>
          <td class="text-end">{{ s.n_evidence }}</td>
          <td>
            {% if s.rate is None %}
              <span class="text-body-secondary small">No student has evidence yet</span>
            {% else %}
              <div class="d-flex align-items-center gap-2">
                <div class="progress flex-grow-1" role="progressbar" aria-label="Attainment rate PO {{ s.po.number }}"
                     aria-valuenow="{{ s.n_attaining }}" aria-valuemin="0" aria-valuemax="{{ s.n_evidence }}" style="height: 8px">
                  <div class="progress-bar" style="width: {{ s.rate|pct }}"></div>
                </div>
                <span class="small text-nowrap">{{ s.rate|pct }} <span class="text-body-secondary">({{ s.n_attaining }}/{{ s.n_evidence }})</span></span>
              </div>
            {% endif %}
          </td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<h2 class="h5">{{ selected_term.name }} courses
  <small class="text-body-secondary">{{ complete_count }} of {{ offerings|length }} fully set up</small></h2>
{% if offerings %}
  <div class="list-group">
    {% for offering, status in offerings %}
      <a href="{% url 'catalog:offering' offering.id %}" class="list-group-item list-group-item-action">
        <div class="d-flex justify-content-between flex-wrap gap-2">
          <span><span class="fw-semibold">{{ offering.course.code }}</span> {{ offering.course.title }}
            <span class="small text-body-secondary">· {% for i in offering.instructors.all %}{{ i.get_full_name }}{% if not forloop.last %}, {% endif %}{% empty %}no instructor{% endfor %}</span></span>
          <span class="d-flex flex-wrap gap-1">
            <span class="badge {% if status.has_los %}text-bg-success{% else %}text-bg-danger{% endif %}">{% if status.has_los %}✓{% else %}✗{% endif %} LOs</span>
            <span class="badge {% if status.has_assessments %}text-bg-success{% else %}text-bg-danger{% endif %}">{% if status.has_assessments %}✓{% else %}✗{% endif %} Assessments</span>
            <span class="badge {% if status.has_assessment_lo and status.has_lo_po %}text-bg-success{% else %}text-bg-danger{% endif %}">{% if status.has_assessment_lo and status.has_lo_po %}✓{% else %}✗{% endif %} Mapping</span>
            <span class="badge {% if status.has_students %}text-bg-success{% else %}text-bg-warning{% endif %}">{% if status.has_students %}✓{% else %}!{% endif %} Students</span>
            <span class="badge text-bg-light border">{{ status.published_count }}/{{ status.assessment_count }} published</span>
          </span>
        </div>
      </a>
    {% endfor %}
  </div>
{% else %}
  <p class="text-body-secondary">No offerings in {{ selected_term.name }}.</p>
{% endif %}
{% endif %}
{% endblock %}
```

Every badge carries ✓, ✗ or ! as well as its colour, because colour alone isn't accessible (§8.2).

### Tests

The hand computation the tests use. **Spring 2026 (closed)**: one course, three students scoring 50, 70 and 90. Each grade is directly the PO score. **Fall 2026 (open)**: student 1 also scores 30 in another course feeding the same PO with the same weight 3.

| Filter | Student 1 | Student 2 | Student 3 | Mean | Attaining ≥ 60 | Rate |
|---|---|---|---|---|---|---|
| Closed only, up to Fall 2026 | 50 | 70 | 90 | 70.0 | 2 | 2/3 = 67% |
| Include open, up to Fall 2026 | (50·3 + 30·3) / 6 = 40 | 70 | 90 | 66.666… → **66.7** | 2 | 67% |
| Include open, up to Spring 2026 | 50 | 70 | 90 | 70.0 | 2 | 67% |

```python
# apps/scoring/tests/test_aggregates_program.py
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.catalog.models import Term
from apps.core.tests.factories import ProgramOutcomeFactory, TermFactory
from apps.core.tests.scenarios import one_lo_class
from apps.scoring.aggregates import program_po_summary
from apps.scoring.engine import display

pytestmark = pytest.mark.django_db


@pytest.fixture
def dept():
    spring = TermFactory(code="2026S", name="Spring 2026", starts_on=date(2026, 2, 9),
                         ends_on=date(2026, 6, 15), status=Term.Status.CLOSED)
    fall = TermFactory(code="2026F", name="Fall 2026", starts_on=date(2026, 9, 14),
                       ends_on=date(2027, 1, 22), status=Term.Status.OPEN)
    a = one_lo_class(students_scores=[(None, 50), (None, 70), (None, 90)], term=spring)
    b = one_lo_class(students_scores=[(a.students[0], 30)], term=fall, po=a.po)
    return SimpleNamespace(spring=spring, fall=fall, a=a, b=b, program=a.program, po=a.po)


def _for(summaries, po):
    return next(s for s in summaries if s.po.id == po.id)


def test_closed_terms_only_matches_hand_computation(dept):
    """B10 AC1."""
    s = _for(program_po_summary(dept.program, terms=[dept.spring, dept.fall],
                                include_open_terms=False), dept.po)
    assert s.mean == Decimal("70")
    assert (s.n_evidence, s.n_attaining) == (3, 2)
    assert s.rate == Decimal(2) / Decimal(3)


def test_including_open_terms_changes_the_numbers(dept):
    """B10 AC2: student 1 drops to 40 once Fall 2026 counts."""
    s = _for(program_po_summary(dept.program, terms=[dept.spring, dept.fall],
                                include_open_terms=True), dept.po)
    assert display(s.mean) == "66.7"
    assert (s.n_evidence, s.n_attaining) == (3, 2)


def test_terms_after_the_cutoff_are_ignored(dept):
    s = _for(program_po_summary(dept.program, terms=[dept.spring],
                                include_open_terms=True), dept.po)
    assert s.mean == Decimal("70")


def test_po_without_evidence_has_no_rate(dept):
    lonely = ProgramOutcomeFactory(po_set=dept.po.po_set, number=11)
    s = _for(program_po_summary(dept.program, terms=[dept.spring], include_open_terms=False),
             lonely)
    assert s.mean is None and s.n_evidence == 0 and s.rate is None


def test_no_terms_gives_empty_rows(dept):
    rows = program_po_summary(dept.program, terms=[], include_open_terms=False)
    assert all(r.n_evidence == 0 for r in rows)


def test_cohort_filter(dept):
    student = dept.a.students[2]                 # the 90
    m = student.memberships.get(program=dept.program)
    m.cohort_year = 2023
    m.save()
    s = _for(program_po_summary(dept.program, terms=[dept.spring], include_open_terms=False,
                                cohort=2023), dept.po)
    assert (s.mean, s.n_evidence) == (Decimal("90"), 1)
```

```python
# apps/reports/tests/test_department.py
from datetime import date

import pytest
from django.urls import reverse

from apps.catalog.models import Term
from apps.core.tests.factories import (
    CourseFactory,
    MembershipFactory,
    OfferingFactory,
    TermFactory,
    UserFactory,
)
from apps.core.tests.scenarios import one_lo_class

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    spring = TermFactory(code="2026S", name="Spring 2026", starts_on=date(2026, 2, 9),
                         ends_on=date(2026, 6, 15), status=Term.Status.CLOSED)
    fall = TermFactory(code="2026F", name="Fall 2026", starts_on=date(2026, 9, 14),
                       ends_on=date(2027, 1, 22), status=Term.Status.OPEN)
    a = one_lo_class(students_scores=[(None, 50), (None, 70), (None, 90)], term=spring)
    one_lo_class(students_scores=[(a.students[0], 30)], term=fall, po=a.po)
    head = UserFactory()
    MembershipFactory(user=head, program=a.program, role="head")
    return spring, fall, a, head


def test_defaults_to_latest_closed_term_closed_only(client, setup):
    spring, _fall, _a, head = setup
    client.force_login(head)
    resp = client.get(reverse("reports:department"))
    assert resp.status_code == 200
    assert resp.context["selected_term"] == spring
    assert resp.context["include_open_terms"] is False
    assert b"70.0" in resp.content
    assert b"67%" in resp.content


def test_toggle_changes_numbers_and_label(client, setup):
    """B10 AC2."""
    _spring, fall, _a, head = setup
    client.force_login(head)

    closed = client.get(reverse("reports:department"), {"term": fall.id})
    assert b"Fall 2026 is still open and not counted" in closed.content
    assert b"70.0" in closed.content

    with_open = client.get(reverse("reports:department"), {"term": fall.id, "include_open": "on"})
    assert b"including courses still in progress" in with_open.content
    assert b"66.7" in with_open.content


def test_offerings_list_flags_incomplete_setup(client, setup):
    _spring, fall, a, head = setup
    bare = OfferingFactory(course=CourseFactory(program=a.program, code="CSE 999"), term=fall)
    client.force_login(head)
    resp = client.get(reverse("reports:department"), {"term": fall.id})
    statuses = {o.id: s for o, s in resp.context["offerings"]}
    assert statuses[bare.id].is_complete is False
    assert b"CSE 999" in resp.content
    assert b"\xe2\x9c\x97 LOs" in resp.content          # "✗ LOs"


def test_instructor_cannot_open_department(client, setup):
    _s, _f, a, _head = setup
    teacher = UserFactory()
    MembershipFactory(user=teacher, program=a.program, role="instructor")
    client.force_login(teacher)
    assert client.get(reverse("reports:department")).status_code == 404
```

### Check it works

1. Seed and log in as Prof. Deniz Kara (head). You land on `/department/`.
2. The term shows **Spring 2026** and the label says "Closed terms up to Spring 2026". PO 11 shows "No student has evidence yet". PO 9 has numbers only for cohort 2023 (CSE 341 is its only course).
3. Pick Fall 2026 without the toggle: the label says Fall 2026 is open and not counted, and the numbers don't change.
4. Tick "Include open terms" and Apply: the numbers move, the label says so, and the URL now has `?term=…&include_open=on`. Copy it into a new tab: same view.
5. The Fall 2026 course list shows CSE 221 with ✗ Mapping (the deliberate flaw from Appendix B).
6. Log in as an instructor and open `/department/`: 404.

### Done when

| Acceptance criterion | Proved by |
|---|---|
| B10 AC1: numbers match a hand computation on a 3-student fixture | `test_closed_terms_only_matches_hand_computation`, `test_defaults_to_latest_closed_term_closed_only` |
| B10 AC2: the toggle changes the numbers and the label says so | `test_including_open_terms_changes_the_numbers`, `test_toggle_changes_numbers_and_label` |
| Completion list shows unmapped or unpublished courses | `test_offerings_list_flags_incomplete_setup` |
| Only heads | `test_instructor_cannot_open_department`, matrix row below |

Matrix row: `reports:department`: head ✓, admin ✓, instructor ✗ 404, student ✗ 404, anonymous 302.

### Commits and PR

```
Add program_po_summary with attainment rate (#S3-04)
Add department overview with term filter and open-term toggle (#S3-04)
List term offerings with setup status on the overview (#S3-04)
Test overview numbers against a hand-computed fixture (#S3-04)
```

PR title: **Department overview v1: PO averages, attainment, course completion (S3-04)**

---
## S3-05 · Enrollment CSV import with a dry run

**Points:** 5 · **Owner:** Person A · **Branch:** `feature/S3-05-enrollment-import` · **Depends on:** S1-01, S1-02, S2-02 (`head_program_or_404`), S2-03 (`ensure_term_open`, `enrollments` page, `_program` helper in `catalog/views.py`)

### Goal

The head uploads a class list for one offering. POlaris shows a preview before anything is written: new accounts, students it already knows, students already enrolled, and rows with errors. Then the head confirms. Unknown students get an account, a student membership with their cohort, and an email with a link to set their password. This delivers B3 AC 1, 2 and 4, and it's the same upload → preview → confirm pattern that T1.1 (grade upload) and T1.2 (syllabus) reuse, so get it right once here.

The file format is fixed by the spec: `student_number,email,first_name,last_name,cohort_year`.

Choices, and why:

- **Parse twice, write once.** The upload parses the file and stores the preview on an `IngestionJob` (kind `ENROLLMENTS`). Confirm parses the stored file **again** and writes from that fresh result. If anything changed in between (someone enrolled a student by hand, or created an account), the fresh preview differs from the stored one. We then show the new preview instead of writing data the head never saw.
- **Errors block the import unless the head ticks "skip rows with errors".** That's the T1.1 rule. A head importing 80 students shouldn't be stuck on one typo, but must say so on purpose.
- **A student number that already belongs to someone with a different email is an error, not a match.** Matching silently would enroll the wrong person, and grades would then appear on the wrong profile. The head fixes the file or the account.
- **Turkish Excel files just work.** Excel in Turkish locale saves CSV as Windows-1254 with `;` as the separator. We try UTF-8 (with or without BOM) first, then Windows-1254, and sniff the separator.
- **New accounts get an unusable password**, not a generated one. The email link is a standard Django password-reset token, so there is no password to leak, and the link stops working once it's used (B1 AC3).

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/accounts/services.py` | modify | `get_or_create_student`, `send_set_password_email` |
| `apps/accounts/templates/accounts/email/set_password_subject.txt` | create | email subject |
| `apps/accounts/templates/accounts/email/set_password.txt` | create | email body |
| `apps/catalog/importers.py` | create | parsing, preview dataclasses, job creation, confirm |
| `apps/catalog/forms.py` | modify | `EnrollmentImportForm` |
| `apps/catalog/views.py` | modify | `enrollment_import`, `enrollment_import_preview`, `enrollment_import_confirm` |
| `apps/catalog/urls.py` | modify | three paths |
| `apps/catalog/templates/catalog/enrollment_import.html` | create | upload form and format help |
| `apps/catalog/templates/catalog/enrollment_import_preview.html` | create | dry-run report |
| `config/settings/base.py` | modify | `SITE_URL` |
| `.env.example` | modify | `SITE_URL` |
| `seed/enrollments/sample_class.csv` | create | example file linked from the upload page |
| `apps/catalog/tests/test_enrollment_import.py` | create | tests |

### Steps

**1. Accounts services.** `get_or_create_student` matches by student number. Matching happens in the importer, which has already refused conflicting rows, so here we only create what's missing. `create_user(password=None)` stores an *unusable* password (Django's `set_password(None)`), so nobody can log in until they use the email link.

`send_set_password_email` builds the same link Django's password-reset flow uses (`uidb64` + token) and points at our `accounts:password_reset_confirm` view from S1-01/S2-09. It needs an absolute URL. During a request we use the request's host. Outside a request (a management command) we fall back to a new setting, `SITE_URL`.

```python
# apps/accounts/services.py  (add; merge imports)
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import ProgramMembership, User


def get_or_create_student(*, student_number, email, first_name, last_name, program, cohort_year):
    """Find a student by number or create them with an unusable password.
    Always ensures a student membership in `program`. Returns (user, created)."""
    user = User.objects.filter(student_number=student_number).first()
    created = user is None
    if created:
        user = User.objects.create_user(
            email=email, password=None, first_name=first_name, last_name=last_name,
            student_number=student_number,
        )
    ProgramMembership.objects.get_or_create(
        user=user, program=program, role=ProgramMembership.Role.STUDENT,
        defaults={"cohort_year": cohort_year},
    )
    return user, created


def set_password_link(user, request=None) -> str:
    path = reverse("accounts:password_reset_confirm", kwargs={
        "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
    })
    if request is not None:
        return request.build_absolute_uri(path)
    return settings.SITE_URL.rstrip("/") + path


def send_set_password_email(user, request=None) -> None:
    context = {"user": user, "link": set_password_link(user, request)}
    subject = render_to_string("accounts/email/set_password_subject.txt", context).strip()
    body = render_to_string("accounts/email/set_password.txt", context)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
```

```text
{# apps/accounts/templates/accounts/email/set_password_subject.txt #}
Your POlaris account is ready
```

```text
{# apps/accounts/templates/accounts/email/set_password.txt #}
{% autoescape off %}Hello {{ user.first_name }},

The CSE department has added you to POlaris, where you can follow your program outcome scores.

Set your password here (the link works once):
{{ link }}

Your login is {{ user.email }}.

If you weren't expecting this, you can ignore this email.
{% endautoescape %}
```

In `config/settings/base.py`, next to the other `env(...)` reads:

```python
SITE_URL = env("SITE_URL", default="http://localhost:8000")
```

And in `.env.example`:

```
SITE_URL=http://localhost:8000
# staging/production: SITE_URL=https://polaris-cse.duckdns.org
```

**2. The importer: data shapes.** The preview must survive being stored as JSON on the job and loaded back on the preview page. So it is made of plain dataclasses with `to_json` / `from_json`, and only strings, ints, lists and None inside.

Row statuses:

| Status | Meaning | What confirm does |
|---|---|---|
| `new` | Student number unknown | Create account + membership, enroll, email |
| `existing` | Known student, not in this offering (or dropped earlier) | Enroll (or re-enroll) |
| `enrolled` | Already enrolled here | Nothing |
| `error` | Something is wrong; `errors` says what | Nothing; blocks confirm unless skipped |

```python
# apps/catalog/importers.py
"""Enrollment CSV import (B3): parse → preview (no writes) → confirm (one transaction)."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass, field

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import get_or_create_student, send_set_password_email
from apps.core.audit import record
from apps.ingestion.models import IngestionJob

from .models import Enrollment
from .services import ensure_term_open

MAX_BYTES = 1_000_000
COLUMNS = ("student_number", "email", "first_name", "last_name", "cohort_year")
HEADER_ALIASES = {
    "student_no": "student_number", "student_number": "student_number", "number": "student_number",
    "öğrenci_no": "student_number", "ogrenci_no": "student_number", "no": "student_number",
    "email": "email", "e-mail": "email", "e_mail": "email", "e-posta": "email",
    "first_name": "first_name", "firstname": "first_name", "name": "first_name", "ad": "first_name",
    "adı": "first_name",
    "last_name": "last_name", "lastname": "last_name", "surname": "last_name", "soyad": "last_name",
    "soyadı": "last_name",
    "cohort_year": "cohort_year", "cohort": "cohort_year", "giriş_yılı": "cohort_year",
}
STUDENT_NUMBER = re.compile(r"^[0-9A-Za-z-]{3,20}$")


@dataclass
class ImportRow:
    line: int                                # line number in the file, header = 1
    student_number: str
    email: str
    first_name: str
    last_name: str
    cohort_year: int | None
    status: str = "new"                      # new | existing | enrolled | error
    errors: list[str] = field(default_factory=list)
    user_id: int | None = None

    def fail(self, message: str) -> None:
        self.status = "error"
        self.errors.append(message)


@dataclass
class EnrollmentImportPreview:
    rows: list[ImportRow] = field(default_factory=list)
    file_errors: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out = {"new": 0, "existing": 0, "enrolled": 0, "error": 0}
        for r in self.rows:
            out[r.status] += 1
        return out

    @property
    def has_errors(self) -> bool:
        return bool(self.file_errors) or any(r.status == "error" for r in self.rows)

    @property
    def actionable(self) -> int:
        c = self.counts
        return c["new"] + c["existing"]

    def to_json(self) -> dict:
        return {"rows": [asdict(r) for r in self.rows], "file_errors": list(self.file_errors)}

    @classmethod
    def from_json(cls, data: dict) -> EnrollmentImportPreview:
        return cls(rows=[ImportRow(**r) for r in data.get("rows", [])],
                   file_errors=list(data.get("file_errors", [])))

    def signature(self) -> list[tuple]:
        """What must not change between preview and confirm."""
        return [(r.line, r.student_number, r.status, r.user_id) for r in self.rows]


@dataclass(frozen=True)
class ImportResult:
    created_accounts: int
    enrolled: int
    reactivated: int
    skipped: int


class PreviewOutdated(Exception):
    """Raised by confirm when the data changed since the head saw the preview."""

    def __init__(self, fresh: EnrollmentImportPreview):
        super().__init__("The class list or the accounts changed since the preview.")
        self.fresh = fresh
```

**3. The importer: parsing.** Read the bytes once, decode, sniff the separator, normalise the header, then check each row twice. The first pass checks the row on its own (required fields, email format, cohort year) and finds duplicates *within the file*. The second pass checks it against the database in two queries in total, one by student number and one by email, not one per row.

```python
# apps/catalog/importers.py  (continued)

def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1254"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError("We couldn't read this file's text encoding. Save it as CSV UTF-8 and try again.")


def _normalise_header(cell: str) -> str:
    key = cell.strip().lower().replace(" ", "_")
    return HEADER_ALIASES.get(key, key)


def _read_rows(text: str) -> tuple[list[str], list[list[str]]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = list(reader)
    if not rows:
        return [], []
    return [_normalise_header(c) for c in rows[0]], rows[1:]


def _row_errors(row: ImportRow) -> None:
    if not row.student_number:
        row.fail("Student number is missing.")
    elif not STUDENT_NUMBER.match(row.student_number):
        row.fail(f"“{row.student_number}” doesn't look like a student number.")
    if not row.email:
        row.fail("Email is missing.")
    else:
        try:
            validate_email(row.email)
        except ValidationError:
            row.fail(f"“{row.email}” isn't a valid email address.")
    if not row.first_name or not row.last_name:
        row.fail("First and last name are both required.")
    if row.cohort_year is None:
        row.fail("Cohort year is missing or not a year (e.g. 2024).")


def _cohort(value: str) -> int | None:
    value = value.strip()
    if not value.isdigit():
        return None
    year = int(value)
    return year if 1990 <= year <= 2100 else None


def parse_enrollment_csv(file, *, offering) -> EnrollmentImportPreview:
    """Read a class list and classify every row against the database. Never writes."""
    preview = EnrollmentImportPreview()
    raw = file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        preview.file_errors.append("The file is larger than 1 MB. A class list should be far smaller.")
        return preview
    try:
        header, body = _read_rows(_decode(raw))
    except ValidationError as exc:
        preview.file_errors.extend(exc.messages)
        return preview

    missing = [c for c in COLUMNS if c not in header]
    if missing:
        preview.file_errors.append(
            "Missing column(s): " + ", ".join(missing)
            + ". The first row must be: " + ",".join(COLUMNS) + "."
        )
        return preview
    index = {name: header.index(name) for name in COLUMNS}

    def cell(values: list[str], name: str) -> str:
        i = index[name]
        return values[i].strip() if i < len(values) else ""

    seen_numbers: dict[str, int] = {}
    seen_emails: dict[str, int] = {}
    for offset, values in enumerate(body, start=2):
        if not any(v.strip() for v in values):
            continue                                   # blank line
        row = ImportRow(
            line=offset,
            student_number=cell(values, "student_number"),
            email=cell(values, "email").lower(),
            first_name=cell(values, "first_name"),
            last_name=cell(values, "last_name"),
            cohort_year=_cohort(cell(values, "cohort_year")),
        )
        _row_errors(row)
        if row.student_number:
            if row.student_number in seen_numbers:
                row.fail(f"Student number {row.student_number} appears twice in the file "
                         f"(also on line {seen_numbers[row.student_number]}).")
            else:
                seen_numbers[row.student_number] = row.line
        if row.email:
            if row.email in seen_emails:
                row.fail(f"Email {row.email} appears twice in the file (also on line {seen_emails[row.email]}).")
            else:
                seen_emails[row.email] = row.line
        preview.rows.append(row)

    _match_against_database(preview, offering)
    return preview


def _match_against_database(preview: EnrollmentImportPreview, offering) -> None:
    candidates = [r for r in preview.rows if r.status != "error"]
    by_number = {u.student_number: u for u in
                 User.objects.filter(student_number__in=[r.student_number for r in candidates])}
    by_email = {u.email_lower: u for u in
                User.objects.annotate(email_lower=Lower("email"))
                .filter(email_lower__in=[r.email for r in candidates])}
    enrolled_ids = set(
        Enrollment.objects.filter(offering=offering, status=Enrollment.Status.ENROLLED)
        .values_list("student_id", flat=True)
    )

    for row in candidates:
        user = by_number.get(row.student_number)
        if user is not None:
            if user.email.lower() != row.email:
                row.fail(f"Student number {row.student_number} belongs to {user.email} in POlaris, "
                         f"but the file says {row.email}. Fix the file or the account first.")
                continue
            row.user_id = user.pk
            row.status = "enrolled" if user.pk in enrolled_ids else "existing"
            continue
        other = by_email.get(row.email)
        if other is not None:
            row.fail(f"{row.email} already belongs to another account"
                     f"{' (student ' + other.student_number + ')' if other.student_number else ''}.")
            continue
        row.status = "new"
```

**4. The importer: job and confirm.** Both write, so both live here, not in the view. `create_enrollment_import_job` stores the file and the preview. `confirm_enrollment_import` re-parses, compares, then writes everything in one transaction:

- `ensure_term_open` first: nothing in a closed term changes (§5.3).
- If the data changed, the fresh preview is saved and `PreviewOutdated` is raised **after** the `atomic()` block ends. Raising inside the block would roll back that save too.
- `select_for_update()` on the job row, so a double-clicked Confirm can't import twice. The second request waits, then sees status `APPLIED` and stops.
- Emails go out with `transaction.on_commit`. If the transaction rolls back, no email is sent for an account that doesn't exist.
- One audit event per enrollment (`enrollment.create` or `enrollment.reactivate`). That way the history of a student's enrollment reads naturally in T1.4.

```python
# apps/catalog/importers.py  (continued)

def create_enrollment_import_job(user, offering, uploaded_file) -> IngestionJob:
    preview = parse_enrollment_csv(uploaded_file, offering=offering)
    uploaded_file.seek(0)
    return IngestionJob.objects.create(
        offering=offering,
        kind=IngestionJob.Kind.ENROLLMENTS,
        file=uploaded_file,
        original_filename=uploaded_file.name[:255],
        status=IngestionJob.Status.READY,
        result=preview.to_json(),
        created_by=user,
    )


def stored_preview(job: IngestionJob) -> EnrollmentImportPreview:
    return EnrollmentImportPreview.from_json(job.result or {})


def confirm_enrollment_import(user, job: IngestionJob, *, skip_invalid=False,
                              request=None) -> ImportResult:
    with transaction.atomic():
        job = IngestionJob.objects.select_for_update().select_related(
            "offering__course__program", "offering__term").get(pk=job.pk)
        if job.status != IngestionJob.Status.READY:
            raise ValidationError("This import was already applied or discarded.")
        offering = job.offering
        ensure_term_open(offering)

        with job.file.open("rb") as f:
            fresh = parse_enrollment_csv(f, offering=offering)
        outdated = fresh.signature() != stored_preview(job).signature()
        if outdated:
            # Save the fresh preview and leave the block normally, so this save is committed.
            job.result = fresh.to_json()
            job.save(update_fields=["result", "updated_at"])
        else:
            result = apply_enrollment_import(user, offering, fresh, skip_invalid=skip_invalid,
                                             request=request)
            job.status = IngestionJob.Status.APPLIED
            job.applied_at = timezone.now()
            job.save(update_fields=["status", "applied_at", "updated_at"])

    if outdated:
        raise PreviewOutdated(fresh)     # raised outside the transaction, or the save above would roll back
    return result


def apply_enrollment_import(user, offering, preview: EnrollmentImportPreview, *,
                            skip_invalid=False, request=None) -> ImportResult:
    """Write a preview. Call inside a transaction (confirm does)."""
    if preview.file_errors:
        raise ValidationError(preview.file_errors)
    if preview.has_errors and not skip_invalid:
        raise ValidationError("Some rows have errors. Fix the file, or tick “skip rows with errors”.")

    program = offering.course.program
    created = enrolled = reactivated = skipped = 0
    for row in preview.rows:
        if row.status in ("error", "enrolled"):
            skipped += 1
            continue
        student, is_new = get_or_create_student(
            student_number=row.student_number, email=row.email,
            first_name=row.first_name, last_name=row.last_name,
            program=program, cohort_year=row.cohort_year,
        )
        enrollment, enr_created = Enrollment.objects.get_or_create(offering=offering, student=student)
        if enr_created:
            enrolled += 1
            record(user, "enrollment.create", enrollment, offering=offering,
                   after={"student": student.student_number, "status": enrollment.status})
        elif enrollment.status == Enrollment.Status.DROPPED:
            enrollment.status = Enrollment.Status.ENROLLED
            enrollment.save(update_fields=["status"])
            reactivated += 1
            record(user, "enrollment.reactivate", enrollment, offering=offering,
                   before={"status": "dropped"}, after={"status": "enrolled"})
        if is_new:
            created += 1
            transaction.on_commit(lambda s=student: send_set_password_email(s, request))
    return ImportResult(created_accounts=created, enrolled=enrolled,
                        reactivated=reactivated, skipped=skipped)
```

Note `lambda s=student: …`. Without the default argument, every callback would capture the *last* student of the loop, which is Python's late-binding closure trap.

**5. Form.** The head picks the offering on the form. Only offerings of their program in terms that aren't closed are offered, so closed terms are refused before upload as well as by the service.

```python
# apps/catalog/forms.py  (add)
from pathlib import Path

from django import forms

from .importers import MAX_BYTES
from .models import CourseOffering, Term


class EnrollmentImportForm(forms.Form):
    offering = forms.ModelChoiceField(queryset=CourseOffering.objects.none(), label="Course offering")
    file = forms.FileField(label="Class list (CSV)",
                           help_text="Columns: student_number, email, first_name, last_name, cohort_year")

    def __init__(self, *args, program, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["offering"].queryset = (
            CourseOffering.objects.filter(course__program=program)
            .exclude(term__status=Term.Status.CLOSED)
            .select_related("course", "term")
            .order_by("-term__starts_on", "course__code", "section")
        )
        self.fields["offering"].label_from_instance = (
            lambda o: f"{o.course.code} {o.course.title} · {o.term.name} · section {o.section}"
        )

    def clean_file(self):
        f = self.cleaned_data["file"]
        if Path(f.name).suffix.lower() not in {".csv", ".txt"}:
            raise forms.ValidationError("Upload a .csv file. In Excel: File → Save As → CSV UTF-8.")
        if f.size > MAX_BYTES:
            raise forms.ValidationError("The file is larger than 1 MB.")
        return f
```

**6. Views.** Three thin views. All are head-only, and the job lookup is scoped to the head's program, so a job from another program is 404. Messages tell the head exactly what happened, and the final redirect goes to the offering's enrollment list (S2-03) so they can see the result.

```python
# apps/catalog/views.py  (add; merge imports)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import require_role
from apps.ingestion.models import IngestionJob

from .forms import EnrollmentImportForm
from .importers import (
    PreviewOutdated,
    confirm_enrollment_import,
    create_enrollment_import_job,
    stored_preview,
)
def _import_job(request, job_id):
    return get_object_or_404(
        IngestionJob.objects.select_related("offering__course", "offering__term"),
        pk=job_id, kind=IngestionJob.Kind.ENROLLMENTS,
        offering__course__program=_program(request),   # S2-03 helper in this file
    )


@login_required
@require_role("head")
def enrollment_import(request):
    program = _program(request)
    form = EnrollmentImportForm(request.POST or None, request.FILES or None, program=program)
    if request.method == "POST" and form.is_valid():
        job = create_enrollment_import_job(request.user, form.cleaned_data["offering"],
                                           form.cleaned_data["file"])
        return redirect("catalog:enrollment_import_preview", job_id=job.pk)
    return render(request, "catalog/enrollment_import.html", {"form": form})


@login_required
@require_role("head")
def enrollment_import_preview(request, job_id):
    job = _import_job(request, job_id)
    return render(request, "catalog/enrollment_import_preview.html",
                  {"job": job, "preview": stored_preview(job)})


@login_required
@require_role("head")
@require_POST
def enrollment_import_confirm(request, job_id):
    job = _import_job(request, job_id)
    try:
        result = confirm_enrollment_import(request.user, job,
                                           skip_invalid=bool(request.POST.get("skip_invalid")),
                                           request=request)
    except PreviewOutdated:
        messages.warning(request, "Something changed since you opened this preview. "
                                  "Here is the updated one. Check it and confirm again.")
        return redirect("catalog:enrollment_import_preview", job_id=job.pk)
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
        return redirect("catalog:enrollment_import_preview", job_id=job.pk)

    messages.success(
        request,
        f"Imported: {result.enrolled} enrolled, {result.reactivated} re-enrolled, "
        f"{result.created_accounts} new account(s) emailed, {result.skipped} row(s) skipped.",
    )
    return redirect("catalog:enrollments", offering_id=job.offering_id)
```

```python
# apps/catalog/urls.py  (add)
    path("department/enrollments/import/", views.enrollment_import, name="enrollment_import"),
    path("department/enrollments/import/<int:job_id>/", views.enrollment_import_preview,
         name="enrollment_import_preview"),
    path("department/enrollments/import/<int:job_id>/confirm/", views.enrollment_import_confirm,
         name="enrollment_import_confirm"),
```

**7. Templates.** The upload page shows the format and links to a sample file. The *Blank Slate* chapter of Getting Real applies here: the first thing a head sees should teach them what a good file looks like.

```django
{# apps/catalog/templates/catalog/enrollment_import.html #}
{% extends "base.html" %}
{% load static %}

{% block title %}Import a class list{% endblock %}

{% block content %}
<h1 class="h3">Import a class list</h1>
<div class="row g-4">
  <div class="col-lg-6">
    <form method="post" enctype="multipart/form-data" novalidate>
      {% csrf_token %}
      {% for field in form %}
        <div class="mb-3">
          <label for="{{ field.id_for_label }}" class="form-label">{{ field.label }}</label>
          {{ field }}
          {% if field.help_text %}<div class="form-text">{{ field.help_text }}</div>{% endif %}
          {% for error in field.errors %}<div class="invalid-feedback d-block">{{ error }}</div>{% endfor %}
        </div>
      {% endfor %}
      <button type="submit" class="btn btn-primary">Upload and preview</button>
      <span class="small text-body-secondary ms-2">Nothing is saved until you confirm.</span>
    </form>
  </div>
  <div class="col-lg-6">
    <h2 class="h6">File format</h2>
    <pre class="bg-body-tertiary p-2 small mb-2">student_number,email,first_name,last_name,cohort_year
2024-0001,ayse.kaya@example.edu,Ayşe,Kaya,2024
2024-0002,mert.demir@example.edu,Mert,Demir,2024</pre>
    <ul class="small">
      <li>Excel's Turkish CSV (semicolons, Windows-1254) works too.</li>
      <li>Students we already know are matched by student number.</li>
      <li>New students get an account and an email to set their password.</li>
    </ul>
    <a href="{% static 'samples/sample_class.csv' %}" download>Download a sample file</a>
  </div>
</div>
{% endblock %}
```

Copy `seed/enrollments/sample_class.csv` to `static/samples/sample_class.csv` so it's served. Keep both: the seed copy is used by tests.

```django
{# apps/catalog/templates/catalog/enrollment_import_preview.html #}
{% extends "base.html" %}

{% block title %}Import preview{% endblock %}

{% block content %}
<h1 class="h3">Import preview <small class="text-body-secondary">{{ job.original_filename }}</small></h1>
<p>Into <strong>{{ job.offering.course.code }} {{ job.offering.course.title }}</strong> · {{ job.offering.term.name }}.
   Nothing has been saved yet.</p>

{% if preview.file_errors %}
  <div class="alert alert-danger">
    {% for e in preview.file_errors %}<p class="mb-0">{{ e }}</p>{% endfor %}
  </div>
  <a href="{% url 'catalog:enrollment_import' %}" class="btn btn-outline-primary">Upload another file</a>
{% else %}
  {% with c=preview.counts %}
  <div class="row g-2 mb-3 text-center">
    <div class="col-6 col-md-3"><div class="border rounded p-2"><div class="fs-4">{{ c.new }}</div><div class="small">✚ new accounts</div></div></div>
    <div class="col-6 col-md-3"><div class="border rounded p-2"><div class="fs-4">{{ c.existing }}</div><div class="small">✓ known students to enroll</div></div></div>
    <div class="col-6 col-md-3"><div class="border rounded p-2"><div class="fs-4">{{ c.enrolled }}</div><div class="small">= already enrolled</div></div></div>
    <div class="col-6 col-md-3"><div class="border rounded p-2 {% if c.error %}border-danger{% endif %}"><div class="fs-4">{{ c.error }}</div><div class="small">✗ rows with errors</div></div></div>
  </div>
  {% endwith %}

  <div class="table-responsive mb-3" style="max-height: 60vh">
    <table class="table table-sm align-middle">
      <thead class="pl-sticky-head">
        <tr><th scope="col">Line</th><th scope="col">Student no.</th><th scope="col">Name</th>
            <th scope="col">Email</th><th scope="col">Cohort</th><th scope="col">Result</th></tr>
      </thead>
      <tbody>
        {% for r in preview.rows %}
          <tr class="{% if r.status == 'error' %}table-danger{% elif r.status == 'enrolled' %}text-body-secondary{% endif %}">
            <td>{{ r.line }}</td>
            <td class="font-monospace">{{ r.student_number }}</td>
            <td>{{ r.first_name }} {{ r.last_name }}</td>
            <td>{{ r.email }}</td>
            <td>{{ r.cohort_year|default:"" }}</td>
            <td>
              {% if r.status == "new" %}✚ New account
              {% elif r.status == "existing" %}✓ Enroll
              {% elif r.status == "enrolled" %}= Already enrolled
              {% else %}✗ {% for e in r.errors %}<span class="d-block">{{ e }}</span>{% endfor %}{% endif %}
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  {% if job.status == "ready" %}
    <form method="post" action="{% url 'catalog:enrollment_import_confirm' job.id %}" class="d-flex flex-wrap align-items-center gap-3">
      {% csrf_token %}
      {% if preview.has_errors %}
        <div class="form-check">
          <input class="form-check-input" type="checkbox" name="skip_invalid" id="skip_invalid" value="1">
          <label class="form-check-label" for="skip_invalid">Skip rows with errors and import the rest</label>
        </div>
      {% endif %}
      <button type="submit" class="btn btn-primary" {% if not preview.actionable %}disabled{% endif %}>
        Confirm import ({{ preview.actionable }} student{{ preview.actionable|pluralize }})
      </button>
      <a href="{% url 'catalog:enrollment_import' %}" class="btn btn-link">Start over</a>
    </form>
  {% else %}
    <div class="alert alert-info">This import was {{ job.get_status_display|lower }}.</div>
  {% endif %}
{% endif %}
{% endblock %}
```

**8. Sample file.** It's also the "clean" fixture for the tests.

```text
# seed/enrollments/sample_class.csv
student_number,email,first_name,last_name,cohort_year
2024-0101,zeynep.arslan@example.edu,Zeynep,Arslan,2024
2024-0102,emre.celik@example.edu,Emre,Çelik,2024
2024-0103,selin.koc@example.edu,Selin,Koç,2024
2023-0150,baris.yildirim@example.edu,Barış,Yıldırım,2023
```

(Don't keep the `# seed/...` comment line in the real file. It only labels the block here.)

### Tests

`mailoutbox` and `django_capture_on_commit_callbacks` are pytest-django fixtures. The first collects sent emails. The second runs `on_commit` callbacks, which otherwise never fire inside a test transaction.

```python
# apps/catalog/tests/test_enrollment_import.py
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import ProgramMembership, User
from apps.catalog.importers import (
    PreviewOutdated,
    confirm_enrollment_import,
    create_enrollment_import_job,
    parse_enrollment_csv,
)
from apps.catalog.models import Enrollment, Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import (
    EnrollmentFactory,
    MembershipFactory,
    OfferingFactory,
    TermFactory,
    UserFactory,
)
from apps.ingestion.models import IngestionJob

pytestmark = pytest.mark.django_db

HEADER = "student_number,email,first_name,last_name,cohort_year\n"


def upload(text, name="class.csv", encoding="utf-8"):
    return SimpleUploadedFile(name, text.encode(encoding), content_type="text/csv")


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def offering():
    term = TermFactory(code="2026F", name="Fall 2026", starts_on=date(2026, 9, 14),
                       ends_on=date(2027, 1, 22), status=Term.Status.OPEN)
    return OfferingFactory(term=term)


@pytest.fixture
def head(offering):
    user = UserFactory()
    MembershipFactory(user=user, program=offering.course.program, role="head")
    return user


def test_classifies_new_existing_and_enrolled(offering):
    known = UserFactory(student_number="2024-0002", email="known@example.edu")
    already = UserFactory(student_number="2024-0003", email="already@example.edu")
    EnrollmentFactory(offering=offering, student=already)
    preview = parse_enrollment_csv(upload(
        HEADER
        + "2024-0001,new@example.edu,Ada,Lovelace,2024\n"
        + "2024-0002,KNOWN@example.edu,Known,Student,2024\n"
        + "2024-0003,already@example.edu,Already,There,2024\n"
    ), offering=offering)

    assert [r.status for r in preview.rows] == ["new", "existing", "enrolled"]
    assert preview.rows[1].user_id == known.pk          # email compared case-insensitively
    assert preview.counts == {"new": 1, "existing": 1, "enrolled": 1, "error": 0}
    assert preview.actionable == 2


def test_reports_every_kind_of_row_error(offering):
    """B3 AC2 and AC4: duplicates are reported, not a crash."""
    UserFactory(student_number="2024-0009", email="owner@example.edu")
    UserFactory(student_number="2024-0010", email="taken@example.edu")
    preview = parse_enrollment_csv(upload(
        HEADER
        + "2024-0001,,No,Email,2024\n"                       # missing email
        + "2024-0002,a@example.edu,Dup,One,2024\n"
        + "2024-0002,b@example.edu,Dup,Two,2024\n"           # duplicate number in file
        + "2024-0004,not-an-email,Bad,Email,2024\n"
        + "2024-0005,c@example.edu,Bad,Cohort,24\n"           # cohort not a year
        + "2024-0009,someone@example.edu,Wrong,Email,2024\n"  # number belongs to another email
        + "2024-0011,taken@example.edu,Email,Taken,2024\n"    # email belongs to another account
    ), offering=offering)

    statuses = [r.status for r in preview.rows]
    assert statuses == ["error", "new", "error", "error", "error", "error", "error"]
    messages = " ".join(e for r in preview.rows for e in r.errors)
    assert "Email is missing" in messages
    assert "appears twice in the file (also on line 3)" in messages
    assert "isn't a valid email" in messages
    assert "Cohort year" in messages
    assert "belongs to owner@example.edu" in messages
    assert "already belongs to another account (student 2024-0010)" in messages


def test_turkish_excel_csv_is_decoded(offering):
    text = ("student_number;email;first_name;last_name;cohort_year\n"
            "2024-0001;sukru@example.edu;Şükrü;Öztürk;2024\n")
    preview = parse_enrollment_csv(upload(text, encoding="cp1254"), offering=offering)
    assert preview.file_errors == []
    assert (preview.rows[0].first_name, preview.rows[0].last_name) == ("Şükrü", "Öztürk")


def test_missing_columns_is_a_file_error(offering):
    preview = parse_enrollment_csv(upload("email,first_name\na@b.co,A\n"), offering=offering)
    assert preview.rows == []
    assert "Missing column(s): student_number, last_name, cohort_year" in preview.file_errors[0]


def test_upload_writes_nothing_but_the_job(client, offering, head):
    """B3 AC2: nothing is written until Confirm."""
    users_before = User.objects.count()
    client.force_login(head)
    resp = client.post(reverse("catalog:enrollment_import"), {
        "offering": offering.pk,
        "file": upload(HEADER + "2024-0001,new@example.edu,Ada,Lovelace,2024\n"),
    })
    job = IngestionJob.objects.get(kind=IngestionJob.Kind.ENROLLMENTS)
    assert resp.status_code == 302
    assert resp.url == reverse("catalog:enrollment_import_preview", args=[job.pk])
    assert User.objects.count() == users_before
    assert not Enrollment.objects.filter(offering=offering).exists()

    page = client.get(resp.url)
    assert b"New account" in page.content and b"Nothing has been saved yet" in page.content


def test_confirm_creates_accounts_enrolls_audits_and_emails(
        offering, head, settings, mailoutbox, django_capture_on_commit_callbacks):
    job = create_enrollment_import_job(head, offering, upload(
        HEADER + "2024-0001,new@example.edu,Ada,Lovelace,2024\n"))

    with django_capture_on_commit_callbacks(execute=True):
        result = confirm_enrollment_import(head, job)

    student = User.objects.get(student_number="2024-0001")
    assert not student.has_usable_password()
    assert ProgramMembership.objects.filter(user=student, role="student", cohort_year=2024,
                                            program=offering.course.program).exists()
    assert Enrollment.objects.filter(offering=offering, student=student).exists()
    assert AuditEvent.objects.filter(action="enrollment.create", actor=head).count() == 1
    assert (result.created_accounts, result.enrolled) == (1, 1)
    assert len(mailoutbox) == 1 and mailoutbox[0].to == ["new@example.edu"]
    assert settings.SITE_URL in mailoutbox[0].body          # no request, so SITE_URL is used
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.APPLIED


def test_errors_block_unless_skipped(offering, head):
    job = create_enrollment_import_job(head, offering, upload(
        HEADER + "2024-0001,ok@example.edu,Ok,Row,2024\n2024-0002,,Bad,Row,2024\n"))
    with pytest.raises(ValidationError):
        confirm_enrollment_import(head, job)
    assert not User.objects.filter(student_number="2024-0001").exists()

    result = confirm_enrollment_import(head, job, skip_invalid=True)
    assert (result.enrolled, result.skipped) == (1, 1)


def test_reimporting_the_same_file_changes_nothing(offering, head):
    content = HEADER + "2024-0001,new@example.edu,Ada,Lovelace,2024\n"
    confirm_enrollment_import(head, create_enrollment_import_job(head, offering, upload(content)))
    second = create_enrollment_import_job(head, offering, upload(content))
    result = confirm_enrollment_import(head, second)
    assert (result.created_accounts, result.enrolled, result.skipped) == (0, 0, 1)


def test_confirm_refuses_when_data_changed_since_preview(offering, head):
    job = create_enrollment_import_job(head, offering, upload(
        HEADER + "2024-0001,new@example.edu,Ada,Lovelace,2024\n"))
    UserFactory(student_number="2024-0001", email="new@example.edu")    # created meanwhile
    with pytest.raises(PreviewOutdated) as exc:
        confirm_enrollment_import(head, job)
    assert exc.value.fresh.rows[0].status == "existing"
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.READY
    assert job.result["rows"][0]["status"] == "existing"     # stored preview updated


def test_closed_term_refuses(offering, head):
    job = create_enrollment_import_job(head, offering, upload(
        HEADER + "2024-0001,new@example.edu,Ada,Lovelace,2024\n"))
    Term.objects.filter(pk=offering.term_id).update(status=Term.Status.CLOSED)
    with pytest.raises(ValidationError):
        confirm_enrollment_import(head, job)


def test_second_confirm_is_refused(offering, head):
    job = create_enrollment_import_job(head, offering, upload(
        HEADER + "2024-0001,new@example.edu,Ada,Lovelace,2024\n"))
    confirm_enrollment_import(head, job)
    with pytest.raises(ValidationError, match="already applied"):
        confirm_enrollment_import(head, job)


def test_dropped_student_is_re_enrolled(offering, head):
    student = UserFactory(student_number="2024-0001", email="back@example.edu")
    EnrollmentFactory(offering=offering, student=student, status="dropped")
    job = create_enrollment_import_job(head, offering, upload(
        HEADER + "2024-0001,back@example.edu,Back,Again,2024\n"))
    result = confirm_enrollment_import(head, job)
    assert result.reactivated == 1
    assert Enrollment.objects.get(offering=offering, student=student).status == "enrolled"


def test_job_of_another_program_is_404(client, offering, head):
    other_offering = OfferingFactory(term=offering.term)
    job = create_enrollment_import_job(head, other_offering, upload(HEADER))
    client.force_login(head)
    assert client.get(reverse("catalog:enrollment_import_preview", args=[job.pk])).status_code == 404


def test_sample_file_imports_cleanly(offering):
    with open("seed/enrollments/sample_class.csv", "rb") as f:
        preview = parse_enrollment_csv(f, offering=offering)
    assert not preview.has_errors and len(preview.rows) == 4
```

In `test_reports_every_kind_of_row_error`, line 3 (the first `2024-0002`) is valid and new. Only the second occurrence of a duplicate is an error, and its message points back to line 3.

### Check it works

1. Log in as the head. Go to Department → Offerings → (a Fall 2026 offering) → Import class list, or straight to `/department/enrollments/import/`.
2. Upload `seed/enrollments/sample_class.csv`. The preview shows 4 new accounts and the message "Nothing has been saved yet". Check in the admin: no new users.
3. Confirm. You land on the offering's enrollment list with 4 new students. The terminal running `runserver` prints 4 emails (console backend). Open one link in a private window: you can set a password and log in.
4. Upload the same file again: 4 "already enrolled", and Confirm is disabled.
5. In Excel, save a class list as "CSV (semicolon delimited)" with Turkish names. Upload it: names come through with ç, ğ, ş intact.
6. Add a row with a duplicate student number: the row turns red with the line number of the first occurrence, and Confirm needs the skip box.

### Done when

| Acceptance criterion | Proved by |
|---|---|
| B3 AC1: empty term → offering with 30 students in under 5 minutes | Manual: time it in the sprint review with a 30-row file; note the time in `docs/process/sprint-03/review.md` |
| B3 AC2: preview lists new, existing and errors; nothing written before Confirm | `test_classifies_new_existing_and_enrolled`, `test_reports_every_kind_of_row_error`, `test_upload_writes_nothing_but_the_job` |
| B3 AC4: duplicate student number reported, never a crash | `test_reports_every_kind_of_row_error`, `test_reimporting_the_same_file_changes_nothing` |
| Closed term refused (§5.3) | `test_closed_term_refuses` |
| Audit + set-password email | `test_confirm_creates_accounts_enrolls_audits_and_emails` |
| No double import, no stale preview | `test_second_confirm_is_refused`, `test_confirm_refuses_when_data_changed_since_preview` |

Matrix rows (already in `ROUTES` since S2-02): `catalog:enrollment_import`, `catalog:enrollment_import_preview`, `catalog:enrollment_import_confirm` (POST): head ✓ (the preview and confirm rows use a job in the head's program), instructor ✗ 404, student ✗ 404, anonymous 302.

### Commits and PR

```
Add student account creation and set-password email (#S3-05)
Parse enrollment CSVs into a preview with row-level errors (#S3-05)
Store import previews on IngestionJob and confirm in one transaction (#S3-05)
Add enrollment import pages with dry-run report (#S3-05)
Test enrollment import edge cases and Turkish Excel files (#S3-05)
```

PR title: **Enrollment CSV import with preview and set-password emails (S3-05)**

---
## S3-07 · `seed_demo` v2: a believable department

**Points:** 2 · **Owner:** Person B · **Branch:** `feature/S3-07-seed-demo-v2` · **Depends on:** S1-05 (CSE program + 11 POs), S1-10 (`seed_demo` v1), S3-01

### Goal

One command fills a fresh database with the department from spec Appendix B: 3 terms, 12 courses (15 offerings), a head who also teaches, 3 instructors, 120 students in three cohorts, and Elif Yıldız, whose profile reproduces the professor's slide exactly. The grades look real, because each student has a hidden ability per PO. The deliberate flaws are there so the lint, the completion panel and the heat map have something to show at the demo. The same seed always produces the same data, so tests, screenshots and the demo script can rely on exact numbers.

This version **replaces** v1 from S1-10. The command's name and flags stay the same, so nothing else changes.

Decisions in this story:

- **No Faker.** Appendix B mentions Faker's `tr_TR` locale, but Faker is a dev dependency, and the production image installs without dev dependencies (`uv sync --no-dev`, §10.5). So `seed_demo` would crash on staging, which is where we need it most. We use two short, hand-written lists of Turkish first names and surnames instead. That is also more deterministic: Faker's output can change between Faker versions. Update Appendix B's wording in the same PR.
- **The data is built in code, not with factories.** Factories are test tools (also dev-only) and are slower. The builder uses `bulk_create` for students, enrollments and grades: the full seed creates about 1,400 grades and 560 enrollments in a couple of seconds.
- **The builder skips the services and writes no audit events.** Seed data is not anybody's action, and 1,400 "grade.update" events from nobody would flood T1.4's history viewer. The services' rules (same offering, max score, closed terms) are still respected by construction, and the tests check the important ones.
- **Elif is a separate student**, number `2024-0041`, enrolled only in CSE 311 in Fall 2026. Our cross-course rule is flat (P8). If she also took other courses, those would change her PO 1 and PO 2 and the slide numbers would no longer appear. In the demo story she is a transfer student who joined this term.
- **Demo passwords are fixed in development and random elsewhere.** With `DEBUG=True`, everyone shares easy passwords (printed). With `--allow-production` (staging), the command generates random ones and prints them once. Copy them into the team's password manager. A public staging URL must never accept `student-demo-311`.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/core/seed/__init__.py` | create | empty |
| `apps/core/seed/data.py` | create | terms, people, names, the 12 course definitions, offering plan |
| `apps/core/seed/builder.py` | create | `DemoBuilder`: wipe, build, summary |
| `apps/core/management/commands/seed_demo.py` | replace | thin command around the builder |
| `apps/core/tests/test_seed_demo.py` | create | tests |
| `POLARIS-PROJECT-SPEC.md` | modify | Appendix B: names come from built-in lists, not Faker |

### Steps

**1. The plan, as data.** Everything that makes the department look the way it does is in one file that reads like a table. To change the demo story, edit this file only.

How offerings are spread over terms, and why:

| Term | Offering | Teacher | Students | State |
|---|---|---|---|---|
| Fall 2025 (closed) | CSE 101, MAT 141, PHY 101 | Can, Ayşe, Mehmet | cohort 2025 | all published |
| | CSE 211, CSE 221 | Can, Mehmet | cohort 2024 | all published |
| | CSE 331 | Deniz (head) | cohort 2023 | all published |
| Spring 2026 (closed) | CSE 102, MAT 241 | Can, Ayşe | cohort 2025 | all published |
| | CSE 231 | Deniz | cohort 2024 | all published |
| | CSE 341 | Ayşe | cohort 2023 | all published |
| Fall 2026 (open) | CSE 311 | Deniz | cohort 2024 + Elif | Midterm I and Project published; Final not held |
| | CSE 321 | Can | cohort 2024 | Midterm published; **one grade edited after publishing** |
| | CSE 211 | Can | cohort 2025 | Midterm published |
| | CSE 221 | Mehmet | cohort 2025 | **no mapping at all**, no grades |
| | CSE 101 (retake) | Can | the 3 weakest of cohort 2025 | Quiz and Midterm published (shows P9) |

PO coverage was designed so that **PO 11 is linked by no course** and **PO 9 by exactly one** (CSE 341), as Appendix B requires. The two MAT courses legitimately put more than 60% of their weight on PO 1, so lint L005 fires on them. That's realistic, and it shows at the demo that lint warnings are advice, not errors.

```python
# apps/core/seed/data.py
"""The demo department (spec Appendix B), as plain data. Edit here to change the demo story."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class LOSpec:
    text: str
    po: dict[int, int]                      # PO number -> weight 1..5


@dataclass(frozen=True)
class AssessmentSpec:
    name: str
    kind: str                               # Assessment.Kind value
    max_score: int
    course_weight: int                      # % of the course grade
    lo: dict[int, int]                      # LO number (1-based) -> weight %


@dataclass(frozen=True)
class CourseSpec:
    code: str
    title: str
    credits: str
    ects: str
    los: tuple[LOSpec, ...]
    assessments: tuple[AssessmentSpec, ...]


@dataclass(frozen=True)
class OfferingSpec:
    course: str
    term: str
    teacher: str                            # key in PEOPLE
    cohorts: tuple[str, ...]                # "2023", "2024", "2025", or "retake"
    published: str | tuple[str, ...] = "all"   # "all", "none", or assessment names
    mapped: bool = True
    unpublished_change: bool = False
    elif_here: bool = False


TERMS = (
    ("2025F", "Fall 2025", date(2025, 9, 15), date(2026, 1, 23), "closed"),
    ("2026S", "Spring 2026", date(2026, 2, 9), date(2026, 6, 19), "closed"),
    ("2026F", "Fall 2026", date(2026, 9, 14), date(2027, 1, 22), "open"),
)

# key: (first name, last name, email local part, roles)
PEOPLE = {
    "head": ("Deniz", "Kara", "deniz.kara", ("head", "instructor")),
    "can": ("Can", "Aydın", "can.aydin", ("instructor",)),
    "ayse": ("Ayşe", "Demir", "ayse.demir", ("instructor",)),
    "mehmet": ("Mehmet", "Şahin", "mehmet.sahin", ("instructor",)),
}

ELIF = {"first_name": "Elif", "last_name": "Yıldız", "email": "elif.yildiz@polaris.test",
        "student_number": "2024-0041", "cohort_year": 2024,
        "grades": {"Midterm I": 90, "Project": 80}}

COHORTS = (2023, 2024, 2025)

FIRST_NAMES = (
    "Ahmet", "Ayşe", "Mehmet", "Zeynep", "Mustafa", "Elif", "Ali", "Merve", "Hüseyin", "Esra",
    "Emre", "Büşra", "Burak", "Selin", "Can", "Ceren", "Kerem", "Damla", "Oğuz", "İrem",
    "Yusuf", "Gizem", "Barış", "Defne", "Serkan", "Ebru", "Tolga", "Nazlı", "Onur", "Şeyma",
    "Berk", "Ece", "Umut", "Dilara", "Kaan", "Melis", "Furkan", "Gamze", "Arda", "Özge",
)
LAST_NAMES = (
    "Yılmaz", "Kaya", "Demir", "Çelik", "Şahin", "Yıldız", "Yıldırım", "Öztürk", "Aydın", "Özdemir",
    "Arslan", "Doğan", "Kılıç", "Aslan", "Çetin", "Kara", "Koç", "Kurt", "Özkan", "Şimşek",
    "Polat", "Korkmaz", "Erdoğan", "Güneş", "Aktaş", "Bulut", "Tekin", "Uçar", "Karaca", "Ateş",
)

A = AssessmentSpec
L = LOSpec

COURSES: dict[str, CourseSpec] = {c.code: c for c in (
    CourseSpec("CSE 101", "Introduction to Programming", "4", "6", (
        L("Write, test and debug small Python programs using variables, conditionals, loops and functions.", {1: 2, 2: 4, 4: 3}),
        L("Decompose a problem into functions and choose suitable built-in data structures.", {2: 4, 3: 3}),
        L("Use an editor, the terminal and version control to manage their own code.", {4: 4, 8: 2}),
    ), (
        A("Quiz", "quiz", 20, 10, {1: 100}),
        A("Midterm", "midterm", 100, 30, {1: 60, 2: 40}),
        A("Lab assignments", "lab", 100, 20, {1: 40, 3: 100}),
        A("Final", "final", 100, 40, {1: 50, 2: 60}),
    )),
    CourseSpec("CSE 102", "Object-Oriented Programming", "4", "6", (
        L("Model a problem domain with classes, objects, inheritance and interfaces.", {2: 3, 3: 4}),
        L("Apply exception handling, unit testing and simple design patterns in Java.", {3: 3, 4: 4}),
        L("Develop a small team project with a shared repository.", {6: 4, 4: 2, 7: 2}),
    ), (
        A("Quiz", "quiz", 20, 10, {1: 100}),
        A("Midterm", "midterm", 100, 30, {1: 70, 2: 30}),
        A("Project", "project", 100, 30, {1: 30, 2: 40, 3: 100}),
        A("Final", "final", 100, 30, {1: 50, 2: 50}),
    )),
    CourseSpec("CSE 211", "Data Structures", "4", "6", (
        L("Implement lists, stacks, queues, trees, heaps and hash tables.", {1: 3, 2: 4}),
        L("Analyse the time and space complexity of algorithms with asymptotic notation.", {1: 5, 2: 3}),
        L("Choose an appropriate data structure for a given problem and justify the choice.", {2: 4, 3: 3}),
        L("Write programs that process large inputs efficiently.", {4: 3, 5: 2}),
    ), (
        A("Midterm", "midterm", 100, 30, {1: 50, 2: 50}),
        A("Homework", "homework", 100, 20, {1: 60, 4: 100}),
        A("Final", "final", 100, 50, {1: 40, 2: 50, 3: 100}),
    )),
    CourseSpec("CSE 221", "Digital Logic Design", "3", "5", (
        L("Simplify Boolean functions with Boolean algebra and Karnaugh maps.", {1: 5}),
        L("Design and analyse combinational circuits.", {1: 3, 3: 4}),
        L("Design sequential circuits with flip-flops and finite state machines.", {3: 4, 5: 3}),
        L("Build and test circuits in the laboratory and report the results.", {5: 4, 7: 2, 6: 2}),
    ), (
        A("Midterm", "midterm", 100, 30, {1: 60, 2: 40}),
        A("Lab assignments", "lab", 100, 25, {4: 100, 2: 30}),
        A("Final", "final", 100, 45, {1: 40, 2: 40, 3: 100}),
    )),
    CourseSpec("CSE 231", "Algorithms", "4", "6", (
        L("Design algorithms with divide and conquer, greedy and dynamic programming strategies.", {2: 5, 3: 3}),
        L("Prove the correctness of algorithms and analyse their running time.", {1: 4, 2: 3}),
        L("Apply graph algorithms (BFS, DFS, shortest paths, spanning trees) to practical problems.", {2: 3, 4: 2}),
    ), (
        A("Quiz", "quiz", 20, 10, {2: 100}),
        A("Midterm", "midterm", 100, 35, {1: 60, 2: 60}),
        A("Homework", "homework", 100, 15, {1: 50, 3: 50}),
        A("Final", "final", 100, 40, {1: 40, 2: 40, 3: 100}),
    )),
    # CSE 311 is the professor's slide example. Do not change its LOs, weights or assessment names.
    CourseSpec("CSE 311", "Software Engineering", "3", "5", (
        L("Learn the design choices and philosophy behind building software products.", {1: 4}),
        L("Learn agile software development methodology and best practices.", {1: 2, 2: 5}),
    ), (
        A("Midterm I", "midterm", 100, 25, {1: 60, 2: 40}),
        A("Project", "project", 100, 40, {1: 40, 2: 100}),
        A("Final exam", "final", 100, 35, {1: 50, 2: 50}),
    )),
    CourseSpec("CSE 321", "Data Systems", "3", "5", (
        L("Design relational schemas and normalise them to third normal form.", {3: 4, 2: 2}),
        L("Write SQL queries with joins, aggregation, subqueries and window functions.", {4: 4, 2: 3}),
        L("Explain transactions, isolation levels and indexing, and their effect on performance.", {1: 3, 5: 2}),
        L("Present the data architecture of a team project.", {7: 4, 6: 3, 10: 2}),
    ), (
        A("Midterm", "midterm", 100, 30, {1: 50, 2: 50, 3: 40}),
        A("Project", "project", 100, 40, {1: 50, 4: 100, 2: 30}),
        A("Final", "final", 100, 30, {2: 20, 3: 60}),
    )),
    CourseSpec("CSE 331", "Operating Systems", "4", "6", (
        L("Explain processes, threads, scheduling and synchronisation.", {1: 3, 2: 3}),
        L("Write concurrent programs that avoid race conditions and deadlocks.", {2: 4, 4: 3}),
        L("Describe memory management, virtual memory and file systems.", {1: 4}),
    ), (
        A("Midterm", "midterm", 100, 30, {1: 60, 3: 40}),
        A("Lab assignments", "lab", 100, 30, {2: 100}),
        A("Final", "final", 100, 40, {1: 40, 3: 60, 2: 20}),
    )),
    # The only course linked to PO 9 (Appendix B: "PO 9 covered by only one course").
    CourseSpec("CSE 341", "Professional Practice and Ethics in Computing", "2", "3", (
        L("Analyse ethical dilemmas in computing using professional codes of conduct.", {9: 5, 7: 2}),
        L("Discuss the legal, social and economic impact of software systems.", {8: 3, 10: 3}),
        L("Write and present a technical report as a team.", {7: 4, 6: 3}),
    ), (
        A("Case study essays", "homework", 100, 30, {1: 100, 2: 50}),
        A("Presentation", "presentation", 100, 30, {3: 100}),
        A("Final", "final", 100, 40, {1: 50, 2: 50}),
    )),
    CourseSpec("MAT 141", "Calculus I", "4", "6", (
        L("Compute limits and derivatives and use them to analyse functions.", {1: 5}),
        L("Evaluate definite and indefinite integrals with standard techniques.", {1: 5}),
        L("Model rates of change and optimisation problems from science and engineering.", {1: 3, 2: 3}),
    ), (
        A("Quiz", "quiz", 20, 15, {1: 100}),
        A("Midterm", "midterm", 100, 35, {1: 60, 2: 30}),
        A("Final", "final", 100, 50, {1: 40, 2: 70, 3: 100}),
    )),
    CourseSpec("MAT 241", "Linear Algebra", "3", "5", (
        L("Solve systems of linear equations with Gaussian elimination and matrix methods.", {1: 5}),
        L("Work with vector spaces, bases, eigenvalues and eigenvectors.", {1: 4, 2: 2}),
        L("Apply linear algebra to problems in computer graphics and data analysis.", {2: 3, 4: 2}),
    ), (
        A("Midterm", "midterm", 100, 40, {1: 60, 2: 40}),
        A("Homework", "homework", 100, 20, {2: 50, 3: 100}),
        A("Final", "final", 100, 40, {1: 40, 2: 60, 3: 50}),
    )),
    CourseSpec("PHY 101", "Physics I", "4", "6", (
        L("Apply Newton's laws and conservation principles to mechanical systems.", {1: 5, 2: 2}),
        L("Carry out laboratory experiments, analyse measurement uncertainty and report results.", {5: 5, 7: 2}),
        L("Solve kinematics and dynamics problems with calculus.", {1: 4, 2: 3}),
    ), (
        A("Midterm", "midterm", 100, 30, {1: 60, 3: 50}),
        A("Lab assignments", "lab", 100, 20, {2: 100}),
        A("Final", "final", 100, 50, {1: 40, 3: 50}),
    )),
)}

OFFERINGS: tuple[OfferingSpec, ...] = (
    OfferingSpec("CSE 101", "2025F", "can", ("2025",)),
    OfferingSpec("MAT 141", "2025F", "ayse", ("2025",)),
    OfferingSpec("PHY 101", "2025F", "mehmet", ("2025",)),
    OfferingSpec("CSE 211", "2025F", "can", ("2024",)),
    OfferingSpec("CSE 221", "2025F", "mehmet", ("2024",)),
    OfferingSpec("CSE 331", "2025F", "head", ("2023",)),
    OfferingSpec("CSE 102", "2026S", "can", ("2025",)),
    OfferingSpec("MAT 241", "2026S", "ayse", ("2025",)),
    OfferingSpec("CSE 231", "2026S", "head", ("2024",)),
    OfferingSpec("CSE 341", "2026S", "ayse", ("2023",)),
    OfferingSpec("CSE 311", "2026F", "head", ("2024",), published=("Midterm I", "Project"), elif_here=True),
    OfferingSpec("CSE 321", "2026F", "can", ("2024",), published=("Midterm",), unpublished_change=True),
    OfferingSpec("CSE 211", "2026F", "can", ("2025",), published=("Midterm",)),
    OfferingSpec("CSE 221", "2026F", "mehmet", ("2025",), published="none", mapped=False),
    OfferingSpec("CSE 101", "2026F", "can", ("retake",), published=("Quiz", "Midterm")),
)

RETAKERS = 3                                  # weakest students of cohort 2025 retake CSE 101
```

**2. The builder.** Four things to understand before reading it:

- **One random generator, seeded with 311**, and every random call happens in a fixed order (offerings in `OFFERINGS` order, students by number, assessments by position). Changing the *order* of anything in `data.py` changes every number after it. Append new things at the end.
- **Ability model.** Each student has a base level `μ ~ N(70, 9)` and an ability per PO `~ N(μ, 7)`, clipped to 30–99. An assessment's expected percentage is the student's abilities averaged over the POs it reaches through its LOs (weighted by A→LO × LO→PO weights), plus noise `N(0, 8)`. So a student who is strong at PO 2 does well in problem-solving-heavy assessments. That's what makes profiles differ "in believable ways" (Appendix B) instead of being flat noise.
- **5% missing, 2% excused.** Missing grades get no row. Excused grades get a row with `is_excused`. The coverage bars then have something to show.
- **Marks are rounded to halves**, the way instructors write them, and scaled to the assessment's max score (a quiz out of 20 gets 17.5, not 87.5).

```python
# apps/core/seed/builder.py
"""Builds the demo department (spec Appendix B). Deterministic: same seed, same data."""
from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from decimal import Decimal

from django.contrib.auth.hashers import make_password

from apps.accounts.models import ProgramMembership, User
from apps.catalog.models import Course, CourseOffering, Enrollment, Program, Term
from apps.catalog.selectors import active_po_set
from apps.core.models import AuditEvent
from apps.grading.models import Grade
from apps.ingestion.models import IngestionJob
from apps.outcomes.models import (
    Assessment,
    AssessmentLOWeight,
    LearningOutcome,
    LOPOWeight,
    Source,
)

from . import data

SEED = 311
DOMAIN = "polaris.test"
MISSING_RATE = 0.05
EXCUSED_RATE = 0.02
FALL_2026_PUBLISHED_AT = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)

TRANSLIT = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def slug(name: str) -> str:
    return name.translate(TRANSLIT).lower().replace(" ", "")


def half(value: float) -> Decimal:
    """Round to the nearest 0.5, the way instructors write marks."""
    return Decimal(round(value * 2)) / Decimal(2)


@dataclass
class Persona:
    role: str
    name: str
    email: str
    password: str


@dataclass
class SeedSummary:
    personas: list[Persona] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


class DemoBuilder:
    def __init__(self, *, students_per_cohort: int = 40, random_passwords: bool = False):
        self.n = students_per_cohort
        self.random_passwords = random_passwords
        self.rng = random.Random(SEED)
        self.summary = SeedSummary()
        self.abilities: dict[int, dict[int, float]] = {}     # user id -> PO number -> ability
        self.base: dict[int, float] = {}                     # user id -> μ
        self.cohort_students: dict[str, list[User]] = {}

    # ---------- housekeeping ----------

    @staticmethod
    def already_seeded() -> bool:
        return Term.objects.filter(code="2026F").exists()

    @staticmethod
    def wipe() -> None:
        """Delete all teaching data and every demo account. Keeps programs, PO sets and
        superusers. Order matters because of PROTECT foreign keys."""
        AuditEvent.objects.all().delete()
        IngestionJob.objects.all().delete()           # created_by is PROTECT
        CourseOffering.objects.all().delete()         # cascades LOs, assessments, weights, enrollments, grades
        Course.objects.all().delete()
        Term.objects.all().delete()
        User.objects.filter(email__endswith=DOMAIN, is_superuser=False).delete()

    def _password(self, fixed: str) -> str:
        return secrets.token_urlsafe(9) if self.random_passwords else fixed

    # ---------- build ----------

    def build(self) -> SeedSummary:
        self.program = Program.objects.get(code="CSE")
        self.pos = {po.number: po for po in active_po_set(self.program).outcomes.all()}
        if len(self.pos) != 11:
            raise RuntimeError("Expected the 11 official POs from the S1-05 data migration.")

        self.terms = {
            code: Term.objects.create(code=code, name=name, starts_on=start, ends_on=end, status=status)
            for code, name, start, end, status in data.TERMS
        }
        self._staff()
        self._students()
        self.courses = {
            code: Course.objects.create(program=self.program, code=code, title=spec.title,
                                        credits=Decimal(spec.credits), ects=Decimal(spec.ects))
            for code, spec in data.COURSES.items()
        }
        for spec in data.OFFERINGS:
            self._offering(spec)

        self.summary.counts = {
            "terms": Term.objects.count(),
            "courses": Course.objects.count(),
            "offerings": CourseOffering.objects.count(),
            "students": User.objects.filter(memberships__role="student").distinct().count(),
            "enrollments": Enrollment.objects.count(),
            "grades": Grade.objects.count(),
        }
        return self.summary

    def _staff(self) -> None:
        password = self._password("teach-demo-311")
        head_password = self._password("head-demo-311")
        self.staff: dict[str, User] = {}
        for key, (first, last, local, roles) in data.PEOPLE.items():
            pw = head_password if key == "head" else password
            user = User.objects.create_user(email=f"{local}@{DOMAIN}", password=pw,
                                            first_name=first, last_name=last)
            for role in roles:
                ProgramMembership.objects.create(user=user, program=self.program, role=role)
            self.staff[key] = user
            self.summary.personas.append(Persona(
                role="Head + instructor" if key == "head" else "Instructor",
                name=f"{first} {last}", email=user.email, password=pw,
            ))

    def _students(self) -> None:
        student_password = self._password("student-demo-311")
        hashed = make_password(student_password)
        users = []
        for cohort in data.COHORTS:
            for i in range(1, self.n + 1):
                first = self.rng.choice(data.FIRST_NAMES)
                last = self.rng.choice(data.LAST_NAMES)
                number = f"{cohort}-{i:04d}"
                users.append(User(
                    email=f"{slug(first)}.{slug(last)}.{cohort % 100}{i:03d}@students.{DOMAIN}",
                    first_name=first, last_name=last, student_number=number, password=hashed,
                ))
        users = User.objects.bulk_create(users)          # PostgreSQL returns primary keys

        memberships = []
        for user in users:
            cohort = int(user.student_number[:4])
            memberships.append(ProgramMembership(user=user, program=self.program,
                                                 role=ProgramMembership.Role.STUDENT, cohort_year=cohort))
            self.cohort_students.setdefault(str(cohort), []).append(user)
            mu = self.rng.gauss(70, 9)
            self.base[user.pk] = mu
            self.abilities[user.pk] = {n: min(99.0, max(30.0, self.rng.gauss(mu, 7))) for n in range(1, 12)}
        ProgramMembership.objects.bulk_create(memberships)

        weakest = sorted(self.cohort_students["2025"], key=lambda u: self.base[u.pk])[:data.RETAKERS]
        self.cohort_students["retake"] = sorted(weakest, key=lambda u: u.student_number)

        self.elif_user = User.objects.create_user(
            email=data.ELIF["email"], password=student_password,
            first_name=data.ELIF["first_name"], last_name=data.ELIF["last_name"],
            student_number=data.ELIF["student_number"],
        )
        ProgramMembership.objects.create(user=self.elif_user, program=self.program,
                                         role=ProgramMembership.Role.STUDENT,
                                         cohort_year=data.ELIF["cohort_year"])
        self.summary.personas.append(Persona("Student (slide example)", "Elif Yıldız",
                                             self.elif_user.email, student_password))
        self.summary.personas.append(Persona("Any other student", f"{len(users)} students",
                                             f"…@students.{DOMAIN} (see admin)", student_password))

    def _offering(self, spec: data.OfferingSpec) -> None:
        course_spec = data.COURSES[spec.course]
        term = self.terms[spec.term]
        teacher = self.staff[spec.teacher]
        offering = CourseOffering.objects.create(course=self.courses[spec.course], term=term)
        offering.instructors.set([teacher])

        los = [
            LearningOutcome.objects.create(offering=offering, number=i, description=lo.text)
            for i, lo in enumerate(course_spec.los, start=1)
        ]
        if term.status == Term.Status.CLOSED:
            published_at = datetime.combine(term.ends_on, time(12, 0), tzinfo=UTC)
        else:
            published_at = FALL_2026_PUBLISHED_AT

        assessments = []
        for position, a in enumerate(course_spec.assessments):
            is_published = spec.published == "all" or (
                isinstance(spec.published, tuple) and a.name in spec.published)
            assessments.append((a, Assessment.objects.create(
                offering=offering, name=a.name, kind=a.kind, max_score=Decimal(a.max_score),
                course_weight=Decimal(a.course_weight), position=position,
                published_at=published_at if is_published else None,
                published_by=teacher if is_published else None,
            )))

        if spec.mapped:
            AssessmentLOWeight.objects.bulk_create([
                AssessmentLOWeight(assessment=obj, learning_outcome=los[lo_no - 1], weight=Decimal(w))
                for a, obj in assessments for lo_no, w in a.lo.items()
            ])
            LOPOWeight.objects.bulk_create([
                LOPOWeight(learning_outcome=los[i], program_outcome=self.pos[po_no], weight=w,
                           source=Source.MANUAL)
                for i, lo in enumerate(course_spec.los) for po_no, w in lo.po.items()
            ])

        students = sorted(
            (u for cohort in spec.cohorts for u in self.cohort_students[cohort]),
            key=lambda u: u.student_number,
        )
        enrollments = Enrollment.objects.bulk_create(
            [Enrollment(offering=offering, student=u) for u in students])

        grades = []
        for enrollment, student in zip(enrollments, students, strict=True):
            for a, obj in assessments:
                if obj.published_at is None:
                    continue                          # not held yet (open term) or not published
                grade = self._grade(student, a, course_spec, obj, enrollment, teacher)
                if grade is not None:
                    grades.append(grade)

        if spec.elif_here:
            elif_enrollment = Enrollment.objects.create(offering=offering, student=self.elif_user)
            for a, obj in assessments:
                if a.name in data.ELIF["grades"]:
                    value = Decimal(data.ELIF["grades"][a.name])
                    grades.append(Grade(assessment=obj, enrollment=elif_enrollment, score=value,
                                        published_score=value, published_at=obj.published_at,
                                        updated_by=teacher))
        Grade.objects.bulk_create(grades)

        if spec.unpublished_change:
            first_published = next(obj for _a, obj in assessments if obj.published_at is not None)
            grade = (Grade.objects.filter(assessment=first_published, score__isnull=False)
                     .order_by("enrollment__student__student_number").first())
            grade.score = min(first_published.max_score, grade.score + Decimal(5))
            if grade.score == grade.published_score:          # was already at max: go down instead
                grade.score -= Decimal(5)
            grade.save(update_fields=["score"])

    def _grade(self, student, a: data.AssessmentSpec, course: data.CourseSpec, obj, enrollment, teacher):
        draw = self.rng.random()
        noise = self.rng.gauss(0, 8)
        if draw < MISSING_RATE:
            return None
        if draw < MISSING_RATE + EXCUSED_RATE:
            return Grade(assessment=obj, enrollment=enrollment, is_excused=True,
                         published_is_excused=True, published_at=obj.published_at, updated_by=teacher)
        num = den = 0.0
        abilities = self.abilities[student.pk]
        for lo_no, w in a.lo.items():
            for po_no, pw in course.los[lo_no - 1].po.items():
                num += abilities[po_no] * w * pw
                den += w * pw
        percent = min(100.0, max(0.0, num / den + noise))
        score = min(Decimal(a.max_score), half(percent / 100 * a.max_score))
        return Grade(assessment=obj, enrollment=enrollment, score=score, published_score=score,
                     published_at=obj.published_at, updated_by=teacher)
```

Two details worth pointing out in review:

- `_grade` draws **both** random numbers before deciding whether the grade is missing. If it drew the noise only for present grades, one extra missing grade would shift every later number, and a tiny change would make the whole dataset different.
- Floats are fine *here*: this is fake data generation, not scoring. The values become `Decimal` (`half()`) before they touch the database. The no-float rule (§0.4) is about computing scores.

**3. The command.** It's thin: guard, wipe-or-refuse, build, print. Everything runs in one transaction, so a crash halfway leaves the database as it was.

```python
# apps/core/management/commands/seed_demo.py
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.seed.builder import DemoBuilder


class Command(BaseCommand):
    help = "Build the demo department described in spec Appendix B."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Delete ALL terms, courses, offerings, grades and demo accounts first.")
        parser.add_argument("--small", action="store_true",
                            help="10 students per cohort instead of 40 (used by the tests).")
        parser.add_argument("--allow-production", action="store_true",
                            help="Allow running with DEBUG=False (staging). Passwords become random.")

    def handle(self, *args, reset=False, small=False, allow_production=False, **options):
        if not settings.DEBUG and not allow_production:
            raise CommandError("DEBUG is False. Seeding writes demo accounts; pass --allow-production "
                               "if this really is a demo environment.")
        builder = DemoBuilder(students_per_cohort=10 if small else 40,
                              random_passwords=not settings.DEBUG)
        with transaction.atomic():
            if reset:
                builder.wipe()
            elif builder.already_seeded():
                raise CommandError("Demo data already exists. Use --reset to rebuild it.")
            summary = builder.build()

        self.stdout.write(self.style.SUCCESS("Demo department ready."))
        for key, value in summary.counts.items():
            self.stdout.write(f"  {key:<12} {value}")
        self.stdout.write("")
        self.stdout.write(f"  {'Role':<24} {'Name':<16} {'Email':<40} Password")
        for p in summary.personas:
            self.stdout.write(f"  {p.role:<24} {p.name:<16} {p.email:<40} {p.password}")
        if not settings.DEBUG:
            self.stdout.write(self.style.WARNING("These passwords are shown once. Store them now."))
```

**4. Appendix B.** In the same PR, change the "People" row of Appendix B from "realistic Turkish names from Faker's `tr_TR` locale" to "realistic Turkish names from built-in lists in `apps/core/seed/data.py` (no Faker: it's a dev dependency and isn't in the production image)". Add a change-log line in Appendix C.

### Tests

`--small` keeps the run under a few seconds. pytest-django runs tests with `DEBUG=False`, so every test that seeds sets `settings.DEBUG = True` first, the same as on a laptop.

```python
# apps/core/tests/test_seed_demo.py
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.db.models import F

from apps.accounts.models import User
from apps.catalog.models import Course, CourseOffering, Enrollment, Program, Term
from apps.catalog.selectors import active_po_set
from apps.grading.models import Grade
from apps.outcomes.models import AssessmentLOWeight, LearningOutcome, LOPOWeight
from apps.scoring.engine import compute_student_profile, display
from apps.scoring.loaders import load_student_inputs

pytestmark = pytest.mark.django_db


def seed(*flags):
    out = StringIO()
    call_command("seed_demo", "--small", *flags, stdout=out)
    return out.getvalue()


@pytest.fixture
def seeded(settings):
    settings.DEBUG = True
    return seed()


def test_elif_reproduces_the_slide(seeded):
    elif_user = User.objects.get(email="elif.yildiz@polaris.test")
    profile = compute_student_profile(load_student_inputs(elif_user))
    pos = {po.number: po for po in active_po_set(Program.objects.get(code="CSE")).outcomes.all()}
    assert display(profile.po_scores[pos[1].id].score) == "85.0"
    assert display(profile.po_scores[pos[2].id].score) == "82.9"


def test_shape_of_the_department(seeded):
    assert Term.objects.count() == 3
    assert Course.objects.count() == 12
    assert CourseOffering.objects.count() == 15
    students = User.objects.filter(memberships__role="student").distinct()
    assert students.count() == 31                      # 3 cohorts × 10 + Elif
    assert "Elif Yıldız" in seeded and "student-demo-311" in seeded


def test_deliberate_flaws_are_present(seeded):
    active = active_po_set(Program.objects.get(code="CSE"))
    # PO 11 linked by no course
    assert not LOPOWeight.objects.filter(program_outcome__po_set=active,
                                         program_outcome__number=11).exists()
    # PO 9 covered by exactly one course
    po9_courses = set(LOPOWeight.objects.filter(program_outcome__number=9)
                      .values_list("learning_outcome__offering__course__code", flat=True))
    assert po9_courses == {"CSE 341"}
    # one Fall 2026 offering with LOs and assessments but no mapping
    unmapped = CourseOffering.objects.get(course__code="CSE 221", term__code="2026F")
    assert LearningOutcome.objects.filter(offering=unmapped).exists()
    assert unmapped.assessments.exists()
    assert not AssessmentLOWeight.objects.filter(assessment__offering=unmapped).exists()
    assert not LOPOWeight.objects.filter(learning_outcome__offering=unmapped).exists()
    # exactly one grade with an unpublished change
    changed = (Grade.objects.filter(assessment__published_at__isnull=False, score__isnull=False)
               .exclude(score=F("published_score")))
    assert changed.count() == 1


def test_retakers_are_in_both_cse101_offerings(seeded):
    old = CourseOffering.objects.get(course__code="CSE 101", term__code="2025F")
    retake = CourseOffering.objects.get(course__code="CSE 101", term__code="2026F")
    retakers = set(Enrollment.objects.filter(offering=retake).values_list("student_id", flat=True))
    assert len(retakers) == 3
    assert retakers <= set(Enrollment.objects.filter(offering=old).values_list("student_id", flat=True))


def test_grades_are_valid(seeded):
    assert not Grade.objects.filter(score__gt=F("assessment__max_score")).exists()
    assert not Grade.objects.filter(score__lt=0).exists()
    assert not Grade.objects.exclude(assessment__offering=F("enrollment__offering")).exists()
    total = Grade.objects.count()
    excused = Grade.objects.filter(is_excused=True).count()
    assert 0 < excused < total * 0.06                   # about 2%


def _fingerprint():
    return list(Grade.objects.order_by(
        "enrollment__student__student_number", "assessment__offering__term__code",
        "assessment__offering__course__code", "assessment__position",
    ).values_list("enrollment__student__student_number", "assessment__offering__course__code",
                  "assessment__name", "score", "is_excused"))


def test_same_seed_same_data(seeded):
    first = _fingerprint()
    seed("--reset")
    assert _fingerprint() == first


def test_second_run_without_reset_is_refused(seeded):
    with pytest.raises(CommandError, match="already exists"):
        seed()


def test_refuses_when_debug_is_false(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG is False"):
        seed()


def test_production_mode_uses_random_passwords(settings):
    settings.DEBUG = False
    out = seed("--allow-production")
    assert "student-demo-311" not in out
    assert "shown once" in out
```

### Check it works

```bash
uv run python manage.py seed_demo --reset
```

Expected output (counts for the full seed; your grade count may differ by a few because of missing and excused draws, but it's identical on every run):

```
Demo department ready.
  terms        3
  courses      12
  offerings    15
  students     121
  enrollments  564
  grades       ~1,400
  Role                     Name             Email                                    Password
  Head + instructor        Deniz Kara       deniz.kara@polaris.test                  head-demo-311
  Instructor               Can Aydın        can.aydin@polaris.test                   teach-demo-311
  …
  Student (slide example)  Elif Yıldız      elif.yildiz@polaris.test                 student-demo-311
```

Then:

1. Log in as Elif: PO 1 85.0, PO 2 82.9.
2. Log in as Deniz Kara: the overview (S3-04) shows PO 11 with no evidence, and the Fall 2026 course list shows CSE 221 with ✗ Mapping.
3. Open CSE 321 (Fall 2026) as Can Aydın → Grades: the Midterm column shows "1 unpublished change".
4. Run the command again with `--reset` and repeat step 1: same numbers.
5. Time it: `time uv run python manage.py seed_demo --reset` should take under 10 seconds.

### Done when

| Requirement (Appendix B) | Proved by |
|---|---|
| 3 terms, 12 courses, 120 students in 3 cohorts | `test_shape_of_the_department` (small), the printed counts (full) |
| Elif shows 85.0 and 82.9 | `test_elif_reproduces_the_slide` |
| Deliberate flaws present | `test_deliberate_flaws_are_present`, `test_retakers_are_in_both_cse101_offerings` |
| Fixed seed: identical every run | `test_same_seed_same_data` |
| Grades realistic and valid | `test_grades_are_valid` |
| Refuses with DEBUG=False unless allowed; random passwords then | `test_refuses_when_debug_is_false`, `test_production_mode_uses_random_passwords` |

### Commits and PR

```
Move demo department definition into seed data module (#S3-07)
Rewrite seed_demo builder with ability-based grades (#S3-07)
Seed Fall 2026 flaws: unmapped course, unpublished change, retakes (#S3-07)
Test seed determinism and Elif's slide numbers (#S3-07)
Update Appendix B: names from built-in lists, not Faker (#S3-07)
```

PR title: **seed_demo v2: full demo department with deliberate flaws (S3-07)**

---
## S3-08 · Spike: what gradebook files really look like

**Points:** 3 · **Owner:** Person B · **Branch:** `spike/S3-08-gradebook-files` · **Depends on:** nothing in code. Read T1.1 in Part 6 first.

### Goal

T1.1 (bulk grade upload, S4-03, 5 points) promises: "my gradebook file is understood whatever Excel export I use". Before we commit to that, we spend a fixed time finding out what such files actually contain, and we leave behind:

1. a short written answer (`docs/spikes/S3-08-gradebook-formats.md`),
2. a set of realistic sample files in `seed/grades/`, generated by a script so they're reproducible. These become the golden-test inputs for T1.1 AC1.
3. a throwaway probe script showing that our planned approach handles every sample,
4. a re-estimate of S4-03.

A spike produces knowledge, not product code. That is why its output is a document and test data, and why the probe lives in `spikes/`, which nothing in `apps/` may import. In Scrum terms it's a time-boxed research item. Its points count toward velocity, because it is real work that reduces the risk of S4-03.

### Timebox

**One and a half days**, about 8 hours of focused work. Stop when the time is up, even if a question is still open, and write down what's open. The re-estimate absorbs the leftover uncertainty. Running over the timebox is the most common way spikes go wrong.

| Block | Time | Output |
|---|---|---|
| Collect real files | 1.5 h | Ask two instructors (and the TA) for an anonymised gradebook export: Excel, Google Sheets CSV, the LMS export. Note the program and locale that produced each one |
| Write the sample generator | 2 h | `seed/grades/make_samples.py` + 5 files |
| Write the probe | 2.5 h | `spikes/grade_files/probe.py` reads every sample |
| Write up + re-estimate | 1.5 h | `docs/spikes/S3-08-gradebook-formats.md`, S4-03 points updated on the board |
| Buffer | 0.5 h | |

**Real files contain real student data.** Never commit them. Keep them outside the repo (`~/polaris-private/`), and copy only their *shape* (headers, separators, quirks) into the generated samples.

### Questions the spike must answer

| # | Question | Why it matters for S4-03 |
|---|---|---|
| Q1 | Which encodings and separators appear? (UTF-8, UTF-8 with BOM, Windows-1254; `,` `;` tab) | Decoding order and separator sniffing |
| Q2 | Is the header always the first row? (Title rows, merged cells, blank rows above it?) | Header detection rule |
| Q3 | How do student numbers arrive? (text `2024-0001`, number `20240001`, float `20240001.0`, leading zeros lost) | Matching students reliably |
| Q4 | How do marks arrive? (`85,5`, `85.5`, `85`, `%85`, `EX`, `M`, `G` for *girmedi*, blank, `-`) | Value parser rules and the excused vocabulary |
| Q5 | What do the column headers look like? (`Vize`, `Midterm I`, `Quiz: Midterm I (Real)`, `Ödev 1`, `Final (100)`) | Column-matching aliases and fuzzy threshold |
| Q6 | What extra columns are there? (`Total`, `Letter grade`, `Email`, `Last downloaded…`) | Which columns to ignore by default |
| Q7 | Do `.xlsx` files contain formulas? Does openpyxl return their values? | Whether we read with `data_only=True` and what happens when values are missing |
| Q8 | How long does a 200-row file take to read? | T1.1 AC4 (under 2 seconds) |

### Steps

**1. The sample generator.** Generated, not hand-made, so anyone can recreate the files and S4-03's golden tests can be regenerated if we change a sample on purpose. Student numbers match the full `seed_demo` (cohort 2024, `2024-0001` …) plus Elif, so you can upload the samples into CSE 311 (Fall 2026) in a demo.

Each file stresses specific questions:

| File | Simulates | Stresses |
|---|---|---|
| `clean.csv` | What we wish everyone sent | Baseline: UTF-8, comma, exact assessment names |
| `turkish_excel.csv` | Excel in Turkish locale, "CSV (semicolon delimited)" | Q1 cp1254 + `;`, Q4 `85,5`, `G`, `M`, Q5 `Vize`/`Proje`, Turkish header `Öğrenci No` |
| `messy.xlsx` | An instructor's hand-made sheet | Q2 title rows, Q3 numbers stored as numbers, Q4 `EX`, `-`, `105`, `-3`, `abc`, Q6 `Total` formula column, duplicate and unknown students |
| `lms_export.xlsx` | A Moodle-style gradebook export | Q5 `Quiz: Midterm I (Real)`, Q6 email and "Last downloaded" columns, Q3 "ID number" column |
| `large.csv` | A big class | Q8: 200 rows × 6 assessments |

```python
# seed/grades/make_samples.py
"""Generate the sample gradebook files for the S3-08 spike and the T1.1 golden tests.
Run from the repo root:  uv run python seed/grades/make_samples.py
Deterministic: the same files every time."""
from __future__ import annotations

import csv
import random
from pathlib import Path

from openpyxl import Workbook

HERE = Path(__file__).parent
rng = random.Random(3118)

STUDENTS = [f"2024-{i:04d}" for i in range(1, 21)] + ["2024-0041"]   # 20 seeded + Elif
NAMES = ["Ayşe Kaya", "Mert Demir", "Zeynep Çelik", "Can Şahin", "Elif Öztürk", "Burak Yıldız",
         "Selin Arslan", "Emre Koç", "Damla Kurt", "Oğuz Polat", "İrem Aslan", "Kerem Güneş",
         "Ceren Tekin", "Barış Bulut", "Defne Aktaş", "Umut Ateş", "Ece Uçar", "Kaan Karaca",
         "Melis Doğan", "Arda Kılıç", "Elif Yıldız"]


def mark() -> float:
    return round(rng.uniform(35, 100) * 2) / 2


def write_csv(name: str, rows: list[list], *, encoding="utf-8", delimiter=",") -> None:
    with open(HERE / name, "w", newline="", encoding=encoding) as f:
        csv.writer(f, delimiter=delimiter).writerows(rows)


def clean_csv() -> None:
    rows = [["Student No", "Name", "Midterm I", "Project"]]
    for number, name in zip(STUDENTS, NAMES, strict=True):
        rows.append([number, name, mark(), mark()])
    rows[-1][2:] = [90, 80]                                  # Elif, as on the slide
    write_csv("clean.csv", rows)


def turkish_excel_csv() -> None:
    rows = [["Öğrenci No", "Adı Soyadı", "Vize", "Proje"]]
    for number, name in zip(STUDENTS, NAMES, strict=True):
        rows.append([number, name, str(mark()).replace(".", ","), str(mark()).replace(".", ",")])
    rows[3][2] = "G"          # girmedi: did not sit the exam -> missing
    rows[5][3] = "M"          # muaf: exempt -> excused
    rows[7][2] = ""           # blank cell
    write_csv("turkish_excel.csv", rows, encoding="cp1254", delimiter=";")


def messy_xlsx() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Notlar"
    ws.append(["CSE 311 Software Engineering — Fall 2026 grades"])
    ws.append(["Instructor: Prof. Deniz Kara"])
    ws.append([])
    ws.append(["No", "Student", "Midterm-1 ", "PROJECT", "Total"])
    for r, (number, name) in enumerate(zip(STUDENTS, NAMES, strict=True), start=5):
        as_number = int(number.replace("-", "")) if r % 4 == 0 else number   # Q3: some numbers are numbers
        ws.append([as_number, name, mark(), mark(), f"=0.25*C{r}+0.4*D{r}"])
    ws["C6"] = "EX"            # excused
    ws["D7"] = "-"             # dash: empty
    ws["C8"] = 105             # above max
    ws["D9"] = -3              # negative
    ws["C10"] = "abc"          # not a number
    last = ws.max_row
    ws.append([STUDENTS[0], NAMES[0], mark(), mark(), f"=0.25*C{last + 1}+0.4*D{last + 1}"])  # duplicate
    ws.append(["2099-0001", "Unknown Student", mark(), mark(), ""])                          # not enrolled
    wb.save(HERE / "messy.xlsx")


def lms_export_xlsx() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Grades"
    ws.append(["First name", "Surname", "ID number", "Email address", "Quiz: Midterm I (Real)",
               "Assignment: Project (Real)", "Course total (Real)", "Last downloaded from this course"])
    for number, name in zip(STUDENTS, NAMES, strict=True):
        first, last = name.split(" ", 1)
        ws.append([first, last, number, f"{number}@students.polaris.test", mark(), mark(), "",
                   "Friday, 6 November 2026, 12:00 PM"])
    wb.save(HERE / "lms_export.xlsx")


def large_csv() -> None:
    header = ["Student No", "Name", "Quiz 1", "Quiz 2", "Midterm I", "Project", "Homework", "Final exam"]
    rows = [header]
    for i in range(1, 201):
        rows.append([f"2024-{i:04d}", f"Student {i}"] + [mark() for _ in range(6)])
    write_csv("large.csv", rows)


if __name__ == "__main__":
    for make in (clean_csv, turkish_excel_csv, messy_xlsx, lms_export_xlsx, large_csv):
        make()
        print(f"wrote {make.__name__}")
```

The `Total` column in `messy.xlsx` contains formulas *written by openpyxl*. Such files have **no cached formula values** until Excel opens and saves them. So `load_workbook(data_only=True)` returns `None` for those cells. That's exactly the Q7 trap, and the sample captures it on purpose. Note in the write-up that a file saved by Excel behaves differently, and confirm it with one of the real files.

**2. The probe.** A prototype of the reading and matching logic S4-03 will need. It's deliberately one file with no Django: the question is only "does this approach handle every sample?". It prints a report per file. Keep it ugly. It gets deleted after S4-03.

```python
# spikes/grade_files/probe.py
"""S3-08 throwaway probe. NOT product code. Delete after S4-03 is merged.
Run:  uv run python spikes/grade_files/probe.py seed/grades/*.csv seed/grades/*.xlsx"""
from __future__ import annotations

import csv
import difflib
import io
import re
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

ASSESSMENTS = ["Midterm I", "Project", "Final exam", "Quiz 1", "Quiz 2", "Homework"]
STUDENT_HEADER = re.compile(r"(student|öğrenci|ogrenci|id number|^no\.?$|number)", re.I)
STUDENT_VALUE = re.compile(r"^\d{4}-?\d{4}$")
EXCUSED = {"ex", "excused", "m", "muaf"}
MISSING = {"", "-", "g", "girmedi", "na", "n/a"}
ALIASES = {"vize": "midterm i", "midterm-1": "midterm i", "midterm 1": "midterm i",
           "proje": "project", "final": "final exam", "ödev": "homework", "odev": "homework"}


def read_table(path: Path) -> list[list[str]]:
    if path.suffix.lower() == ".xlsx":
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        return [["" if v is None else str(v) for v in row] for row in ws.iter_rows(values_only=True)]
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1254"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("unknown encoding")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


def find_header(rows: list[list[str]]) -> int:
    """First row with >= 2 non-empty cells where one looks like a student-number header."""
    for i, row in enumerate(rows[:15]):
        cells = [c.strip() for c in row if c and c.strip()]
        if len(cells) >= 2 and any(STUDENT_HEADER.search(c) for c in cells):
            return i
    return 0


def normalise_number(value: str) -> str:
    value = value.strip()
    if value.endswith(".0"):
        value = value[:-2]                                   # 20240001.0 -> 20240001
    if re.fullmatch(r"\d{8}", value):
        value = f"{value[:4]}-{value[4:]}"                   # 20240001 -> 2024-0001
    return value


def parse_mark(value: str):
    v = value.strip().lower().lstrip("%")
    if v in MISSING:
        return ("missing", None)
    if v in EXCUSED:
        return ("excused", None)
    try:
        number = Decimal(v.replace(",", "."))
    except InvalidOperation:
        return ("invalid", value)
    return ("value", number)


def guess_column(header: str) -> str | None:
    h = re.sub(r"\s*\((real|100)\)\s*$", "", header.strip().lower())
    h = re.sub(r"^(quiz|assignment):\s*", "", h)
    h = ALIASES.get(h, h)
    names = {a.lower(): a for a in ASSESSMENTS}
    if h in names:
        return names[h]
    match = difflib.get_close_matches(h, names, n=1, cutoff=0.75)
    return names[match[0]] if match else None


def probe(path: Path) -> None:
    start = time.perf_counter()
    rows = read_table(path)
    h = find_header(rows)
    header = rows[h]
    student_col = next((i for i, c in enumerate(header) if STUDENT_HEADER.search(c or "")), None)
    mapping = {i: guess_column(c) for i, c in enumerate(header) if i != student_col and c}
    counts = {"value": 0, "missing": 0, "excused": 0, "invalid": 0}
    numbers = []
    for row in rows[h + 1:]:
        if not any(c.strip() for c in row):
            continue
        numbers.append(normalise_number(row[student_col]) if student_col is not None else "?")
        for i, target in mapping.items():
            if target and i < len(row):
                counts[parse_mark(row[i])[0]] += 1
    elapsed = (time.perf_counter() - start) * 1000
    dupes = {n for n in numbers if numbers.count(n) > 1}
    bad_numbers = [n for n in numbers if not STUDENT_VALUE.match(n)]
    print(f"\n== {path.name}  ({elapsed:.0f} ms)")
    print(f"   header row: {h + 1}  student column: {header[student_col] if student_col is not None else 'NOT FOUND'}")
    print(f"   columns: { {header[i]: t for i, t in mapping.items()} }")
    print(f"   marks: {counts}   rows: {len(numbers)}   duplicates: {sorted(dupes)}")
    print(f"   odd student numbers: {bad_numbers}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        probe(Path(arg))
```

It's a probe: quick, not polished, and nothing imports it. S4-03 rewrites the parts that worked properly in `apps/grading/upload.py`, with tests.

**3. Run it and fill the results table.** Run the generator, then the probe on the five samples and on each real file (privately). For each file, record whether the planned approach got it right without help:

```bash
uv run python seed/grades/make_samples.py
uv run python spikes/grade_files/probe.py seed/grades/*.csv seed/grades/*.xlsx
```

**4. The write-up.** Use this template. Fill every cell. "Not tested" is a valid answer, but a blank cell is not.

```markdown
<!-- docs/spikes/S3-08-gradebook-formats.md -->
# Spike S3-08: gradebook file formats

**Question:** Can POlaris read the grade files instructors actually have, well enough to make
T1.1's dry run trustworthy?
**Timebox:** 1.5 days · **Spent:** … h · **Author:** … · **Date:** …

## Files examined
| File | Source (program, locale) | Real or generated | Rows | Notes |
|---|---|---|---|---|

## Results
| Check | clean.csv | turkish_excel.csv | messy.xlsx | lms_export.xlsx | large.csv | real file 1 | real file 2 |
|---|---|---|---|---|---|---|---|
| Decoded correctly (Q1) | | | | | | | |
| Separator sniffed (Q1) | | | | | | | |
| Header row found (Q2) | | | | | | | |
| Student column found (Q3) | | | | | | | |
| All student numbers normalised (Q3) | | | | | | | |
| Marks parsed: `85,5`, EX/M/G, blanks (Q4) | | | | | | | |
| Columns auto-matched (Q5) | | | | | | | |
| Extra columns ignored (Q6) | | | | | | | |
| Formula cells (Q7) | | | | | | | |
| Time, ms (Q8) | | | | | | | |

## Decisions for S4-03
- Encodings, in order: …
- Header detection rule: …
- Student-number normalisation: …
- Excused vocabulary: … · missing vocabulary: …
- Column matching: aliases …, fuzzy cutoff …
- Formula cells: … (reject with a message / read cached values / ask to re-save in Excel)

## Still open
- …

## Re-estimate
S4-03 was 5 points. After this spike: … points, because …
```

**5. Re-estimate S4-03 at the next refinement.** Bring the write-up to the Sprint 4 planning meeting and re-run planning poker for S4-03 with everyone. Record the old and new estimates in `docs/process/velocity.md` (§9.5). The change itself is evidence for the CSE 311 report ("we used a spike to reduce estimation uncertainty").

### Tests

A spike ships no product tests. Two cheap checks keep its outputs honest:

```python
# seed/grades/test_samples.py  (collected by pytest because python_files = test_*.py)
from pathlib import Path

import pytest

HERE = Path(__file__).parent
FILES = ["clean.csv", "turkish_excel.csv", "messy.xlsx", "lms_export.xlsx", "large.csv"]


@pytest.mark.parametrize("name", FILES)
def test_sample_file_exists(name):
    assert (HERE / name).stat().st_size > 0


def test_turkish_sample_is_cp1254_with_semicolons():
    raw = (HERE / "turkish_excel.csv").read_bytes()
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")
    assert raw.decode("cp1254").splitlines()[0] == "Öğrenci No;Adı Soyadı;Vize;Proje"
```

Add `"seed"` to `testpaths` in `pyproject.toml` if you've restricted it to `apps`. Otherwise pytest collects it automatically. Coverage is measured on `apps/` only, so these don't affect the 85% gate.

### Check it works

1. `uv run python seed/grades/make_samples.py` prints five "wrote …" lines, and `git status` shows the five files.
2. Run it again: `git status` shows **no** changes, so the files are deterministic. (`.xlsx` files contain a creation timestamp. If they show as changed, set `wb.properties.created` to a fixed datetime in the generator and note it in the write-up.)
3. The probe prints a block per file. `messy.xlsx` reports header row 4, duplicates `['2024-0001']`, and `invalid` ≥ 1.
4. The write-up is merged and S4-03 has its new estimate on the board.

### Done when

- [ ] `docs/spikes/S3-08-gradebook-formats.md` merged with every cell filled
- [ ] `seed/grades/make_samples.py` and the five generated files committed. No real student data anywhere in the repo
- [ ] `spikes/grade_files/probe.py` committed with a "delete after S4-03" note
- [ ] S4-03 re-estimated in planning poker; old → new points in `velocity.md`
- [ ] Timebox respected: time spent recorded in the write-up

### Commits and PR

```
Add generator for sample gradebook files (#S3-08)
Add throwaway probe for gradebook parsing (#S3-08)
Write up gradebook format spike and decisions for bulk upload (#S3-08)
```

PR title: **Spike: gradebook file formats, samples and decisions for T1.1 (S3-08)**

Merge the spike PR like any other: squash into `develop`. The `spike/` branch prefix tells reviewers to judge the write-up, not the probe's code quality.

---

## Code map additions

Names this chapter introduces that are not yet in spec §4.8. Add them to §4.8 when these stories merge.

| Module | Name / signature | Purpose |
|---|---|---|
| `reports.selectors` | `student_program(student) -> Program \| None` | The program a user studies in (newest student membership) |
| `reports.selectors` | `PORow`, `CourseRow`, `ContributionRow`, `AssessmentRow` (frozen dataclasses) | Row types for the student pages |
| `reports.selectors` | `po_contributions(student, po_id) -> dict` | Data for the "where does this number come from" drawer; 404 for POs outside the student's set |
| `reports.selectors` | `student_course_context(enrollment) -> dict` | One course from the student's side, including superseded attempts |
| `reports.selectors` | `course_results_context(offering) -> dict` | Wraps `class_lo_summary` + `setup_status` for B9 |
| `reports.views` | `department_student_po(request, user_id, po_id)` | Head's version of the drawer |
| URL | `reports:department_student_po` → `/department/students/<user_id>/po/<po_id>/` | Same, as a URL (add to §8.3 and the permission matrix) |
| `reports.forms` | `DepartmentFilterForm` | Term + include-open filter (GET) |
| `scoring.aggregates` | `mean(values) -> Decimal \| None`, `bucket_of(score) -> int` | Shared helpers |
| `scoring.aggregates` | `StudentLORow`, `LOStats` (with `histogram_heights`), `POContribution`, `ClassLOSummary`, `POSummary` (with `rate`) | Fields of the return types |
| `scoring.aggregates` | `program_po_summary(program, *, terms, include_open_terms, cohort=None)` | **Signature extended** with `cohort`; `terms` = every term to consider, the latest is the cumulative cut-off |
| `reports.views` | `_selected_terms(request, program) -> (terms, include_open, form)` | Term filter shared by the dashboard and its drill-downs (S6-05) |
| `catalog.selectors` | `default_report_term() -> Term \| None` | Latest closed term, else latest started term |
| `catalog.importers` | `parse_enrollment_csv(file, *, offering)` | **Signature extended** with `offering` (needed to classify "already enrolled") |
| `catalog.importers` | `apply_enrollment_import(user, offering, preview, *, skip_invalid=False, request=None) -> ImportResult` | **Signature extended** |
| `catalog.importers` | `ImportRow`, `EnrollmentImportPreview` (`to_json`, `from_json`, `counts`, `has_errors`, `actionable`, `signature`), `ImportResult`, `PreviewOutdated` | Preview types |
| `catalog.importers` | `create_enrollment_import_job(user, offering, uploaded_file) -> IngestionJob` | Upload step (stores file + preview) |
| `catalog.importers` | `stored_preview(job) -> EnrollmentImportPreview` | Load the preview saved on a job |
| `catalog.importers` | `confirm_enrollment_import(user, job, *, skip_invalid=False, request=None) -> ImportResult` | Re-parse, compare, apply in one transaction; raises `PreviewOutdated` |
| `accounts.services` | `set_password_link(user, request=None) -> str` | Absolute set-password URL |
| settings | `SITE_URL` (env, default `http://localhost:8000`) | Absolute links when there is no request; add to §4.6 and `.env.example` |
| `core.templatetags.polaris` | filter `get_item` | `{{ dict|get_item:key }}` |
| `core.tests.scenarios` | `one_lo_class(*, students_scores=(), term=None, program=None, po=None, lo_po_weight=3)` | One-assessment, one-LO, one-PO class for aggregate tests |
| `core.seed.data` | `LOSpec`, `AssessmentSpec`, `CourseSpec`, `OfferingSpec`, `TERMS`, `PEOPLE`, `ELIF`, `COHORTS`, `FIRST_NAMES`, `LAST_NAMES`, `COURSES`, `OFFERINGS`, `RETAKERS` | The demo department as data |
| `core.seed.builder` | `DemoBuilder(*, students_per_cohort=40, random_passwords=False)` with `wipe()`, `already_seeded()`, `build() -> SeedSummary` | Builds Appendix B |
| `static/js/polaris.js` | `Polaris.cssVar(name, fallback)`, `Polaris.poBarChart(canvasId, dataId)` | Chart helper |
| CSS tokens | `--pl-attained`, `--pl-below`, `--pl-none` | Names for the semantic colours listed in §8.2 (the chart reads them) |
| Repo | `seed/enrollments/sample_class.csv`, `static/samples/sample_class.csv`, `seed/grades/*`, `spikes/grade_files/probe.py`, `docs/spikes/` | New files and folders (add `spikes/` and `docs/spikes/` to the §4.3 layout) |
