from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog.models import Term
from apps.core.tests.factories import (
    EnrollmentFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    UserFactory,
)
from apps.core.tests.scenarios import elif_scenario
from apps.grading.models import Grade
from apps.reports import selectors
from apps.scoring.engine import display

pytestmark = pytest.mark.django_db


def _row(ctx, po):
    return next(r for r in ctx["rows"] if r.po.id == po.id)


def test_elif_sees_the_slide_numbers(client):
    data = elif_scenario()
    client.force_login(data.student)
    resp = client.get(reverse("student:profile"))
    assert resp.status_code == 200
    assert display(_row(resp.context, data.po1).score) == "85.0"
    assert display(_row(resp.context, data.po2).score) == "82.9"
    assert b"85.0" in resp.content and b"82.9" in resp.content


def test_chart_uses_the_same_rounded_numbers_as_the_table():
    data = elif_scenario()
    ctx = selectors.student_profile_context(data.student, viewer=data.student)
    i = ctx["chart"]["labels"].index(f"PO {data.po1.number}")
    assert ctx["chart"]["values"][i] == 85.0
    assert ctx["chart"]["states"][i] == "attained"


def test_po_without_evidence_shows_dash_not_zero(client):
    data = elif_scenario()
    po3 = ProgramOutcomeFactory(po_set=data.po1.po_set, number=3, short_name="System design")
    client.force_login(data.student)
    resp = client.get(reverse("student:profile"))
    row = _row(resp.context, po3)
    assert row.score is None and row.attained is None and row.course_count == 0
    assert b"No courses have contributed to this outcome yet" in resp.content


def test_unpublished_grades_never_appear():
    unpublished = elif_scenario(published=False)
    ctx = selectors.student_profile_context(unpublished.student, viewer=unpublished.student)
    assert all(r.score is None for r in ctx["rows"])
    assert ctx["has_any_score"] is False


def test_draft_edits_do_not_change_published_score():
    data = elif_scenario()
    Grade.objects.filter(assessment=data.midterm, enrollment__student=data.student).update(
        score=Decimal("10")
    )
    ctx = selectors.student_profile_context(data.student, viewer=data.student)
    assert display(_row(ctx, data.po1).score) == "85.0"


def test_drawer_lists_every_contributor_with_weight_and_share(client):
    data = elif_scenario()
    client.force_login(data.student)
    resp = client.get(reverse("student:po_detail", args=[data.po1.id]), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    rows = resp.context["rows"]
    assert [(r.lo.id, r.weight) for r in rows] == [(data.lo1.id, 4), (data.lo2.id, 2)]
    assert rows[0].share == Decimal(4) / Decimal(6)
    assert b"<html" not in resp.content


def test_drawer_without_htmx_renders_full_page(client):
    data = elif_scenario()
    client.force_login(data.student)
    resp = client.get(reverse("student:po_detail", args=[data.po1.id]))
    assert b"<html" in resp.content
    assert b"Back to my profile" in resp.content


def test_drawer_for_po_of_another_program_is_404(client):
    data = elif_scenario()
    other = ProgramOutcomeFactory()
    client.force_login(data.student)
    assert client.get(reverse("student:po_detail", args=[other.id])).status_code == 404


def test_course_page_shows_published_marks_and_lo_scores(client):
    data = elif_scenario()
    client.force_login(data.student)
    resp = client.get(reverse("student:course", args=[data.offering.id]))
    assert resp.status_code == 200
    states = {r.assessment.id: r.state for r in resp.context["assessment_rows"]}
    assert states[data.midterm.id] == "scored"
    lo_scores = {lo.id: ns.score for lo, ns in resp.context["lo_rows"]}
    assert display(lo_scores[data.lo1.id]) == "86.0"
    assert resp.context["in_progress"] == (data.offering.term.status != Term.Status.CLOSED)


def test_unpublished_assessment_says_not_published(client):
    data = elif_scenario(published=False)
    client.force_login(data.student)
    resp = client.get(reverse("student:course", args=[data.offering.id]))
    assert {r.state for r in resp.context["assessment_rows"]} == {"not_published"}
    assert b"Not published yet" in resp.content


def test_another_students_course_page_is_404(client):
    data = elif_scenario()
    classmate = UserFactory()
    MembershipFactory(
        user=classmate, program=data.offering.course.program, role="student", cohort_year=2024
    )
    client.force_login(classmate)
    assert client.get(reverse("student:course", args=[data.offering.id])).status_code == 404


def test_head_sees_student_of_own_program_only(client):
    data = elif_scenario()
    head = UserFactory()
    MembershipFactory(user=head, program=data.offering.course.program, role="head")
    other_head = UserFactory()
    MembershipFactory(user=other_head, program=ProgramFactory(), role="head")

    client.force_login(head)
    resp = client.get(reverse("reports:department_student", args=[data.student.id]))
    assert resp.status_code == 200
    assert resp.context["is_self"] is False
    assert b"85.0" in resp.content

    client.force_login(other_head)
    url = reverse("reports:department_student", args=[data.student.id])
    assert client.get(url).status_code == 404


def test_retaken_course_is_marked_superseded():
    data = elif_scenario()
    later_term = Term.objects.create(
        code="2030S", name="Spring 2030", starts_on=date(2030, 2, 1), ends_on=date(2030, 6, 30)
    )
    retake = OfferingFactory(course=data.offering.course, term=later_term)
    EnrollmentFactory(offering=retake, student=data.student)
    by_offering = {r.offering.id: r for r in selectors._course_rows(data.student)}
    assert by_offering[data.offering.id].superseded is True
    assert by_offering[retake.id].superseded is False


def test_profile_query_count_is_bounded(client, django_assert_max_num_queries):
    data = elif_scenario()
    client.force_login(data.student)
    with django_assert_max_num_queries(25):
        client.get(reverse("student:profile"))
