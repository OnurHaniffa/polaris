"""Every permission decision in POlaris (spec §3.4)."""

from __future__ import annotations

from dataclasses import dataclass

from django.http import Http404

from apps.accounts.models import ProgramMembership
from apps.catalog.models import Program, Term

Role = ProgramMembership.Role
ROLE_ORDER = (Role.HEAD.value, Role.INSTRUCTOR.value, Role.STUDENT.value, "admin")
_CACHE_ATTR = "_polaris_roles"


def _authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def roles_of(user) -> set[str]:
    if not _authenticated(user):
        return set()

    cached = getattr(user, _CACHE_ATTR, None)
    if cached is None:
        cached = frozenset(set(user.memberships.values_list("role", flat=True)) | ({"admin"} if user.is_superuser else set()))
        setattr(user, _CACHE_ATTR, cached)

    return set(cached)


def forget_roles(user):
    if hasattr(user, _CACHE_ATTR):
        delattr(user, _CACHE_ATTR)


def ordered_roles(user) -> list[str]:
    held = roles_of(user)
    return [role for role in ROLE_ORDER if role in held]


def is_head(user, program: Program | None = None) -> bool:
    if not _authenticated(user):
        return False

    qs = user.memberships.filter(role=Role.HEAD)
    if program is not None:
        qs = qs.filter(program=program)
    return qs.exists()


def head_program(user):
    if not _authenticated(user):
        return None

    membership = user.memberships.filter(role=Role.HEAD).select_related("program").order_by("program__code").first()
    if membership:
        return membership.program

    if user.is_superuser:
        return Program.objects.order_by("code").first()

    return None


def head_program_or_404(user):
    program = head_program(user)
    if program is None:
        raise Http404("No program")
    return program


def _teaches(user, offering) -> bool:
    return _authenticated(user) and offering.instructors.filter(pk=user.pk).exists()


def can_view_offering(user, offering) -> bool:
    if not _authenticated(user):
        return False
    if user.is_superuser:
        return True
    return is_head(user, offering.course.program) or _teaches(user, offering)


def _is_closed(offering) -> bool:
    return offering.term.status == Term.Status.CLOSED


def can_edit_offering(user, offering) -> bool:
    return can_view_offering(user, offering) and not _is_closed(offering)


def can_view_student(user, student) -> bool:
    if not _authenticated(user):
        return False
    if user.is_superuser or user.pk == student.pk:
        return True

    headed_programs = user.memberships.filter(role=Role.HEAD).values("program_id")

    return student.memberships.filter(
        role=Role.STUDENT,
        program_id__in=headed_programs,
    ).exists()


@dataclass(frozen=True)
class OfferingPerms:
    can_view: bool
    can_edit: bool
    can_publish: bool
    is_closed: bool


def offering_perms(user, offering) -> OfferingPerms:
    can_view = can_view_offering(user, offering)
    is_closed = _is_closed(offering)
    can_edit = can_view and not is_closed

    return OfferingPerms(
        can_view=can_view,
        can_edit=can_edit,
        can_publish=can_edit,
        is_closed=is_closed,
    )


# Compatibility helpers for code/tests from earlier iterations.
def has_role(user, role, program=None) -> bool:
    if not _authenticated(user):
        return False
    if user.is_superuser:
        return True

    qs = user.memberships.filter(role=role)
    if program is not None:
        qs = qs.filter(program=program)
    return qs.exists()


def can_manage_offering(user, offering) -> bool:
    """Dersi yönetmek (hoca atamak gibi) sadece bölüm başkanı ve admin içindir."""
    if not _authenticated(user):
        return False
    is_manager = user.is_superuser or is_head(user, offering.course.program)
    return is_manager and not _is_closed(offering)


def can_edit_setup(user, offering) -> bool:
    return can_edit_offering(user, offering)


def can_enter_grades(user, offering) -> bool:
    return can_edit_offering(user, offering)


def is_enrolled(user, offering) -> bool:
    if not _authenticated(user):
        return False
    return offering.enrollments.filter(student=user).exclude(status="dropped").exists()


def can_view_student_scores(user, student) -> bool:
    return can_view_student(user, student)
