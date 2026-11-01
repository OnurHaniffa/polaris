from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.accounts.decorators import require_offering_access, require_role
from apps.accounts.models import User
from apps.accounts.permissions import can_view_student

from . import selectors


def _student_for_head(request, user_id) -> User:
    student = get_object_or_404(User, pk=user_id)
    if not can_view_student(request.user, student):
        raise Http404
    return student


@login_required
@require_role("head")
def department_student(request, user_id):
    student = _student_for_head(request, user_id)
    ctx = selectors.student_profile_context(student, viewer=request.user)
    return render(request, "reports/student_profile.html", ctx)


@login_required
@require_role("head")
def department_student_po(request, user_id, po_id):
    student = _student_for_head(request, user_id)
    ctx = selectors.po_contributions(student, po_id)
    template = "reports/po_detail.html#drawer" if request.htmx else "reports/po_detail.html"
    return render(request, template, ctx)


@login_required
@require_offering_access()
def course_results(request, offering, perms_for):
    ctx = selectors.course_results_context(offering)
    ctx["perms_for"] = perms_for
    return render(request, "reports/course_results.html", ctx)
