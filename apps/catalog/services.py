"""Every write for terms, catalog courses, offerings, enrollments and program outcomes.
Rules from spec B2, B3 and §5.3. Each function audits inside its own transaction."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import ProgramMembership
from apps.catalog.models import (
    Course,
    CourseOffering,
    Enrollment,
    Program,
    ProgramOutcome,
    ProgramOutcomeSet,
    Term,
)
from apps.core import audit

TERM_FIELDS = ["code", "name", "starts_on", "ends_on", "status"]
COURSE_FIELDS = ["program", "code", "title", "credits", "ects"]
PO_FIELDS = ["number", "short_name", "description"]

# (from, to) -> action name used in the audit trail
TERM_TRANSITIONS = {
    (Term.Status.PLANNED, Term.Status.OPEN): "term.open",
    (Term.Status.OPEN, Term.Status.CLOSED): "term.close",
    (Term.Status.CLOSED, Term.Status.OPEN): "term.reopen",
}


# ---------- guard used by every offering-level service in the codebase ----------


def ensure_term_open(offering: CourseOffering) -> None:
    """Refuse any change inside a closed term (spec §3.3, §5.3)."""
    if offering.term.status == Term.Status.CLOSED:
        raise ValidationError(
            f"{offering.term.name} is closed, so {offering.course.code} can't be changed. "
            "Ask the department head to reopen the term."
        )


# ---------- terms ----------


@transaction.atomic
def create_term(user, **fields) -> Term:
    term = Term(**fields)
    term.full_clean()
    term.save()
    audit.record(user, "term.create", term, after=audit.snapshot(term, TERM_FIELDS))
    return term


@transaction.atomic
def update_term(user, term: Term, **fields) -> Term:
    """Change code, name or dates. Status changes go through set_term_status."""
    if "status" in fields:
        raise ValueError("use set_term_status() to change a term's status")
    before = audit.snapshot(term, TERM_FIELDS)
    for name, value in fields.items():
        setattr(term, name, value)
    term.full_clean()
    term.save()
    audit.record(user, "term.update", term, before=before, after=audit.snapshot(term, TERM_FIELDS))
    return term


@transaction.atomic
def set_term_status(user, term: Term, status: str, *, reason: str = "") -> Term:
    term = Term.objects.select_for_update().get(pk=term.pk)
    action = TERM_TRANSITIONS.get((term.status, status))
    if action is None:
        raise ValidationError(
            f"A term can't go from {term.get_status_display().lower()} "
            f"to {Term.Status(status).label.lower()}."
        )
    reason = reason.strip()
    if action == "term.reopen" and len(reason) < 10:
        raise ValidationError(
            {"reason": "Say why the term is being reopened (at least 10 characters)."}
        )
    before = {"status": term.status}
    term.status = status
    term.save(update_fields=["status"])
    after = {"status": status}
    if reason:
        after["reason"] = reason
    audit.record(user, action, term, before=before, after=after)
    return term


# ---------- catalog courses ----------


@transaction.atomic
def save_course(user, course: Course | None = None, **fields) -> Course:
    """Create a course (pass program= in fields) or update one. Codes are unique per program."""
    creating = course is None
    before = None if creating else audit.snapshot(course, COURSE_FIELDS)
    course = course or Course()
    for name, value in fields.items():
        setattr(course, name, value)
    course.code = " ".join(course.code.upper().split())  # "cse  311" -> "CSE 311"
    if (
        Course.objects.filter(program=course.program, code=course.code)
        .exclude(pk=course.pk)
        .exists()
    ):
        raise ValidationError({"code": f"{course.code} already exists in {course.program.code}."})
    course.full_clean()
    course.save()
    audit.record(
        user,
        "course.create" if creating else "course.update",
        course,
        before=before,
        after=audit.snapshot(course, COURSE_FIELDS),
    )
    return course


# ---------- offerings ----------


def _check_instructors(program: Program, instructors) -> list:
    instructors = list(instructors)
    allowed = set(
        ProgramMembership.objects.filter(
            program=program,
            role=ProgramMembership.Role.INSTRUCTOR,
            user__in=[u.pk for u in instructors],
        ).values_list("user_id", flat=True)
    )
    wrong = [u for u in instructors if u.pk not in allowed]
    if wrong:
        names = ", ".join(u.get_full_name() or u.email for u in wrong)
        raise ValidationError({"instructors": f"Not an instructor in {program.code}: {names}."})
    return instructors


def _offering_snapshot(offering: CourseOffering) -> dict:
    return {
        "course": offering.course.code,
        "term": offering.term.code,
        "section": offering.section,
        "instructors": sorted(offering.instructors.values_list("email", flat=True)),
    }


@transaction.atomic
def create_offering(
    user, *, course: Course, term: Term, section: str = "1", instructors=()
) -> CourseOffering:
    if term.status == Term.Status.CLOSED:
        raise ValidationError(
            {"term": f"{term.name} is closed. Reopen it before adding offerings."}
        )
    section = (section or "1").strip()
    if CourseOffering.objects.filter(course=course, term=term, section=section).exists():
        raise ValidationError(
            {"section": f"{course.code} section {section} already exists in {term.name}."}
        )
    instructors = _check_instructors(course.program, instructors)
    offering = CourseOffering(course=course, term=term, section=section)
    offering.full_clean()
    try:
        offering.save()
    except IntegrityError as exc:  # two heads, same click, same second
        raise ValidationError(
            "This offering was just created by someone else. Reload the page."
        ) from exc
    offering.instructors.set(instructors)
    audit.record(
        user, "offering.create", offering, offering=offering, after=_offering_snapshot(offering)
    )
    return offering


@transaction.atomic
def update_offering(
    user, offering: CourseOffering, *, section: str | None = None, instructors=None
) -> CourseOffering:
    """Change the section label and/or the instructor list. Course and term never change:
    create a new offering instead, so grades never move between courses."""
    ensure_term_open(offering)
    before = _offering_snapshot(offering)
    if section is not None:
        section = section.strip()
        clash = CourseOffering.objects.filter(
            course=offering.course, term=offering.term, section=section
        )
        if clash.exclude(pk=offering.pk).exists():
            raise ValidationError(
                {"section": f"Section {section} already exists for this course and term."}
            )
        offering.section = section
        offering.full_clean()
        offering.save(update_fields=["section"])
    if instructors is not None:
        offering.instructors.set(_check_instructors(offering.course.program, instructors))
    audit.record(
        user,
        "offering.update",
        offering,
        offering=offering,
        before=before,
        after=_offering_snapshot(offering),
    )
    return offering


# ---------- enrollments ----------


@transaction.atomic
def enroll(user, offering: CourseOffering, student) -> Enrollment:
    """Enroll a student (or re-enroll a dropped one).
    B3 AC 4: duplicates are refused with a message."""
    ensure_term_open(offering)
    program = offering.course.program
    if not student.memberships.filter(
        program=program, role=ProgramMembership.Role.STUDENT
    ).exists():
        raise ValidationError(f"{student.get_full_name()} is not a {program.code} student.")
    existing = (
        Enrollment.objects.select_for_update().filter(offering=offering, student=student).first()
    )
    if existing and existing.status == Enrollment.Status.ENROLLED:
        raise ValidationError(
            f"{student.get_full_name()} ({student.student_number}) is already enrolled."
        )
    if existing:
        existing.status = Enrollment.Status.ENROLLED
        existing.save(update_fields=["status"])
        audit.record(
            user,
            "enrollment.reenroll",
            existing,
            offering=offering,
            before={"status": "dropped"},
            after={"status": "enrolled"},
        )
        return existing
    try:
        enrollment = Enrollment.objects.create(offering=offering, student=student)
    except IntegrityError as exc:
        raise ValidationError(f"{student.student_number} is already enrolled.") from exc
    audit.record(
        user,
        "enrollment.create",
        enrollment,
        offering=offering,
        after={"student_number": student.student_number, "status": "enrolled"},
    )
    return enrollment


@transaction.atomic
def drop(user, enrollment: Enrollment) -> Enrollment:
    """Mark as dropped. The row and its grades stay (history),
    but loaders ignore dropped students."""
    ensure_term_open(enrollment.offering)
    if enrollment.status == Enrollment.Status.DROPPED:
        return enrollment
    enrollment.status = Enrollment.Status.DROPPED
    enrollment.save(update_fields=["status"])
    audit.record(
        user,
        "enrollment.drop",
        enrollment,
        offering=enrollment.offering,
        before={"status": "enrolled"},
        after={"status": "dropped"},
    )
    return enrollment


# ---------- program outcome sets ----------


@transaction.atomic
def copy_po_set(
    user, po_set: ProgramOutcomeSet, *, label: str, effective_from_year: int
) -> ProgramOutcomeSet:
    """B2 AC 2: a new version starts as an exact copy of the old one, inactive."""
    label = label.strip()
    if ProgramOutcomeSet.objects.filter(program=po_set.program, label=label).exists():
        raise ValidationError({"label": f"A PO set called “{label}” already exists."})
    new_set = ProgramOutcomeSet.objects.create(
        program=po_set.program,
        label=label,
        effective_from_year=effective_from_year,
        is_active=False,
    )
    ProgramOutcome.objects.bulk_create(
        ProgramOutcome(
            po_set=new_set, number=po.number, short_name=po.short_name, description=po.description
        )
        for po in po_set.outcomes.all()
    )
    audit.record(
        user,
        "po_set.copy",
        new_set,
        after={"copied_from": po_set.label, "label": label, "outcomes": new_set.outcomes.count()},
    )
    return new_set


@transaction.atomic
def activate_po_set(user, po_set: ProgramOutcomeSet) -> ProgramOutcomeSet:
    """Make this set the active one. The old one is deactivated first, inside the same
    transaction, because the partial unique index allows only one active set per program."""
    sets = list(ProgramOutcomeSet.objects.select_for_update().filter(program=po_set.program))
    previous = next((s for s in sets if s.is_active), None)
    if previous and previous.pk == po_set.pk:
        return po_set
    if not po_set.outcomes.exists():
        raise ValidationError("An empty PO set can't be activated.")
    ProgramOutcomeSet.objects.filter(program=po_set.program, is_active=True).update(is_active=False)
    ProgramOutcomeSet.objects.filter(pk=po_set.pk).update(is_active=True)
    po_set.is_active = True
    audit.record(
        user,
        "po_set.activate",
        po_set,
        before={"active": previous.label if previous else None},
        after={"active": po_set.label},
    )
    return po_set


@transaction.atomic
def update_po(user, po: ProgramOutcome, **fields) -> ProgramOutcome:
    """Edit short name or description. Numbers don't change: every mapping refers to them."""
    allowed = {"short_name", "description"}
    if set(fields) - allowed:
        raise ValueError(f"only {sorted(allowed)} can be edited")
    before = audit.snapshot(po, PO_FIELDS)
    for name, value in fields.items():
        setattr(po, name, value.strip())
    po.full_clean()
    po.save()
    audit.record(user, "po.update", po, before=before, after=audit.snapshot(po, PO_FIELDS))
    return po


def courses_using_po(po: ProgramOutcome) -> list[str]:
    """Human labels of the offerings whose LOs link to this PO, e.g. 'CSE 311 (Fall 2026)'."""
    rows = po.lo_weights.select_related(
        "learning_outcome__offering__course", "learning_outcome__offering__term"
    ).order_by("learning_outcome__offering__course__code")
    labels = []
    for w in rows:
        o = w.learning_outcome.offering
        label = f"{o.course.code} ({o.term.name})"
        if label not in labels:
            labels.append(label)
    return labels


@transaction.atomic
def delete_po(user, po: ProgramOutcome) -> None:
    """B2 AC 3: a PO with LO→PO weights can't be deleted; the message names the courses."""
    used_by = courses_using_po(po)
    if used_by:
        raise ValidationError(
            f"PO {po.number} is used by {', '.join(used_by)}. "
            "Edit its wording instead of deleting it."
        )
    audit.record(user, "po.delete", po, before=audit.snapshot(po, PO_FIELDS))
    po.delete()
