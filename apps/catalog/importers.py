"""Enrollment CSV import (B3): parse → preview (no writes) → confirm (one transaction)."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass, field

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import get_or_create_student, send_set_password_email
from apps.core.audit import record
from apps.ingestion.models import IngestionJob

from .models import Enrollment
from .services import ensure_term_open

MAX_BYTES = 1_000_000
COLUMNS = ("student_number", "email", "first_name", "last_name", "cohort_year")
HEADER_ALIASES = {
    "student_no": "student_number",
    "student_number": "student_number",
    "number": "student_number",
    "öğrenci_no": "student_number",
    "ogrenci_no": "student_number",
    "no": "student_number",
    "email": "email",
    "e-mail": "email",
    "e_mail": "email",
    "e-posta": "email",
    "first_name": "first_name",
    "firstname": "first_name",
    "name": "first_name",
    "ad": "first_name",
    "adı": "first_name",
    "last_name": "last_name",
    "lastname": "last_name",
    "surname": "last_name",
    "soyad": "last_name",
    "soyadı": "last_name",
    "cohort_year": "cohort_year",
    "cohort": "cohort_year",
    "giriş_yılı": "cohort_year",
}
STUDENT_NUMBER = re.compile(r"^[0-9A-Za-z-]{3,20}$")


@dataclass
class ImportRow:
    line: int  # line number in the file, header = 1
    student_number: str
    email: str
    first_name: str
    last_name: str
    cohort_year: int | None
    status: str = "new"  # new | existing | enrolled | error
    errors: list[str] = field(default_factory=list)
    user_id: int | None = None

    def fail(self, message: str) -> None:
        self.status = "error"
        self.errors.append(message)


@dataclass
class EnrollmentImportPreview:
    rows: list[ImportRow] = field(default_factory=list)
    file_errors: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out = {"new": 0, "existing": 0, "enrolled": 0, "error": 0}
        for r in self.rows:
            out[r.status] += 1
        return out

    @property
    def has_errors(self) -> bool:
        return bool(self.file_errors) or any(r.status == "error" for r in self.rows)

    @property
    def actionable(self) -> int:
        c = self.counts
        return c["new"] + c["existing"]

    def to_json(self) -> dict:
        return {"rows": [asdict(r) for r in self.rows], "file_errors": list(self.file_errors)}

    @classmethod
    def from_json(cls, data: dict) -> EnrollmentImportPreview:
        return cls(
            rows=[ImportRow(**r) for r in data.get("rows", [])],
            file_errors=list(data.get("file_errors", [])),
        )

    def signature(self) -> list[tuple]:
        """What must not change between preview and confirm."""
        return [(r.line, r.student_number, r.status, r.user_id) for r in self.rows]


@dataclass(frozen=True)
class ImportResult:
    created_accounts: int
    enrolled: int
    reactivated: int
    skipped: int


class PreviewOutdated(Exception):
    """Raised by confirm when the data changed since the head saw the preview."""

    def __init__(self, fresh: EnrollmentImportPreview):
        super().__init__("The class list or the accounts changed since the preview.")
        self.fresh = fresh


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1254"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError("We couldn't read this file's text encoding. Save it as CSV UTF-8 and try again.")


def _normalise_header(cell: str) -> str:
    key = cell.strip().lower().replace(" ", "_")
    return HEADER_ALIASES.get(key, key)


def _read_rows(text: str) -> tuple[list[str], list[list[str]]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    if not rows:
        return [], []
    return [_normalise_header(c) for c in rows[0]], rows[1:]


def _row_errors(row: ImportRow) -> None:
    if not row.student_number:
        row.fail("Student number is missing.")
    elif not STUDENT_NUMBER.match(row.student_number):
        row.fail(f"“{row.student_number}” doesn't look like a student number.")
    if not row.email:
        row.fail("Email is missing.")
    else:
        try:
            validate_email(row.email)
        except ValidationError:
            row.fail(f"“{row.email}” isn't a valid email address.")
    if not row.first_name or not row.last_name:
        row.fail("First and last name are both required.")
    if row.cohort_year is None:
        row.fail("Cohort year is missing or not a year (e.g. 2024).")


def _cohort(value: str) -> int | None:
    value = value.strip()
    if not value.isdigit():
        return None
    year = int(value)
    return year if 1990 <= year <= 2100 else None


def parse_enrollment_csv(file, *, offering) -> EnrollmentImportPreview:
    """Read a class list and classify every row against the database. Never writes."""
    preview = EnrollmentImportPreview()
    raw = file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        preview.file_errors.append("The file is larger than 1 MB. A class list should be far smaller.")
        return preview
    try:
        header, body = _read_rows(_decode(raw))
    except ValidationError as exc:
        preview.file_errors.extend(exc.messages)
        return preview

    missing = [c for c in COLUMNS if c not in header]
    if missing:
        preview.file_errors.append(
            "Missing column(s): " + ", ".join(missing) + ". The first row must be: " + ",".join(COLUMNS) + "."
        )
        return preview
    index = {name: header.index(name) for name in COLUMNS}

    def cell(values: list[str], name: str) -> str:
        i = index[name]
        return values[i].strip() if i < len(values) else ""

    seen_numbers: dict[str, int] = {}
    seen_emails: dict[str, int] = {}
    for offset, values in enumerate(body, start=2):
        if not any(v.strip() for v in values):
            continue  # blank line
        row = ImportRow(
            line=offset,
            student_number=cell(values, "student_number"),
            email=cell(values, "email").lower(),
            first_name=cell(values, "first_name"),
            last_name=cell(values, "last_name"),
            cohort_year=_cohort(cell(values, "cohort_year")),
        )
        _row_errors(row)
        if row.student_number:
            if row.student_number in seen_numbers:
                row.fail(
                    f"Student number {row.student_number} appears twice in the file "
                    f"(also on line {seen_numbers[row.student_number]})."
                )
            else:
                seen_numbers[row.student_number] = row.line
        if row.email:
            if row.email in seen_emails:
                row.fail(f"Email {row.email} appears twice in the file (also on line {seen_emails[row.email]}).")
            else:
                seen_emails[row.email] = row.line
        preview.rows.append(row)

    _match_against_database(preview, offering)
    return preview


def _match_against_database(preview: EnrollmentImportPreview, offering) -> None:
    candidates = [r for r in preview.rows if r.status != "error"]
    by_number = {u.student_number: u for u in User.objects.filter(student_number__in=[r.student_number for r in candidates])}
    by_email = {
        u.email_lower: u
        for u in User.objects.annotate(email_lower=Lower("email")).filter(email_lower__in=[r.email for r in candidates])
    }
    enrolled_ids = set(
        Enrollment.objects.filter(offering=offering, status=Enrollment.Status.ENROLLED).values_list("student_id", flat=True)
    )

    for row in candidates:
        user = by_number.get(row.student_number)
        if user is not None:
            if user.email.lower() != row.email:
                row.fail(
                    f"Student number {row.student_number} belongs to {user.email} in POlaris, "
                    f"but the file says {row.email}. Fix the file or the account first."
                )
                continue
            row.user_id = user.pk
            row.status = "enrolled" if user.pk in enrolled_ids else "existing"
            continue
        other = by_email.get(row.email)
        if other is not None:
            suffix = f" (student {other.student_number})" if other.student_number else ""
            row.fail(f"{row.email} already belongs to another account{suffix}.")
            continue
        row.status = "new"


def create_enrollment_import_job(user, offering, uploaded_file) -> IngestionJob:
    preview = parse_enrollment_csv(uploaded_file, offering=offering)
    uploaded_file.seek(0)
    return IngestionJob.objects.create(
        offering=offering,
        kind=IngestionJob.Kind.ENROLLMENTS,
        file=uploaded_file,
        original_filename=uploaded_file.name[:255],
        status=IngestionJob.Status.READY,
        result=preview.to_json(),
        created_by=user,
    )


def stored_preview(job: IngestionJob) -> EnrollmentImportPreview:
    return EnrollmentImportPreview.from_json(job.result or {})


def confirm_enrollment_import(user, job: IngestionJob, *, skip_invalid=False, request=None) -> ImportResult:
    with transaction.atomic():
        job = (
            IngestionJob.objects.select_for_update().select_related("offering__course__program", "offering__term").get(pk=job.pk)
        )
        if job.status != IngestionJob.Status.READY:
            raise ValidationError("This import was already applied or discarded.")
        offering = job.offering
        ensure_term_open(offering)

        with job.file.open("rb") as f:
            fresh = parse_enrollment_csv(f, offering=offering)
        outdated = fresh.signature() != stored_preview(job).signature()
        if outdated:
            job.result = fresh.to_json()
            job.save(update_fields=["result", "updated_at"])
        else:
            result = apply_enrollment_import(user, offering, fresh, skip_invalid=skip_invalid, request=request)
            job.status = IngestionJob.Status.APPLIED
            job.applied_at = timezone.now()
            job.save(update_fields=["status", "applied_at", "updated_at"])

    if outdated:
        raise PreviewOutdated(fresh)  # outside the transaction, or the save above rolls back
    return result


def apply_enrollment_import(
    user, offering, preview: EnrollmentImportPreview, *, skip_invalid=False, request=None
) -> ImportResult:
    """Write a preview. Call inside a transaction (confirm does)."""
    if preview.file_errors:
        raise ValidationError(preview.file_errors)
    if preview.has_errors and not skip_invalid:
        raise ValidationError("Some rows have errors. Fix the file, or tick “skip rows with errors”.")

    program = offering.course.program
    created = enrolled = reactivated = skipped = 0
    for row in preview.rows:
        if row.status in ("error", "enrolled"):
            skipped += 1
            continue
        student, is_new = get_or_create_student(
            student_number=row.student_number,
            email=row.email,
            first_name=row.first_name,
            last_name=row.last_name,
            program=program,
            cohort_year=row.cohort_year,
            actor=user,
        )
        enrollment, enr_created = Enrollment.objects.get_or_create(offering=offering, student=student)
        if enr_created:
            enrolled += 1
            record(
                user,
                "enrollment.create",
                enrollment,
                offering=offering,
                after={"student": student.student_number, "status": enrollment.status},
            )
        elif enrollment.status == Enrollment.Status.DROPPED:
            enrollment.status = Enrollment.Status.ENROLLED
            enrollment.save(update_fields=["status"])
            reactivated += 1
            record(
                user,
                "enrollment.reactivate",
                enrollment,
                offering=offering,
                before={"status": "dropped"},
                after={"status": "enrolled"},
            )
        if is_new:
            created += 1
            transaction.on_commit(lambda s=student: send_set_password_email(s, request))
    return ImportResult(
        created_accounts=created,
        enrolled=enrolled,
        reactivated=reactivated,
        skipped=skipped,
    )
