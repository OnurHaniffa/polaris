"""setup_status(offering): the setup checklist numbers (spec 4.8)."""

import dataclasses

import pytest
from django.utils import timezone

from apps.accounts.tests.permission_world import build_world
from apps.catalog.models import Enrollment, ProgramOutcome, ProgramOutcomeSet
from apps.catalog.selectors import SetupStatus, setup_status
from apps.outcomes.models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight


@pytest.fixture
def world(db):
    return build_world()


def test_fields_match_the_spec():
    assert [f.name for f in dataclasses.fields(SetupStatus)] == [
        "has_los",
        "has_assessments",
        "has_assessment_lo",
        "has_lo_po",
        "has_students",
        "published_count",
        "assessment_count",
        "is_complete",
    ]


def test_a_fresh_offering_with_students_is_not_set_up(world):
    status = setup_status(world.open_offering)
    assert status.has_students  # the world enrolls one student
    assert not status.has_los
    assert not status.has_assessments
    assert not status.has_assessment_lo
    assert not status.has_lo_po
    assert (status.assessment_count, status.published_count) == (0, 0)
    assert not status.is_complete


def test_status_follows_each_setup_step(world):
    offering = world.open_offering

    lo = LearningOutcome.objects.create(offering=offering, number=1, description="Design schemas")
    assert setup_status(offering).has_los
    assert not setup_status(offering).is_complete

    assessment = Assessment.objects.create(offering=offering, name="Midterm I", kind="midterm")
    status = setup_status(offering)
    assert status.has_assessments and status.assessment_count == 1
    assert not status.is_complete

    AssessmentLOWeight.objects.create(assessment=assessment, learning_outcome=lo, weight=100)
    assert setup_status(offering).has_assessment_lo
    assert not setup_status(offering).is_complete

    po_set = ProgramOutcomeSet.objects.create(program=world.program, label="test set", effective_from_year=2099, is_active=False)
    po = ProgramOutcome.objects.create(po_set=po_set, number=1, short_name="PO1", description="x")
    LOPOWeight.objects.create(learning_outcome=lo, program_outcome=po, weight=3)
    status = setup_status(offering)
    assert status.has_lo_po
    assert status.is_complete
    assert status.published_count == 0

    Assessment.objects.filter(pk=assessment.pk).update(published_at=timezone.now())
    assert setup_status(offering).published_count == 1


def test_dropped_students_do_not_count(world):
    Enrollment.objects.filter(offering=world.open_offering).update(status=Enrollment.Status.DROPPED)
    assert not setup_status(world.open_offering).has_students


def test_setup_status_uses_few_queries(world, django_assert_max_num_queries):
    with django_assert_max_num_queries(6):
        setup_status(world.open_offering)
