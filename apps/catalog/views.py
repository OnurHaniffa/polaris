from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import require_offering_access, require_role
from apps.accounts.permissions import head_program_or_404
from apps.accounts.services import get_or_create_student
from apps.catalog import services
from apps.catalog.forms import (
    CourseForm,
    EnrollmentAddForm,
    OfferingForm,
    POForm,
    POSetCopyForm,
    TermForm,
    TermReopenForm,
)
from apps.catalog.models import (
    Course,
    CourseOffering,
    Enrollment,
    ProgramOutcome,
    ProgramOutcomeSet,
    Term,
)
from apps.catalog.selectors import teaching_offerings, visible_enrollments
from apps.core.forms import add_service_errors
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
    return render(
        request,
        "catalog/terms.html",
        {
            "terms": Term.objects.all(),
            "form": form,
            "reopen_form": TermReopenForm(),
            "section": "terms",
        },
    )


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
    return render(
        request, "catalog/term_edit.html", {"term": term, "form": form, "section": "terms"}
    )


@login_required
@require_role("head")
@require_POST
def term_status(request, term_id):
    term = get_object_or_404(Term, pk=term_id)
    target = {
        "open": Term.Status.OPEN,
        "close": Term.Status.CLOSED,
        "reopen": Term.Status.OPEN,
    }.get(request.POST.get("action", ""))
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
    return render(
        request,
        "catalog/courses.html",
        {
            "courses": program.courses.order_by("code"),
            "form": form,
            "program": program,
            "section": "courses",
        },
    )


@login_required
@require_role("head")
def course_edit(request, course_id):
    program = _program(request)
    course = get_object_or_404(Course, pk=course_id, program=program)
    form = CourseForm(request.POST or None, instance=course, program=program)
    if request.method == "POST" and form.is_valid():
        try:
            services.save_course(
                request.user, Course.objects.get(pk=course.pk), **form.cleaned_data
            )
        except ValidationError as exc:
            add_service_errors(form, exc)
        else:
            messages.success(request, "Course saved.")
            return redirect("catalog:courses")
    return render(
        request, "catalog/course_edit.html", {"course": course, "form": form, "section": "courses"}
    )


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
    selected_term = (
        Term.objects.filter(pk=term_id).first() if term_id and term_id.isdigit() else None
    )
    qs = (
        CourseOffering.objects.filter(course__program=program)
        .select_related("course", "term")
        .prefetch_related("instructors")
        .order_by("-term__starts_on", "course__code", "section")
    )
    if selected_term:
        qs = qs.filter(term=selected_term)
    return render(
        request,
        "catalog/offerings.html",
        {
            "offerings": qs,
            "form": form,
            "terms": Term.objects.all(),
            "selected_term": selected_term,
            "section": "offerings",
        },
    )


@login_required
@require_role("head")
def offering_edit(request, offering_id):
    program = _program(request)
    offering = get_object_or_404(
        CourseOffering.objects.select_related("course", "term"),
        pk=offering_id,
        course__program=program,
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
    return render(
        request,
        "catalog/offering_edit.html",
        {
            "offering": offering,
            "form": form,
            "section": "offerings",
            "is_closed": offering.term.status == Term.Status.CLOSED,
        },
    )


@login_required
@require_role("head")
def enrollments(request, offering_id):
    """List students; add one (action=add) or drop one (action=drop)."""
    program = _program(request)
    offering = get_object_or_404(
        CourseOffering.objects.select_related("course", "term"),
        pk=offering_id,
        course__program=program,
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
        enrollment = get_object_or_404(
            Enrollment, pk=request.POST.get("enrollment_id"), offering=offering
        )
        try:
            services.drop(request.user, enrollment)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(
                request, f"{enrollment.student.get_full_name()} dropped. Their grades are kept."
            )
        return redirect("catalog:enrollments", offering_id=offering.pk)

    return render(
        request,
        "catalog/enrollments.html",
        {
            "offering": offering,
            "enrollments": visible_enrollments(request.user, offering, include_dropped=True),
            "form": form,
            "is_closed": offering.term.status == Term.Status.CLOSED,
            "section": "offerings",
        },
    )


# ---------- program outcomes ----------


@login_required
@require_role("head")
def po_sets(request):
    program = _program(request)
    sets = program.po_sets.annotate(n=Count("outcomes")).order_by(
        "-is_active", "-effective_from_year"
    )
    return render(
        request, "catalog/po_sets.html", {"program": program, "sets": sets, "section": "outcomes"}
    )


@login_required
@require_role("head")
def po_set_detail(request, set_id):
    program = _program(request)
    po_set = get_object_or_404(ProgramOutcomeSet, pk=set_id, program=program)
    return render(
        request,
        "catalog/po_set_detail.html",
        {
            "po_set": po_set,
            "outcomes": po_set.outcomes.annotate(links=Count("lo_weights")),
            "copy_form": POSetCopyForm(program=program),
            "section": "outcomes",
        },
    )


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
            messages.success(
                request, f"Copied to “{new_set.label}”. It stays inactive until you activate it."
            )
            return redirect("catalog:po_set", set_id=new_set.pk)
    return render(
        request,
        "catalog/po_set_detail.html",
        {
            "po_set": po_set,
            "outcomes": po_set.outcomes.annotate(links=Count("lo_weights")),
            "copy_form": form,
            "section": "outcomes",
        },
        status=400,
    )


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
    po = get_object_or_404(
        ProgramOutcome.objects.select_related("po_set"), pk=po_id, po_set__program=program
    )
    form = POForm(request.POST or None, instance=po)
    if request.method == "POST" and form.is_valid():
        try:
            services.update_po(
                request.user, ProgramOutcome.objects.get(pk=po.pk), **form.cleaned_data
            )
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
    po = get_object_or_404(
        ProgramOutcome.objects.select_related("po_set"), pk=po_id, po_set__program=program
    )
    if request.method == "POST":
        try:
            services.delete_po(request.user, po)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"PO {po.number} deleted.")
        return redirect("catalog:po_set", set_id=po.po_set_id)
    template = "catalog/po_delete.html#confirm" if request.htmx else "catalog/po_delete.html"
    return render(
        request,
        template,
        {"po": po, "used_by": services.courses_using_po(po), "section": "outcomes"},
    )
