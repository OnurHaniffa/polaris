from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from apps.accounts.models import ProgramMembership
from apps.catalog.models import Course, CourseOffering, Enrollment, Program, Term

Role = ProgramMembership.Role
User = get_user_model()


@pytest.fixture(autouse=True)
def _login_url(settings):
    # TEMPORARY: "accounts:login" does not exist until S2-01. Delete this fixture after S2-01.
    settings.LOGIN_URL = "/accounts/login/"


def make_user(name, **extra):
    return User.objects.create_user(
        email=f"{name}@test.local",
        password="pw-12345-test",
        first_name=name,
        last_name="Test",
        **extra,
    )


def join(user, program, role):
    cohort = 2023 if role == Role.STUDENT else None
    ProgramMembership.objects.create(user=user, program=program, role=role, cohort_year=cohort)


@pytest.fixture
def cse(db):
    program, _ = Program.objects.get_or_create(
        code="CSE",
        defaults={"name": "Computer Engineering"},
    )
    return program


@pytest.fixture
def mat(db):
    return Program.objects.create(code="MAT", name="Mathematics")


@pytest.fixture
def term(db):
    return Term.objects.create(
        code="2026F",
        name="Fall 2026",
        starts_on=date(2026, 9, 14),
        ends_on=date(2027, 1, 15),
        status=Term.Status.OPEN,
    )


def _offering(program, term, code):
    course = Course.objects.create(
        program=program, code=code, title=code, credits=Decimal("3"), ects=Decimal("5")
    )
    return CourseOffering.objects.create(course=course, term=term)


@pytest.fixture
def offering(cse, term):
    return _offering(cse, term, "CSE 311")


@pytest.fixture
def other_offering(mat, term):
    return _offering(mat, term, "MAT 241")


@pytest.fixture
def head(cse):
    u = make_user("head")
    join(u, cse, Role.HEAD)
    return u


@pytest.fixture
def other_head(mat):
    u = make_user("otherhead")
    join(u, mat, Role.HEAD)
    return u


@pytest.fixture
def instructor(cse, offering):
    u = make_user("instructor")
    join(u, cse, Role.INSTRUCTOR)
    offering.instructors.add(u)
    return u


@pytest.fixture
def other_instructor(cse):  # instructor in CSE but NOT assigned to `offering`
    u = make_user("otherinstructor")
    join(u, cse, Role.INSTRUCTOR)
    return u


@pytest.fixture
def student(cse, offering):
    u = make_user("student")
    join(u, cse, Role.STUDENT)
    Enrollment.objects.create(offering=offering, student=u)
    return u


@pytest.fixture
def other_student(cse):  # student in CSE but NOT enrolled in `offering`
    u = make_user("otherstudent")
    join(u, cse, Role.STUDENT)
    return u


@pytest.fixture
def outsider(db):
    return make_user("outsider")


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email="root@test.local", password="pw-12345-test", first_name="Root", last_name="Test"
    )


@pytest.fixture
def actors(
    head, other_head, instructor, other_instructor, student, other_student, outsider, superuser
):
    return {
        "head": head,
        "other_head": other_head,
        "instructor": instructor,
        "other_instructor": other_instructor,
        "student": student,
        "other_student": other_student,
        "outsider": outsider,
        "superuser": superuser,
        "anonymous": AnonymousUser(),
    }


@pytest.fixture(autouse=True)
def _plain_staticfiles(settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
