"""Every rule has a passing case (CLEAN) and at least one failing case (B11 AC1). No database."""

from dataclasses import replace
from decimal import Decimal

import pytest

from apps.outcomes.lint import (
    AI_SUGGESTED,
    ERROR,
    INFO,
    RULES,
    WARNING,
    AssessmentInfo,
    LOInfo,
    LOPOLink,
    MappingSnapshot,
    count_issues,
    l001_unassessed_lo,
    l002_unlinked_lo,
    l003_unused_assessment,
    l004_course_weights,
    l005_overclaimed_po,
    l006_few_pos,
    l007_unconfirmed_ai,
    run_lint,
)
from apps.outcomes.models import Source


def link(lo_id, po_number, weight, source="manual"):
    """LO ids equal LO numbers and PO ids are 100 + PO number, to keep fixtures readable."""
    return LOPOLink(
        lo_id=lo_id,
        lo_number=lo_id,
        po_id=100 + po_number,
        po_number=po_number,
        weight=weight,
        source=source,
    )


CLEAN = MappingSnapshot(
    assessments=(
        AssessmentInfo(10, "Midterm I", Decimal("40")),
        AssessmentInfo(11, "Project", Decimal("60")),
    ),
    los=(LOInfo(1, 1), LOInfo(2, 2)),
    assessment_lo=frozenset({(10, 1), (11, 1), (11, 2)}),
    lo_po=(link(1, 1, 3), link(1, 2, 2), link(2, 3, 3)),  # PO shares 3/8, 2/8, 3/8
)


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.__name__)
def test_every_rule_passes_a_clean_mapping(rule):
    assert rule(CLEAN) == []


def test_clean_mapping_has_no_issues_at_all():
    assert run_lint(CLEAN) == []


def test_l001_lo_without_assessment():
    issues = l001_unassessed_lo(replace(CLEAN, assessment_lo=frozenset({(10, 1), (11, 1)})))
    assert [(i.code, i.severity, i.target) for i in issues] == [("L001", ERROR, "LO 2")]
    assert "never be calculated" in issues[0].message


def test_l002_lo_without_po_link():
    issues = l002_unlinked_lo(replace(CLEAN, lo_po=(link(1, 1, 3), link(1, 2, 2))))
    assert [(i.code, i.severity, i.target) for i in issues] == [("L002", ERROR, "LO 2")]


def test_l003_assessment_feeding_nothing():
    quiz = AssessmentInfo(12, "Quiz 1", None)
    issues = l003_unused_assessment(replace(CLEAN, assessments=CLEAN.assessments + (quiz,)))
    assert [(i.code, i.severity, i.target) for i in issues] == [("L003", WARNING, "Quiz 1")]


def test_l004_course_weights_not_100():
    snap = replace(
        CLEAN,
        assessments=(
            AssessmentInfo(10, "Midterm I", Decimal("40")),
            AssessmentInfo(11, "Project", Decimal("50.00")),
            AssessmentInfo(12, "Quiz", None),
        ),
    )
    [issue] = l004_course_weights(snap)
    assert (
        issue.message
        == "Course weights add up to 90%, not 100%. 1 assessment has no course weight."
    )


def test_l004_quiet_when_no_course_weights_at_all():
    snap = replace(
        CLEAN,
        assessments=(AssessmentInfo(10, "Midterm I", None), AssessmentInfo(11, "Project", None)),
    )
    assert l004_course_weights(snap) == []


def test_l005_boundary_60_percent_is_fine():
    assert l005_overclaimed_po(replace(CLEAN, lo_po=(link(1, 1, 3), link(2, 2, 2)))) == []


def test_l005_over_60_percent_fires():
    [issue] = l005_overclaimed_po(replace(CLEAN, lo_po=(link(1, 1, 4), link(2, 2, 2))))
    assert (issue.code, issue.severity, issue.target) == ("L005", WARNING, "PO 1")
    assert "66.7%" in issue.message


def test_l006_one_po_only():
    [issue] = l006_few_pos(replace(CLEAN, lo_po=(link(1, 4, 3), link(2, 4, 2))))
    assert (issue.code, issue.severity) == ("L006", INFO)


def test_l006_quiet_without_any_links():
    assert l006_few_pos(replace(CLEAN, lo_po=())) == []


def test_l007_unconfirmed_ai_weights():
    snap = replace(
        CLEAN, lo_po=(link(1, 1, 3, AI_SUGGESTED), link(1, 2, 2), link(2, 3, 3, AI_SUGGESTED))
    )
    [issue] = l007_unconfirmed_ai(snap)
    assert (issue.code, issue.severity) == ("L007", WARNING)
    assert issue.message.startswith("2 LO → PO weights suggested by AI have not been checked")


def test_ai_constant_matches_the_model_choice():
    assert AI_SUGGESTED == Source.AI_SUGGESTED


def test_run_lint_lists_errors_first():
    broken = MappingSnapshot(
        assessments=(AssessmentInfo(10, "Midterm I", Decimal("50")),),
        los=(LOInfo(1, 1),),
        assessment_lo=frozenset(),
        lo_po=(),
    )
    codes = [i.code for i in run_lint(broken)]
    assert codes == ["L001", "L002", "L003", "L004"]
    counts = count_issues(run_lint(broken))
    assert (counts.errors, counts.warnings, counts.infos) == (2, 2, 0)
