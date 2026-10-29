"""Tests for the pure scoring engine (spec §2.6). No database: these run in milliseconds.

Golden tests pin the professor's numbers. Policy tests pin each rule in §2.3.
Property tests (Hypothesis) throw hundreds of random inputs at the maths."""

import random
from decimal import Decimal as D

import pytest
from hypothesis import given
from hypothesis import strategies as st

from apps.scoring.engine import (
    Edge,
    NodeScore,
    OfferingInputs,
    compute_student_profile,
    display,
    normalise,
    propagate,
    weighted_average,
)

# ---------- the professor's example (spec §2.2) ----------

GRADES = {"midterm": D(90), "project": D(80)}
A_TO_LO = [
    Edge("midterm", "LO1", D(60)),
    Edge("project", "LO1", D(40)),
    Edge("midterm", "LO2", D(40)),
    Edge("project", "LO2", D(100)),
]
LO_TO_PO = [
    Edge("LO1", "PO1", D(4)),
    Edge("LO2", "PO1", D(2)),
    Edge("LO2", "PO2", D(5)),
]


def lo_scores(grades=GRADES):
    return {k: v.score for k, v in propagate(grades, A_TO_LO).items() if v.score is not None}


# ---------- golden tests ----------


def test_elif_lo1():
    assert propagate(GRADES, A_TO_LO)["LO1"].score == D(86)


def test_elif_lo2():
    score = propagate(GRADES, A_TO_LO)["LO2"].score
    assert display(score) == "82.9"
    assert abs(score - D(11600) / D(140)) < D("1e-20")  # 82.857142…, not rounded


def test_elif_po1_on_1_to_5_scale():
    po = propagate(lo_scores(), LO_TO_PO)
    assert display(po["PO1"].score) == "85.0"


def test_elif_po2():
    po = propagate(lo_scores(), LO_TO_PO)
    assert display(po["PO2"].score) == "82.9"


def test_brief_rounding_discrepancy():
    """The brief rounded LO 2 to 82 before computing PO 1. That gives 84.7, not 85.0:
    this is why we never round intermediate values (P7)."""
    rounded_too_early = {"LO1": D(86), "LO2": D(82)}
    po = propagate(rounded_too_early, LO_TO_PO)
    assert display(po["PO1"].score) == "84.7"


# ---------- policy tests ----------


def test_missing_grade_is_skipped_not_zero():
    lo = propagate({"midterm": D(90)}, A_TO_LO)
    assert display(lo["LO2"].score) == "90.0"
    assert display(lo["LO2"].coverage * 100) == "28.6"  # 40 / 140


def test_full_coverage_is_exactly_one():
    lo = propagate(GRADES, A_TO_LO)
    assert lo["LO1"].coverage == D(1)
    assert lo["LO2"].coverage == D(1)


def test_no_data_gives_none():
    lo = propagate({}, A_TO_LO)
    assert lo["LO1"] == NodeScore(score=None, coverage=D(0))
    assert display(lo["LO1"].score) == "—"


def test_weighted_average_of_nothing_is_none():
    assert weighted_average([]) is None


@pytest.mark.parametrize("bad", [D(0), D(-1)])
def test_zero_or_negative_weight_raises(bad):
    with pytest.raises(ValueError, match="weight must be positive"):
        propagate(GRADES, [Edge("midterm", "LO1", bad)])


def test_normalise_out_of_20():
    assert normalise(D(17), D(20)) == D(85)


@pytest.mark.parametrize("bad_max", [D(0), D(-5)])
def test_normalise_rejects_zero_max(bad_max):
    with pytest.raises(ValueError, match="max_score must be positive"):
        normalise(D(10), bad_max)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(D("84.95"), "85.0"), (D("84.94"), "84.9"), (D("0"), "0.0"), (D("100"), "100.0"), (None, "—")],
)
def test_display_half_up(value, expected):
    assert display(value) == expected


# ---------- whole-student calculation ----------


def elif_cse311():
    """Offering 311 with the slide example. Assessment ids 1 (midterm) and 2 (project),
    LO ids 11 and 12, PO ids 1 and 2."""
    return OfferingInputs(
        offering_id=311,
        grades={1: D(90), 2: D(80)},
        max_scores={1: D(100), 2: D(100)},
        assessment_lo_edges=(
            Edge(1, 11, D(60)),
            Edge(2, 11, D(40)),
            Edge(1, 12, D(40)),
            Edge(2, 12, D(100)),
        ),
        lo_po_edges=(Edge(11, 1, D(4)), Edge(12, 1, D(2)), Edge(12, 2, D(5))),
    )


def test_profile_reproduces_the_slide():
    profile = compute_student_profile([elif_cse311()])
    assert display(profile.lo_scores[(311, 11)].score) == "86.0"
    assert display(profile.lo_scores[(311, 12)].score) == "82.9"
    assert display(profile.po_scores[1].score) == "85.0"
    assert display(profile.po_scores[2].score) == "82.9"


def test_raw_marks_are_normalised_before_weighting():
    """Same example, but the midterm is marked out of 50: 45/50 is still 90%."""
    off = elif_cse311()
    out_of_50 = OfferingInputs(
        offering_id=off.offering_id,
        grades={1: D(45), 2: D(80)},
        max_scores={1: D(50), 2: D(100)},
        assessment_lo_edges=off.assessment_lo_edges,
        lo_po_edges=off.lo_po_edges,
    )
    profile = compute_student_profile([out_of_50])
    assert display(profile.po_scores[1].score) == "85.0"


def test_two_courses_feed_one_po():
    """P8: one flat weighted average over every LO→PO link from every course.
    Course 321 has one assessment (70/100) feeding LO 21, linked to PO 1 with weight 3.
    Expected PO 1 = (86×4 + 82.857…×2 + 70×3) ÷ (4+2+3) = 719.714… ÷ 9 = 79.968…"""
    cse321 = OfferingInputs(
        offering_id=321,
        grades={5: D(70)},
        max_scores={5: D(100)},
        assessment_lo_edges=(Edge(5, 21, D(100)),),
        lo_po_edges=(Edge(21, 1, D(3)),),
    )
    profile = compute_student_profile([elif_cse311(), cse321])
    expected = (D(86) * 4 + D(11600) / D(140) * 2 + D(70) * 3) / D(9)
    assert abs(profile.po_scores[1].score - expected) < D("1e-20")
    assert display(profile.po_scores[1].score) == "80.0"
    assert display(profile.po_scores[2].score) == "82.9"  # untouched by course 321


def test_lo_keys_do_not_collide_across_offerings():
    """LO id 11 exists in both offerings here; they must stay two separate LOs."""
    other = OfferingInputs(
        offering_id=999,
        grades={7: D(50)},
        max_scores={7: D(100)},
        assessment_lo_edges=(Edge(7, 11, D(100)),),
        lo_po_edges=(Edge(11, 3, D(5)),),
    )
    profile = compute_student_profile([elif_cse311(), other])
    assert profile.lo_scores[(311, 11)].score == D(86)
    assert profile.lo_scores[(999, 11)].score == D(50)
    assert profile.po_scores[3].score == D(50)


def test_contributors_list():
    profile = compute_student_profile([elif_cse311()])
    assert profile.po_contributors[1] == [(311, 11, D(4)), (311, 12, D(2))]
    assert profile.po_contributors[2] == [(311, 12, D(5))]


def test_ungraded_course_gives_po_with_no_score():
    """An in-progress course with nothing graded yet: the PO exists but has score None,
    and coverage 0, never a 0 score (P12)."""
    off = elif_cse311()
    ungraded = OfferingInputs(
        offering_id=off.offering_id,
        grades={},
        max_scores=off.max_scores,
        assessment_lo_edges=off.assessment_lo_edges,
        lo_po_edges=off.lo_po_edges,
    )
    profile = compute_student_profile([ungraded])
    assert profile.po_scores[1] == NodeScore(score=None, coverage=D(0))


def test_no_offerings_gives_empty_profile():
    profile = compute_student_profile([])
    assert profile.lo_scores == {}
    assert profile.po_scores == {}


# ---------- properties (Hypothesis) ----------

scores = st.decimals(min_value=0, max_value=100, places=2)
weights = st.decimals(min_value=1, max_value=100, places=0)
pairs_strategy = st.lists(st.tuples(scores, weights), min_size=1, max_size=12)


def _layer(pairs):
    src = {i: s for i, (s, _) in enumerate(pairs)}
    edges = [Edge(i, "T", w) for i, (_, w) in enumerate(pairs)]
    return src, edges


@given(pairs_strategy)
def test_weighted_average_is_bounded(pairs):
    src, edges = _layer(pairs)
    result = propagate(src, edges)["T"].score
    assert min(src.values()) <= result <= max(src.values())


@given(pairs_strategy, st.decimals(min_value=D("0.01"), max_value=1000, places=2))
def test_scale_invariant(pairs, factor):
    src, edges = _layer(pairs)
    scaled = [Edge(e.source, e.target, e.weight * factor) for e in edges]
    a = propagate(src, edges)["T"].score
    b = propagate(src, scaled)["T"].score
    assert abs(a - b) < D("1e-20")


@given(pairs_strategy, st.randoms(use_true_random=False))
def test_order_independent(pairs, rnd: random.Random):
    src, edges = _layer(pairs)
    shuffled = edges[:]
    rnd.shuffle(shuffled)
    a = propagate(src, edges)["T"].score
    b = propagate(src, shuffled)["T"].score
    assert abs(a - b) < D("1e-20")


@given(pairs_strategy, weights)
def test_neutral_addition(pairs, extra_weight):
    src, edges = _layer(pairs)
    before = propagate(src, edges)["T"].score
    src["extra"] = before
    after = propagate(src, [*edges, Edge("extra", "T", extra_weight)])["T"].score
    assert abs(after - before) < D("1e-20")


@given(pairs_strategy, st.data())
def test_coverage_range(pairs, data):
    src, edges = _layer(pairs)
    keep = data.draw(st.sets(st.sampled_from(sorted(src))))
    partial = {k: v for k, v in src.items() if k in keep}
    coverage = propagate(partial, edges)["T"].coverage
    assert D(0) <= coverage <= D(1)
    assert (coverage == D(1)) == (keep == set(src))
