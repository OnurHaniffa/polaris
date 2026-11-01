from decimal import Decimal

import pytest

from apps.core.tests.scenarios import elif_scenario, one_lo_class
from apps.scoring.aggregates import bucket_of, class_lo_summary, mean
from apps.scoring.engine import display

pytestmark = pytest.mark.django_db


def test_class_average_is_mean_of_non_none_scores():
    """B9 AC1: (80 + 60) / 2 = 70; the ungraded student is left out, not counted as 0."""
    data = one_lo_class(students_scores=[(None, 80), (None, 60), (None, None)])
    summary = class_lo_summary(data.offering)

    (lo,) = summary.los
    assert lo.mean == Decimal("70")
    assert lo.n == 2
    assert summary.enrolled == 3
    missing_row = next(r for r in summary.rows if r.student_id == data.students[2].id)
    assert missing_row.scores[data.lo.id].score is None


def test_po_contribution_is_mean_of_per_student_po_scores():
    data = one_lo_class(students_scores=[(None, 90), (None, 50)])
    (contrib,) = class_lo_summary(data.offering).po_contribution
    assert contrib.po_id == data.po.id
    assert contrib.mean == Decimal("70")
    assert contrib.n == 2


def test_elif_row_in_her_class():
    data = elif_scenario()
    summary = class_lo_summary(data.offering)
    row = next(r for r in summary.rows if r.student_id == data.student.id)
    assert display(row.scores[data.lo1.id].score) == "86.0"
    assert display(row.scores[data.lo2.id].score) == "82.9"
    po1 = next(c for c in summary.po_contribution if c.po_id == data.po1.id)
    assert display(po1.mean) == "85.0"           # she is the only student


def test_dropped_students_are_not_listed():
    data = one_lo_class(students_scores=[(None, 80), (None, 40)])
    data.enrollments[1].status = "dropped"
    data.enrollments[1].save()
    summary = class_lo_summary(data.offering)
    assert summary.enrolled == 1
    assert summary.los[0].mean == Decimal("80")


@pytest.mark.parametrize(("score", "bucket"), [
    ("0", 0), ("9.99", 0), ("10", 1), ("59.5", 5), ("99.9", 9), ("100", 9),
])
def test_bucket_edges(score, bucket):
    assert bucket_of(Decimal(score)) == bucket


def test_histogram_counts_and_heights():
    data = one_lo_class(students_scores=[(None, 95), (None, 100), (None, 55)])
    (lo,) = class_lo_summary(data.offering).los
    assert lo.histogram[9] == 2 and lo.histogram[5] == 1
    assert lo.histogram_heights[9] == 100 and lo.histogram_heights[5] == 50


def test_mean_of_nothing_is_none():
    assert mean([]) is None


def test_offering_without_los_gives_empty_summary():
    data = one_lo_class(students_scores=[(None, 70)])
    data.lo.delete()
    summary = class_lo_summary(data.offering)
    assert summary.los == []
    assert summary.po_contribution == []
