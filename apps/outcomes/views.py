"""Course setup (B4) and the weight grids (B5).
Views parse, call one service or selector, and render."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.decorators import require_offering_access
from apps.accounts.permissions import is_head
from apps.catalog.selectors import setup_status
from apps.core.navigation import offering_tabs

from . import services
from .forms import AssessmentForm, LearningOutcomeForm
from .matrix import (
    A_LO,
    LO_PO,
    VALIDATORS,
    GridCell,
    WeightGrid,
    overlay_submitted,
    parse_cell_name,
    parse_matrix_post,
)
from .models import Assessment, LearningOutcome
from .selectors import assessment_deletion_impact, lo_deletion_impact, mapping_grid, setup_context


def _setup_url(offering, anchor: str) -> str:
    return reverse("outcomes:setup", kwargs={"offering_id": offering.pk}) + f"#{anchor}"


def _page(request, template, offering, perms_for, current_tab, **extra):
    return render(
        request,
        template,
        {
            "offering": offering,
            "perms_for": perms_for,
            "tabs": offering_tabs(offering, current_tab),
            **extra,
        },
    )


@login_required
@require_offering_access()
def setup(request, offering, perms_for):
    can_manage_enrollment = request.user.is_superuser or is_head(
        request.user, offering.course.program
    )
    return _page(
        request,
        "outcomes/setup.html",
        offering,
        perms_for,
        "outcomes:setup",
        status=setup_status(offering),
        can_manage_enrollment=can_manage_enrollment,
        **setup_context(offering),
    )


# ---------- learning outcomes ----------


@login_required
@require_offering_access(edit=True)
def lo_create(request, offering, perms_for):
    form = LearningOutcomeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            lo = services.create_lo(
                request.user, offering, description=form.cleaned_data["description"]
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"Added LO {lo.number}.")
            return redirect(_setup_url(offering, "los"))
    return _page(
        request, "outcomes/lo_form.html", offering, perms_for, "outcomes:setup", form=form, lo=None
    )


@login_required
@require_offering_access(edit=True)
def lo_edit(request, lo_id, offering, perms_for):
    lo = get_object_or_404(LearningOutcome, pk=lo_id, offering=offering)
    form = LearningOutcomeForm(request.POST or None, initial={"description": lo.description})
    if request.method == "POST" and form.is_valid():
        try:
            services.update_lo(request.user, lo, description=form.cleaned_data["description"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"Saved LO {lo.number}.")
            return redirect(_setup_url(offering, "los"))
    return _page(
        request, "outcomes/lo_form.html", offering, perms_for, "outcomes:setup", form=form, lo=lo
    )


def _confirm_delete(request, offering, perms_for, impact, action_url):
    """GET of a delete URL: modal body for HTMX, full page otherwise (no-JS fallback)."""
    context = {"impact": impact, "action_url": action_url, "as_modal": bool(request.htmx)}
    if request.htmx:
        return render(request, "outcomes/confirm_delete.html#body", context)
    return _page(
        request, "outcomes/confirm_delete.html", offering, perms_for, "outcomes:setup", **context
    )


@login_required
@require_offering_access(edit=True)
def lo_delete(request, lo_id, offering, perms_for):
    lo = get_object_or_404(LearningOutcome, pk=lo_id, offering=offering)
    if request.method == "POST":
        number = lo.number
        try:
            services.delete_lo(request.user, lo)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(
                request, f"Deleted LO {number}. The outcomes after it were renumbered."
            )
        return redirect(_setup_url(offering, "los"))
    action = reverse("outcomes:lo_delete", kwargs={"offering_id": offering.pk, "lo_id": lo.pk})
    return _confirm_delete(request, offering, perms_for, lo_deletion_impact(lo), action)


@login_required
@require_offering_access(edit=True)
@require_POST
def lo_reorder(request, offering, perms_for):
    try:
        ordered = [int(part) for part in request.POST.get("order", "").split(",") if part.strip()]
        services.reorder_los(request.user, offering, ordered)
    except (ValueError, ValidationError):
        messages.error(
            request,
            "The list of outcomes changed while you were editing. This is the current order.",
        )
    return redirect(_setup_url(offering, "los"))


# ---------- assessments ----------


@login_required
@require_offering_access(edit=True)
def assessment_create(request, offering, perms_for):
    form = AssessmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            assessment = services.create_assessment(request.user, offering, **form.model_data())
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"Added {assessment.name}.")
            return redirect(_setup_url(offering, "assessments"))
    return _page(
        request,
        "outcomes/assessment_form.html",
        offering,
        perms_for,
        "outcomes:setup",
        form=form,
        assessment=None,
        needs_confirm=False,
    )


@login_required
@require_offering_access(edit=True)
def assessment_edit(request, assessment_id, offering, perms_for):
    assessment = get_object_or_404(Assessment, pk=assessment_id, offering=offering)
    form = AssessmentForm(request.POST or None, initial=AssessmentForm.initial_for(assessment))
    needs_confirm = False
    if request.method == "POST" and form.is_valid():
        try:
            services.update_assessment(
                request.user,
                assessment,
                confirm_max_change=form.cleaned_data["confirm_max_change"],
                **form.model_data(),
            )
        except ValidationError as exc:
            needs_confirm = getattr(exc, "code", None) == "confirm_max_change"
            form.add_error(None, exc)
        else:
            messages.success(request, f"Saved {form.cleaned_data['name']}.")
            return redirect(_setup_url(offering, "assessments"))
    return _page(
        request,
        "outcomes/assessment_form.html",
        offering,
        perms_for,
        "outcomes:setup",
        form=form,
        assessment=assessment,
        needs_confirm=needs_confirm,
    )


@login_required
@require_offering_access(edit=True)
def assessment_delete(request, assessment_id, offering, perms_for):
    assessment = get_object_or_404(Assessment, pk=assessment_id, offering=offering)
    if request.method == "POST":
        name = assessment.name
        try:
            services.delete_assessment(request.user, assessment)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"Deleted {name}.")
        return redirect(_setup_url(offering, "assessments"))
    action = reverse(
        "outcomes:assessment_delete",
        kwargs={"offering_id": offering.pk, "assessment_id": assessment.pk},
    )
    return _confirm_delete(
        request, offering, perms_for, assessment_deletion_impact(assessment), action
    )


GRID_LABEL = {A_LO: "assessment → LO", LO_PO: "LO → PO"}
GRID_ANCHOR = {A_LO: "a-lo", LO_PO: "lo-po"}


def _cell_errors(exc: ValidationError) -> dict[str, str]:
    if hasattr(exc, "error_dict"):
        return {name: messages_[0] for name, messages_ in exc.message_dict.items()}
    return {"__all__": " ".join(exc.messages)}


def _mapping_page(request, offering, perms_for, *, failed=None, status=200):
    """The Mapping tab. `failed` = (kind, cells, posted_version, exc) after a refused save."""
    validate_url = reverse("outcomes:validate_cell", kwargs={"offering_id": offering.pk})
    mapping = mapping_grid(offering, validate_url=validate_url)
    stale_kind = None
    if failed is not None:
        kind, cells, posted_version, exc = failed
        grid = mapping.grid(kind)
        if getattr(exc, "code", None) == "stale":
            stale_kind = kind
            overlay_submitted(grid, cells)
            grid.version = (
                posted_version  # keep the old version: re-submitting stays refused until reload
            )
        else:
            overlay_submitted(grid, cells, _cell_errors(exc))
    return render(
        request,
        "outcomes/mapping.html",
        {
            "offering": offering,
            "perms_for": perms_for,
            "tabs": offering_tabs(offering, "outcomes:mapping"),
            "mapping": mapping,
            "stale_label": GRID_LABEL.get(stale_kind, ""),
        },
        status=status,
    )


@login_required
@require_offering_access()
def mapping(request, offering, perms_for):
    return _mapping_page(request, offering, perms_for)


def _save_grid(request, offering, perms_for, kind):
    if "version" not in request.POST:
        return HttpResponseBadRequest("This form is missing its version. Reload the page.")
    cells = parse_matrix_post(request.POST, kind)
    posted_version = request.POST["version"]
    save = services.save_assessment_lo_matrix if kind == A_LO else services.save_lo_po_matrix
    try:
        result = save(request.user, offering, cells, expected_version=posted_version)
    except ValidationError as exc:
        code = 409 if getattr(exc, "code", None) == "stale" else 422
        return _mapping_page(
            request, offering, perms_for, failed=(kind, cells, posted_version, exc), status=code
        )
    if result.changed:
        messages.success(request, f"Saved the {GRID_LABEL[kind]} weights.")
    else:
        messages.info(request, "Nothing changed.")
    return redirect(
        reverse("outcomes:mapping", kwargs={"offering_id": offering.pk}) + f"#{GRID_ANCHOR[kind]}"
    )


@login_required
@require_offering_access(edit=True)
@require_POST
def save_assessment_lo(request, offering, perms_for):
    return _save_grid(request, offering, perms_for, A_LO)


@login_required
@require_offering_access(edit=True)
@require_POST
def save_lo_po(request, offering, perms_for):
    return _save_grid(request, offering, perms_for, LO_PO)


@login_required
@require_offering_access(edit=True)
@require_POST
def validate_cell(request, offering, perms_for):
    """HTMX: check one cell as the user leaves it. Never writes, never reads the database."""
    name = request.POST.get("name", "")
    parsed = parse_cell_name(name)
    if parsed is None or parsed[0] != request.POST.get("kind"):
        return HttpResponseBadRequest("Unknown cell")
    kind = parsed[0]
    raw = request.POST.get(name, "").strip()
    try:
        VALIDATORS[kind](raw)
        error = ""
    except ValidationError as exc:
        error = exc.messages[0]
    cell = GridCell(name=name, value=raw, label=request.POST.get("label", "")[:200], error=error)
    grid = WeightGrid(kind=kind, caption="", cols=[], rows=[], validate_url=request.path)
    return render(
        request, "includes/weight_grid.html#cell", {"cell": cell, "grid": grid, "editable": True}
    )
