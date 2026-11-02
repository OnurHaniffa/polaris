from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import ProgramMembership, User
from apps.catalog.importers import (
    PreviewOutdated,
    confirm_enrollment_import,
    create_enrollment_import_job,
    parse_enrollment_csv,
)
from apps.catalog.models import Enrollment, Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import (
    EnrollmentFactory,
    MembershipFactory,
    OfferingFactory,
    TermFactory,
    UserFactory,
)
from apps.ingestion.models import IngestionJob

pytestmark = pytest.mark.django_db

HEADER = "student_number,email,first_name,last_name,cohort_year\n"


def upload(text, name="class.csv", encoding="utf-8"):
    return SimpleUploadedFile(name, text.encode(encoding), content_type="text/csv")


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def offering():
    term = TermFactory(
        code="2026F",
        name="Fall 2026",
        starts_on=date(2026, 9, 14),
        ends_on=date(2027, 1, 22),
        status=Term.Status.OPEN,
    )
    return OfferingFactory(term=term)


@pytest.fixture
def head(offering):
    user = UserFactory()
    MembershipFactory(user=user, program=offering.course.program, role="head")
    return user


def test_classifies_new_existing_and_enrolled(offering):
    known = UserFactory(student_number="2024-0002", email="known@example.edu")
    already = UserFactory(student_number="2024-0003", email="already@example.edu")
    EnrollmentFactory(offering=offering, student=already)
    preview = parse_enrollment_csv(
        upload(
            HEADER
            + "2024-0001,new@example.edu,Ada,Lovelace,2024\n"
            + "2024-0002,KNOWN@example.edu,Known,Student,2024\n"
            + "2024-0003,already@example.edu,Already,There,2024\n"
        ),
        offering=offering,
    )

    assert [r.status for r in preview.rows] == ["new", "existing", "enrolled"]
    assert preview.rows[1].user_id == known.pk
    assert preview.counts == {"new": 1, "existing": 1, "enrolled": 1, "error": 0}
    assert preview.actionable == 2


def test_turkish_excel_csv_is_decoded(offering):
    text = (
        "student_number;email;first_name;last_name;cohort_year\n"
        "2024-0001;sukru@example.edu;Şükrü;Öztürk;2024\n"
    )
    preview = parse_enrollment_csv(upload(text, encoding="cp1254"), offering=offering)
    assert preview.file_errors == []
    assert (preview.rows[0].first_name, preview.rows[0].last_name) == ("Şükrü", "Öztürk")


def test_missing_columns_is_a_file_error(offering):
    preview = parse_enrollment_csv(upload("email,first_name\na@b.co,A\n"), offering=offering)
    assert preview.rows == []
    assert "Missing column(s): student_number, last_name, cohort_year" in preview.file_errors[0]


def test_confirm_creates_accounts_enrolls_audits_and_emails(
    offering, head, settings, mailoutbox, django_capture_on_commit_callbacks
):
    job = create_enrollment_import_job(
        head, offering, upload(HEADER + "2024-0001,new@example.edu,Ada,Lovelace,2024\n")
    )

    with django_capture_on_commit_callbacks(execute=True):
        result = confirm_enrollment_import(head, job)

    student = User.objects.get(student_number="2024-0001")
    assert not student.has_usable_password()
    assert ProgramMembership.objects.filter(
        user=student, role="student", cohort_year=2024, program=offering.course.program
    ).exists()
    assert Enrollment.objects.filter(offering=offering, student=student).exists()
    assert AuditEvent.objects.filter(action="enrollment.create", actor=head).count() == 1
    assert (result.created_accounts, result.enrolled) == (1, 1)
    assert len(mailoutbox) == 1 and mailoutbox[0].to == ["new@example.edu"]
    assert settings.SITE_URL in mailoutbox[0].body
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.APPLIED


def test_errors_block_unless_skipped(offering, head):
    job = create_enrollment_import_job(
        head,
        offering,
        upload(HEADER + "2024-0001,ok@example.edu,Ok,Row,2024\n2024-0002,,Bad,Row,2024\n"),
    )
    with pytest.raises(ValidationError):
        confirm_enrollment_import(head, job)
    assert not User.objects.filter(student_number="2024-0001").exists()

    result = confirm_enrollment_import(head, job, skip_invalid=True)
    assert (result.enrolled, result.skipped) == (1, 1)


def test_reimporting_the_same_file_changes_nothing(offering, head):
    content = HEADER + "2024-0001,new@example.edu,Ada,Lovelace,2024\n"
    confirm_enrollment_import(head, create_enrollment_import_job(head, offering, upload(content)))
    second = create_enrollment_import_job(head, offering, upload(content))
    result = confirm_enrollment_import(head, second)
    assert (result.created_accounts, result.enrolled, result.skipped) == (0, 0, 1)


def test_confirm_refuses_when_data_changed_since_preview(offering, head):
    job = create_enrollment_import_job(
        head, offering, upload(HEADER + "2024-0001,new@example.edu,Ada,Lovelace,2024\n")
    )
    UserFactory(student_number="2024-0001", email="new@example.edu")
    with pytest.raises(PreviewOutdated) as exc:
        confirm_enrollment_import(head, job)
    assert exc.value.fresh.rows[0].status == "existing"
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.READY
    assert job.result["rows"][0]["status"] == "existing"


def test_closed_term_refuses(offering, head):
    job = create_enrollment_import_job(
        head, offering, upload(HEADER + "2024-0001,new@example.edu,Ada,Lovelace,2024\n")
    )
    Term.objects.filter(pk=offering.term_id).update(status=Term.Status.CLOSED)
    with pytest.raises(ValidationError):
        confirm_enrollment_import(head, job)


def test_second_confirm_is_refused(offering, head):
    job = create_enrollment_import_job(
        head, offering, upload(HEADER + "2024-0001,new@example.edu,Ada,Lovelace,2024\n")
    )
    confirm_enrollment_import(head, job)
    with pytest.raises(ValidationError, match="already applied"):
        confirm_enrollment_import(head, job)


def test_dropped_student_is_re_enrolled(offering, head):
    student = UserFactory(student_number="2024-0001", email="back@example.edu")
    EnrollmentFactory(offering=offering, student=student, status="dropped")
    job = create_enrollment_import_job(
        head, offering, upload(HEADER + "2024-0001,back@example.edu,Back,Again,2024\n")
    )
    result = confirm_enrollment_import(head, job)
    assert result.reactivated == 1
    assert Enrollment.objects.get(offering=offering, student=student).status == "enrolled"
