from decimal import Decimal

from django.utils import timezone

from apps.catalog.selectors import setup_status, setup_statuses
from apps.core.tests.factories import EnrollmentFactory, OfferingFactory
from apps.outcomes.models import Assessment, AssessmentLOWeight, LOPOWeight


def test_status_of_a_half_set_up_course(course):
    status = setup_status(course.offering)
    assert (status.has_los, status.has_assessments) == (True, True)
    assert (status.has_assessment_lo, status.has_lo_po, status.has_students) == (
        False,
        False,
        False,
    )
    assert status.done_count == 2 and not status.is_complete


def test_status_of_a_complete_course(course):
    AssessmentLOWeight.objects.create(
        assessment=course.midterm, learning_outcome=course.lo1, weight=Decimal("60")
    )
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
