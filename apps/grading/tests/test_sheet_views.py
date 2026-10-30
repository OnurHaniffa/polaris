from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import ProgramMembership
from apps.catalog.models import Term
from apps.core.tests.factories import (
    AssessmentFactory,
    EnrollmentFactory,
    GradeFactory,
    MembershipFactory,
    OfferingFactory,
    UserFactory,
)
from apps.grading.models import Grade
from apps.grading.selectors import grade_sheet

pytestmark = pytest.mark.django_db


@pytest.fixture
def course():
    offering = OfferingFactory(term__status=Term.Status.OPEN)
    instructor = UserFactory()
    MembershipFactory(
        user=instructor, program=offering.course.program, role=ProgramMembership.Role.INSTRUCTOR
    )
    offering.instructors.add(instructor)
    return offering, instructor


def _big_class(offering, students=80, assessments=6):
    tests = [
        AssessmentFactory(offering=offering, name=f"A{i}", position=i) for i in range(assessments)
    ]
    for _ in range(students):
        e = EnrollmentFactory(offering=offering)
        for a in tests:
            GradeFactory(assessment=a, enrollment=e, score=Decimal("70"))
    return tests


def test_selector_uses_three_queries(course, django_assert_num_queries):
    offering, _ = course
    _big_class(offering)
    with django_assert_num_queries(3):
        sheet = grade_sheet(offering)
        # touching every cell must not trigger lazy loads
        values = [c.input_value for r in sheet.rows for c in r.cells]
        names = [r.enrollment.student.last_name for r in sheet.rows]
    assert len(values) == 480 and len(names) == 80


def test_sheet_page_80_by_6_has_no_n_plus_one(course, client, django_assert_max_num_queries):
    offering, instructor = course
    _big_class(offering)
    client.force_login(instructor)
    # 3 sheet queries + session, user, offering, memberships and navigation; never 480
    with django_assert_max_num_queries(12):
        response = client.get(reverse("grading:sheet", kwargs={"offering_id": offering.id}))
    assert response.status_code == 200
    assert response.content.count(b'class="form-control form-control-sm grade-input') == 480


def test_htmx_cell_save_returns_only_the_cell(course, client):
    offering, instructor = course
    a = AssessmentFactory(offering=offering, name="Midterm I", max_score=Decimal("100"))
    e = EnrollmentFactory(offering=offering)
    client.force_login(instructor)
    url = reverse(
        "grading:cell",
        kwargs={"offering_id": offering.id, "assessment_id": a.id, "enrollment_id": e.id},
    )
    response = client.post(url, {"value": "85,5"}, headers={"HX-Request": "true"})
    body = response.content.decode()
    assert response.status_code == 200
    assert body.lstrip().startswith(f'<td id="cell-{a.id}-{e.id}"')
    assert "is-valid" in body and 'value="85.5"' in body
    assert f'id="col-status-{a.id}"' in body and 'hx-swap-oob="true"' in body
    assert "<html" not in body  # partial, not the page
    assert Grade.objects.get().score == Decimal("85.5")


def test_htmx_cell_error_shows_message_and_saves_nothing(course, client):
    offering, instructor = course
    a = AssessmentFactory(offering=offering, name="Midterm I", max_score=Decimal("100"))
    e = EnrollmentFactory(offering=offering)
    client.force_login(instructor)
    url = reverse(
        "grading:cell",
        kwargs={"offering_id": offering.id, "assessment_id": a.id, "enrollment_id": e.id},
    )
    response = client.post(url, {"value": "105"}, headers={"HX-Request": "true"})
    body = response.content.decode()
    assert response.status_code == 200
    assert "Max for Midterm I is 100" in body
    assert 'value="105"' in body and "is-invalid" in body  # what they typed stays visible
    assert not Grade.objects.exists()


def test_draft_grade_is_invisible_to_scores(course, client):
    """B6 AC 2: a saved draft does not change what students or scores see."""
    offering, instructor = course
    a = AssessmentFactory(offering=offering, max_score=Decimal("100"))
    e = EnrollmentFactory(offering=offering)
    client.force_login(instructor)
    client.post(
        reverse(
            "grading:cell",
            kwargs={"offering_id": offering.id, "assessment_id": a.id, "enrollment_id": e.id},
        ),
        {"value": "90"},
    )
    grade = Grade.objects.get()
    assert grade.score == Decimal("90") and grade.published_score is None


def test_cell_in_another_offering_is_404(course, client):
    offering, instructor = course
    a = AssessmentFactory(offering=offering)
    other_enrollment = EnrollmentFactory()  # student of a different offering
    client.force_login(instructor)
    url = reverse(
        "grading:cell",
        kwargs={
            "offering_id": offering.id,
            "assessment_id": a.id,
            "enrollment_id": other_enrollment.id,
        },
    )
    assert client.post(url, {"value": "50"}).status_code == 404


def test_closed_term_renders_disabled_inputs(course, client):
    offering, instructor = course
    AssessmentFactory(offering=offering)
    EnrollmentFactory(offering=offering)
    Term.objects.filter(pk=offering.term_id).update(status=Term.Status.CLOSED)
    client.force_login(instructor)
    response = client.get(reverse("grading:sheet", kwargs={"offering_id": offering.id}))
    assert b"Grades are read-only" in response.content
    assert b"disabled" in response.content
