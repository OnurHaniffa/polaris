import pytest

from apps.catalog.models import Program, ProgramOutcome, ProgramOutcomeSet

pytestmark = pytest.mark.django_db


def active_po_set(program):
    return ProgramOutcomeSet.objects.get(program=program, is_active=True)


def test_official_pos_are_seeded():
    """S1-05 / B2 AC1: a fresh database has CSE with the 11 official POs."""
    cse = Program.objects.get(code="CSE")
    outcomes = ProgramOutcome.objects.filter(po_set=active_po_set(cse))
    assert outcomes.count() == 11
    assert outcomes.get(number=6).short_name == "Teamwork"
    assert outcomes.get(number=8).description.startswith("Gain awareness of of the need")
