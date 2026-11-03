from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.accounts.models import ProgramMembership
from apps.catalog.models import Term
from apps.core.tests.factories import (
    AssessmentFactory, EnrollmentFactory, GradeFactory, MembershipFactory, OfferingFactory,
    UserFactory,
)
from apps.grading.models import Grade

pytestmark = pytest.mark.django_db


@pytest.fixture
def course(client):
    offering = OfferingFactory(term__status=Term.Status.OPEN)
    instructor = UserFactory()
    MembershipFactory(user=instructor, program=offering.course.program,
                      role=ProgramMembership.Role.INSTRUCTOR)
    offering.instructors.add(instructor)
    a = AssessmentFactory(offering=offering, name="Midterm I", max_score=Decimal("100"))
    for score in ("90", "80", None):
        e = EnrollmentFactory(offering=offering)
        if score:
            GradeFactory(assessment=a, enrollment=e, score=Decimal(score))
    client.force_login(instructor)
    return offering, a


def _url(name, offering, a):
    return reverse(name, kwargs={"offering_id": offering.id, "assessment_id": a.id})


def test_modal_shows_counts_and_zero_warning(course, client):
    offering, a = course
    response = client.get(_url("grading:publish", offering, a), headers={"HX-Request": "true"})
    body = response.content.decode()
    assert response.status_code == 200
    assert "Publish Midterm I?" in body
    assert "<strong>2</strong> of 3 students have a score" in body
    assert "skipped, not counted as zero" in body
    assert 'name="expected_changes"' in body and 'value="2"' in body


def test_htmx_publish_redirects_client_and_reports(course, client):
    offering, a = course
    response = client.post(_url("grading:publish", offering, a), {"expected_changes": "2"},
                           headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response["HX-Redirect"] == reverse("grading:sheet", kwargs={"offering_id": offering.id})
    text = [str(m) for m in get_messages(response.wsgi_request)]
    assert text == ["Midterm I published to 2 students. "
                    "1 had no grade and were skipped (not counted as zero)."]
    assert Grade.objects.filter(published_score__isnull=False).count() == 2


def test_plain_post_falls_back_to_normal_redirect(course, client):
    offering, a = course
    response = client.post(_url("grading:publish", offering, a), {"expected_changes": "2"})
    assert response.status_code == 302


def test_stale_count_shows_error_and_publishes_nothing(course, client):
    offering, a = course
    response = client.post(_url("grading:publish", offering, a), {"expected_changes": "5"},
                           headers={"HX-Request": "true"})
    text = " ".join(str(m) for m in get_messages(response.wsgi_request))
    assert "changed while the confirmation was open" in text
    assert not Grade.objects.filter(published_score__isnull=False).exists()


def test_unpublish_short_reason_keeps_modal_open(course, client):
    offering, a = course
    client.post(_url("grading:publish", offering, a), {"expected_changes": "2"})
    response = client.post(_url("grading:unpublish", offering, a), {"reason": "no"},
                           headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert "HX-Redirect" not in response
    assert "is-invalid" in response.content.decode()
    assert Grade.objects.filter(published_score__isnull=False).count() == 2


def test_unpublish_with_reason(course, client):
    offering, a = course
    client.post(_url("grading:publish", offering, a), {"expected_changes": "2"})
    response = client.post(_url("grading:unpublish", offering, a),
                           {"reason": "Wrong answer key"}, headers={"HX-Request": "true"})
    assert "HX-Redirect" in response
    assert not Grade.objects.filter(published_score__isnull=False).exists()


def test_student_cannot_open_publish(course, client):
    offering, a = course
    student = EnrollmentFactory(offering=offering).student
    client.force_login(student)
    assert client.get(_url("grading:publish", offering, a)).status_code == 404
    assert client.post(_url("grading:publish", offering, a), {"expected_changes": "2"}).status_code == 404
    assert not Grade.objects.filter(published_score__isnull=False).exists()