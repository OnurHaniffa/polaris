"""Reusable access-control decorators for views (spec §3.4 rules 1 and 3)."""

from __future__ import annotations

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import Http404

from apps.accounts.permissions import offering_perms, roles_of
from apps.catalog.models import CourseOffering


def closed_term_message(term) -> str:
    """Shown on 403.html. Spec §3.4: "Fall 2025 is closed. Ask the department head to reopen it"."""
    return f"{term.name} is closed. Ask the department head to reopen it."


def require_role(*roles: str):
    """Allow users holding one of `roles` (superusers always pass).

    Anonymous → login redirect (302). Wrong role → 404, so a page's existence isn't revealed.
    """
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
    """Load the offering, check access, and pass `offering=` and `perms_for=` to the view.

    By default the offering id comes from the URL kwarg `offering_id` (consumed here, so the
    view doesn't receive it). For URLs without one (e.g. `/ingestion/<job_id>/`), pass
    `lookup=lambda **kw: <offering id>`; the URL kwargs are then left for the view untouched.

    Order: login → load (404 if missing) → can view? (404 if not) → can edit? (403 if not).
    """

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())

            offering_id = lookup(**kwargs) if lookup is not None else kwargs.pop("offering_id", None)

            if offering_id is None:
                raise Http404("Page not found")

            offering = CourseOffering.objects.select_related("course__program", "term").filter(pk=offering_id).first()
            if offering is None:
                raise Http404("Page not found")

            perms = offering_perms(request.user, offering)

            if not perms.can_view:
                raise Http404("Page not found")

            if edit and not perms.can_edit:
                raise PermissionDenied(closed_term_message(offering.term))

            return view(request, *args, offering=offering, perms_for=perms, **kwargs)

        return wrapped

    return decorator
