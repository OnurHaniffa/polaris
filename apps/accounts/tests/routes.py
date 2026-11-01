"""Every URL in POlaris and who may open it (spec §3.3, §4.8)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

OK, DENY, LOGIN = "OK", "DENY", "LOGIN"
ROLES = ("anon", "student", "instructor", "other_instructor", "head", "admin")


def _expect(**allowed: str) -> dict[str, str]:
    base = {
        "anon": LOGIN,
        "student": DENY,
        "instructor": DENY,
        "other_instructor": DENY,
        "head": DENY,
        "admin": DENY,
    }
    base.update(allowed)
    return base


PUBLIC = dict.fromkeys(ROLES, OK)
ANY_USER = _expect(student=OK, instructor=OK, other_instructor=OK, head=OK, admin=OK)
STUDENT = _expect(student=OK, admin=OK)
STUDENT_OWN = _expect(student=OK)
TEACHING = _expect(instructor=OK, other_instructor=OK, head=OK, admin=OK)
OFFERING_STAFF = _expect(instructor=OK, head=OK, admin=OK)
HEAD = _expect(head=OK, admin=OK)
EXPORT_OWNER = _expect(instructor=OK)


def _none(world) -> dict:
    return {}


@dataclass(frozen=True)
class Route:
    name: str
    expect: Mapping[str, str]
    kwargs: Callable[..., dict] = _none
    method: str = "GET"
    ok: frozenset[int] | None = None
    edit: bool = False
    story: str = ""
    htmx: bool = False

    @property
    def ok_codes(self) -> frozenset[int]:
        if self.ok is not None:
            return self.ok
        return frozenset({200}) if self.method == "GET" else frozenset({200, 302, 400})


def off(w):
    return {"offering_id": w.offering.pk}


def off_lo(w):
    return {"offering_id": w.offering.pk, "lo_id": w.lo.pk}


def off_a(w):
    return {"offering_id": w.offering.pk, "assessment_id": w.assessment.pk}


def off_cell(w):
    return {
        "offering_id": w.offering.pk,
        "assessment_id": w.assessment.pk,
        "enrollment_id": w.enrollment.pk,
    }


def grade_job(w):
    return {"offering_id": w.offering.pk, "job_id": w.grade_job().pk}


def syllabus_job(w):
    return {"job_id": w.syllabus_job().pk}


P = frozenset

# ROUTES tablosunun geri kalanını rehberdeki Step 5'ten
# aynı dosyanın devamına ekleyeceğiz.


ROUTES: list[Route] = [
    # Core / accounts
    Route("home", ANY_USER, ok=P({302}), story="S2-01"),
    Route("accounts:login", PUBLIC, ok=P({200, 302}), story="S2-01"),
    Route("accounts:logout", PUBLIC, method="POST", ok=P({302}), story="S2-01"),
    Route("accounts:switch_role", ANY_USER, method="POST", ok=P({302}), story="S2-01"),
    Route("accounts:password_reset", PUBLIC, story="S2-09"),
    Route("accounts:password_reset_done", PUBLIC, story="S2-09"),
    Route(
        "accounts:password_reset_confirm",
        PUBLIC,
        kwargs=lambda w: {"uidb64": "MQ", "token": "set-password"},
        ok=P({200}),
        story="S2-09",
    ),
    Route("accounts:password_reset_complete", PUBLIC, story="S2-09"),
    # Student pages
    Route("student:profile", STUDENT, story="S3-02"),
    Route("student:po_detail", STUDENT_OWN, kwargs=lambda w: {"po_id": w.po.pk}, story="S3-02"),
    Route("student:course", STUDENT_OWN, kwargs=off, story="S3-02"),
    Route("student:transcript", STUDENT_OWN, ok=P({200, 302}), story="S8-04"),
    # Teaching / offering
    Route("catalog:teaching", TEACHING, story="S2-01"),
    Route("catalog:offering", OFFERING_STAFF, kwargs=off, story="S2-01"),
    # Course setup
    Route("outcomes:setup", OFFERING_STAFF, kwargs=off, story="S2-04"),
    Route("outcomes:lo_create", OFFERING_STAFF, kwargs=off, edit=True, story="S2-04"),
    Route("outcomes:lo_edit", OFFERING_STAFF, kwargs=off_lo, edit=True, story="S2-04"),
    Route("outcomes:lo_delete", OFFERING_STAFF, kwargs=off_lo, edit=True, story="S2-04"),
    Route(
        "outcomes:lo_reorder", OFFERING_STAFF, kwargs=off, method="POST", edit=True, story="S2-04"
    ),
    Route("outcomes:assessment_create", OFFERING_STAFF, kwargs=off, edit=True, story="S2-04"),
    Route("outcomes:assessment_edit", OFFERING_STAFF, kwargs=off_a, edit=True, story="S2-04"),
    Route("outcomes:assessment_delete", OFFERING_STAFF, kwargs=off_a, edit=True, story="S2-04"),
    # Mapping
    Route("outcomes:mapping", OFFERING_STAFF, kwargs=off, story="S2-05"),
    Route(
        "outcomes:save_assessment_lo",
        OFFERING_STAFF,
        kwargs=off,
        method="POST",
        edit=True,
        story="S2-05",
    ),
    Route(
        "outcomes:save_lo_po", OFFERING_STAFF, kwargs=off, method="POST", edit=True, story="S2-05"
    ),
    Route(
        "outcomes:validate_cell",
        OFFERING_STAFF,
        kwargs=off,
        method="POST",
        edit=True,
        htmx=True,
        story="S2-05",
    ),
    Route(
        "outcomes:suggest_lo_po",
        OFFERING_STAFF,
        kwargs=off,
        method="POST",
        edit=True,
        story="S6-04",
    ),
    Route(
        "outcomes:accept_suggestions",
        OFFERING_STAFF,
        kwargs=off,
        method="POST",
        edit=True,
        story="S6-04",
    ),
    # Grades
    Route("grading:sheet", OFFERING_STAFF, kwargs=off, story="S2-06"),
    Route(
        "grading:cell",
        OFFERING_STAFF,
        kwargs=off_cell,
        method="POST",
        edit=True,
        htmx=True,
        story="S2-06",
    ),
    Route("grading:cell_history", OFFERING_STAFF, kwargs=off_cell, htmx=True, story="S7-05"),
    Route("grading:publish", OFFERING_STAFF, kwargs=off_a, edit=True, story="S3-01"),
    Route("grading:unpublish", OFFERING_STAFF, kwargs=off_a, edit=True, story="S3-01"),
    Route("grading:upload", OFFERING_STAFF, kwargs=off, edit=True, story="S4-03"),
    Route(
        "grading:upload_map",
        OFFERING_STAFF,
        kwargs=grade_job,
        edit=True,
        ok=P({200, 302}),
        story="S4-03",
    ),
    Route(
        "grading:upload_preview",
        OFFERING_STAFF,
        kwargs=grade_job,
        edit=True,
        ok=P({200, 302}),
        story="S4-03",
    ),
    Route(
        "grading:upload_confirm",
        OFFERING_STAFF,
        kwargs=grade_job,
        method="POST",
        edit=True,
        story="S4-03",
    ),
    # Syllabus wizard
    Route("ingestion:start", OFFERING_STAFF, kwargs=off, edit=True, story="S6-01"),
    Route("ingestion:job", OFFERING_STAFF, kwargs=syllabus_job, ok=P({200, 302}), story="S6-01"),
    Route("ingestion:status", OFFERING_STAFF, kwargs=syllabus_job, htmx=True, story="S6-01"),
    Route(
        "ingestion:review",
        OFFERING_STAFF,
        kwargs=syllabus_job,
        edit=True,
        ok=P({200, 302}),
        story="S6-02",
    ),
    Route(
        "ingestion:apply",
        OFFERING_STAFF,
        kwargs=syllabus_job,
        method="POST",
        edit=True,
        story="S6-03",
    ),
    Route(
        "ingestion:discard",
        OFFERING_STAFF,
        kwargs=syllabus_job,
        method="POST",
        edit=True,
        story="S6-03",
    ),
    # Reports
    Route("reports:results", OFFERING_STAFF, kwargs=off, story="S3-03"),
    Route("reports:history", OFFERING_STAFF, kwargs=off, story="S7-05"),
    Route(
        "reports:course_export",
        OFFERING_STAFF,
        kwargs=lambda w: {**off(w), "fmt": "pdf"},
        method="POST",
        story="S7-03",
    ),
    Route(
        "reports:export_status",
        EXPORT_OWNER,
        kwargs=lambda w: {"export_id": w.export_job().pk},
        story="S7-03",
    ),
    Route("reports:department", HEAD, story="S3-04"),
    Route(
        "reports:department_student",
        HEAD,
        kwargs=lambda w: {"user_id": w.users["student"].pk},
        story="S3-04",
    ),
    Route("reports:department_history", HEAD, story="S7-05"),
    Route(
        "reports:department_export",
        HEAD,
        kwargs=lambda w: {"fmt": "pdf"},
        method="POST",
        story="S7-03",
    ),
    Route("reports:department_student_po", HEAD,
        kwargs=lambda w: {"user_id": w.users["student"].pk,
        "po_id": w.po.pk},
        story="S3-02"),
    # Department outcomes
    Route("catalog:outcomes", HEAD, story="S2-03"),
    Route("catalog:po_set", HEAD, kwargs=lambda w: {"set_id": w.po_set.pk}, story="S2-03"),
    Route(
        "catalog:po_set_copy",
        HEAD,
        kwargs=lambda w: {"set_id": w.po_set.pk},
        method="POST",
        story="S2-03",
    ),
    Route(
        "catalog:po_set_activate",
        HEAD,
        kwargs=lambda w: {"set_id": w.po_set.pk},
        method="POST",
        story="S2-03",
    ),
    Route("catalog:po_edit", HEAD, kwargs=lambda w: {"po_id": w.po.pk}, story="S2-03"),
    Route("catalog:po_delete", HEAD, kwargs=lambda w: {"po_id": w.po.pk}, story="S2-03"),
    # Terms / courses / offerings / enrollments
    Route("catalog:terms", HEAD, story="S2-03"),
    Route("catalog:term_edit", HEAD, kwargs=lambda w: {"term_id": w.term.pk}, story="S2-03"),
    Route(
        "catalog:term_status",
        HEAD,
        kwargs=lambda w: {"term_id": w.term.pk},
        method="POST",
        story="S2-03",
    ),
    Route("catalog:courses", HEAD, story="S2-03"),
    Route("catalog:course_edit", HEAD, kwargs=lambda w: {"course_id": w.course.pk}, story="S2-03"),
    Route("catalog:offerings", HEAD, story="S2-03"),
    Route("catalog:offering_edit", HEAD, kwargs=off, story="S2-03"),
    Route("catalog:enrollments", HEAD, kwargs=off, story="S2-03"),
    Route("catalog:enrollment_import", HEAD, story="S3-05"),
    Route(
        "catalog:enrollment_import_preview",
        HEAD,
        kwargs=lambda w: {"job_id": w.enrollment_job().pk},
        ok=P({200, 302}),
        story="S3-05",
    ),
    Route(
        "catalog:enrollment_import_confirm",
        HEAD,
        kwargs=lambda w: {"job_id": w.enrollment_job().pk},
        method="POST",
        story="S3-05",
    ),
]

NOT_IN_MATRIX = {
    "healthz": "public; touches Redis, tested in apps/core/tests/test_healthz.py",
}
NOT_IN_MATRIX_PREFIXES = ("admin:", "djdt:")
