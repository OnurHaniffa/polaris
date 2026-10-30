"""Reads for the setup and mapping pages. The decorator has already checked access."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.catalog.models import ProgramOutcomeSet
from apps.catalog.selectors import active_po_set

from .lint import (
    AssessmentInfo,
    LintCounts,
    LOInfo,
    LOPOLink,
    MappingSnapshot,
    count_issues,
    run_lint,
)
from .matrix import (
    A_LO,
    LO_PO,
    SOURCE_TO_ORIGIN,
    GridCell,
    GridCol,
    GridRow,
    WeightGrid,
    cell_name,
    column_totals,
    fmt_weight,
    version_of,
)
from .models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight

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


@dataclass
class MappingGrid:
    assessments: list  # Assessment objects, display order
    los: list  # LearningOutcome objects, by number
    pos: list  # ProgramOutcome objects of the active set, by number
    a_lo: dict  # (assessment_id, lo_id) -> Decimal weight
    lo_po: dict  # (lo_id, po_id) -> int weight (every LO→PO row, active set or not)
    a_lo_grid: WeightGrid
    lo_po_grid: WeightGrid

    def grid(self, kind: str) -> WeightGrid:
        return self.a_lo_grid if kind == A_LO else self.lo_po_grid


def mapping_grid(offering, *, validate_url: str = "") -> MappingGrid:
    assessments = list(offering.assessments.all())
    los = list(offering.learning_outcomes.all())
    try:
        pos = list(active_po_set(offering.course.program).outcomes.all())
    except ProgramOutcomeSet.DoesNotExist:
        pos = []
    a_lo_rows = list(AssessmentLOWeight.objects.filter(assessment__offering=offering))
    lo_po_rows = list(LOPOWeight.objects.filter(learning_outcome__offering=offering))
    a_lo = {(w.assessment_id, w.learning_outcome_id): w.weight for w in a_lo_rows}
    lo_po = {(w.learning_outcome_id, w.program_outcome_id): w.weight for w in lo_po_rows}
    lo_po_meta = {(w.learning_outcome_id, w.program_outcome_id): w for w in lo_po_rows}

    a_lo_grid = WeightGrid(
        kind=A_LO,
        caption="Assessment → LO weights (%). Blank = this assessment doesn't measure that LO.",
        cols=[GridCol(f"LO {lo.number}", lo.description) for lo in los],
        rows=[
            GridRow(
                label=a.name,
                tooltip=f"{a.get_kind_display()}, out of {fmt_weight(a.max_score)}",
                cells=[
                    GridCell(
                        name=cell_name(A_LO, a.pk, lo.pk),
                        value=fmt_weight(a_lo[(a.pk, lo.pk)]) if (a.pk, lo.pk) in a_lo else "",
                        label=f"{a.name} to LO {lo.number}",
                    )
                    for lo in los
                ],
            )
            for a in assessments
        ],
        footer_label="Total %",
        version=version_of((a_id, lo_id, w) for (a_id, lo_id), w in a_lo.items()),
        validate_url=validate_url,
        empty_message="Add assessments and learning outcomes on the Setup tab first.",
    )

    def lo_po_cell(lo, po):
        row = lo_po_meta.get((lo.pk, po.pk))
        return GridCell(
            name=cell_name(LO_PO, lo.pk, po.pk),
            value=str(row.weight) if row else "",
            label=f"LO {lo.number} to PO {po.number}",
            origin=SOURCE_TO_ORIGIN.get(row.source, "") if row else "",
            rationale=row.rationale if row else "",
        )

    lo_po_grid = WeightGrid(
        kind=LO_PO,
        caption="LO → PO weights (1–5). Blank = no contribution.",
        cols=[
            GridCol(f"PO {po.number}", f"PO {po.number} · {po.short_name}: {po.description}")
            for po in pos
        ],
        rows=[
            GridRow(
                label=f"LO {lo.number}",
                tooltip=lo.description,
                cells=[lo_po_cell(lo, po) for po in pos],
            )
            for lo in los
        ],
        footer_label="PO coverage",
        version=version_of((lo_id, po_id, w) for (lo_id, po_id), w in lo_po.items()),
        validate_url=validate_url,
        empty_message=(
            "Add learning outcomes on the Setup tab first."
            if pos
            else "This program has no active list of program outcomes. Ask the department head."
        ),
    )
    for grid in (a_lo_grid, lo_po_grid):
        grid.footer = column_totals(grid)
    return MappingGrid(
        assessments=assessments,
        los=los,
        pos=pos,
        a_lo=a_lo,
        lo_po=lo_po,
        a_lo_grid=a_lo_grid,
        lo_po_grid=lo_po_grid,
    )


def snapshot_mappings(offering_ids) -> dict[int, MappingSnapshot]:
    ids = list(offering_ids)
    parts = {i: {"assessments": [], "los": [], "a_lo": set(), "lo_po": []} for i in ids}

    for row in (
        Assessment.objects.filter(offering_id__in=ids)
        .order_by("offering_id", "position", "id")
        .values("id", "offering_id", "name", "course_weight")
    ):
        parts[row["offering_id"]]["assessments"].append(
            AssessmentInfo(row["id"], row["name"], row["course_weight"])
        )

    for row in (
        LearningOutcome.objects.filter(offering_id__in=ids)
        .order_by("offering_id", "number")
        .values("id", "offering_id", "number")
    ):
        parts[row["offering_id"]]["los"].append(LOInfo(row["id"], row["number"]))

    for offering_id, a_id, lo_id in AssessmentLOWeight.objects.filter(
        assessment__offering_id__in=ids
    ).values_list("assessment__offering_id", "assessment_id", "learning_outcome_id"):
        parts[offering_id]["a_lo"].add((a_id, lo_id))

    for offering_id, lo_id, lo_number, po_id, po_number, weight, source in (
        LOPOWeight.objects.filter(learning_outcome__offering_id__in=ids)
        .order_by("learning_outcome__number", "program_outcome__number")
        .values_list(
            "learning_outcome__offering_id",
            "learning_outcome_id",
            "learning_outcome__number",
            "program_outcome_id",
            "program_outcome__number",
            "weight",
            "source",
        )
    ):
        parts[offering_id]["lo_po"].append(
            LOPOLink(lo_id, lo_number, po_id, po_number, weight, source)
        )

    return {
        i: MappingSnapshot(
            assessments=tuple(p["assessments"]),
            los=tuple(p["los"]),
            assessment_lo=frozenset(p["a_lo"]),
            lo_po=tuple(p["lo_po"]),
        )
        for i, p in parts.items()
    }


def snapshot_mapping(offering) -> MappingSnapshot:
    return snapshot_mappings([offering.pk])[offering.pk]


def lint_counts(offering_ids) -> dict[int, LintCounts]:
    """Badge numbers for many courses (4 queries in total)."""
    return {
        offering_id: count_issues(run_lint(snap), empty=not snap.los)
        for offering_id, snap in snapshot_mappings(offering_ids).items()
    }
