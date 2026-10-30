from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.decorators import require_offering_access
from apps.catalog.models import Enrollment
from apps.core.navigation import offering_tabs
from apps.outcomes.models import Assessment

from . import selectors, services
from .selectors import SheetCell


@login_required
@require_GET
@require_offering_access(edit=False)
def sheet(request, *, offering, perms_for, **_):
    data = selectors.grade_sheet(offering)
    return render(
        request,
        "grading/sheet.html",
        {
            "offering": offering,
            "perms_for": perms_for,
            "tabs": offering_tabs(offering, "grading:sheet"),
            "sheet": data,
        },
    )


@login_required
@require_POST
@require_offering_access(edit=True)
def cell(request, *, offering, perms_for, assessment_id, enrollment_id, **_):
    assessment = get_object_or_404(Assessment, pk=assessment_id, offering=offering)
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("student"),
        pk=enrollment_id,
        offering=offering,
        status=Enrollment.Status.ENROLLED,
    )
    raw = request.POST.get("value", "")
    ctx = {"offering": offering, "perms_for": perms_for}
    try:
        grade = services.save_grade(request.user, assessment, enrollment, raw)
    except ValidationError as exc:
        current = assessment.grades.filter(enrollment=enrollment).first()
        ctx |= {
            "cell": SheetCell(assessment, enrollment, current),
            "error": " ".join(exc.messages),
            "raw": raw,
        }
        # 200, not 422: HTMX 2 does not swap 4xx responses by default,
        # and we want the red cell shown.
        return HttpResponse(render_to_string("grading/sheet.html#cell", ctx, request))

    ctx |= {"cell": SheetCell(assessment, enrollment, grade), "saved": True}
    html = render_to_string("grading/sheet.html#cell", ctx, request)
    html += render_to_string(
        "grading/sheet.html#col_status",
        {
            "column": selectors.column_for(assessment),
            "oob": True,
            "offering": offering,
            "perms_for": perms_for,  # S3-01 puts the Publish button in this partial
        },
        request,
    )
    return HttpResponse(html)
