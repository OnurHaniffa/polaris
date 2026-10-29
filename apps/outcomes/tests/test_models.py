from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction

from apps.core.tests.factories import (
    AssessmentFactory,
    AssessmentLOWeightFactory,
    GradeFactory,
    LearningOutcomeFactory,
    LOPOWeightFactory,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("weight", [D(0), D("-5"), D("100.01")])
def test_assessment_lo_weight_range(weight):
    """P1: 0 < weight ≤ 100."""
    with pytest.raises(IntegrityError), transaction.atomic():
        AssessmentLOWeightFactory(weight=weight)


@pytest.mark.parametrize("weight", [0, 6])
def test_lo_po_weight_range(weight):
    """P2: integers 1..5."""
    with pytest.raises(IntegrityError), transaction.atomic():
        LOPOWeightFactory(weight=weight)


def test_valid_weights_save():
    a_lo = AssessmentLOWeightFactory(weight=D("40"))
    lo_po = LOPOWeightFactory(weight=5)
    assert str(a_lo).endswith(": 40%")
    assert str(lo_po).endswith(": 5")


def test_lo_number_unique_per_offering():
    lo = LearningOutcomeFactory(number=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        LearningOutcomeFactory(offering=lo.offering, number=1)
    assert str(lo) == "LO 1"


def test_max_score_must_be_positive():
    with pytest.raises(IntegrityError), transaction.atomic():
        AssessmentFactory(max_score=D(0))


def test_negative_score_rejected():
    with pytest.raises(IntegrityError), transaction.atomic():
        GradeFactory(score=D(-1))


def test_unpublished_change_flag():
    grade = GradeFactory(score=D(80), published=True)
    assert not grade.has_unpublished_change
    grade.score = D(85)
    assert grade.has_unpublished_change
    assert str(grade.assessment) == grade.assessment.name
    assert "85" in str(grade)
