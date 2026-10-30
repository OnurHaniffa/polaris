from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.catalog.models import Term
from apps.core.tests.factories import (
    AssessmentFactory,
    CourseFactory,
    LearningOutcomeFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)


@pytest.fixture
def course(db):
    program = ProgramFactory(code="TST")  # "CSE" is the real program from the data migration
    po_set = ProgramOutcomeSetFactory(
        program=program, label="2023 curriculum", effective_from_year=2020, is_active=True
    )
    po1 = ProgramOutcomeFactory(po_set=po_set, number=1, short_name="Math & science")
    po2 = ProgramOutcomeFactory(po_set=po_set, number=2, short_name="Problem solving")
    po3 = ProgramOutcomeFactory(po_set=po_set, number=3, short_name="Design")
    term = TermFactory(
        code="2026F",
        name="Fall 2026",
        starts_on=date(2026, 9, 21),
        ends_on=date(2027, 1, 15),
        status=Term.Status.OPEN,
    )
    offering = OfferingFactory(course=CourseFactory(program=program, code="CSE 311"), term=term)
    teacher = UserFactory(email="can.aydin@test.edu")
    MembershipFactory(user=teacher, program=program, role="instructor")
    offering.instructors.add(teacher)
    midterm = AssessmentFactory(
        offering=offering,
        name="Midterm I",
        max_score=Decimal("100"),
        course_weight=Decimal("40"),
        position=1,
    )
    project = AssessmentFactory(
        offering=offering,
        name="Project",
        max_score=Decimal("100"),
        course_weight=Decimal("60"),
        position=2,
    )
    lo1 = LearningOutcomeFactory(offering=offering, number=1, description="Explain design choices")
    lo2 = LearningOutcomeFactory(offering=offering, number=2, description="Apply agile practices")
    return SimpleNamespace(
        program=program,
        po_set=po_set,
        po1=po1,
        po2=po2,
        po3=po3,
        term=term,
        offering=offering,
        teacher=teacher,
        midterm=midterm,
        project=project,
        lo1=lo1,
        lo2=lo2,
    )


@pytest.fixture
def teacher_client(client, course):
    client.force_login(course.teacher)
    return client


@pytest.fixture
def head_user(course):
    head = UserFactory(email="head@test.edu")
    MembershipFactory(user=head, program=course.program, role="head")
    return head
