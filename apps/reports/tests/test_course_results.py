import pytest
from django.urls import reverse

from apps.core.tests.factories import MembershipFactory, UserFactory
from apps.core.tests.scenarios import one_lo_class

pytestmark = pytest.mark.django_db


@pytest.fixture
def klass():
    data = one_lo_class(students_scores=[(None, 80), (None, 60), (None, None)])
    instructor = UserFactory()
    MembershipFactory(user=instructor, program=data.program, role="instructor")
    data.offering.instructors.add(instructor)
    data.instructor = instructor
    return data


def test_instructor_of_offering_sees_results(client, klass):
    client.force_login(klass.instructor)
    resp = client.get(reverse("reports:results", args=[klass.offering.id]))
    assert resp.status_code == 200
    assert b"Class average" in resp.content
    assert b"70.0" in resp.content
    assert b"n = 2" in resp.content


def test_head_of_program_sees_results(client, klass):
    head = UserFactory()
    MembershipFactory(user=head, program=klass.program, role="head")
    client.force_login(head)
    assert client.get(reverse("reports:results", args=[klass.offering.id])).status_code == 200


def test_other_instructor_gets_404(client, klass):
    stranger = UserFactory()
    MembershipFactory(user=stranger, program=klass.program, role="instructor")
    client.force_login(stranger)
    assert client.get(reverse("reports:results", args=[klass.offering.id])).status_code == 404


def test_student_in_the_class_gets_404(client, klass):
    client.force_login(klass.students[0])
    assert client.get(reverse("reports:results", args=[klass.offering.id])).status_code == 404


def test_results_page_query_count_does_not_grow_with_class_size(client, klass, django_assert_max_num_queries):
    client.force_login(klass.instructor)
    with django_assert_max_num_queries(30):
        client.get(reverse("reports:results", args=[klass.offering.id]))
