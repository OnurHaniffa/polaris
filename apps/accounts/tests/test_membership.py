import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import ProgramMembership
from apps.core.tests.factories import MembershipFactory, ProgramFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_student_membership_needs_cohort():
    with pytest.raises(IntegrityError), transaction.atomic():
        MembershipFactory(role=ProgramMembership.Role.STUDENT, cohort_year=None)


def test_instructor_membership_needs_no_cohort():
    m = MembershipFactory(role=ProgramMembership.Role.INSTRUCTOR)
    assert m.cohort_year is None


def test_one_person_can_be_instructor_and_head():
    """D6: a department head usually also teaches."""
    user, program = UserFactory(), ProgramFactory()
    MembershipFactory(user=user, program=program, role="instructor")
    MembershipFactory(user=user, program=program, role="head")
    assert set(user.memberships.values_list("role", flat=True)) == {"instructor", "head"}


def test_membership_str():
    m = MembershipFactory(role=ProgramMembership.Role.HEAD)
    assert "Department Head" in str(m)
