import pytest
from django.urls import reverse

from apps.core.navigation import offering_tabs, safe_reverse
from apps.core.tests.factories import (
    CourseFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramFactory,
    TermFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def cse():
    return ProgramFactory(code="TST")


def _login(client, user):
    client.force_login(user)
    return client


def test_instructor_lands_on_my_courses(client, cse):
    """B1 AC 1 (instructor part)."""
    user = UserFactory()
    MembershipFactory(user=user, program=cse, role="instructor")
    response = _login(client, user).get(reverse("home"))
    assert response.status_code == 302
    assert response["Location"] == reverse("catalog:teaching")


def test_head_lands_on_department_or_offerings(client, cse):
    """B1 AC 1 (head part). Before S3-04 the offerings list stands in for the overview."""
    user = UserFactory()
    MembershipFactory(user=user, program=cse, role="head")
    response = _login(client, user).get(reverse("home"))
    expected = safe_reverse("reports:department") or safe_reverse("catalog:offerings")
    if expected:
        assert response["Location"] == expected
    else:
        assert response.status_code == 200


def test_student_lands_on_profile_or_welcome(client, cse):
    """B1 AC 1 (student part). Before S3-02 students see the welcome page."""
    user = UserFactory()
    MembershipFactory(user=user, program=cse, role="student", cohort_year=2023)
    response = _login(client, user).get(reverse("home"))
    profile = safe_reverse("student:profile")
    if profile:
        assert response["Location"] == profile
    else:
        assert response.status_code == 200
        assert "being built" in response.text


def test_user_without_role_sees_welcome(client):
    response = _login(client, UserFactory()).get(reverse("home"))
    assert response.status_code == 200
    assert "isn't linked to a program" in response.text


def test_default_role_is_head_and_switch_changes_home(client, cse):
    """B1 AC 4: a head who teaches switches views without logging out."""
    user = UserFactory()
    MembershipFactory(user=user, program=cse, role="head")
    MembershipFactory(user=user, program=cse, role="instructor")
    _login(client, user)
    client.get(reverse("home"))
    assert client.session["active_role"] == "head"

    response = client.post(reverse("accounts:switch_role"), {"role": "instructor"})
    assert response["Location"] == reverse("home")
    assert client.session["active_role"] == "instructor"
    assert client.get(reverse("home"))["Location"] == reverse("catalog:teaching")


def test_switch_to_role_not_held_is_ignored(client, cse):
    user = UserFactory()
    MembershipFactory(user=user, program=cse, role="instructor")
    _login(client, user).post(reverse("accounts:switch_role"), {"role": "head"})
    assert client.session["active_role"] == "instructor"


def test_role_removed_by_admin_falls_back_to_one_still_held(client, cse):
    user = UserFactory()
    head = MembershipFactory(user=user, program=cse, role="head")
    MembershipFactory(user=user, program=cse, role="instructor")
    _login(client, user).get(reverse("home"))
    assert client.session["active_role"] == "head"
    head.delete()
    client.get(reverse("home"))
    assert client.session["active_role"] == "instructor"


def test_head_in_instructor_mode_keeps_department_access(client, cse):
    """Active role is a preference, not a permission (S2-02 rule 1)."""
    user = UserFactory()
    MembershipFactory(user=user, program=cse, role="head")
    MembershipFactory(user=user, program=cse, role="instructor")
    _login(client, user).post(reverse("accounts:switch_role"), {"role": "instructor"})
    assert client.get(reverse("catalog:teaching")).status_code == 200
    url = safe_reverse("catalog:terms")
    if url:
        assert client.get(url).status_code == 200


def test_navbar_shows_role_items_and_switcher(client, cse):
    user = UserFactory()
    MembershipFactory(user=user, program=cse, role="head")
    MembershipFactory(user=user, program=cse, role="instructor")
    _login(client, user).post(reverse("accounts:switch_role"), {"role": "instructor"})
    html = client.get(reverse("catalog:teaching")).text
    assert "My courses" in html
    assert "View as" in html and "Department head" in html


def test_student_navbar_has_no_teaching_link(client, cse):
    user = UserFactory()
    MembershipFactory(user=user, program=cse, role="student", cohort_year=2023)
    html = _login(client, user).get(reverse("home"), follow=True).text
    assert reverse("catalog:teaching") not in html


def test_teaching_lists_only_own_offerings(client, cse):
    term = TermFactory()
    mine = OfferingFactory(course=CourseFactory(program=cse, code="CSE 311"), term=term)
    OfferingFactory(course=CourseFactory(program=cse, code="CSE 321"), term=term)
    user = UserFactory()
    MembershipFactory(user=user, program=cse, role="instructor")
    mine.instructors.add(user)
    html = _login(client, user).get(reverse("catalog:teaching")).text
    assert "CSE 311" in html and "CSE 321" not in html


def test_teaching_empty_state(client, cse):
    user = UserFactory()
    MembershipFactory(user=user, program=cse, role="instructor")
    html = _login(client, user).get(reverse("catalog:teaching")).text
    assert "not teaching any courses yet" in html


def test_offering_home_shows_header_and_closed_badge(client, cse):
    course = CourseFactory(program=cse, code="CSE 311")
    offering = OfferingFactory(course=course, term=TermFactory())
    user = UserFactory()
    MembershipFactory(user=user, program=cse, role="instructor")
    offering.instructors.add(user)
    url = reverse("catalog:offering", kwargs={"offering_id": offering.pk})
    html = _login(client, user).get(url).text
    assert "CSE 311" in html and "Term closed" not in html

    offering.term.status = "closed"
    offering.term.save()
    assert "Term closed: read-only" in client.get(url).text


def test_offering_tabs_skip_missing_pages(cse):
    offering = OfferingFactory(course=CourseFactory(program=cse), term=TermFactory())
    tabs = offering_tabs(offering, "catalog:offering")
    assert tabs[0] == {
        "label": "Overview",
        "url": reverse("catalog:offering", kwargs={"offering_id": offering.pk}),
        "active": True,
    }
    assert all(t["url"] for t in tabs)
