"""The permission matrix (spec §3.3 table, §3.4 rule 5).

Every URL in the project × every persona is REALLY requested through the Django test
client, and the status code is compared with the expectation. Nothing here checks only
the shape of the table.

    302  anonymous user → redirected to the login page
    200  allowed
    404  not allowed, or the object is not yours (a 403 would reveal it exists)
    403  you can see it but may not change it (offering in a closed term)

A URL that is in the URLconf but not in ROWS fails `test_every_url_is_in_the_matrix`.

HOW TO ADD A URL (do this in the same PR that adds the URL):

    # an offering page, decorated @require_offering_access()
    Row("catalog:offering", "GET", READ_OFFERING, offering_kwargs("open_offering"), "open"),
    Row("catalog:offering", "GET", READ_OFFERING, offering_kwargs("closed_offering"), "closed"),

    # a write on an offering, decorated @require_offering_access(edit=True)
    Row("outcomes:lo_create", "POST", WRITE_OPEN, offering_kwargs("open_offering"), "open term"),
    Row(
    "outcomes:lo_create",
    "POST",
    WRITE_CLOSED,
    offering_kwargs("closed_offering"),
    "closed term",
),

    # a department page, decorated @require_role("head")
    Row("reports:department", "GET", DEPARTMENT),

Pick the expectation table from permission_world.py, or write a literal dict if the page
has its own rule. Every persona must be listed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from django.conf import settings
from django.shortcuts import resolve_url
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.accounts.tests.permission_world import (
    DEPARTMENT,
    PERSONAS,
    PUBLIC,
    READ_OFFERING,
    WRITE_CLOSED,
    WRITE_OPEN,
    World,
    build_world,
)
from apps.outcomes.models import Assessment, LearningOutcome

# Not ours: Django's admin has its own staff-only login (tested separately below), and
# the debug toolbar only exists in DEBUG.
EXTERNAL_PREFIXES = ("admin:", "djdt:")


def _no_kwargs(world: World) -> dict:
    return {}


def offering_kwargs(attr: str) -> Callable[[World], dict]:
    """URL kwargs for a page about one of the world's offerings."""
    return lambda world: {"offering_id": getattr(world, attr).pk}


@dataclass(frozen=True)
class Row:
    name: str  # namespaced URL name, e.g. "catalog:offering"
    method: str  # "GET" or "POST"
    expect: dict  # persona → expected status code
    kwargs: Callable[[World], dict] = _no_kwargs
    scenario: str = ""  # shown in the test id, e.g. "closed term"

    @property
    def id(self) -> str:
        return f"{self.name}[{self.scenario}]" if self.scenario else self.name


NOWHERE = {p: 404 for p in PERSONAS}  # the style guide only exists while DEBUG is on

# "home" redirects to the active role's home page (S2-01). Students get the welcome page
# until S3-02 builds their profile.
HOME = {
    "anonymous": 302,
    "student": 200,
    "other_student": 200,
    "instructor": 302,
    "other_instructor": 302,
    "head": 302,
    "other_head": 302,
    "admin": 302,
}
# require_role("instructor", "head"); superusers always pass.
TEACHING = {
    **NOWHERE,
    "anonymous": 302,
    "instructor": 200,
    "other_instructor": 200,
    "head": 200,
    "other_head": 200,
    "admin": 200,
}

# A /department/ page about one CSE object: the EEE head gets 404 like everyone else
# outside the program (S2-03 scopes every lookup to head_program()).
CSE_OBJECT = {**DEPARTMENT, "other_head": 404}


def _status(table: dict, allowed: int) -> dict:
    """Same people as `table`, but the allowed ones get `allowed` (e.g. 302 after a POST)."""
    return {p: (allowed if code == 200 else code) for p, code in table.items()}


def _cse_set(world):
    return {"set_id": world.program.po_sets.get(is_active=True).pk}


def _cse_po(world):
    return {"po_id": world.program.po_sets.get(is_active=True).outcomes.first().pk}


def _term(world):
    return {"term_id": world.open_offering.term_id}


def _course(world):
    return {"course_id": world.open_offering.course_id}


def _with_lo(attr: str) -> Callable[[World], dict]:
    """An LO inside one of the world's offerings (sub-object URLs, S2-04)."""

    def kwargs(world):
        offering = getattr(world, attr)
        lo, _ = LearningOutcome.objects.get_or_create(
            offering=offering, number=1, defaults={"description": "Design schemas"}
        )
        return {"offering_id": offering.pk, "lo_id": lo.pk}

    return kwargs


def _with_assessment(attr: str) -> Callable[[World], dict]:
    def kwargs(world):
        offering = getattr(world, attr)
        assessment, _ = Assessment.objects.get_or_create(
            offering=offering, name="Midterm I", defaults={"kind": "midterm"}
        )
        return {"offering_id": offering.pk, "assessment_id": assessment.pk}

    return kwargs


def _grade_cell(attr: str) -> Callable[[World], dict]:
    """One grade-sheet cell: the world's student in that offering (S2-06)."""

    def kwargs(world):
        base = _with_assessment(attr)(world)
        enrollment = getattr(world, attr).enrollments.get(student=world.users["student"])
        return {**base, "enrollment_id": enrollment.pk}

    return kwargs


def offering_rows(name, method, kwargs_for, open_expect=WRITE_OPEN, closed_expect=WRITE_CLOSED):
    """The same URL on the open and on the closed offering."""
    return [
        Row(name, method, open_expect, kwargs_for("open_offering"), "open"),
        Row(name, method, closed_expect, kwargs_for("closed_offering"), "closed"),
    ]


ROWS: list[Row] = [
    Row("healthz", "GET", PUBLIC),
    Row("home", "GET", HOME),
    Row("styleguide", "GET", NOWHERE),
    # Already logged in → sent home instead of seeing the form again.
    Row("accounts:login", "GET", {p: (200 if p == "anonymous" else 302) for p in PERSONAS}),
    Row("accounts:logout", "POST", {p: 302 for p in PERSONAS}),
    Row("accounts:switch_role", "POST", {p: 302 for p in PERSONAS}),
    # S2-09: password reset is public; a made-up token shows the "link doesn't work" page.
    Row("accounts:password_reset", "GET", PUBLIC),
    Row("accounts:password_reset_done", "GET", PUBLIC),
    Row(
        "accounts:password_reset_confirm",
        "GET",
        PUBLIC,
        lambda world: {"uidb64": "MQ", "token": "abc-123"},
        "bad token",
    ),
    Row("accounts:password_reset_complete", "GET", PUBLIC),
    Row("catalog:teaching", "GET", TEACHING),
    Row("catalog:offering", "GET", READ_OFFERING, offering_kwargs("open_offering"), "open"),
    Row("catalog:offering", "GET", READ_OFFERING, offering_kwargs("closed_offering"), "closed"),
    # S2-03: department pages
    Row("catalog:terms", "GET", DEPARTMENT),
    Row("catalog:term_edit", "GET", DEPARTMENT, _term),  # one calendar for every program
    Row("catalog:term_status", "POST", _status(DEPARTMENT, 302), _term),  # no action → message
    Row("catalog:courses", "GET", DEPARTMENT),
    Row("catalog:course_edit", "GET", CSE_OBJECT, _course),
    Row("catalog:offerings", "GET", DEPARTMENT),
    Row("catalog:offering_edit", "GET", CSE_OBJECT, offering_kwargs("open_offering"), "open"),
    Row("catalog:offering_edit", "GET", CSE_OBJECT, offering_kwargs("closed_offering"), "closed"),
    Row("catalog:enrollments", "GET", CSE_OBJECT, offering_kwargs("open_offering"), "open"),
    Row("catalog:enrollments", "GET", CSE_OBJECT, offering_kwargs("closed_offering"), "closed"),
    Row("catalog:outcomes", "GET", DEPARTMENT),
    Row("catalog:po_set", "GET", CSE_OBJECT, _cse_set),
    Row("catalog:po_set_copy", "POST", _status(CSE_OBJECT, 400), _cse_set),  # empty form
    Row("catalog:po_set_activate", "POST", _status(CSE_OBJECT, 302), _cse_set),  # already active
    Row("catalog:po_edit", "GET", CSE_OBJECT, _cse_po),
    Row("catalog:po_delete", "GET", CSE_OBJECT, _cse_po),
    # S2-04: course setup. Reads work in a closed term, writes answer 403 there.
    *offering_rows("outcomes:setup", "GET", offering_kwargs, READ_OFFERING, READ_OFFERING),
    *offering_rows("outcomes:lo_create", "GET", offering_kwargs),
    *offering_rows("outcomes:lo_edit", "GET", _with_lo),
    *offering_rows("outcomes:lo_delete", "GET", _with_lo),
    *offering_rows("outcomes:lo_reorder", "POST", offering_kwargs, _status(WRITE_OPEN, 302)),
    *offering_rows("outcomes:assessment_create", "GET", offering_kwargs),
    *offering_rows("outcomes:assessment_edit", "GET", _with_assessment),
    *offering_rows("outcomes:assessment_delete", "GET", _with_assessment),
    # S2-05: weight grids. An empty POST has no version / no cell, so the views answer 400.
    *offering_rows("outcomes:mapping", "GET", offering_kwargs, READ_OFFERING, READ_OFFERING),
    *offering_rows(
        "outcomes:save_assessment_lo", "POST", offering_kwargs, _status(WRITE_OPEN, 400)
    ),
    *offering_rows("outcomes:save_lo_po", "POST", offering_kwargs, _status(WRITE_OPEN, 400)),
    *offering_rows("outcomes:validate_cell", "POST", offering_kwargs, _status(WRITE_OPEN, 400)),
    # S2-06: grade sheet. An empty POST is a blank cell: nothing saved, the cell comes back.
    *offering_rows("grading:sheet", "GET", offering_kwargs, READ_OFFERING, READ_OFFERING),
    *offering_rows("grading:cell", "POST", _grade_cell),
]


# --------------------------------------------------------------------------- the matrix


@pytest.fixture
def world(db) -> World:
    return build_world()


@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize("row", ROWS, ids=lambda r: r.id)
def test_url_role_matrix(world, row, persona):
    client = Client()
    user = world.users[persona]
    if user is not None:
        client.force_login(user)

    url = reverse(row.name, kwargs=row.kwargs(world))
    response = getattr(client, row.method.lower())(url)

    expected = row.expect[persona]
    assert response.status_code == expected, (
        f"{row.method} {url} as {persona}: expected {expected}, got {response.status_code}"
    )
    if expected == 302 and persona == "anonymous":
        assert response["Location"].startswith(resolve_url(settings.LOGIN_URL)), (
            f"{url}: anonymous users must be sent to the login page"
        )


# --------------------------------------------------------------- the matrix stays complete


def iter_url_names(patterns, namespace=""):
    """Every route in the URLconf as a namespaced name. Unnamed routes get a marker."""
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            inner = f"{namespace}{pattern.namespace}:" if pattern.namespace else namespace
            yield from iter_url_names(pattern.url_patterns, inner)
        elif isinstance(pattern, URLPattern):
            yield (
                f"{namespace}{pattern.name}"
                if pattern.name
                else f"{namespace}<unnamed: {pattern.pattern}>"
            )


def project_url_names() -> set[str]:
    names = set(iter_url_names(get_resolver().url_patterns))
    return {n for n in names if not n.startswith(EXTERNAL_PREFIXES)}


def test_every_url_is_in_the_matrix():
    missing = project_url_names() - {row.name for row in ROWS}
    assert not missing, (
        "These URLs are not in the permission matrix. Add a Row for each one in "
        f"apps/accounts/tests/test_permission_matrix.py (unnamed routes need a name first): "
        f"{sorted(missing)}"
    )


def test_matrix_has_no_stale_rows():
    stale = {row.name for row in ROWS} - project_url_names()
    assert not stale, f"Rows for URLs that no longer exist: {sorted(stale)}"


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r.id)
def test_every_row_covers_every_persona(row):
    assert set(row.expect) == set(PERSONAS)


# ------------------------------------------------------------------------ Django's admin


@pytest.mark.parametrize(
    ("persona", "expected"),
    [("anonymous", 302), ("student", 302), ("head", 302), ("admin", 200)],
)
def test_django_admin_is_staff_only(world, persona, expected):
    client = Client()
    if world.users[persona] is not None:
        client.force_login(world.users[persona])
    assert client.get(reverse("admin:index")).status_code == expected
