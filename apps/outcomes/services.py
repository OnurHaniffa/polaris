"""Every write to learning outcomes, assessments and the two weight matrices.

Rules (spec §4.4, §5.3): one transaction per call, closed terms refused, and an
AuditEvent written in the same transaction as the change.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Max, Q

from apps.catalog.models import CourseOffering
from apps.catalog.services import ensure_term_open
from apps.core.audit import record, snapshot

from .matrix import (
    A_LO,
    LO_PO,
    Cell,
    cell_name,
    fmt_weight,
    matrix_version,
    validate_assessment_lo_cell,
    validate_lo_po_cell,
)
from .models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight, Source

LO_FIELDS = ["number", "description", "source"]
ASSESSMENT_FIELDS = ["name", "kind", "max_score", "course_weight", "due_date", "position"]
EDITABLE_ASSESSMENT_FIELDS = frozenset({"name", "kind", "max_score", "course_weight", "due_date"})
RENUMBER_OFFSET = 1000


def _lock_offering(offering: CourseOffering) -> CourseOffering:
    """Lock this offering's row until the transaction ends (spec §5.6) and return a fresh copy."""
    return (
        CourseOffering.objects.select_for_update(of=("self",))
        .select_related("term", "course__program")
        .get(pk=offering.pk)
    )


# ---------- learning outcomes ----------


def create_lo(user, offering, *, description, source=Source.MANUAL) -> LearningOutcome:
    with transaction.atomic():
        offering = _lock_offering(offering)
        ensure_term_open(offering)
        last = offering.learning_outcomes.aggregate(m=Max("number"))["m"] or 0
        lo = LearningOutcome.objects.create(
            offering=offering,
            number=last + 1,
            description=description.strip(),
            source=source,
        )
        record(user, "lo.create", lo, after=snapshot(lo, LO_FIELDS), offering=offering)
        return lo


def update_lo(user, lo, *, description) -> LearningOutcome:
    with transaction.atomic():
        offering = _lock_offering(lo.offering)
        ensure_term_open(offering)
        lo = LearningOutcome.objects.get(pk=lo.pk, offering=offering)
        before = snapshot(lo, LO_FIELDS)
        lo.description = description.strip()
        lo.save(update_fields=["description"])
        record(
            user, "lo.update", lo, before=before, after=snapshot(lo, LO_FIELDS), offering=offering
        )
        return lo


def _renumber(offering, ordered_ids: list[int]) -> None:
    """Give the offering's LOs the numbers 1..n in `ordered_ids` order (two-phase, see above)."""
    by_id = {lo.id: lo for lo in LearningOutcome.objects.filter(offering=offering)}
    LearningOutcome.objects.filter(offering=offering).update(number=F("number") + RENUMBER_OFFSET)
    for position, lo_id in enumerate(ordered_ids, start=1):
        by_id[lo_id].number = position
    LearningOutcome.objects.bulk_update([by_id[i] for i in ordered_ids], ["number"])


def delete_lo(user, lo) -> None:
    """Delete an LO and both kinds of weight attached to it, then close the gap in numbering.
    The audit event stores the weights that disappeared, so the history can explain a
    changed PO score later."""
    with transaction.atomic():
        offering = _lock_offering(lo.offering)
        ensure_term_open(offering)
        lo = LearningOutcome.objects.get(pk=lo.pk, offering=offering)
        before = snapshot(lo, LO_FIELDS)
        before["assessment_weights"] = {
            str(a_id): str(w)
            for a_id, w in lo.assessment_weights.values_list("assessment_id", "weight")
        }
        before["po_weights"] = {
            str(po_id): w for po_id, w in lo.po_weights.values_list("program_outcome_id", "weight")
        }
        record(
            user, "lo.delete", lo, before=before, offering=offering
        )  # before delete(): needs lo.pk
        lo.delete()  # CASCADE removes AssessmentLOWeight and LOPOWeight rows
        remaining = list(
            LearningOutcome.objects.filter(offering=offering)
            .order_by("number")
            .values_list("id", flat=True)
        )
        _renumber(offering, remaining)


def reorder_los(user, offering, ordered_ids: list[int]) -> None:
    """`ordered_ids` must contain every LO of the offering exactly once. A different set
    means the page was stale (someone added or deleted an LO in another tab)."""
    with transaction.atomic():
        offering = _lock_offering(offering)
        ensure_term_open(offering)
        current = dict(
            LearningOutcome.objects.filter(offering=offering).values_list("id", "number")
        )
        if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(current):
            raise ValidationError(
                "The list of outcomes changed while you were editing. Reload and try again.",
                code="stale",
            )
        before = {str(i): current[i] for i in sorted(current)}
        _renumber(offering, ordered_ids)
        after = {str(i): n for n, i in enumerate(ordered_ids, start=1)}
        if before != {k: after[k] for k in before}:
            record(
                user,
                "lo.reorder",
                offering,
                before={"numbers": before},
                after={"numbers": after},
                offering=offering,
            )


# apps/outcomes/services.py  (continued)


def _check_unique_name(offering, name: str, *, exclude_pk=None) -> None:
    qs = offering.assessments.filter(name__iexact=name)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise ValidationError(
            {"name": f"There is already an assessment called “{name}” in this course."}
        )


def _check_fields(fields: dict) -> None:
    unknown = set(fields) - EDITABLE_ASSESSMENT_FIELDS
    if unknown:
        raise TypeError(f"Not editable through this service: {sorted(unknown)}")


def create_assessment(user, offering, **fields) -> Assessment:
    _check_fields(fields)
    with transaction.atomic():
        offering = _lock_offering(offering)
        ensure_term_open(offering)
        _check_unique_name(offering, fields["name"])
        last = offering.assessments.aggregate(m=Max("position"))["m"] or 0
        assessment = Assessment.objects.create(offering=offering, position=last + 1, **fields)
        record(
            user,
            "assessment.create",
            assessment,
            after=snapshot(assessment, ASSESSMENT_FIELDS),
            offering=offering,
        )
        return assessment


def update_assessment(user, assessment, *, confirm_max_change=False, **fields) -> Assessment:
    _check_fields(fields)
    with transaction.atomic():
        offering = _lock_offering(assessment.offering)
        ensure_term_open(offering)
        # Re-read inside the lock: the caller's object may be stale or already modified in memory.
        assessment = Assessment.objects.select_for_update().get(pk=assessment.pk, offering=offering)
        before = snapshot(assessment, ASSESSMENT_FIELDS)

        if "name" in fields and fields["name"] != assessment.name:
            _check_unique_name(offering, fields["name"], exclude_pk=assessment.pk)

        new_max = fields.get("max_score", assessment.max_score)
        if new_max != assessment.max_score:
            graded = assessment.grades.filter(
                Q(score__isnull=False) | Q(published_score__isnull=False)
            )
            if graded.exists():
                if not confirm_max_change:
                    raise ValidationError(
                        f"{assessment.name} already has grades. Changing the maximum from "
                        f"{assessment.max_score.normalize():f} to {new_max.normalize():f} "
                        "changes every "
                        "student's converted score for it, including published ones.",
                        code="confirm_max_change",
                    )
                over = graded.filter(Q(score__gt=new_max) | Q(published_score__gt=new_max)).count()
                if over:
                    raise ValidationError(
                        {
                            "max_score": (
                                f"{over} grade{'s are' if over != 1 else ' is'} "
                                f"above {new_max.normalize():f}. "
                                "Fix those grades first, or choose a higher maximum."
                            )
                        }
                    )

        for name, value in fields.items():
            setattr(assessment, name, value)
        assessment.save()
        after = snapshot(assessment, ASSESSMENT_FIELDS)
        if after != before:
            record(
                user, "assessment.update", assessment, before=before, after=after, offering=offering
            )
        return assessment


def delete_assessment(user, assessment) -> None:
    with transaction.atomic():
        offering = _lock_offering(assessment.offering)
        ensure_term_open(offering)
        assessment = Assessment.objects.select_for_update().get(pk=assessment.pk, offering=offering)
        published = assessment.grades.filter(
            Q(published_at__isnull=False) | Q(published_score__isnull=False)
        ).exists()
        if assessment.published_at is not None or published:
            raise ValidationError(
                f"{assessment.name} has published grades, so it can't be deleted. "
                "Unpublish it on the Grades tab first; the unpublish is recorded in the history.",
                code="published",
            )
        before = snapshot(assessment, ASSESSMENT_FIELDS)
        before["lo_weights"] = {
            str(lo_id): str(w)
            for lo_id, w in assessment.lo_weights.values_list("learning_outcome_id", "weight")
        }
        before["draft_grades"] = assessment.grades.filter(score__isnull=False).count()
        record(user, "assessment.delete", assessment, before=before, offering=offering)
        assessment.delete()  # CASCADE removes its AssessmentLOWeight rows and draft Grade rows


STALE_MESSAGE = (
    "This mapping changed since you opened it. Someone else saved it in the meantime. "
    "Reload to see their version, then make your change again."
)
FOREIGN_CELL_MESSAGE = "This cell isn't part of this course's mapping any more. Reload the page."


@dataclass(frozen=True)
class MatrixSaveResult:
    created: int
    updated: int
    deleted: int

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated or self.deleted)


def _check_version(offering, kind: str, expected: str) -> None:
    if matrix_version(offering, kind) != expected:
        raise ValidationError(STALE_MESSAGE, code="stale")


def _validated_cells(kind, cells: list[Cell], row_ids: set[int], col_ids: set[int], validator):
    """-> (wanted {(row, col): value}, posted {(row, col)}). Raises one ValidationError
    listing every bad cell, so the user sees all problems at once."""
    errors: dict[str, str] = {}
    wanted: dict[tuple[int, int], object] = {}
    posted: set[tuple[int, int]] = set()
    for c in cells:
        name = cell_name(kind, c.row_id, c.col_id)
        if c.row_id not in row_ids or c.col_id not in col_ids:
            errors[name] = FOREIGN_CELL_MESSAGE
            continue
        try:
            value = validator(c.raw)
        except ValidationError as exc:
            errors[name] = exc.messages[0]
            continue
        posted.add((c.row_id, c.col_id))
        if value is not None:
            wanted[(c.row_id, c.col_id)] = value
    if errors:
        raise ValidationError(errors)
    return wanted, posted


def _as_audit(rows) -> dict[str, str]:
    """{(row, col): weight} -> {"row:col": "60"} (JSON-safe, stable formatting)."""
    return {f"{r}:{c}": fmt_weight(w) for (r, c), w in sorted(rows.items())}


def save_assessment_lo_matrix(
    user, offering, cells: list[Cell], *, expected_version: str
) -> MatrixSaveResult:
    with transaction.atomic():
        offering = _lock_offering(offering)
        ensure_term_open(offering)
        _check_version(offering, A_LO, expected_version)
        wanted, posted = _validated_cells(
            A_LO,
            cells,
            row_ids=set(offering.assessments.values_list("id", flat=True)),
            col_ids=set(offering.learning_outcomes.values_list("id", flat=True)),
            validator=validate_assessment_lo_cell,
        )
        existing = {
            (w.assessment_id, w.learning_outcome_id): w
            for w in AssessmentLOWeight.objects.filter(assessment__offering=offering)
        }
        before = _as_audit({k: w.weight for k, w in existing.items()})

        to_create, to_update, to_delete = [], [], []
        for key in posted:
            current, value = existing.get(key), wanted.get(key)
            if value is None:
                if current is not None:
                    to_delete.append(current.pk)
            elif current is None:
                to_create.append(
                    AssessmentLOWeight(
                        assessment_id=key[0], learning_outcome_id=key[1], weight=value
                    )
                )
            elif current.weight != value:  # Decimal: 60.00 == 60, so no false updates
                current.weight = value
                to_update.append(current)

        AssessmentLOWeight.objects.filter(pk__in=to_delete).delete()
        AssessmentLOWeight.objects.bulk_create(to_create)
        AssessmentLOWeight.objects.bulk_update(to_update, ["weight"])
        result = MatrixSaveResult(len(to_create), len(to_update), len(to_delete))

        if result.changed:
            after = _as_audit(
                {
                    (w.assessment_id, w.learning_outcome_id): w.weight
                    for w in AssessmentLOWeight.objects.filter(assessment__offering=offering)
                }
            )
            record(
                user,
                "assessment_lo.update",
                offering,
                before={"cells": before},
                after={"cells": after},
                offering=offering,
            )
        return result


def save_lo_po_matrix(
    user, offering, cells: list[Cell], *, expected_version: str
) -> MatrixSaveResult:
    """Like the assessment grid, plus provenance: a cell whose value a human changes becomes
    source=MANUAL with no rationale. Unchanged cells keep their source (lint L007 needs that)."""
    from apps.catalog.selectors import active_po_set

    with transaction.atomic():
        offering = _lock_offering(offering)
        ensure_term_open(offering)
        _check_version(offering, LO_PO, expected_version)
        po_ids = set(active_po_set(offering.course.program).outcomes.values_list("id", flat=True))
        wanted, posted = _validated_cells(
            LO_PO,
            cells,
            row_ids=set(offering.learning_outcomes.values_list("id", flat=True)),
            col_ids=po_ids,
            validator=validate_lo_po_cell,
        )
        existing = {
            (w.learning_outcome_id, w.program_outcome_id): w
            for w in LOPOWeight.objects.filter(learning_outcome__offering=offering)
        }
        before = _as_audit({k: w.weight for k, w in existing.items()})

        to_create, to_update, to_delete = [], [], []
        for key in posted:
            current, value = existing.get(key), wanted.get(key)
            if value is None:
                if current is not None:
                    to_delete.append(current.pk)
            elif current is None:
                to_create.append(
                    LOPOWeight(
                        learning_outcome_id=key[0],
                        program_outcome_id=key[1],
                        weight=value,
                        source=Source.MANUAL,
                    )
                )
            elif current.weight != value:
                current.weight, current.source, current.rationale = value, Source.MANUAL, ""
                to_update.append(current)

        LOPOWeight.objects.filter(pk__in=to_delete).delete()
        LOPOWeight.objects.bulk_create(to_create)
        LOPOWeight.objects.bulk_update(to_update, ["weight", "source", "rationale"])
        result = MatrixSaveResult(len(to_create), len(to_update), len(to_delete))

        if result.changed:
            after = _as_audit(
                {
                    (w.learning_outcome_id, w.program_outcome_id): w.weight
                    for w in LOPOWeight.objects.filter(learning_outcome__offering=offering)
                }
            )
            record(
                user,
                "lo_po.update",
                offering,
                before={"cells": before},
                after={"cells": after},
                offering=offering,
            )
        return result
