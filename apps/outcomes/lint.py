"""Mapping lint (spec B11). Pure functions over a MappingSnapshot: no Django, no database.
Each rule returns a list of LintIssue. run_lint runs them all, errors first."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ERROR, WARNING, INFO = "error", "warning", "info"
SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}

AI_SUGGESTED = "ai_suggested"  # == outcomes.models.Source.AI_SUGGESTED (checked by a test)
OVERCLAIM_SHARE = Decimal("0.60")  # L005: more than this share of the course's LO→PO weight
MIN_LINKED_POS = 2  # L006
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class LintIssue:
    code: str  # "L001"
    severity: str  # ERROR / WARNING / INFO
    message: str  # one plain sentence (or two)
    target: str = ""  # what it's about: "LO 3", "Quiz 1", "PO 2", "Assessments", "LO → PO"


@dataclass(frozen=True)
class AssessmentInfo:
    id: int
    name: str
    course_weight: Decimal | None


@dataclass(frozen=True)
class LOInfo:
    id: int
    number: int


@dataclass(frozen=True)
class LOPOLink:
    lo_id: int
    lo_number: int
    po_id: int
    po_number: int
    weight: int
    source: str


@dataclass(frozen=True)
class MappingSnapshot:
    """Everything lint needs about one offering's mapping, as plain values."""

    assessments: tuple[AssessmentInfo, ...] = ()
    los: tuple[LOInfo, ...] = ()
    assessment_lo: frozenset[tuple[int, int]] = frozenset()  # (assessment_id, lo_id) with a weight
    lo_po: tuple[LOPOLink, ...] = ()


def _fmt(value: Decimal) -> str:
    return f"{value.normalize():f}"


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


# ---------- the rules ----------


def l001_unassessed_lo(snap: MappingSnapshot) -> list[LintIssue]:
    measured = {lo_id for _, lo_id in snap.assessment_lo}
    return [
        LintIssue(
            "L001",
            ERROR,
            f"LO {lo.number} isn't measured by any assessment, "
            "so its score can never be calculated.",
            f"LO {lo.number}",
        )
        for lo in snap.los
        if lo.id not in measured
    ]


def l002_unlinked_lo(snap: MappingSnapshot) -> list[LintIssue]:
    linked = {link.lo_id for link in snap.lo_po}
    return [
        LintIssue(
            "L002",
            ERROR,
            f"LO {lo.number} isn't linked to any program outcome, so it adds nothing to PO scores.",
            f"LO {lo.number}",
        )
        for lo in snap.los
        if lo.id not in linked
    ]


def l003_unused_assessment(snap: MappingSnapshot) -> list[LintIssue]:
    used = {a_id for a_id, _ in snap.assessment_lo}
    return [
        LintIssue(
            "L003",
            WARNING,
            f"{a.name} doesn't feed any learning outcome, "
            "so its grades are ignored by every score.",
            a.name,
        )
        for a in snap.assessments
        if a.id not in used
    ]


def l004_course_weights(snap: MappingSnapshot) -> list[LintIssue]:
    weights = [a.course_weight for a in snap.assessments if a.course_weight is not None]
    if not weights:
        return []  # course weights are optional; none at all is fine
    total = sum(weights, Decimal("0"))
    if total == HUNDRED:
        return []
    message = f"Course weights add up to {_fmt(total)}%, not 100%."
    missing = sum(1 for a in snap.assessments if a.course_weight is None)
    if missing:
        message += (
            f" {missing} {_plural(missing, 'assessment has', 'assessments have')} no course weight."
        )
    return [LintIssue("L004", WARNING, message, "Assessments")]


def l005_overclaimed_po(snap: MappingSnapshot) -> list[LintIssue]:
    per_po: dict[int, int] = defaultdict(int)
    number: dict[int, int] = {}
    for link in snap.lo_po:
        per_po[link.po_id] += link.weight
        number[link.po_id] = link.po_number
    total = sum(per_po.values())
    if total == 0:
        return []
    issues = []
    for po_id in sorted(per_po, key=number.__getitem__):
        share = Decimal(per_po[po_id]) / Decimal(total)
        if share > OVERCLAIM_SHARE:
            pct = _fmt((share * HUNDRED).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
            issues.append(
                LintIssue(
                    "L005",
                    WARNING,
                    f"PO {number[po_id]} receives {pct}% of this course's LO → PO weight. "
                    "Check that the course really focuses this much on one outcome.",
                    f"PO {number[po_id]}",
                )
            )
    return issues


def l006_few_pos(snap: MappingSnapshot) -> list[LintIssue]:
    linked = {link.po_id for link in snap.lo_po}
    if not linked or len(linked) >= MIN_LINKED_POS:
        return []  # no links at all is L002's job
    return [
        LintIssue(
            "L006",
            INFO,
            "This course links to only 1 program outcome. Most courses support two or more.",
            "LO → PO",
        )
    ]


def l007_unconfirmed_ai(snap: MappingSnapshot) -> list[LintIssue]:
    n = sum(1 for link in snap.lo_po if link.source == AI_SUGGESTED)
    if not n:
        return []
    return [
        LintIssue(
            "L007",
            WARNING,
            f"{n} LO → PO {_plural(n, 'weight', 'weights')} suggested by AI "
            f"{_plural(n, 'has', 'have')} not been checked by a person. "
            "Edit them, or use “Accept all suggestions”.",
            "LO → PO",
        )
    ]


RULES = (
    l001_unassessed_lo,
    l002_unlinked_lo,
    l003_unused_assessment,
    l004_course_weights,
    l005_overclaimed_po,
    l006_few_pos,
    l007_unconfirmed_ai,
)


def run_lint(snap: MappingSnapshot) -> list[LintIssue]:
    issues = [issue for rule in RULES for issue in rule(snap)]
    return sorted(
        issues, key=lambda i: (SEVERITY_ORDER[i.severity], i.code)
    )  # stable: keeps rule order


# ---------- counts for badges ----------


@dataclass(frozen=True)
class LintCounts:
    errors: int
    warnings: int
    infos: int
    empty: bool  # the course has no LOs yet: "not set up", not "mapping OK"


def count_issues(issues: list[LintIssue], *, empty: bool = False) -> LintCounts:
    return LintCounts(
        errors=sum(1 for i in issues if i.severity == ERROR),
        warnings=sum(1 for i in issues if i.severity == WARNING),
        infos=sum(1 for i in issues if i.severity == INFO),
        empty=empty,
    )
