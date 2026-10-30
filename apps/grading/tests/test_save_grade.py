from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.models import Enrollment, Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import (
    AssessmentFactory,
    EnrollmentFactory,
    GradeFactory,
    OfferingFactory,
    UserFactory,
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
    assert grade.published_score is None  # draft only (D2)
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
    GradeFactory(
        assessment=assessment,
        enrollment=enrollment,
        score=Decimal("70"),
        published_score=Decimal("70"),
    )
    grade = save_grade(user, assessment, enrollment, "")
    grade.refresh_from_db()
    assert grade.score is None
    assert grade.published_score == Decimal("70")  # students still see 70 until the next publish
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
    stranger = EnrollmentFactory()  # different offering
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
