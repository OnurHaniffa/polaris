"""Unit tests for permissions.py, decorators.py and the student-data selectors (S2-02)."""

from __future__ import annotations

import dataclasses

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.test import RequestFactory
from django.views.defaults import permission_denied

from apps.accounts.decorators import require_offering_access, require_role
from apps.accounts.permissions import (
    OfferingPerms,
    can_edit_offering,
    can_view_offering,
    can_view_student,
    is_head,
    offering_perms,
    roles_of,
)
from apps.accounts.tests.permission_world import (
    PERSONAS,
    READ_OFFERING,
    WRITE_CLOSED,
    WRITE_OPEN,
    build_world,
)
from apps.catalog.models import Course, CourseOffering, Enrollment
from apps.catalog.selectors import visible_enrollments


@pytest.fixture
def world(db):
    return build_world()


# ------------------------------------------------------------------ roles and programs


def test_anonymous_has_no_roles():
    assert roles_of(AnonymousUser()) == set()


def test_roles_come_from_memberships(world):
    expected = {
        "student": {"student"},
        "instructor": {"instructor"},
        "head": {"head"},
        "admin": {"admin"},
    }
    for persona, roles in expected.items():
        assert roles_of(world.users[persona]) == roles


def test_head_is_specific_to_a_program(world):
    head = world.users["head"]
    assert is_head(head)
    assert is_head(head, world.program)
    assert not is_head(head, world.other_program)
    assert not is_head(world.users["instructor"])


# ------------------------------------------------------------------------- offerings


def test_instructor_is_only_authorised_on_assigned_offerings(world):
    unassigned = CourseOffering.objects.create(course=world.open_offering.course, term=world.open_offering.term, section="2")
    instructor, head = world.users["instructor"], world.users["head"]

    assert can_view_offering(instructor, world.open_offering)
    assert not can_view_offering(instructor, unassigned)
    assert can_view_offering(head, unassigned)


@pytest.mark.parametrize("persona", PERSONAS)
def test_offering_perms_follow_the_spec_table(world, persona):
    user = world.user(persona)

    open_perms = offering_perms(user, world.open_offering)
    assert open_perms.can_view == (READ_OFFERING[persona] == 200)
    assert open_perms.can_edit == (WRITE_OPEN[persona] == 200)
    assert open_perms.can_publish == open_perms.can_edit
    assert not open_perms.is_closed

    closed_perms = offering_perms(user, world.closed_offering)
    assert closed_perms.can_view == (READ_OFFERING[persona] == 200)
    assert not closed_perms.can_edit  # closed term: nobody edits, superusers included
    assert not closed_perms.can_publish
    assert closed_perms.is_closed


def test_closed_term_denies_editing_to_everyone(world):
    for persona in ("instructor", "head", "admin"):
        user = world.users[persona]
        assert can_view_offering(user, world.closed_offering)
        assert not can_edit_offering(user, world.closed_offering)
        assert can_edit_offering(user, world.open_offering)


def test_offering_perms_is_a_frozen_dataclass_with_the_spec_fields(world):
    assert {f.name for f in dataclasses.fields(OfferingPerms)} == {
        "can_view",
        "can_edit",
        "can_publish",
        "is_closed",
    }
    perms = offering_perms(world.users["head"], world.open_offering)
    with pytest.raises(dataclasses.FrozenInstanceError):
        perms.can_edit = False


# --------------------------------------------------------------------------- students


def test_who_can_view_a_students_profile(world):
    student = world.users["student"]
    allowed = {
        "anonymous": False,
        "student": True,  # themselves
        "other_student": False,  # not another student
        "instructor": False,  # spec §3.3: heads and admins only
        "other_instructor": False,
        "head": True,  # head of the student's program
        "other_head": False,  # head of a different program
        "admin": True,
    }
    for persona, ok in allowed.items():
        assert can_view_student(world.user(persona), student) is ok, persona


def test_visible_enrollments_is_scoped_to_the_user(world):
    expected_count = {
        "anonymous": 0,
        "student": 0,  # students never list a class
        "other_student": 0,
        "instructor": 1,
        "other_instructor": 0,  # teaches a different offering
        "head": 1,
        "other_head": 0,  # head of another program
        "admin": 1,
    }
    for persona, count in expected_count.items():
        rows = visible_enrollments(world.user(persona), world.open_offering)
        assert rows.count() == count, persona


def test_visible_enrollments_hides_dropped_students_by_default(world):
    Enrollment.objects.filter(offering=world.open_offering).update(status=Enrollment.Status.DROPPED)
    assert visible_enrollments(world.users["head"], world.open_offering).count() == 0
    assert visible_enrollments(world.users["head"], world.open_offering, include_dropped=True).count() == 1


# ------------------------------------------------------------------------ decorators


@require_offering_access()
def read_view(request, offering, perms_for):
    return HttpResponse(
        f"{offering.course.code}|{perms_for.can_edit}|"
        f"{CourseOffering.course.is_cached(offering)}|"
        f"{Course.program.is_cached(offering.course)}|"
        f"{CourseOffering.term.is_cached(offering)}"
    )


@require_offering_access(edit=True)
def write_view(request, offering, perms_for):
    return HttpResponse("saved")


@require_role("head")
def head_only_view(request):
    return HttpResponse("ok")


def _request(user):
    request = RequestFactory().get("/x/")
    request.user = user
    return request


def _status(view, user, **kwargs) -> int:
    try:
        return view(_request(user), **kwargs).status_code
    except Http404:
        return 404
    except PermissionDenied:
        return 403


@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize(
    ("view", "attr", "table"),
    [
        (read_view, "open_offering", READ_OFFERING),
        (read_view, "closed_offering", READ_OFFERING),
        (write_view, "open_offering", WRITE_OPEN),
        (write_view, "closed_offering", WRITE_CLOSED),
    ],
    ids=["read-open", "read-closed", "write-open", "write-closed"],
)
def test_require_offering_access_statuses(world, persona, view, attr, table):
    offering = getattr(world, attr)
    assert _status(view, world.user(persona), offering_id=offering.pk) == table[persona]


def test_missing_offering_is_a_404_not_a_403(world):
    assert _status(write_view, world.users["admin"], offering_id=999_999) == 404


def test_view_receives_offering_and_perms_with_related_rows_preloaded(world):
    response = read_view(_request(world.users["head"]), offering_id=world.open_offering.pk)
    assert response.content.decode() == "CSE 311|True|True|True|True"


def test_require_role_statuses(world):
    assert _status(head_only_view, AnonymousUser()) == 302
    assert _status(head_only_view, world.users["instructor"]) == 404
    assert _status(head_only_view, world.users["head"]) == 200
    assert _status(head_only_view, world.users["admin"]) == 200  # superuser passes


# ------------------------------------------------------------------------- 403 page


def test_closed_term_403_page_explains_why(world):
    with pytest.raises(PermissionDenied) as caught:
        write_view(_request(world.users["head"]), offering_id=world.closed_offering.pk)

    message = str(caught.value)
    assert "Fall 2025" in message
    assert "reopen" in message

    request = _request(world.users["head"])
    response = permission_denied(request, caught.value)
    body = response.content.decode()
    assert response.status_code == 403
    assert "Fall 2025 is closed" in body
    assert "department head" in body
