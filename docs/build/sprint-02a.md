# Build guide · Sprint 2: Instructor flows (Mon 26 Oct – Sun 1 Nov)

> Part of the POlaris build guide. The spec ([`POLARIS-PROJECT-SPEC.md`](../../POLARIS-PROJECT-SPEC.md)) says **what** to build. This guide says **how**, one story at a time.
> Sprint 2 spans three files: this one (header + S2-01, S2-02, S2-03, S2-09), `sprint-02b.md` (S2-04, S2-05, S2-07) and `sprint-02c.md` (S2-06, S2-08).

## Sprint goal

By Sunday an instructor can log in, land on their course list, open a course, set up its LOs and assessments, fill both weight grids, and type draft grades. The head can run the term from the browser: terms, catalog courses, offerings with instructors, and enrollments. Every page is guarded by one permission layer, and a test proves it for every URL and every role. Everything is live on **staging**.

This is the sprint where POlaris stops being a data model and becomes an app. It is also the sprint with the most parallel work, so the merge order below matters.

## Stories

| ID | Story | Pts | Owner | File |
|---|---|---|---|---|
| S2-01 | Login / logout, role-based redirect, role switcher, navbar | 2 | C | this file |
| S2-02 | `permissions.py`, decorators, selector pattern, permission matrix test | 5 | C | this file |
| S2-03 | Head: terms, catalog, offerings, instructor assignment, enrollments, PO sets | 3 | A | this file |
| S2-04 | Instructor: LO and assessment editors + setup checklist | 3 | B | `sprint-02b.md` |
| S2-05 | Both weight grids (HTMX), validation, stale-edit detection | 5 | B | `sprint-02b.md` |
| S2-06 | Grade sheet with HTMX inline save + keyboard navigation | 5 | A | `sprint-02c.md` |
| S2-07 | Mapping lint rules L001–L006 + display | 2 | A | `sprint-02b.md` |
| S2-08 | Dockerfile, `compose.prod.yml`, VPS, CD to **staging** | 5 | C | `sprint-02c.md` |
| S2-09 | Password reset by email | 1 | B | this file |

**Planned:** 31 points (A 10 · B 9 · C 12). If Wednesday's stand-up shows we are behind, S2-07 moves to Sprint 3 first, then S2-09.

## Merge order

Every view in this sprint needs the decorators from S2-02, so that PR goes first. Everyone else starts on the parts that don't need it (services, forms, selectors, their tests) and wires views once it lands.

```
Mon ─ Tue          Tue ─ Wed               Wed ─ Fri                         any day
S2-02 (C) ───────► S2-01 (C) ────────────► S2-04 (B) ──► S2-05 (B) ──► S2-07 (A)
   │                                        S2-06 (A) (needs S2-04 assessments)
   └─────────────► S2-03 (A) (its views)    S2-09 (B)                     S2-08 (C), start Monday
```

1. **S2-02** by Tuesday noon. It contains `permissions.py`, `decorators.py`, the base selectors, `templates/403.html`, and the matrix test with its route table already listing every URL the spec plans (§4.8). Routes that don't exist yet are waiting rows; they activate automatically when the URL appears.
2. **S2-01** right after. It needs `roles_of()` from S2-02.
3. **S2-03**, **S2-09**, **S2-04** in any order once the decorators exist.
4. **S2-05** and **S2-06** need the LO and assessment models filled by S2-04's editors for manual testing. Their code doesn't import S2-04.
5. **S2-07** last (it reads the grids from S2-05).
6. **S2-08** is independent. Start it Monday. It is the riskiest story of the sprint (*Test in the Wild*, Getting Real Ch. 6).

## What must work by Sunday (on staging)

1. Log in as **Dr. Can Aydın** (`can.aydin@acibadem.edu.tr`, seed password) → land on *My courses* → open CSE 311 → add LOs and assessments → fill both grids → type grades into the sheet.
2. Log in as the **head** → create a term → add a course → create an offering, assign Dr. Aydın → enroll a student by hand → close the term → as Dr. Aydın, every edit page of that offering now answers *403 This term is closed*.
3. Log in as **Elif** → try `/department/terms/` and `/offerings/<CSE 311 id>/setup/` → both 404.
4. Request a password reset → the email (staging: console log of the `web` container) contains a link that works once.
5. `uv run pytest apps/accounts/tests/test_permission_matrix.py -q` passes, and the "every URL is in the matrix" test passes.

---

## S2-02 · Permissions, decorators, selector pattern, permission matrix test

**Points:** 5 · **Owner:** Person C · **Branch:** `feature/S2-02-permissions` · **Depends on:** S1-01, S1-02, S1-08

> This section comes before S2-01 because it merges first. S2-01 imports `roles_of()` from here.

### Goal

Put every permission decision in one module, enforce it with two decorators, and prove it with one parametrised test that hits every URL as every role. This delivers §3.3 (the permission matrix) and §3.4 (the enforcement rules). It is the evidence for the report claim "students cannot see each other's grades".

Three rules shape everything below:

1. **Memberships decide access, not the role switcher.** The active role (S2-01) only chooses your home page and navbar. A head who has switched to instructor mode can still open `/department/`. If access followed the switcher, people would get 404s for pages they are allowed to see, and the matrix would depend on session state.
2. **Can't see it → 404. Can see it but can't change it → 403.** An instructor asking for another instructor's course gets 404, so the URL doesn't confirm the course exists (§3.4 rule 3). An instructor whose own course is in a **closed term** gets 403 with "This term is closed": they know the course exists, so hiding it would only confuse them.
3. **Superusers pass every role check.** Admin is `is_superuser` (§3.2). On a closed term, though, nobody edits through the app, admin included. The admin exception in §3.3 is the Django admin site at `/admin/`. One rule with no special case is easier to test, and the services refuse closed-term writes anyway (`ensure_term_open`).

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/accounts/permissions.py` | create | `ROLE_ORDER`, `roles_of`, `ordered_roles`, `is_head`, `head_program`, `head_program_or_404`, `can_view_offering`, `can_edit_offering`, `can_view_student`, `OfferingPerms`, `offering_perms` |
| `apps/accounts/decorators.py` | create | `require_role`, `require_offering_access` |
| `apps/catalog/selectors.py` | create | `active_po_set`, `offerings_for_user`, `teaching_offerings`, `visible_enrollments` |
| `templates/403.html` | create | "You can see this course but can't change it" page |
| `config/urls.py` | modify | no change yet; S2-01 adds the app includes |
| `apps/accounts/tests/test_permissions.py` | create | unit tests for every helper |
| `apps/accounts/tests/test_decorators.py` | create | 302 / 404 / 403 behaviour of both decorators |
| `apps/accounts/tests/routes.py` | create | the route table: every URL in §4.8 with its expected result per role |
| `apps/accounts/tests/test_permission_matrix.py` | create | the matrix test, the closed-term test, the "every URL is listed" test |

### Steps

#### Step 1: `apps/accounts/permissions.py`

Every function takes the user first. They are plain functions, not methods on `User`, so the whole policy reads top to bottom in one file. That file is what a reviewer (or the TA) checks.

`roles_of()` caches its answer on the user object. One request asks it several times (the middleware, the context processor, a decorator). Django builds a fresh `request.user` for every request, so the cache can't go stale between requests. In unit tests, create memberships *before* the first call. If you create one after, call `forget_roles(user)`.

```python
# apps/accounts/permissions.py
"""Every permission decision in POlaris. Views never check access by hand (spec §3.4)."""
from __future__ import annotations

from dataclasses import dataclass

from django.http import Http404

from apps.accounts.models import ProgramMembership
from apps.catalog.models import Program, Term

Role = ProgramMembership.Role

# Order used for the default active role and for the role switcher.
ROLE_ORDER = (Role.HEAD.value, Role.INSTRUCTOR.value, Role.STUDENT.value, "admin")
_CACHE_ATTR = "_polaris_roles"


def roles_of(user) -> set[str]:
    """Role names this user holds in any program, plus "admin" for superusers."""
    if not getattr(user, "is_authenticated", False):
        return set()
    cached = getattr(user, _CACHE_ATTR, None)
    if cached is None:
        cached = frozenset(
            set(user.memberships.values_list("role", flat=True))
            | ({"admin"} if user.is_superuser else set())
        )
        setattr(user, _CACHE_ATTR, cached)
    return set(cached)


def forget_roles(user) -> None:
    """Drop the cached roles (tests that add a membership after a check)."""
    if hasattr(user, _CACHE_ATTR):
        delattr(user, _CACHE_ATTR)


def ordered_roles(user) -> list[str]:
    held = roles_of(user)
    return [r for r in ROLE_ORDER if r in held]


def is_head(user, program: Program | None = None) -> bool:
    """True if the user holds a head membership (in `program`, or in any program)."""
    if not getattr(user, "is_authenticated", False):
        return False
    qs = user.memberships.filter(role=Role.HEAD)
    if program is not None:
        qs = qs.filter(program=program)
    return qs.exists()


def head_program(user) -> Program | None:
    """The program a head manages on /department/ pages.

    One head membership per person is the normal case. With several, the first by
    code wins until T2.6 adds a program switcher. Superusers without a head
    membership get the first program so /department/ works for them too."""
    if not getattr(user, "is_authenticated", False):
        return None
    membership = (
        user.memberships.filter(role=Role.HEAD)
        .select_related("program")
        .order_by("program__code")
        .first()
    )
    if membership:
        return membership.program
    if user.is_superuser:
        return Program.objects.order_by("code").first()
    return None


def head_program_or_404(user) -> Program:
    """head_program for views: a head page with no program to show is a 404, not a crash."""
    program = head_program(user)
    if program is None:
        raise Http404("No program")
    return program


def _teaches(user, offering) -> bool:
    return offering.instructors.filter(pk=user.pk).exists()


def can_view_offering(user, offering) -> bool:
    """Superuser, head of the offering's program, or one of its instructors."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return is_head(user, offering.course.program) or _teaches(user, offering)


def _is_closed(offering) -> bool:
    return offering.term.status == Term.Status.CLOSED


def can_edit_offering(user, offering) -> bool:
    """Viewers may edit unless the term is closed. Closed means closed for everyone
    in the app, superusers included (they use /admin/ for emergencies)."""
    return can_view_offering(user, offering) and not _is_closed(offering)


def can_view_student(user, student) -> bool:
    """Yourself, a superuser, or the head of a program the student belongs to."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.pk == student.pk:
        return True
    headed = user.memberships.filter(role=Role.HEAD).values("program")
    return student.memberships.filter(role=Role.STUDENT, program__in=headed).exists()


@dataclass(frozen=True)
class OfferingPerms:
    """What the current user may do on one offering. Passed to templates as `perms_for`.
    Hiding buttons with it is cosmetic; the decorator is the real check (§3.4 rule 4)."""
    can_view: bool
    can_edit: bool
    can_publish: bool
    is_closed: bool


def offering_perms(user, offering) -> OfferingPerms:
    view = can_view_offering(user, offering)
    closed = _is_closed(offering)
    edit = view and not closed
    # Publishing equals editing for now. T2.8 (TA role) makes them differ.
    return OfferingPerms(can_view=view, can_edit=edit, can_publish=edit, is_closed=closed)
```

Templates read it as `{% if perms_for.can_edit %}`. §3.4 writes `perms_for.offering.can_edit`. The flat form is what we build, and the spec gets the same fix in this PR.

#### Step 2: `apps/accounts/decorators.py`

Two decorators, and every view gets exactly one of them.

- `require_role(*roles)`: the user holds at least one of the roles in any program, or is a superuser. Use it for pages that aren't about one offering, such as `/teaching/` and `/department/…`. Department views then scope their queries to `head_program(request.user)`.
- `require_offering_access(edit=False)`: for every URL with an `offering_id`. It loads the offering once with the joins the permission check needs, then passes `offering=` and `perms_for=` to the view. The view doesn't receive `offering_id` (the decorator removes it), so views can't reload the offering by accident without the check.

URLs that identify a course through another object, like `/ingestion/<job_id>/`, pass a `lookup` function that turns the URL kwargs into an offering id. The view still gets `job_id` and loads the job itself, filtered by `offering=offering`.

Both decorators also handle anonymous users by redirecting to login, so `@login_required` on top is belt and braces. We keep it anyway, because §3.4 rule 1 says every view shows both and reviewers check for it.

```python
# apps/accounts/decorators.py
from __future__ import annotations

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import Http404

from apps.accounts.permissions import offering_perms, roles_of
from apps.catalog.models import CourseOffering

CLOSED_TERM_MESSAGE = "This term is closed. Ask the department head to reopen it if something must change."


def require_role(*roles: str):
    """Allow users who hold any of `roles` (in any program). Superusers always pass.
    Everyone else gets 404, so the page's existence isn't confirmed (§3.4 rule 3)."""
    wanted = set(roles)

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if user.is_superuser or roles_of(user) & wanted:
                return view(request, *args, **kwargs)
            raise Http404("Page not found")

        return wrapped

    return decorator


def require_offering_access(*, edit: bool = False, lookup=None):
    """Guard a view about one offering.

    The offering id comes from the `offering_id` URL kwarg (removed before calling the
    view), or from `lookup(**kwargs)` for URLs like /ingestion/<job_id>/.
    Can't view → 404. edit=True and the term is closed → 403.
    The view receives `offering=` and `perms_for=` as keyword arguments."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            offering_id = lookup(**kwargs) if lookup else kwargs.pop("offering_id")
            if offering_id is None:
                raise Http404("Page not found")
            offering = (
                CourseOffering.objects.select_related("course__program", "term")
                .filter(pk=offering_id)
                .first()
            )
            if offering is None:
                raise Http404("Page not found")
            perms = offering_perms(request.user, offering)
            if not perms.can_view:
                raise Http404("Page not found")
            if edit and not perms.can_edit:
                raise PermissionDenied(CLOSED_TERM_MESSAGE)
            return view(request, *args, offering=offering, perms_for=perms, **kwargs)

        return wrapped

    return decorator
```

**The rule for sub-objects.** The decorator checks the offering. The view must check that the LO, assessment, enrollment or job in the URL **belongs to that offering**:

```python
lo = get_object_or_404(LearningOutcome, pk=lo_id, offering=offering)   # right
lo = get_object_or_404(LearningOutcome, pk=lo_id)                       # WRONG: any LO of any course
```

Without the `offering=` filter, an instructor could edit another course's LO by putting its id into their own course's URL. The matrix test can't catch this, because it only uses ids from the course being tested. Reviewers check it on every PR (add it to the PR template's checklist).

A `lookup` function for jobs (S5/S6 adds it next to the ingestion views):

```python
# apps/ingestion/views.py (example of the lookup pattern)
def _offering_of_job(*, job_id, **_):
    return IngestionJob.objects.filter(pk=job_id).values_list("offering_id", flat=True).first()


@login_required
@require_offering_access(edit=False, lookup=_offering_of_job)
def job(request, job_id, offering, perms_for):
    job = get_object_or_404(IngestionJob, pk=job_id, offering=offering)
    ...
```

#### Step 3: the selector pattern, `apps/catalog/selectors.py`

A selector is a read function that takes `user` first and returns only what that user may see. Views call selectors instead of writing `Model.objects.filter(...)`, so scoping happens in one place (§3.4 rule 2). If the user may not see anything, a selector returns an empty queryset, not an exception. The decorator has already done the loud refusal.

```python
# apps/catalog/selectors.py
from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from apps.accounts.models import ProgramMembership
from apps.accounts.permissions import can_view_offering
from apps.catalog.models import CourseOffering, Enrollment, Program, ProgramOutcomeSet

Role = ProgramMembership.Role


def active_po_set(program: Program) -> ProgramOutcomeSet:
    """The program's active PO set. The partial unique index guarantees at most one."""
    return ProgramOutcomeSet.objects.get(program=program, is_active=True)


def offerings_for_user(user, *, term=None) -> QuerySet[CourseOffering]:
    """Every offering the user may open: all of them for superusers, their programs'
    offerings for heads, the ones they teach for instructors. Newest term first."""
    qs = CourseOffering.objects.select_related("course", "term")
    if not user.is_superuser:
        headed = user.memberships.filter(role=Role.HEAD).values("program")
        qs = qs.filter(Q(course__program__in=headed) | Q(instructors=user)).distinct()
    if term is not None:
        qs = qs.filter(term=term)
    return qs.order_by("-term__starts_on", "course__code", "section")


def teaching_offerings(user) -> QuerySet[CourseOffering]:
    """Offerings the user personally teaches (the /teaching/ page), with student counts."""
    return (
        CourseOffering.objects.filter(instructors=user)
        .select_related("course", "term")
        .annotate(
            student_count=Count(
                "enrollments", filter=Q(enrollments__status=Enrollment.Status.ENROLLED)
            )
        )
        .order_by("-term__starts_on", "course__code", "section")
    )


def visible_enrollments(user, offering, *, include_dropped: bool = False) -> QuerySet[Enrollment]:
    """Students of one offering, ordered by student number. Empty if the user can't view it."""
    if not can_view_offering(user, offering):
        return Enrollment.objects.none()
    qs = offering.enrollments.select_related("student")
    if not include_dropped:
        qs = qs.filter(status=Enrollment.Status.ENROLLED)
    return qs.order_by("student__student_number", "student__last_name")
```

`setup_status()` and `po_set_for_student()` also belong in this file, but S2-04 and S3-02 write them.

#### Step 4: `templates/403.html`

Django renders `403.html` from the template dirs whenever a view raises `PermissionDenied`. The exception's message is available as `{{ exception }}`.

```django
{% extends "base.html" %}
{% block title %}Read-only · POlaris{% endblock %}
{% block content %}
<div class="container py-5" style="max-width: 40rem">
  <h1 class="h3 mb-3"><span aria-hidden="true">🔒</span> You can't change this</h1>
  <p class="lead">{{ exception|default:"You don't have permission to change this page." }}</p>
  <p class="text-body-secondary">You can still view everything. Use the back button, or go to your
    <a href="{% url 'home' %}">home page</a>.</p>
</div>
{% endblock %}
```

#### Step 5: the route table, `apps/accounts/tests/routes.py`

The matrix test has two halves: a **world** (a tiny department with one object of each kind) and a **route table** (every URL with what each role should get). The table is plain data. That makes it reviewable: the TA can read it next to §3.3 and check every line.

**Six test roles:**

| Key | Who | Why this role exists |
|---|---|---|
| `anon` | Not logged in | Every non-public page must redirect to login |
| `student` | Student enrolled in offering A | Must see only their own things |
| `instructor` | Teaches offering A (the course in every URL) | "own" in §3.3 |
| `other_instructor` | Teaches offering B, not A | Proves "own" really means own |
| `head` | Head of the program | §3.3 head column |
| `admin` | Superuser, no memberships | §3.3 admin column |

**Five outcomes:**

| Code | Meaning | Assertion |
|---|---|---|
| `OK` | Allowed | status in the route's `ok` set (GET default `{200}`, POST default `{200, 302, 400}`) |
| `DENY` | Not allowed, existence hidden | 404 |
| `LOGIN` | Anonymous | 302 to `settings.LOGIN_URL` |
| `CLOSED` | (closed-term test only) | 403 |

POST routes are sent with an empty body. An allowed user then sees a form error (200), a redirect (302), or a 400. We are testing the guard, not the form.

**The table already lists every URL in §4.8**, each tagged with the story that builds it. A row whose URL name doesn't exist yet is skipped at collection time, and it starts running the day the URL appears. So **you don't need to write rows for later stories: they are already here.** Your job when you add a view is:

1. Check that your URL's row exists and its expectations match §3.3. If you changed the plan, change the row in the same PR.
2. Set `edit=True` on the row exactly when the view uses `@require_offering_access(edit=True)`.
3. If your view needs an object the world doesn't have yet, add a method to `World`.

A URL that exists but has **no row** fails `test_every_url_is_in_the_matrix`. That's the "forgot to think about permissions" alarm from §3.4 rule 5.

```python
# apps/accounts/tests/routes.py
"""Every URL in POlaris and who may open it (spec §3.3, §4.8). Plain data, reviewed like code."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

OK, DENY, LOGIN = "OK", "DENY", "LOGIN"
ROLES = ("anon", "student", "instructor", "other_instructor", "head", "admin")


def _expect(**allowed: str) -> dict[str, str]:
    base = {"anon": LOGIN, "student": DENY, "instructor": DENY,
            "other_instructor": DENY, "head": DENY, "admin": DENY}
    base.update(allowed)
    return base


PUBLIC = dict.fromkeys(ROLES, OK)
ANY_USER = _expect(student=OK, instructor=OK, other_instructor=OK, head=OK, admin=OK)
STUDENT = _expect(student=OK, admin=OK)                          # own profile: §3.3 lets admin open it too
STUDENT_OWN = _expect(student=OK)      # needs the student's own enrollment or cohort; admin has neither → 404
TEACHING = _expect(instructor=OK, other_instructor=OK, head=OK, admin=OK)
OFFERING_STAFF = _expect(instructor=OK, head=OK, admin=OK)      # "own" + head + admin
HEAD = _expect(head=OK, admin=OK)
EXPORT_OWNER = _expect(instructor=OK)                            # only whoever created the export


def _none(world) -> dict:
    return {}


@dataclass(frozen=True)
class Route:
    name: str
    expect: Mapping[str, str]
    kwargs: Callable[..., dict] = _none
    method: str = "GET"
    ok: frozenset[int] | None = None
    edit: bool = False          # True ⇔ the view uses @require_offering_access(edit=True)
    story: str = ""
    htmx: bool = False          # send the HX-Request header (for partial-only views)

    @property
    def ok_codes(self) -> frozenset[int]:
        if self.ok is not None:
            return self.ok
        return frozenset({200}) if self.method == "GET" else frozenset({200, 302, 400})


def off(w):
    return {"offering_id": w.offering.pk}


def off_lo(w):
    return {"offering_id": w.offering.pk, "lo_id": w.lo.pk}


def off_a(w):
    return {"offering_id": w.offering.pk, "assessment_id": w.assessment.pk}


def off_cell(w):
    return {"offering_id": w.offering.pk, "assessment_id": w.assessment.pk,
            "enrollment_id": w.enrollment.pk}


def grade_job(w):
    return {"offering_id": w.offering.pk, "job_id": w.grade_job().pk}


def syllabus_job(w):
    return {"job_id": w.syllabus_job().pk}


P = frozenset  # short alias for ok sets

ROUTES: list[Route] = [
    # ---- core / accounts (S2-01, S2-09) ----
    Route("home", ANY_USER, ok=P({302}), story="S2-01"),
    Route("accounts:login", PUBLIC, ok=P({200, 302}), story="S2-01"),
    Route("accounts:logout", PUBLIC, method="POST", ok=P({302}), story="S2-01"),
    Route("accounts:switch_role", ANY_USER, method="POST", ok=P({302}), story="S2-01"),
    Route("accounts:password_reset", PUBLIC, story="S2-09"),
    Route("accounts:password_reset_done", PUBLIC, story="S2-09"),
    Route("accounts:password_reset_confirm", PUBLIC,
          kwargs=lambda w: {"uidb64": "MQ", "token": "set-password"}, ok=P({200}), story="S2-09"),
    Route("accounts:password_reset_complete", PUBLIC, story="S2-09"),
    # ---- student pages (S3-02, T1.5, T2.4) ----
    Route("student:profile", STUDENT, story="S3-02"),
    Route("student:po_detail", STUDENT_OWN, kwargs=lambda w: {"po_id": w.po.pk}, story="S3-02"),
    Route("student:course", STUDENT_OWN, kwargs=off, story="S3-02"),
    Route("student:transcript", STUDENT_OWN, ok=P({200, 302}), story="S8-04"),
    # ---- teaching + offering home (S2-01) ----
    Route("catalog:teaching", TEACHING, story="S2-01"),
    Route("catalog:offering", OFFERING_STAFF, kwargs=off, story="S2-01"),
    # ---- course setup (S2-04) ----
    Route("outcomes:setup", OFFERING_STAFF, kwargs=off, story="S2-04"),
    Route("outcomes:lo_create", OFFERING_STAFF, kwargs=off, edit=True, story="S2-04"),
    Route("outcomes:lo_edit", OFFERING_STAFF, kwargs=off_lo, edit=True, story="S2-04"),
    Route("outcomes:lo_delete", OFFERING_STAFF, kwargs=off_lo, edit=True, story="S2-04"),
    Route("outcomes:lo_reorder", OFFERING_STAFF, kwargs=off, method="POST", edit=True, story="S2-04"),
    Route("outcomes:assessment_create", OFFERING_STAFF, kwargs=off, edit=True, story="S2-04"),
    Route("outcomes:assessment_edit", OFFERING_STAFF, kwargs=off_a, edit=True, story="S2-04"),
    Route("outcomes:assessment_delete", OFFERING_STAFF, kwargs=off_a, edit=True, story="S2-04"),
    # ---- mapping (S2-05, T1.3) ----
    Route("outcomes:mapping", OFFERING_STAFF, kwargs=off, story="S2-05"),
    Route("outcomes:save_assessment_lo", OFFERING_STAFF, kwargs=off, method="POST", edit=True, story="S2-05"),
    Route("outcomes:save_lo_po", OFFERING_STAFF, kwargs=off, method="POST", edit=True, story="S2-05"),
    Route("outcomes:validate_cell", OFFERING_STAFF, kwargs=off, method="POST", edit=True,
          htmx=True, story="S2-05"),
    Route("outcomes:suggest_lo_po", OFFERING_STAFF, kwargs=off, method="POST", edit=True, story="S6-04"),
    Route("outcomes:accept_suggestions", OFFERING_STAFF, kwargs=off, method="POST", edit=True, story="S6-04"),
    # ---- grades (S2-06, S3-01, T1.1, T1.4) ----
    Route("grading:sheet", OFFERING_STAFF, kwargs=off, story="S2-06"),
    Route("grading:cell", OFFERING_STAFF, kwargs=off_cell, method="POST", edit=True,
          htmx=True, story="S2-06"),
    Route("grading:cell_history", OFFERING_STAFF, kwargs=off_cell, htmx=True, story="S7-05"),
    Route("grading:publish", OFFERING_STAFF, kwargs=off_a, edit=True, story="S3-01"),
    Route("grading:unpublish", OFFERING_STAFF, kwargs=off_a, edit=True, story="S3-01"),
    Route("grading:upload", OFFERING_STAFF, kwargs=off, edit=True, story="S4-03"),
    Route("grading:upload_map", OFFERING_STAFF, kwargs=grade_job, edit=True, ok=P({200, 302}), story="S4-03"),
    Route("grading:upload_preview", OFFERING_STAFF, kwargs=grade_job, edit=True, ok=P({200, 302}), story="S4-03"),
    Route("grading:upload_confirm", OFFERING_STAFF, kwargs=grade_job, method="POST", edit=True, story="S4-03"),
    # ---- syllabus wizard (S6-01..03) ----
    Route("ingestion:start", OFFERING_STAFF, kwargs=off, edit=True, story="S6-01"),
    Route("ingestion:job", OFFERING_STAFF, kwargs=syllabus_job, ok=P({200, 302}), story="S6-01"),
    Route("ingestion:status", OFFERING_STAFF, kwargs=syllabus_job, htmx=True, story="S6-01"),
    Route("ingestion:review", OFFERING_STAFF, kwargs=syllabus_job, edit=True, ok=P({200, 302}), story="S6-02"),
    Route("ingestion:apply", OFFERING_STAFF, kwargs=syllabus_job, method="POST", edit=True, story="S6-03"),
    Route("ingestion:discard", OFFERING_STAFF, kwargs=syllabus_job, method="POST", edit=True, story="S6-03"),
    # ---- reports (S3-03, S3-04, T1.4, T1.6, T1.7) ----
    Route("reports:results", OFFERING_STAFF, kwargs=off, story="S3-03"),
    Route("reports:history", OFFERING_STAFF, kwargs=off, story="S7-05"),
    Route("reports:course_export", OFFERING_STAFF, kwargs=lambda w: {**off(w), "fmt": "pdf"},
          method="POST", story="S7-03"),
    Route("reports:export_status", EXPORT_OWNER, kwargs=lambda w: {"export_id": w.export_job().pk},
          story="S7-03"),
    Route("reports:department", HEAD, story="S3-04"),
    Route("reports:department_student", HEAD, kwargs=lambda w: {"user_id": w.users["student"].pk},
          story="S3-04"),
    Route("reports:department_history", HEAD, story="S7-05"),
    Route("reports:department_export", HEAD, kwargs=lambda w: {"fmt": "pdf"}, method="POST", story="S7-03"),
    # ---- department: outcomes (S2-03) ----
    Route("catalog:outcomes", HEAD, story="S2-03"),
    Route("catalog:po_set", HEAD, kwargs=lambda w: {"set_id": w.po_set.pk}, story="S2-03"),
    Route("catalog:po_set_copy", HEAD, kwargs=lambda w: {"set_id": w.po_set.pk}, method="POST", story="S2-03"),
    Route("catalog:po_set_activate", HEAD, kwargs=lambda w: {"set_id": w.po_set.pk}, method="POST", story="S2-03"),
    Route("catalog:po_edit", HEAD, kwargs=lambda w: {"po_id": w.po.pk}, story="S2-03"),
    Route("catalog:po_delete", HEAD, kwargs=lambda w: {"po_id": w.po.pk}, story="S2-03"),
    # ---- department: terms, courses, offerings, enrollments (S2-03, S3-05) ----
    Route("catalog:terms", HEAD, story="S2-03"),
    Route("catalog:term_edit", HEAD, kwargs=lambda w: {"term_id": w.term.pk}, story="S2-03"),
    Route("catalog:term_status", HEAD, kwargs=lambda w: {"term_id": w.term.pk}, method="POST", story="S2-03"),
    Route("catalog:courses", HEAD, story="S2-03"),
    Route("catalog:course_edit", HEAD, kwargs=lambda w: {"course_id": w.course.pk}, story="S2-03"),
    Route("catalog:offerings", HEAD, story="S2-03"),
    Route("catalog:offering_edit", HEAD, kwargs=off, story="S2-03"),
    Route("catalog:enrollments", HEAD, kwargs=off, story="S2-03"),
    Route("catalog:enrollment_import", HEAD, story="S3-05"),
    Route("catalog:enrollment_import_preview", HEAD, kwargs=lambda w: {"job_id": w.enrollment_job().pk},
          ok=P({200, 302}), story="S3-05"),
    Route("catalog:enrollment_import_confirm", HEAD, kwargs=lambda w: {"job_id": w.enrollment_job().pk},
          method="POST", story="S3-05"),
]

# URL names deliberately not in the matrix, with the reason.
NOT_IN_MATRIX = {
    "healthz": "public; touches Redis, tested in apps/core/tests/test_healthz.py",
}
NOT_IN_MATRIX_PREFIXES = ("admin:", "djdt:")   # Django admin has its own staff check; debug toolbar is dev-only
```

The password-reset confirm row uses a fake uid and token. Django answers 200 with an "invalid link" page, which is all the matrix needs to know: the page is public. S2-09 tests the real link.

#### Step 6: the world and the matrix test

The world is built fresh for every test (function-scoped database, rolled back after). It costs about 30 inserts. 68 routes × 6 roles is about 400 cases, around 15 seconds locally. That's acceptable for the most important test we have. If it ever gets slow, the fix is pytest-xdist, not a shared world: shared state between permission tests hides bugs.

Jobs and exports are created **lazily** by methods (`w.syllabus_job()`), because their models arrive in later sprints. A row only calls its method once the URL exists, and by then the model exists too.

```python
# apps/accounts/tests/test_permission_matrix.py
"""Every URL × every role (spec §3.3–3.4). The evidence that students can't see each other's data."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pytest
from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.accounts.tests.routes import (
    DENY, LOGIN, NOT_IN_MATRIX, NOT_IN_MATRIX_PREFIXES, OK, ROLES, ROUTES, Route,
)
from apps.catalog.models import Term
from apps.core.tests.factories import (
    AssessmentFactory, CourseFactory, EnrollmentFactory, LearningOutcomeFactory,
    MembershipFactory, OfferingFactory, ProgramFactory, ProgramOutcomeFactory,
    ProgramOutcomeSetFactory, TermFactory, UserFactory,
)


# ---------- which URL names exist right now ----------

def _url_names(patterns=None, namespace: str = ""):
    if patterns is None:
        patterns = get_resolver().url_patterns
    for p in patterns:
        if isinstance(p, URLResolver):
            ns = f"{namespace}{p.namespace}:" if p.namespace else namespace
            yield from _url_names(p.url_patterns, ns)
        elif isinstance(p, URLPattern) and p.name:
            yield f"{namespace}{p.name}"


EXISTING = set(_url_names())
ACTIVE = [r for r in ROUTES if r.name in EXISTING]          # rows for URLs built so far
EDIT_ROUTES = [r for r in ACTIVE if r.edit]


# ---------- the world ----------

@dataclass
class World:
    program: object
    po_set: object
    po: object
    term: object
    course: object
    offering: object
    other_offering: object
    enrollment: object
    lo: object
    assessment: object
    users: dict = field(default_factory=dict)

    def syllabus_job(self):
        from apps.ingestion.models import IngestionJob
        return IngestionJob.objects.create(
            offering=self.offering, kind=IngestionJob.Kind.SYLLABUS, file="uploads/test/syllabus.pdf",
            original_filename="syllabus.pdf", created_by=self.users["instructor"],
        )

    def grade_job(self):
        from apps.ingestion.models import IngestionJob
        return IngestionJob.objects.create(
            offering=self.offering, kind=IngestionJob.Kind.GRADES, file="uploads/test/grades.csv",
            original_filename="grades.csv", created_by=self.users["instructor"],
        )

    def enrollment_job(self):
        from apps.ingestion.models import IngestionJob
        return IngestionJob.objects.create(
            offering=self.offering, kind=IngestionJob.Kind.ENROLLMENTS, file="uploads/test/class.csv",
            original_filename="class.csv", created_by=self.users["head"],
        )

    def export_job(self):
        from apps.reports.models import ExportJob
        return ExportJob.objects.create(
            kind=ExportJob.Kind.COURSE, fmt=ExportJob.Format.PDF, offering=self.offering,
            created_by=self.users["instructor"],
        )


def build_world() -> World:
    program = ProgramFactory(code="TST")
    po_set = ProgramOutcomeSetFactory(program=program, label="2023 curriculum",
                                      effective_from_year=2020, is_active=True)
    po = ProgramOutcomeFactory(po_set=po_set, number=1, short_name="Math & science")
    term = TermFactory(code="2026F", name="Fall 2026", starts_on=date(2026, 9, 21),
                       ends_on=date(2027, 1, 15), status=Term.Status.OPEN)
    course = CourseFactory(program=program, code="CSE 311")
    other_course = CourseFactory(program=program, code="CSE 321")
    offering = OfferingFactory(course=course, term=term)
    other_offering = OfferingFactory(course=other_course, term=term)

    users = {
        "student": UserFactory(email="student@test.edu", student_number="2023001"),
        "instructor": UserFactory(email="instructor@test.edu"),
        "other_instructor": UserFactory(email="other@test.edu"),
        "head": UserFactory(email="head@test.edu"),
        "admin": UserFactory(email="admin@test.edu", is_superuser=True, is_staff=True),
    }
    MembershipFactory(user=users["student"], program=program, role="student", cohort_year=2023)
    MembershipFactory(user=users["instructor"], program=program, role="instructor")
    MembershipFactory(user=users["other_instructor"], program=program, role="instructor")
    MembershipFactory(user=users["head"], program=program, role="head")
    offering.instructors.add(users["instructor"])
    other_offering.instructors.add(users["other_instructor"])

    enrollment = EnrollmentFactory(offering=offering, student=users["student"])
    lo = LearningOutcomeFactory(offering=offering, number=1)
    assessment = AssessmentFactory(offering=offering, name="Midterm I")
    return World(program, po_set, po, term, course, offering, other_offering,
                 enrollment, lo, assessment, users)


@pytest.fixture
def world(db) -> World:
    return build_world()


def _request(client, world: World, role: str, route: Route):
    if role != "anon":
        client.force_login(world.users[role])
    url = reverse(route.name, kwargs=route.kwargs(world))
    headers = {"HX-Request": "true"} if route.htmx else {}
    send = client.get if route.method == "GET" else client.post
    return send(url, headers=headers), url


def _check(response, expected: str, route: Route, role: str, url: str):
    where = f"{route.method} {url} as {role} (row {route.name})"
    if expected == LOGIN:
        assert response.status_code == 302, f"{where}: expected login redirect, got {response.status_code}"
        assert response["Location"].startswith(reverse(settings.LOGIN_URL)), where
    elif expected == DENY:
        assert response.status_code == 404, f"{where}: expected 404, got {response.status_code}"
    else:
        assert expected == OK, f"bad expectation {expected!r} in {route.name}"
        assert response.status_code in route.ok_codes, (
            f"{where}: expected one of {sorted(route.ok_codes)}, got {response.status_code}"
        )


# ---------- the tests ----------

@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("route", ACTIVE, ids=lambda r: r.name)
def test_permission_matrix(client, world, route, role):
    response, url = _request(client, world, role, route)
    _check(response, route.expect[role], route, role, url)


@pytest.mark.parametrize("role", ["instructor", "head", "admin"])
@pytest.mark.parametrize("route", EDIT_ROUTES, ids=lambda r: r.name)
def test_closed_term_blocks_every_edit_route(client, world, route, role):
    """B3 AC 3: closing a term makes every page of its offerings read-only, for everyone."""
    world.term.status = Term.Status.CLOSED
    world.term.save(update_fields=["status"])
    response, url = _request(client, world, role, route)
    assert response.status_code == 403, f"{route.method} {url} as {role}: got {response.status_code}"


def test_every_url_is_in_the_matrix():
    """§3.4 rule 5: adding a URL without deciding who may open it fails CI."""
    listed = {r.name for r in ROUTES} | set(NOT_IN_MATRIX)
    missing = sorted(
        name for name in EXISTING
        if name not in listed and not name.startswith(NOT_IN_MATRIX_PREFIXES)
    )
    assert not missing, f"Add these URLs to apps/accounts/tests/routes.py: {missing}"


def test_matrix_rows_are_well_formed():
    names = [r.name for r in ROUTES]
    assert len(names) == len(set(names)), "duplicate route rows"
    for r in ROUTES:
        assert set(r.expect) == set(ROLES), f"{r.name} must give an expectation for every role"
        assert r.method in {"GET", "POST"}, r.name
```

Why `test_matrix_rows_are_well_formed` exists: a row with a typo in a role key would otherwise raise `KeyError` inside one parametrised case, which is easy to misread as a permission bug.

**The report evidence.** Run `uv run pytest apps/accounts/tests/test_permission_matrix.py -q --co | tail -1` at the end of each sprint and record "N permission cases" in `docs/process/velocity.md`. The number growing from about 150 now to about 420 at feature complete is a good line for CSE 311 report Section 5.

#### Step 7: unit tests for the helpers

The matrix proves the wiring. These tests prove the rules themselves, including cases the matrix world doesn't have (a student of another program, a dropped enrollment).

```python
# apps/accounts/tests/test_permissions.py
from datetime import date

import pytest

from apps.accounts.permissions import (
    can_edit_offering, can_view_offering, can_view_student, forget_roles, head_program,
    head_program_or_404, is_head, offering_perms, ordered_roles, roles_of,
)
from django.http import Http404

from apps.catalog.models import Enrollment, Term
from apps.catalog.selectors import offerings_for_user, teaching_offerings, visible_enrollments
from apps.core.tests.factories import (
    CourseFactory, EnrollmentFactory, MembershipFactory, OfferingFactory, ProgramFactory,
    TermFactory, UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def cse():
    return ProgramFactory(code="TST")


@pytest.fixture
def offering(cse):
    term = TermFactory(starts_on=date(2026, 9, 21), ends_on=date(2027, 1, 15), status=Term.Status.OPEN)
    return OfferingFactory(course=CourseFactory(program=cse, code="CSE 311"), term=term)


def test_roles_of_lists_memberships_and_admin(cse):
    user = UserFactory(is_superuser=True)
    MembershipFactory(user=user, program=cse, role="instructor")
    MembershipFactory(user=user, program=cse, role="head")
    assert roles_of(user) == {"instructor", "head", "admin"}
    assert ordered_roles(user) == ["head", "instructor", "admin"]


def test_roles_of_anonymous_is_empty():
    from django.contrib.auth.models import AnonymousUser
    assert roles_of(AnonymousUser()) == set()


def test_roles_cache_can_be_forgotten(cse):
    user = UserFactory()
    assert roles_of(user) == set()
    MembershipFactory(user=user, program=cse, role="head")
    assert roles_of(user) == set()            # cached
    forget_roles(user)
    assert roles_of(user) == {"head"}


def test_is_head_is_per_program(cse):
    other = ProgramFactory(code="BME")
    head = UserFactory()
    MembershipFactory(user=head, program=cse, role="head")
    assert is_head(head) and is_head(head, cse)
    assert not is_head(head, other)


def test_head_program(cse):
    head = UserFactory()
    MembershipFactory(user=head, program=cse, role="head")
    assert head_program(head) == cse
    assert head_program(UserFactory()) is None
    assert head_program(UserFactory(is_superuser=True)) == cse
    with pytest.raises(Http404):
        head_program_or_404(UserFactory())


def test_instructor_sees_only_own_offering(offering, cse):
    mine, theirs = UserFactory(), UserFactory()
    offering.instructors.add(mine)
    assert can_view_offering(mine, offering)
    assert not can_view_offering(theirs, offering)


def test_head_of_other_program_cannot_view(offering):
    outsider = UserFactory()
    MembershipFactory(user=outsider, program=ProgramFactory(code="BME"), role="head")
    assert not can_view_offering(outsider, offering)


def test_closed_term_blocks_edit_for_everyone(offering):
    instructor, admin = UserFactory(), UserFactory(is_superuser=True)
    offering.instructors.add(instructor)
    offering.term.status = Term.Status.CLOSED
    offering.term.save()
    assert can_view_offering(instructor, offering) and not can_edit_offering(instructor, offering)
    assert can_view_offering(admin, offering) and not can_edit_offering(admin, offering)
    perms = offering_perms(instructor, offering)
    assert perms.is_closed and not perms.can_edit and not perms.can_publish


def test_can_view_student(cse):
    student, other_student, head = UserFactory(), UserFactory(), UserFactory()
    MembershipFactory(user=student, program=cse, role="student", cohort_year=2023)
    MembershipFactory(user=head, program=cse, role="head")
    bme_head = UserFactory()
    MembershipFactory(user=bme_head, program=ProgramFactory(code="BME"), role="head")
    assert can_view_student(student, student)
    assert not can_view_student(other_student, student)
    assert can_view_student(head, student)
    assert not can_view_student(bme_head, student)


def test_visible_enrollments_scoped_and_drops_hidden(offering):
    instructor, stranger = UserFactory(), UserFactory()
    offering.instructors.add(instructor)
    kept = EnrollmentFactory(offering=offering)
    dropped = EnrollmentFactory(offering=offering, status=Enrollment.Status.DROPPED)
    assert list(visible_enrollments(instructor, offering)) == [kept]
    assert set(visible_enrollments(instructor, offering, include_dropped=True)) == {kept, dropped}
    assert not visible_enrollments(stranger, offering).exists()


def test_offerings_for_user(offering, cse):
    head, instructor, nobody = UserFactory(), UserFactory(), UserFactory()
    MembershipFactory(user=head, program=cse, role="head")
    offering.instructors.add(instructor)
    other = OfferingFactory(course=CourseFactory(program=cse, code="CSE 321"), term=offering.term)
    assert set(offerings_for_user(head)) == {offering, other}
    assert list(offerings_for_user(instructor)) == [offering]
    assert not offerings_for_user(nobody).exists()
    assert list(teaching_offerings(instructor))[0].student_count == 0
```

```python
# apps/accounts/tests/test_decorators.py
import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from apps.accounts.decorators import require_offering_access, require_role
from apps.catalog.models import Term
from apps.core.tests.factories import (
    CourseFactory, MembershipFactory, OfferingFactory, ProgramFactory, TermFactory, UserFactory,
)

pytestmark = pytest.mark.django_db
rf = RequestFactory()


@require_role("head")
def head_view(request):
    return HttpResponse("ok")


@require_offering_access(edit=True)
def edit_view(request, offering, perms_for):
    return HttpResponse(f"{offering.pk}:{perms_for.can_edit}")


def _get(user, **kwargs):
    from django.contrib.auth.models import AnonymousUser
    request = rf.get("/x/")
    request.user = user or AnonymousUser()
    return request


def test_require_role_redirects_anonymous():
    response = head_view(_get(None))
    assert response.status_code == 302


def test_require_role_404_for_wrong_role():
    from django.http import Http404
    with pytest.raises(Http404):
        head_view(_get(UserFactory()))


def test_require_role_allows_head_and_superuser():
    cse = ProgramFactory()
    head = UserFactory()
    MembershipFactory(user=head, program=cse, role="head")
    assert head_view(_get(head)).status_code == 200
    assert head_view(_get(UserFactory(is_superuser=True))).status_code == 200


def test_offering_access_passes_offering_and_perms():
    offering = OfferingFactory(course=CourseFactory(), term=TermFactory(status=Term.Status.OPEN))
    instructor = UserFactory()
    offering.instructors.add(instructor)
    response = edit_view(_get(instructor), offering_id=offering.pk)
    assert response.content == f"{offering.pk}:True".encode()


def test_offering_access_404_for_missing_and_foreign():
    from django.http import Http404
    offering = OfferingFactory(course=CourseFactory(), term=TermFactory(status=Term.Status.OPEN))
    with pytest.raises(Http404):
        edit_view(_get(UserFactory()), offering_id=offering.pk)
    with pytest.raises(Http404):
        edit_view(_get(UserFactory(is_superuser=True)), offering_id=999_999)


def test_offering_access_403_when_closed():
    from django.core.exceptions import PermissionDenied
    offering = OfferingFactory(course=CourseFactory(), term=TermFactory(status=Term.Status.CLOSED))
    instructor = UserFactory()
    offering.instructors.add(instructor)
    with pytest.raises(PermissionDenied):
        edit_view(_get(instructor), offering_id=offering.pk)
```

### Check it works

```bash
uv run pytest apps/accounts -q
# expected: all pass. The matrix runs only rows whose URLs exist. On this branch that is almost nothing
# (S2-01 adds home, login, logout, teaching), so most of the value shows up as the next PRs merge.
# "test_every_url_is_in_the_matrix" passes.

uv run python manage.py shell -c "
from apps.accounts.tests.routes import ROUTES; print(len(ROUTES), 'rows planned')"
# 68 rows planned
```

Then prove the alarm works: add `path("secret/", views.home, name="secret")` to `config/urls.py`, run `uv run pytest apps/accounts/tests/test_permission_matrix.py::test_every_url_is_in_the_matrix`, see it fail and name `secret`, then remove the line.

### Done when

| Requirement | Proved by |
|---|---|
| §3.4 rule 1: every view decorated | review checklist + matrix (an undecorated view returns 200 for `anon` instead of 302) |
| §3.4 rule 2: student data through selectors that take `user` | `test_visible_enrollments_scoped_and_drops_hidden`, `test_offerings_for_user` |
| §3.4 rule 3: 404 not 403 for things you can't see | `test_permission_matrix` (`DENY` = 404), `test_offering_access_404_for_missing_and_foreign` |
| §3.4 rule 5: every URL × every role | `test_permission_matrix`, `test_every_url_is_in_the_matrix` |
| §3.3 closed-term rule | `test_closed_term_blocks_every_edit_route`, `test_closed_term_blocks_edit_for_everyone` |
| B8 AC 3 / report claim "students can't see each other" | `test_can_view_student` + `student:*` rows once S3-02 lands |

### Commits and PR

```
Add permission helpers for offerings, students and heads (#21)
Add require_role and require_offering_access decorators (#21)
Add catalog selectors scoped by user (#21)
Add permission matrix test with route table for every planned URL (#21)
```

PR title: **Permissions layer and URL × role matrix test (S2-02)**. Ask both teammates to review this one, not just one: everyone will use these decorators all term.

---

## S2-01 · Login, role-based home, role switcher, navbar

**Points:** 2 · **Owner:** Person C · **Branch:** `feature/S2-01-login-home-nav` · **Depends on:** S1-01, S1-09, S2-02

### Goal

A user logs in with their email, lands on the page that fits their role, and sees a navbar with only the links their role needs. Someone who is both head and instructor switches between the two views without logging out. This delivers B1 AC 1, 2, 4 and 5. AC 3, password reset, is S2-09. The story also builds the two pages every instructor flow starts from: **My courses** (`/teaching/`) and the **offering home** (`/offerings/<id>/`) with its tab bar. S2-04 adds the setup checklist to the offering home.

**What the active role is, and isn't.** The active role is a preference stored in the session. It picks your home page and navbar, and nothing else. Access is decided by your memberships (S2-02). A head in instructor mode can still type `/department/` and get in, which is correct: they *are* the head.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `config/settings/base.py` | modify | `LOGIN_URL`, `LOGOUT_REDIRECT_URL`, middleware, context processor |
| `config/urls.py` | modify | include `accounts`, `catalog` (and the other apps as they arrive) |
| `apps/core/middleware.py` | create | `ActiveRoleMiddleware` |
| `apps/core/context_processors.py` | create | `navigation(request)` |
| `apps/core/navigation.py` | create | `safe_reverse`, `nav_items_for`, `offering_tabs` |
| `apps/core/views.py` | modify | `home` |
| `apps/core/templates/core/welcome.html` | create | fallback home while a role's real home page doesn't exist yet |
| `apps/accounts/forms.py` | create | `EmailAuthenticationForm` |
| `apps/accounts/views.py` | create | `LoginView`, `switch_role` |
| `apps/accounts/urls.py` | create | login, logout, switch role (S2-09 adds password reset) |
| `apps/accounts/templates/accounts/login.html` | create | login page |
| `templates/includes/navbar.html` | create | role-aware navbar with role switcher and logout |
| `templates/base.html` | modify | include the navbar |
| `apps/catalog/urls.py` | create | `teaching`, `offering` (S2-03 adds the department URLs) |
| `apps/catalog/views.py` | create | `teaching`, `offering_home` |
| `apps/catalog/templates/catalog/teaching.html` | create | My courses |
| `apps/catalog/templates/catalog/offering_home.html` | create | offering header + tabs + overview |
| `templates/includes/offering_header.html` | create | course title, term badge, tabs; reused by every offering page |
| `apps/core/tests/test_home_and_nav.py` | create | tests |
| `apps/accounts/tests/test_login.py` | create | tests |

### Steps

#### Step 1: settings

`LOGIN_URL` in §10.3 says `"login"`, but our URL is namespaced, so it must be `"accounts:login"`. The spec gets the same fix in this PR. Logout is POST-only since Django 5, so the navbar uses a small form, not a link.

```python
# config/settings/base.py  (change / add these lines)
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "accounts:login"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.ActiveRoleMiddleware",          # needs request.user and the session
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

TEMPLATES[0]["OPTIONS"]["context_processors"] += ["apps.core.context_processors.navigation"]
```

#### Step 2: the middleware

It runs on every request, after authentication. It reads the role from the session. If the stored role is missing or no longer held (an admin removed a membership), it falls back to the first role in `ROLE_ORDER`. So a fresh login lands as head if you're a head.

```python
# apps/core/middleware.py
from apps.accounts.permissions import ordered_roles

SESSION_KEY = "active_role"


class ActiveRoleMiddleware:
    """Sets request.active_role and request.available_roles (spec §4.8).
    The active role picks the home page and navbar only; access is decided by memberships."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_role = None
        request.available_roles = []
        if request.user.is_authenticated:
            roles = ordered_roles(request.user)
            chosen = request.session.get(SESSION_KEY)
            if chosen not in roles:
                chosen = roles[0] if roles else None
                if chosen:
                    request.session[SESSION_KEY] = chosen
                else:
                    request.session.pop(SESSION_KEY, None)
            request.active_role = chosen
            request.available_roles = roles
        return self.get_response(request)
```

#### Step 3: navigation helpers and the context processor

Some nav targets don't exist yet. *My profile* arrives in S3-02, *Department* in S3-04. `safe_reverse` returns `None` for a URL name that doesn't exist, and the item is left out. So the navbar grows by itself as stories merge, and nobody edits it again. The same trick drives the home redirect and the offering tabs.

```python
# apps/core/navigation.py
from __future__ import annotations

from django.urls import NoReverseMatch, reverse

ROLE_LABELS = {"head": "Department head", "instructor": "Instructor", "student": "Student", "admin": "Admin"}

# (label, url name) per active role, in navbar order
NAV = {
    "student": [("My profile", "student:profile")],
    "instructor": [("My courses", "catalog:teaching")],
    "head": [
        ("Overview", "reports:department"),
        ("Offerings", "catalog:offerings"),
        ("Terms", "catalog:terms"),
        ("Courses", "catalog:courses"),
        ("Outcomes", "catalog:outcomes"),
        ("My courses", "catalog:teaching"),
    ],
    "admin": [("Offerings", "catalog:offerings"), ("Django admin", "admin:index")],
}

# Each tab: (label, url name). Tabs whose view doesn't exist yet are hidden.
OFFERING_TABS = [
    ("Overview", "catalog:offering"),
    ("Setup", "outcomes:setup"),
    ("Mapping", "outcomes:mapping"),
    ("Grades", "grading:sheet"),
    ("Results", "reports:results"),
    ("History", "reports:history"),
]


def safe_reverse(name: str, **kwargs) -> str | None:
    try:
        return reverse(name, kwargs=kwargs or None)
    except NoReverseMatch:
        return None


def nav_items_for(role: str | None, current_path: str) -> list[dict]:
    items = []
    for label, name in NAV.get(role or "", []):
        url = safe_reverse(name)
        if url:
            items.append({"label": label, "url": url, "active": current_path.startswith(url)})
    return items


def offering_tabs(offering, current: str) -> list[dict]:
    """Tabs for the offering pages. `current` is the url name of the page being shown."""
    tabs = []
    for label, name in OFFERING_TABS:
        url = safe_reverse(name, offering_id=offering.pk)
        if url:
            tabs.append({"label": label, "url": url, "active": name == current})
    return tabs
```

```python
# apps/core/context_processors.py
from apps.core.navigation import ROLE_LABELS, nav_items_for


def navigation(request):
    role = getattr(request, "active_role", None)
    roles = getattr(request, "available_roles", [])
    return {
        "active_role": role,
        "active_role_label": ROLE_LABELS.get(role, ""),
        "available_roles": [(r, ROLE_LABELS[r]) for r in roles],
        "nav_items": nav_items_for(role, request.path),
    }
```

#### Step 4: the home view

Each role has a list of candidate pages, tried in order. A head goes to the department overview once S3-04 builds it, and to the offerings list until then. A student goes to their profile. Before S3-02 exists, students and anyone with no role at all get the welcome page instead of a crash.

```python
# apps/core/views.py  (add; healthz from Sprint 0 stays)
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch

ROLE_HOME = {
    "head": ("reports:department", "catalog:offerings"),
    "instructor": ("catalog:teaching",),
    "student": ("student:profile",),
    "admin": ("catalog:offerings", "admin:index"),
}


@login_required
def home(request):
    """Send each user to the page that fits their active role (B1 AC 1)."""
    for name in ROLE_HOME.get(request.active_role, ()):
        try:
            return redirect(name)
        except NoReverseMatch:
            continue
    return render(request, "core/welcome.html")
```

```django
{# apps/core/templates/core/welcome.html #}
{% extends "base.html" %}
{% block title %}Welcome · POlaris{% endblock %}
{% block content %}
<div class="container py-5" style="max-width: 40rem">
  <h1 class="h3">Welcome, {{ request.user.first_name|default:request.user.email }}</h1>
  {% if active_role %}
    <p class="lead">Your {{ active_role_label|lower }} pages are being built. They will appear here automatically.</p>
  {% else %}
    <p class="lead">Your account isn't linked to a program yet.</p>
    <p>Ask the department head to add you. Until then there is nothing for you to see here.</p>
  {% endif %}
</div>
{% endblock %}
```

The `home` view gets the `ANY_USER` row with `ok={302}` in the route table. A user with no role gets 200 from the welcome page, which the matrix doesn't cover because every matrix user has a role. `test_user_without_role_sees_welcome` covers it below.

#### Step 5: the login form and views

`AuthenticationForm` already uses `USERNAME_FIELD`, which is `email` on our `User`, so the field named `username` actually holds an email. We relabel it and give it an email input. Django's default error text already avoids saying which part was wrong. We replace it with the exact wording from B1 AC 2. Inactive accounts get the same message, because "This account is inactive" would confirm the email exists.

```python
# apps/accounts/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm

GENERIC_LOGIN_ERROR = "Email or password is incorrect."


class EmailAuthenticationForm(AuthenticationForm):
    error_messages = {"invalid_login": GENERIC_LOGIN_ERROR, "inactive": GENERIC_LOGIN_ERROR}

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "University email"
        self.fields["username"].widget = forms.EmailInput(
            attrs={"autocomplete": "email", "autofocus": True, "class": "form-control"}
        )
        self.fields["password"].widget.attrs.update({"class": "form-control"})
```

`switch_role` only accepts a role the user really holds. Anything else is ignored with a warning, because a forged POST shouldn't silently do something. After switching, it goes home, because the page you were on may not make sense in the other role.

```python
# apps/accounts/views.py
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from apps.accounts.forms import EmailAuthenticationForm
from apps.accounts.permissions import ordered_roles
from apps.core.middleware import SESSION_KEY
from apps.core.navigation import ROLE_LABELS


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


@login_required
@require_POST
def switch_role(request):
    """Change which hat the user is wearing (B1 AC 4). Pure preference: access is unchanged."""
    role = request.POST.get("role", "")
    if role in ordered_roles(request.user):
        request.session[SESSION_KEY] = role
        messages.info(request, f"You are now viewing POlaris as: {ROLE_LABELS[role]}.")
    else:
        messages.warning(request, "You don't have that role.")
    return redirect("home")
```

`LoginView` already handles `?next=` safely. It only follows URLs on our own host, which covers B1 AC 5 with no extra code.

```python
# apps/accounts/urls.py
from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("role/", views.switch_role, name="switch_role"),
    # S2-09 adds the four password-reset URLs here.
]
```

```python
# config/urls.py
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

urlpatterns = [
    path("", core_views.home, name="home"),
    path("healthz", core_views.healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.catalog.urls")),
    # Added by later stories, in this order:
    # path("", include("apps.outcomes.urls")),    S2-04
    # path("", include("apps.grading.urls")),     S2-06
    # path("", include("apps.reports.urls")),     S3-02 (also holds the student: namespace)
    # path("", include("apps.ingestion.urls")),   S6-01
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
```

Every app's `urls.py` contains full paths (`"offerings/<int:offering_id>/setup/"`), all included at `""`. Then the path you see in `urls.py` is the path in the browser, which makes `grep` work. Note for S3-02: the `student:` namespace lives in `apps/reports/urls_student.py`, included with `path("me/", include("apps.reports.urls_student"))`.

#### Step 6: templates for login and the navbar

```django
{# apps/accounts/templates/accounts/login.html #}
{% extends "base.html" %}
{% block title %}Log in · POlaris{% endblock %}
{% block content %}
<div class="container py-5" style="max-width: 26rem">
  <h1 class="h3 mb-4">Log in to POlaris</h1>
  <form method="post" novalidate>
    {% csrf_token %}
    <input type="hidden" name="next" value="{{ next }}">
    {% if form.non_field_errors %}
      <div class="alert alert-danger" role="alert">{{ form.non_field_errors.0 }}</div>
    {% endif %}
    <div class="mb-3">
      <label class="form-label" for="{{ form.username.id_for_label }}">{{ form.username.label }}</label>
      {{ form.username }}
    </div>
    <div class="mb-3">
      <label class="form-label" for="{{ form.password.id_for_label }}">Password</label>
      {{ form.password }}
    </div>
    <button type="submit" class="btn btn-primary w-100">Log in</button>
  </form>
  {% url 'accounts:password_reset' as reset_url %}
  {% if reset_url %}
    <p class="mt-3 text-center"><a href="{{ reset_url }}">Forgot your password?</a></p>
  {% endif %}
  <p class="mt-4 text-body-secondary small">Accounts are created by the department. There is no public sign-up.</p>
</div>
{% endblock %}
```

`{% url … as var %}` doesn't raise when the name is missing; it just sets an empty value. That's why the login page works before S2-09 merges.

```django
{# templates/includes/navbar.html #}
<nav class="navbar navbar-expand-md border-bottom bg-body-tertiary" aria-label="Main">
  <div class="container-fluid">
    <a class="navbar-brand fw-semibold" href="{% url 'home' %}">POlaris</a>
    {% if user.is_authenticated %}
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#nav-main"
              aria-controls="nav-main" aria-expanded="false" aria-label="Toggle navigation">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="nav-main">
        <ul class="navbar-nav me-auto">
          {% for item in nav_items %}
            <li class="nav-item">
              <a class="nav-link{% if item.active %} active{% endif %}" href="{{ item.url }}"
                 {% if item.active %}aria-current="page"{% endif %}>{{ item.label }}</a>
            </li>
          {% endfor %}
        </ul>
        <ul class="navbar-nav">
          <li class="nav-item dropdown">
            <button class="nav-link dropdown-toggle btn btn-link" data-bs-toggle="dropdown" aria-expanded="false">
              {{ user.get_full_name|default:user.email }}
              {% if active_role_label %}<span class="badge text-bg-secondary ms-1">{{ active_role_label }}</span>{% endif %}
            </button>
            <ul class="dropdown-menu dropdown-menu-end">
              {% if available_roles|length > 1 %}
                <li><h6 class="dropdown-header">View as</h6></li>
                {% for value, label in available_roles %}
                  <li>
                    <form method="post" action="{% url 'accounts:switch_role' %}">
                      {% csrf_token %}
                      <button class="dropdown-item{% if value == active_role %} active{% endif %}"
                              name="role" value="{{ value }}"
                              {% if value == active_role %}aria-current="true"{% endif %}>{{ label }}</button>
                    </form>
                  </li>
                {% endfor %}
                <li><hr class="dropdown-divider"></li>
              {% endif %}
              <li>
                <form method="post" action="{% url 'accounts:logout' %}">
                  {% csrf_token %}
                  <button class="dropdown-item">Log out</button>
                </form>
              </li>
            </ul>
          </li>
        </ul>
      </div>
    {% endif %}
  </div>
</nav>
```

In `templates/base.html` (from S1-09), replace whatever navbar is there with one line, directly after `<body …>`:

```django
{% include "includes/navbar.html" %}
```

Leave the rest of `base.html` alone: the CSRF `hx-headers` on `<body>`, the messages and the content block all stay as S1-09 wrote them.

#### Step 7: My courses and the offering home

`teaching` lists only courses the user personally teaches. A head who teaches nothing sees an empty state that points to the department's offerings page instead. *The Blank Slate* (Getting Real Ch. 9): an empty page should say what to do next.

```python
# apps/catalog/views.py  (first two views; S2-03 adds the department views below them)
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.decorators import require_offering_access, require_role
from apps.catalog.selectors import teaching_offerings, visible_enrollments
from apps.core.navigation import offering_tabs, safe_reverse


@login_required
@require_role("instructor", "head")
def teaching(request):
    offerings = list(teaching_offerings(request.user))
    return render(request, "catalog/teaching.html", {
        "offerings": offerings,
        "department_offerings_url": safe_reverse("catalog:offerings"),
    })


@login_required
@require_offering_access()
def offering_home(request, offering, perms_for):
    return render(request, "catalog/offering_home.html", {
        "offering": offering,
        "perms_for": perms_for,
        "tabs": offering_tabs(offering, "catalog:offering"),
        "student_count": visible_enrollments(request.user, offering).count(),
    })
```

```python
# apps/catalog/urls.py
from django.urls import path

from apps.catalog import views

app_name = "catalog"

urlpatterns = [
    path("teaching/", views.teaching, name="teaching"),
    path("offerings/<int:offering_id>/", views.offering_home, name="offering"),
    # S2-03 adds the /department/ URLs here.
]
```

```django
{# apps/catalog/templates/catalog/teaching.html #}
{% extends "base.html" %}
{% block title %}My courses · POlaris{% endblock %}
{% block content %}
<div class="container py-4">
  <h1 class="h3 mb-4">My courses</h1>
  {% if offerings %}
    <div class="table-responsive">
      <table class="table align-middle">
        <thead>
          <tr><th scope="col">Course</th><th scope="col">Term</th><th scope="col">Section</th>
              <th scope="col" class="text-end">Students</th><th scope="col">Status</th></tr>
        </thead>
        <tbody>
          {% for o in offerings %}
            <tr>
              <td><a href="{% url 'catalog:offering' offering_id=o.pk %}">{{ o.course.code }} · {{ o.course.title }}</a></td>
              <td>{{ o.term.name }}</td>
              <td>{{ o.section }}</td>
              <td class="text-end tabular-nums">{{ o.student_count }}</td>
              <td>
                {% if o.term.status == "closed" %}<span class="badge text-bg-secondary">🔒 Closed</span>
                {% elif o.term.status == "planned" %}<span class="badge text-bg-info">Planned</span>
                {% else %}<span class="badge text-bg-success">Open</span>{% endif %}
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  {% else %}
    {% include "includes/empty_state.html" with title="You're not teaching any courses yet" message="When the department head assigns you to a course offering, it appears here." only %}
    {% if department_offerings_url %}
      <p class="text-center"><a href="{{ department_offerings_url }}">See all the department's offerings</a></p>
    {% endif %}
  {% endif %}
</div>
{% endblock %}
```

> `includes/empty_state.html` comes from S1-09. If its parameters differ from `title` / `message`, use S1-09's names. S2-04 adds a *Setup* column to this table using `setup_status()`.

The offering header is its own include, because every offering page (setup, mapping, grades, results, history) shows the same title, term badge and tabs.

```django
{# templates/includes/offering_header.html — use with: offering, tabs, perms_for #}
<header class="mb-4">
  <p class="text-body-secondary mb-1">{{ offering.term.name }} · Section {{ offering.section }}</p>
  <h1 class="h3 mb-2">{{ offering.course.code }} · {{ offering.course.title }}
    {% if perms_for.is_closed %}
      <span class="badge text-bg-secondary align-middle fs-6">🔒 Term closed: read-only</span>
    {% endif %}
  </h1>
  <ul class="nav nav-tabs">
    {% for tab in tabs %}
      <li class="nav-item">
        <a class="nav-link{% if tab.active %} active{% endif %}" href="{{ tab.url }}"
           {% if tab.active %}aria-current="page"{% endif %}>{{ tab.label }}</a>
      </li>
    {% endfor %}
  </ul>
</header>
```

```django
{# apps/catalog/templates/catalog/offering_home.html #}
{% extends "base.html" %}
{% block title %}{{ offering.course.code }} · POlaris{% endblock %}
{% block content %}
<div class="container py-4">
  {% include "includes/offering_header.html" with offering=offering tabs=tabs perms_for=perms_for only %}
  <div class="row g-3">
    <div class="col-md-4">
      <div class="card"><div class="card-body">
        <h2 class="h6 text-body-secondary">Students enrolled</h2>
        <p class="display-6 mb-0 tabular-nums">{{ student_count }}</p>
      </div></div>
    </div>
    <div class="col-md-8">
      {# S2-04 puts the setup checklist card here: {% include "includes/setup_checklist.html" ... %} #}
      <div class="card"><div class="card-body">
        <h2 class="h6 text-body-secondary">Instructors</h2>
        <ul class="list-unstyled mb-0">
          {% for person in offering.instructors.all %}<li>{{ person.get_full_name }}</li>
          {% empty %}<li class="text-body-secondary">No instructor assigned yet.</li>{% endfor %}
        </ul>
      </div></div>
    </div>
  </div>
</div>
{% endblock %}
```

### Tests

```python
# apps/core/tests/test_home_and_nav.py
import pytest
from django.urls import reverse

from apps.core.navigation import offering_tabs, safe_reverse
from apps.core.tests.factories import (
    CourseFactory, MembershipFactory, OfferingFactory, ProgramFactory, TermFactory, UserFactory,
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
    expected = safe_reverse("reports:department") or reverse("catalog:offerings")
    assert _login(client, user).get(reverse("home"))["Location"] == expected


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


def test_offering_tabs_skip_missing_pages(cse):
    offering = OfferingFactory(course=CourseFactory(program=cse), term=TermFactory())
    tabs = offering_tabs(offering, "catalog:offering")
    assert tabs[0] == {"label": "Overview", "url": reverse("catalog:offering", kwargs={"offering_id": offering.pk}),
                       "active": True}
    assert all(t["url"] for t in tabs)
```

```python
# apps/accounts/tests/test_login.py
import pytest
from django.urls import reverse

from apps.accounts.forms import GENERIC_LOGIN_ERROR
from apps.core.tests.factories import MembershipFactory, ProgramFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_login_with_email(client):
    user = UserFactory(email="can.aydin@acibadem.edu.tr")
    user.set_password("correct horse")
    user.save()
    MembershipFactory(user=user, program=ProgramFactory(), role="instructor")
    response = client.post(reverse("accounts:login"),
                           {"username": "can.aydin@acibadem.edu.tr", "password": "correct horse"})
    assert response.status_code == 302
    assert response["Location"] == reverse("home")


@pytest.mark.parametrize("email,password", [
    ("can.aydin@acibadem.edu.tr", "wrong"),          # right email, wrong password
    ("nobody@acibadem.edu.tr", "correct horse"),     # unknown email
])
def test_wrong_credentials_give_one_generic_message(client, email, password):
    """B1 AC 2: the message doesn't reveal whether the email exists."""
    user = UserFactory(email="can.aydin@acibadem.edu.tr")
    user.set_password("correct horse")
    user.save()
    response = client.post(reverse("accounts:login"), {"username": email, "password": password})
    assert response.status_code == 200
    assert GENERIC_LOGIN_ERROR in response.text


def test_logged_out_user_is_sent_to_login_then_back(client):
    """B1 AC 5."""
    target = reverse("catalog:teaching")
    response = client.get(target)
    assert response.status_code == 302
    assert response["Location"] == f"{reverse('accounts:login')}?next={target}"

    user = UserFactory(email="x@acibadem.edu.tr")
    user.set_password("pw-123456")
    user.save()
    MembershipFactory(user=user, program=ProgramFactory(), role="instructor")
    response = client.post(f"{reverse('accounts:login')}?next={target}",
                           {"username": "x@acibadem.edu.tr", "password": "pw-123456", "next": target})
    assert response["Location"] == target


def test_logout_is_post_only(client):
    client.force_login(UserFactory())
    assert client.get(reverse("accounts:logout")).status_code == 405
    assert client.post(reverse("accounts:logout"))["Location"] == reverse("accounts:login")
```

### Check it works

1. `uv run python manage.py seed_demo` (S1-10), then `uv run python manage.py runserver`.
2. Open `/teaching/` while logged out → redirected to `/login/?next=/teaching/`.
3. Log in as Dr. Can Aydın → back on *My courses*, with his seeded offerings listed.
4. Log out (navbar menu) → log in as the head. Make sure the seed gives the head an instructor membership too, or add one in `/admin/`. → navbar shows *Offerings, Terms, …* and a *View as* section → choose *Instructor* → you land on *My courses*, and the badge says *Instructor*.
5. Type a wrong password → "Email or password is incorrect." Type an email that doesn't exist → the same message.
6. Open an offering from *My courses* → title, term badge, and only the tabs whose pages exist.

### Done when

| AC | Proved by |
|---|---|
| B1 AC 1: lands on the right page per role | `test_instructor_lands_on_my_courses`, `test_head_lands_on_department_or_offerings`, `test_student_lands_on_profile_or_welcome` |
| B1 AC 2: generic login error | `test_wrong_credentials_give_one_generic_message` |
| B1 AC 4: switch roles without logging out | `test_default_role_is_head_and_switch_changes_home` |
| B1 AC 5: login then back to requested page | `test_logged_out_user_is_sent_to_login_then_back` |
| Navbar is role-aware | `test_navbar_shows_role_items_and_switcher`, `test_student_navbar_has_no_teaching_link` |
| Rows `home`, `accounts:login`, `accounts:logout`, `accounts:switch_role`, `catalog:teaching`, `catalog:offering` pass in the matrix | `test_permission_matrix` |

### Commits and PR

```
Add email login with a single generic error message (#22)
Remember the active role in the session and redirect home by role (#22)
Add role-aware navbar with role switcher and POST logout (#22)
Add My courses page and offering header with tabs (#22)
```

PR title: **Login, role-based home and navbar (S2-01)**

---

## S2-03 · Head: terms, catalog, offerings, enrollments and PO sets

**Points:** 3 · **Owner:** Person A · **Branch:** `feature/S2-03-department-catalog` · **Depends on:** S1-02, S1-04, S1-05, S2-02

> Three points is tight for this much CRUD. Most of it is the same pattern five times, so after terms the rest goes quickly. If it spills over, enrollments move into S3-05, which reuses the same service anyway. Re-estimate at refinement if the team disagrees.

### Goal

The head runs the department from the browser:

- open, close and reopen terms; reopening asks for a reason, which goes into the audit trail;
- maintain catalog courses;
- create offerings and assign instructors;
- add and drop students by hand;
- maintain the program outcomes: edit wording, copy the set into a new version, activate a version, and delete only unused POs.

This delivers B2 AC 1–3 and B3 AC 3–4. B3 AC 1–2 (the CSV import) is S3-05, which builds on `get_or_create_student()` and `enroll()` written here.

**Scope of "the head's program".** Every `/department/` page works on `head_program(request.user)` (S2-02). Terms are the exception: `Term` has no program field, because the whole university shares one calendar, so any head manages them. Objects from another program return 404, exactly like the matrix's `DENY`.

**Where the rules live.** Views are thin. Every rule is in `catalog/services.py`: closed term, valid status change, reason for reopening, duplicate course code, instructors must be instructors, no double enrollment, PO in use. Each rule has a service test. Every write records an `AuditEvent` in the same transaction.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/core/forms.py` | create | `BootstrapFormMixin`, `add_service_errors` |
| `apps/core/audit.py` | modify | add `snapshot()` if S1-04 didn't |
| `templates/includes/form_fields.html` | create | renders any form with labels, help text and errors |
| `apps/accounts/services.py` | create | `get_or_create_student` |
| `apps/catalog/services.py` | create | every write in this story |
| `apps/catalog/forms.py` | create | `TermForm`, `TermReopenForm`, `CourseForm`, `OfferingForm`, `EnrollmentAddForm`, `POForm`, `POSetCopyForm` |
| `apps/catalog/views.py` | modify | department views |
| `apps/catalog/urls.py` | modify | `/department/…` URLs |
| `apps/catalog/templates/catalog/department_base.html` | create | sub-navigation for department pages |
| `apps/catalog/templates/catalog/{terms,term_edit,courses,course_edit,offerings,offering_edit,enrollments,po_sets,po_set_detail,po_edit,po_delete}.html` | create | pages |
| `apps/catalog/tests/test_services.py` | create | rule tests |
| `apps/catalog/tests/test_views.py` | create | flow tests through the browser layer |

### Steps

#### Step 1: two small helpers in `apps/core`

Bootstrap needs a CSS class on every input. Rather than repeating widget `attrs` in every form, one mixin adds them. `add_service_errors` puts a service's `ValidationError` onto the form: messages for fields the form has go next to the field, everything else goes to the top. Then the user sees *why* a save was refused, in the place they are looking.

```python
# apps/core/forms.py
from django import forms
from django.core.exceptions import ValidationError

_CHECK_WIDGETS = (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)


class BootstrapFormMixin:
    """Adds Bootstrap 5 classes to every widget. Put it first: class F(BootstrapFormMixin, forms.Form)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.HiddenInput):
                continue
            if isinstance(widget, _CHECK_WIDGETS):
                css = "form-check-input"
            elif isinstance(widget, forms.Select | forms.SelectMultiple):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()
                widget.attrs["aria-invalid"] = "true"


def add_service_errors(form, exc: ValidationError) -> None:
    """Show a service's ValidationError on the form, next to the field when the form has it."""
    if hasattr(exc, "error_dict"):
        for name, messages in exc.message_dict.items():
            target = name if name in form.fields else None
            for message in messages:
                form.add_error(target, message)
    else:
        for message in exc.messages:
            form.add_error(None, message)
```

```django
{# templates/includes/form_fields.html — use with: form #}
{% for hidden in form.hidden_fields %}{{ hidden }}{% endfor %}
{% if form.non_field_errors %}
  <div class="alert alert-danger" role="alert">
    {% for error in form.non_field_errors %}<div>{{ error }}</div>{% endfor %}
  </div>
{% endif %}
{% for field in form.visible_fields %}
  <div class="mb-3">
    {% if field.widget_type == "checkbox" %}
      <div class="form-check">
        {{ field }}
        <label class="form-check-label" for="{{ field.id_for_label }}">{{ field.label }}</label>
      </div>
    {% elif field.widget_type == "checkboxselectmultiple" %}
      <fieldset>
        <legend class="form-label fs-6">{{ field.label }}</legend>
        {% for choice in field %}
          <div class="form-check">
            {{ choice.tag }}
            <label class="form-check-label" for="{{ choice.id_for_label }}">{{ choice.choice_label }}</label>
          </div>
        {% empty %}
          <p class="text-body-secondary small mb-0">No options available.</p>
        {% endfor %}
      </fieldset>
    {% else %}
      <label class="form-label" for="{{ field.id_for_label }}">{{ field.label }}</label>
      {{ field }}
    {% endif %}
    {% if field.help_text %}<div class="form-text">{{ field.help_text }}</div>{% endif %}
    {% for error in field.errors %}<div class="invalid-feedback d-block">{{ error }}</div>{% endfor %}
  </div>
{% endfor %}
```

`snapshot()` is listed in §4.8 under `core/audit.py`. If S1-04 didn't write it, add it now:

```python
# apps/core/audit.py  (add below record())
import datetime
from decimal import Decimal


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime.date | datetime.datetime):
        return value.isoformat()
    if hasattr(value, "pk"):
        return value.pk
    return value


def snapshot(instance, fields) -> dict:
    """JSON-safe dict of the named fields, for AuditEvent.before / after."""
    return {name: _json_safe(getattr(instance, name)) for name in fields}
```

#### Step 2: `accounts.services.get_or_create_student`

One function decides "is this the same student?", and both the manual add form and the CSV import (S3-05) use it. The **student number** is the identity, because it's printed on every university document. Email is checked for conflicts. New accounts get an **unusable password**: they can't log in until they set one through the link S3-05 sends.

```python
# apps/accounts/services.py
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import ProgramMembership, User
from apps.core import audit


@transaction.atomic
def get_or_create_student(*, student_number, email, first_name, last_name, program, cohort_year,
                          actor=None) -> tuple[User, bool]:
    """Find a student by student number, or create the account. Ensures a student membership
    in `program`. Returns (user, created). Raises ValidationError on conflicting data."""
    student_number = (student_number or "").strip()
    email = User.objects.normalize_email((email or "").strip())
    if not student_number:
        raise ValidationError({"student_number": "Student number is required."})

    user = User.objects.filter(student_number=student_number).first()
    created = False
    if user is None:
        if not email or not first_name or not last_name or not cohort_year:
            raise ValidationError(
                "New students need a student number, email, first name, last name and cohort year."
            )
        clash = User.objects.filter(email__iexact=email).first()
        if clash is not None:
            raise ValidationError({"email": f"{email} already belongs to another account "
                                            f"(student number {clash.student_number or 'none'})."})
        user = User(email=email, first_name=first_name.strip(), last_name=last_name.strip(),
                    student_number=student_number)
        user.set_unusable_password()
        user.full_clean(exclude=["password"])
        user.save()
        created = True
        audit.record(actor, "user.create", user, after={"student_number": student_number, "email": email})
    elif email and user.email.lower() != email.lower():
        raise ValidationError({"email": f"Student {student_number} is registered as {user.email}, not {email}."})

    membership = ProgramMembership.objects.filter(
        user=user, program=program, role=ProgramMembership.Role.STUDENT
    ).first()
    if membership is None:
        if not cohort_year:
            raise ValidationError({"cohort_year": "Cohort year is required for a new student."})
        membership = ProgramMembership.objects.create(
            user=user, program=program, role=ProgramMembership.Role.STUDENT, cohort_year=cohort_year
        )
        audit.record(actor, "membership.create", membership,
                     after={"role": "student", "program": program.code, "cohort_year": cohort_year})
    return user, created
```

Why not `ProgramMembership.objects.get_or_create(...)`? With an empty cohort year, the database's `student_has_cohort` constraint would refuse the insert with an `IntegrityError`, which reaches the user as a 500. Checking first lets us say what's wrong in words.


#### Step 3: `apps/catalog/services.py`

Read this file top to bottom before writing it. It is the department's rulebook.

**Term status is a small state machine.** Allowed moves:

```
planned ──open──► open ──close──► closed
                    ▲                │
                    └────reopen──────┘   (reason required, audited)
```

Going straight from planned to closed, or back to planned, is refused. Neither happens in real life, and allowing them would only create odd states to test.

**Closed means closed.** `ensure_term_open(offering)` is the first line of every service that changes an offering or anything inside it. S2-04, S2-05 and S2-06 call it too. A *planned* term is editable on purpose: instructors set up their courses before the term opens.

**Locking.** `set_term_status` and `activate_po_set` lock the rows they change (`select_for_update`). Two heads clicking "activate" on two different PO sets at the same moment would otherwise both pass the check. The partial unique index would then reject one with an `IntegrityError` (a 500) instead of a clean result. This is the same idea as the publish flow in §4.5, and a good concrete example for CSE 321's concurrency section.

```python
# apps/catalog/services.py
"""Every write for terms, catalog courses, offerings, enrollments and program outcomes.
Rules from spec B2, B3 and §5.3. Each function audits inside its own transaction."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import ProgramMembership
from apps.catalog.models import (
    Course, CourseOffering, Enrollment, Program, ProgramOutcome, ProgramOutcomeSet, Term,
)
from apps.core import audit

TERM_FIELDS = ["code", "name", "starts_on", "ends_on", "status"]
COURSE_FIELDS = ["program", "code", "title", "credits", "ects"]
PO_FIELDS = ["number", "short_name", "description"]

# (from, to) -> action name used in the audit trail
TERM_TRANSITIONS = {
    (Term.Status.PLANNED, Term.Status.OPEN): "term.open",
    (Term.Status.OPEN, Term.Status.CLOSED): "term.close",
    (Term.Status.CLOSED, Term.Status.OPEN): "term.reopen",
}


# ---------- guard used by every offering-level service in the codebase ----------

def ensure_term_open(offering: CourseOffering) -> None:
    """Refuse any change inside a closed term (spec §3.3, §5.3)."""
    if offering.term.status == Term.Status.CLOSED:
        raise ValidationError(
            f"{offering.term.name} is closed, so {offering.course.code} can't be changed. "
            "Ask the department head to reopen the term."
        )


# ---------- terms ----------

@transaction.atomic
def create_term(user, **fields) -> Term:
    term = Term(**fields)
    term.full_clean()
    term.save()
    audit.record(user, "term.create", term, after=audit.snapshot(term, TERM_FIELDS))
    return term


@transaction.atomic
def update_term(user, term: Term, **fields) -> Term:
    """Change code, name or dates. Status changes go through set_term_status."""
    if "status" in fields:
        raise ValueError("use set_term_status() to change a term's status")
    before = audit.snapshot(term, TERM_FIELDS)
    for name, value in fields.items():
        setattr(term, name, value)
    term.full_clean()
    term.save()
    audit.record(user, "term.update", term, before=before, after=audit.snapshot(term, TERM_FIELDS))
    return term


@transaction.atomic
def set_term_status(user, term: Term, status: str, *, reason: str = "") -> Term:
    term = Term.objects.select_for_update().get(pk=term.pk)
    action = TERM_TRANSITIONS.get((term.status, status))
    if action is None:
        raise ValidationError(
            f"A term can't go from {term.get_status_display().lower()} to {Term.Status(status).label.lower()}."
        )
    reason = reason.strip()
    if action == "term.reopen" and len(reason) < 10:
        raise ValidationError({"reason": "Say why the term is being reopened (at least 10 characters)."})
    before = {"status": term.status}
    term.status = status
    term.save(update_fields=["status"])
    after = {"status": status}
    if reason:
        after["reason"] = reason
    audit.record(user, action, term, before=before, after=after)
    return term


# ---------- catalog courses ----------

@transaction.atomic
def save_course(user, course: Course | None = None, **fields) -> Course:
    """Create a course (pass program= in fields) or update one. Codes are unique per program."""
    creating = course is None
    before = None if creating else audit.snapshot(course, COURSE_FIELDS)
    course = course or Course()
    for name, value in fields.items():
        setattr(course, name, value)
    course.code = " ".join(course.code.upper().split())          # "cse  311" -> "CSE 311"
    if Course.objects.filter(program=course.program, code=course.code).exclude(pk=course.pk).exists():
        raise ValidationError({"code": f"{course.code} already exists in {course.program.code}."})
    course.full_clean()
    course.save()
    audit.record(user, "course.create" if creating else "course.update", course,
                 before=before, after=audit.snapshot(course, COURSE_FIELDS))
    return course


# ---------- offerings ----------

def _check_instructors(program: Program, instructors) -> list:
    instructors = list(instructors)
    allowed = set(
        ProgramMembership.objects.filter(
            program=program, role=ProgramMembership.Role.INSTRUCTOR,
            user__in=[u.pk for u in instructors],
        ).values_list("user_id", flat=True)
    )
    wrong = [u for u in instructors if u.pk not in allowed]
    if wrong:
        names = ", ".join(u.get_full_name() or u.email for u in wrong)
        raise ValidationError({"instructors": f"Not an instructor in {program.code}: {names}."})
    return instructors


def _offering_snapshot(offering: CourseOffering) -> dict:
    return {
        "course": offering.course.code,
        "term": offering.term.code,
        "section": offering.section,
        "instructors": sorted(offering.instructors.values_list("email", flat=True)),
    }


@transaction.atomic
def create_offering(user, *, course: Course, term: Term, section: str = "1", instructors=()) -> CourseOffering:
    if term.status == Term.Status.CLOSED:
        raise ValidationError({"term": f"{term.name} is closed. Reopen it before adding offerings."})
    section = (section or "1").strip()
    if CourseOffering.objects.filter(course=course, term=term, section=section).exists():
        raise ValidationError({"section": f"{course.code} section {section} already exists in {term.name}."})
    instructors = _check_instructors(course.program, instructors)
    offering = CourseOffering(course=course, term=term, section=section)
    offering.full_clean()
    try:
        offering.save()
    except IntegrityError as exc:                    # two heads, same click, same second
        raise ValidationError("This offering was just created by someone else. Reload the page.") from exc
    offering.instructors.set(instructors)
    audit.record(user, "offering.create", offering, offering=offering, after=_offering_snapshot(offering))
    return offering


@transaction.atomic
def update_offering(user, offering: CourseOffering, *, section: str | None = None,
                    instructors=None) -> CourseOffering:
    """Change the section label and/or the instructor list. Course and term never change:
    create a new offering instead, so grades never move between courses."""
    ensure_term_open(offering)
    before = _offering_snapshot(offering)
    if section is not None:
        section = section.strip()
        clash = CourseOffering.objects.filter(course=offering.course, term=offering.term, section=section)
        if clash.exclude(pk=offering.pk).exists():
            raise ValidationError({"section": f"Section {section} already exists for this course and term."})
        offering.section = section
        offering.full_clean()
        offering.save(update_fields=["section"])
    if instructors is not None:
        offering.instructors.set(_check_instructors(offering.course.program, instructors))
    audit.record(user, "offering.update", offering, offering=offering,
                 before=before, after=_offering_snapshot(offering))
    return offering


# ---------- enrollments ----------

@transaction.atomic
def enroll(user, offering: CourseOffering, student) -> Enrollment:
    """Enroll a student (or re-enroll a dropped one). B3 AC 4: duplicates are refused with a message."""
    ensure_term_open(offering)
    program = offering.course.program
    if not student.memberships.filter(program=program, role=ProgramMembership.Role.STUDENT).exists():
        raise ValidationError(f"{student.get_full_name()} is not a {program.code} student.")
    existing = Enrollment.objects.select_for_update().filter(offering=offering, student=student).first()
    if existing and existing.status == Enrollment.Status.ENROLLED:
        raise ValidationError(f"{student.get_full_name()} ({student.student_number}) is already enrolled.")
    if existing:
        existing.status = Enrollment.Status.ENROLLED
        existing.save(update_fields=["status"])
        audit.record(user, "enrollment.reenroll", existing, offering=offering,
                     before={"status": "dropped"}, after={"status": "enrolled"})
        return existing
    try:
        enrollment = Enrollment.objects.create(offering=offering, student=student)
    except IntegrityError as exc:
        raise ValidationError(f"{student.student_number} is already enrolled.") from exc
    audit.record(user, "enrollment.create", enrollment, offering=offering,
                 after={"student_number": student.student_number, "status": "enrolled"})
    return enrollment


@transaction.atomic
def drop(user, enrollment: Enrollment) -> Enrollment:
    """Mark as dropped. The row and its grades stay (history), but loaders ignore dropped students."""
    ensure_term_open(enrollment.offering)
    if enrollment.status == Enrollment.Status.DROPPED:
        return enrollment
    enrollment.status = Enrollment.Status.DROPPED
    enrollment.save(update_fields=["status"])
    audit.record(user, "enrollment.drop", enrollment, offering=enrollment.offering,
                 before={"status": "enrolled"}, after={"status": "dropped"})
    return enrollment


# ---------- program outcome sets ----------

@transaction.atomic
def copy_po_set(user, po_set: ProgramOutcomeSet, *, label: str, effective_from_year: int) -> ProgramOutcomeSet:
    """B2 AC 2: a new version starts as an exact copy of the old one, inactive."""
    label = label.strip()
    if ProgramOutcomeSet.objects.filter(program=po_set.program, label=label).exists():
        raise ValidationError({"label": f"A PO set called “{label}” already exists."})
    new_set = ProgramOutcomeSet.objects.create(
        program=po_set.program, label=label, effective_from_year=effective_from_year, is_active=False,
    )
    ProgramOutcome.objects.bulk_create(
        ProgramOutcome(po_set=new_set, number=po.number, short_name=po.short_name, description=po.description)
        for po in po_set.outcomes.all()
    )
    audit.record(user, "po_set.copy", new_set,
                 after={"copied_from": po_set.label, "label": label, "outcomes": new_set.outcomes.count()})
    return new_set


@transaction.atomic
def activate_po_set(user, po_set: ProgramOutcomeSet) -> ProgramOutcomeSet:
    """Make this set the active one. The old one is deactivated first, inside the same
    transaction, because the partial unique index allows only one active set per program."""
    sets = list(ProgramOutcomeSet.objects.select_for_update().filter(program=po_set.program))
    previous = next((s for s in sets if s.is_active), None)
    if previous and previous.pk == po_set.pk:
        return po_set
    if not po_set.outcomes.exists():
        raise ValidationError("An empty PO set can't be activated.")
    ProgramOutcomeSet.objects.filter(program=po_set.program, is_active=True).update(is_active=False)
    ProgramOutcomeSet.objects.filter(pk=po_set.pk).update(is_active=True)
    po_set.is_active = True
    audit.record(user, "po_set.activate", po_set,
                 before={"active": previous.label if previous else None}, after={"active": po_set.label})
    return po_set


@transaction.atomic
def update_po(user, po: ProgramOutcome, **fields) -> ProgramOutcome:
    """Edit short name or description. Numbers don't change: every mapping refers to them."""
    allowed = {"short_name", "description"}
    if set(fields) - allowed:
        raise ValueError(f"only {sorted(allowed)} can be edited")
    before = audit.snapshot(po, PO_FIELDS)
    for name, value in fields.items():
        setattr(po, name, value.strip())
    po.full_clean()
    po.save()
    audit.record(user, "po.update", po, before=before, after=audit.snapshot(po, PO_FIELDS))
    return po


def courses_using_po(po: ProgramOutcome) -> list[str]:
    """Human labels of the offerings whose LOs link to this PO, e.g. 'CSE 311 (Fall 2026)'."""
    rows = (
        po.lo_weights.select_related("learning_outcome__offering__course", "learning_outcome__offering__term")
        .order_by("learning_outcome__offering__course__code")
    )
    labels = []
    for w in rows:
        o = w.learning_outcome.offering
        label = f"{o.course.code} ({o.term.name})"
        if label not in labels:
            labels.append(label)
    return labels


@transaction.atomic
def delete_po(user, po: ProgramOutcome) -> None:
    """B2 AC 3: a PO with LO→PO weights can't be deleted; the message names the courses."""
    used_by = courses_using_po(po)
    if used_by:
        raise ValidationError(
            f"PO {po.number} is used by {', '.join(used_by)}. Edit its wording instead of deleting it."
        )
    audit.record(user, "po.delete", po, before=audit.snapshot(po, PO_FIELDS))
    po.delete()
```

`courses_using_po` is a helper the delete page also uses, to warn *before* the click. It goes into the code map.

Notes for the reviewer:

- `activate_po_set` uses `.update()`, not `.save()`, for both rows. A `.save()` on the new set while the old one was still active in the database would violate the index mid-transaction. The PostgreSQL unique index is not deferrable, so it is checked on every statement.
- `drop` keeps the row. Deleting it would delete the student's grades (cascade) and their audit context. Dropped students are filtered out by `visible_enrollments` and by the loaders.
- `update_offering` can't change course or term. Moving an offering to another course would silently move all its grades and LOs.

#### Step 4: `apps/catalog/forms.py`

Forms check **shape**: required fields, date order, number ranges. Services check **rules** that need the database: duplicates, closed terms, memberships. Two exceptions, both on purpose: the course-code and PO-set-label checks also live in the form, because the user should see "already exists" next to the field before anything else happens. The service checks again, because services are also called from imports and the shell.

```python
# apps/catalog/forms.py
from __future__ import annotations

from django import forms

from apps.accounts.models import ProgramMembership, User
from apps.catalog.models import Course, CourseOffering, ProgramOutcome, ProgramOutcomeSet, Term
from apps.core.forms import BootstrapFormMixin


class DateInput(forms.DateInput):
    input_type = "date"


class TermForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Term
        fields = ["code", "name", "starts_on", "ends_on"]
        widgets = {"starts_on": DateInput(), "ends_on": DateInput()}
        help_texts = {"code": "Short and sortable, e.g. 2026F, 2027S."}

    def clean(self):
        data = super().clean()
        starts, ends = data.get("starts_on"), data.get("ends_on")
        if starts and ends and ends <= starts:
            self.add_error("ends_on", "The term must end after it starts.")
        return data


class TermReopenForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(
        min_length=10, widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Stored in the audit trail. Example: 'Grade appeal for CSE 311 Midterm I, approved by the board.'",
    )


class CourseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = ["code", "title", "credits", "ects"]
        labels = {"ects": "ECTS"}

    def __init__(self, *args, program, **kwargs):
        super().__init__(*args, **kwargs)
        self.program = program

    def clean_code(self):
        code = " ".join(self.cleaned_data["code"].upper().split())
        clash = Course.objects.filter(program=self.program, code=code).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(f"{code} already exists in {self.program.code}.")
        return code


def instructor_choices(program):
    return (
        User.objects.filter(memberships__program=program, memberships__role=ProgramMembership.Role.INSTRUCTOR)
        .distinct()
        .order_by("last_name", "first_name")
    )


class InstructorField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.get_full_name()} <{obj.email}>"


class OfferingForm(BootstrapFormMixin, forms.Form):
    """Create form with course + term; edit form (offering=…) has section + instructors only."""

    course = forms.ModelChoiceField(queryset=Course.objects.none())
    term = forms.ModelChoiceField(queryset=Term.objects.none())
    section = forms.CharField(max_length=8, initial="1")
    instructors = InstructorField(
        queryset=User.objects.none(), required=False, widget=forms.CheckboxSelectMultiple,
        help_text="Only people with an instructor membership in this program are listed.",
    )

    def __init__(self, *args, program, offering: CourseOffering | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["instructors"].queryset = instructor_choices(program)
        if offering is None:
            self.fields["course"].queryset = program.courses.order_by("code")
            self.fields["term"].queryset = Term.objects.exclude(status=Term.Status.CLOSED)
        else:
            del self.fields["course"]
            del self.fields["term"]
            self.initial.setdefault("section", offering.section)
            self.initial.setdefault("instructors", list(offering.instructors.all()))


class EnrollmentAddForm(BootstrapFormMixin, forms.Form):
    """Add one student by student number. For a student who has no account yet,
    also fill in email, names and cohort year."""

    student_number = forms.CharField(max_length=20)
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    cohort_year = forms.IntegerField(required=False, min_value=1990, max_value=2100,
                                     help_text="Year the student started, e.g. 2023.")


class POForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProgramOutcome
        fields = ["short_name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
        help_texts = {"description": "The official wording. Instructors map their LOs against this text."}


class POSetCopyForm(BootstrapFormMixin, forms.Form):
    label = forms.CharField(max_length=100, help_text="e.g. 2027 curriculum")
    effective_from_year = forms.IntegerField(
        min_value=1990, max_value=2100, help_text="First cohort (entry year) that uses this set.",
    )

    def __init__(self, *args, program, **kwargs):
        super().__init__(*args, **kwargs)
        self.program = program

    def clean_label(self):
        label = self.cleaned_data["label"].strip()
        if ProgramOutcomeSet.objects.filter(program=self.program, label=label).exists():
            raise forms.ValidationError(f"A PO set called “{label}” already exists.")
        return label
```

#### Step 5: views and URLs

Every department view starts the same way: `@login_required`, `@require_role("head")`, then `program = _program(request)`. Objects are always fetched **with the program in the filter** (`course__program=program`), so a head of another program gets 404 (T2.6 makes this matter).

The pattern for a write view, used five times below:

```python
form = SomeForm(request.POST or None)
if request.method == "POST" and form.is_valid():
    try:
        services.do_the_thing(request.user, **form.cleaned_data)
    except ValidationError as exc:
        add_service_errors(form, exc)       # stay on the page and show why
    else:
        messages.success(request, "Saved.")
        return redirect("catalog:terms")    # Post/Redirect/Get: reload doesn't resubmit
return render(request, "catalog/terms.html", {"form": form})
```

```python
# apps/catalog/views.py  (add below teaching / offering_home from S2-01)
# The complete import block for this file is shown after the views.


def _program(request):
    return head_program_or_404(request.user)


# ---------- terms ----------

@login_required
@require_role("head")
def terms(request):
    form = TermForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            term = services.create_term(request.user, **form.cleaned_data)
        except ValidationError as exc:
            add_service_errors(form, exc)
        else:
            messages.success(request, f"Term {term.name} created. It is planned until you open it.")
            return redirect("catalog:terms")
    return render(request, "catalog/terms.html", {
        "terms": Term.objects.all(),
        "form": form,
        "reopen_form": TermReopenForm(),
        "section": "terms",
    })


@login_required
@require_role("head")
def term_edit(request, term_id):
    term = get_object_or_404(Term, pk=term_id)
    form = TermForm(request.POST or None, instance=term)
    if request.method == "POST" and form.is_valid():
        try:
            services.update_term(request.user, Term.objects.get(pk=term.pk), **form.cleaned_data)
        except ValidationError as exc:
            add_service_errors(form, exc)
        else:
            messages.success(request, "Term saved.")
            return redirect("catalog:terms")
    return render(request, "catalog/term_edit.html", {"term": term, "form": form, "section": "terms"})


@login_required
@require_role("head")
@require_POST
def term_status(request, term_id):
    term = get_object_or_404(Term, pk=term_id)
    target = {"open": Term.Status.OPEN, "close": Term.Status.CLOSED, "reopen": Term.Status.OPEN}.get(
        request.POST.get("action", "")
    )
    if target is None:
        messages.error(request, "Unknown action.")
        return redirect("catalog:terms")
    try:
        services.set_term_status(request.user, term, target, reason=request.POST.get("reason", ""))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, f"{term.name} is now {Term.Status(target).label.lower()}.")
    return redirect("catalog:terms")


# ---------- courses ----------

@login_required
@require_role("head")
def courses(request):
    program = _program(request)
    form = CourseForm(request.POST or None, program=program)
    if request.method == "POST" and form.is_valid():
        try:
            course = services.save_course(request.user, program=program, **form.cleaned_data)
        except ValidationError as exc:
            add_service_errors(form, exc)
        else:
            messages.success(request, f"{course.code} added to the catalog.")
            return redirect("catalog:courses")
    return render(request, "catalog/courses.html", {
        "courses": program.courses.order_by("code"), "form": form, "program": program, "section": "courses",
    })


@login_required
@require_role("head")
def course_edit(request, course_id):
    program = _program(request)
    course = get_object_or_404(Course, pk=course_id, program=program)
    form = CourseForm(request.POST or None, instance=course, program=program)
    if request.method == "POST" and form.is_valid():
        try:
            services.save_course(request.user, Course.objects.get(pk=course.pk), **form.cleaned_data)
        except ValidationError as exc:
            add_service_errors(form, exc)
        else:
            messages.success(request, "Course saved.")
            return redirect("catalog:courses")
    return render(request, "catalog/course_edit.html", {"course": course, "form": form, "section": "courses"})
```

`term_edit` and `course_edit` pass a fresh copy (`objects.get(pk=…)`) to the service. A `ModelForm` writes the posted values into `form.instance` during `is_valid()`, so the original object already holds the *new* values. The audit `before` snapshot needs the old ones.

```python
# apps/catalog/views.py  (continued)

# ---------- offerings ----------

@login_required
@require_role("head")
def offerings(request):
    program = _program(request)
    form = OfferingForm(request.POST or None, program=program)
    if request.method == "POST" and form.is_valid():
        try:
            offering = services.create_offering(request.user, **form.cleaned_data)
        except ValidationError as exc:
            add_service_errors(form, exc)
        else:
            messages.success(request, f"{offering.course.code} section {offering.section} created.")
            return redirect("catalog:enrollments", offering_id=offering.pk)

    term_id = request.GET.get("term")
    selected_term = Term.objects.filter(pk=term_id).first() if term_id and term_id.isdigit() else None
    qs = (
        CourseOffering.objects.filter(course__program=program)
        .select_related("course", "term")
        .prefetch_related("instructors")
        .order_by("-term__starts_on", "course__code", "section")
    )
    if selected_term:
        qs = qs.filter(term=selected_term)
    return render(request, "catalog/offerings.html", {
        "offerings": qs, "form": form, "terms": Term.objects.all(), "selected_term": selected_term,
        "section": "offerings",
    })


@login_required
@require_role("head")
def offering_edit(request, offering_id):
    program = _program(request)
    offering = get_object_or_404(
        CourseOffering.objects.select_related("course", "term"), pk=offering_id, course__program=program
    )
    form = OfferingForm(request.POST or None, program=program, offering=offering)
    if request.method == "POST" and form.is_valid():
        try:
            services.update_offering(request.user, offering, **form.cleaned_data)
        except ValidationError as exc:
            add_service_errors(form, exc)
        else:
            messages.success(request, "Offering saved.")
            return redirect("catalog:offerings")
    return render(request, "catalog/offering_edit.html", {
        "offering": offering, "form": form, "section": "offerings",
        "is_closed": offering.term.status == Term.Status.CLOSED,
    })


@login_required
@require_role("head")
def enrollments(request, offering_id):
    """List students; add one (action=add) or drop one (action=drop)."""
    program = _program(request)
    offering = get_object_or_404(
        CourseOffering.objects.select_related("course", "term"), pk=offering_id, course__program=program
    )
    action = request.POST.get("action") if request.method == "POST" else None
    form = EnrollmentAddForm(request.POST if action == "add" else None)

    if action == "add" and form.is_valid():
        data = form.cleaned_data
        try:
            student, created = get_or_create_student(program=program, actor=request.user, **data)
            services.enroll(request.user, offering, student)
        except ValidationError as exc:
            add_service_errors(form, exc)
        else:
            note = " (new account)" if created else ""
            messages.success(request, f"{student.get_full_name()} enrolled{note}.")
            return redirect("catalog:enrollments", offering_id=offering.pk)

    if action == "drop":
        enrollment = get_object_or_404(Enrollment, pk=request.POST.get("enrollment_id"), offering=offering)
        try:
            services.drop(request.user, enrollment)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"{enrollment.student.get_full_name()} dropped. Their grades are kept.")
        return redirect("catalog:enrollments", offering_id=offering.pk)

    return render(request, "catalog/enrollments.html", {
        "offering": offering,
        "enrollments": visible_enrollments(request.user, offering, include_dropped=True),
        "form": form,
        "is_closed": offering.term.status == Term.Status.CLOSED,
        "section": "offerings",
    })
```

`get_or_create_student` and `enroll` run inside the view's request, each in its own `atomic` block. If `enroll` fails after a new account was created, the account stays. That's intended: the person exists either way, and the next attempt will find them. To make the pair all-or-nothing, wrap both in `with transaction.atomic():` in a future `enroll_new_student` service. S3-05 does exactly that for the CSV import.

```python
# apps/catalog/views.py  (continued)

# ---------- program outcomes ----------

@login_required
@require_role("head")
def po_sets(request):
    program = _program(request)
    sets = program.po_sets.annotate(n=Count("outcomes")).order_by("-is_active", "-effective_from_year")
    return render(request, "catalog/po_sets.html", {"program": program, "sets": sets, "section": "outcomes"})


@login_required
@require_role("head")
def po_set_detail(request, set_id):
    program = _program(request)
    po_set = get_object_or_404(ProgramOutcomeSet, pk=set_id, program=program)
    return render(request, "catalog/po_set_detail.html", {
        "po_set": po_set,
        "outcomes": po_set.outcomes.annotate(links=Count("lo_weights")),
        "copy_form": POSetCopyForm(program=program),
        "section": "outcomes",
    })


@login_required
@require_role("head")
@require_POST
def po_set_copy(request, set_id):
    program = _program(request)
    po_set = get_object_or_404(ProgramOutcomeSet, pk=set_id, program=program)
    form = POSetCopyForm(request.POST, program=program)
    if form.is_valid():
        try:
            new_set = services.copy_po_set(request.user, po_set, **form.cleaned_data)
        except ValidationError as exc:
            add_service_errors(form, exc)
        else:
            messages.success(request, f"Copied to “{new_set.label}”. It stays inactive until you activate it.")
            return redirect("catalog:po_set", set_id=new_set.pk)
    return render(request, "catalog/po_set_detail.html", {
        "po_set": po_set,
        "outcomes": po_set.outcomes.annotate(links=Count("lo_weights")),
        "copy_form": form,
        "section": "outcomes",
    }, status=400)


@login_required
@require_role("head")
@require_POST
def po_set_activate(request, set_id):
    program = _program(request)
    po_set = get_object_or_404(ProgramOutcomeSet, pk=set_id, program=program)
    try:
        services.activate_po_set(request.user, po_set)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, f"“{po_set.label}” is now the active PO set for {program.code}.")
    return redirect("catalog:outcomes")


@login_required
@require_role("head")
def po_edit(request, po_id):
    program = _program(request)
    po = get_object_or_404(ProgramOutcome.objects.select_related("po_set"), pk=po_id, po_set__program=program)
    form = POForm(request.POST or None, instance=po)
    if request.method == "POST" and form.is_valid():
        try:
            services.update_po(request.user, ProgramOutcome.objects.get(pk=po.pk), **form.cleaned_data)
        except ValidationError as exc:
            add_service_errors(form, exc)
        else:
            messages.success(request, f"PO {po.number} saved.")
            return redirect("catalog:po_set", set_id=po.po_set_id)
    return render(request, "catalog/po_edit.html", {"po": po, "form": form, "section": "outcomes"})


@login_required
@require_role("head")
def po_delete(request, po_id):
    """GET: confirmation (full page, or just the modal body for HTMX). POST: delete."""
    program = _program(request)
    po = get_object_or_404(ProgramOutcome.objects.select_related("po_set"), pk=po_id, po_set__program=program)
    if request.method == "POST":
        try:
            services.delete_po(request.user, po)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"PO {po.number} deleted.")
        return redirect("catalog:po_set", set_id=po.po_set_id)
    template = "catalog/po_delete.html#confirm" if request.htmx else "catalog/po_delete.html"
    return render(request, template, {"po": po, "used_by": services.courses_using_po(po), "section": "outcomes"})
```

The complete import block at the top of `apps/catalog/views.py` after this story (it replaces S2-01's shorter one):

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import require_offering_access, require_role
from apps.accounts.permissions import head_program_or_404
from apps.accounts.services import get_or_create_student
from apps.catalog import services
from apps.catalog.forms import (
    CourseForm, EnrollmentAddForm, OfferingForm, POForm, POSetCopyForm, TermForm, TermReopenForm,
)
from apps.catalog.models import Course, CourseOffering, Enrollment, ProgramOutcome, ProgramOutcomeSet, Term
from apps.catalog.selectors import teaching_offerings, visible_enrollments
from apps.core.forms import add_service_errors
from apps.core.navigation import offering_tabs, safe_reverse
```


```python
# apps/catalog/urls.py  (complete after this story)
from django.urls import path

from apps.catalog import views

app_name = "catalog"

urlpatterns = [
    path("teaching/", views.teaching, name="teaching"),
    path("offerings/<int:offering_id>/", views.offering_home, name="offering"),
    # department: outcomes
    path("department/outcomes/", views.po_sets, name="outcomes"),
    path("department/outcomes/sets/<int:set_id>/", views.po_set_detail, name="po_set"),
    path("department/outcomes/sets/<int:set_id>/copy/", views.po_set_copy, name="po_set_copy"),
    path("department/outcomes/sets/<int:set_id>/activate/", views.po_set_activate, name="po_set_activate"),
    path("department/outcomes/<int:po_id>/edit/", views.po_edit, name="po_edit"),
    path("department/outcomes/<int:po_id>/delete/", views.po_delete, name="po_delete"),
    # department: terms, courses, offerings, enrollments
    path("department/terms/", views.terms, name="terms"),
    path("department/terms/<int:term_id>/edit/", views.term_edit, name="term_edit"),
    path("department/terms/<int:term_id>/status/", views.term_status, name="term_status"),
    path("department/courses/", views.courses, name="courses"),
    path("department/courses/<int:course_id>/edit/", views.course_edit, name="course_edit"),
    path("department/offerings/", views.offerings, name="offerings"),
    path("department/offerings/<int:offering_id>/edit/", views.offering_edit, name="offering_edit"),
    path("department/offerings/<int:offering_id>/enrollments/", views.enrollments, name="enrollments"),
    # S3-05 adds: enrollment_import, enrollment_import_preview, enrollment_import_confirm
]
```

#### Step 6: templates

All department pages extend one base with a sub-navigation. Each view passes `section` to highlight the current item.

```django
{# apps/catalog/templates/catalog/department_base.html #}
{% extends "base.html" %}
{% block content %}
<div class="container py-4">
  <nav aria-label="Department sections" class="mb-4">
    <ul class="nav nav-pills">
      {% url 'reports:department' as overview_url %}
      {% if overview_url %}
        <li class="nav-item"><a class="nav-link" href="{{ overview_url }}">Overview</a></li>
      {% endif %}
      <li class="nav-item"><a class="nav-link{% if section == 'offerings' %} active{% endif %}" href="{% url 'catalog:offerings' %}">Offerings</a></li>
      <li class="nav-item"><a class="nav-link{% if section == 'terms' %} active{% endif %}" href="{% url 'catalog:terms' %}">Terms</a></li>
      <li class="nav-item"><a class="nav-link{% if section == 'courses' %} active{% endif %}" href="{% url 'catalog:courses' %}">Courses</a></li>
      <li class="nav-item"><a class="nav-link{% if section == 'outcomes' %} active{% endif %}" href="{% url 'catalog:outcomes' %}">Program outcomes</a></li>
    </ul>
  </nav>
  {% block department %}{% endblock %}
</div>
{% endblock %}
```

**Terms.** One page lists the terms and has the create form. Each row gets the one status button that is valid for its state. Reopen opens an inline form for the reason: a `<details>` element, so it works without JavaScript.

```django
{# apps/catalog/templates/catalog/terms.html #}
{% extends "catalog/department_base.html" %}
{% block title %}Terms · POlaris{% endblock %}
{% block department %}
<div class="row g-4">
  <div class="col-lg-8">
    <h1 class="h3 mb-3">Terms</h1>
    {% if terms %}
      <table class="table align-middle">
        <thead><tr><th scope="col">Code</th><th scope="col">Name</th><th scope="col">Dates</th>
                   <th scope="col">Status</th><th scope="col"><span class="visually-hidden">Actions</span></th></tr></thead>
        <tbody>
        {% for term in terms %}
          <tr>
            <td class="fw-semibold">{{ term.code }}</td>
            <td>{{ term.name }}</td>
            <td class="text-nowrap">{{ term.starts_on|date:"j M Y" }} – {{ term.ends_on|date:"j M Y" }}</td>
            <td>
              {% if term.status == "open" %}<span class="badge text-bg-success">Open</span>
              {% elif term.status == "closed" %}<span class="badge text-bg-secondary">🔒 Closed</span>
              {% else %}<span class="badge text-bg-info">Planned</span>{% endif %}
            </td>
            <td class="text-end">
              <a class="btn btn-sm btn-outline-secondary" href="{% url 'catalog:term_edit' term_id=term.pk %}">Edit</a>
              {% if term.status == "planned" %}
                <form class="d-inline" method="post" action="{% url 'catalog:term_status' term_id=term.pk %}">
                  {% csrf_token %}<button class="btn btn-sm btn-primary" name="action" value="open">Open</button>
                </form>
              {% elif term.status == "open" %}
                <form class="d-inline" method="post" action="{% url 'catalog:term_status' term_id=term.pk %}">
                  {% csrf_token %}<button class="btn btn-sm btn-outline-danger" name="action" value="close">Close</button>
                </form>
              {% else %}
                <details class="d-inline-block text-start">
                  <summary class="btn btn-sm btn-outline-warning">Reopen…</summary>
                  <form method="post" action="{% url 'catalog:term_status' term_id=term.pk %}" class="mt-2" style="min-width: 18rem">
                    {% csrf_token %}
                    <input type="hidden" name="action" value="reopen">
                    <label class="form-label small" for="reason-{{ term.pk }}">Why reopen? (saved in the audit trail)</label>
                    <textarea class="form-control form-control-sm mb-2" id="reason-{{ term.pk }}" name="reason" rows="2" minlength="10" required></textarea>
                    <button class="btn btn-sm btn-warning">Reopen {{ term.code }}</button>
                  </form>
                </details>
              {% endif %}
            </td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
      <p class="small text-body-secondary">Closing a term makes all its courses read-only for everyone. Instructors can still view them.</p>
    {% else %}
      {% include "includes/empty_state.html" with title="No terms yet" message="Create the current term on the right. It starts as planned, so instructors can set up their courses before you open it." only %}
    {% endif %}
  </div>
  <div class="col-lg-4">
    <div class="card"><div class="card-body">
      <h2 class="h5">New term</h2>
      <form method="post" novalidate>
        {% csrf_token %}
        {% include "includes/form_fields.html" with form=form only %}
        <button class="btn btn-primary">Create term</button>
      </form>
    </div></div>
  </div>
</div>
{% endblock %}
```

The edit pages for terms, courses and POs share one shape. Here is the term page in full. The other two differ only in title, back link and object name.

```django
{# apps/catalog/templates/catalog/term_edit.html #}
{% extends "catalog/department_base.html" %}
{% block title %}Edit {{ term.code }} · POlaris{% endblock %}
{% block department %}
<div style="max-width: 36rem">
  <h1 class="h3 mb-3">Edit term {{ term.code }}</h1>
  <form method="post" novalidate>
    {% csrf_token %}
    {% include "includes/form_fields.html" with form=form only %}
    <button class="btn btn-primary">Save</button>
    <a class="btn btn-link" href="{% url 'catalog:terms' %}">Cancel</a>
  </form>
</div>
{% endblock %}
```

```django
{# apps/catalog/templates/catalog/course_edit.html #}
{% extends "catalog/department_base.html" %}
{% block title %}Edit {{ course.code }} · POlaris{% endblock %}
{% block department %}
<div style="max-width: 36rem">
  <h1 class="h3 mb-3">Edit {{ course.code }}</h1>
  <form method="post" novalidate>
    {% csrf_token %}
    {% include "includes/form_fields.html" with form=form only %}
    <button class="btn btn-primary">Save</button>
    <a class="btn btn-link" href="{% url 'catalog:courses' %}">Cancel</a>
  </form>
</div>
{% endblock %}
```

```django
{# apps/catalog/templates/catalog/po_edit.html #}
{% extends "catalog/department_base.html" %}
{% block title %}Edit PO {{ po.number }} · POlaris{% endblock %}
{% block department %}
<div style="max-width: 44rem">
  <p class="text-body-secondary mb-1">{{ po.po_set.label }}</p>
  <h1 class="h3 mb-3">Edit PO {{ po.number }}</h1>
  <form method="post" novalidate>
    {% csrf_token %}
    {% include "includes/form_fields.html" with form=form only %}
    <button class="btn btn-primary">Save</button>
    <a class="btn btn-link" href="{% url 'catalog:po_set' set_id=po.po_set_id %}">Cancel</a>
  </form>
</div>
{% endblock %}
```

```django
{# apps/catalog/templates/catalog/courses.html #}
{% extends "catalog/department_base.html" %}
{% block title %}Courses · POlaris{% endblock %}
{% block department %}
<div class="row g-4">
  <div class="col-lg-8">
    <h1 class="h3 mb-3">{{ program.code }} course catalog</h1>
    {% if courses %}
      <table class="table align-middle">
        <thead><tr><th scope="col">Code</th><th scope="col">Title</th><th scope="col" class="text-end">Credits</th>
                   <th scope="col" class="text-end">ECTS</th><th scope="col"><span class="visually-hidden">Actions</span></th></tr></thead>
        <tbody>
        {% for c in courses %}
          <tr>
            <td class="fw-semibold text-nowrap">{{ c.code }}</td>
            <td>{{ c.title }}</td>
            <td class="text-end tabular-nums">{{ c.credits|weight }}</td>
            <td class="text-end tabular-nums">{{ c.ects|weight }}</td>
            <td class="text-end"><a class="btn btn-sm btn-outline-secondary" href="{% url 'catalog:course_edit' course_id=c.pk %}">Edit</a></td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    {% else %}
      {% include "includes/empty_state.html" with title="The catalog is empty" message="Add the courses your program teaches. You create a term's offerings from these." only %}
    {% endif %}
  </div>
  <div class="col-lg-4">
    <div class="card"><div class="card-body">
      <h2 class="h5">New course</h2>
      <form method="post" novalidate>
        {% csrf_token %}
        {% include "includes/form_fields.html" with form=form only %}
        <button class="btn btn-primary">Add course</button>
      </form>
    </div></div>
  </div>
</div>
{% endblock %}
```

Put `{% load polaris %}` at the top of every template that uses `|weight` (the filter from S1-09, §4.8). If S1-09 added `polaris` to `TEMPLATES["OPTIONS"]["builtins"]`, you don't need it.

```django
{# apps/catalog/templates/catalog/offerings.html #}
{% extends "catalog/department_base.html" %}
{% block title %}Offerings · POlaris{% endblock %}
{% block department %}
<div class="row g-4">
  <div class="col-lg-8">
    <div class="d-flex flex-wrap align-items-end justify-content-between gap-2 mb-3">
      <h1 class="h3 mb-0">Offerings</h1>
      <form method="get" class="d-flex gap-2 align-items-end">
        <div>
          <label class="form-label small mb-0" for="term-filter">Term</label>
          <select class="form-select form-select-sm" id="term-filter" name="term" onchange="this.form.submit()">
            <option value="">All terms</option>
            {% for t in terms %}
              <option value="{{ t.pk }}"{% if selected_term and t.pk == selected_term.pk %} selected{% endif %}>{{ t.name }}</option>
            {% endfor %}
          </select>
        </div>
        <noscript><button class="btn btn-sm btn-outline-secondary">Filter</button></noscript>
      </form>
    </div>
    {% if offerings %}
      <table class="table align-middle">
        <thead><tr><th scope="col">Course</th><th scope="col">Term</th><th scope="col">Sec.</th>
                   <th scope="col">Instructors</th><th scope="col"><span class="visually-hidden">Actions</span></th></tr></thead>
        <tbody>
        {% for o in offerings %}
          <tr>
            <td><a href="{% url 'catalog:offering' offering_id=o.pk %}">{{ o.course.code }}</a>
                <div class="small text-body-secondary">{{ o.course.title }}</div></td>
            <td class="text-nowrap">{{ o.term.name }}{% if o.term.status == "closed" %} 🔒{% endif %}</td>
            <td>{{ o.section }}</td>
            <td>{% for p in o.instructors.all %}{{ p.get_full_name }}{% if not forloop.last %}, {% endif %}
                {% empty %}<span class="text-warning-emphasis">⚠ none assigned</span>{% endfor %}</td>
            <td class="text-end text-nowrap">
              <a class="btn btn-sm btn-outline-secondary" href="{% url 'catalog:offering_edit' offering_id=o.pk %}">Edit</a>
              <a class="btn btn-sm btn-outline-secondary" href="{% url 'catalog:enrollments' offering_id=o.pk %}">Students</a>
            </td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    {% else %}
      {% include "includes/empty_state.html" with title="No offerings yet" message="Pick a course and a term on the right, assign its instructors, then add students." only %}
    {% endif %}
  </div>
  <div class="col-lg-4">
    <div class="card"><div class="card-body">
      <h2 class="h5">New offering</h2>
      <form method="post" novalidate>
        {% csrf_token %}
        {% include "includes/form_fields.html" with form=form only %}
        <button class="btn btn-primary">Create offering</button>
      </form>
    </div></div>
  </div>
</div>
{% endblock %}
```

The `onchange` submit is the only inline JavaScript in this story. The `<noscript>` button keeps the filter working without it.

```django
{# apps/catalog/templates/catalog/offering_edit.html #}
{% extends "catalog/department_base.html" %}
{% block title %}Edit {{ offering.course.code }} · POlaris{% endblock %}
{% block department %}
<div style="max-width: 40rem">
  <p class="text-body-secondary mb-1">{{ offering.term.name }}</p>
  <h1 class="h3 mb-3">{{ offering.course.code }} · {{ offering.course.title }}</h1>
  {% if is_closed %}
    <div class="alert alert-secondary" role="status">🔒 {{ offering.term.name }} is closed. Reopen the term to change this offering.</div>
  {% endif %}
  <form method="post" novalidate>
    {% csrf_token %}
    <fieldset {% if is_closed %}disabled{% endif %}>
      {% include "includes/form_fields.html" with form=form only %}
      <button class="btn btn-primary">Save</button>
    </fieldset>
    <a class="btn btn-link px-0 mt-2" href="{% url 'catalog:offerings' %}">Back to offerings</a>
  </form>
</div>
{% endblock %}
```

```django
{# apps/catalog/templates/catalog/enrollments.html #}
{% extends "catalog/department_base.html" %}
{% block title %}Students · {{ offering.course.code }} · POlaris{% endblock %}
{% block department %}
<p class="text-body-secondary mb-1">{{ offering.term.name }} · Section {{ offering.section }}</p>
<h1 class="h3 mb-3">Students in {{ offering.course.code }}</h1>
{% if is_closed %}
  <div class="alert alert-secondary" role="status">🔒 {{ offering.term.name }} is closed. The class list is read-only.</div>
{% endif %}
<div class="row g-4">
  <div class="col-lg-8">
    {% if enrollments %}
      <table class="table table-sm align-middle">
        <thead><tr><th scope="col">Student no.</th><th scope="col">Name</th><th scope="col">Email</th>
                   <th scope="col">Status</th><th scope="col"><span class="visually-hidden">Actions</span></th></tr></thead>
        <tbody>
        {% for e in enrollments %}
          <tr{% if e.status == "dropped" %} class="text-body-secondary"{% endif %}>
            <td class="tabular-nums">{{ e.student.student_number }}</td>
            <td>{{ e.student.get_full_name }}</td>
            <td class="small">{{ e.student.email }}</td>
            <td>{% if e.status == "dropped" %}<span class="badge text-bg-light">Dropped</span>{% else %}Enrolled{% endif %}</td>
            <td class="text-end">
              {% if e.status == "enrolled" and not is_closed %}
                <form method="post" class="d-inline">
                  {% csrf_token %}
                  <input type="hidden" name="action" value="drop">
                  <input type="hidden" name="enrollment_id" value="{{ e.pk }}">
                  <button class="btn btn-sm btn-outline-danger"
                          aria-label="Drop {{ e.student.get_full_name }}">Drop</button>
                </form>
              {% endif %}
            </td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    {% else %}
      {% include "includes/empty_state.html" with title="No students yet" message="Add students one by one on the right, or import the class list as CSV." only %}
    {% endif %}
  </div>
  {% if not is_closed %}
  <div class="col-lg-4">
    <div class="card"><div class="card-body">
      <h2 class="h5">Add a student</h2>
      <p class="small text-body-secondary">Existing student: the number is enough. New student: fill in every field.</p>
      <form method="post" novalidate>
        {% csrf_token %}
        <input type="hidden" name="action" value="add">
        {% include "includes/form_fields.html" with form=form only %}
        <button class="btn btn-primary">Add</button>
      </form>
      {% url 'catalog:enrollment_import' as import_url %}
      {% if import_url %}<p class="mt-3 mb-0"><a href="{{ import_url }}?offering={{ offering.pk }}">Import a CSV class list instead</a></p>{% endif %}
    </div></div>
  </div>
  {% endif %}
</div>
{% endblock %}
```

Drop has no confirmation dialog. It is undoable: add the same student again and they are re-enrolled with their grades intact. *Getting Real* argues for undo over "are you sure?" when undo is cheap.

```django
{# apps/catalog/templates/catalog/po_sets.html #}
{% extends "catalog/department_base.html" %}
{% block title %}Program outcomes · POlaris{% endblock %}
{% block department %}
<h1 class="h3 mb-3">{{ program.code }} program outcome sets</h1>
<p class="text-body-secondary">Students are measured against the newest set whose start year is on or before their cohort (policy P13). New mappings always use the <strong>active</strong> set.</p>
<div class="list-group" style="max-width: 44rem">
  {% for s in sets %}
    <a class="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
       href="{% url 'catalog:po_set' set_id=s.pk %}">
      <span><span class="fw-semibold">{{ s.label }}</span>
        <span class="small text-body-secondary">· cohorts from {{ s.effective_from_year }} · {{ s.n }} outcomes</span></span>
      {% if s.is_active %}<span class="badge text-bg-success">Active</span>{% endif %}
    </a>
  {% endfor %}
</div>
{% endblock %}
```

```django
{# apps/catalog/templates/catalog/po_set_detail.html #}
{% extends "catalog/department_base.html" %}
{% block title %}{{ po_set.label }} · POlaris{% endblock %}
{% block department %}
<div class="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-3">
  <div>
    <h1 class="h3 mb-1">{{ po_set.label }} {% if po_set.is_active %}<span class="badge text-bg-success align-middle fs-6">Active</span>{% endif %}</h1>
    <p class="text-body-secondary mb-0">For cohorts from {{ po_set.effective_from_year }}</p>
  </div>
  {% if not po_set.is_active %}
    <form method="post" action="{% url 'catalog:po_set_activate' set_id=po_set.pk %}">
      {% csrf_token %}
      <button class="btn btn-warning">Make this the active set</button>
    </form>
  {% endif %}
</div>
<table class="table align-middle">
  <thead><tr><th scope="col">PO</th><th scope="col">Short name</th><th scope="col">Official wording</th>
             <th scope="col" class="text-end">LO links</th><th scope="col"><span class="visually-hidden">Actions</span></th></tr></thead>
  <tbody>
  {% for po in outcomes %}
    <tr>
      <td class="fw-semibold">{{ po.number }}</td>
      <td>{{ po.short_name }}</td>
      <td class="small">{{ po.description }}</td>
      <td class="text-end tabular-nums">{{ po.links }}</td>
      <td class="text-end text-nowrap">
        <a class="btn btn-sm btn-outline-secondary" href="{% url 'catalog:po_edit' po_id=po.pk %}">Edit</a>
        {% if po.links == 0 %}
          <a class="btn btn-sm btn-outline-danger" href="{% url 'catalog:po_delete' po_id=po.pk %}"
             hx-get="{% url 'catalog:po_delete' po_id=po.pk %}" hx-target="#modal-content"
             data-bs-toggle="modal" data-bs-target="#modal">Delete</a>
        {% endif %}
      </td>
    </tr>
  {% endfor %}
  </tbody>
</table>
<details class="card" style="max-width: 36rem" {% if copy_form.errors %}open{% endif %}>
  <summary class="card-header">Create a new version from this set</summary>
  <div class="card-body">
    <p class="small text-body-secondary">Copies all {{ outcomes|length }} outcomes. The copy stays inactive until you activate it.</p>
    <form method="post" action="{% url 'catalog:po_set_copy' set_id=po_set.pk %}" novalidate>
      {% csrf_token %}
      {% include "includes/form_fields.html" with form=copy_form only %}
      <button class="btn btn-primary">Copy set</button>
    </form>
  </div>
</details>
{% endblock %}
```

The delete link is a normal link (a full confirmation page) and also an HTMX trigger that loads the same page's `confirm` partial into a modal. Without JavaScript you get the page; with it, the modal. It uses the one shared modal that S1-09 put in `base.html` (`#modal`, with HTMX filling `#modal-content`). S2-04's LO and assessment deletes reuse it.

```django
{# apps/catalog/templates/catalog/po_delete.html #}
{% extends "catalog/department_base.html" %}
{% block title %}Delete PO {{ po.number }} · POlaris{% endblock %}
{% block department %}
<div class="card" style="max-width: 36rem">
  {% partialdef confirm inline %}
  <div class="modal-header"><h2 class="modal-title h5">Delete PO {{ po.number }} · {{ po.short_name }}?</h2></div>
  <div class="modal-body">
    {% if used_by %}
      <div class="alert alert-danger mb-0" role="alert">
        PO {{ po.number }} is used by {{ used_by|join:", " }}. It can't be deleted. Edit its wording instead.
      </div>
    {% else %}
      <p class="mb-0">No course links to this outcome, so nothing else changes. The deletion is recorded in the audit trail.</p>
    {% endif %}
  </div>
  <div class="modal-footer">
    <a class="btn btn-link" href="{% url 'catalog:po_set' set_id=po.po_set_id %}" data-bs-dismiss="modal">Cancel</a>
    {% if not used_by %}
      <form method="post" action="{% url 'catalog:po_delete' po_id=po.pk %}">
        {% csrf_token %}
        <button class="btn btn-danger">Delete PO {{ po.number }}</button>
      </form>
    {% endif %}
  </div>
  {% endpartialdef %}
</div>
{% endblock %}
```

`inline` renders the partial in place on the full page, and the view renders `po_delete.html#confirm` alone for HTMX (§8.5 "Modal content").

### Tests

Service tests prove the rules. View tests prove the head can actually do the job through the browser layer, and that errors come back as messages on the page instead of 500s.

```python
# apps/catalog/tests/test_services.py
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.services import get_or_create_student
from apps.catalog import services
from apps.catalog.models import Enrollment, ProgramOutcomeSet, Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import (
    CourseFactory, EnrollmentFactory, LearningOutcomeFactory, LOPOWeightFactory, MembershipFactory,
    OfferingFactory, ProgramFactory, ProgramOutcomeFactory, ProgramOutcomeSetFactory, TermFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def head():
    return UserFactory(email="head@acibadem.edu.tr")


@pytest.fixture
def cse():
    return ProgramFactory(code="TST")


@pytest.fixture
def term():
    return TermFactory(code="2026F", name="Fall 2026", starts_on=date(2026, 9, 21),
                       ends_on=date(2027, 1, 15), status=Term.Status.OPEN)


@pytest.fixture
def offering(cse, term):
    return OfferingFactory(course=CourseFactory(program=cse, code="CSE 311"), term=term)


@pytest.fixture
def student(cse):
    user = UserFactory(student_number="2023001")
    MembershipFactory(user=user, program=cse, role="student", cohort_year=2023)
    return user


# ---------- terms ----------

def test_term_lifecycle_and_audit(head):
    term = services.create_term(head, code="2027S", name="Spring 2027",
                                 starts_on=date(2027, 2, 15), ends_on=date(2027, 6, 20))
    assert term.status == Term.Status.PLANNED
    services.set_term_status(head, term, Term.Status.OPEN)
    services.set_term_status(head, term, Term.Status.CLOSED)
    term.refresh_from_db()
    assert term.status == Term.Status.CLOSED
    actions = list(AuditEvent.objects.filter(entity_type="term").order_by("created_at", "id")
                   .values_list("action", flat=True))
    assert actions == ["term.create", "term.open", "term.close"]


@pytest.mark.parametrize("start,target", [
    (Term.Status.PLANNED, Term.Status.CLOSED),
    (Term.Status.OPEN, Term.Status.PLANNED),
    (Term.Status.OPEN, Term.Status.OPEN),
])
def test_invalid_term_transitions_refused(head, start, target):
    term = TermFactory(status=start)
    with pytest.raises(ValidationError):
        services.set_term_status(head, term, target)


def test_reopen_needs_a_reason_and_records_it(head, term):
    services.set_term_status(head, term, Term.Status.CLOSED)
    with pytest.raises(ValidationError):
        services.set_term_status(head, term, Term.Status.OPEN, reason="oops")
    services.set_term_status(head, term, Term.Status.OPEN, reason="Grade appeal approved by the board")
    event = AuditEvent.objects.get(action="term.reopen")
    assert event.after == {"status": "open", "reason": "Grade appeal approved by the board"}
    assert event.actor == head


def test_update_term_cannot_change_status(head, term):
    with pytest.raises(ValueError):
        services.update_term(head, term, status=Term.Status.CLOSED)


# ---------- courses ----------

def test_course_code_normalised_and_unique_per_program(head, cse):
    course = services.save_course(head, program=cse, code="cse  311", title="Software",
                                  credits=3, ects=6)
    assert course.code == "CSE 311"
    with pytest.raises(ValidationError) as err:
        services.save_course(head, program=cse, code="CSE 311", title="Dup", credits=3, ects=6)
    assert "already exists" in str(err.value)
    other = ProgramFactory(code="BME")
    assert services.save_course(head, program=other, code="CSE 311", title="Elsewhere", credits=3, ects=6)


# ---------- offerings ----------

def test_create_offering_with_instructors(head, cse, term):
    teacher = UserFactory()
    MembershipFactory(user=teacher, program=cse, role="instructor")
    offering = services.create_offering(head, course=CourseFactory(program=cse), term=term,
                                        section="1", instructors=[teacher])
    assert list(offering.instructors.all()) == [teacher]
    event = AuditEvent.objects.get(action="offering.create")
    assert event.offering == offering and event.after["instructors"] == [teacher.email]


def test_non_instructor_cannot_be_assigned(head, cse, term):
    random_user = UserFactory()
    with pytest.raises(ValidationError) as err:
        services.create_offering(head, course=CourseFactory(program=cse), term=term, instructors=[random_user])
    assert "instructors" in err.value.message_dict


def test_duplicate_section_refused(head, offering):
    with pytest.raises(ValidationError):
        services.create_offering(head, course=offering.course, term=offering.term, section=offering.section)


def test_no_offerings_in_closed_term(head, cse):
    closed = TermFactory(status=Term.Status.CLOSED)
    with pytest.raises(ValidationError):
        services.create_offering(head, course=CourseFactory(program=cse), term=closed)


def test_update_offering_blocked_when_term_closed(head, offering):
    offering.term.status = Term.Status.CLOSED
    offering.term.save()
    with pytest.raises(ValidationError) as err:
        services.update_offering(head, offering, section="2")
    assert "is closed" in str(err.value)


# ---------- enrollments ----------

def test_enroll_twice_is_a_message_not_a_crash(head, offering, student):
    """B3 AC 4."""
    services.enroll(head, offering, student)
    with pytest.raises(ValidationError) as err:
        services.enroll(head, offering, student)
    assert "already enrolled" in str(err.value)
    assert Enrollment.objects.filter(offering=offering, student=student).count() == 1


def test_drop_keeps_row_and_reenroll_restores_it(head, offering, student):
    enrollment = services.enroll(head, offering, student)
    services.drop(head, enrollment)
    enrollment.refresh_from_db()
    assert enrollment.status == Enrollment.Status.DROPPED
    again = services.enroll(head, offering, student)
    assert again.pk == enrollment.pk and again.status == Enrollment.Status.ENROLLED


def test_cannot_enroll_non_student(head, offering):
    with pytest.raises(ValidationError):
        services.enroll(head, offering, UserFactory())


def test_closed_term_blocks_enrollment_changes(head, offering, student):
    """B3 AC 3, service side."""
    enrollment = EnrollmentFactory(offering=offering, student=student)
    offering.term.status = Term.Status.CLOSED
    offering.term.save()
    with pytest.raises(ValidationError):
        services.drop(head, enrollment)
    with pytest.raises(ValidationError):
        services.enroll(head, offering, UserFactory())


def test_get_or_create_student_matches_by_number(head, cse, student):
    found, created = get_or_create_student(student_number="2023001", email="", first_name="", last_name="",
                                           program=cse, cohort_year=None, actor=head)
    assert found == student and not created


def test_get_or_create_student_creates_with_unusable_password(head, cse):
    user, created = get_or_create_student(student_number="2024777", email="Ada@Acibadem.edu.tr",
                                          first_name="Ada", last_name="Kaya", program=cse,
                                          cohort_year=2024, actor=head)
    assert created and not user.has_usable_password()
    assert user.memberships.get().cohort_year == 2024


def test_get_or_create_student_rejects_email_of_someone_else(head, cse):
    UserFactory(email="taken@acibadem.edu.tr")
    with pytest.raises(ValidationError) as err:
        get_or_create_student(student_number="2024888", email="taken@acibadem.edu.tr", first_name="A",
                              last_name="B", program=cse, cohort_year=2024, actor=head)
    assert "email" in err.value.message_dict


def test_get_or_create_student_needs_cohort_for_new_membership(head, cse):
    existing = UserFactory(student_number="2022555")          # account exists, no membership in CSE
    with pytest.raises(ValidationError) as err:
        get_or_create_student(student_number="2022555", email=existing.email, first_name="", last_name="",
                              program=cse, cohort_year=None, actor=head)
    assert "cohort_year" in err.value.message_dict


# ---------- PO sets ----------

@pytest.fixture
def active_set(cse):
    po_set = ProgramOutcomeSetFactory(program=cse, label="2023 curriculum", effective_from_year=2020,
                                      is_active=True)
    for n in range(1, 12):
        ProgramOutcomeFactory(po_set=po_set, number=n, short_name=f"PO {n} name")
    return po_set


def test_copy_po_set_copies_everything_inactive(head, active_set):
    """B2 AC 2, first half."""
    copy = services.copy_po_set(head, active_set, label="2027 curriculum", effective_from_year=2027)
    assert copy.outcomes.count() == 11 and not copy.is_active
    assert list(copy.outcomes.values_list("number", flat=True)) == list(range(1, 12))


def test_activate_switches_the_single_active_set(head, active_set, cse):
    """B2 AC 2, second half: exactly one active set afterwards."""
    copy = services.copy_po_set(head, active_set, label="2027 curriculum", effective_from_year=2027)
    services.activate_po_set(head, copy)
    assert list(ProgramOutcomeSet.objects.filter(program=cse, is_active=True)) == [copy]
    event = AuditEvent.objects.get(action="po_set.activate")
    assert event.before == {"active": "2023 curriculum"} and event.after == {"active": "2027 curriculum"}


def test_empty_set_cannot_be_activated(head, cse):
    empty = ProgramOutcomeSetFactory(program=cse, label="empty", effective_from_year=2030, is_active=False)
    with pytest.raises(ValidationError):
        services.activate_po_set(head, empty)


def test_copy_label_must_be_unique(head, active_set):
    with pytest.raises(ValidationError):
        services.copy_po_set(head, active_set, label="2023 curriculum", effective_from_year=2027)


def test_delete_referenced_po_names_the_courses(head, active_set, offering):
    """B2 AC 3."""
    po = active_set.outcomes.get(number=3)
    LOPOWeightFactory(learning_outcome=LearningOutcomeFactory(offering=offering, number=1),
                      program_outcome=po, weight=4)
    with pytest.raises(ValidationError) as err:
        services.delete_po(head, po)
    assert "CSE 311 (Fall 2026)" in str(err.value)
    assert active_set.outcomes.filter(number=3).exists()


def test_delete_unused_po_is_audited(head, active_set):
    po = active_set.outcomes.get(number=11)
    services.delete_po(head, po)
    assert not active_set.outcomes.filter(number=11).exists()
    assert AuditEvent.objects.get(action="po.delete").before["number"] == 11


def test_update_po_only_wording(head, active_set):
    po = active_set.outcomes.get(number=1)
    services.update_po(head, po, short_name="Math & science")
    with pytest.raises(ValueError):
        services.update_po(head, po, number=99)
```

```python
# apps/catalog/tests/test_views.py
import pytest
from django.urls import reverse

from apps.catalog.models import CourseOffering, Enrollment, Term
from apps.core.tests.factories import (
    CourseFactory, MembershipFactory, OfferingFactory, ProgramFactory, ProgramOutcomeFactory,
    ProgramOutcomeSetFactory, TermFactory, UserFactory,
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

    r = head_client.post(reverse("catalog:terms"), {"code": "2026F", "name": "Fall 2026",
                                                    "starts_on": "2026-09-21", "ends_on": "2027-01-15"})
    assert r.status_code == 302
    term = Term.objects.get(code="2026F")
    head_client.post(reverse("catalog:term_status", kwargs={"term_id": term.pk}), {"action": "open"})

    r = head_client.post(reverse("catalog:courses"), {"code": "cse 311", "title": "Software",
                                                      "credits": "3", "ects": "6"})
    assert r.status_code == 302
    course = cse.courses.get(code="CSE 311")

    r = head_client.post(reverse("catalog:offerings"), {"course": course.pk, "term": term.pk,
                                                        "section": "1", "instructors": [teacher.pk]})
    offering = CourseOffering.objects.get(course=course, term=term)
    assert r["Location"] == reverse("catalog:enrollments", kwargs={"offering_id": offering.pk})

    r = head_client.post(r["Location"], {"action": "add", "student_number": "2023001",
                                         "email": "elif@live.acibadem.edu.tr", "first_name": "Elif",
                                         "last_name": "Yıldız", "cohort_year": "2023"})
    assert r.status_code == 302
    assert Enrollment.objects.get(offering=offering).student.email == "elif@live.acibadem.edu.tr"


def test_term_with_end_before_start_shows_field_error(head_client):
    r = head_client.post(reverse("catalog:terms"), {"code": "X", "name": "X",
                                                    "starts_on": "2027-01-15", "ends_on": "2026-09-21"})
    assert r.status_code == 200
    assert "must end after it starts" in r.text


def test_reopen_without_reason_shows_error(head_client):
    term = TermFactory(status=Term.Status.CLOSED)
    r = head_client.post(reverse("catalog:term_status", kwargs={"term_id": term.pk}),
                         {"action": "reopen", "reason": ""}, follow=True)
    assert "Say why the term is being reopened" in r.text
    term.refresh_from_db()
    assert term.status == Term.Status.CLOSED


def test_duplicate_enrollment_shows_message(head_client, cse):
    offering = OfferingFactory(course=CourseFactory(program=cse), term=TermFactory(status=Term.Status.OPEN))
    student = UserFactory(student_number="2023001")
    MembershipFactory(user=student, program=cse, role="student", cohort_year=2023)
    url = reverse("catalog:enrollments", kwargs={"offering_id": offering.pk})
    head_client.post(url, {"action": "add", "student_number": "2023001"})
    r = head_client.post(url, {"action": "add", "student_number": "2023001"})
    assert r.status_code == 200 and "already enrolled" in r.text


def test_closed_term_enrollment_page_is_read_only(head_client, cse):
    """B3 AC 3 on the head's side: no add form, no drop buttons."""
    offering = OfferingFactory(course=CourseFactory(program=cse), term=TermFactory(status=Term.Status.CLOSED))
    r = head_client.get(reverse("catalog:enrollments", kwargs={"offering_id": offering.pk}))
    assert "is closed" in r.text and 'value="add"' not in r.text


def test_other_programs_objects_are_404(head_client):
    bme = ProgramFactory(code="BME")
    foreign = CourseFactory(program=bme, code="BME 101")
    assert head_client.get(reverse("catalog:course_edit", kwargs={"course_id": foreign.pk})).status_code == 404


def test_po_delete_modal_partial_for_htmx(head_client, cse):
    po_set = ProgramOutcomeSetFactory(program=cse, label="2023", effective_from_year=2020, is_active=True)
    po = ProgramOutcomeFactory(po_set=po_set, number=11)
    r = head_client.get(reverse("catalog:po_delete", kwargs={"po_id": po.pk}), headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "<nav" not in r.text and "Delete PO 11" in r.text


def test_fresh_install_shows_eleven_official_pos(head_client):
    """B2 AC 1. Needs the S1-05 data migration, so it uses the migrated CSE program."""
    from apps.catalog.models import Program
    program = Program.objects.get(code="CSE")
    active = program.po_sets.get(is_active=True)
    assert active.outcomes.count() == 11
    assert active.outcomes.get(number=1).description.startswith("Gain adequate knowledge in mathematics")
```

That last test reads the real data migration (S1-05), so it can't use the `cse` fixture: a factory-made program has no POs.

**Why every fixture uses `code="TST"`.** pytest-django builds the test database by running all migrations, including S1-05's data migration, which creates the real `CSE` program. A fixture that makes another program with code `CSE` would hit the unique constraint on `Program.code`. So test programs are called `TST` (and `BME` for "another program"). The fixtures keep the name `cse` because that's what they stand for. Make sure S1-08's `ProgramFactory` default is not `CSE` either, for example `factory.Sequence(lambda n: f"P{n:03d}")`.

> Check the first words of PO 1 against Appendix A when you write the test. They must match the official text exactly.

### Check it works

1. Log in as the head. *Terms* → create `2027S Spring 2027` → it shows *Planned* → *Open* → *Close*.
2. Click *Reopen…* with an empty reason → the browser stops you (`required`). Remove `required` in dev tools and submit → the page shows "Say why the term is being reopened…". Type a real reason → *Open*.
3. `/admin/core/auditevent/` → the `term.reopen` event shows your reason in *after*.
4. *Courses* → add `cse 311` → it is saved as `CSE 311`. Add it again → "CSE 311 already exists in CSE."
5. *Offerings* → create CSE 311 in Fall 2026, tick Dr. Aydın → you land on *Students* → add Elif by number only → a new number without the other fields gives a clear message.
6. Close Fall 2026 → *Students* for CSE 311 shows the 🔒 banner and no forms. Log in as Dr. Aydın → his course's setup pages answer 403 with the closed-term message.
7. *Program outcomes* → *2023 curriculum* → copy it to *2027 curriculum* → activate → only the new one shows *Active*. Try deleting a PO that seed data links → the dialog names the courses.

### Done when

| AC | Proved by |
|---|---|
| B2 AC 1: 11 POs with official wording on a fresh install | `test_fresh_install_shows_eleven_official_pos` |
| B2 AC 2: copy, activate, one active set | `test_copy_po_set_copies_everything_inactive`, `test_activate_switches_the_single_active_set` |
| B2 AC 3: referenced PO can't be deleted, message names courses | `test_delete_referenced_po_names_the_courses` |
| B3 AC 3: closed term read-only | `test_closed_term_blocks_enrollment_changes`, `test_closed_term_enrollment_page_is_read_only`, matrix `test_closed_term_blocks_every_edit_route` |
| B3 AC 4: duplicate student reported, not crashed | `test_enroll_twice_is_a_message_not_a_crash`, `test_duplicate_enrollment_shows_message` |
| Reopen asks for a reason, stored in audit (B3) | `test_reopen_needs_a_reason_and_records_it` |
| Every write audited | the `AuditEvent` assertions above |
| Department rows in the matrix pass | `test_permission_matrix` (`catalog:*` rows) |

### Commits and PR

```
Add term, course and offering services with audit events (#23)
Add enrollment and student lookup services (#23)
Add PO set copy, activate and safe delete (#23)
Add department pages for terms, courses, offerings and students (#23)
Add program outcome pages with HTMX delete confirmation (#23)
```

PR title: **Department catalog management (S2-03)**. This PR will be over the 400-line guideline (§0.4). Split it into two if review drags: services + tests first, then views + templates.

---

## S2-09 · Password reset by email

**Points:** 1 · **Owner:** Person B · **Branch:** `feature/S2-09-password-reset` · **Depends on:** S2-01

### Goal

A user who forgot their password requests a reset link by email, follows it once, and sets a new password. In development the email is printed in the `runserver` console. On staging and production it goes out over SMTP (`EMAIL_URL`, §4.6). This delivers B1 AC 3.

Django ships all four views. Our work is to put them under our `accounts:` namespace, which needs two `success_url` overrides and our own email template. Then we give them our templates. Two security properties come for free, and the tests pin them so nobody breaks them later:

- **No account enumeration.** The form says "check your inbox" whether or not the email exists.
- **Single use.** The token is derived from the user's password hash and last-login time. Once the password changes, the old link stops working. Links also expire after `PASSWORD_RESET_TIMEOUT`, which we set to 24 hours (Django's default is 3 days).

**One limitation.** Django sends reset emails only to accounts with a *usable* password. Students created by the enrollment import (S3-05) start with an unusable password, so the forgot-password form silently ignores them. That is why S3-05 sends a separate "set your password" email through `accounts.services.send_set_password_email`, which reuses the same confirm view and token.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/accounts/urls.py` | modify | four password-reset URLs |
| `config/settings/base.py` | modify | `PASSWORD_RESET_TIMEOUT`, `DEFAULT_FROM_EMAIL` default |
| `apps/accounts/templates/accounts/password_reset_form.html` | create | ask for email |
| `apps/accounts/templates/accounts/password_reset_done.html` | create | "check your inbox" |
| `apps/accounts/templates/accounts/password_reset_confirm.html` | create | new password form, or "link invalid" |
| `apps/accounts/templates/accounts/password_reset_complete.html` | create | done, go log in |
| `apps/accounts/templates/accounts/password_reset_subject.txt` | create | email subject |
| `apps/accounts/templates/accounts/password_reset_email.txt` | create | email body with the namespaced link |
| `apps/accounts/tests/test_password_reset.py` | create | tests |

### Steps

#### Step 1: URLs

Django's views reverse un-namespaced names like `password_reset_done` by default. Under `app_name = "accounts"` those names don't exist, so each view gets its `success_url` and templates explicitly. The confirm URL has two segments (`<uidb64>/<token>/`), so it can't collide with `done/` or `complete/`.

```python
# apps/accounts/urls.py  (complete after this story)
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("role/", views.switch_role, name="switch_role"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]
```

#### Step 2: settings

```python
# config/settings/base.py  (add)
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24          # links work for 24 hours
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="POlaris <noreply@localhost>")
```

`prod.py` already reads `DEFAULT_FROM_EMAIL` and `EMAIL_URL` (§10.3). `dev.py` prints mail to the console and `test.py` stores it in `mail.outbox`, so nothing else changes.

#### Step 3: the email

The link is built from `protocol` and `domain`, which Django fills from the incoming request. Behind Caddy, `SECURE_PROXY_SSL_HEADER` (prod settings) makes the protocol `https`.

```django
{# apps/accounts/templates/accounts/password_reset_subject.txt #}
Reset your POlaris password
```

```django
{# apps/accounts/templates/accounts/password_reset_email.txt #}{% autoescape off %}
Hello {{ user.first_name|default:user.email }},

Someone (hopefully you) asked to reset the password for your POlaris account.
Open this link to choose a new password. It works once and expires in 24 hours:

{{ protocol }}://{{ domain }}{% url 'accounts:password_reset_confirm' uidb64=uid token=token %}

If you didn't ask for this, ignore this email. Your password stays the same.

POlaris · Acıbadem University Computer Engineering
{% endautoescape %}
```

The subject template must be a single line. Django joins multiple lines, but a trailing newline in the file is fine.

#### Step 4: the four pages

```django
{# apps/accounts/templates/accounts/password_reset_form.html #}
{% extends "base.html" %}
{% block title %}Reset password · POlaris{% endblock %}
{% block content %}
<div class="container py-5" style="max-width: 28rem">
  <h1 class="h3 mb-3">Reset your password</h1>
  <p class="text-body-secondary">Enter your university email. If it belongs to a POlaris account, we'll send a link.</p>
  <form method="post" novalidate>
    {% csrf_token %}
    <div class="mb-3">
      <label class="form-label" for="{{ form.email.id_for_label }}">University email</label>
      <input type="email" class="form-control{% if form.email.errors %} is-invalid{% endif %}"
             name="{{ form.email.html_name }}" id="{{ form.email.id_for_label }}"
             value="{{ form.email.value|default:'' }}" autocomplete="email" required autofocus>
      {% for error in form.email.errors %}<div class="invalid-feedback">{{ error }}</div>{% endfor %}
    </div>
    <button class="btn btn-primary w-100">Send reset link</button>
  </form>
  <p class="mt-3 text-center"><a href="{% url 'accounts:login' %}">Back to log in</a></p>
</div>
{% endblock %}
```

```django
{# apps/accounts/templates/accounts/password_reset_done.html #}
{% extends "base.html" %}
{% block title %}Check your email · POlaris{% endblock %}
{% block content %}
<div class="container py-5" style="max-width: 28rem">
  <h1 class="h3 mb-3">Check your email</h1>
  <p>If that address belongs to a POlaris account, a reset link is on its way. It expires in 24 hours.</p>
  <p class="text-body-secondary small">Nothing after a few minutes? Check your spam folder, or ask the department to check the address on your account.</p>
  <a href="{% url 'accounts:login' %}">Back to log in</a>
</div>
{% endblock %}
```

```django
{# apps/accounts/templates/accounts/password_reset_confirm.html #}
{% extends "base.html" %}
{% block title %}Choose a new password · POlaris{% endblock %}
{% block content %}
<div class="container py-5" style="max-width: 28rem">
  {% if validlink %}
    <h1 class="h3 mb-3">Choose a new password</h1>
    <form method="post" novalidate>
      {% csrf_token %}
      {% for field in form %}
        <div class="mb-3">
          <label class="form-label" for="{{ field.id_for_label }}">{{ field.label }}</label>
          <input type="password" class="form-control{% if field.errors %} is-invalid{% endif %}"
                 name="{{ field.html_name }}" id="{{ field.id_for_label }}" autocomplete="new-password" required>
          {% if field.help_text %}<div class="form-text">{{ field.help_text|safe }}</div>{% endif %}
          {% for error in field.errors %}<div class="invalid-feedback">{{ error }}</div>{% endfor %}
        </div>
      {% endfor %}
      <button class="btn btn-primary w-100">Set password</button>
    </form>
  {% else %}
    <h1 class="h3 mb-3">This link doesn't work any more</h1>
    <p>Reset links work once and expire after 24 hours.</p>
    <a class="btn btn-primary" href="{% url 'accounts:password_reset' %}">Send a new link</a>
  {% endif %}
</div>
{% endblock %}
```

`field.help_text|safe` is safe here: it's Django's own validator text (an HTML list), not user input.

```django
{# apps/accounts/templates/accounts/password_reset_complete.html #}
{% extends "base.html" %}
{% block title %}Password changed · POlaris{% endblock %}
{% block content %}
<div class="container py-5" style="max-width: 28rem">
  <h1 class="h3 mb-3">Password changed</h1>
  <p>You can log in with your new password now.</p>
  <a class="btn btn-primary" href="{% url 'accounts:login' %}">Log in</a>
</div>
{% endblock %}
```

### Tests

The confirm link works in two hops. A GET on the emailed URL validates the token, stores it in the session, and redirects to `/password-reset/<uid>/set-password/`, so the token never sits in the browser history or a `Referer` header. The test follows that redirect.

```python
# apps/accounts/tests/test_password_reset.py
import re

import pytest
from django.core import mail
from django.urls import reverse

from apps.core.tests.factories import UserFactory

pytestmark = pytest.mark.django_db
LINK = re.compile(r"https?://[^/\s]+(/password-reset/[^/\s]+/[^/\s]+/)")


@pytest.fixture
def user():
    u = UserFactory(email="elif@live.acibadem.edu.tr", first_name="Elif")
    u.set_password("old-password-1")
    u.save()
    return u


def _request_link(client, email) -> str:
    response = client.post(reverse("accounts:password_reset"), {"email": email})
    assert response["Location"] == reverse("accounts:password_reset_done")
    assert len(mail.outbox) == 1
    return LINK.search(mail.outbox[0].body).group(1)


def test_reset_email_link_works_once(client, user):
    """B1 AC 3."""
    link = _request_link(client, user.email)
    assert mail.outbox[0].subject == "Reset your POlaris password"

    set_password_url = client.get(link)["Location"]               # token moves into the session
    response = client.post(set_password_url, {"new_password1": "a-new-Pass-2026",
                                              "new_password2": "a-new-Pass-2026"})
    assert response["Location"] == reverse("accounts:password_reset_complete")
    user.refresh_from_db()
    assert user.check_password("a-new-Pass-2026")

    second = client.get(link, follow=True)                        # same link again
    assert second.context["validlink"] is False
    assert "doesn't work any more" in second.text


def test_unknown_email_looks_the_same_and_sends_nothing(client):
    """No account enumeration: same redirect, no email."""
    response = client.post(reverse("accounts:password_reset"), {"email": "nobody@acibadem.edu.tr"})
    assert response["Location"] == reverse("accounts:password_reset_done")
    assert mail.outbox == []


def test_user_without_usable_password_gets_no_email(client):
    """Imported students (S3-05) get the set-password email instead."""
    u = UserFactory(email="new@live.acibadem.edu.tr")
    u.set_unusable_password()
    u.save()
    client.post(reverse("accounts:password_reset"), {"email": u.email})
    assert mail.outbox == []


def test_weak_password_rejected(client, user):
    set_password_url = client.get(_request_link(client, user.email))["Location"]
    response = client.post(set_password_url, {"new_password1": "123", "new_password2": "123"})
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("old-password-1")


def test_login_page_links_to_reset(client):
    assert reverse("accounts:password_reset") in client.get(reverse("accounts:login")).text
```

`test_weak_password_rejected` assumes `AUTH_PASSWORD_VALIDATORS` from the generated settings is still in `base.py`. It is in the `startproject` template, and §10.3 doesn't remove it. Don't remove it.

### Check it works

1. `uv run python manage.py runserver`, open `/login/` → *Forgot your password?*
2. Enter Dr. Aydın's email → *Check your email*. The terminal running `runserver` shows the message with a link.
3. Open the link → set a new password → *Password changed* → log in with it.
4. Open the same link again → *This link doesn't work any more*.
5. Enter an email that doesn't exist → the same *Check your email* page, and nothing is printed.
6. On staging (after S2-08), repeat with a real inbox. If no email arrives, `docker compose -f compose.prod.yml logs web | grep -i smtp` shows the SMTP error.

### Done when

| AC | Proved by |
|---|---|
| B1 AC 3: reset email arrives, link works once | `test_reset_email_link_works_once` |
| No account enumeration | `test_unknown_email_looks_the_same_and_sends_nothing` |
| Password rules enforced | `test_weak_password_rejected` |
| Four reset rows in the matrix pass as public | `test_permission_matrix` (`accounts:password_reset*` rows) |

### Commits and PR

```
Add password reset pages under the accounts namespace (#24)
Send reset links with our own email template and 24-hour expiry (#24)
```

PR title: **Password reset by email (S2-09)**

---

## Code map additions

Names this chapter introduces that are not in spec §4.8. They go into §4.8 when these PRs merge.

| Module | Name | Signature | Purpose |
|---|---|---|---|
| `accounts/permissions.py` | `ROLE_ORDER` | `tuple[str, ...]` | head > instructor > student > admin; default active role and switcher order |
| `accounts/permissions.py` | `ordered_roles` | `(user) -> list[str]` | held roles in `ROLE_ORDER` order |
| `accounts/permissions.py` | `forget_roles` | `(user) -> None` | clear the per-request roles cache (tests) |
| `accounts/permissions.py` | `head_program` | `(user) -> Program \| None` | the program a head's `/department/` pages work on (until T2.6) |
| `accounts/permissions.py` | `head_program_or_404` | `(user) -> Program` | same, raising `Http404` when there is none. **Every** head view in later sprints uses this; don't write another helper |
| `accounts/decorators.py` | `require_offering_access` | `(*, edit=False, lookup=None)` | `lookup(**url_kwargs) -> offering_id \| None` for URLs without `offering_id` (jobs) |
| `accounts/decorators.py` | `CLOSED_TERM_MESSAGE` | `str` | text of the 403 on closed terms |
| `accounts/forms.py` | `GENERIC_LOGIN_ERROR` | `str` | B1 AC 2 wording |
| `accounts/tests/routes.py` | `Route`, `ROUTES`, `ROLES`, presets, `NOT_IN_MATRIX` | — | the permission matrix data |
| `catalog/selectors.py` | `teaching_offerings` | `(user) -> QuerySet[CourseOffering]` | offerings the user teaches, annotated `student_count` |
| `catalog/selectors.py` | `visible_enrollments` | `(user, offering, *, include_dropped=False)` | adds `include_dropped` to §4.8's signature |
| `catalog/services.py` | `update_term` | `(user, term, **fields) -> Term` | edit code/name/dates (status via `set_term_status`) |
| `catalog/services.py` | `courses_using_po` | `(po) -> list[str]` | "CSE 311 (Fall 2026)" labels for the delete warning |
| `catalog/services.py` | `TERM_TRANSITIONS` | `dict` | allowed term status moves → audit action |
| `accounts/services.py` | `get_or_create_student` | adds `actor=None` keyword | actor for the audit events |
| `core/middleware.py` | `SESSION_KEY` | `"active_role"` | session key for the active role |
| `core/navigation.py` | `safe_reverse`, `nav_items_for`, `offering_tabs`, `ROLE_LABELS` | see S2-01 | navbar, home redirect and offering tabs that grow as URLs appear |
| `core/views.py` | `ROLE_HOME` | `dict[str, tuple[str, ...]]` | candidate home pages per role |
| `core/forms.py` | `BootstrapFormMixin`, `add_service_errors` | see S2-03 | Bootstrap classes; service errors onto forms |
| `templates/includes/` | `navbar.html`, `offering_header.html`, `form_fields.html` | — | shared partials |
| `templates/403.html` | — | — | closed-term page |
| `catalog` templates | `department_base.html` | — | sub-navigation for `/department/` pages |
| `base.html` (S1-09) | `#modal` / `#modal-content` | — | one Bootstrap modal that HTMX fills (§8.5 "Modal content") |
| `apps/reports/urls_student.py` | `student:` namespace | — | included at `me/` by S3-02 |
| `config/settings/base.py` | `LOGIN_URL = "accounts:login"`, `LOGOUT_REDIRECT_URL`, `PASSWORD_RESET_TIMEOUT` | — | §10.3 has `LOGIN_URL = "login"`, which breaks with the namespace |
