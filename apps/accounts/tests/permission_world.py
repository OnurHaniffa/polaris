"""Shared test world + expected-status tables for the permission tests (spec §3.3, §3.4).

One small department, eight personas. Every permission test (unit, decorator, matrix)
uses the same world and the same expectation tables, so they cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from apps.accounts.models import ProgramMembership
from apps.catalog.models import Course, CourseOffering, Enrollment, Program, Term

User = get_user_model()
Role = ProgramMembership.Role

PERSONAS = (
    "anonymous",
    "student",  # enrolled in the CSE offerings
    "other_student",  # enrolled only in the EEE offering
    "instructor",  # teaches both CSE offerings
    "other_instructor",  # teaches the EEE offering
    "head",  # head of CSE
    "other_head",  # head of EEE
    "admin",  # superuser
)


@dataclass
class World:
    program: Program
    other_program: Program
    open_offering: CourseOffering  # CSE 311, Fall 2026 (open)
    closed_offering: CourseOffering  # CSE 311, Fall 2025 (closed)
    other_offering: CourseOffering  # EEE 201, Fall 2026 (open), other program
    users: dict

    def user(self, persona):
        return self.users[persona] or AnonymousUser()


def _make_user(email, **extra):
    first = email.split("@")[0].title()
    return User.objects.create_user(email=email, password="pw", first_name=first, last_name="Test", **extra)


def build_world() -> World:
    cse, _ = Program.objects.get_or_create(code="CSE", defaults={"name": "Computer Engineering"})
    eee, _ = Program.objects.get_or_create(code="EEE", defaults={"name": "Electrical Engineering"})

    open_term, _ = Term.objects.update_or_create(
        code="2026F",
        defaults=dict(
            name="Fall 2026",
            starts_on=date(2026, 9, 28),
            ends_on=date(2027, 1, 15),
            status=Term.Status.OPEN,
        ),
    )
    closed_term, _ = Term.objects.update_or_create(
        code="2025F",
        defaults=dict(
            name="Fall 2025",
            starts_on=date(2025, 9, 29),
            ends_on=date(2026, 1, 16),
            status=Term.Status.CLOSED,
        ),
    )

    cse_course, _ = Course.objects.get_or_create(program=cse, code="CSE 311", defaults=dict(title="Databases", credits=3, ects=6))
    eee_course, _ = Course.objects.get_or_create(program=eee, code="EEE 201", defaults=dict(title="Circuits", credits=3, ects=6))

    open_offering, _ = CourseOffering.objects.get_or_create(course=cse_course, term=open_term)
    closed_offering, _ = CourseOffering.objects.get_or_create(course=cse_course, term=closed_term)
    other_offering, _ = CourseOffering.objects.get_or_create(course=eee_course, term=open_term)

    student = _make_user("student@x.edu", student_number="2201001")
    other_student = _make_user("other_student@x.edu", student_number="2201002")
    instructor = _make_user("instructor@x.edu")
    other_instructor = _make_user("other_instructor@x.edu")
    head = _make_user("head@x.edu")
    other_head = _make_user("other_head@x.edu")
    admin = User.objects.create_superuser(email="admin@x.edu", password="pw", first_name="Ad", last_name="Min")

    def member(user, program, role, **extra):
        ProgramMembership.objects.create(user=user, program=program, role=role, **extra)

    member(student, cse, Role.STUDENT, cohort_year=2023)
    member(other_student, eee, Role.STUDENT, cohort_year=2023)
    member(instructor, cse, Role.INSTRUCTOR)
    member(other_instructor, eee, Role.INSTRUCTOR)
    member(head, cse, Role.HEAD)
    member(other_head, eee, Role.HEAD)

    open_offering.instructors.add(instructor)
    closed_offering.instructors.add(instructor)
    other_offering.instructors.add(other_instructor)

    Enrollment.objects.create(offering=open_offering, student=student)
    Enrollment.objects.create(offering=closed_offering, student=student)
    Enrollment.objects.create(offering=other_offering, student=other_student)

    return World(
        program=cse,
        other_program=eee,
        open_offering=open_offering,
        closed_offering=closed_offering,
        other_offering=other_offering,
        users={
            "anonymous": None,
            "student": student,
            "other_student": other_student,
            "instructor": instructor,
            "other_instructor": other_instructor,
            "head": head,
            "other_head": other_head,
            "admin": admin,
        },
    )


# ---------------------------------------------------------------------------
# Expected status tables (spec §3.3 / §3.4). Targets: the CSE offerings in `World`.
#   302 = redirect to login   404 = not yours / not allowed   403 = visible but read-only
# ---------------------------------------------------------------------------

PUBLIC = {p: 200 for p in PERSONAS}

# View an offering (edit=False): its head, its instructors, admin.
READ_OFFERING = {
    "anonymous": 302,
    "student": 404,
    "other_student": 404,
    "instructor": 200,
    "other_instructor": 404,
    "head": 200,
    "other_head": 404,
    "admin": 200,
}

# Change an offering (edit=True) in an OPEN term: same people as READ_OFFERING.
WRITE_OPEN = READ_OFFERING

# Change an offering in a CLOSED term: everyone who could see it gets 403,
# superusers included (spec §3.3). Everyone else still gets 404, never 403.
WRITE_CLOSED = {
    **READ_OFFERING,
    "instructor": 403,
    "head": 403,
    "admin": 403,
}

# Department pages, @require_role("head"): any head (any program) and admin.
DEPARTMENT = {
    "anonymous": 302,
    "student": 404,
    "other_student": 404,
    "instructor": 404,
    "other_instructor": 404,
    "head": 200,
    "other_head": 200,
    "admin": 200,
}

# Pages for students only, @require_role("student"). Admin passes (spec §3.3).
STUDENT_ONLY = {
    "anonymous": 302,
    "student": 200,
    "other_student": 200,
    "instructor": 404,
    "other_instructor": 404,
    "head": 404,
    "other_head": 404,
    "admin": 200,
}

for _table in (PUBLIC, READ_OFFERING, WRITE_CLOSED, DEPARTMENT, STUDENT_ONLY):
    assert set(_table) == set(PERSONAS), "expectation table is missing a persona"
