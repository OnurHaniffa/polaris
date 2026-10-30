import pytest
from django.urls import reverse

from apps.catalog.models import CourseOffering, Enrollment, Term
from apps.core.tests.factories import (
    CourseFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def cse():
    return ProgramFactory(code="TST")


@pytest.fixture
def head_client(client, cse):
    head = UserFactory()
    MembershipFactory(user=head, program=cse, role="head")
    client.force_login(head)
    return client


def test_head_sets_up_a_term_end_to_end(head_client, cse):
    """B3 happy path: term → course → offering with instructor → student, all through the views."""
    teacher = UserFactory(first_name="Can", last_name="Aydın")
    MembershipFactory(user=teacher, program=cse, role="instructor")

    r = head_client.post(
        reverse("catalog:terms"),
        {"code": "2026F", "name": "Fall 2026", "starts_on": "2026-09-21", "ends_on": "2027-01-15"},
    )
    assert r.status_code == 302
    term = Term.objects.get(code="2026F")
    head_client.post(
        reverse("catalog:term_status", kwargs={"term_id": term.pk}), {"action": "open"}
    )

    r = head_client.post(
        reverse("catalog:courses"),
        {"code": "cse 311", "title": "Software", "credits": "3", "ects": "6"},
    )
    assert r.status_code == 302
    course = cse.courses.get(code="CSE 311")

    r = head_client.post(
        reverse("catalog:offerings"),
        {"course": course.pk, "term": term.pk, "section": "1", "instructors": [teacher.pk]},
    )
    offering = CourseOffering.objects.get(course=course, term=term)
    assert r["Location"] == reverse("catalog:enrollments", kwargs={"offering_id": offering.pk})

    r = head_client.post(
        r["Location"],
        {
            "action": "add",
            "student_number": "2023001",
            "email": "elif@live.acibadem.edu.tr",
            "first_name": "Elif",
            "last_name": "Yıldız",
            "cohort_year": "2023",
        },
    )
    assert r.status_code == 302
    assert Enrollment.objects.get(offering=offering).student.email == "elif@live.acibadem.edu.tr"


def test_term_with_end_before_start_shows_field_error(head_client):
    r = head_client.post(
        reverse("catalog:terms"),
        {"code": "X", "name": "X", "starts_on": "2027-01-15", "ends_on": "2026-09-21"},
    )
    assert r.status_code == 200
    assert "must end after it starts" in r.text


def test_reopen_without_reason_shows_error(head_client):
    term = TermFactory(status=Term.Status.CLOSED)
    r = head_client.post(
        reverse("catalog:term_status", kwargs={"term_id": term.pk}),
        {"action": "reopen", "reason": ""},
        follow=True,
    )
    assert "Say why the term is being reopened" in r.text
    term.refresh_from_db()
    assert term.status == Term.Status.CLOSED


def test_duplicate_enrollment_shows_message(head_client, cse):
    offering = OfferingFactory(
        course=CourseFactory(program=cse), term=TermFactory(status=Term.Status.OPEN)
    )
    student = UserFactory(student_number="2023001")
    MembershipFactory(user=student, program=cse, role="student", cohort_year=2023)
    url = reverse("catalog:enrollments", kwargs={"offering_id": offering.pk})
    head_client.post(url, {"action": "add", "student_number": "2023001"})
    r = head_client.post(url, {"action": "add", "student_number": "2023001"})
    assert r.status_code == 200 and "already enrolled" in r.text


def test_closed_term_enrollment_page_is_read_only(head_client, cse):
    """B3 AC 3 on the head's side: no add form, no drop buttons."""
    offering = OfferingFactory(
        course=CourseFactory(program=cse), term=TermFactory(status=Term.Status.CLOSED)
    )
    r = head_client.get(reverse("catalog:enrollments", kwargs={"offering_id": offering.pk}))
    assert "is closed" in r.text and 'value="add"' not in r.text


def test_other_programs_objects_are_404(head_client):
    bme = ProgramFactory(code="BME")
    foreign = CourseFactory(program=bme, code="BME 101")
    assert (
        head_client.get(
            reverse("catalog:course_edit", kwargs={"course_id": foreign.pk})
        ).status_code
        == 404
    )


def test_po_delete_modal_partial_for_htmx(head_client, cse):
    po_set = ProgramOutcomeSetFactory(
        program=cse, label="2023", effective_from_year=2020, is_active=True
    )
    po = ProgramOutcomeFactory(po_set=po_set, number=11)
    r = head_client.get(
        reverse("catalog:po_delete", kwargs={"po_id": po.pk}), headers={"HX-Request": "true"}
    )
    assert r.status_code == 200
    assert "<nav" not in r.text and "Delete PO 11" in r.text


def test_fresh_install_shows_eleven_official_pos(head_client):
    """B2 AC 1. Needs the S1-05 data migration, so it uses the migrated CSE program."""
    from apps.catalog.models import Program

    program = Program.objects.get(code="CSE")
    active = program.po_sets.get(is_active=True)
    assert active.outcomes.count() == 11
    assert active.outcomes.get(number=1).description.startswith(
        "Gain adequate knowledge in mathematics"
    )
