from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.accounts.decorators import require_offering_access, require_role
from apps.accounts.models import User
from apps.accounts.permissions import can_view_student, head_program_or_404
from apps.catalog.models import Term
from apps.catalog.selectors import default_report_term

from . import selectors
from .forms import DepartmentFilterForm


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


def _selected_terms(request, program):
    """Read the term filter from the query string. Returns (terms, include_open, form).
    Shared by the dashboard and every drill-down (S6-05)."""
    form = DepartmentFilterForm(request.GET or None)
    if form.is_bound and form.is_valid():
        term = form.cleaned_data["term"] or default_report_term()
        include_open = form.cleaned_data["include_open"]
    else:
        term = default_report_term()
        include_open = False
        form = DepartmentFilterForm(initial={"term": term, "include_open": False})
    terms = Term.objects.filter(starts_on__lte=term.starts_on) if term else Term.objects.none()
    return terms, include_open, form


@login_required
@require_role("head")
def department(request):
    program = head_program_or_404(request.user)
    terms, include_open, form = _selected_terms(request, program)
    ctx = selectors.department_context(program, terms=terms, include_open_terms=include_open)
    ctx["form"] = form
    return render(request, "reports/department.html", ctx)
