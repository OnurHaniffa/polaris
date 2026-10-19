<!-- Sprint 2, part B: S2-04, S2-05, S2-07. The sprint header, story table and merge order are in sprint-02a.md. -->

## S2-04 · Course setup: learning outcomes, assessments and the setup checklist

**Points:** 3 · **Owner:** Person B · **Branch:** `feature/S2-04-course-setup` · **Depends on:** S1-03 (outcome models), S1-08 (factories), S1-09 (base template, `empty_state`, shared modal), S2-02 (decorators, `offering_header.html`, `offering_tabs`)

### Goal

An instructor opens their course, sees a checklist of what's still missing, and adds, edits, reorders and deletes learning outcomes (LOs) and assessments. LO numbers always stay 1, 2, 3… with no gaps. Deleting anything first shows exactly what else goes with it. This delivers **B4** (all four ACs) and the setup checklist that the course list, offering home and department overview reuse.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/outcomes/forms.py` | create | `LearningOutcomeForm`, `AssessmentForm` (using `core.forms.BootstrapFormMixin` from S2-03) |
| `apps/outcomes/services.py` | create | `create_lo`, `update_lo`, `delete_lo`, `reorder_los`, `create_assessment`, `update_assessment`, `delete_assessment` (S2-05 adds the matrix functions) |
| `apps/outcomes/selectors.py` | create | `setup_context`, `DeletionImpact`, `lo_deletion_impact`, `assessment_deletion_impact` (S2-05 and S2-07 add more) |
| `apps/catalog/selectors.py` | modify | `SetupStatus`, `setup_statuses`, `setup_status` |
| `apps/outcomes/views.py` | create | `setup`, `lo_create`, `lo_edit`, `lo_delete`, `lo_reorder`, `assessment_create`, `assessment_edit`, `assessment_delete` |
| `apps/outcomes/urls.py` | create | The setup URLs (S2-05 adds the mapping URLs) |
| `config/urls.py` | modify | `include("apps.outcomes.urls")` |
| `templates/includes/setup_checklist.html` | create | The five-item checklist card |
| `apps/outcomes/templates/outcomes/setup.html` | create | The setup page |
| `apps/outcomes/templates/outcomes/lo_form.html` | create | Add / edit an LO |
| `apps/outcomes/templates/outcomes/assessment_form.html` | create | Add / edit an assessment, including the max-score confirmation |
| `apps/outcomes/templates/outcomes/confirm_delete.html` | create | Delete confirmation, as a modal body (HTMX) or a full page |
| `apps/catalog/views.py`, `catalog/teaching.html`, `catalog/offering_home.html` | modify | Setup column on *My courses*; checklist card on the offering home |
| `apps/outcomes/tests/conftest.py` | create | The `course` fixture shared by S2-04, S2-05 and S2-07 tests |
| `apps/outcomes/tests/test_setup_services.py` | create | Service tests |
| `apps/outcomes/tests/test_setup_views.py` | create | View tests |
| `apps/outcomes/tests/test_setup_status.py` | create | Checklist selector tests (lives next to the `course` fixture) |

The permission matrix rows for every URL in this story are already in `apps/accounts/tests/routes.py` (S2-02 listed them with `story="S2-04"`). They become active the moment the URL names exist. You don't edit the matrix, but run it before opening the PR.

### Steps

**1. Forms.** Plain `forms.Form`, not `ModelForm`. A `ModelForm` has a `.save()` method, and sooner or later someone calls it from a view and skips the service: no transaction, no audit event, no closed-term check. Plain forms only clean input, and the service does the write. `BootstrapFormMixin` (S2-03, `apps/core/forms.py`) adds Bootstrap's CSS classes once, so templates can print `{{ field }}` without per-field markup.

`confirm_max_change` is the "yes, I really want to change the maximum" box. It is only shown after the service has refused a max-score change once (step 3).

```python
# apps/outcomes/forms.py
from __future__ import annotations

from decimal import Decimal

from django import forms

from apps.core.forms import BootstrapFormMixin

from .models import Assessment


class LearningOutcomeForm(BootstrapFormMixin, forms.Form):
    description = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="What a student should be able to do after the course. "
                  "Copy the wording from your syllabus if you have one.",
    )

    def clean_description(self):
        text = " ".join(self.cleaned_data["description"].split())  # collapse pasted line breaks
        if len(text) < 5:
            raise forms.ValidationError("Write at least a few words.")
        return text


class AssessmentForm(BootstrapFormMixin, forms.Form):
    name = forms.CharField(max_length=100, help_text="As students know it, e.g. “Midterm I”.")
    kind = forms.ChoiceField(choices=Assessment.Kind.choices)
    max_score = forms.DecimalField(
        max_digits=7, decimal_places=2, min_value=Decimal("0.01"), initial=Decimal("100"),
        help_text="The highest possible raw mark. Grades are converted to 0–100 using it.",
    )
    course_weight = forms.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100"),
        required=False, label="Course weight (%)",
        help_text="Share of the course grade, e.g. 25. Leave blank if you don't know.",
    )
    due_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    confirm_max_change = forms.BooleanField(
        required=False, label="Yes, change the maximum and re-check every grade",
    )

    #: Fields passed to the service. confirm_max_change is a flag, not a model field.
    MODEL_FIELDS = ("name", "kind", "max_score", "course_weight", "due_date")

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())

    def model_data(self) -> dict:
        return {name: self.cleaned_data[name] for name in self.MODEL_FIELDS}

    @classmethod
    def initial_for(cls, assessment: Assessment) -> dict:
        return {name: getattr(assessment, name) for name in cls.MODEL_FIELDS}
```

**2. LO services.** Four rules shape this code.

- **Lock the offering row first.** `select_for_update(of=("self",))` makes every setup write for one course wait for the previous one. Without it, two tabs adding an LO at the same moment both read "highest number = 3" and both try to insert LO 4. `of=("self",)` locks only the offering row, not the joined term and program rows, which other courses also need.
- **Closed terms are read-only.** `ensure_term_open` raises `ValidationError` (spec §5.3). The decorator already returns 403 for closed terms, but services are also called from the shell, seed scripts and the syllabus wizard, so the rule lives here too.
- **The audit event goes in the same transaction.** If the audit insert fails, the change rolls back with it. A change with no history is worse than no change.
- **Renumbering in two phases.** `(offering, number)` is unique. Renumbering 1,2,3 → 3,1,2 row by row would collide: setting LO "3" to 1 while LO "1" still exists breaks the constraint. So first every LO in the course gets +1000 (no collisions, because numbers are below 1000), then each gets its final number. Both phases run in one transaction, so nobody ever sees the +1000 numbers.

```python
# apps/outcomes/services.py
"""Every write to learning outcomes, assessments and the two weight matrices.

Rules (spec §4.4, §5.3): one transaction per call, closed terms refused, and an
AuditEvent written in the same transaction as the change.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Max, Q

from apps.catalog.models import CourseOffering
from apps.catalog.services import ensure_term_open
from apps.core.audit import record, snapshot

from .models import Assessment, LearningOutcome, Source

LO_FIELDS = ["number", "description", "source"]
ASSESSMENT_FIELDS = ["name", "kind", "max_score", "course_weight", "due_date", "position"]
EDITABLE_ASSESSMENT_FIELDS = frozenset({"name", "kind", "max_score", "course_weight", "due_date"})
RENUMBER_OFFSET = 1000


def _lock_offering(offering: CourseOffering) -> CourseOffering:
    """Lock this offering's row until the transaction ends (spec §5.6) and return a fresh copy."""
    return (
        CourseOffering.objects.select_for_update(of=("self",))
        .select_related("term", "course__program")
        .get(pk=offering.pk)
    )


# ---------- learning outcomes ----------

def create_lo(user, offering, *, description, source=Source.MANUAL) -> LearningOutcome:
    with transaction.atomic():
        offering = _lock_offering(offering)
        ensure_term_open(offering)
        last = offering.learning_outcomes.aggregate(m=Max("number"))["m"] or 0
        lo = LearningOutcome.objects.create(
            offering=offering, number=last + 1, description=description.strip(), source=source,
        )
        record(user, "lo.create", lo, after=snapshot(lo, LO_FIELDS), offering=offering)
        return lo


def update_lo(user, lo, *, description) -> LearningOutcome:
    with transaction.atomic():
        offering = _lock_offering(lo.offering)
        ensure_term_open(offering)
        lo = LearningOutcome.objects.get(pk=lo.pk, offering=offering)
        before = snapshot(lo, LO_FIELDS)
        lo.description = description.strip()
        lo.save(update_fields=["description"])
        record(user, "lo.update", lo, before=before, after=snapshot(lo, LO_FIELDS), offering=offering)
        return lo


def _renumber(offering, ordered_ids: list[int]) -> None:
    """Give the offering's LOs the numbers 1..n in `ordered_ids` order (two-phase, see above)."""
    by_id = {lo.id: lo for lo in LearningOutcome.objects.filter(offering=offering)}
    LearningOutcome.objects.filter(offering=offering).update(number=F("number") + RENUMBER_OFFSET)
    for position, lo_id in enumerate(ordered_ids, start=1):
        by_id[lo_id].number = position
    LearningOutcome.objects.bulk_update([by_id[i] for i in ordered_ids], ["number"])


def delete_lo(user, lo) -> None:
    """Delete an LO and both kinds of weight attached to it, then close the gap in numbering.
    The audit event stores the weights that disappeared, so the history can explain a
    changed PO score later."""
    with transaction.atomic():
        offering = _lock_offering(lo.offering)
        ensure_term_open(offering)
        lo = LearningOutcome.objects.get(pk=lo.pk, offering=offering)
        before = snapshot(lo, LO_FIELDS)
        before["assessment_weights"] = {
            str(a_id): str(w) for a_id, w in lo.assessment_weights.values_list("assessment_id", "weight")
        }
        before["po_weights"] = {
            str(po_id): w for po_id, w in lo.po_weights.values_list("program_outcome_id", "weight")
        }
        record(user, "lo.delete", lo, before=before, offering=offering)  # before delete(): needs lo.pk
        lo.delete()  # CASCADE removes AssessmentLOWeight and LOPOWeight rows
        remaining = list(
            LearningOutcome.objects.filter(offering=offering).order_by("number").values_list("id", flat=True)
        )
        _renumber(offering, remaining)


def reorder_los(user, offering, ordered_ids: list[int]) -> None:
    """`ordered_ids` must contain every LO of the offering exactly once. A different set
    means the page was stale (someone added or deleted an LO in another tab)."""
    with transaction.atomic():
        offering = _lock_offering(offering)
        ensure_term_open(offering)
        current = dict(LearningOutcome.objects.filter(offering=offering).values_list("id", "number"))
        if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(current):
            raise ValidationError("The list of outcomes changed while you were editing. Reload and try again.",
                                  code="stale")
        before = {str(i): current[i] for i in sorted(current)}
        _renumber(offering, ordered_ids)
        after = {str(i): n for n, i in enumerate(ordered_ids, start=1)}
        if before != {k: after[k] for k in before}:
            record(user, "lo.reorder", offering, before={"numbers": before}, after={"numbers": after},
                   offering=offering)
```

**3. Assessment services.** Three rules from spec §5.3 live here.

- **Names are unique per course, ignoring case.** The database constraint is case-sensitive, so "Midterm I" and "midterm i" would both be allowed. Students would see two columns that look identical. We check case-insensitively before inserting and report it on the `name` field.
- **Changing the maximum needs confirmation once grades exist.** Every grade is converted with `raw ÷ max × 100` (P3). If Midterm I goes from out of 100 to out of 80, every student's normalised score for it changes, including published ones. So the first attempt raises `ValidationError(code="confirm_max_change")`. The view then shows the warning and the confirmation box. A confirmed change still fails if any existing grade would be above the new maximum.
- **Assessments with published grades can't be deleted.** Students have seen those grades. The instructor must unpublish first (S3-01), which is audited with a reason.

```python
# apps/outcomes/services.py  (continued)

def _check_unique_name(offering, name: str, *, exclude_pk=None) -> None:
    qs = offering.assessments.filter(name__iexact=name)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise ValidationError({"name": f"There is already an assessment called “{name}” in this course."})


def _check_fields(fields: dict) -> None:
    unknown = set(fields) - EDITABLE_ASSESSMENT_FIELDS
    if unknown:
        raise TypeError(f"Not editable through this service: {sorted(unknown)}")


def create_assessment(user, offering, **fields) -> Assessment:
    _check_fields(fields)
    with transaction.atomic():
        offering = _lock_offering(offering)
        ensure_term_open(offering)
        _check_unique_name(offering, fields["name"])
        last = offering.assessments.aggregate(m=Max("position"))["m"] or 0
        assessment = Assessment.objects.create(offering=offering, position=last + 1, **fields)
        record(user, "assessment.create", assessment,
               after=snapshot(assessment, ASSESSMENT_FIELDS), offering=offering)
        return assessment


def update_assessment(user, assessment, *, confirm_max_change=False, **fields) -> Assessment:
    _check_fields(fields)
    with transaction.atomic():
        offering = _lock_offering(assessment.offering)
        ensure_term_open(offering)
        # Re-read inside the lock: the caller's object may be stale or already modified in memory.
        assessment = Assessment.objects.select_for_update().get(pk=assessment.pk, offering=offering)
        before = snapshot(assessment, ASSESSMENT_FIELDS)

        if "name" in fields and fields["name"] != assessment.name:
            _check_unique_name(offering, fields["name"], exclude_pk=assessment.pk)

        new_max = fields.get("max_score", assessment.max_score)
        if new_max != assessment.max_score:
            graded = assessment.grades.filter(Q(score__isnull=False) | Q(published_score__isnull=False))
            if graded.exists():
                if not confirm_max_change:
                    raise ValidationError(
                        f"{assessment.name} already has grades. Changing the maximum from "
                        f"{assessment.max_score.normalize():f} to {new_max.normalize():f} changes every "
                        "student's converted score for it, including published ones.",
                        code="confirm_max_change",
                    )
                over = graded.filter(Q(score__gt=new_max) | Q(published_score__gt=new_max)).count()
                if over:
                    raise ValidationError({"max_score": (
                        f"{over} grade{'s are' if over != 1 else ' is'} above {new_max.normalize():f}. "
                        "Fix those grades first, or choose a higher maximum."
                    )})

        for name, value in fields.items():
            setattr(assessment, name, value)
        assessment.save()
        after = snapshot(assessment, ASSESSMENT_FIELDS)
        if after != before:
            record(user, "assessment.update", assessment, before=before, after=after, offering=offering)
        return assessment


def delete_assessment(user, assessment) -> None:
    with transaction.atomic():
        offering = _lock_offering(assessment.offering)
        ensure_term_open(offering)
        assessment = Assessment.objects.select_for_update().get(pk=assessment.pk, offering=offering)
        published = assessment.grades.filter(
            Q(published_at__isnull=False) | Q(published_score__isnull=False)
        ).exists()
        if assessment.published_at is not None or published:
            raise ValidationError(
                f"{assessment.name} has published grades, so it can't be deleted. "
                "Unpublish it on the Grades tab first; the unpublish is recorded in the history.",
                code="published",
            )
        before = snapshot(assessment, ASSESSMENT_FIELDS)
        before["lo_weights"] = {
            str(lo_id): str(w) for lo_id, w in assessment.lo_weights.values_list("learning_outcome_id", "weight")
        }
        before["draft_grades"] = assessment.grades.filter(score__isnull=False).count()
        record(user, "assessment.delete", assessment, before=before, offering=offering)
        assessment.delete()  # CASCADE removes its AssessmentLOWeight rows and draft Grade rows
```

> **Why `snapshot()` handles the types.** `snapshot(instance, fields)` from S2-02 (`apps/core/audit.py`) turns `Decimal` into `str` and dates into ISO strings, because `AuditEvent.before` / `after` are JSON columns and `json` can't store a `Decimal`.

**4. Read-side helpers for the page.** The setup page needs a few facts that would be business logic if they were in a template: the up/down order for each LO's arrow buttons, the course-weight total and whether it's 100, and the list of things a delete would remove. They live in `outcomes/selectors.py`. These selectors don't take `user`: the decorator has already decided that this user may see this offering, and they only read that offering's own setup.

The arrow buttons post the **whole new order** (`order=7,5,6`), not "move LO 6 up". The server then checks the posted list against the database (`reorder_los` above), so a stale page can't scramble numbers.

```python
# apps/outcomes/selectors.py
"""Reads for the setup and mapping pages. The decorator has already checked access."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import Assessment, LearningOutcome

HUNDRED = Decimal("100")


def _swap(ids: list[int], i: int, j: int) -> str:
    order = list(ids)
    order[i], order[j] = order[j], order[i]
    return ",".join(str(x) for x in order)


def setup_context(offering) -> dict:
    """Everything setup.html shows apart from the checklist."""
    los = list(offering.learning_outcomes.all())               # ordered by number (model Meta)
    ids = [lo.id for lo in los]
    lo_rows = [
        {
            "lo": lo,
            "up_order": _swap(ids, i, i - 1) if i > 0 else "",
            "down_order": _swap(ids, i, i + 1) if i < len(ids) - 1 else "",
        }
        for i, lo in enumerate(los)
    ]
    assessments = list(offering.assessments.all())             # ordered by position, id
    weights = [a.course_weight for a in assessments if a.course_weight is not None]
    total = sum(weights, Decimal("0"))
    return {
        "lo_rows": lo_rows,
        "assessments": assessments,
        "course_weight_total": total if weights else None,
        "course_weight_ok": not weights or total == HUNDRED,
        "missing_course_weight": sum(1 for a in assessments if a.course_weight is None),
    }


@dataclass(frozen=True)
class DeletionImpact:
    """What the delete confirmation lists (B4 AC3). `blocked_reason` set = the delete is refused."""
    title: str
    lines: tuple[str, ...]
    blocked_reason: str = ""


def _names(values, limit=6) -> str:
    values = list(values)
    shown = ", ".join(values[:limit])
    return shown + (f" and {len(values) - limit} more" if len(values) > limit else "")


def lo_deletion_impact(lo: LearningOutcome) -> DeletionImpact:
    a_names = list(lo.assessment_weights.order_by("assessment__position")
                   .values_list("assessment__name", flat=True))
    po_numbers = list(lo.po_weights.order_by("program_outcome__number")
                      .values_list("program_outcome__number", flat=True))
    lines = []
    if a_names:
        lines.append(f"{len(a_names)} assessment → LO weight{'s' if len(a_names) != 1 else ''} "
                     f"({_names(a_names)})")
    if po_numbers:
        lines.append(f"{len(po_numbers)} LO → PO weight{'s' if len(po_numbers) != 1 else ''} "
                     f"({_names(f'PO {n}' for n in po_numbers)})")
    later = lo.offering.learning_outcomes.filter(number__gt=lo.number).count()
    if later:
        lines.append(f"LO {lo.number + 1}{'–' + str(lo.number + later) if later > 1 else ''} "
                     f"will be renumbered to close the gap")
    return DeletionImpact(title=f"Delete LO {lo.number}?", lines=tuple(lines))


def assessment_deletion_impact(assessment: Assessment) -> DeletionImpact:
    if assessment.published_at is not None or assessment.grades.filter(published_score__isnull=False).exists():
        return DeletionImpact(
            title=f"{assessment.name} can't be deleted",
            lines=(),
            blocked_reason=f"{assessment.name} has published grades. Unpublish it on the Grades tab first.",
        )
    lo_numbers = list(assessment.lo_weights.order_by("learning_outcome__number")
                      .values_list("learning_outcome__number", flat=True))
    drafts = assessment.grades.filter(score__isnull=False).count()
    lines = []
    if lo_numbers:
        lines.append(f"{len(lo_numbers)} assessment → LO weight{'s' if len(lo_numbers) != 1 else ''} "
                     f"({_names(f'LO {n}' for n in lo_numbers)})")
    if drafts:
        lines.append(f"{drafts} draft grade{'s' if drafts != 1 else ''} (never published)")
    return DeletionImpact(title=f"Delete {assessment.name}?", lines=tuple(lines))
```

**5. The setup checklist selector.** `setup_status` answers "what's missing in this course?" for the checklist card, the course list badge (below), the offering home and the department overview (S3-04). One query per call: `Exists(...)` subqueries for the yes/no facts and a filtered `Count` for the assessment numbers. `setup_statuses(ids)` answers it for many offerings in the same single query, so the course list doesn't do one query per row.

```python
# apps/catalog/selectors.py  (add below visible_enrollments)
from dataclasses import dataclass

from django.db.models import Exists, OuterRef

from apps.outcomes.models import AssessmentLOWeight, LearningOutcome, LOPOWeight


@dataclass(frozen=True)
class SetupStatus:
    has_los: bool
    has_assessments: bool
    has_assessment_lo: bool
    has_lo_po: bool
    has_students: bool
    published_count: int
    assessment_count: int

    TOTAL = 5

    @property
    def done_count(self) -> int:
        return sum([self.has_los, self.has_assessments, self.has_assessment_lo,
                    self.has_lo_po, self.has_students])

    @property
    def is_complete(self) -> bool:
        return self.done_count == self.TOTAL


def setup_statuses(offering_ids) -> dict[int, SetupStatus]:
    """SetupStatus for many offerings in one query. Missing ids are simply absent."""
    rows = (
        CourseOffering.objects.filter(pk__in=list(offering_ids))
        .annotate(
            x_los=Exists(LearningOutcome.objects.filter(offering=OuterRef("pk"))),
            x_al=Exists(AssessmentLOWeight.objects.filter(assessment__offering=OuterRef("pk"))),
            x_lp=Exists(LOPOWeight.objects.filter(learning_outcome__offering=OuterRef("pk"))),
            x_students=Exists(Enrollment.objects.filter(offering=OuterRef("pk"),
                                                        status=Enrollment.Status.ENROLLED)),
            n_assessments=Count("assessments", distinct=True),
            n_published=Count("assessments", filter=Q(assessments__published_at__isnull=False),
                              distinct=True),
        )
        .values("pk", "x_los", "x_al", "x_lp", "x_students", "n_assessments", "n_published")
    )
    return {
        r["pk"]: SetupStatus(
            has_los=r["x_los"], has_assessments=r["n_assessments"] > 0,
            has_assessment_lo=r["x_al"], has_lo_po=r["x_lp"], has_students=r["x_students"],
            published_count=r["n_published"], assessment_count=r["n_assessments"],
        )
        for r in rows
    }


def setup_status(offering) -> SetupStatus:
    return setup_statuses([offering.pk])[offering.pk]
```

Merge the new imports into the existing import block at the top of the file: `Exists` and `OuterRef` join the existing `from django.db.models import Count, Q, QuerySet`, and `dataclass` goes with the other standard-library imports. Importing outcome models into `catalog.selectors` is safe. The model modules refer to each other with strings (`"catalog.CourseOffering"`), so there's no import cycle.

"Has LO→PO weights" ticks as soon as one link exists. Whether *every* LO is linked is mapping lint's job (L002, S2-07). The checklist says "you started this", and lint says "this is complete and sensible".

**6. Views.** The decorator from S2-02 removes `offering_id` from the URL kwargs and passes `offering` and `perms_for` instead. Read views use `@require_offering_access()`. Write views use `edit=True`, so a closed term gives 403 before the view runs. Every sub-object is loaded **filtered by the offering** (`get_object_or_404(LearningOutcome, pk=lo_id, offering=offering)`). Otherwise an instructor could put another course's LO id into their own course's URL.

Every POST that succeeds redirects (Post/Redirect/Get), so refreshing the page never re-submits a form. The `#los` / `#assessments` fragment scrolls back to the card the user was working on.

```python
# apps/outcomes/views.py
"""Course setup (B4) and the weight grids (B5). Views parse, call one service or selector, render."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.decorators import require_offering_access
from apps.accounts.permissions import is_head
from apps.catalog.selectors import setup_status
from apps.core.navigation import offering_tabs

from . import services
from .forms import AssessmentForm, LearningOutcomeForm
from .models import Assessment, LearningOutcome
from .selectors import assessment_deletion_impact, lo_deletion_impact, setup_context


def _setup_url(offering, anchor: str) -> str:
    return reverse("outcomes:setup", kwargs={"offering_id": offering.pk}) + f"#{anchor}"


def _page(request, template, offering, perms_for, current_tab, **extra):
    return render(request, template, {
        "offering": offering,
        "perms_for": perms_for,
        "tabs": offering_tabs(offering, current_tab),
        **extra,
    })


@login_required
@require_offering_access()
def setup(request, offering, perms_for):
    can_manage_enrollment = request.user.is_superuser or is_head(request.user, offering.course.program)
    return _page(request, "outcomes/setup.html", offering, perms_for, "outcomes:setup",
                 status=setup_status(offering), can_manage_enrollment=can_manage_enrollment,
                 **setup_context(offering))


# ---------- learning outcomes ----------

@login_required
@require_offering_access(edit=True)
def lo_create(request, offering, perms_for):
    form = LearningOutcomeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            lo = services.create_lo(request.user, offering, description=form.cleaned_data["description"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"Added LO {lo.number}.")
            return redirect(_setup_url(offering, "los"))
    return _page(request, "outcomes/lo_form.html", offering, perms_for, "outcomes:setup", form=form, lo=None)


@login_required
@require_offering_access(edit=True)
def lo_edit(request, lo_id, offering, perms_for):
    lo = get_object_or_404(LearningOutcome, pk=lo_id, offering=offering)
    form = LearningOutcomeForm(request.POST or None, initial={"description": lo.description})
    if request.method == "POST" and form.is_valid():
        try:
            services.update_lo(request.user, lo, description=form.cleaned_data["description"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"Saved LO {lo.number}.")
            return redirect(_setup_url(offering, "los"))
    return _page(request, "outcomes/lo_form.html", offering, perms_for, "outcomes:setup", form=form, lo=lo)


def _confirm_delete(request, offering, perms_for, impact, action_url):
    """GET of a delete URL: modal body for HTMX, full page otherwise (no-JS fallback)."""
    context = {"impact": impact, "action_url": action_url, "as_modal": bool(request.htmx)}
    if request.htmx:
        return render(request, "outcomes/confirm_delete.html#body", context)
    return _page(request, "outcomes/confirm_delete.html", offering, perms_for, "outcomes:setup", **context)


@login_required
@require_offering_access(edit=True)
def lo_delete(request, lo_id, offering, perms_for):
    lo = get_object_or_404(LearningOutcome, pk=lo_id, offering=offering)
    if request.method == "POST":
        number = lo.number
        try:
            services.delete_lo(request.user, lo)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"Deleted LO {number}. The outcomes after it were renumbered.")
        return redirect(_setup_url(offering, "los"))
    action = reverse("outcomes:lo_delete", kwargs={"offering_id": offering.pk, "lo_id": lo.pk})
    return _confirm_delete(request, offering, perms_for, lo_deletion_impact(lo), action)


@login_required
@require_offering_access(edit=True)
@require_POST
def lo_reorder(request, offering, perms_for):
    try:
        ordered = [int(part) for part in request.POST.get("order", "").split(",") if part.strip()]
        services.reorder_los(request.user, offering, ordered)
    except (ValueError, ValidationError):
        messages.error(request, "The list of outcomes changed while you were editing. This is the current order.")
    return redirect(_setup_url(offering, "los"))


# ---------- assessments ----------

@login_required
@require_offering_access(edit=True)
def assessment_create(request, offering, perms_for):
    form = AssessmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            assessment = services.create_assessment(request.user, offering, **form.model_data())
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"Added {assessment.name}.")
            return redirect(_setup_url(offering, "assessments"))
    return _page(request, "outcomes/assessment_form.html", offering, perms_for, "outcomes:setup",
                 form=form, assessment=None, needs_confirm=False)


@login_required
@require_offering_access(edit=True)
def assessment_edit(request, assessment_id, offering, perms_for):
    assessment = get_object_or_404(Assessment, pk=assessment_id, offering=offering)
    form = AssessmentForm(request.POST or None, initial=AssessmentForm.initial_for(assessment))
    needs_confirm = False
    if request.method == "POST" and form.is_valid():
        try:
            services.update_assessment(request.user, assessment,
                                       confirm_max_change=form.cleaned_data["confirm_max_change"],
                                       **form.model_data())
        except ValidationError as exc:
            needs_confirm = getattr(exc, "code", None) == "confirm_max_change"
            form.add_error(None, exc)
        else:
            messages.success(request, f"Saved {form.cleaned_data['name']}.")
            return redirect(_setup_url(offering, "assessments"))
    return _page(request, "outcomes/assessment_form.html", offering, perms_for, "outcomes:setup",
                 form=form, assessment=assessment, needs_confirm=needs_confirm)


@login_required
@require_offering_access(edit=True)
def assessment_delete(request, assessment_id, offering, perms_for):
    assessment = get_object_or_404(Assessment, pk=assessment_id, offering=offering)
    if request.method == "POST":
        name = assessment.name
        try:
            services.delete_assessment(request.user, assessment)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"Deleted {name}.")
        return redirect(_setup_url(offering, "assessments"))
    action = reverse("outcomes:assessment_delete",
                     kwargs={"offering_id": offering.pk, "assessment_id": assessment.pk})
    return _confirm_delete(request, offering, perms_for, assessment_deletion_impact(assessment), action)
```

`form.add_error(None, exc)` does the right thing for both kinds of `ValidationError`: a plain one becomes a form-level error shown at the top, and a dict one (`{"name": "..."}`) attaches each message to its field.

**7. URLs.** Paths are written in full, so you can read the whole URL from this one file. `config/urls.py` gets `path("", include("apps.outcomes.urls"))` next to the other app includes, if S2-01 didn't add it already.

```python
# apps/outcomes/urls.py
from django.urls import path

from . import views

app_name = "outcomes"

O = "offerings/<int:offering_id>/"

urlpatterns = [
    path(O + "setup/", views.setup, name="setup"),
    path(O + "setup/los/new/", views.lo_create, name="lo_create"),
    path(O + "setup/los/<int:lo_id>/edit/", views.lo_edit, name="lo_edit"),
    path(O + "setup/los/<int:lo_id>/delete/", views.lo_delete, name="lo_delete"),
    path(O + "setup/los/reorder/", views.lo_reorder, name="lo_reorder"),
    path(O + "setup/assessments/new/", views.assessment_create, name="assessment_create"),
    path(O + "setup/assessments/<int:assessment_id>/edit/", views.assessment_edit, name="assessment_edit"),
    path(O + "setup/assessments/<int:assessment_id>/delete/", views.assessment_delete,
         name="assessment_delete"),
    # S2-05 adds the mapping URLs below.
]
```

```python
# config/urls.py  (inside urlpatterns, next to the catalog include)
    path("", include("apps.outcomes.urls")),
```

**8. The checklist include.** Five items, each a link to where you fix it. "Students enrolled" links to the enrollment page only for heads, because instructors can't open it (it would 404 for them). Every tick also has text ("done" / "to do") for screen readers, since an emoji alone is announced inconsistently.

```django
{# templates/includes/setup_checklist.html — params: status (SetupStatus), offering, can_manage_enrollment (bool) #}
<section class="card mb-4" aria-labelledby="checklist-title-{{ offering.pk }}">
  <div class="card-body">
    <div class="d-flex justify-content-between align-items-baseline mb-2">
      <h2 class="h6 mb-0" id="checklist-title-{{ offering.pk }}">Setup checklist</h2>
      <span class="small text-body-secondary">{{ status.done_count }} of 5 done</span>
    </div>
    <div class="progress mb-3" style="height: .4rem" role="progressbar" aria-label="Setup progress"
         aria-valuenow="{{ status.done_count }}" aria-valuemin="0" aria-valuemax="5">
      <div class="progress-bar{% if status.is_complete %} bg-success{% endif %}"
           style="width: {% widthratio status.done_count 5 100 %}%"></div>
    </div>
    <ul class="list-unstyled d-flex flex-wrap gap-3 mb-0 small">
      {% url 'outcomes:setup' offering_id=offering.pk as setup_url %}
      {% url 'outcomes:mapping' offering_id=offering.pk as mapping_url %}
      <li>{% if status.has_los %}<span aria-hidden="true">✅</span><span class="visually-hidden">Done:</span>{% else %}<span aria-hidden="true">⬜</span><span class="visually-hidden">To do:</span>{% endif %}
        <a href="{{ setup_url }}#los">Learning outcomes</a></li>
      <li>{% if status.has_assessments %}<span aria-hidden="true">✅</span><span class="visually-hidden">Done:</span>{% else %}<span aria-hidden="true">⬜</span><span class="visually-hidden">To do:</span>{% endif %}
        <a href="{{ setup_url }}#assessments">Assessments</a></li>
      <li>{% if status.has_assessment_lo %}<span aria-hidden="true">✅</span><span class="visually-hidden">Done:</span>{% else %}<span aria-hidden="true">⬜</span><span class="visually-hidden">To do:</span>{% endif %}
        {% if mapping_url %}<a href="{{ mapping_url }}#a-lo">Assessment → LO weights</a>{% else %}Assessment → LO weights{% endif %}</li>
      <li>{% if status.has_lo_po %}<span aria-hidden="true">✅</span><span class="visually-hidden">Done:</span>{% else %}<span aria-hidden="true">⬜</span><span class="visually-hidden">To do:</span>{% endif %}
        {% if mapping_url %}<a href="{{ mapping_url }}#lo-po">LO → PO weights</a>{% else %}LO → PO weights{% endif %}</li>
      <li>{% if status.has_students %}<span aria-hidden="true">✅</span><span class="visually-hidden">Done:</span>{% else %}<span aria-hidden="true">⬜</span><span class="visually-hidden">To do:</span>{% endif %}
        {% if can_manage_enrollment %}<a href="{% url 'catalog:enrollments' offering_id=offering.pk %}">Students enrolled</a>{% else %}Students enrolled{% if not status.has_students %} <span class="text-body-secondary">(the department adds them)</span>{% endif %}{% endif %}</li>
    </ul>
  </div>
</section>
```

`{% url … as mapping_url %}` doesn't raise when the URL doesn't exist yet. It sets the variable to an empty string. So this include works before S2-05 merges, and the mapping items become links automatically once it does.

**9. The setup page.** Two cards side by side on a laptop, stacked on a phone. Empty states say what an LO *is* and what to do first (*The Blank Slate*, Getting Real Ch. 9). Edit controls appear only when `perms_for.can_edit`. On a closed term the page is a clean read-only view, and the header from S2-02 shows the 🔒 badge.

The delete buttons use the shared modal from `base.html` (S1-09: `#modal`, HTMX fills `#modal-content`). `hx-get` loads the confirmation body into it while Bootstrap opens it. Without JavaScript the same link opens the full-page confirmation, because it's a real `href`.

```django
{# apps/outcomes/templates/outcomes/setup.html #}
{% extends "base.html" %}
{% load polaris %}
{% block title %}Setup · {{ offering.course.code }} · POlaris{% endblock %}
{% block content %}
<div class="container py-4">
  {% include "includes/offering_header.html" with offering=offering tabs=tabs perms_for=perms_for only %}
  {% include "includes/setup_checklist.html" with status=status offering=offering can_manage_enrollment=can_manage_enrollment only %}

  <div class="row g-4">
    {# ---------------- Learning outcomes ---------------- #}
    <div class="col-lg-6">
      <section class="card h-100" id="los" aria-labelledby="los-title">
        <div class="card-header d-flex justify-content-between align-items-center">
          <h2 class="h5 mb-0" id="los-title">Learning outcomes</h2>
          {% if perms_for.can_edit and lo_rows %}
            <a class="btn btn-sm btn-primary" href="{% url 'outcomes:lo_create' offering_id=offering.pk %}">+ Add outcome</a>
          {% endif %}
        </div>
        {% if lo_rows %}
          <ul class="list-group list-group-flush">
            {% for row in lo_rows %}
              <li class="list-group-item d-flex gap-2 align-items-start">
                <span class="badge text-bg-secondary pl-num mt-1">LO {{ row.lo.number }}</span>
                <span class="flex-grow-1">
                  {{ row.lo.description }}
                  {% if row.lo.source != "manual" %}<span class="badge text-bg-light border ms-1">{{ row.lo.get_source_display }}</span>{% endif %}
                </span>
                {% if perms_for.can_edit %}
                  <div class="d-flex gap-1 flex-shrink-0">
                    {% if row.up_order %}
                      <form method="post" action="{% url 'outcomes:lo_reorder' offering_id=offering.pk %}">
                        {% csrf_token %}<input type="hidden" name="order" value="{{ row.up_order }}">
                        <button class="btn btn-sm btn-outline-secondary" aria-label="Move LO {{ row.lo.number }} up">↑</button>
                      </form>
                    {% endif %}
                    {% if row.down_order %}
                      <form method="post" action="{% url 'outcomes:lo_reorder' offering_id=offering.pk %}">
                        {% csrf_token %}<input type="hidden" name="order" value="{{ row.down_order }}">
                        <button class="btn btn-sm btn-outline-secondary" aria-label="Move LO {{ row.lo.number }} down">↓</button>
                      </form>
                    {% endif %}
                    <a class="btn btn-sm btn-outline-secondary" aria-label="Edit LO {{ row.lo.number }}"
                       href="{% url 'outcomes:lo_edit' offering_id=offering.pk lo_id=row.lo.pk %}">Edit</a>
                    {% url 'outcomes:lo_delete' offering_id=offering.pk lo_id=row.lo.pk as delete_url %}
                    <a class="btn btn-sm btn-outline-danger" aria-label="Delete LO {{ row.lo.number }}" href="{{ delete_url }}"
                       hx-get="{{ delete_url }}" hx-target="#modal-content"
                       data-bs-toggle="modal" data-bs-target="#modal">Delete</a>
                  </div>
                {% endif %}
              </li>
            {% endfor %}
          </ul>
        {% else %}
          <div class="card-body">
            {% include "includes/empty_state.html" with title="No learning outcomes yet" message="Learning outcomes say what a student can do after this course, for example “Design a relational schema in 3NF”. Every grade reaches the program outcomes through them, so add them first." only %}
            {% if perms_for.can_edit %}
              <p class="text-center mb-0">
                <a class="btn btn-primary" href="{% url 'outcomes:lo_create' offering_id=offering.pk %}">+ Add the first outcome</a>
                {# S6-01 adds an "Upload syllabus instead" button here. #}
              </p>
            {% endif %}
          </div>
        {% endif %}
      </section>
    </div>

    {# ---------------- Assessments ---------------- #}
    <div class="col-lg-6">
      <section class="card h-100" id="assessments" aria-labelledby="assessments-title">
        <div class="card-header d-flex justify-content-between align-items-center">
          <h2 class="h5 mb-0" id="assessments-title">Assessments</h2>
          {% if perms_for.can_edit and assessments %}
            <a class="btn btn-sm btn-primary" href="{% url 'outcomes:assessment_create' offering_id=offering.pk %}">+ Add assessment</a>
          {% endif %}
        </div>
        {% if assessments %}
          <div class="table-responsive">
            <table class="table table-sm align-middle mb-0">
              <thead>
                <tr><th scope="col">Name</th><th scope="col">Kind</th><th scope="col" class="text-end">Max</th>
                    <th scope="col" class="text-end">Course %</th><th scope="col">Due</th>
                    {% if perms_for.can_edit %}<th scope="col"><span class="visually-hidden">Actions</span></th>{% endif %}</tr>
              </thead>
              <tbody>
                {% for a in assessments %}
                  <tr>
                    <td>{{ a.name }}{% if a.published_at %} <span class="badge text-bg-success">Published</span>{% endif %}</td>
                    <td>{{ a.get_kind_display }}</td>
                    <td class="text-end pl-num">{{ a.max_score|weight }}</td>
                    <td class="text-end pl-num">{% if a.course_weight is not None %}{{ a.course_weight|weight }}{% else %}<span class="text-body-secondary">—</span>{% endif %}</td>
                    <td>{{ a.due_date|date:"j M"|default:"—" }}</td>
                    {% if perms_for.can_edit %}
                      <td class="text-end text-nowrap">
                        <a class="btn btn-sm btn-outline-secondary" aria-label="Edit {{ a.name }}"
                           href="{% url 'outcomes:assessment_edit' offering_id=offering.pk assessment_id=a.pk %}">Edit</a>
                        {% url 'outcomes:assessment_delete' offering_id=offering.pk assessment_id=a.pk as delete_url %}
                        <a class="btn btn-sm btn-outline-danger" aria-label="Delete {{ a.name }}" href="{{ delete_url }}"
                           hx-get="{{ delete_url }}" hx-target="#modal-content"
                           data-bs-toggle="modal" data-bs-target="#modal">Delete</a>
                      </td>
                    {% endif %}
                  </tr>
                {% endfor %}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row" colspan="3">Course weights</th>
                  <td class="text-end pl-num">{% if course_weight_total is not None %}{{ course_weight_total|weight }}%{% else %}—{% endif %}</td>
                  <td colspan="{% if perms_for.can_edit %}2{% else %}1{% endif %}">
                    {% if not course_weight_ok %}
                      <span class="text-warning-emphasis small"><span aria-hidden="true">⚠</span> Should add up to 100%</span>
                    {% elif course_weight_total is not None %}
                      <span class="text-success small"><span aria-hidden="true">✓</span> Adds up to 100%</span>
                    {% endif %}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          {% if missing_course_weight and course_weight_total is not None %}
            <p class="small text-body-secondary px-3 pt-2 mb-2">{{ missing_course_weight }} assessment{{ missing_course_weight|pluralize }} without a course weight.</p>
          {% endif %}
        {% else %}
          <div class="card-body">
            {% include "includes/empty_state.html" with title="No assessments yet" message="Assessments are the things you grade: midterms, the final, projects, quizzes. Add each one with its maximum mark." only %}
            {% if perms_for.can_edit %}
              <p class="text-center mb-0"><a class="btn btn-primary" href="{% url 'outcomes:assessment_create' offering_id=offering.pk %}">+ Add the first assessment</a></p>
            {% endif %}
          </div>
        {% endif %}
      </section>
    </div>
  </div>
</div>
{% endblock %}
```

The `weight` filter (from `apps/core/templatetags/polaris.py`, listed in §4.8) prints `100.00` as `100` and `12.50` as `12.5`. If S1-09 didn't write it, add it now:

```python
# apps/core/templatetags/polaris.py  (add if missing)
from decimal import Decimal


@register.filter
def weight(value):
    """40.00 -> "40", 12.50 -> "12.5". For weights and max scores, never for scores (use |score)."""
    if value is None or value == "":
        return ""
    return f"{Decimal(value).normalize():f}"
```

**10. The two form pages and the delete confirmation.** The assessment form shows the confirmation checkbox only after the service has asked for it (`needs_confirm`). Otherwise an instructor might tick it "just in case" and lose the protection.

```django
{# apps/outcomes/templates/outcomes/lo_form.html #}
{% extends "base.html" %}
{% block title %}{% if lo %}Edit LO {{ lo.number }}{% else %}New learning outcome{% endif %} · POlaris{% endblock %}
{% block content %}
<div class="container py-4" style="max-width: 48rem">
  {% include "includes/offering_header.html" with offering=offering tabs=tabs perms_for=perms_for only %}
  <h2 class="h4 mb-3">{% if lo %}Edit LO {{ lo.number }}{% else %}New learning outcome{% endif %}</h2>
  <form method="post" novalidate>
    {% csrf_token %}
    {% if form.non_field_errors %}<div class="alert alert-danger">{{ form.non_field_errors|join:" " }}</div>{% endif %}
    <div class="mb-3">
      <label class="form-label" for="{{ form.description.id_for_label }}">Description</label>
      {{ form.description }}
      {% if form.description.errors %}<div class="invalid-feedback d-block">{{ form.description.errors|join:" " }}</div>{% endif %}
      <div class="form-text">{{ form.description.help_text }}</div>
    </div>
    <button class="btn btn-primary">{% if lo %}Save{% else %}Add outcome{% endif %}</button>
    <a class="btn btn-link" href="{% url 'outcomes:setup' offering_id=offering.pk %}#los">Cancel</a>
  </form>
</div>
{% endblock %}
```

```django
{# apps/outcomes/templates/outcomes/assessment_form.html #}
{% extends "base.html" %}
{% block title %}{% if assessment %}Edit {{ assessment.name }}{% else %}New assessment{% endif %} · POlaris{% endblock %}
{% block content %}
<div class="container py-4" style="max-width: 48rem">
  {% include "includes/offering_header.html" with offering=offering tabs=tabs perms_for=perms_for only %}
  <h2 class="h4 mb-3">{% if assessment %}Edit {{ assessment.name }}{% else %}New assessment{% endif %}</h2>
  <form method="post" novalidate>
    {% csrf_token %}
    {% if form.non_field_errors %}
      <div class="alert {% if needs_confirm %}alert-warning{% else %}alert-danger{% endif %}">{{ form.non_field_errors|join:" " }}</div>
    {% endif %}
    <div class="row g-3">
      {% for field in form %}
        {% if field.name != "confirm_max_change" %}
          <div class="{% if field.name == 'name' %}col-md-8{% elif field.name == 'kind' %}col-md-4{% else %}col-md-4{% endif %}">
            <label class="form-label" for="{{ field.id_for_label }}">{{ field.label }}</label>
            {{ field }}
            {% if field.errors %}<div class="invalid-feedback d-block">{{ field.errors|join:" " }}</div>{% endif %}
            {% if field.help_text %}<div class="form-text">{{ field.help_text }}</div>{% endif %}
          </div>
        {% endif %}
      {% endfor %}
    </div>
    {% if needs_confirm %}
      <div class="form-check mt-3">
        {{ form.confirm_max_change }}
        <label class="form-check-label" for="{{ form.confirm_max_change.id_for_label }}">{{ form.confirm_max_change.label }}</label>
      </div>
    {% endif %}
    <div class="mt-4">
      <button class="btn btn-primary">{% if assessment %}Save{% else %}Add assessment{% endif %}</button>
      <a class="btn btn-link" href="{% url 'outcomes:setup' offering_id=offering.pk %}#assessments">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

The `body` partial is defined `inline`, so it renders in place on the full page and can also be loaded alone as `"outcomes/confirm_delete.html#body"` for the modal (Django 6 template partials).

```django
{# apps/outcomes/templates/outcomes/confirm_delete.html #}
{% extends "base.html" %}
{% block title %}{{ impact.title }} · POlaris{% endblock %}
{% block content %}
<div class="container py-4" style="max-width: 40rem">
  {% if not as_modal %}{% include "includes/offering_header.html" with offering=offering tabs=tabs perms_for=perms_for only %}{% endif %}
  <div class="{% if not as_modal %}card{% endif %}">
  {% partialdef body inline %}
    <div class="modal-header">
      <h2 class="modal-title h5">{{ impact.title }}</h2>
      {% if as_modal %}<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>{% endif %}
    </div>
    <div class="modal-body">
      {% if impact.blocked_reason %}
        <div class="alert alert-warning mb-0">{{ impact.blocked_reason }}</div>
      {% else %}
        <p>This also removes:</p>
        <ul>
          {% for line in impact.lines %}<li>{{ line }}</li>{% empty %}<li>Nothing else. It isn't used anywhere yet.</li>{% endfor %}
        </ul>
        <p class="mb-0 small text-body-secondary">The deletion is recorded in the course history.</p>
      {% endif %}
    </div>
    <div class="modal-footer">
      {% if as_modal %}
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
      {% else %}
        <a class="btn btn-secondary" href="javascript:history.back()">Cancel</a>
      {% endif %}
      {% if not impact.blocked_reason %}
        <form method="post" action="{{ action_url }}">{% csrf_token %}<button class="btn btn-danger">Delete</button></form>
      {% endif %}
    </div>
  {% endpartialdef %}
  </div>
</div>
{% endblock %}
```

**11. Show setup progress on *My courses* and the offering home.** S2-01 left a placeholder for both. The course list gets a "Setup" column with "3/5" and, once S2-07 merges, a lint badge. Both come from batched selectors, so 10 courses still cost one query each, not ten.

```python
# apps/catalog/views.py  (replace teaching and offering_home from S2-01)
from apps.catalog.selectors import setup_status, setup_statuses, teaching_offerings, visible_enrollments


@login_required
@require_role("instructor", "head")
def teaching(request):
    offerings = list(teaching_offerings(request.user))
    statuses = setup_statuses(o.pk for o in offerings)
    for o in offerings:                     # display-only attributes; templates can't index dicts
        o.setup = statuses[o.pk]
    return render(request, "catalog/teaching.html", {
        "offerings": offerings,
        "department_offerings_url": safe_reverse("catalog:offerings"),
    })


@login_required
@require_offering_access()
def offering_home(request, offering, perms_for):
    return render(request, "catalog/offering_home.html", {
        "offering": offering,
        "perms_for": perms_for,
        "tabs": offering_tabs(offering, "catalog:offering"),
        "student_count": visible_enrollments(request.user, offering).count(),
        "status": setup_status(offering),
        "can_manage_enrollment": request.user.is_superuser or is_head(request.user, offering.course.program),
    })
```

Add `from apps.accounts.permissions import is_head` to the imports. In `catalog/teaching.html`, add a header cell `<th scope="col">Setup</th>` after *Status* and this cell in the row:

```django
<td>
  <span class="small pl-num{% if o.setup.is_complete %} text-success{% endif %}">{{ o.setup.done_count }}/5</span>
  {# S2-07 adds the lint badge here #}
</td>
```

In `catalog/offering_home.html`, replace the S2-04 comment with:

```django
{% include "includes/setup_checklist.html" with status=status offering=offering can_manage_enrollment=can_manage_enrollment only %}
```

### Tests

The `course` fixture is shared by all three stories. It builds an open-term offering with an assigned instructor, an active PO set with three POs, two LOs and two assessments. Everything else builds on it. The factories come from S1-08 and accept any model field as a keyword.

```python
# apps/outcomes/tests/conftest.py
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.catalog.models import Term
from apps.core.tests.factories import (
    AssessmentFactory, CourseFactory, LearningOutcomeFactory, MembershipFactory, OfferingFactory,
    ProgramFactory, ProgramOutcomeFactory, ProgramOutcomeSetFactory, TermFactory, UserFactory,
)


@pytest.fixture
def course(db):
    program = ProgramFactory(code="CSE")
    po_set = ProgramOutcomeSetFactory(program=program, label="2023 curriculum",
                                      effective_from_year=2020, is_active=True)
    po1 = ProgramOutcomeFactory(po_set=po_set, number=1, short_name="Math & science")
    po2 = ProgramOutcomeFactory(po_set=po_set, number=2, short_name="Problem solving")
    po3 = ProgramOutcomeFactory(po_set=po_set, number=3, short_name="Design")
    term = TermFactory(code="2026F", name="Fall 2026", starts_on=date(2026, 9, 21),
                       ends_on=date(2027, 1, 15), status=Term.Status.OPEN)
    offering = OfferingFactory(course=CourseFactory(program=program, code="CSE 311"), term=term)
    teacher = UserFactory(email="can.aydin@test.edu")
    MembershipFactory(user=teacher, program=program, role="instructor")
    offering.instructors.add(teacher)
    midterm = AssessmentFactory(offering=offering, name="Midterm I", max_score=Decimal("100"),
                                course_weight=Decimal("40"), position=1)
    project = AssessmentFactory(offering=offering, name="Project", max_score=Decimal("100"),
                                course_weight=Decimal("60"), position=2)
    lo1 = LearningOutcomeFactory(offering=offering, number=1, description="Explain design choices")
    lo2 = LearningOutcomeFactory(offering=offering, number=2, description="Apply agile practices")
    return SimpleNamespace(program=program, po_set=po_set, po1=po1, po2=po2, po3=po3, term=term,
                           offering=offering, teacher=teacher, midterm=midterm, project=project,
                           lo1=lo1, lo2=lo2)


@pytest.fixture
def teacher_client(client, course):
    client.force_login(course.teacher)
    return client
```

```python
# apps/outcomes/tests/test_setup_services.py
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.catalog.models import Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import EnrollmentFactory, GradeFactory
from apps.outcomes import services
from apps.outcomes.models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight


def numbers(offering):
    return list(offering.learning_outcomes.order_by("number").values_list("number", flat=True))


def descriptions(offering):
    return list(offering.learning_outcomes.order_by("number").values_list("description", flat=True))


def test_new_los_get_the_next_number_and_are_audited(course):
    lo3 = services.create_lo(course.teacher, course.offering, description="Test software")
    assert lo3.number == 3
    event = AuditEvent.objects.get(action="lo.create", entity_id=lo3.pk)
    assert event.actor == course.teacher
    assert event.offering == course.offering
    assert event.after["description"] == "Test software"


def test_deleting_an_lo_closes_the_gap(course):
    """B4 AC1: numbers stay contiguous."""
    services.create_lo(course.teacher, course.offering, description="Third")
    services.delete_lo(course.teacher, course.lo1)
    assert numbers(course.offering) == [1, 2]
    assert descriptions(course.offering) == ["Apply agile practices", "Third"]


def test_deleting_an_lo_removes_its_weights_and_records_them(course):
    AssessmentLOWeight.objects.create(assessment=course.midterm, learning_outcome=course.lo1, weight=Decimal("60"))
    LOPOWeight.objects.create(learning_outcome=course.lo1, program_outcome=course.po1, weight=4)
    lo1_id = course.lo1.pk
    services.delete_lo(course.teacher, course.lo1)
    assert not AssessmentLOWeight.objects.filter(learning_outcome_id=lo1_id).exists()
    assert not LOPOWeight.objects.filter(learning_outcome_id=lo1_id).exists()
    event = AuditEvent.objects.get(action="lo.delete", entity_id=lo1_id)
    assert event.before["assessment_weights"] == {str(course.midterm.pk): "60.00"}
    assert event.before["po_weights"] == {str(course.po1.pk): 4}


def test_reorder_renumbers_in_the_new_order(course):
    lo3 = services.create_lo(course.teacher, course.offering, description="Third")
    services.reorder_los(course.teacher, course.offering, [lo3.pk, course.lo1.pk, course.lo2.pk])
    ids = list(course.offering.learning_outcomes.order_by("number").values_list("id", flat=True))
    assert ids == [lo3.pk, course.lo1.pk, course.lo2.pk]
    assert numbers(course.offering) == [1, 2, 3]
    assert AuditEvent.objects.filter(action="lo.reorder").count() == 1


@pytest.mark.parametrize("bad", [[], "missing_one", "duplicate"])
def test_reorder_refuses_a_stale_or_broken_list(course, bad):
    ids = {"missing_one": [course.lo2.pk], "duplicate": [course.lo1.pk, course.lo1.pk]}.get(bad, bad)
    with pytest.raises(ValidationError) as exc:
        services.reorder_los(course.teacher, course.offering, ids)
    assert exc.value.code == "stale"
    assert numbers(course.offering) == [1, 2]


def test_closed_term_refuses_setup_writes(course):
    course.term.status = Term.Status.CLOSED
    course.term.save()
    with pytest.raises(ValidationError):
        services.create_lo(course.teacher, course.offering, description="Too late")
    with pytest.raises(ValidationError):
        services.create_assessment(course.teacher, course.offering, name="Quiz", kind="quiz",
                                   max_score=Decimal("10"), course_weight=None, due_date=None)
    with pytest.raises(ValidationError):
        services.delete_lo(course.teacher, course.lo1)
    assert LearningOutcome.objects.filter(offering=course.offering).count() == 2


def test_assessment_names_are_unique_ignoring_case(course):
    with pytest.raises(ValidationError) as exc:
        services.create_assessment(course.teacher, course.offering, name="midterm i", kind="midterm",
                                   max_score=Decimal("100"), course_weight=None, due_date=None)
    assert "name" in exc.value.message_dict


def test_new_assessment_goes_last(course):
    quiz = services.create_assessment(course.teacher, course.offering, name="Quiz 1", kind="quiz",
                                      max_score=Decimal("20"), course_weight=Decimal("0"), due_date=None)
    assert quiz.position == 3


def test_max_change_with_grades_needs_confirmation(course):
    enrollment = EnrollmentFactory(offering=course.offering)
    GradeFactory(assessment=course.midterm, enrollment=enrollment, score=Decimal("70"))
    with pytest.raises(ValidationError) as exc:
        services.update_assessment(course.teacher, course.midterm, max_score=Decimal("80"))
    assert exc.value.code == "confirm_max_change"
    with pytest.raises(ValidationError) as exc:
        services.update_assessment(course.teacher, course.midterm, confirm_max_change=True,
                                   max_score=Decimal("50"))
    assert "max_score" in exc.value.message_dict           # 70 > 50
    services.update_assessment(course.teacher, course.midterm, confirm_max_change=True,
                               max_score=Decimal("80"))
    course.midterm.refresh_from_db()
    assert course.midterm.max_score == Decimal("80")


def test_max_change_without_grades_needs_no_confirmation(course):
    services.update_assessment(course.teacher, course.midterm, max_score=Decimal("50"))
    course.midterm.refresh_from_db()
    assert course.midterm.max_score == Decimal("50")


def test_assessment_with_published_grades_cannot_be_deleted(course):
    """B4 AC4 / spec §5.3."""
    enrollment = EnrollmentFactory(offering=course.offering)
    GradeFactory(assessment=course.midterm, enrollment=enrollment, score=Decimal("50"),
                 published_score=Decimal("50"), published_at=timezone.now())
    with pytest.raises(ValidationError) as exc:
        services.delete_assessment(course.teacher, course.midterm)
    assert exc.value.code == "published"
    assert Assessment.objects.filter(pk=course.midterm.pk).exists()


def test_deleting_an_assessment_removes_its_weights_and_drafts(course):
    AssessmentLOWeight.objects.create(assessment=course.midterm, learning_outcome=course.lo1, weight=Decimal("60"))
    GradeFactory(assessment=course.midterm, enrollment=EnrollmentFactory(offering=course.offering),
                 score=Decimal("50"))
    midterm_id = course.midterm.pk
    services.delete_assessment(course.teacher, course.midterm)
    assert not Assessment.objects.filter(pk=midterm_id).exists()
    event = AuditEvent.objects.get(action="assessment.delete", entity_id=midterm_id)
    assert event.before["draft_grades"] == 1
```

```python
# apps/outcomes/tests/test_setup_views.py
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.core.tests.factories import EnrollmentFactory, GradeFactory, MembershipFactory, UserFactory
from apps.outcomes.models import Assessment, AssessmentLOWeight, LearningOutcome


def url(name, course, **extra):
    return reverse(f"outcomes:{name}", kwargs={"offering_id": course.offering.pk, **extra})


def test_setup_page_lists_los_and_assessments(teacher_client, course):
    response = teacher_client.get(url("setup", course))
    assert response.status_code == 200
    html = response.content.decode()
    assert "Explain design choices" in html and "Midterm I" in html
    assert "Setup checklist" in html


def test_empty_course_shows_empty_states(client, course):
    LearningOutcome.objects.filter(offering=course.offering).delete()
    Assessment.objects.filter(offering=course.offering).delete()
    client.force_login(course.teacher)
    html = client.get(url("setup", course)).content.decode()
    assert "No learning outcomes yet" in html and "No assessments yet" in html


def test_course_weights_not_100_show_a_warning(teacher_client, course):
    """B4 AC2: a warning, not an error."""
    Assessment.objects.filter(pk=course.project.pk).update(course_weight=Decimal("50"))
    html = teacher_client.get(url("setup", course)).content.decode()
    assert "Should add up to 100%" in html


def test_create_lo_redirects_back_to_the_card(teacher_client, course):
    response = teacher_client.post(url("lo_create", course), {"description": "Test the software"})
    assert response.status_code == 302
    assert response["Location"].endswith("#los")
    assert course.offering.learning_outcomes.get(number=3).description == "Test the software"


def _other_offering(course):
    from apps.core.tests.factories import OfferingFactory
    return OfferingFactory(course__program=course.program, term=course.term)


def test_lo_from_another_course_is_404(teacher_client, course):
    """The sub-object rule from S2-02: ids are filtered by the offering in the URL."""
    other = LearningOutcome.objects.create(offering=_other_offering(course), number=1, description="Not yours")
    response = teacher_client.get(url("lo_edit", course, lo_id=other.pk))
    assert response.status_code == 404


def test_reorder_view(teacher_client, course):
    order = f"{course.lo2.pk},{course.lo1.pk}"
    response = teacher_client.post(url("lo_reorder", course), {"order": order})
    assert response.status_code == 302
    course.lo1.refresh_from_db()
    assert course.lo1.number == 2


def test_delete_modal_lists_what_goes_with_it(teacher_client, course):
    """B4 AC3."""
    AssessmentLOWeight.objects.create(assessment=course.midterm, learning_outcome=course.lo1, weight=Decimal("60"))
    response = teacher_client.get(url("lo_delete", course, lo_id=course.lo1.pk), headers={"HX-Request": "true"})
    html = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in html                      # partial only
    assert "1 assessment → LO weight (Midterm I)" in html
    assert "LO 2 will be renumbered" in html


def test_delete_published_assessment_is_refused_with_a_message(teacher_client, course):
    GradeFactory(assessment=course.midterm, enrollment=EnrollmentFactory(offering=course.offering),
                 score=Decimal("50"), published_score=Decimal("50"), published_at=timezone.now())
    modal = teacher_client.get(url("assessment_delete", course, assessment_id=course.midterm.pk),
                               headers={"HX-Request": "true"}).content.decode()
    assert "Unpublish it on the Grades tab first" in modal and "Delete</button>" not in modal
    response = teacher_client.post(url("assessment_delete", course, assessment_id=course.midterm.pk), follow=True)
    assert "Unpublish it on the Grades tab first" in response.content.decode()
    assert Assessment.objects.filter(pk=course.midterm.pk).exists()


def test_max_change_asks_for_confirmation_in_the_form(teacher_client, course):
    GradeFactory(assessment=course.midterm, enrollment=EnrollmentFactory(offering=course.offering),
                 score=Decimal("70"))
    data = {"name": "Midterm I", "kind": "midterm", "max_score": "80", "course_weight": "40", "due_date": ""}
    first = teacher_client.post(url("assessment_edit", course, assessment_id=course.midterm.pk), data)
    assert first.status_code == 200
    assert "Yes, change the maximum" in first.content.decode()
    second = teacher_client.post(url("assessment_edit", course, assessment_id=course.midterm.pk),
                                 {**data, "confirm_max_change": "on"})
    assert second.status_code == 302


def test_instructor_of_another_course_gets_404(client, course):
    stranger = UserFactory(email="stranger@test.edu")
    MembershipFactory(user=stranger, program=course.program, role="instructor")
    client.force_login(stranger)
    assert client.get(url("setup", course)).status_code == 404
```

```python
# apps/outcomes/tests/test_setup_status.py  (here, not in apps/catalog, so it can use the `course` fixture)
from decimal import Decimal

from django.utils import timezone

from apps.catalog.selectors import setup_status, setup_statuses
from apps.core.tests.factories import EnrollmentFactory, OfferingFactory
from apps.outcomes.models import Assessment, AssessmentLOWeight, LOPOWeight


def test_status_of_a_half_set_up_course(course):
    status = setup_status(course.offering)
    assert (status.has_los, status.has_assessments) == (True, True)
    assert (status.has_assessment_lo, status.has_lo_po, status.has_students) == (False, False, False)
    assert status.done_count == 2 and not status.is_complete


def test_status_of_a_complete_course(course):
    AssessmentLOWeight.objects.create(assessment=course.midterm, learning_outcome=course.lo1, weight=Decimal("60"))
    LOPOWeight.objects.create(learning_outcome=course.lo1, program_outcome=course.po1, weight=3)
    EnrollmentFactory(offering=course.offering)
    Assessment.objects.filter(pk=course.midterm.pk).update(published_at=timezone.now())
    status = setup_status(course.offering)
    assert status.is_complete
    assert (status.assessment_count, status.published_count) == (2, 1)


def test_dropped_students_dont_count(course):
    EnrollmentFactory(offering=course.offering, status="dropped")
    assert setup_status(course.offering).has_students is False


def test_many_offerings_cost_one_query(course, django_assert_num_queries):
    others = [OfferingFactory(course__program=course.program, term=course.term) for _ in range(5)]
    ids = [course.offering.pk] + [o.pk for o in others]
    with django_assert_num_queries(1):
        statuses = setup_statuses(ids)
    assert set(statuses) == set(ids)
    assert statuses[others[0].pk].done_count == 0
```

### Check it works

1. `uv run python manage.py seed_demo --reset`, then `uv run python manage.py runserver`.
2. Log in as the seeded instructor (Dr. Can Aydın, `can.aydin@acibadem.edu.tr`, password from Appendix B). *My courses* shows a **Setup** column with numbers like `2/5`.
3. Open a course → **Setup** tab. The checklist shows what's done.
4. Add two LOs. They appear as LO 3 and LO 4 (or 1 and 2 on an empty course). Click ↑ on the last one: it becomes LO 3 and the other moves down. The numbers have no gaps.
5. Delete LO 1. The modal says what else goes with it and which LOs get renumbered. Confirm. The list now starts at LO 1 again.
6. Add an assessment called `midterm i` when "Midterm I" exists. The form shows "There is already an assessment called…".
7. Change course weights so they add up to 90. The footer shows "⚠ Should add up to 100%", and you can still save.
8. In the Django shell, publish a grade on one assessment (`Assessment.objects.filter(name="Midterm I").update(published_at=timezone.now())`), then try to delete it. The modal explains why it can't be deleted.
9. As the head, close the term (`/department/terms/`). Reload the setup page: no edit buttons, and the 🔒 badge shows. Typing `…/setup/los/new/` directly gives the 403 page.
10. `uv run pytest apps/outcomes apps/catalog apps/accounts/tests/test_permission_matrix.py -q` is green.

### Done when

| AC (spec Part 6, B4) | Proven by |
|---|---|
| AC1 LO numbers unique and contiguous after reorder and delete | `test_deleting_an_lo_closes_the_gap`, `test_reorder_renumbers_in_the_new_order`, the `uniq_lo_number` constraint |
| AC2 course weights not summing to 100 warn, don't block | `test_course_weights_not_100_show_a_warning` (and lint L004 in S2-07) |
| AC3 delete asks for confirmation and lists what goes | `test_delete_modal_lists_what_goes_with_it` |
| AC4 assessments with published grades can't be deleted | `test_assessment_with_published_grades_cannot_be_deleted`, `test_delete_published_assessment_is_refused_with_a_message` |
| §5.3 max-score change confirmed and re-validated | `test_max_change_with_grades_needs_confirmation`, `test_max_change_asks_for_confirmation_in_the_form` |
| §5.3 closed term refuses writes | `test_closed_term_refuses_setup_writes`, matrix `test_closed_term_blocks_every_edit_route` |
| Permission matrix rows `story="S2-04"` pass | `test_permission_matrix` |
| Checklist works for many offerings in one query | `test_many_offerings_cost_one_query` |

### Commits and PR

```
Add LO and assessment services with audit and closed-term checks (#S2-04)
Add setup page with LO reordering and delete confirmation (#S2-04)
Add setup checklist selector and show it on My courses (#S2-04)
Test max-score confirmation and published-assessment delete guard (#S2-04)
```

PR title: **Course setup: LOs, assessments and the setup checklist (S2-04)**. Use the real issue number in place of `S2-04` in commit messages.

---

## S2-05 · Both weight grids with live validation and stale-edit detection

**Points:** 5 · **Owner:** Person B · **Branch:** `feature/S2-05-weight-grids` · **Depends on:** S2-04 (merge it first: same `services.py`, `selectors.py`, `views.py`, `urls.py`)

### Goal

On the **Mapping** tab an instructor fills two spreadsheet-like grids: assessment → LO weights (percent) and LO → PO weights (1–5). A blank cell means "no arrow", and no row is stored. Each cell is checked as soon as you leave it. A whole grid saves in one transaction with one audit event that stores the full before and after matrix. If someone else (usually the head) saved the same grid after you opened the page, your save is refused instead of silently overwriting theirs. This delivers **B5** ACs 1–3. AC4 (lint above the grid) arrives with S2-07, and the page already has the place for it.

The grid include is also reused by the syllabus review screen (S6-02). That's why the grid is built from plain dataclasses and not straight from model objects.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/outcomes/matrix.py` | create | Cell names, the two cell validators, `fmt_weight`, `version_of` / `matrix_version`, the grid dataclasses (`GridCol`, `GridCell`, `GridRow`, `WeightGrid`), `column_totals`, `overlay_submitted` |
| `apps/outcomes/selectors.py` | modify | `MappingGrid`, `mapping_grid` |
| `apps/outcomes/services.py` | modify | `MatrixSaveResult`, `save_assessment_lo_matrix`, `save_lo_po_matrix` |
| `apps/outcomes/views.py` | modify | `mapping`, `save_assessment_lo`, `save_lo_po`, `validate_cell` |
| `apps/outcomes/urls.py` | modify | Four mapping URLs |
| `templates/includes/weight_grid.html` | create | The grid component, with a `cell` partial for HTMX |
| `apps/outcomes/templates/outcomes/mapping.html` | create | The Mapping tab |
| `static/js/polaris.js` | modify | Grid keyboard navigation, Save-button state, PO tooltips, unsaved-changes warning |
| `static/css/polaris.css` | modify | Grid sizing and origin colours |
| `apps/outcomes/tests/test_matrix.py` | create | Pure tests: parsing, validators, versions, totals |
| `apps/outcomes/tests/test_mapping_services.py` | create | Saves, audit, stale edits, rollback, cross-course cells, the Elif example |
| `apps/outcomes/tests/test_mapping_views.py` | create | Page, save, 422/409/400 answers, HTMX validation, head access |

### Steps

**1. How a grid is posted.** Each cell is an `<input>` named `<kind>-<row id>-<column id>`, for example `a_lo-12-34` (assessment 12 → LO 34) or `lo_po-34-5` (LO 34 → PO 5). The kinds are `a_lo` and `lo_po`. They contain an underscore, never a dash, so splitting on `-` always gives three parts. A whole grid is one ordinary HTML form with one hidden `version` field. There's nothing clever on the wire, so the form also works with JavaScript off.

**What a blank cell means.** Blank = no arrow, and we store **no row** (policy P2: never a 0). So saving is a diff, not "delete everything and re-insert". For every posted cell: blank and a row exists → delete it; a value and no row → create one; a different value → update it; the same value → leave the row alone. Leaving unchanged rows alone matters for the LO → PO grid. A cell that came from the syllabus or from the AI keeps its `source` and `rationale` until a human changes its value. That's what lint L007 ("AI-suggested and never confirmed") relies on.

**Only posted cells are touched.** If an LO was added in another tab after this page loaded, its cells aren't in the posted form, and the save leaves them alone instead of deleting them.

**2. Validation rules, and why they're strict.**

| Grid | Accepts | Rejects (with this message) |
|---|---|---|
| Assessment → LO | Blank (no link), or a number from 1 to 100 with at most 2 decimals. `12,5` is read as 12.5 (Turkish keyboards) | `0` "0 isn't a weight. Leave the cell blank for no link." · `0.5`, `101`, `-5` "A weight must be between 1 and 100." · `abc`, `NaN` "Enter a number, for example 40." · `12.345` "Use at most 2 decimal places." |
| LO → PO | Blank, or a whole number 1–5 | `0` "0 isn't a weight…" · `6`, `2.5`, `-1`, `abc` "Use a whole number from 1 to 5." |

`0` gets its own message because instructors coming from Bologna tables type 0 for "no contribution". In POlaris that's a blank cell, and the message says so. The 1–100 range follows decision D1. The database check (`weight > 0`) is looser on purpose: it's the last line of defence, not the user-facing rule.

Inputs are `type="text"` with `inputmode="decimal"` / `"numeric"`, not `type="number"`. A number input silently turns `abc` into an empty value, so the server would see "blank" and quietly delete a link. B5 AC2 needs `abc` to be rejected with a message.

**3. Stale-edit detection.** The page carries a **version** for each grid: a short SHA-256 hash of that grid's current rows (`row:col:weight`, sorted). The save recomputes the hash inside the transaction, *after* locking the offering row. If it differs from the posted one, someone saved this grid since you loaded the page, and the save is refused with `ValidationError(code="stale")`. The view answers **409 Conflict** and shows your typed values with the warning (B5 AC3).

Why a hash of the rows and not "the id of the last audit event" (the idea in spec Part 11's Sprint 2 notes): the hash changes exactly when the grid's content changes. It doesn't change when someone edits an LO's wording, which shouldn't block your weight save. It also doesn't depend on every writer remembering to audit. It costs one small query that the save does anyway.

Why lock the offering row first: without the lock, two saves could both pass the version check at the same moment and then both write. With `select_for_update` on the offering, the second save waits until the first commits, then sees the new version and is refused.

**4. `apps/outcomes/matrix.py`.** Everything here is pure except `matrix_version`, which does one read. The grid dataclasses are what the template renders. Django templates can't look up `weights[(row, col)]`, so the selector builds rows of cells in display order and the template only loops.

```python
# apps/outcomes/matrix.py
"""The two weight grids (B5): cell names, validation, versions, and the plain
dataclasses that templates/includes/weight_grid.html renders. No database writes."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

A_LO = "a_lo"      # assessment → LO, percent 1–100 (policy P1, decision D1)
LO_PO = "lo_po"    # LO → PO, whole number 1–5 (policy P2)
KINDS = (A_LO, LO_PO)

ONE = Decimal("1")
HUNDRED = Decimal("100")
CENT = Decimal("0.01")

ZERO_MESSAGE = "0 isn't a weight. Leave the cell blank for no link."
LO_PO_MESSAGE = "Use a whole number from 1 to 5."


# ---------- names and posted cells ----------

@dataclass(frozen=True)
class Cell:
    """One posted cell. `raw` is what the user typed, stripped; "" means no link."""
    row_id: int
    col_id: int
    raw: str


def cell_name(kind: str, row, col) -> str:
    return f"{kind}-{row}-{col}"


def parse_cell_name(name: str) -> tuple[str, int, int] | None:
    """'a_lo-12-34' -> ('a_lo', 12, 34). Anything else -> None."""
    parts = name.split("-")
    if len(parts) != 3 or parts[0] not in KINDS:
        return None
    kind, row, col = parts
    if not (row.isascii() and row.isdigit() and col.isascii() and col.isdigit()):
        return None
    return kind, int(row), int(col)


def parse_matrix_post(post, kind: str) -> list[Cell]:
    """Every cell of one grid from request.POST. Other fields (version, csrf) are ignored."""
    cells = []
    for name in post:
        parsed = parse_cell_name(name)
        if parsed is not None and parsed[0] == kind:
            cells.append(Cell(row_id=parsed[1], col_id=parsed[2], raw=post.get(name, "").strip()))
    return cells


# ---------- validation ----------

def validate_assessment_lo_cell(raw: str | None) -> Decimal | None:
    """Blank -> None (no link). Otherwise a Decimal in [1, 100] with at most 2 decimals."""
    text = (raw or "").strip().replace(",", ".")
    if text == "":
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValidationError("Enter a number, for example 40.", code="not_a_number") from None
    if not value.is_finite():
        raise ValidationError("Enter a number, for example 40.", code="not_a_number")
    if value == 0:
        raise ValidationError(ZERO_MESSAGE, code="zero")
    if value < ONE or value > HUNDRED:            # checked before quantize: 1e400 can't be quantized
        raise ValidationError("A weight must be between 1 and 100.", code="range")
    if value != value.quantize(CENT):
        raise ValidationError("Use at most 2 decimal places.", code="precision")
    return value


def validate_lo_po_cell(raw: str | None) -> int | None:
    """Blank -> None (no link). Otherwise an int in [1, 5]."""
    text = (raw or "").strip()
    if text == "":
        return None
    if not (text.isascii() and text.isdigit()):   # rejects "2.5", "-1", "abc", "٣"
        raise ValidationError(LO_PO_MESSAGE, code="not_integer")
    value = int(text)
    if value == 0:
        raise ValidationError(ZERO_MESSAGE, code="zero")
    if value > 5:
        raise ValidationError(LO_PO_MESSAGE, code="range")
    return value


VALIDATORS = {A_LO: validate_assessment_lo_cell, LO_PO: validate_lo_po_cell}


def fmt_weight(value) -> str:
    """Decimal('60.00') -> '60', Decimal('12.50') -> '12.5', 4 -> '4'."""
    return f"{Decimal(value).normalize():f}"


# ---------- versions (stale-edit detection) ----------

def version_of(triples) -> str:
    """Hash of (row_id, col_id, weight) triples. Order and number format don't matter:
    60 and 60.00 give the same version."""
    payload = ";".join(sorted(f"{r}:{c}:{fmt_weight(w)}" for r, c, w in triples))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def matrix_version(offering, kind: str) -> str:
    """The current version of one grid, read from the database."""
    from .models import AssessmentLOWeight, LOPOWeight  # local: keep this module importable without apps

    if kind == A_LO:
        rows = AssessmentLOWeight.objects.filter(assessment__offering=offering).values_list(
            "assessment_id", "learning_outcome_id", "weight")
    elif kind == LO_PO:
        rows = LOPOWeight.objects.filter(learning_outcome__offering=offering).values_list(
            "learning_outcome_id", "program_outcome_id", "weight")
    else:
        raise ValueError(f"unknown grid kind {kind!r}")
    return version_of(rows)


# ---------- what the template renders ----------

#: LOPOWeight.source -> the cell's colour class. Manual and cloned cells are plain.
SOURCE_TO_ORIGIN = {"syllabus": "document", "ai_suggested": "ai_suggested"}


@dataclass
class GridCol:
    label: str             # "LO 2", "PO 3"
    tooltip: str = ""      # full description, shown on hover and keyboard focus


@dataclass
class GridCell:
    name: str              # the <input name>, unique in the form
    value: str             # what the input shows ("" = no link)
    label: str             # accessible name, e.g. "Midterm I to LO 2"
    error: str = ""
    origin: str = ""       # "", "document", "derived", "ai_suggested" (colour + text mark); "manual" = plain
    rationale: str = ""    # one sentence, shown on hover for AI-suggested cells


@dataclass
class GridRow:
    label: str
    cells: list[GridCell]
    tooltip: str = ""


@dataclass
class WeightGrid:
    kind: str                                   # A_LO or LO_PO
    caption: str
    cols: list[GridCol]
    rows: list[GridRow]
    footer: list[str] | None = None             # per-column totals
    footer_label: str = "Total"
    version: str = ""                           # posted back as the hidden "version" field
    validate_url: str = ""                      # set -> cells validate live over HTMX
    empty_message: str = ""
    form_errors: list[str] = field(default_factory=list)

    def all_cells(self):
        for row in self.rows:
            yield from row.cells

    @property
    def has_errors(self) -> bool:
        return bool(self.form_errors) or any(cell.error for cell in self.all_cells())

    @property
    def has_origins(self) -> bool:
        return any(cell.origin for cell in self.all_cells())


def column_totals(grid: WeightGrid) -> list[str]:
    """Sum of the valid values in each column. Invalid or blank cells count as nothing."""
    totals = [Decimal("0")] * len(grid.cols)
    validator = VALIDATORS[grid.kind]
    for row in grid.rows:
        for i, cell in enumerate(row.cells):
            try:
                value = validator(cell.value)
            except ValidationError:
                continue
            if value is not None:
                totals[i] += Decimal(value)
    return [fmt_weight(t) for t in totals]


def overlay_submitted(grid: WeightGrid, cells: list[Cell], errors: dict[str, str] | None = None) -> WeightGrid:
    """Show what the user typed (and the errors) instead of the saved values, so a refused
    save never throws their work away. Mutates and returns `grid`. Errors for cells that
    aren't on the page, and the "__all__" key, go to grid.form_errors."""
    remaining = dict(errors or {})
    typed = {cell_name(grid.kind, c.row_id, c.col_id): c.raw for c in cells}
    for cell in grid.all_cells():
        if cell.name in typed and typed[cell.name] != cell.value:
            cell.value = typed[cell.name]
            cell.origin = ""            # a human changed it: no longer "from the document" / "AI"
            cell.rationale = ""
        cell.error = remaining.pop(cell.name, "")
    grid.form_errors.extend(remaining.values())
    grid.footer = column_totals(grid)
    return grid
```

**5. The selector.** `mapping_grid` reads everything for both grids in six small queries: assessments, LOs, the active PO set, its POs, and the two weight tables. It returns the raw facts (other pages, such as the course report in S7-03, use `.a_lo` and `.lo_po` directly) and the two ready-to-render `WeightGrid`s.

The PO columns are the **active** PO set of the course's program (spec §5.3). If the program has no active set, which only happens in a half-configured test database, the LO → PO grid shows an explanation instead of crashing.

```python
# apps/outcomes/selectors.py  (add)
from dataclasses import dataclass  # already imported by S2-04

from apps.catalog.models import ProgramOutcomeSet
from apps.catalog.selectors import active_po_set

from .matrix import (
    A_LO, LO_PO, SOURCE_TO_ORIGIN, GridCell, GridCol, GridRow, WeightGrid, cell_name,
    column_totals, fmt_weight, version_of,
)
from .models import AssessmentLOWeight, LOPOWeight


@dataclass
class MappingGrid:
    assessments: list            # Assessment objects, display order
    los: list                    # LearningOutcome objects, by number
    pos: list                    # ProgramOutcome objects of the active set, by number
    a_lo: dict                   # (assessment_id, lo_id) -> Decimal weight
    lo_po: dict                  # (lo_id, po_id) -> int weight (every LO→PO row, active set or not)
    a_lo_grid: WeightGrid
    lo_po_grid: WeightGrid

    def grid(self, kind: str) -> WeightGrid:
        return self.a_lo_grid if kind == A_LO else self.lo_po_grid


def mapping_grid(offering, *, validate_url: str = "") -> MappingGrid:
    assessments = list(offering.assessments.all())
    los = list(offering.learning_outcomes.all())
    try:
        pos = list(active_po_set(offering.course.program).outcomes.all())
    except ProgramOutcomeSet.DoesNotExist:
        pos = []
    a_lo_rows = list(AssessmentLOWeight.objects.filter(assessment__offering=offering))
    lo_po_rows = list(LOPOWeight.objects.filter(learning_outcome__offering=offering))
    a_lo = {(w.assessment_id, w.learning_outcome_id): w.weight for w in a_lo_rows}
    lo_po = {(w.learning_outcome_id, w.program_outcome_id): w.weight for w in lo_po_rows}
    lo_po_meta = {(w.learning_outcome_id, w.program_outcome_id): w for w in lo_po_rows}

    a_lo_grid = WeightGrid(
        kind=A_LO,
        caption="Assessment → LO weights (%). Blank = this assessment doesn't measure that LO.",
        cols=[GridCol(f"LO {lo.number}", lo.description) for lo in los],
        rows=[
            GridRow(
                label=a.name,
                tooltip=f"{a.get_kind_display()}, out of {fmt_weight(a.max_score)}",
                cells=[
                    GridCell(
                        name=cell_name(A_LO, a.pk, lo.pk),
                        value=fmt_weight(a_lo[(a.pk, lo.pk)]) if (a.pk, lo.pk) in a_lo else "",
                        label=f"{a.name} to LO {lo.number}",
                    )
                    for lo in los
                ],
            )
            for a in assessments
        ],
        footer_label="Total %",
        version=version_of((a_id, lo_id, w) for (a_id, lo_id), w in a_lo.items()),
        validate_url=validate_url,
        empty_message="Add assessments and learning outcomes on the Setup tab first.",
    )

    def lo_po_cell(lo, po):
        row = lo_po_meta.get((lo.pk, po.pk))
        return GridCell(
            name=cell_name(LO_PO, lo.pk, po.pk),
            value=str(row.weight) if row else "",
            label=f"LO {lo.number} to PO {po.number}",
            origin=SOURCE_TO_ORIGIN.get(row.source, "") if row else "",
            rationale=row.rationale if row else "",
        )

    lo_po_grid = WeightGrid(
        kind=LO_PO,
        caption="LO → PO weights (1–5). Blank = no contribution.",
        cols=[GridCol(f"PO {po.number}", f"PO {po.number} · {po.short_name}: {po.description}") for po in pos],
        rows=[GridRow(label=f"LO {lo.number}", tooltip=lo.description,
                      cells=[lo_po_cell(lo, po) for po in pos]) for lo in los],
        footer_label="PO coverage",
        version=version_of((lo_id, po_id, w) for (lo_id, po_id), w in lo_po.items()),
        validate_url=validate_url,
        empty_message=("Add learning outcomes on the Setup tab first." if pos else
                       "This program has no active list of program outcomes. Ask the department head."),
    )
    for grid in (a_lo_grid, lo_po_grid):
        grid.footer = column_totals(grid)
    return MappingGrid(assessments=assessments, los=los, pos=pos, a_lo=a_lo, lo_po=lo_po,
                       a_lo_grid=a_lo_grid, lo_po_grid=lo_po_grid)
```

S2-02 wrote `active_po_set(program)` with `.get(...)`, so it raises `ProgramOutcomeSet.DoesNotExist` when there's no active set. That's why the `try` is there.

**6. The two save services.** Same shape for both, in this order inside one transaction:

1. Lock the offering row (`_lock_offering` from S2-04).
2. `ensure_term_open`.
3. Version check → `ValidationError(code="stale")`.
4. Validate every posted cell. A cell whose row or column isn't part of *this* course (a tampered form, or an LO deleted in another tab) is an error, not something to skip silently (spec §5.3 rule 1 and 2). Any error → `ValidationError({cell_name: message, …})`, and **nothing** is written.
5. Diff and write (create, update, delete).
6. One `AuditEvent` on the offering with the full before and after matrix, only if something changed. A save that changed nothing doesn't clutter the history.

Spec §5.3's rule that an LO→PO weight must point at the **active** PO set is the column check in step 4: the allowed columns are exactly the active set's PO ids.

```python
# apps/outcomes/services.py  (add)
from dataclasses import dataclass

from .matrix import (
    A_LO, LO_PO, Cell, cell_name, fmt_weight, matrix_version, validate_assessment_lo_cell,
    validate_lo_po_cell,
)
from .models import AssessmentLOWeight, LOPOWeight

STALE_MESSAGE = ("This mapping changed since you opened it. Someone else saved it in the meantime. "
                 "Reload to see their version, then make your change again.")
FOREIGN_CELL_MESSAGE = "This cell isn't part of this course's mapping any more. Reload the page."


@dataclass(frozen=True)
class MatrixSaveResult:
    created: int
    updated: int
    deleted: int

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated or self.deleted)


def _check_version(offering, kind: str, expected: str) -> None:
    if matrix_version(offering, kind) != expected:
        raise ValidationError(STALE_MESSAGE, code="stale")


def _validated_cells(kind, cells: list[Cell], row_ids: set[int], col_ids: set[int], validator):
    """-> (wanted {(row, col): value}, posted {(row, col)}). Raises one ValidationError
    listing every bad cell, so the user sees all problems at once."""
    errors: dict[str, str] = {}
    wanted: dict[tuple[int, int], object] = {}
    posted: set[tuple[int, int]] = set()
    for c in cells:
        name = cell_name(kind, c.row_id, c.col_id)
        if c.row_id not in row_ids or c.col_id not in col_ids:
            errors[name] = FOREIGN_CELL_MESSAGE
            continue
        try:
            value = validator(c.raw)
        except ValidationError as exc:
            errors[name] = exc.messages[0]
            continue
        posted.add((c.row_id, c.col_id))
        if value is not None:
            wanted[(c.row_id, c.col_id)] = value
    if errors:
        raise ValidationError(errors)
    return wanted, posted


def _as_audit(rows) -> dict[str, str]:
    """{(row, col): weight} -> {"row:col": "60"} (JSON-safe, stable formatting)."""
    return {f"{r}:{c}": fmt_weight(w) for (r, c), w in sorted(rows.items())}


def save_assessment_lo_matrix(user, offering, cells: list[Cell], *, expected_version: str) -> MatrixSaveResult:
    with transaction.atomic():
        offering = _lock_offering(offering)
        ensure_term_open(offering)
        _check_version(offering, A_LO, expected_version)
        wanted, posted = _validated_cells(
            A_LO, cells,
            row_ids=set(offering.assessments.values_list("id", flat=True)),
            col_ids=set(offering.learning_outcomes.values_list("id", flat=True)),
            validator=validate_assessment_lo_cell,
        )
        existing = {(w.assessment_id, w.learning_outcome_id): w
                    for w in AssessmentLOWeight.objects.filter(assessment__offering=offering)}
        before = _as_audit({k: w.weight for k, w in existing.items()})

        to_create, to_update, to_delete = [], [], []
        for key in posted:
            current, value = existing.get(key), wanted.get(key)
            if value is None:
                if current is not None:
                    to_delete.append(current.pk)
            elif current is None:
                to_create.append(AssessmentLOWeight(assessment_id=key[0], learning_outcome_id=key[1],
                                                    weight=value))
            elif current.weight != value:          # Decimal: 60.00 == 60, so no false updates
                current.weight = value
                to_update.append(current)

        AssessmentLOWeight.objects.filter(pk__in=to_delete).delete()
        AssessmentLOWeight.objects.bulk_create(to_create)
        AssessmentLOWeight.objects.bulk_update(to_update, ["weight"])
        result = MatrixSaveResult(len(to_create), len(to_update), len(to_delete))

        if result.changed:
            after = _as_audit({(w.assessment_id, w.learning_outcome_id): w.weight
                               for w in AssessmentLOWeight.objects.filter(assessment__offering=offering)})
            record(user, "assessment_lo.update", offering,
                   before={"cells": before}, after={"cells": after}, offering=offering)
        return result


def save_lo_po_matrix(user, offering, cells: list[Cell], *, expected_version: str) -> MatrixSaveResult:
    """Like the assessment grid, plus provenance: a cell whose value a human changes becomes
    source=MANUAL with no rationale. Unchanged cells keep their source (lint L007 needs that)."""
    from apps.catalog.selectors import active_po_set

    with transaction.atomic():
        offering = _lock_offering(offering)
        ensure_term_open(offering)
        _check_version(offering, LO_PO, expected_version)
        po_ids = set(active_po_set(offering.course.program).outcomes.values_list("id", flat=True))
        wanted, posted = _validated_cells(
            LO_PO, cells,
            row_ids=set(offering.learning_outcomes.values_list("id", flat=True)),
            col_ids=po_ids,
            validator=validate_lo_po_cell,
        )
        existing = {(w.learning_outcome_id, w.program_outcome_id): w
                    for w in LOPOWeight.objects.filter(learning_outcome__offering=offering)}
        before = _as_audit({k: w.weight for k, w in existing.items()})

        to_create, to_update, to_delete = [], [], []
        for key in posted:
            current, value = existing.get(key), wanted.get(key)
            if value is None:
                if current is not None:
                    to_delete.append(current.pk)
            elif current is None:
                to_create.append(LOPOWeight(learning_outcome_id=key[0], program_outcome_id=key[1],
                                            weight=value, source=Source.MANUAL))
            elif current.weight != value:
                current.weight, current.source, current.rationale = value, Source.MANUAL, ""
                to_update.append(current)

        LOPOWeight.objects.filter(pk__in=to_delete).delete()
        LOPOWeight.objects.bulk_create(to_create)
        LOPOWeight.objects.bulk_update(to_update, ["weight", "source", "rationale"])
        result = MatrixSaveResult(len(to_create), len(to_update), len(to_delete))

        if result.changed:
            after = _as_audit({(w.learning_outcome_id, w.program_outcome_id): w.weight
                               for w in LOPOWeight.objects.filter(learning_outcome__offering=offering)})
            record(user, "lo_po.update", offering,
                   before={"cells": before}, after={"cells": after}, offering=offering)
        return result
```

Merge the imports into the top of `services.py`. The audit action names `assessment_lo.update` and `lo_po.update` follow the `entity.verb` pattern in spec §5.2, and the audit viewer (S7-05) filters on them. Spec §4.5 reserves a T2.3 hook here: when snapshots exist, both saves end with `transaction.on_commit(lambda: refresh_scores.delay(offering.pk))`. Don't add it now, since the task doesn't exist yet.

`accept_suggestions` (code map) is written by S6-04 together with its button. Nothing in Sprint 2 creates AI cells.

**7. Views and URLs.** Four views:

- `mapping` (GET): both grids plus, after S2-07, the lint list.
- `save_assessment_lo` / `save_lo_po` (POST): call the service. Success → redirect to the grid's anchor with a message. Bad cells → **422**, and the same page shows the typed values with red cells. Stale → **409** with the warning. A POST without a `version` field isn't from our page → **400**.
- `validate_cell` (POST, HTMX): validates one cell and returns that cell's `<td>`. It never writes and reads nothing from the database. The save re-validates everything anyway. This view only exists so the red cell appears while you're still looking at it.

The status codes matter for tests and for HTMX. HTMX doesn't swap 4xx responses by default, and the full-page form post shows the page body whatever the status is.

```python
# apps/outcomes/views.py  (add)
from django.http import HttpResponseBadRequest

from .matrix import A_LO, LO_PO, VALIDATORS, GridCell, WeightGrid, overlay_submitted, parse_cell_name, parse_matrix_post
from .selectors import mapping_grid

GRID_LABEL = {A_LO: "assessment → LO", LO_PO: "LO → PO"}
GRID_ANCHOR = {A_LO: "a-lo", LO_PO: "lo-po"}


def _cell_errors(exc: ValidationError) -> dict[str, str]:
    if hasattr(exc, "error_dict"):
        return {name: messages_[0] for name, messages_ in exc.message_dict.items()}
    return {"__all__": " ".join(exc.messages)}


def _mapping_page(request, offering, perms_for, *, failed=None, status=200):
    """The Mapping tab. `failed` = (kind, cells, posted_version, exc) after a refused save."""
    validate_url = reverse("outcomes:validate_cell", kwargs={"offering_id": offering.pk})
    mapping = mapping_grid(offering, validate_url=validate_url)
    stale_kind = None
    if failed is not None:
        kind, cells, posted_version, exc = failed
        grid = mapping.grid(kind)
        if getattr(exc, "code", None) == "stale":
            stale_kind = kind
            overlay_submitted(grid, cells)
            grid.version = posted_version      # keep the old version: re-submitting stays refused until reload
        else:
            overlay_submitted(grid, cells, _cell_errors(exc))
    return render(request, "outcomes/mapping.html", {
        "offering": offering,
        "perms_for": perms_for,
        "tabs": offering_tabs(offering, "outcomes:mapping"),
        "mapping": mapping,
        "stale_label": GRID_LABEL.get(stale_kind, ""),
    }, status=status)


@login_required
@require_offering_access()
def mapping(request, offering, perms_for):
    return _mapping_page(request, offering, perms_for)


def _save_grid(request, offering, perms_for, kind):
    if "version" not in request.POST:
        return HttpResponseBadRequest("This form is missing its version. Reload the page.")
    cells = parse_matrix_post(request.POST, kind)
    posted_version = request.POST["version"]
    save = services.save_assessment_lo_matrix if kind == A_LO else services.save_lo_po_matrix
    try:
        result = save(request.user, offering, cells, expected_version=posted_version)
    except ValidationError as exc:
        code = 409 if getattr(exc, "code", None) == "stale" else 422
        return _mapping_page(request, offering, perms_for,
                             failed=(kind, cells, posted_version, exc), status=code)
    if result.changed:
        messages.success(request, f"Saved the {GRID_LABEL[kind]} weights.")
    else:
        messages.info(request, "Nothing changed.")
    return redirect(reverse("outcomes:mapping", kwargs={"offering_id": offering.pk}) + f"#{GRID_ANCHOR[kind]}")


@login_required
@require_offering_access(edit=True)
@require_POST
def save_assessment_lo(request, offering, perms_for):
    return _save_grid(request, offering, perms_for, A_LO)


@login_required
@require_offering_access(edit=True)
@require_POST
def save_lo_po(request, offering, perms_for):
    return _save_grid(request, offering, perms_for, LO_PO)


@login_required
@require_offering_access(edit=True)
@require_POST
def validate_cell(request, offering, perms_for):
    """HTMX: check one cell as the user leaves it. Never writes, never reads the database."""
    name = request.POST.get("name", "")
    parsed = parse_cell_name(name)
    if parsed is None or parsed[0] != request.POST.get("kind"):
        return HttpResponseBadRequest("Unknown cell")
    kind = parsed[0]
    raw = request.POST.get(name, "").strip()
    try:
        VALIDATORS[kind](raw)
        error = ""
    except ValidationError as exc:
        error = exc.messages[0]
    cell = GridCell(name=name, value=raw, label=request.POST.get("label", "")[:200], error=error)
    grid = WeightGrid(kind=kind, caption="", cols=[], rows=[], validate_url=request.path)
    return render(request, "includes/weight_grid.html#cell", {"cell": cell, "grid": grid, "editable": True})
```

(`messages_` has a trailing underscore so it doesn't shadow `django.contrib.messages`.)

```python
# apps/outcomes/urls.py  (add to urlpatterns)
    path(O + "mapping/", views.mapping, name="mapping"),
    path(O + "mapping/assessment-lo/", views.save_assessment_lo, name="save_assessment_lo"),
    path(O + "mapping/lo-po/", views.save_lo_po, name="save_lo_po"),
    path(O + "mapping/validate/", views.validate_cell, name="validate_cell"),
```

**8. The grid include.** One file for both grids and for the syllabus review screen later. Parameters: `grid` (a `WeightGrid`) and `editable` (bool). The `cell` partial is defined once at the top and used in the loop with `{% partial cell %}`. `validate_cell` renders the same partial alone as `"includes/weight_grid.html#cell"`, so a re-validated cell is byte-for-byte what the full page draws. Spec Part 11 suggests `outcomes/mapping.html#cell`. We put the partial in the include instead, because the review screen (S6-02) uses the include without `mapping.html`.

How the live check works: `hx-post` sends the input's value plus `hx-vals` (which grid, which cell, its accessible label) when the value changes. `hx-target="closest td"` with `hx-swap="outerHTML"` replaces the whole `<td>` with the server's version. A read-only grid (closed term, or a viewer who can't edit) gets `disabled` inputs and no HTMX attributes.

Colour is never the only signal (spec §8.2). A coloured cell also shows a tiny text mark (`doc`, `calc`, `AI`) and has visually hidden text for screen readers.

```django
{# templates/includes/weight_grid.html — params: grid (WeightGrid), editable (bool) #}
{% partialdef cell %}
<td class="pl-cell{% if cell.origin and cell.origin != 'manual' %} pl-cell--{{ cell.origin }}{% endif %}"{% if cell.rationale %} title="{{ cell.rationale }}"{% endif %}>
  <input type="text" name="{{ cell.name }}" value="{{ cell.value }}" autocomplete="off"
         inputmode="{% if grid.kind == 'lo_po' %}numeric{% else %}decimal{% endif %}"
         class="form-control form-control-sm text-center pl-cell__input{% if cell.error %} is-invalid{% endif %}"
         aria-label="{{ cell.label }}"
         {% if cell.error %}aria-invalid="true" aria-describedby="{{ cell.name }}-err"{% endif %}
         {% if not editable %}disabled
         {% elif grid.validate_url %}hx-post="{{ grid.validate_url }}" hx-trigger="change" hx-target="closest td" hx-swap="outerHTML"
         hx-vals='{"kind": "{{ grid.kind|escapejs }}", "name": "{{ cell.name|escapejs }}", "label": "{{ cell.label|escapejs }}"}'{% endif %}>
  {% if cell.origin == "document" %}<span class="pl-cell__mark" aria-hidden="true">doc</span><span class="visually-hidden">from the syllabus</span>
  {% elif cell.origin == "derived" %}<span class="pl-cell__mark" aria-hidden="true">calc</span><span class="visually-hidden">derived from the course weight</span>
  {% elif cell.origin == "ai_suggested" %}<span class="pl-cell__mark" aria-hidden="true">AI</span><span class="visually-hidden">suggested by AI, not yet confirmed: {{ cell.rationale }}</span>{% endif %}
  {% if cell.error %}<div id="{{ cell.name }}-err" class="invalid-feedback">{{ cell.error }}</div>{% endif %}
</td>
{% endpartialdef %}
<div class="table-responsive pl-grid-wrap">
  <table class="table table-sm align-middle pl-grid" data-grid-kind="{{ grid.kind }}">
    <caption class="text-body-secondary small">{{ grid.caption }}</caption>
    {% if grid.rows and grid.cols %}
      <thead>
        <tr>
          <th scope="col"><span class="visually-hidden">Row</span></th>
          {% for col in grid.cols %}
            <th scope="col" class="text-center text-nowrap">
              {% if col.tooltip %}<span class="pl-col-tip" tabindex="0" data-bs-toggle="tooltip" data-bs-title="{{ col.tooltip }}">{{ col.label }}</span>{% else %}{{ col.label }}{% endif %}
            </th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for row in grid.rows %}
          <tr>
            <th scope="row" class="pl-grid__rowhead"{% if row.tooltip %} title="{{ row.tooltip }}"{% endif %}>{{ row.label }}</th>
            {% for cell in row.cells %}{% partial cell %}{% endfor %}
          </tr>
        {% endfor %}
      </tbody>
      {% if grid.footer %}
        <tfoot>
          <tr>
            <th scope="row" class="small">{{ grid.footer_label }}</th>
            {% for total in grid.footer %}
              <td class="text-center pl-num small{% if total == '0' %} pl-total--zero{% endif %}">{{ total }}{% if total == '0' %}<span class="visually-hidden"> (nothing)</span>{% endif %}</td>
            {% endfor %}
          </tr>
        </tfoot>
      {% endif %}
    {% else %}
      <tbody><tr><td class="text-body-secondary">{{ grid.empty_message }}</td></tr></tbody>
    {% endif %}
  </table>
</div>
```

`escapejs` is the right filter inside `hx-vals`. It escapes quotes as `"` / `'`, which keeps both the JSON string and the single-quoted HTML attribute intact, even for an assessment named `Bob's "big" quiz`.

**9. The Mapping page.** The A→LO grid is narrow and the LO→PO grid is wide (11 PO columns), so they sit side by side only on very wide screens (`col-xxl`) and stack otherwise. Each grid is its own form with its own Save button and version. One page holding two independent forms is why the unsaved-changes warning (step 10) is per form.

```django
{# apps/outcomes/templates/outcomes/mapping.html #}
{% extends "base.html" %}
{% block title %}Mapping · {{ offering.course.code }} · POlaris{% endblock %}
{% block content %}
<div class="container-fluid py-4 px-lg-4">
  {% include "includes/offering_header.html" with offering=offering tabs=tabs perms_for=perms_for only %}

  {% if stale_label %}
    <div class="alert alert-warning" role="alert">
      <strong>This mapping changed since you opened it.</strong>
      Someone else saved the {{ stale_label }} weights after you loaded this page. Your edits are shown below
      but were <strong>not</strong> saved.
      <a class="alert-link" href="{% url 'outcomes:mapping' offering_id=offering.pk %}">Load the latest version</a>,
      then make your change again.
    </div>
  {% endif %}

  {# S2-07 puts the mapping checks (lint) here. #}

  <div class="row g-4">
    <div class="col-xxl-5">
      <section id="a-lo" aria-labelledby="a-lo-title">
        <h2 class="h5" id="a-lo-title">Assessment → LO weights</h2>
        <p class="small text-body-secondary">How much each assessment measures each learning outcome, in percent (1–100).
          They don't need to add up to 100: a score divides by the sum of its weights anyway (policy P1).</p>
        <form method="post" action="{% url 'outcomes:save_assessment_lo' offering_id=offering.pk %}" class="pl-grid-form" novalidate>
          {% csrf_token %}
          <input type="hidden" name="version" value="{{ mapping.a_lo_grid.version }}">
          {% if mapping.a_lo_grid.has_errors %}
            <div class="alert alert-danger py-2" role="alert">Nothing was saved. Fix the cells marked in red.
              {% for e in mapping.a_lo_grid.form_errors %}<br>{{ e }}{% endfor %}</div>
          {% endif %}
          {% include "includes/weight_grid.html" with grid=mapping.a_lo_grid editable=perms_for.can_edit only %}
          {% if perms_for.can_edit and mapping.a_lo_grid.rows and mapping.a_lo_grid.cols %}
            <button type="submit" class="btn btn-primary" data-pl-save>Save assessment → LO weights</button>
          {% endif %}
        </form>
      </section>
    </div>

    <div class="col-xxl-7">
      <section id="lo-po" aria-labelledby="lo-po-title">
        <h2 class="h5" id="lo-po-title">LO → PO weights</h2>
        <p class="small text-body-secondary">How strongly each learning outcome supports each program outcome:
          1 = a little, 5 = strongly, blank = not at all. Hover or focus a PO number to read its official wording.</p>
        {% if mapping.lo_po_grid.has_origins %}
          <p class="small mb-2">
            <span class="pl-legend__swatch pl-cell--ai_suggested"></span><strong>AI</strong> suggested by AI, not yet confirmed ·
            <span class="pl-legend__swatch pl-cell--document"></span><strong>doc</strong> read from the syllabus.
            Editing a cell makes it yours.
          </p>
        {% endif %}
        <form method="post" action="{% url 'outcomes:save_lo_po' offering_id=offering.pk %}" class="pl-grid-form" novalidate>
          {% csrf_token %}
          <input type="hidden" name="version" value="{{ mapping.lo_po_grid.version }}">
          {% if mapping.lo_po_grid.has_errors %}
            <div class="alert alert-danger py-2" role="alert">Nothing was saved. Fix the cells marked in red.
              {% for e in mapping.lo_po_grid.form_errors %}<br>{{ e }}{% endfor %}</div>
          {% endif %}
          {% include "includes/weight_grid.html" with grid=mapping.lo_po_grid editable=perms_for.can_edit only %}
          {% if perms_for.can_edit and mapping.lo_po_grid.rows and mapping.lo_po_grid.cols %}
            <button type="submit" class="btn btn-primary" data-pl-save>Save LO → PO weights</button>
          {% endif %}
        </form>
      </section>
    </div>
  </div>
</div>
{% endblock %}
```

**10. JavaScript.** Four small behaviours, each attached once to `document` (event delegation), so they keep working after HTMX swaps a cell.

1. **Keyboard movement.** Enter / Shift+Enter and ↓ / ↑ move between rows. ← / → move between columns when the caret is at the edge of the text. Enter would otherwise submit the form, which is the last thing you want halfway through a grid. This mirrors the grade sheet's handler from S2-06 (`input.grade-input`). The two stay separate because the grade sheet has extra rules (Escape to undo, excused cells).
2. **Save button state.** If any cell in a form is red, its Save button is disabled with a reason in its `title`. Typing into a red cell clears the red at once (the server re-checks on `change`, and the save re-checks everything). So fixing a cell and clicking Save straight away works.
3. **PO tooltips.** Bootstrap tooltips are opt-in, so we create them for every `[data-bs-toggle="tooltip"]` on load and after each swap.
4. **Unsaved changes.** Leaving the page with typed but unsaved edits asks first. Submitting a form clears its own flag, but not the other grid's: saving grid A while grid B has edits still warns, because B's edits would be lost.

```javascript
// static/js/polaris.js  (add below the existing code)
(function weightGrids() {
  "use strict";

  // ---- 1. keyboard movement ----
  function inputAt(table, rowIndex, colIndex) {
    const row = table.tBodies[0] && table.tBodies[0].rows[rowIndex];
    if (!row) return null;
    const cell = row.cells[colIndex];
    return cell ? cell.querySelector("input.pl-cell__input:not([disabled])") : null;
  }

  document.addEventListener("keydown", function (event) {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.classList.contains("pl-cell__input")) return;
    const td = input.closest("td");
    const tr = td.closest("tr");
    const table = tr.closest("table");
    const row = tr.sectionRowIndex;
    const col = td.cellIndex;
    const len = input.value.length;
    let target = null;
    switch (event.key) {
      case "Enter":
        event.preventDefault();                       // never submit the grid by accident
        target = inputAt(table, event.shiftKey ? row - 1 : row + 1, col);
        if (!target) input.blur();                     // last row: still triggers the cell check
        break;
      case "ArrowDown": target = inputAt(table, row + 1, col); break;
      case "ArrowUp": target = inputAt(table, row - 1, col); break;
      case "ArrowLeft": if (input.selectionStart === 0) target = inputAt(table, row, col - 1); break;
      case "ArrowRight": if (input.selectionEnd === len) target = inputAt(table, row, col + 1); break;
      default: return;
    }
    if (target) {
      event.preventDefault();
      target.focus();
      target.select();
    }
  });

  // ---- 2. save buttons ----
  function refreshSaveButtons() {
    document.querySelectorAll("form.pl-grid-form").forEach(function (form) {
      const invalid = form.querySelector(".pl-cell__input.is-invalid") !== null;
      form.querySelectorAll("[data-pl-save]").forEach(function (button) {
        button.disabled = invalid;
        button.title = invalid ? "Fix the cells marked in red first" : "";
      });
    });
  }

  document.addEventListener("input", function (event) {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.classList.contains("pl-cell__input")) return;
    input.classList.remove("is-invalid");
    const form = input.closest("form.pl-grid-form");
    if (form) form.dataset.dirty = "1";
    refreshSaveButtons();
  });

  // ---- 3. tooltips ----
  function initTooltips() {
    if (!window.bootstrap) return;
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
      window.bootstrap.Tooltip.getOrCreateInstance(el);
    });
  }

  document.addEventListener("htmx:afterSwap", function () {
    refreshSaveButtons();
    initTooltips();
  });

  // ---- 4. unsaved changes ----
  document.addEventListener("submit", function (event) {
    if (event.target.matches && event.target.matches("form.pl-grid-form")) {
      event.target.dataset.dirty = "";
    }
  });

  window.addEventListener("beforeunload", function (event) {
    if (document.querySelector('form.pl-grid-form[data-dirty="1"]')) {
      event.preventDefault();
      event.returnValue = "";                         // older browsers need this to show the prompt
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { refreshSaveButtons(); initTooltips(); });
  } else {
    refreshSaveButtons();
    initTooltips();
  }
})();
```

A known small gap: after you edit an AI-suggested cell, the browser drops its violet colour even if you type the same number back. The server still treats an unchanged value as unchanged and keeps it `ai_suggested`. Reloading shows the truth. It's not worth more JavaScript.

**11. CSS.** Sizes keep an 11-column LO→PO grid usable on a laptop. The origin colours use the semantic tokens from spec §8.2 and are the same ones S6-02 extends. If S6-02 merges later, it finds them already here.

```css
/* static/css/polaris.css — weight grids (S2-05) */
/* Cell backgrounds are light tints of the §8.2 semantic tokens (S1-09), so dark mode follows automatically */
:root {
  --pl-origin-document: color-mix(in srgb, var(--pl-document) 16%, transparent);
  --pl-origin-derived: color-mix(in srgb, var(--pl-derived) 16%, transparent);
  --pl-origin-ai: color-mix(in srgb, var(--pl-ai) 16%, transparent);
}

.pl-grid { width: auto; }
.pl-grid__rowhead { max-width: 14rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }
.pl-grid thead th, .pl-grid__rowhead { position: sticky; background: var(--bs-body-bg); }
.pl-grid thead th { top: 0; z-index: 2; }
.pl-grid__rowhead { left: 0; z-index: 1; }
.pl-cell { position: relative; min-width: 4.25rem; padding: .15rem !important; }
.pl-cell__input { width: 3.75rem; margin: 0 auto; font-variant-numeric: tabular-nums; padding: .15rem .25rem; }
.pl-cell__input.is-invalid { background-image: none; padding-right: .25rem; }  /* no icon: cells are too narrow */
.pl-cell .invalid-feedback { position: absolute; z-index: 3; width: 12rem; left: 0; top: 100%;
  background: var(--bs-body-bg); border: 1px solid var(--bs-danger); border-radius: .25rem; padding: .15rem .35rem; }
.pl-cell--document { background: var(--pl-origin-document); }
.pl-cell--derived { background: var(--pl-origin-derived); }
.pl-cell--ai_suggested { background: var(--pl-origin-ai); }
.pl-cell__mark { position: absolute; top: 1px; right: 3px; font-size: .625rem; line-height: 1;
  color: var(--bs-secondary-color); pointer-events: none; }
.pl-legend__swatch { display: inline-block; width: .9rem; height: .9rem; border-radius: .2rem;
  vertical-align: -2px; margin-right: .25rem; border: 1px solid var(--bs-border-color); }
.pl-col-tip { text-decoration: underline dotted; cursor: help; }
.pl-total--zero { color: var(--bs-danger-text-emphasis); }
.pl-num { font-variant-numeric: tabular-nums; }
```

### Tests

```python
# apps/outcomes/tests/test_matrix.py
"""Pure tests: no database."""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.http import QueryDict

from apps.outcomes.matrix import (
    A_LO, LO_PO, Cell, GridCell, GridCol, GridRow, WeightGrid, column_totals, fmt_weight,
    overlay_submitted, parse_cell_name, parse_matrix_post, validate_assessment_lo_cell,
    validate_lo_po_cell, version_of,
)


@pytest.mark.parametrize("raw, expected", [
    ("60", Decimal("60")), (" 40 ", Decimal("40")), ("12,5", Decimal("12.5")),
    ("1", Decimal("1")), ("100", Decimal("100")), ("33.33", Decimal("33.33")),
    ("", None), ("   ", None), (None, None),
])
def test_assessment_lo_accepts(raw, expected):
    assert validate_assessment_lo_cell(raw) == expected


@pytest.mark.parametrize("raw, message", [
    ("0", "Leave the cell blank"), ("-0", "Leave the cell blank"),
    ("0.5", "between 1 and 100"), ("101", "between 1 and 100"), ("-5", "between 1 and 100"),
    ("1e400", "between 1 and 100"),
    ("abc", "Enter a number"), ("NaN", "Enter a number"), ("Infinity", "Enter a number"),
    ("12.345", "2 decimal places"),
])
def test_assessment_lo_rejects(raw, message):
    with pytest.raises(ValidationError) as exc:
        validate_assessment_lo_cell(raw)
    assert message in exc.value.messages[0]


@pytest.mark.parametrize("raw, expected", [("1", 1), ("5", 5), (" 3 ", 3), ("", None), (None, None)])
def test_lo_po_accepts(raw, expected):
    assert validate_lo_po_cell(raw) == expected


@pytest.mark.parametrize("raw, message", [
    ("0", "Leave the cell blank"),                      # B5 AC2
    ("6", "whole number from 1 to 5"),                  # B5 AC2
    ("2.5", "whole number from 1 to 5"),                # B5 AC2
    ("abc", "whole number from 1 to 5"),                # B5 AC2
    ("-1", "whole number from 1 to 5"),
    ("٣", "whole number from 1 to 5"),                  # non-ASCII digit
])
def test_lo_po_rejects(raw, message):
    with pytest.raises(ValidationError) as exc:
        validate_lo_po_cell(raw)
    assert message in exc.value.messages[0]


def test_cell_names_round_trip():
    assert parse_cell_name("a_lo-12-34") == (A_LO, 12, 34)
    assert parse_cell_name("lo_po-3-11") == (LO_PO, 3, 11)
    for bad in ["a_lo-12", "a_lo-x-1", "zz-1-2", "a_lo-1-2-3", "lo_po--1-2", ""]:
        assert parse_cell_name(bad) is None


def test_parse_matrix_post_takes_only_its_grid():
    post = QueryDict("a_lo-1-2=60&a_lo-1-3=&lo_po-2-9=4&version=abc&csrfmiddlewaretoken=t&a_lo-x-1=5")
    cells = sorted(parse_matrix_post(post, A_LO), key=lambda c: (c.row_id, c.col_id))
    assert cells == [Cell(1, 2, "60"), Cell(1, 3, "")]
    assert parse_matrix_post(post, LO_PO) == [Cell(2, 9, "4")]


def test_fmt_weight():
    assert [fmt_weight(Decimal(x)) for x in ("60.00", "12.50", "100", "0.25")] == ["60", "12.5", "100", "0.25"]
    assert fmt_weight(4) == "4"


def test_version_ignores_order_and_number_format():
    a = version_of([(1, 2, Decimal("60.00")), (1, 3, Decimal("40"))])
    b = version_of([(1, 3, Decimal("40.0")), (1, 2, Decimal("60"))])
    assert a == b
    assert a != version_of([(1, 2, Decimal("61")), (1, 3, Decimal("40"))])
    assert version_of([]) == version_of([])


def _grid():
    return WeightGrid(
        kind=LO_PO, caption="", cols=[GridCol("PO 1"), GridCol("PO 2")],
        rows=[GridRow("LO 1", [GridCell("lo_po-1-1", "4", "LO 1 to PO 1", origin="ai_suggested", rationale="r"),
                               GridCell("lo_po-1-2", "", "LO 1 to PO 2")]),
              GridRow("LO 2", [GridCell("lo_po-2-1", "2", "LO 2 to PO 1"),
                               GridCell("lo_po-2-2", "5", "LO 2 to PO 2")])],
    )


def test_column_totals_skip_blank_and_invalid():
    grid = _grid()
    grid.rows[1].cells[1].value = "abc"
    assert column_totals(grid) == ["6", "0"]


def test_overlay_shows_typed_values_and_errors():
    grid = overlay_submitted(_grid(), [Cell(1, 1, "4"), Cell(1, 2, "9")],
                             {"lo_po-1-2": "Use a whole number from 1 to 5.", "lo_po-7-7": "Not in this course"})
    first, second = grid.rows[0].cells
    assert (first.value, first.origin) == ("4", "ai_suggested")     # unchanged keeps its origin
    assert (second.value, second.error) == ("9", "Use a whole number from 1 to 5.")
    assert grid.form_errors == ["Not in this course"]               # cell not on the page
    assert grid.has_errors


def test_overlay_drops_origin_when_a_human_changes_the_value():
    grid = overlay_submitted(_grid(), [Cell(1, 1, "3")])
    cell = grid.rows[0].cells[0]
    assert (cell.value, cell.origin, cell.rationale) == ("3", "", "")
```

```python
# apps/outcomes/tests/test_mapping_services.py
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.catalog.models import Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import (
    EnrollmentFactory, GradeFactory, LearningOutcomeFactory, OfferingFactory, ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
)
from apps.outcomes import services
from apps.outcomes.matrix import A_LO, LO_PO, Cell, matrix_version
from apps.outcomes.models import Assessment, AssessmentLOWeight, LOPOWeight, Source
from apps.scoring.engine import compute_student_profile, display
from apps.scoring.loaders import load_offering_inputs


def cells(mapping):
    return [Cell(row.pk, col.pk, raw) for (row, col), raw in mapping.items()]


def save_a_lo(course, mapping, *, version=None, user=None):
    version = matrix_version(course.offering, A_LO) if version is None else version
    return services.save_assessment_lo_matrix(user or course.teacher, course.offering, cells(mapping),
                                              expected_version=version)


def save_lo_po(course, mapping, *, version=None, user=None):
    version = matrix_version(course.offering, LO_PO) if version is None else version
    return services.save_lo_po_matrix(user or course.teacher, course.offering, cells(mapping),
                                      expected_version=version)


def a_lo_rows(course):
    return {(w.assessment_id, w.learning_outcome_id): w.weight
            for w in AssessmentLOWeight.objects.filter(assessment__offering=course.offering)}


def test_save_creates_rows_and_one_audit_event(course):
    result = save_a_lo(course, {(course.midterm, course.lo1): "60", (course.midterm, course.lo2): "40",
                                (course.project, course.lo1): ""})
    assert (result.created, result.updated, result.deleted) == (2, 0, 0)
    assert a_lo_rows(course) == {(course.midterm.pk, course.lo1.pk): Decimal("60"),
                                 (course.midterm.pk, course.lo2.pk): Decimal("40")}
    event = AuditEvent.objects.get(action="assessment_lo.update")
    assert event.offering == course.offering and event.actor == course.teacher
    assert event.before == {"cells": {}}
    assert event.after == {"cells": {f"{course.midterm.pk}:{course.lo1.pk}": "60",
                                     f"{course.midterm.pk}:{course.lo2.pk}": "40"}}


def test_blank_cell_deletes_the_row_and_unposted_cells_stay(course):
    save_a_lo(course, {(course.midterm, course.lo1): "60", (course.project, course.lo2): "100"})
    result = save_a_lo(course, {(course.midterm, course.lo1): ""})          # project→lo2 not posted
    assert result.deleted == 1
    assert a_lo_rows(course) == {(course.project.pk, course.lo2.pk): Decimal("100")}


def test_saving_the_same_values_changes_nothing(course):
    save_a_lo(course, {(course.midterm, course.lo1): "60"})
    result = save_a_lo(course, {(course.midterm, course.lo1): "60.00"})
    assert not result.changed
    assert AuditEvent.objects.filter(action="assessment_lo.update").count() == 1


@pytest.mark.parametrize("raw", ["0", "6", "2.5", "abc"])
def test_one_bad_cell_saves_nothing(course, raw):
    """B5 AC2, at service level: every error is reported, no partial save."""
    with pytest.raises(ValidationError) as exc:
        save_lo_po(course, {(course.lo1, course.po1): "4", (course.lo2, course.po2): raw})
    assert list(exc.value.message_dict) == [f"lo_po-{course.lo2.pk}-{course.po2.pk}"]
    assert not LOPOWeight.objects.exists()


def test_cell_from_another_course_is_rejected(course):
    other_lo = LearningOutcomeFactory(offering=OfferingFactory(course__program=course.program, term=course.term),
                                      number=1)
    with pytest.raises(ValidationError) as exc:
        save_a_lo(course, {(course.midterm, other_lo): "50"})
    assert "isn't part of this course" in str(exc.value)
    assert not AssessmentLOWeight.objects.exists()


def test_po_from_an_inactive_set_is_rejected(course):
    old_set = ProgramOutcomeSetFactory(program=course.program, label="2018 curriculum",
                                       effective_from_year=2018, is_active=False)
    old_po = ProgramOutcomeFactory(po_set=old_set, number=1)
    with pytest.raises(ValidationError):
        save_lo_po(course, {(course.lo1, old_po): "3"})


def test_stale_version_is_refused_and_keeps_the_other_save(course, head_user):
    """B5 AC3: the instructor opened the page, then the head saved."""
    opened_with = matrix_version(course.offering, LO_PO)
    save_lo_po(course, {(course.lo1, course.po1): "5"}, user=head_user)
    with pytest.raises(ValidationError) as exc:
        save_lo_po(course, {(course.lo1, course.po1): "2"}, version=opened_with)
    assert exc.value.code == "stale"
    assert LOPOWeight.objects.get().weight == 5


def test_a_failure_after_writing_rolls_everything_back(course, monkeypatch):
    def audit_is_down(*args, **kwargs):
        raise RuntimeError("audit table unavailable")

    monkeypatch.setattr(services, "record", audit_is_down)
    with pytest.raises(RuntimeError):
        save_a_lo(course, {(course.midterm, course.lo1): "60"})
    assert not AssessmentLOWeight.objects.exists()


def test_closed_term_refuses_the_save(course):
    course.term.status = Term.Status.CLOSED
    course.term.save()
    with pytest.raises(ValidationError):
        save_a_lo(course, {(course.midterm, course.lo1): "60"})


def test_unchanged_ai_cell_keeps_its_source_and_a_changed_one_becomes_manual(course):
    LOPOWeight.objects.create(learning_outcome=course.lo1, program_outcome=course.po1, weight=3,
                              source=Source.AI_SUGGESTED, rationale="Design choices need math")
    LOPOWeight.objects.create(learning_outcome=course.lo2, program_outcome=course.po2, weight=4,
                              source=Source.AI_SUGGESTED, rationale="Agile is problem solving")
    save_lo_po(course, {(course.lo1, course.po1): "3", (course.lo2, course.po2): "5"})
    kept = LOPOWeight.objects.get(learning_outcome=course.lo1)
    changed = LOPOWeight.objects.get(learning_outcome=course.lo2)
    assert (kept.source, kept.rationale) == (Source.AI_SUGGESTED, "Design choices need math")
    assert (changed.weight, changed.source, changed.rationale) == (5, Source.MANUAL, "")


def test_elif_example_entered_through_the_grids(course):
    """B5 AC1: the professor's slide, typed into the two grids, gives 86.0 / 82.9 / 85.0 / 82.9."""
    save_a_lo(course, {(course.midterm, course.lo1): "60", (course.midterm, course.lo2): "40",
                       (course.project, course.lo1): "40", (course.project, course.lo2): "100"})
    save_lo_po(course, {(course.lo1, course.po1): "4", (course.lo2, course.po1): "2",
                        (course.lo2, course.po2): "5"})
    elif_ = EnrollmentFactory(offering=course.offering)
    now = timezone.now()
    for assessment, mark in ((course.midterm, "90"), (course.project, "80")):
        GradeFactory(assessment=assessment, enrollment=elif_, score=Decimal(mark),
                     published_score=Decimal(mark), published_at=now)
    Assessment.objects.filter(offering=course.offering).update(published_at=now)

    profile = compute_student_profile([load_offering_inputs(course.offering)[elif_.pk]])
    o = course.offering.pk
    assert display(profile.lo_scores[(o, course.lo1.pk)].score) == "86.0"
    assert display(profile.lo_scores[(o, course.lo2.pk)].score) == "82.9"
    assert display(profile.po_scores[course.po1.pk].score) == "85.0"
    assert display(profile.po_scores[course.po2.pk].score) == "82.9"
```

These tests use a `head_user` fixture. Add it to `apps/outcomes/tests/conftest.py`:

```python
# apps/outcomes/tests/conftest.py  (add)
@pytest.fixture
def head_user(course):
    head = UserFactory(email="head@test.edu")
    MembershipFactory(user=head, program=course.program, role="head")
    return head
```

```python
# apps/outcomes/tests/test_mapping_views.py
from django.urls import reverse

from apps.catalog.models import Term
from apps.outcomes.matrix import A_LO, LO_PO, Cell, matrix_version
from apps.outcomes.models import AssessmentLOWeight, LOPOWeight
from apps.outcomes.services import save_lo_po_matrix


def url(name, course):
    return reverse(f"outcomes:{name}", kwargs={"offering_id": course.offering.pk})


def test_mapping_page_shows_both_grids_with_saved_values(teacher_client, course, django_assert_max_num_queries):
    AssessmentLOWeight.objects.create(assessment=course.midterm, learning_outcome=course.lo1, weight="60.00")
    with django_assert_max_num_queries(20):
        response = teacher_client.get(url("mapping", course))
    html = response.content.decode()
    assert response.status_code == 200
    assert f'name="a_lo-{course.midterm.pk}-{course.lo1.pk}" value="60"' in html
    assert f'name="lo_po-{course.lo1.pk}-{course.po1.pk}" value=""' in html
    assert "PO 3 · Design" in html                       # header tooltip carries the PO wording
    assert 'hx-post="' + url("validate_cell", course) in html


def test_valid_save_redirects_to_the_grid(teacher_client, course):
    response = teacher_client.post(url("save_lo_po", course), {
        "version": matrix_version(course.offering, LO_PO),
        f"lo_po-{course.lo1.pk}-{course.po1.pk}": "4",
    })
    assert response.status_code == 302
    assert response["Location"].endswith("#lo-po")
    assert LOPOWeight.objects.get().weight == 4


def test_invalid_cells_answer_422_and_keep_what_was_typed(teacher_client, course):
    """B5 AC2."""
    name = f"lo_po-{course.lo1.pk}-{course.po1.pk}"
    response = teacher_client.post(url("save_lo_po", course),
                                   {"version": matrix_version(course.offering, LO_PO), name: "6"})
    html = response.content.decode()
    assert response.status_code == 422
    assert f'name="{name}" value="6"' in html
    assert "Use a whole number from 1 to 5." in html and "Nothing was saved" in html
    assert not LOPOWeight.objects.exists()


def test_stale_save_answers_409_with_the_warning(teacher_client, course, head_user):
    """B5 AC3."""
    opened_with = matrix_version(course.offering, LO_PO)
    save_lo_po_matrix(head_user, course.offering, [Cell(course.lo1.pk, course.po1.pk, "5")],
                      expected_version=opened_with)
    response = teacher_client.post(url("save_lo_po", course), {
        "version": opened_with, f"lo_po-{course.lo1.pk}-{course.po1.pk}": "2"})
    assert response.status_code == 409
    assert "This mapping changed since you opened it" in response.content.decode()
    assert LOPOWeight.objects.get().weight == 5


def test_post_without_version_is_400(teacher_client, course):
    assert teacher_client.post(url("save_assessment_lo", course), {}).status_code == 400


def test_validate_cell_returns_a_red_cell(teacher_client, course):
    name = f"lo_po-{course.lo1.pk}-{course.po1.pk}"
    response = teacher_client.post(url("validate_cell", course),
                                   {"kind": LO_PO, "name": name, name: "7", "label": "LO 1 to PO 1"},
                                   headers={"HX-Request": "true"})
    html = response.content.decode().strip()
    assert response.status_code == 200
    assert html.startswith("<td") and "is-invalid" in html
    assert "Use a whole number from 1 to 5." in html
    assert 'aria-label="LO 1 to PO 1"' in html


def test_validate_cell_accepts_a_good_value(teacher_client, course):
    name = f"a_lo-{course.midterm.pk}-{course.lo1.pk}"
    html = teacher_client.post(url("validate_cell", course), {"kind": A_LO, "name": name, name: "12,5"},
                               headers={"HX-Request": "true"}).content.decode()
    assert "is-invalid" not in html


def test_validate_cell_refuses_a_mismatched_kind(teacher_client, course):
    name = f"a_lo-{course.midterm.pk}-{course.lo1.pk}"
    response = teacher_client.post(url("validate_cell", course), {"kind": LO_PO, "name": name, name: "3"})
    assert response.status_code == 400


def test_head_can_edit_any_course_mapping(client, course, head_user):
    """Decision D13: the head sees and can override every mapping."""
    client.force_login(head_user)
    response = client.post(url("save_assessment_lo", course), {
        "version": matrix_version(course.offering, A_LO),
        f"a_lo-{course.midterm.pk}-{course.lo1.pk}": "50",
    })
    assert response.status_code == 302


def test_closed_term_shows_a_read_only_grid(teacher_client, course):
    Term.objects.filter(pk=course.term.pk).update(status=Term.Status.CLOSED)
    html = teacher_client.get(url("mapping", course)).content.decode()
    assert "disabled" in html
    assert "data-pl-save" not in html
    assert url("validate_cell", course) not in html
```

The permission matrix rows for `outcomes:mapping`, `save_assessment_lo`, `save_lo_po` and `validate_cell` are already in `routes.py` (S2-02). The empty POST the matrix sends gets 400 from our views (no `version`, unknown cell), which the matrix accepts for POST rows. The closed-term variant gets 403 from the decorator.

### Check it works

1. `seed_demo --reset`, `runserver`, log in as Dr. Can Aydın, open CSE 311 → **Mapping**.
2. Hover over (or tab to) "PO 3" in the LO → PO header. A tooltip shows the full official wording.
3. Type `6` into an LO → PO cell and press Enter. Focus moves down, the cell turns red with "Use a whole number from 1 to 5.", and **Save LO → PO weights** is disabled with a reason on hover. Change it to `4`: the red disappears as you type, and the button is enabled.
4. Enter the Elif example (Midterm I: 60 / 40, Project: 40 / 100. LO 1 → PO 1: 4, LO 2 → PO 1: 2, LO 2 → PO 2: 5) and save both grids. The bottom row shows PO coverage 6, 5, 0, …
5. Open the Mapping tab in a **second browser** (or a private window) as the head (`head@acibadem.edu.tr`). Change one LO → PO cell and save. Back in the first window, change a different cell and save. You get the yellow "This mapping changed since you opened it" banner, your typed value is still visible, and nothing was saved. Click **Load the latest version**: the head's change is there.
6. Type in a grid and try to close the tab. The browser asks whether to leave.
7. Django admin → Audit events: one `assessment_lo.update` and one `lo_po.update` per save, each with the whole before and after matrix.
8. In DevTools → Network, leaving a cell sends one `POST …/mapping/validate/` of under 1 KB, and the response is a single `<td>`.
9. `uv run pytest apps/outcomes -q` is green, and so is the permission matrix.

### Done when

| AC (spec Part 6, B5) | Proven by |
|---|---|
| AC1 Elif example gives LO1 86.0, LO2 82.9, PO1 85.0, PO2 82.9 | `test_elif_example_entered_through_the_grids` (the results page that displays it is S3-03) |
| AC2 `0`, `6`, `2.5`, `abc` rejected with a clear message | `test_lo_po_rejects`, `test_one_bad_cell_saves_nothing`, `test_invalid_cells_answer_422_and_keep_what_was_typed` |
| AC3 "changed since you opened it" instead of overwriting | `test_stale_version_is_refused_and_keeps_the_other_save`, `test_stale_save_answers_409_with_the_warning` |
| AC4 lint re-runs after saving | S2-07 (`test_mapping_page_shows_lint`) |
| One transaction, one audit event per grid save | `test_save_creates_rows_and_one_audit_event`, `test_a_failure_after_writing_rolls_everything_back` |
| §5.3: same-offering cells, active-set POs only | `test_cell_from_another_course_is_rejected`, `test_po_from_an_inactive_set_is_rejected` |
| Head can override (D13) | `test_head_can_edit_any_course_mapping` |
| Provenance kept until a human edits (needed for L007, T1.2 AC5) | `test_unchanged_ai_cell_keeps_its_source_and_a_changed_one_becomes_manual` |

### Commits and PR

```
Add matrix cell parsing, validation and grid versions (#S2-05)
Save weight grids as a diff in one locked transaction (#S2-05)
Add Mapping tab with HTMX cell validation (#S2-05)
Refuse stale grid saves with 409 and keep the typed values (#S2-05)
Add grid keyboard navigation and unsaved-changes warning (#S2-05)
```

PR title: **Mapping tab: both weight grids with live validation (S2-05)**. This PR is close to the 400-line guideline. If it goes over, split it into "matrix.py + services + tests" and "views + templates + JS".

---

## S2-07 · Mapping lint L001–L007

**Points:** 2 · **Owner:** Person A · **Branch:** `feature/S2-07-mapping-lint` · **Depends on:** S2-05 (the Mapping tab), S2-04 (the course list's Setup column)

### Goal

A mapping can be valid cell by cell and still be broken as a whole. For example, an LO that no assessment measures can never get a score. Lint finds these problems and explains each one in a sentence, on the Mapping tab and as a badge on *My courses*. This delivers **B11** (both ACs) and B5 AC4 (lint re-runs after every save, because the save redirects back to the Mapping tab, which recomputes it).

Each rule is a **pure function** over a small snapshot of the mapping: no Django, no database, no `request`. That makes the rules trivial to test (one passing and one failing case each, B11 AC1). The syllabus wizard (S6) and the course report (S7-03) can also run them on data that isn't saved yet.

The Sprint 2 story table says L001–L006. L007 is included here because it needs nothing extra: the snapshot already carries each link's `source`. It stays silent until S6 creates AI-suggested cells.

### The rules

| Code | Severity | Fires when | Message (example) | Why it matters |
|---|---|---|---|---|
| L001 | error | An LO has no assessment → LO weight | "LO 3 isn't measured by any assessment, so its score can never be calculated." | Its LO score is always None (P12), so it never reaches any PO |
| L002 | error | An LO has no LO → PO weight | "LO 3 isn't linked to any program outcome, so it adds nothing to PO scores." | The LO is graded but invisible to the program |
| L003 | warning | An assessment feeds no LO | "Quiz 1 doesn't feed any learning outcome, so its grades are ignored by every score." | Grades entered for nothing |
| L004 | warning | At least one assessment has a course weight, and the weights don't sum to 100 | "Course weights add up to 90%, not 100%. 1 assessment has no course weight." | Usually a typo. Course weights are informational (P1), so it's a warning, not an error. With no course weights at all, nothing fires: they're optional |
| L005 | warning | One PO gets **more than** 60% of the course's total LO → PO weight | "PO 2 receives 66.7% of this course's LO → PO weight. Check that the course really focuses this much on one outcome." | Possible over-claiming. Exactly 60% does not fire |
| L006 | info | The course links to exactly one PO | "This course links to only 1 program outcome. Most courses support two or more." | Courses with no links at all are already covered by L002, so L006 stays quiet then |
| L007 | warning | Some LO → PO weights still have `source = ai_suggested` | "3 LO → PO weights suggested by AI have not been checked by a person. Edit them, or use “Accept all suggestions”." | T1.3: AI suggestions need a human decision. One issue per course, not one per cell, to avoid 30 identical lines |

Errors are listed first, then warnings, then info. Within a rule the order follows LO / PO numbers.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/outcomes/lint.py` | create | Snapshot dataclasses, the seven rules, `run_lint`, `LintCounts`, `count_issues` |
| `apps/outcomes/selectors.py` | modify | `snapshot_mappings`, `snapshot_mapping`, `lint_counts` |
| `apps/outcomes/views.py` | modify | `_mapping_page` passes `issues` |
| `apps/outcomes/templates/outcomes/mapping.html` | modify | The "Mapping checks" section |
| `templates/includes/lint_list.html` | create | Issue list, plus a `badge` partial |
| `apps/catalog/views.py`, `catalog/teaching.html` | modify | Lint badge per course |
| `static/css/polaris.css` | modify | Issue list styles |
| `apps/outcomes/tests/test_lint.py` | create | Pure rule tests |
| `apps/outcomes/tests/test_lint_display.py` | create | Snapshot query count, Mapping tab and course list display |

### Steps

**1. `apps/outcomes/lint.py`.** The snapshot holds plain values (ids, numbers, names, weights, source strings), not model objects. That keeps the module importable without Django. `AI_SUGGESTED` is a literal copy of `Source.AI_SUGGESTED`, and a test checks that they stay equal.

L005 compares with `Decimal` division, never float. The threshold is a strict `>`, so a course that splits 3/2 between two POs (exactly 60%) isn't flagged.

```python
# apps/outcomes/lint.py
"""Mapping lint (spec B11). Pure functions over a MappingSnapshot: no Django, no database.
Each rule returns a list of LintIssue. run_lint runs them all, errors first."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ERROR, WARNING, INFO = "error", "warning", "info"
SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}

AI_SUGGESTED = "ai_suggested"          # == outcomes.models.Source.AI_SUGGESTED (checked by a test)
OVERCLAIM_SHARE = Decimal("0.60")      # L005: more than this share of the course's LO→PO weight
MIN_LINKED_POS = 2                     # L006
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class LintIssue:
    code: str          # "L001"
    severity: str      # ERROR / WARNING / INFO
    message: str       # one plain sentence (or two)
    target: str = ""   # what it's about: "LO 3", "Quiz 1", "PO 2", "Assessments", "LO → PO"


@dataclass(frozen=True)
class AssessmentInfo:
    id: int
    name: str
    course_weight: Decimal | None


@dataclass(frozen=True)
class LOInfo:
    id: int
    number: int


@dataclass(frozen=True)
class LOPOLink:
    lo_id: int
    lo_number: int
    po_id: int
    po_number: int
    weight: int
    source: str


@dataclass(frozen=True)
class MappingSnapshot:
    """Everything lint needs about one offering's mapping, as plain values."""
    assessments: tuple[AssessmentInfo, ...] = ()
    los: tuple[LOInfo, ...] = ()
    assessment_lo: frozenset[tuple[int, int]] = frozenset()   # (assessment_id, lo_id) with a weight
    lo_po: tuple[LOPOLink, ...] = ()


def _fmt(value: Decimal) -> str:
    return f"{value.normalize():f}"


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


# ---------- the rules ----------

def l001_unassessed_lo(snap: MappingSnapshot) -> list[LintIssue]:
    measured = {lo_id for _, lo_id in snap.assessment_lo}
    return [
        LintIssue("L001", ERROR,
                  f"LO {lo.number} isn't measured by any assessment, so its score can never be calculated.",
                  f"LO {lo.number}")
        for lo in snap.los if lo.id not in measured
    ]


def l002_unlinked_lo(snap: MappingSnapshot) -> list[LintIssue]:
    linked = {link.lo_id for link in snap.lo_po}
    return [
        LintIssue("L002", ERROR,
                  f"LO {lo.number} isn't linked to any program outcome, so it adds nothing to PO scores.",
                  f"LO {lo.number}")
        for lo in snap.los if lo.id not in linked
    ]


def l003_unused_assessment(snap: MappingSnapshot) -> list[LintIssue]:
    used = {a_id for a_id, _ in snap.assessment_lo}
    return [
        LintIssue("L003", WARNING,
                  f"{a.name} doesn't feed any learning outcome, so its grades are ignored by every score.",
                  a.name)
        for a in snap.assessments if a.id not in used
    ]


def l004_course_weights(snap: MappingSnapshot) -> list[LintIssue]:
    weights = [a.course_weight for a in snap.assessments if a.course_weight is not None]
    if not weights:
        return []                       # course weights are optional; none at all is fine
    total = sum(weights, Decimal("0"))
    if total == HUNDRED:
        return []
    message = f"Course weights add up to {_fmt(total)}%, not 100%."
    missing = sum(1 for a in snap.assessments if a.course_weight is None)
    if missing:
        message += f" {missing} {_plural(missing, 'assessment has', 'assessments have')} no course weight."
    return [LintIssue("L004", WARNING, message, "Assessments")]


def l005_overclaimed_po(snap: MappingSnapshot) -> list[LintIssue]:
    per_po: dict[int, int] = defaultdict(int)
    number: dict[int, int] = {}
    for link in snap.lo_po:
        per_po[link.po_id] += link.weight
        number[link.po_id] = link.po_number
    total = sum(per_po.values())
    if total == 0:
        return []
    issues = []
    for po_id in sorted(per_po, key=number.__getitem__):
        share = Decimal(per_po[po_id]) / Decimal(total)
        if share > OVERCLAIM_SHARE:
            pct = _fmt((share * HUNDRED).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
            issues.append(LintIssue(
                "L005", WARNING,
                f"PO {number[po_id]} receives {pct}% of this course's LO → PO weight. "
                "Check that the course really focuses this much on one outcome.",
                f"PO {number[po_id]}",
            ))
    return issues


def l006_few_pos(snap: MappingSnapshot) -> list[LintIssue]:
    linked = {link.po_id for link in snap.lo_po}
    if not linked or len(linked) >= MIN_LINKED_POS:
        return []                       # no links at all is L002's job
    return [LintIssue("L006", INFO,
                      "This course links to only 1 program outcome. Most courses support two or more.",
                      "LO → PO")]


def l007_unconfirmed_ai(snap: MappingSnapshot) -> list[LintIssue]:
    n = sum(1 for link in snap.lo_po if link.source == AI_SUGGESTED)
    if not n:
        return []
    return [LintIssue(
        "L007", WARNING,
        f"{n} LO → PO {_plural(n, 'weight', 'weights')} suggested by AI "
        f"{_plural(n, 'has', 'have')} not been checked by a person. "
        "Edit them, or use “Accept all suggestions”.",
        "LO → PO",
    )]


RULES = (
    l001_unassessed_lo, l002_unlinked_lo, l003_unused_assessment, l004_course_weights,
    l005_overclaimed_po, l006_few_pos, l007_unconfirmed_ai,
)


def run_lint(snap: MappingSnapshot) -> list[LintIssue]:
    issues = [issue for rule in RULES for issue in rule(snap)]
    return sorted(issues, key=lambda i: (SEVERITY_ORDER[i.severity], i.code))  # stable: keeps rule order


# ---------- counts for badges ----------

@dataclass(frozen=True)
class LintCounts:
    errors: int
    warnings: int
    infos: int
    empty: bool        # the course has no LOs yet: "not set up", not "mapping OK"


def count_issues(issues: list[LintIssue], *, empty: bool = False) -> LintCounts:
    return LintCounts(
        errors=sum(1 for i in issues if i.severity == ERROR),
        warnings=sum(1 for i in issues if i.severity == WARNING),
        infos=sum(1 for i in issues if i.severity == INFO),
        empty=empty,
    )
```

**2. Building snapshots: four queries for any number of courses.** `snapshot_mappings(ids)` reads assessments, LOs and both weight tables for *all* given offerings at once, then splits the rows by offering in Python. The course list with 10 courses costs 4 queries, not 40. `snapshot_mapping(offering)` is the one-course version the Mapping tab uses.

```python
# apps/outcomes/selectors.py  (add)
from .lint import (
    AssessmentInfo, LintCounts, LOInfo, LOPOLink, MappingSnapshot, count_issues, run_lint,
)
from .models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight


def snapshot_mappings(offering_ids) -> dict[int, MappingSnapshot]:
    ids = list(offering_ids)
    parts = {i: {"assessments": [], "los": [], "a_lo": set(), "lo_po": []} for i in ids}

    for row in (Assessment.objects.filter(offering_id__in=ids)
                .order_by("offering_id", "position", "id")
                .values("id", "offering_id", "name", "course_weight")):
        parts[row["offering_id"]]["assessments"].append(
            AssessmentInfo(row["id"], row["name"], row["course_weight"]))

    for row in (LearningOutcome.objects.filter(offering_id__in=ids)
                .order_by("offering_id", "number").values("id", "offering_id", "number")):
        parts[row["offering_id"]]["los"].append(LOInfo(row["id"], row["number"]))

    for offering_id, a_id, lo_id in (AssessmentLOWeight.objects.filter(assessment__offering_id__in=ids)
                                     .values_list("assessment__offering_id", "assessment_id",
                                                  "learning_outcome_id")):
        parts[offering_id]["a_lo"].add((a_id, lo_id))

    for offering_id, lo_id, lo_number, po_id, po_number, weight, source in (
        LOPOWeight.objects.filter(learning_outcome__offering_id__in=ids)
        .order_by("learning_outcome__number", "program_outcome__number")
        .values_list("learning_outcome__offering_id", "learning_outcome_id", "learning_outcome__number",
                     "program_outcome_id", "program_outcome__number", "weight", "source")
    ):
        parts[offering_id]["lo_po"].append(LOPOLink(lo_id, lo_number, po_id, po_number, weight, source))

    return {
        i: MappingSnapshot(assessments=tuple(p["assessments"]), los=tuple(p["los"]),
                           assessment_lo=frozenset(p["a_lo"]), lo_po=tuple(p["lo_po"]))
        for i, p in parts.items()
    }


def snapshot_mapping(offering) -> MappingSnapshot:
    return snapshot_mappings([offering.pk])[offering.pk]


def lint_counts(offering_ids) -> dict[int, LintCounts]:
    """Badge numbers for many courses (4 queries in total)."""
    return {
        offering_id: count_issues(run_lint(snap), empty=not snap.los)
        for offering_id, snap in snapshot_mappings(offering_ids).items()
    }
```

**3. Show it on the Mapping tab.** `_mapping_page` adds one entry to its context:

```python
# apps/outcomes/views.py  — the end of _mapping_page after this story
    return render(request, "outcomes/mapping.html", {
        "offering": offering,
        "perms_for": perms_for,
        "tabs": offering_tabs(offering, "outcomes:mapping"),
        "mapping": mapping,
        "stale_label": GRID_LABEL.get(stale_kind, ""),
        "issues": run_lint(snapshot_mapping(offering)),      # new in S2-07
    }, status=status)
```

with `from .lint import run_lint` added, and `snapshot_mapping` added to the `from .selectors import …` line. In `mapping.html`, replace the comment `{# S2-07 puts the mapping checks (lint) here. #}` with:

```django
  <section id="lint" class="mb-4" aria-labelledby="lint-title">
    <h2 class="h6 mb-2" id="lint-title">Mapping checks</h2>
    {% include "includes/lint_list.html" with issues=issues only %}
  </section>
```

The checks always describe the **saved** mapping. After a refused (422/409) save they show the state before your edits, which is correct: nothing you typed was saved.

**4. The include.** Two parts in one file: the full list (rendered by a normal include) and a `badge` partial (not inline, so it only renders when included as `"includes/lint_list.html#badge"`). Each issue shows its severity as a word and an icon, never colour alone.

```django
{# templates/includes/lint_list.html — params: issues (list[LintIssue]). Partial "badge": counts (LintCounts) #}
{% partialdef badge %}
  {% if counts.empty %}
    <span class="badge text-bg-light border">Not set up</span>
  {% elif counts.errors %}
    <span class="badge text-bg-danger"><span aria-hidden="true">✕</span> {{ counts.errors }} error{{ counts.errors|pluralize }}</span>
  {% elif counts.warnings %}
    <span class="badge text-bg-warning"><span aria-hidden="true">⚠</span> {{ counts.warnings }} warning{{ counts.warnings|pluralize }}</span>
  {% else %}
    <span class="badge text-bg-success"><span aria-hidden="true">✓</span> Mapping OK</span>
  {% endif %}
{% endpartialdef %}
{% if issues %}
  <ul class="list-unstyled pl-lint mb-0">
    {% for issue in issues %}
      <li class="pl-lint__item pl-lint__item--{{ issue.severity }}">
        <span class="pl-lint__icon" aria-hidden="true">{% if issue.severity == "error" %}✕{% elif issue.severity == "warning" %}⚠{% else %}ℹ{% endif %}</span>
        <span class="visually-hidden">{{ issue.severity|capfirst }}:</span>
        <span class="badge text-bg-light border font-monospace">{{ issue.code }}</span>
        {{ issue.message }}
      </li>
    {% endfor %}
  </ul>
{% else %}
  <p class="text-success mb-0"><span aria-hidden="true">✓</span> No problems found in this mapping.</p>
{% endif %}
```

```css
/* static/css/polaris.css — mapping lint (S2-07) */
.pl-lint__item { display: flex; gap: .5rem; align-items: baseline; padding: .35rem .6rem;
  border-left: 3px solid transparent; border-radius: .25rem; margin-bottom: .25rem; }
.pl-lint__item--error { border-left-color: var(--bs-danger); background: var(--bs-danger-bg-subtle); }
.pl-lint__item--warning { border-left-color: var(--bs-warning); background: var(--bs-warning-bg-subtle); }
.pl-lint__item--info { border-left-color: var(--bs-info); background: var(--bs-info-bg-subtle); }
.pl-lint__icon { width: 1rem; text-align: center; flex-shrink: 0; }
```

**5. The badge on *My courses*.** One more batched selector in the `teaching` view (S2-04 already attached `o.setup`):

```python
# apps/catalog/views.py — teaching(), after the setup_statuses() lines
    from apps.outcomes.selectors import lint_counts   # local import: catalog must not import outcomes at module load

    counts = lint_counts(o.pk for o in offerings)
    for o in offerings:
        o.lint = counts[o.pk]
```

Put the import at the top of the file if `ruff` complains. It's local only so the dependency direction (outcomes uses catalog) stays obvious at a glance. In `catalog/teaching.html`, replace `{# S2-07 adds the lint badge here #}` with:

```django
{% include "includes/lint_list.html#badge" with counts=o.lint only %}
```

### Tests

```python
# apps/outcomes/tests/test_lint.py
"""Every rule has a passing case (CLEAN) and at least one failing case (B11 AC1). No database."""
from dataclasses import replace
from decimal import Decimal

import pytest

from apps.outcomes.lint import (
    AI_SUGGESTED, ERROR, INFO, RULES, WARNING, AssessmentInfo, LOInfo, LOPOLink, MappingSnapshot,
    count_issues, l001_unassessed_lo, l002_unlinked_lo, l003_unused_assessment, l004_course_weights,
    l005_overclaimed_po, l006_few_pos, l007_unconfirmed_ai, run_lint,
)
from apps.outcomes.models import Source


def link(lo_id, po_number, weight, source="manual"):
    """LO ids equal LO numbers and PO ids are 100 + PO number, to keep fixtures readable."""
    return LOPOLink(lo_id=lo_id, lo_number=lo_id, po_id=100 + po_number, po_number=po_number,
                    weight=weight, source=source)


CLEAN = MappingSnapshot(
    assessments=(AssessmentInfo(10, "Midterm I", Decimal("40")), AssessmentInfo(11, "Project", Decimal("60"))),
    los=(LOInfo(1, 1), LOInfo(2, 2)),
    assessment_lo=frozenset({(10, 1), (11, 1), (11, 2)}),
    lo_po=(link(1, 1, 3), link(1, 2, 2), link(2, 3, 3)),          # PO shares 3/8, 2/8, 3/8
)


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.__name__)
def test_every_rule_passes_a_clean_mapping(rule):
    assert rule(CLEAN) == []


def test_clean_mapping_has_no_issues_at_all():
    assert run_lint(CLEAN) == []


def test_l001_lo_without_assessment():
    issues = l001_unassessed_lo(replace(CLEAN, assessment_lo=frozenset({(10, 1), (11, 1)})))
    assert [(i.code, i.severity, i.target) for i in issues] == [("L001", ERROR, "LO 2")]
    assert "never be calculated" in issues[0].message


def test_l002_lo_without_po_link():
    issues = l002_unlinked_lo(replace(CLEAN, lo_po=(link(1, 1, 3), link(1, 2, 2))))
    assert [(i.code, i.severity, i.target) for i in issues] == [("L002", ERROR, "LO 2")]


def test_l003_assessment_feeding_nothing():
    quiz = AssessmentInfo(12, "Quiz 1", None)
    issues = l003_unused_assessment(replace(CLEAN, assessments=CLEAN.assessments + (quiz,)))
    assert [(i.code, i.severity, i.target) for i in issues] == [("L003", WARNING, "Quiz 1")]


def test_l004_course_weights_not_100():
    snap = replace(CLEAN, assessments=(AssessmentInfo(10, "Midterm I", Decimal("40")),
                                       AssessmentInfo(11, "Project", Decimal("50.00")),
                                       AssessmentInfo(12, "Quiz", None)))
    [issue] = l004_course_weights(snap)
    assert issue.message == "Course weights add up to 90%, not 100%. 1 assessment has no course weight."


def test_l004_quiet_when_no_course_weights_at_all():
    snap = replace(CLEAN, assessments=(AssessmentInfo(10, "Midterm I", None), AssessmentInfo(11, "Project", None)))
    assert l004_course_weights(snap) == []


def test_l005_boundary_60_percent_is_fine():
    assert l005_overclaimed_po(replace(CLEAN, lo_po=(link(1, 1, 3), link(2, 2, 2)))) == []


def test_l005_over_60_percent_fires():
    [issue] = l005_overclaimed_po(replace(CLEAN, lo_po=(link(1, 1, 4), link(2, 2, 2))))
    assert (issue.code, issue.severity, issue.target) == ("L005", WARNING, "PO 1")
    assert "66.7%" in issue.message


def test_l006_one_po_only():
    [issue] = l006_few_pos(replace(CLEAN, lo_po=(link(1, 4, 3), link(2, 4, 2))))
    assert (issue.code, issue.severity) == ("L006", INFO)


def test_l006_quiet_without_any_links():
    assert l006_few_pos(replace(CLEAN, lo_po=())) == []


def test_l007_unconfirmed_ai_weights():
    snap = replace(CLEAN, lo_po=(link(1, 1, 3, AI_SUGGESTED), link(1, 2, 2), link(2, 3, 3, AI_SUGGESTED)))
    [issue] = l007_unconfirmed_ai(snap)
    assert (issue.code, issue.severity) == ("L007", WARNING)
    assert issue.message.startswith("2 LO → PO weights suggested by AI have not been checked")


def test_ai_constant_matches_the_model_choice():
    assert AI_SUGGESTED == Source.AI_SUGGESTED


def test_run_lint_lists_errors_first():
    broken = MappingSnapshot(
        assessments=(AssessmentInfo(10, "Midterm I", Decimal("50")),),
        los=(LOInfo(1, 1),),
        assessment_lo=frozenset(),
        lo_po=(),
    )
    codes = [i.code for i in run_lint(broken)]
    assert codes == ["L001", "L002", "L003", "L004"]
    counts = count_issues(run_lint(broken))
    assert (counts.errors, counts.warnings, counts.infos) == (2, 2, 0)
```

```python
# apps/outcomes/tests/test_lint_display.py
from decimal import Decimal

from django.urls import reverse

from apps.core.tests.factories import OfferingFactory
from apps.outcomes.lint import LOPOLink
from apps.outcomes.models import AssessmentLOWeight, LOPOWeight, Source
from apps.outcomes.selectors import lint_counts, snapshot_mapping, snapshot_mappings


def test_snapshot_reads_the_saved_mapping(course):
    AssessmentLOWeight.objects.create(assessment=course.midterm, learning_outcome=course.lo1, weight=Decimal("60"))
    LOPOWeight.objects.create(learning_outcome=course.lo1, program_outcome=course.po2, weight=4,
                              source=Source.AI_SUGGESTED)
    snap = snapshot_mapping(course.offering)
    assert [a.name for a in snap.assessments] == ["Midterm I", "Project"]
    assert [lo.number for lo in snap.los] == [1, 2]
    assert snap.assessment_lo == frozenset({(course.midterm.pk, course.lo1.pk)})
    assert snap.lo_po == (LOPOLink(course.lo1.pk, 1, course.po2.pk, 2, 4, "ai_suggested"),)


def test_many_snapshots_cost_four_queries(course, django_assert_num_queries):
    others = [OfferingFactory(course__program=course.program, term=course.term) for _ in range(4)]
    ids = [course.offering.pk] + [o.pk for o in others]
    with django_assert_num_queries(4):
        snaps = snapshot_mappings(ids)
    assert set(snaps) == set(ids)
    assert snaps[others[0].pk].los == ()


def test_counts_mark_empty_courses(course):
    empty = OfferingFactory(course__program=course.program, term=course.term)
    counts = lint_counts([course.offering.pk, empty.pk])
    assert counts[empty.pk].empty and counts[empty.pk].errors == 0
    assert counts[course.offering.pk].errors == 4          # 2 LOs × (L001 + L002)


def test_mapping_tab_shows_the_checks(teacher_client, course):
    """B11 AC2 (Mapping tab) and B5 AC4 (checks reflect the saved mapping)."""
    html = teacher_client.get(reverse("outcomes:mapping", kwargs={"offering_id": course.offering.pk})).content.decode()
    assert "Mapping checks" in html
    assert "L001" in html and "L002" in html and "L003" in html
    assert "measured by any assessment" in html


def test_course_list_shows_a_lint_badge(teacher_client, course):
    """B11 AC2 (badge on the course list)."""
    html = teacher_client.get(reverse("catalog:teaching")).content.decode()
    assert "4 errors" in html
```

### Check it works

1. On the seeded CSE 311 offering, open **Mapping**. With a complete seed mapping you see "✓ No problems found in this mapping".
2. In the LO → PO grid, clear every cell of LO 2 and save. The redirect lands back on the tab, and an **L002** error for LO 2 is listed first.
3. On **Setup**, add an assessment "Quiz 1" with course weight 10. Back on Mapping: **L003** (Quiz 1 feeds nothing) and **L004** (weights add up to 110%).
4. Give PO 1 most of the LO → PO weight (for example all 5s on PO 1 and a single 1 elsewhere). **L005** appears with the percentage.
5. *My courses* shows a red "✕ 1 error" badge for that course and "Mapping OK" for a clean one. A brand-new empty course shows "Not set up".
6. In the Django shell, set one `LOPOWeight.source = "ai_suggested"` and reload. **L007** appears, and the cell shows the violet `AI` mark. Edit that cell's value and save: L007 disappears.
7. `uv run pytest apps/outcomes/tests/test_lint.py -q`: 20-odd tests in well under a second, since none of them touch the database.

### Done when

| AC | Proven by |
|---|---|
| B11 AC1: every rule has a passing and a failing test | `test_every_rule_passes_a_clean_mapping` (×7) + `test_l001_…` to `test_l007_…` |
| B11 AC2: lint on the Mapping tab and as a course-list badge | `test_mapping_tab_shows_the_checks`, `test_course_list_shows_a_lint_badge` |
| B5 AC4: lint re-runs after saving | Save redirects to the Mapping tab, which recomputes it (`test_valid_save_redirects_to_the_grid` + `test_mapping_tab_shows_the_checks`) |
| The course list doesn't grow queries per course | `test_many_snapshots_cost_four_queries` |
| L007 clears when a human edits the cell | `test_unchanged_ai_cell_keeps_its_source_and_a_changed_one_becomes_manual` (S2-05) + `test_l007_unconfirmed_ai_weights` |

### Commits and PR

```
Add mapping lint rules L001-L007 as pure functions (#S2-07)
Test every lint rule with a passing and a failing mapping (#S2-07)
Show mapping checks on the Mapping tab and a badge on My courses (#S2-07)
```

PR title: **Mapping lint L001–L007 on the Mapping tab and course list (S2-07)**.

---

## Code map additions

New names this chapter defines beyond spec §4.8. Add them to §4.8 in the same PR as the code.

| Module | Name | Signature | Purpose |
|---|---|---|---|
| `outcomes.services` | `MatrixSaveResult` | frozen dataclass `created, updated, deleted`; property `changed` | What a grid save did. "Nothing changed" message, no empty audit events |
| `outcomes.services` | `STALE_MESSAGE` | str | Text of the stale-grid refusal (`ValidationError` code `"stale"`) |
| `outcomes.services` | `_lock_offering` (private, shared) | `(offering) -> CourseOffering` | `SELECT … FOR UPDATE OF` the offering row (§5.6) |
| `outcomes.selectors` | `setup_context` | `(offering) -> dict` | LO rows with reorder strings, assessments, course-weight total and flags |
| `outcomes.selectors` | `DeletionImpact`, `lo_deletion_impact`, `assessment_deletion_impact` | `(lo) / (assessment) -> DeletionImpact(title, lines, blocked_reason)` | What a delete also removes (B4 AC3) |
| `outcomes.selectors` | `MappingGrid` | dataclass `assessments, los, pos, a_lo, lo_po, a_lo_grid, lo_po_grid`; method `grid(kind)` | Return type of `mapping_grid`. §4.8 says "two queries", but it needs six |
| `outcomes.selectors` | `mapping_grid` | `(offering, *, validate_url="") -> MappingGrid` | Extra keyword over §4.8 |
| `outcomes.selectors` | `snapshot_mappings`, `lint_counts` | `(offering_ids) -> dict[int, MappingSnapshot]` / `dict[int, LintCounts]` | Batched lint for course lists (4 queries total) |
| `outcomes.matrix` | `A_LO = "a_lo"`, `LO_PO = "lo_po"`, `KINDS`, `VALIDATORS` | constants | Grid kinds (also the cell-name prefixes) and their validators |
| `outcomes.matrix` | `cell_name`, `parse_cell_name` | `(kind, row, col) -> str`, `(name) -> (kind, row, col) \| None` | `<kind>-<row>-<col>` input names |
| `outcomes.matrix` | `fmt_weight` | `(value) -> str` | `60.00` → `60` |
| `outcomes.matrix` | `version_of` | `(triples) -> str` | 16-hex-char grid version; `matrix_version` uses it |
| `outcomes.matrix` | `GridCol`, `GridCell`, `GridRow`, `WeightGrid` | dataclasses (owned here; S6-02 reuses them unchanged. `GridCell.origin` ∈ `""`, `document`, `derived`, `ai_suggested`, `manual`) | What `includes/weight_grid.html` renders |
| `outcomes.matrix` | `column_totals`, `overlay_submitted` | `(grid) -> list[str]`, `(grid, cells, errors=None) -> grid` | Footer totals; re-show typed values after a refused save |
| `outcomes.matrix` | `SOURCE_TO_ORIGIN` | dict | `LOPOWeight.source` → cell colour class |
| `outcomes.lint` | `ERROR`, `WARNING`, `INFO`, `RULES`, `AssessmentInfo`, `LOInfo`, `LOPOLink`, `LintCounts`, `count_issues` | as in S2-07 step 1 | Snapshot shape and badge counts. `LOPOLink` has `lo_number`, `po_number`, `source` (what S6-04's L007 note assumes) |
| `catalog.selectors` | `SetupStatus.TOTAL`, `.done_count`; `setup_statuses` | `(offering_ids) -> dict[int, SetupStatus]` | Batched checklist (1 query) |
| `core.templatetags.polaris` | `weight` filter | as §4.8 | Code given in S2-04 step 9 in case S1-09 didn't write it |
| templates | `includes/weight_grid.html#cell` | partial | One grid cell. Rendered alone by `outcomes:validate_cell` |
| templates | `includes/lint_list.html#badge` | partial, param `counts` | Course-list badge |
| templates | `includes/setup_checklist.html` | params `status, offering, can_manage_enrollment` | §8.2's `setup_checklist` component |
| templates | `outcomes/confirm_delete.html#body` | partial | Delete confirmation for the shared modal |
| audit actions | `lo.create`, `lo.update`, `lo.delete`, `lo.reorder`, `assessment.create`, `assessment.update`, `assessment.delete`, `assessment_lo.update`, `lo_po.update` | — | For the T1.4 history filters |
