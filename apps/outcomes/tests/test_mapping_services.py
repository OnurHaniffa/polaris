from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.catalog.models import Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import (
    EnrollmentFactory,
    GradeFactory,
    LearningOutcomeFactory,
    OfferingFactory,
    ProgramOutcomeFactory,
    ProgramOutcomeSetFactory,
)
from apps.outcomes import services
from apps.outcomes.matrix import A_LO, LO_PO, Cell, matrix_version
from apps.outcomes.models import Assessment, AssessmentLOWeight, LOPOWeight, Source
from apps.scoring.engine import compute_student_profile, display
from apps.scoring.loaders import load_offering_inputs


def cells(mapping):
    return [Cell(row.pk, col.pk, raw) for (row, col), raw in mapping.items()]


def save_a_lo(course, mapping, *, version=None, user=None):
    version = matrix_version(course.offering, A_LO) if version is None else version
    return services.save_assessment_lo_matrix(
        user or course.teacher, course.offering, cells(mapping), expected_version=version
    )


def save_lo_po(course, mapping, *, version=None, user=None):
    version = matrix_version(course.offering, LO_PO) if version is None else version
    return services.save_lo_po_matrix(
        user or course.teacher, course.offering, cells(mapping), expected_version=version
    )


def a_lo_rows(course):
    return {
        (w.assessment_id, w.learning_outcome_id): w.weight
        for w in AssessmentLOWeight.objects.filter(assessment__offering=course.offering)
    }


def test_save_creates_rows_and_one_audit_event(course):
    result = save_a_lo(
        course,
        {
            (course.midterm, course.lo1): "60",
            (course.midterm, course.lo2): "40",
            (course.project, course.lo1): "",
        },
    )
    assert (result.created, result.updated, result.deleted) == (2, 0, 0)
    assert a_lo_rows(course) == {
        (course.midterm.pk, course.lo1.pk): Decimal("60"),
        (course.midterm.pk, course.lo2.pk): Decimal("40"),
    }
    event = AuditEvent.objects.get(action="assessment_lo.update")
    assert event.offering == course.offering and event.actor == course.teacher
    assert event.before == {"cells": {}}
    assert event.after == {
        "cells": {
            f"{course.midterm.pk}:{course.lo1.pk}": "60",
            f"{course.midterm.pk}:{course.lo2.pk}": "40",
        }
    }


def test_blank_cell_deletes_the_row_and_unposted_cells_stay(course):
    save_a_lo(course, {(course.midterm, course.lo1): "60", (course.project, course.lo2): "100"})
    result = save_a_lo(course, {(course.midterm, course.lo1): ""})  # project→lo2 not posted
    assert result.deleted == 1
    assert a_lo_rows(course) == {(course.project.pk, course.lo2.pk): Decimal("100")}


def test_saving_the_same_values_changes_nothing(course):
    save_a_lo(course, {(course.midterm, course.lo1): "60"})
    result = save_a_lo(course, {(course.midterm, course.lo1): "60.00"})
    assert not result.changed
    assert AuditEvent.objects.filter(action="assessment_lo.update").count() == 1


@pytest.mark.parametrize("raw", ["0", "6", "2.5", "abc"])
def test_one_bad_cell_saves_nothing(course, raw):
    """B5 AC2, at service level: every error is reported, no partial save."""
    with pytest.raises(ValidationError) as exc:
        save_lo_po(course, {(course.lo1, course.po1): "4", (course.lo2, course.po2): raw})
    assert list(exc.value.message_dict) == [f"lo_po-{course.lo2.pk}-{course.po2.pk}"]
    assert not LOPOWeight.objects.exists()


def test_cell_from_another_course_is_rejected(course):
    other_lo = LearningOutcomeFactory(
        offering=OfferingFactory(course__program=course.program, term=course.term), number=1
    )
    with pytest.raises(ValidationError) as exc:
        save_a_lo(course, {(course.midterm, other_lo): "50"})
    assert "isn't part of this course" in str(exc.value)
    assert not AssessmentLOWeight.objects.exists()


def test_po_from_an_inactive_set_is_rejected(course):
    old_set = ProgramOutcomeSetFactory(
        program=course.program, label="2018 curriculum", effective_from_year=2018, is_active=False
    )
    old_po = ProgramOutcomeFactory(po_set=old_set, number=1)
    with pytest.raises(ValidationError):
        save_lo_po(course, {(course.lo1, old_po): "3"})


def test_stale_version_is_refused_and_keeps_the_other_save(course, head_user):
    """B5 AC3: the instructor opened the page, then the head saved."""
    opened_with = matrix_version(course.offering, LO_PO)
    save_lo_po(course, {(course.lo1, course.po1): "5"}, user=head_user)
    with pytest.raises(ValidationError) as exc:
        save_lo_po(course, {(course.lo1, course.po1): "2"}, version=opened_with)
    assert exc.value.code == "stale"
    assert LOPOWeight.objects.get().weight == 5


def test_a_failure_after_writing_rolls_everything_back(course, monkeypatch):
    def audit_is_down(*args, **kwargs):
        raise RuntimeError("audit table unavailable")

    monkeypatch.setattr(services, "record", audit_is_down)
    with pytest.raises(RuntimeError):
        save_a_lo(course, {(course.midterm, course.lo1): "60"})
    assert not AssessmentLOWeight.objects.exists()


def test_closed_term_refuses_the_save(course):
    course.term.status = Term.Status.CLOSED
    course.term.save()
    with pytest.raises(ValidationError):
        save_a_lo(course, {(course.midterm, course.lo1): "60"})


def test_unchanged_ai_cell_keeps_its_source_and_a_changed_one_becomes_manual(course):
    LOPOWeight.objects.create(
        learning_outcome=course.lo1,
        program_outcome=course.po1,
        weight=3,
        source=Source.AI_SUGGESTED,
        rationale="Design choices need math",
    )
    LOPOWeight.objects.create(
        learning_outcome=course.lo2,
        program_outcome=course.po2,
        weight=4,
        source=Source.AI_SUGGESTED,
        rationale="Agile is problem solving",
    )
    save_lo_po(course, {(course.lo1, course.po1): "3", (course.lo2, course.po2): "5"})
    kept = LOPOWeight.objects.get(learning_outcome=course.lo1)
    changed = LOPOWeight.objects.get(learning_outcome=course.lo2)
    assert (kept.source, kept.rationale) == (Source.AI_SUGGESTED, "Design choices need math")
    assert (changed.weight, changed.source, changed.rationale) == (5, Source.MANUAL, "")


def test_elif_example_entered_through_the_grids(course):
    """B5 AC1: the professor's slide, typed into the two grids, gives 86.0 / 82.9 / 85.0 / 82.9."""
    save_a_lo(
        course,
        {
            (course.midterm, course.lo1): "60",
            (course.midterm, course.lo2): "40",
            (course.project, course.lo1): "40",
            (course.project, course.lo2): "100",
        },
    )
    save_lo_po(
        course,
        {
            (course.lo1, course.po1): "4",
            (course.lo2, course.po1): "2",
            (course.lo2, course.po2): "5",
        },
    )
    elif_ = EnrollmentFactory(offering=course.offering)
    now = timezone.now()
    for assessment, mark in ((course.midterm, "90"), (course.project, "80")):
        GradeFactory(
            assessment=assessment,
            enrollment=elif_,
            score=Decimal(mark),
            published_score=Decimal(mark),
            published_at=now,
        )
    Assessment.objects.filter(offering=course.offering).update(published_at=now)

    profile = compute_student_profile([load_offering_inputs(course.offering)[elif_.pk]])
    o = course.offering.pk
    assert display(profile.lo_scores[(o, course.lo1.pk)].score) == "86.0"
    assert display(profile.lo_scores[(o, course.lo2.pk)].score) == "82.9"
    assert display(profile.po_scores[course.po1.pk].score) == "85.0"
    assert display(profile.po_scores[course.po2.pk].score) == "82.9"
