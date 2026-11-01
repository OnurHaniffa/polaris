"""Ready-made worlds for tests. elif_scenario() is the professor's slide in one line.

Both scenarios build their OWN test program (via ProgramFactory: code TST0, TST1, ...) with
their own PO set. They never touch the real CSE program created by the data migration, so
tests can't interfere with it or with each other."""

import datetime
from datetime import date
from decimal import Decimal
from decimal import Decimal as D
from types import SimpleNamespace

from django.utils import timezone

from apps.accounts.models import ProgramMembership
from apps.core.tests.factories import (
    AssessmentFactory,
    AssessmentLOWeightFactory,
    CourseFactory,
    EnrollmentFactory,
    GradeFactory,
    LearningOutcomeFactory,
    LOPOWeightFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)


def elif_scenario(*, published=True, student_number="2024-0041"):

    """Offering with 2 assessments, 2 LOs, 2 POs, weights and grades from the professor's
    slide (spec §2.2). With published=True, Elif's profile is PO 1 = 85.0, PO 2 = 82.9.
    With published=False the grades are drafts: her profile has no scores at all."""
    program = ProgramFactory()
    po_set = ProgramOutcomeSetFactory(program=program, effective_from_year=2020)
    po1 = ProgramOutcomeFactory(po_set=po_set, number=1, short_name="Knowledge")
    po2 = ProgramOutcomeFactory(po_set=po_set, number=2, short_name="Problem solving")

    instructor = UserFactory(first_name="Ahmet", last_name="Hoca")
    MembershipFactory(user=instructor, program=program, role=ProgramMembership.Role.INSTRUCTOR)
    student = UserFactory(first_name="Elif", last_name="Yıldız", student_number=student_number)
    MembershipFactory(user=student, program=program, cohort_year=2024)

    course = CourseFactory(program=program, code="CSE 311", title="Software Engineering")
    offering = OfferingFactory(course=course, term=TermFactory(), instructors=[instructor])
    enrollment = EnrollmentFactory(offering=offering, student=student)

    midterm = AssessmentFactory(offering=offering, name="Midterm", position=1)
    project = AssessmentFactory(offering=offering, name="Project", kind="project", position=2)
    lo1 = LearningOutcomeFactory(offering=offering, number=1)
    lo2 = LearningOutcomeFactory(offering=offering, number=2)

    for assessment, lo, weight in [
        (midterm, lo1, 60),
        (project, lo1, 40),
        (midterm, lo2, 40),
        (project, lo2, 100),
    ]:
        AssessmentLOWeightFactory(assessment=assessment, learning_outcome=lo, weight=D(weight))
    LOPOWeightFactory(learning_outcome=lo1, program_outcome=po1, weight=4)
    LOPOWeightFactory(learning_outcome=lo2, program_outcome=po1, weight=2)
    LOPOWeightFactory(learning_outcome=lo2, program_outcome=po2, weight=5)

    GradeFactory(assessment=midterm, enrollment=enrollment, score=D(90), published=published)
    GradeFactory(assessment=project, enrollment=enrollment, score=D(80), published=published)

    return SimpleNamespace(
        program=program,
        po_set=po_set,
        offering=offering,
        enrollment=enrollment,
        student=student,
        instructor=instructor,
        midterm=midterm,
        project=project,
        lo1=lo1,
        lo2=lo2,
        po1=po1,
        po2=po2,
    )


def small_department():
    """3 students × 2 offerings in one closed term, for aggregate tests (B9, B10).

    Course A: one assessment → LO A1 (weight 100) → PO 1 (weight 5).
    Course B: one assessment → LO B1 (weight 100) → PO 1 (weight 5) and PO 2 (weight 3).
    Published marks: Ali 90/70, Ayşe 60/50, Mert 40/(none)."""
    program = ProgramFactory()
    po_set = ProgramOutcomeSetFactory(program=program)
    po1 = ProgramOutcomeFactory(po_set=po_set, number=1)
    po2 = ProgramOutcomeFactory(po_set=po_set, number=2)
    term = TermFactory(
        code="2026S",
        name="Spring 2026",
        starts_on=datetime.date(2026, 2, 9),
        ends_on=datetime.date(2026, 6, 12),
        status="closed",
    )
    students = [
        UserFactory(first_name=name, student_number=f"2024-00{i}")
        for i, name in enumerate(["Ali", "Ayşe", "Mert"], start=1)
    ]
    for s in students:
        MembershipFactory(user=s, program=program, cohort_year=2024)

    offerings, assessments = [], []
    for code, links in [("CSE 101", [(po1, 5)]), ("CSE 102", [(po1, 5), (po2, 3)])]:
        offering = OfferingFactory(course=CourseFactory(program=program, code=code), term=term)
        assessment = AssessmentFactory(offering=offering, name="Final", published=True)
        lo = LearningOutcomeFactory(offering=offering, number=1)
        AssessmentLOWeightFactory(assessment=assessment, learning_outcome=lo, weight=D(100))
        for po, weight in links:
            LOPOWeightFactory(learning_outcome=lo, program_outcome=po, weight=weight)
        offerings.append(offering)
        assessments.append(assessment)

    marks = {"Ali": (90, 70), "Ayşe": (60, 50), "Mert": (40, None)}
    for s in students:
        for assessment, mark in zip(assessments, marks[s.first_name], strict=True):
            enrollment = EnrollmentFactory(offering=assessment.offering, student=s)
            if mark is not None:
                GradeFactory(
                    assessment=assessment, enrollment=enrollment, score=D(mark), published=True
                )
    return SimpleNamespace(
        program=program, term=term, offerings=offerings, students=students, po1=po1, po2=po2
    )

def one_lo_class(*, students_scores=(), term=None, program=None, po=None, lo_po_weight=3):
    """One offering whose single published assessment (max 100) feeds one LO (weight 100),
    which maps to one PO. A student's grade is therefore also their LO and PO score."""
    if po is None:
        program = program or ProgramFactory()
        po_set = ProgramOutcomeSetFactory(program=program, is_active=True, effective_from_year=2000)
        po = ProgramOutcomeFactory(po_set=po_set, number=1)
    program = po.po_set.program
    term = term or TermFactory(code="2026S", name="Spring 2026", starts_on=date(2026, 2, 9),
                               ends_on=date(2026, 6, 15), status="closed")
    offering = OfferingFactory(course=CourseFactory(program=program), term=term)
    published_at = timezone.now()
    assessment = AssessmentFactory(offering=offering, name="Exam", max_score=Decimal("100"),
                                   published_at=published_at)
    lo = LearningOutcomeFactory(offering=offering, number=1)
    AssessmentLOWeightFactory(assessment=assessment, learning_outcome=lo, weight=Decimal("100"))
    LOPOWeightFactory(learning_outcome=lo, program_outcome=po, weight=lo_po_weight)

    students, enrollments = [], []
    for student, score in students_scores:
        if student is None:
            student = UserFactory()
        ProgramMembership.objects.get_or_create(
            user=student, program=program, role=ProgramMembership.Role.STUDENT,
            defaults={"cohort_year": 2024},
        )
        enrollment = EnrollmentFactory(offering=offering, student=student)
        if score is not None:
            value = Decimal(str(score))
            GradeFactory(assessment=assessment, enrollment=enrollment, score=value,
                         published_score=value, published_at=published_at)
        students.append(student)
        enrollments.append(enrollment)

    return SimpleNamespace(offering=offering, assessment=assessment, lo=lo, po=po,
                           program=program, term=term, students=students,
                           enrollments=enrollments)
