"""Read-side helpers for report pages. Each returns plain data for one template."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.http import Http404

from apps.accounts.models import ProgramMembership, User
from apps.catalog.models import (
    CourseOffering,
    Enrollment,
    Program,
    ProgramOutcome,
    ProgramOutcomeSet,
    Term,
)
from apps.catalog.selectors import po_set_for_student, setup_status
from apps.grading.models import Grade
from apps.outcomes.models import Assessment, LearningOutcome
from apps.scoring.aggregates import class_lo_summary, program_po_summary
from apps.scoring.engine import ZERO, NodeScore, compute_student_profile, display, normalise
from apps.scoring.loaders import load_offering_inputs, load_student_inputs

NO_EVIDENCE = NodeScore(score=None, coverage=ZERO)


def student_program(student: User) -> Program | None:
    membership = (
        ProgramMembership.objects.select_related("program")
        .filter(user=student, role=ProgramMembership.Role.STUDENT)
        .order_by("-cohort_year")
        .first()
    )
    return membership.program if membership else None


@dataclass(frozen=True)
class PORow:
    po: ProgramOutcome
    score: Decimal | None
    coverage: Decimal
    attained: bool | None
    course_count: int


@dataclass(frozen=True)
class CourseRow:
    offering: CourseOffering
    in_progress: bool
    superseded: bool


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
    return {
        "labels": [f"PO {r.po.number}" for r in rows],
        "names": [r.po.short_name for r in rows],
        "values": [None if r.score is None else float(display(r.score)) for r in rows],
        "states": [
            "none" if r.attained is None else ("attained" if r.attained else "below") for r in rows
        ],
        "threshold": float(threshold),
    }


def student_profile_context(student: User, *, viewer: User) -> dict:
    program = student_program(student)
    if program is None:
        return {
            "student": student,
            "program": None,
            "rows": [],
            "courses": [],
            "is_self": viewer == student,
            "has_any_score": False,
        }

    try:
        po_set = po_set_for_student(student, program)
    except ProgramOutcomeSet.DoesNotExist:
        return {
            "student": student,
            "program": program,
            "po_set": None,
            "rows": [],
            "courses": [],
            "is_self": viewer == student,
            "has_any_score": False,
        }
    pos = list(po_set.outcomes.all())
    profile = compute_student_profile(load_student_inputs(student, include_open_terms=True))
    threshold = program.attainment_threshold

    rows: list[PORow] = []
    for po in pos:
        ns = profile.po_scores.get(po.id, NO_EVIDENCE)
        offerings = {off_id for off_id, _lo, _w in profile.po_contributors.get(po.id, [])}
        rows.append(
            PORow(
                po=po,
                score=ns.score,
                coverage=ns.coverage,
                attained=None if ns.score is None else ns.score >= threshold,
                course_count=len(offerings),
            )
        )

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


@dataclass(frozen=True)
class ContributionRow:
    offering: CourseOffering
    lo: LearningOutcome
    weight: int
    lo_score: Decimal | None
    share: Decimal | None


def po_contributions(student: User, po_id: int) -> dict:
    program = student_program(student)
    if program is None:
        raise Http404
    try:
        po_set = po_set_for_student(student, program)
    except ProgramOutcomeSet.DoesNotExist as exc:
        raise Http404 from exc
    try:
        po = po_set.outcomes.get(pk=po_id)
    except ProgramOutcome.DoesNotExist as exc:
        raise Http404 from exc

    profile = compute_student_profile(load_student_inputs(student, include_open_terms=True))
    triples = profile.po_contributors.get(po.id, [])
    los = {
        lo.id: lo
        for lo in LearningOutcome.objects.filter(
            id__in={lo_id for _o, lo_id, _w in triples}
        ).select_related("offering__course", "offering__term")
    }

    present_weight = sum(
        (
            Decimal(w)
            for off, lo_id, w in triples
            if profile.lo_scores.get((off, lo_id), NO_EVIDENCE).score is not None
        ),
        ZERO,
    )
    rows = []
    for off_id, lo_id, weight in triples:
        lo_score = profile.lo_scores.get((off_id, lo_id), NO_EVIDENCE).score
        rows.append(
            ContributionRow(
                offering=los[lo_id].offering,
                lo=los[lo_id],
                weight=int(weight),
                lo_score=lo_score,
                share=None
                if lo_score is None or present_weight == ZERO
                else Decimal(weight) / present_weight,
            )
        )
    rows.sort(key=lambda r: (r.lo_score is None, -r.weight, r.offering.course.code, r.lo.number))

    ns = profile.po_scores.get(po.id, NO_EVIDENCE)
    return {
        "student": student,
        "po": po,
        "score": ns.score,
        "coverage": ns.coverage,
        "rows": rows,
        "threshold": program.attainment_threshold,
    }


@dataclass(frozen=True)
class AssessmentRow:
    assessment: Assessment
    state: str  # not_published | missing | excused | scored
    raw: Decimal | None
    normalised: Decimal | None


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
            rows.append(
                AssessmentRow(
                    a, "scored", g.published_score, normalise(g.published_score, a.max_score)
                )
            )

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
def course_results_context(offering: CourseOffering) -> dict:
    summary = class_lo_summary(offering)
    return {
        "offering": offering,
        "summary": summary,
        "status": setup_status(offering),
        "threshold": offering.course.program.attainment_threshold,
        "in_progress": offering.term.status != Term.Status.CLOSED,
    }


def department_context(program: Program, *, terms, include_open_terms: bool, cohort=None) -> dict:
    terms = list(terms)
    selected = max(terms, key=lambda t: t.starts_on) if terms else None
    summaries = program_po_summary(
        program, terms=terms, include_open_terms=include_open_terms, cohort=cohort
    )

    offerings = []
    if selected is not None:
        qs = (
            CourseOffering.objects.filter(term=selected, course__program=program)
            .select_related("course", "term")
            .prefetch_related("instructors")
            .order_by("course__code", "section")
        )
        offerings = [(o, setup_status(o)) for o in qs]

    open_terms_in_range = [t for t in terms if t.status != Term.Status.CLOSED]
    if selected is None:
        scope = "No terms yet."
    elif include_open_terms:
        scope = f"All terms up to {selected.name}, including courses still in progress."
    elif open_terms_in_range:
        names = ", ".join(t.name for t in open_terms_in_range)
        scope = (
            f"Closed terms up to {selected.name}. {names} "
            f"{'is' if len(open_terms_in_range) == 1 else 'are'} still open and not counted."
        )
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
