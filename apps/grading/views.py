from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django_htmx.http import HttpResponseClientRedirect
from .forms import PublishForm, UnpublishForm

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
def _back_to_sheet(request, offering):
    url = reverse("grading:sheet", kwargs={"offering_id": offering.id})
    return HttpResponseClientRedirect(url) if request.htmx else redirect(url)


def _publish_message(assessment, result) -> str:
    parts = [f"{assessment.name} published to {result.published + result.excused} students."]
    if result.excused:
        parts.append(f"{result.excused} excused.")
    if result.skipped_missing:
        parts.append(f"{result.skipped_missing} had no grade and were skipped (not counted as zero).")
    return " ".join(parts)


@login_required
@require_http_methods(["GET", "POST"])
@require_offering_access(edit=True)
def publish(request, *, offering, perms_for, assessment_id, **_):
    if not perms_for.can_publish:
        raise Http404
    assessment = get_object_or_404(Assessment, pk=assessment_id, offering=offering)

    if request.method == "POST":
        form = PublishForm(request.POST)
        if form.is_valid():
            try:
                result = services.publish_assessment(
                    request.user, assessment,
                    expected_changes=form.cleaned_data["expected_changes"],
                )
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
            else:
                messages.success(request, _publish_message(assessment, result))
        else:
            messages.error(request, "The publish form was incomplete. Please try again.")
        return _back_to_sheet(request, offering)

    preview = selectors.publish_preview(assessment)
    return render(request, "grading/publish_modal.html", {
        "offering": offering,
        "preview": preview,
        "form": PublishForm(initial={"expected_changes": preview.changes}),
    })


@login_required
@require_http_methods(["GET", "POST"])
@require_offering_access(edit=True)
def unpublish(request, *, offering, perms_for, assessment_id, **_):
    if not perms_for.can_publish:
        raise Http404
    assessment = get_object_or_404(Assessment, pk=assessment_id, offering=offering)
    form = UnpublishForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            hidden = services.unpublish_assessment(request.user, assessment,
                                                   reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.warning(request, f"{assessment.name} unpublished. "
                                      f"{hidden} grades are hidden from students again.")
            return _back_to_sheet(request, offering)

    return render(request, "grading/unpublish_modal.html", {
        "offering": offering, "assessment": assessment, "form": form,
    })