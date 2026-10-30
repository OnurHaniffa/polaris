"""Read-only queries for the catalog. Lower layers handle PO-set resolution (spec §4.8)."""

from dataclasses import dataclass

from django.db.models import Count, Q

from apps.accounts.models import ProgramMembership
from apps.accounts.permissions import can_view_offering
from apps.outcomes.models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight

from .models import CourseOffering, Enrollment, ProgramOutcomeSet


def active_po_set(program):
    """The program's active PO set. The partial unique index guarantees at most one."""
    return ProgramOutcomeSet.objects.get(program=program, is_active=True)


def po_set_ids_for_students(student_ids, program):
    """Policy P13 for many students at once: {student_id: po_set_id}.

    Candidates are the active set and the older sets it replaced. A set that is newer than
    the active one (or as new) and not active is a draft being edited: it counts only once
    the head activates it. A student gets the newest candidate whose effective_from_year is
    <= their cohort year; a cohort older than every candidate gets the oldest one; a student
    without a cohort year gets the active set."""
    sets = list(
        ProgramOutcomeSet.objects.filter(program=program)
        .order_by("-effective_from_year", "-id")
        .values_list("id", "effective_from_year", "is_active")
    )

    active = [(set_id, year) for set_id, year, is_active in sets if is_active]
    if not active:
        raise ProgramOutcomeSet.DoesNotExist(f"{program} has no active PO set")
    active_id, active_year = active[0]
    candidates = [
        (set_id, year) for set_id, year, is_active in sets if is_active or year < active_year
    ]

    cohorts = dict(
        ProgramMembership.objects.filter(
            user_id__in=student_ids,
            program=program,
            role=ProgramMembership.Role.STUDENT,
        ).values_list("user_id", "cohort_year")
    )

    def pick(cohort_year):
        if cohort_year is None:
            return active_id
        for set_id, year in candidates:
            if year <= cohort_year:
                return set_id
        return candidates[-1][0]  # older than every set: the oldest one (P13)

    return {student_id: pick(cohorts.get(student_id)) for student_id in student_ids}


def po_set_for_student(student, program):
    """The PO set one student's profile is shown against (P13)."""
    set_id = po_set_ids_for_students([student.id], program)[student.id]
    return ProgramOutcomeSet.objects.get(pk=set_id)


def offerings_for_user(user, *, term=None):
    """Return offerings visible to a head or assigned instructor."""
    if user is None or not user.is_authenticated or not user.is_active:
        return CourseOffering.objects.none()

    qs = CourseOffering.objects.select_related("course", "term")

    if not user.is_superuser:
        headed_programs = user.memberships.filter(role=ProgramMembership.Role.HEAD).values(
            "program_id"
        )

        qs = qs.filter(Q(course__program_id__in=headed_programs) | Q(instructors=user)).distinct()

    if term is not None:
        qs = qs.filter(term=term)

    return qs.order_by("-term__starts_on", "course__code", "section")


def teaching_offerings(user):
    """Return offerings assigned to an active instructor, with enrolled-student counts."""
    if user is None or not user.is_authenticated or not user.is_active:
        return CourseOffering.objects.none()

    return (
        CourseOffering.objects.filter(instructors=user)
        .select_related("course", "term")
        .annotate(
            student_count=Count(
                "enrollments",
                filter=Q(enrollments__status=Enrollment.Status.ENROLLED),
            )
        )
        .order_by("-term__starts_on", "course__code", "section")
    )


def visible_enrollments(user, offering, *, include_dropped=False):
    """Return enrollments only when the user may view the offering."""
    if not can_view_offering(user, offering):
        return Enrollment.objects.none()

    qs = Enrollment.objects.filter(offering=offering).select_related("student")

    if not include_dropped:
        qs = qs.filter(status=Enrollment.Status.ENROLLED)

    return qs.order_by("student__student_number", "student__last_name")


def offerings_visible_to(user):
    """Compatibility alias used by existing account selector tests."""
    return offerings_for_user(user)


@dataclass(frozen=True)
class SetupStatus:
    """The setup checklist numbers for one offering (spec 4.8)."""

    has_los: bool
    has_assessments: bool
    has_assessment_lo: bool
    has_lo_po: bool
    has_students: bool
    published_count: int
    assessment_count: int
    is_complete: bool


def setup_status(offering):
    """Checklist state for an offering, in 5 queries."""
    counts = Assessment.objects.filter(offering=offering).aggregate(
        total=Count("pk"),
        published=Count("pk", filter=Q(published_at__isnull=False)),
    )
    has_los = LearningOutcome.objects.filter(offering=offering).exists()
    has_assessment_lo = AssessmentLOWeight.objects.filter(assessment__offering=offering).exists()
    has_lo_po = LOPOWeight.objects.filter(learning_outcome__offering=offering).exists()
    has_students = Enrollment.objects.filter(
        offering=offering, status=Enrollment.Status.ENROLLED
    ).exists()

    has_assessments = counts["total"] > 0
    return SetupStatus(
        has_los=has_los,
        has_assessments=has_assessments,
        has_assessment_lo=has_assessment_lo,
        has_lo_po=has_lo_po,
        has_students=has_students,
        published_count=counts["published"],
        assessment_count=counts["total"],
        is_complete=has_los and has_assessments and has_assessment_lo and has_lo_po,
    )
