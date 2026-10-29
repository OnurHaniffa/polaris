"""The database enforces these rules itself (constraints in §5.2). Each test proves one
constraint exists by trying to break it. IntegrityError = the database said no.

Each test that expects an IntegrityError wraps the failing write in transaction.atomic():
on PostgreSQL a failed statement poisons the whole transaction, and pytest-django runs
every test inside one."""

import datetime
from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction

from apps.core.tests.factories import (
    EnrollmentFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
)

pytestmark = pytest.mark.django_db


def test_only_one_active_po_set_per_program():
    program = ProgramFactory()
    ProgramOutcomeSetFactory(program=program, is_active=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        ProgramOutcomeSetFactory(program=program, is_active=True)


def test_inactive_sets_are_unlimited():
    program = ProgramFactory()
    ProgramOutcomeSetFactory(program=program, is_active=False)
    ProgramOutcomeSetFactory(program=program, is_active=False)  # no error


def test_po_number_unique_within_set():
    po_set = ProgramOutcomeSetFactory()
    ProgramOutcomeFactory(po_set=po_set, number=3)
    with pytest.raises(IntegrityError), transaction.atomic():
        ProgramOutcomeFactory(po_set=po_set, number=3)


def test_term_must_end_after_it_starts():
    with pytest.raises(IntegrityError), transaction.atomic():
        TermFactory(
            code="BAD", starts_on=datetime.date(2026, 9, 1), ends_on=datetime.date(2026, 8, 1)
        )


def test_student_enrolled_once_per_offering():
    enrollment = EnrollmentFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        EnrollmentFactory(offering=enrollment.offering, student=enrollment.student)


def test_offering_str_shows_section_only_when_not_default():
    offering = OfferingFactory(course__code="CSE 311")
    assert str(offering) == "CSE 311 · Fall 2026"
    offering.section = "2"
    assert str(offering) == "CSE 311 · Fall 2026 (section 2)"


def test_course_credits_are_decimals():
    offering = OfferingFactory()
    assert offering.course.credits == D("3.0")
