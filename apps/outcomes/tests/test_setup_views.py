from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.core.tests.factories import (
    EnrollmentFactory,
    GradeFactory,
    MembershipFactory,
    UserFactory,
)
from apps.outcomes.models import Assessment, AssessmentLOWeight, LearningOutcome


def url(name, course, **extra):
    return reverse(f"outcomes:{name}", kwargs={"offering_id": course.offering.pk, **extra})


def test_setup_page_lists_los_and_assessments(teacher_client, course):
    response = teacher_client.get(url("setup", course))
    assert response.status_code == 200
    html = response.content.decode()
    assert "Explain design choices" in html and "Midterm I" in html
    assert "Setup checklist" in html


def test_empty_course_shows_empty_states(client, course):
    LearningOutcome.objects.filter(offering=course.offering).delete()
    Assessment.objects.filter(offering=course.offering).delete()
    client.force_login(course.teacher)
    html = client.get(url("setup", course)).content.decode()
    assert "No learning outcomes yet" in html and "No assessments yet" in html


def test_course_weights_not_100_show_a_warning(teacher_client, course):
    """B4 AC2: a warning, not an error."""
    Assessment.objects.filter(pk=course.project.pk).update(course_weight=Decimal("50"))
    html = teacher_client.get(url("setup", course)).content.decode()
    assert "Should add up to 100%" in html


def test_create_lo_redirects_back_to_the_card(teacher_client, course):
    response = teacher_client.post(url("lo_create", course), {"description": "Test the software"})
    assert response.status_code == 302
    assert response["Location"].endswith("#los")
    assert course.offering.learning_outcomes.get(number=3).description == "Test the software"


def _other_offering(course):
    from apps.core.tests.factories import OfferingFactory

    return OfferingFactory(course__program=course.program, term=course.term)


def test_lo_from_another_course_is_404(teacher_client, course):
    """The sub-object rule from S2-02: ids are filtered by the offering in the URL."""
    other = LearningOutcome.objects.create(
        offering=_other_offering(course), number=1, description="Not yours"
    )
    response = teacher_client.get(url("lo_edit", course, lo_id=other.pk))
    assert response.status_code == 404


def test_reorder_view(teacher_client, course):
    order = f"{course.lo2.pk},{course.lo1.pk}"
    response = teacher_client.post(url("lo_reorder", course), {"order": order})
    assert response.status_code == 302
    course.lo1.refresh_from_db()
    assert course.lo1.number == 2


def test_delete_modal_lists_what_goes_with_it(teacher_client, course):
    """B4 AC3."""
    AssessmentLOWeight.objects.create(
        assessment=course.midterm, learning_outcome=course.lo1, weight=Decimal("60")
    )
    response = teacher_client.get(
        url("lo_delete", course, lo_id=course.lo1.pk), headers={"HX-Request": "true"}
    )
    html = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in html  # partial only
    assert "1 assessment → LO weight (Midterm I)" in html
    assert "LO 2 will be renumbered" in html


def test_delete_published_assessment_is_refused_with_a_message(teacher_client, course):
    GradeFactory(
        assessment=course.midterm,
        enrollment=EnrollmentFactory(offering=course.offering),
        score=Decimal("50"),
        published_score=Decimal("50"),
        published_at=timezone.now(),
    )
    modal = teacher_client.get(
        url("assessment_delete", course, assessment_id=course.midterm.pk),
        headers={"HX-Request": "true"},
    ).content.decode()
    assert "Unpublish it on the Grades tab first" in modal and "Delete</button>" not in modal
    response = teacher_client.post(
        url("assessment_delete", course, assessment_id=course.midterm.pk), follow=True
    )
    assert "Unpublish it on the Grades tab first" in response.content.decode()
    assert Assessment.objects.filter(pk=course.midterm.pk).exists()


def test_max_change_asks_for_confirmation_in_the_form(teacher_client, course):
    GradeFactory(
        assessment=course.midterm,
        enrollment=EnrollmentFactory(offering=course.offering),
        score=Decimal("70"),
    )
    data = {
        "name": "Midterm I",
        "kind": "midterm",
        "max_score": "80",
        "course_weight": "40",
        "due_date": "",
    }
    first = teacher_client.post(
        url("assessment_edit", course, assessment_id=course.midterm.pk), data
    )
    assert first.status_code == 200
    assert "Yes, change the maximum" in first.content.decode()
    second = teacher_client.post(
        url("assessment_edit", course, assessment_id=course.midterm.pk),
        {**data, "confirm_max_change": "on"},
    )
    assert second.status_code == 302


def test_instructor_of_another_course_gets_404(client, course):
    stranger = UserFactory(email="stranger@test.edu")
    MembershipFactory(user=stranger, program=course.program, role="instructor")
    client.force_login(stranger)
    assert client.get(url("setup", course)).status_code == 404
