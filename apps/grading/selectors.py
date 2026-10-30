"""Reads for the grading app."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from apps.catalog.models import Enrollment
from apps.outcomes.models import Assessment

from .models import Grade


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")


@dataclass(frozen=True)
class SheetCell:
    assessment: Assessment
    enrollment: Enrollment
    grade: Grade | None

    @property
    def input_value(self) -> str:
        """What the <input> shows: '85.5', 'EX' or ''."""
        if self.grade is None:
            return ""
        if self.grade.is_excused:
            return "EX"
        return "" if self.grade.score is None else _plain(self.grade.score)

    @property
    def is_excused(self) -> bool:
        return self.grade is not None and self.grade.is_excused

    @property
    def has_unpublished_change(self) -> bool:
        return self.grade is not None and self.grade.has_unpublished_change


@dataclass(frozen=True)
class SheetRow:
    enrollment: Enrollment
    cells: tuple[SheetCell, ...]


@dataclass(frozen=True)
class SheetColumn:
    assessment: Assessment
    unpublished: int  # grades whose draft differs from what students see
    graded: int  # grades with a score or excused

    @property
    def is_published(self) -> bool:
        return self.assessment.published_at is not None


@dataclass(frozen=True)
class GradeSheet:
    offering: object
    columns: tuple[SheetColumn, ...]
    rows: tuple[SheetRow, ...]
    grades: dict[tuple[int, int], Grade] = field(default_factory=dict)

    @property
    def assessments(self) -> list[Assessment]:
        return [c.assessment for c in self.columns]

    @property
    def students(self) -> list:
        return [r.enrollment.student for r in self.rows]

    @property
    def unpublished_counts(self) -> dict[int, int]:
        return {c.assessment.id: c.unpublished for c in self.columns}


def grade_sheet(offering) -> GradeSheet:
    """Everything the grade sheet shows, in exactly three queries."""
    enrollments = list(
        Enrollment.objects.filter(offering=offering, status=Enrollment.Status.ENROLLED)
        .select_related("student")
        .order_by("student__last_name", "student__first_name", "student__student_number")
    )  # query 1
    assessments = list(Assessment.objects.filter(offering=offering))  # query 2 (Meta ordering)
    grades = {
        (g.assessment_id, g.enrollment_id): g
        for g in Grade.objects.filter(
            assessment__offering=offering, enrollment__status=Enrollment.Status.ENROLLED
        )
    }  # query 3

    columns = []
    for a in assessments:
        col = [grades.get((a.id, e.id)) for e in enrollments]
        columns.append(
            SheetColumn(
                assessment=a,
                unpublished=sum(1 for g in col if g is not None and g.has_unpublished_change),
                graded=sum(
                    1 for g in col if g is not None and (g.score is not None or g.is_excused)
                ),
            )
        )
    rows = tuple(
        SheetRow(
            enrollment=e,
            cells=tuple(SheetCell(a, e, grades.get((a.id, e.id))) for a in assessments),
        )
        for e in enrollments
    )
    return GradeSheet(offering=offering, columns=tuple(columns), rows=rows, grades=grades)


def unpublished_changes(assessment) -> int:
    """How many enrolled students' grades on this assessment differ from the published value.
    One query. Used to refresh the column badge after a single cell save."""
    qs = Grade.objects.filter(assessment=assessment, enrollment__status=Enrollment.Status.ENROLLED)
    return sum(
        1
        for g in qs.only("score", "is_excused", "published_score", "published_is_excused")
        if g.has_unpublished_change
    )


def column_for(assessment) -> SheetColumn:
    """One column's header numbers (two counts, one query)."""
    qs = Grade.objects.filter(assessment=assessment, enrollment__status=Enrollment.Status.ENROLLED)
    grades = list(qs.only("score", "is_excused", "published_score", "published_is_excused"))
    return SheetColumn(
        assessment=assessment,
        unpublished=sum(1 for g in grades if g.has_unpublished_change),
        graded=sum(1 for g in grades if g.score is not None or g.is_excused),
    )
