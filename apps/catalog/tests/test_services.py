from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.services import get_or_create_student
from apps.catalog import services
from apps.catalog.models import Enrollment, ProgramOutcomeSet, Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import (
    CourseFactory,
    EnrollmentFactory,
    LearningOutcomeFactory,
    LOPOWeightFactory,
    MembershipFactory,
    OfferingFactory,
    ProgramFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
    TermFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def head():
    return UserFactory(email="head@acibadem.edu.tr")


@pytest.fixture
def cse():
    return ProgramFactory(code="TST")


@pytest.fixture
def term():
    return TermFactory(
        code="2026F",
        name="Fall 2026",
        starts_on=date(2026, 9, 21),
        ends_on=date(2027, 1, 15),
        status=Term.Status.OPEN,
    )


@pytest.fixture
def offering(cse, term):
    return OfferingFactory(course=CourseFactory(program=cse, code="CSE 311"), term=term)


@pytest.fixture
def student(cse):
    user = UserFactory(student_number="2023001")
    MembershipFactory(user=user, program=cse, role="student", cohort_year=2023)
    return user


# ---------- terms ----------


def test_term_lifecycle_and_audit(head):
    term = services.create_term(
        head,
        code="2027S",
        name="Spring 2027",
        starts_on=date(2027, 2, 15),
        ends_on=date(2027, 6, 20),
    )
    assert term.status == Term.Status.PLANNED
    services.set_term_status(head, term, Term.Status.OPEN)
    services.set_term_status(head, term, Term.Status.CLOSED)
    term.refresh_from_db()
    assert term.status == Term.Status.CLOSED
    actions = list(
        AuditEvent.objects.filter(entity_type="term")
        .order_by("created_at", "id")
        .values_list("action", flat=True)
    )
    assert actions == ["term.create", "term.open", "term.close"]


@pytest.mark.parametrize(
    "start,target",
    [
        (Term.Status.PLANNED, Term.Status.CLOSED),
        (Term.Status.OPEN, Term.Status.PLANNED),
        (Term.Status.OPEN, Term.Status.OPEN),
    ],
)
def test_invalid_term_transitions_refused(head, start, target):
    term = TermFactory(status=start)
    with pytest.raises(ValidationError):
        services.set_term_status(head, term, target)


def test_reopen_needs_a_reason_and_records_it(head, term):
    services.set_term_status(head, term, Term.Status.CLOSED)
    with pytest.raises(ValidationError):
        services.set_term_status(head, term, Term.Status.OPEN, reason="oops")
    services.set_term_status(
        head, term, Term.Status.OPEN, reason="Grade appeal approved by the board"
    )
    event = AuditEvent.objects.get(action="term.reopen")
    assert event.after == {"status": "open", "reason": "Grade appeal approved by the board"}
    assert event.actor == head


def test_update_term_cannot_change_status(head, term):
    with pytest.raises(ValueError):
        services.update_term(head, term, status=Term.Status.CLOSED)


# ---------- courses ----------


def test_course_code_normalised_and_unique_per_program(head, cse):
    course = services.save_course(
        head, program=cse, code="cse  311", title="Software", credits=3, ects=6
    )
    assert course.code == "CSE 311"
    with pytest.raises(ValidationError) as err:
        services.save_course(head, program=cse, code="CSE 311", title="Dup", credits=3, ects=6)
    assert "already exists" in str(err.value)
    other = ProgramFactory(code="BME")
    assert services.save_course(
        head, program=other, code="CSE 311", title="Elsewhere", credits=3, ects=6
    )


# ---------- offerings ----------


def test_create_offering_with_instructors(head, cse, term):
    teacher = UserFactory()
    MembershipFactory(user=teacher, program=cse, role="instructor")
    offering = services.create_offering(
        head, course=CourseFactory(program=cse), term=term, section="1", instructors=[teacher]
    )
    assert list(offering.instructors.all()) == [teacher]
    event = AuditEvent.objects.get(action="offering.create")
    assert event.offering == offering and event.after["instructors"] == [teacher.email]


def test_non_instructor_cannot_be_assigned(head, cse, term):
    random_user = UserFactory()
    with pytest.raises(ValidationError) as err:
        services.create_offering(
            head, course=CourseFactory(program=cse), term=term, instructors=[random_user]
        )
    assert "instructors" in err.value.message_dict


def test_duplicate_section_refused(head, offering):
    with pytest.raises(ValidationError):
        services.create_offering(
            head, course=offering.course, term=offering.term, section=offering.section
        )


def test_no_offerings_in_closed_term(head, cse):
    closed = TermFactory(status=Term.Status.CLOSED)
    with pytest.raises(ValidationError):
        services.create_offering(head, course=CourseFactory(program=cse), term=closed)


def test_update_offering_blocked_when_term_closed(head, offering):
    offering.term.status = Term.Status.CLOSED
    offering.term.save()
    with pytest.raises(ValidationError) as err:
        services.update_offering(head, offering, section="2")
    assert "is closed" in str(err.value)


# ---------- enrollments ----------


def test_enroll_twice_is_a_message_not_a_crash(head, offering, student):
    """B3 AC 4."""
    services.enroll(head, offering, student)
    with pytest.raises(ValidationError) as err:
        services.enroll(head, offering, student)
    assert "already enrolled" in str(err.value)
    assert Enrollment.objects.filter(offering=offering, student=student).count() == 1


def test_drop_keeps_row_and_reenroll_restores_it(head, offering, student):
    enrollment = services.enroll(head, offering, student)
    services.drop(head, enrollment)
    enrollment.refresh_from_db()
    assert enrollment.status == Enrollment.Status.DROPPED
    again = services.enroll(head, offering, student)
    assert again.pk == enrollment.pk and again.status == Enrollment.Status.ENROLLED


def test_cannot_enroll_non_student(head, offering):
    with pytest.raises(ValidationError):
        services.enroll(head, offering, UserFactory())


def test_closed_term_blocks_enrollment_changes(head, offering, student):
    """B3 AC 3, service side."""
    enrollment = EnrollmentFactory(offering=offering, student=student)
    offering.term.status = Term.Status.CLOSED
    offering.term.save()
    with pytest.raises(ValidationError):
        services.drop(head, enrollment)
    with pytest.raises(ValidationError):
        services.enroll(head, offering, UserFactory())


def test_get_or_create_student_matches_by_number(head, cse, student):
    found, created = get_or_create_student(
        student_number="2023001",
        email="",
        first_name="",
        last_name="",
        program=cse,
        cohort_year=None,
        actor=head,
    )
    assert found == student and not created


def test_get_or_create_student_creates_with_unusable_password(head, cse):
    user, created = get_or_create_student(
        student_number="2024777",
        email="Ada@Acibadem.edu.tr",
        first_name="Ada",
        last_name="Kaya",
        program=cse,
        cohort_year=2024,
        actor=head,
    )
    assert created and not user.has_usable_password()
    assert user.memberships.get().cohort_year == 2024


def test_get_or_create_student_rejects_email_of_someone_else(head, cse):
    UserFactory(email="taken@acibadem.edu.tr")
    with pytest.raises(ValidationError) as err:
        get_or_create_student(
            student_number="2024888",
            email="taken@acibadem.edu.tr",
            first_name="A",
            last_name="B",
            program=cse,
            cohort_year=2024,
            actor=head,
        )
    assert "email" in err.value.message_dict


def test_get_or_create_student_needs_cohort_for_new_membership(head, cse):
    existing = UserFactory(student_number="2022555")  # account exists, no membership in CSE
    with pytest.raises(ValidationError) as err:
        get_or_create_student(
            student_number="2022555",
            email=existing.email,
            first_name="",
            last_name="",
            program=cse,
            cohort_year=None,
            actor=head,
        )
    assert "cohort_year" in err.value.message_dict


# ---------- PO sets ----------


@pytest.fixture
def active_set(cse):
    po_set = ProgramOutcomeSetFactory(
        program=cse, label="2023 curriculum", effective_from_year=2020, is_active=True
    )
    for n in range(1, 12):
        ProgramOutcomeFactory(po_set=po_set, number=n, short_name=f"PO {n} name")
    return po_set


def test_copy_po_set_copies_everything_inactive(head, active_set):
    """B2 AC 2, first half."""
    copy = services.copy_po_set(head, active_set, label="2027 curriculum", effective_from_year=2027)
    assert copy.outcomes.count() == 11 and not copy.is_active
    assert list(copy.outcomes.values_list("number", flat=True)) == list(range(1, 12))


def test_activate_switches_the_single_active_set(head, active_set, cse):
    """B2 AC 2, second half: exactly one active set afterwards."""
    copy = services.copy_po_set(head, active_set, label="2027 curriculum", effective_from_year=2027)
    services.activate_po_set(head, copy)
    assert list(ProgramOutcomeSet.objects.filter(program=cse, is_active=True)) == [copy]
    event = AuditEvent.objects.get(action="po_set.activate")
    assert event.before == {"active": "2023 curriculum"} and event.after == {
        "active": "2027 curriculum"
    }


def test_empty_set_cannot_be_activated(head, cse):
    empty = ProgramOutcomeSetFactory(
        program=cse, label="empty", effective_from_year=2030, is_active=False
    )
    with pytest.raises(ValidationError):
        services.activate_po_set(head, empty)


def test_copy_label_must_be_unique(head, active_set):
    with pytest.raises(ValidationError):
        services.copy_po_set(head, active_set, label="2023 curriculum", effective_from_year=2027)


def test_delete_referenced_po_names_the_courses(head, active_set, offering):
    """B2 AC 3."""
    po = active_set.outcomes.get(number=3)
    LOPOWeightFactory(
        learning_outcome=LearningOutcomeFactory(offering=offering, number=1),
        program_outcome=po,
        weight=4,
    )
    with pytest.raises(ValidationError) as err:
        services.delete_po(head, po)
    assert "CSE 311 (Fall 2026)" in str(err.value)
    assert active_set.outcomes.filter(number=3).exists()


def test_delete_unused_po_is_audited(head, active_set):
    po = active_set.outcomes.get(number=11)
    services.delete_po(head, po)
    assert not active_set.outcomes.filter(number=11).exists()
    assert AuditEvent.objects.get(action="po.delete").before["number"] == 11


def test_update_po_only_wording(head, active_set):
    po = active_set.outcomes.get(number=1)
    services.update_po(head, po, short_name="Math & science")
    with pytest.raises(ValueError):
        services.update_po(head, po, number=99)
