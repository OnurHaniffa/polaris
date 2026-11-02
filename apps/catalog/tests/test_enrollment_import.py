from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalog.importers import parse_enrollment_csv
from apps.catalog.models import Term
from apps.core.tests.factories import (
    EnrollmentFactory,
    MembershipFactory,
    OfferingFactory,
    TermFactory,
    UserFactory,
)

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
        code="2026F", name="Fall 2026", starts_on=date(2026, 9, 14),
        ends_on=date(2027, 1, 22), status=Term.Status.OPEN,
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