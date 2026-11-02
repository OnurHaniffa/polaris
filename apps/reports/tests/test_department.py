from datetime import date

import pytest
from django.urls import reverse

from apps.catalog.models import Term
from apps.core.tests.factories import (
    CourseFactory,
    MembershipFactory,
    OfferingFactory,
    TermFactory,
    UserFactory,
)
from apps.core.tests.scenarios import one_lo_class

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    spring = TermFactory(
        code="2026S",
        name="Spring 2026",
        starts_on=date(2026, 2, 9),
        ends_on=date(2026, 6, 15),
        status=Term.Status.CLOSED,
    )
    fall = TermFactory(
        code="2026F",
        name="Fall 2026",
        starts_on=date(2026, 9, 14),
        ends_on=date(2027, 1, 22),
        status=Term.Status.OPEN,
    )
    a = one_lo_class(students_scores=[(None, 50), (None, 70), (None, 90)], term=spring)
    one_lo_class(students_scores=[(a.students[0], 30)], term=fall, po=a.po)
    head = UserFactory()
    MembershipFactory(user=head, program=a.program, role="head")
    return spring, fall, a, head


def test_defaults_to_latest_closed_term_closed_only(client, setup):
    spring, _fall, _a, head = setup
    client.force_login(head)
    resp = client.get(reverse("reports:department"))
    assert resp.status_code == 200
    assert resp.context["selected_term"] == spring
    assert resp.context["include_open_terms"] is False
    assert b"70.0" in resp.content
    assert b"67%" in resp.content


def test_toggle_changes_numbers_and_label(client, setup):
    """B10 AC2."""
    _spring, fall, _a, head = setup
    client.force_login(head)

    closed = client.get(reverse("reports:department"), {"term": fall.id})
    assert b"Fall 2026 is still open and not counted" in closed.content
    assert b"70.0" in closed.content

    with_open = client.get(reverse("reports:department"), {"term": fall.id, "include_open": "on"})
    assert b"including courses still in progress" in with_open.content
    assert b"66.7" in with_open.content


def test_offerings_list_flags_incomplete_setup(client, setup):
    _spring, fall, a, head = setup
    bare = OfferingFactory(course=CourseFactory(program=a.program, code="CSE 999"), term=fall)
    client.force_login(head)
    resp = client.get(reverse("reports:department"), {"term": fall.id})
    statuses = {o.id: s for o, s in resp.context["offerings"]}
    assert statuses[bare.id].is_complete is False
    assert b"CSE 999" in resp.content
    assert b"\xe2\x9c\x97 LOs" in resp.content  # "✗ LOs"


def test_instructor_cannot_open_department(client, setup):
    _s, _f, a, _head = setup
    teacher = UserFactory()
    MembershipFactory(user=teacher, program=a.program, role="instructor")
    client.force_login(teacher)
    assert client.get(reverse("reports:department")).status_code == 404
