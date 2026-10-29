import pytest

from apps.catalog.selectors import po_set_for_student, po_set_ids_for_students
from apps.core.tests.factories import (
    MembershipFactory,
    ProgramFactory,
    ProgramOutcomeSetFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def test_po_set_fallbacks():
    program = ProgramFactory()
    old = ProgramOutcomeSetFactory(program=program, effective_from_year=2020, is_active=False)
    new = ProgramOutcomeSetFactory(program=program, effective_from_year=2026, is_active=True)
    veteran = UserFactory()
    MembershipFactory(user=veteran, program=program, cohort_year=2019)  # older than every set
    stranger = UserFactory()  # no membership at all
    mid = UserFactory()
    MembershipFactory(user=mid, program=program, cohort_year=2022)

    ids = po_set_ids_for_students([veteran.id, stranger.id, mid.id], program)
    assert ids == {veteran.id: new.id, stranger.id: new.id, mid.id: old.id}
    assert po_set_for_student(mid, program) == old


def test_program_without_active_set_is_an_error():
    program = ProgramFactory()
    ProgramOutcomeSetFactory(program=program, is_active=False)
    with pytest.raises(Exception, match="no active PO set"):
        po_set_ids_for_students([1], program)
