from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.catalog.models import ProgramOutcomeSet, Term
from apps.core.tests.factories import ProgramOutcomeFactory, TermFactory
from apps.core.tests.scenarios import one_lo_class
from apps.scoring.aggregates import program_po_summary
from apps.scoring.engine import display

pytestmark = pytest.mark.django_db


@pytest.fixture
def dept():
    spring = TermFactory(
        code="2026S",
        name="Spring 2026",
        starts_on=date(2026, 2, 9),
        ends_on=date(2026, 6, 15),
        status=Term.Status.CLOSED,
    )
    fall = TermFactory(
        code="2026F",
        name="Fall 2026",
        starts_on=date(2026, 9, 14),
        ends_on=date(2027, 1, 22),
        status=Term.Status.OPEN,
    )
    a = one_lo_class(students_scores=[(None, 50), (None, 70), (None, 90)], term=spring)
    b = one_lo_class(students_scores=[(a.students[0], 30)], term=fall, po=a.po)
    return SimpleNamespace(spring=spring, fall=fall, a=a, b=b, program=a.program, po=a.po)


def _for(summaries, po):
    return next(s for s in summaries if s.po.id == po.id)


def test_closed_terms_only_matches_hand_computation(dept):
    """B10 AC1."""
    s = _for(
        program_po_summary(dept.program, terms=[dept.spring, dept.fall], include_open_terms=False),
        dept.po,
    )
    assert s.mean == Decimal("70")
    assert (s.n_evidence, s.n_attaining) == (3, 2)
    assert s.rate == Decimal(2) / Decimal(3)


def test_including_open_terms_changes_the_numbers(dept):
    """B10 AC2: öğrenci 1, Fall 2026 sayılınca 40'a düşer."""
    s = _for(
        program_po_summary(dept.program, terms=[dept.spring, dept.fall], include_open_terms=True),
        dept.po,
    )
    assert display(s.mean) == "66.7"
    assert (s.n_evidence, s.n_attaining) == (3, 2)


def test_terms_after_the_cutoff_are_ignored(dept):
    s = _for(
        program_po_summary(dept.program, terms=[dept.spring], include_open_terms=True), dept.po
    )
    assert s.mean == Decimal("70")


def test_po_without_evidence_has_no_rate(dept):
    lonely = ProgramOutcomeFactory(po_set=dept.po.po_set, number=11)
    s = _for(
        program_po_summary(dept.program, terms=[dept.spring], include_open_terms=False), lonely
    )
    assert s.mean is None and s.n_evidence == 0 and s.rate is None


def test_no_terms_gives_empty_rows(dept):
    rows = program_po_summary(dept.program, terms=[], include_open_terms=False)
    assert all(r.n_evidence == 0 for r in rows)


def test_cohort_filter(dept):
    student = dept.a.students[2]  # 90 alan öğrenci
    m = student.memberships.get(program=dept.program)
    m.cohort_year = 2023
    m.save()
    s = _for(
        program_po_summary(
            dept.program, terms=[dept.spring], include_open_terms=False, cohort=2023
        ),
        dept.po,
    )
    assert (s.mean, s.n_evidence) == (Decimal("90"), 1)


def test_program_without_active_po_set_gives_no_rows(dept):
    ProgramOutcomeSet.objects.filter(program=dept.program).update(is_active=False)
    rows = program_po_summary(dept.program, terms=[dept.spring], include_open_terms=False)
    assert rows == []
