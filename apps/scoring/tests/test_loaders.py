"""Loader tests: the policies that decide WHICH data reaches the engine (P4, P9, P10, P13).
These hit the database, so they use pytest-django's `db` fixture (via elif_data)."""

import datetime
from decimal import Decimal as D

import pytest

from apps.catalog.models import Term
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
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)
from apps.core.tests.scenarios import elif_scenario
from apps.scoring.engine import compute_student_profile, display
from apps.scoring.loaders import load_offering_inputs, load_student_inputs

pytestmark = pytest.mark.django_db

SPRING_2026 = {
    "code": "2026S",
    "name": "Spring 2026",
    "starts_on": datetime.date(2026, 2, 9),
    "ends_on": datetime.date(2026, 6, 12),
    "status": Term.Status.CLOSED,
}


def profile_of(student, **kwargs):
    return compute_student_profile(load_student_inputs(student, **kwargs))


def add_simple_offering(program, po, student, *, term, mark, code="MAT 241", weight=5):
    """A one-assessment, one-LO course for `student`, linked to `po`."""
    offering = OfferingFactory(course=CourseFactory(program=program, code=code), term=term)
    assessment = AssessmentFactory(offering=offering, name="Final")
    lo = LearningOutcomeFactory(offering=offering, number=1)
    AssessmentLOWeightFactory(assessment=assessment, learning_outcome=lo, weight=D(100))
    LOPOWeightFactory(learning_outcome=lo, program_outcome=po, weight=weight)
    enrollment = EnrollmentFactory(offering=offering, student=student)
    GradeFactory(assessment=assessment, enrollment=enrollment, score=D(mark), published=True)
    return offering


def test_elif_profile_from_the_database(elif_data):
    """The end-to-end check of Sprint 1: database → loader → engine → slide numbers."""
    profile = profile_of(elif_data.student)
    assert display(profile.po_scores[elif_data.po1.id].score) == "85.0"
    assert display(profile.po_scores[elif_data.po2.id].score) == "82.9"


def test_loader_builds_the_expected_inputs(elif_data):
    [inputs] = load_student_inputs(elif_data.student)
    assert inputs.offering_id == elif_data.offering.id
    assert inputs.grades == {elif_data.midterm.id: D(90), elif_data.project.id: D(80)}
    assert inputs.max_scores == {elif_data.midterm.id: D(100), elif_data.project.id: D(100)}
    assert len(inputs.assessment_lo_edges) == 4
    assert len(inputs.lo_po_edges) == 3


def test_draft_grades_are_invisible():
    """P4: unpublished grades never reach the engine."""
    data = elif_scenario(published=False)
    profile = profile_of(data.student)
    assert profile.po_scores[data.po1.id].score is None


def test_edited_published_grade_shows_old_value_until_republished(elif_data):
    """P4: the loader reads published_score, not the draft score."""
    grade = elif_data.enrollment.grades.get(assessment=elif_data.midterm)
    grade.score = D(10)  # instructor edits, does not publish yet
    grade.save()
    [inputs] = load_student_inputs(elif_data.student)
    assert inputs.grades[elif_data.midterm.id] == D(90)


def test_excused_published_grade_is_skipped(elif_data):
    """P6: excused grades are left out, like missing ones."""
    grade = elif_data.enrollment.grades.get(assessment=elif_data.project)
    grade.published_is_excused = True
    grade.save()
    [inputs] = load_student_inputs(elif_data.student)
    assert elif_data.project.id not in inputs.grades
    profile = compute_student_profile([inputs])
    assert display(profile.po_scores[elif_data.po2.id].score) == "90.0"  # midterm only


def test_dropped_enrollment_does_not_count(elif_data):
    elif_data.enrollment.status = "dropped"
    elif_data.enrollment.save()
    assert load_student_inputs(elif_data.student) == []


def test_retake_latest_attempt_counts(elif_data):
    """P9: Elif failed MAT 241 in Spring 2026 (40) and retook it in Fall 2026 (80).
    Only the Fall attempt reaches the engine."""
    program, po2, student = elif_data.program, elif_data.po2, elif_data.student
    course = CourseFactory(program=program, code="MAT 241")
    spring = TermFactory(**SPRING_2026)
    for term, mark in [(spring, 40), (elif_data.offering.term, 80)]:
        offering = OfferingFactory(course=course, term=term)
        assessment = AssessmentFactory(offering=offering, name="Final")
        lo = LearningOutcomeFactory(offering=offering, number=1)
        AssessmentLOWeightFactory(assessment=assessment, learning_outcome=lo, weight=D(100))
        LOPOWeightFactory(learning_outcome=lo, program_outcome=po2, weight=5)
        enrollment = EnrollmentFactory(offering=offering, student=student)
        GradeFactory(assessment=assessment, enrollment=enrollment, score=D(mark), published=True)

    inputs = load_student_inputs(student)
    assert len(inputs) == 2  # CSE 311 + the latest MAT 241 only
    profile = compute_student_profile(inputs)
    # PO 2 = (82.857… × 5 + 80 × 5) ÷ 10 = 81.43; the old 40 would have given 61.4
    assert display(profile.po_scores[po2.id].score) == "81.4"


def test_open_terms_can_be_excluded(elif_data):
    """P10: department numbers use closed terms only. Elif's CSE 311 is in an open term."""
    add_simple_offering(
        elif_data.program,
        elif_data.po2,
        elif_data.student,
        term=TermFactory(**SPRING_2026),
        mark=70,
    )
    assert len(load_student_inputs(elif_data.student)) == 2
    closed_only = load_student_inputs(elif_data.student, include_open_terms=False)
    assert len(closed_only) == 1
    profile = compute_student_profile(closed_only)
    assert display(profile.po_scores[elif_data.po2.id].score) == "70.0"
    assert elif_data.po1.id not in profile.po_scores


def test_planned_terms_never_count(elif_data):
    planned = TermFactory(
        code="2027S",
        name="Spring 2027",
        starts_on=datetime.date(2027, 2, 8),
        ends_on=datetime.date(2027, 6, 11),
        status=Term.Status.PLANNED,
    )
    add_simple_offering(elif_data.program, elif_data.po2, elif_data.student, term=planned, mark=10)
    assert len(load_student_inputs(elif_data.student)) == 1


def test_up_to_term_cuts_later_terms(elif_data):
    """Used by the trend chart (T1.5): the profile as it was at the end of Spring 2026."""
    spring = TermFactory(**SPRING_2026)
    maths = add_simple_offering(
        elif_data.program, elif_data.po2, elif_data.student, term=spring, mark=70
    )
    inputs = load_student_inputs(elif_data.student, up_to_term=spring)
    assert [i.offering_id for i in inputs] == [maths.id]


def test_po_set_follows_cohort(elif_data):
    """P13: a 2026 curriculum appears with a new PO. Elif (cohort 2023) keeps the old set,
    so links to the new set's PO are ignored for her; a 2026 student gets the new set."""
    new_set = ProgramOutcomeSetFactory(
        program=elif_data.program,
        label="2026 curriculum",
        effective_from_year=2026,
        is_active=False,
    )
    new_po = ProgramOutcomeFactory(po_set=new_set, number=1)
    LOPOWeightFactory(learning_outcome=elif_data.lo1, program_outcome=new_po, weight=5)

    elif_profile = profile_of(elif_data.student)
    assert new_po.id not in elif_profile.po_scores
    assert display(elif_profile.po_scores[elif_data.po1.id].score) == "85.0"

    newcomer = UserFactory()
    MembershipFactory(user=newcomer, program=elif_data.program, cohort_year=2026)
    enrollment = EnrollmentFactory(offering=elif_data.offering, student=newcomer)
    GradeFactory(assessment=elif_data.midterm, enrollment=enrollment, score=D(50), published=True)
    newcomer_profile = profile_of(newcomer)
    assert set(newcomer_profile.po_scores) == {new_po.id}


def test_offering_inputs_cover_the_whole_class(elif_data):
    classmate = UserFactory()
    MembershipFactory(user=classmate, program=elif_data.program, cohort_year=2023)
    enrollment = EnrollmentFactory(offering=elif_data.offering, student=classmate)
    GradeFactory(assessment=elif_data.midterm, enrollment=enrollment, score=D(70), published=True)

    by_enrollment = load_offering_inputs(elif_data.offering)
    assert set(by_enrollment) == {elif_data.enrollment.id, enrollment.id}
    assert by_enrollment[enrollment.id].grades == {elif_data.midterm.id: D(70)}


def test_offering_inputs_of_empty_class(db):
    assert load_offering_inputs(OfferingFactory()) == {}


def test_student_loader_query_count(elif_data, django_assert_max_num_queries):
    """Four offerings must not mean four times the queries: the loader batches."""
    spring = TermFactory(**SPRING_2026)
    for code in ["MAT 141", "PHY 101", "CSE 102"]:
        add_simple_offering(
            elif_data.program, elif_data.po1, elif_data.student, term=spring, mark=60, code=code
        )
    with django_assert_max_num_queries(7):
        inputs = load_student_inputs(elif_data.student)
    assert len(inputs) == 4
