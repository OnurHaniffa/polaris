from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.accounts.decorators import require_role
from apps.catalog.models import Enrollment

from . import selectors


@login_required
@require_role("student")
def profile(request):
    ctx = selectors.student_profile_context(request.user, viewer=request.user)
    return render(request, "reports/student_profile.html", ctx)


@login_required
@require_role("student")
def po_detail(request, po_id):
    ctx = selectors.po_contributions(request.user, po_id)
    ctx["back_url_name"] = "student:profile"
    template = "reports/po_detail.html#drawer" if request.htmx else "reports/po_detail.html"
    return render(request, template, ctx)


@login_required
@require_role("student")
def course(request, offering_id):
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("offering__course", "offering__term", "student"),
        offering_id=offering_id,
        student=request.user,
    )
    return render(
        request, "reports/student_course.html", selectors.student_course_context(enrollment)
    )


def transcript(request):
    """T2.4 (Sprint 8) placeholder."""
    raise Http404
