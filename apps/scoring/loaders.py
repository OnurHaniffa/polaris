"""Turn database rows into the engine's plain dataclasses (spec §2.4)."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import F

from apps.catalog.models import Enrollment, Term
from apps.catalog.selectors import po_set_ids_for_students
from apps.grading.models import Grade
from apps.outcomes.models import Assessment, AssessmentLOWeight, LOPOWeight

from .engine import Edge, OfferingInputs


def _counted_enrollments(student, *, include_open_terms, up_to_term):
    qs = Enrollment.objects.filter(
        student=student, status=Enrollment.Status.ENROLLED
    ).select_related("offering__course__program", "offering__term")
    if include_open_terms:
        qs = qs.exclude(offering__term__status=Term.Status.PLANNED)
    else:
        qs = qs.filter(offering__term__status=Term.Status.CLOSED)
    if up_to_term is not None:
        qs = qs.filter(offering__term__starts_on__lte=up_to_term.starts_on)

    latest = {}
    for enrollment in qs.order_by("offering__term__starts_on", "offering_id"):
        latest[enrollment.offering.course_id] = enrollment
    return list(latest.values())


def _published_grades(enrollment_ids):
    """Published scores, and the assessments each enrollment is excused from (P6).

    Only grades whose assessment belongs to the enrollment's own offering count: a grade
    pointing at another course's assessment (possible through the admin) is ignored."""
    rows = Grade.objects.filter(
        enrollment_id__in=enrollment_ids,
        assessment__published_at__isnull=False,
        assessment__offering_id=F("enrollment__offering_id"),
    ).values_list("enrollment_id", "assessment_id", "published_score", "published_is_excused")
    grades = defaultdict(dict)
    excused = defaultdict(set)
    for enrollment_id, assessment_id, score, is_excused in rows:
        if is_excused:
            excused[enrollment_id].add(assessment_id)
        elif score is not None:
            grades[enrollment_id][assessment_id] = score
    return grades, excused


def _offering_structure(offering_ids):
    max_scores = defaultdict(dict)
    for offering_id, assessment_id, max_score in Assessment.objects.filter(
        offering_id__in=offering_ids
    ).values_list("offering_id", "id", "max_score"):
        max_scores[offering_id][assessment_id] = max_score

    a_lo = defaultdict(list)
    for offering_id, assessment_id, lo_id, weight in AssessmentLOWeight.objects.filter(
        assessment__offering_id__in=offering_ids
    ).values_list("assessment__offering_id", "assessment_id", "learning_outcome_id", "weight"):
        a_lo[offering_id].append(Edge(assessment_id, lo_id, weight))

    lo_po = defaultdict(list)
    for offering_id, lo_id, po_id, po_set_id, weight in LOPOWeight.objects.filter(
        learning_outcome__offering_id__in=offering_ids
    ).values_list(
        "learning_outcome__offering_id",
        "learning_outcome_id",
        "program_outcome_id",
        "program_outcome__po_set_id",
        "weight",
    ):
        lo_po[offering_id].append((po_set_id, Edge(lo_id, po_id, Decimal(weight))))
    return max_scores, a_lo, lo_po


def _inputs(offering_id, grades, excused, max_scores, a_lo, lo_po, po_set_id):
    return OfferingInputs(
        offering_id=offering_id,
        grades=grades,
        excused=frozenset(excused),
        max_scores=max_scores[offering_id],
        assessment_lo_edges=tuple(a_lo[offering_id]),
        lo_po_edges=tuple(edge for set_id, edge in lo_po[offering_id] if set_id == po_set_id),
    )


def load_student_inputs(student, *, include_open_terms=True, up_to_term=None):
    enrollments = _counted_enrollments(
        student, include_open_terms=include_open_terms, up_to_term=up_to_term
    )
    if not enrollments:
        return []
    offering_ids = [e.offering_id for e in enrollments]
    grades, excused = _published_grades([e.id for e in enrollments])
    max_scores, a_lo, lo_po = _offering_structure(offering_ids)

    po_sets = {}
    result = []
    for e in sorted(enrollments, key=lambda e: e.offering_id):
        program = e.offering.course.program
        if program.id not in po_sets:
            po_sets[program.id] = po_set_ids_for_students([student.id], program)[student.id]
        result.append(
            _inputs(
                e.offering_id,
                grades[e.id],
                excused[e.id],
                max_scores,
                a_lo,
                lo_po,
                po_sets[program.id],
            )
        )
    return result


def load_offering_inputs(offering):
    enrollments = list(
        Enrollment.objects.filter(offering=offering, status=Enrollment.Status.ENROLLED)
    )
    if not enrollments:
        return {}
    grades, excused = _published_grades([e.id for e in enrollments])
    max_scores, a_lo, lo_po = _offering_structure([offering.id])
    program = offering.course.program

    po_set_ids = po_set_ids_for_students([e.student_id for e in enrollments], program)
    return {
        e.id: _inputs(
            offering.id,
            grades[e.id],
            excused[e.id],
            max_scores,
            a_lo,
            lo_po,
            po_set_ids[e.student_id],
        )
        for e in enrollments
    }
