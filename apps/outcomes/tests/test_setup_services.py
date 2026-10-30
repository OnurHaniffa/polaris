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
    AssessmentLOWeight.objects.create(
        assessment=course.midterm, learning_outcome=course.lo1, weight=Decimal("60")
    )
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


@pytest.mark.parametrize("bad", ["empty", "missing_one", "duplicate"])
def test_reorder_refuses_a_stale_or_broken_list(course, bad):
    ids = {
        "empty": [],
        "missing_one": [course.lo2.pk],
        "duplicate": [course.lo1.pk, course.lo1.pk],
    }[bad]
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
        services.create_assessment(
            course.teacher,
            course.offering,
            name="Quiz",
            kind="quiz",
            max_score=Decimal("10"),
            course_weight=None,
            due_date=None,
        )
    with pytest.raises(ValidationError):
        services.delete_lo(course.teacher, course.lo1)
    assert LearningOutcome.objects.filter(offering=course.offering).count() == 2


def test_assessment_names_are_unique_ignoring_case(course):
    with pytest.raises(ValidationError) as exc:
        services.create_assessment(
            course.teacher,
            course.offering,
            name="midterm i",
            kind="midterm",
            max_score=Decimal("100"),
            course_weight=None,
            due_date=None,
        )
    assert "name" in exc.value.message_dict


def test_new_assessment_goes_last(course):
    quiz = services.create_assessment(
        course.teacher,
        course.offering,
        name="Quiz 1",
        kind="quiz",
        max_score=Decimal("20"),
        course_weight=Decimal("0"),
        due_date=None,
    )
    assert quiz.position == 3


def test_max_change_with_grades_needs_confirmation(course):
    enrollment = EnrollmentFactory(offering=course.offering)
    GradeFactory(assessment=course.midterm, enrollment=enrollment, score=Decimal("70"))
    with pytest.raises(ValidationError) as exc:
        services.update_assessment(course.teacher, course.midterm, max_score=Decimal("80"))
    assert exc.value.code == "confirm_max_change"
    with pytest.raises(ValidationError) as exc:
        services.update_assessment(
            course.teacher, course.midterm, confirm_max_change=True, max_score=Decimal("50")
        )
    assert "max_score" in exc.value.message_dict  # 70 > 50
    services.update_assessment(
        course.teacher, course.midterm, confirm_max_change=True, max_score=Decimal("80")
    )
    course.midterm.refresh_from_db()
    assert course.midterm.max_score == Decimal("80")


def test_max_change_without_grades_needs_no_confirmation(course):
    services.update_assessment(course.teacher, course.midterm, max_score=Decimal("50"))
    course.midterm.refresh_from_db()
    assert course.midterm.max_score == Decimal("50")


def test_assessment_with_published_grades_cannot_be_deleted(course):
    """B4 AC4 / spec §5.3."""
    enrollment = EnrollmentFactory(offering=course.offering)
    GradeFactory(
        assessment=course.midterm,
        enrollment=enrollment,
        score=Decimal("50"),
        published_score=Decimal("50"),
        published_at=timezone.now(),
    )
    with pytest.raises(ValidationError) as exc:
        services.delete_assessment(course.teacher, course.midterm)
    assert exc.value.code == "published"
    assert Assessment.objects.filter(pk=course.midterm.pk).exists()


def test_deleting_an_assessment_removes_its_weights_and_drafts(course):
    AssessmentLOWeight.objects.create(
        assessment=course.midterm, learning_outcome=course.lo1, weight=Decimal("60")
    )
    GradeFactory(
        assessment=course.midterm,
        enrollment=EnrollmentFactory(offering=course.offering),
        score=Decimal("50"),
    )
    midterm_id = course.midterm.pk
    services.delete_assessment(course.teacher, course.midterm)
    assert not Assessment.objects.filter(pk=midterm_id).exists()
    event = AuditEvent.objects.get(action="assessment.delete", entity_id=midterm_id)
    assert event.before["draft_grades"] == 1
