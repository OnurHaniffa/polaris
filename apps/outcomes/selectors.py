"""Reads for the setup and mapping pages. The decorator has already checked access."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import Assessment, LearningOutcome

HUNDRED = Decimal("100")


def _swap(ids: list[int], i: int, j: int) -> str:
    order = list(ids)
    order[i], order[j] = order[j], order[i]
    return ",".join(str(x) for x in order)


def setup_context(offering) -> dict:
    """Everything setup.html shows apart from the checklist."""
    los = list(offering.learning_outcomes.all())  # ordered by number (model Meta)
    ids = [lo.id for lo in los]
    lo_rows = [
        {
            "lo": lo,
            "up_order": _swap(ids, i, i - 1) if i > 0 else "",
            "down_order": _swap(ids, i, i + 1) if i < len(ids) - 1 else "",
        }
        for i, lo in enumerate(los)
    ]
    assessments = list(offering.assessments.all())  # ordered by position, id
    weights = [a.course_weight for a in assessments if a.course_weight is not None]
    total = sum(weights, Decimal("0"))
    return {
        "lo_rows": lo_rows,
        "assessments": assessments,
        "course_weight_total": total if weights else None,
        "course_weight_ok": not weights or total == HUNDRED,
        "missing_course_weight": sum(1 for a in assessments if a.course_weight is None),
    }


@dataclass(frozen=True)
class DeletionImpact:
    """What the delete confirmation lists (B4 AC3). `blocked_reason` set = the delete is refused."""

    title: str
    lines: tuple[str, ...]
    blocked_reason: str = ""


def _names(values, limit=6) -> str:
    values = list(values)
    shown = ", ".join(values[:limit])
    return shown + (f" and {len(values) - limit} more" if len(values) > limit else "")


def lo_deletion_impact(lo: LearningOutcome) -> DeletionImpact:
    a_names = list(
        lo.assessment_weights.order_by("assessment__position").values_list(
            "assessment__name", flat=True
        )
    )
    po_numbers = list(
        lo.po_weights.order_by("program_outcome__number").values_list(
            "program_outcome__number", flat=True
        )
    )
    lines = []
    if a_names:
        lines.append(
            f"{len(a_names)} assessment → LO weight{'s' if len(a_names) != 1 else ''} "
            f"({_names(a_names)})"
        )
    if po_numbers:
        lines.append(
            f"{len(po_numbers)} LO → PO weight{'s' if len(po_numbers) != 1 else ''} "
            f"({_names(f'PO {n}' for n in po_numbers)})"
        )
    later = lo.offering.learning_outcomes.filter(number__gt=lo.number).count()
    if later:
        lines.append(
            f"LO {lo.number + 1}{'–' + str(lo.number + later) if later > 1 else ''} "
            f"will be renumbered to close the gap"
        )
    return DeletionImpact(title=f"Delete LO {lo.number}?", lines=tuple(lines))


def assessment_deletion_impact(assessment: Assessment) -> DeletionImpact:
    if (
        assessment.published_at is not None
        or assessment.grades.filter(published_score__isnull=False).exists()
    ):
        return DeletionImpact(
            title=f"{assessment.name} can't be deleted",
            lines=(),
            blocked_reason=(
                f"{assessment.name} has published grades. Unpublish it on the Grades tab first."
            ),
        )
    lo_numbers = list(
        assessment.lo_weights.order_by("learning_outcome__number").values_list(
            "learning_outcome__number", flat=True
        )
    )
    drafts = assessment.grades.filter(score__isnull=False).count()
    lines = []
    if lo_numbers:
        lines.append(
            f"{len(lo_numbers)} assessment → LO weight{'s' if len(lo_numbers) != 1 else ''} "
            f"({_names(f'LO {n}' for n in lo_numbers)})"
        )
    if drafts:
        lines.append(f"{drafts} draft grade{'s' if drafts != 1 else ''} (never published)")
    return DeletionImpact(title=f"Delete {assessment.name}?", lines=tuple(lines))
