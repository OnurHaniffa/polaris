from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.decorators import require_offering_access, require_role
from apps.catalog.selectors import teaching_offerings, visible_enrollments
from apps.core.navigation import offering_tabs, safe_reverse


@login_required
@require_role("instructor", "head")
def teaching(request):
    offerings = list(teaching_offerings(request.user))
    return render(
        request,
        "catalog/teaching.html",
        {
            "offerings": offerings,
            "department_offerings_url": safe_reverse("catalog:offerings"),
        },
    )


@login_required
@require_offering_access()
def offering_home(request, offering, perms_for):
    return render(
        request,
        "catalog/offering_home.html",
        {
            "offering": offering,
            "perms_for": perms_for,
            "tabs": offering_tabs(offering, "catalog:offering"),
            "student_count": visible_enrollments(request.user, offering).count(),
        },
    )
