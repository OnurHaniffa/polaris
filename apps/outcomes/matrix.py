"""The two weight grids (B5): cell names, validation, versions, and the plain
dataclasses that templates/includes/weight_grid.html renders. No database writes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

A_LO = "a_lo"  # assessment → LO, percent 1–100 (policy P1, decision D1)
LO_PO = "lo_po"  # LO → PO, whole number 1–5 (policy P2)
KINDS = (A_LO, LO_PO)

ONE = Decimal("1")
HUNDRED = Decimal("100")
CENT = Decimal("0.01")

ZERO_MESSAGE = "0 isn't a weight. Leave the cell blank for no link."
LO_PO_MESSAGE = "Use a whole number from 1 to 5."


# ---------- names and posted cells ----------


@dataclass(frozen=True)
class Cell:
    """One posted cell. `raw` is what the user typed, stripped; "" means no link."""

    row_id: int
    col_id: int
    raw: str


def cell_name(kind: str, row, col) -> str:
    return f"{kind}-{row}-{col}"


def parse_cell_name(name: str) -> tuple[str, int, int] | None:
    """'a_lo-12-34' -> ('a_lo', 12, 34). Anything else -> None."""
    parts = name.split("-")
    if len(parts) != 3 or parts[0] not in KINDS:
        return None
    kind, row, col = parts
    if not (row.isascii() and row.isdigit() and col.isascii() and col.isdigit()):
        return None
    return kind, int(row), int(col)


def parse_matrix_post(post, kind: str) -> list[Cell]:
    """Every cell of one grid from request.POST. Other fields (version, csrf) are ignored."""
    cells = []
    for name in post:
        parsed = parse_cell_name(name)
        if parsed is not None and parsed[0] == kind:
            cells.append(Cell(row_id=parsed[1], col_id=parsed[2], raw=post.get(name, "").strip()))
    return cells


# ---------- validation ----------


def validate_assessment_lo_cell(raw: str | None) -> Decimal | None:
    """Blank -> None (no link). Otherwise a Decimal in [1, 100] with at most 2 decimals."""
    text = (raw or "").strip().replace(",", ".")
    if text == "":
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValidationError("Enter a number, for example 40.", code="not_a_number") from None
    if not value.is_finite():
        raise ValidationError("Enter a number, for example 40.", code="not_a_number")
    if value == 0:
        raise ValidationError(ZERO_MESSAGE, code="zero")
    if value < ONE or value > HUNDRED:  # checked before quantize: 1e400 can't be quantized
        raise ValidationError("A weight must be between 1 and 100.", code="range")
    if value != value.quantize(CENT):
        raise ValidationError("Use at most 2 decimal places.", code="precision")
    return value


def validate_lo_po_cell(raw: str | None) -> int | None:
    """Blank -> None (no link). Otherwise an int in [1, 5]."""
    text = (raw or "").strip()
    if text == "":
        return None
    if not (text.isascii() and text.isdigit()):  # rejects "2.5", "-1", "abc", "٣"
        raise ValidationError(LO_PO_MESSAGE, code="not_integer")
    value = int(text)
    if value == 0:
        raise ValidationError(ZERO_MESSAGE, code="zero")
    if value > 5:
        raise ValidationError(LO_PO_MESSAGE, code="range")
    return value


VALIDATORS = {A_LO: validate_assessment_lo_cell, LO_PO: validate_lo_po_cell}


def fmt_weight(value) -> str:
    """Decimal('60.00') -> '60', Decimal('12.50') -> '12.5', 4 -> '4'."""
    return f"{Decimal(value).normalize():f}"


# ---------- versions (stale-edit detection) ----------


def version_of(triples) -> str:
    """Hash of (row_id, col_id, weight) triples. Order and number format don't matter:
    60 and 60.00 give the same version."""
    payload = ";".join(sorted(f"{r}:{c}:{fmt_weight(w)}" for r, c, w in triples))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def matrix_version(offering, kind: str) -> str:
    """The current version of one grid, read from the database."""
    from .models import (  # local: keep this module importable without apps
        AssessmentLOWeight,
        LOPOWeight,
    )

    if kind == A_LO:
        rows = AssessmentLOWeight.objects.filter(assessment__offering=offering).values_list(
            "assessment_id", "learning_outcome_id", "weight"
        )
    elif kind == LO_PO:
        rows = LOPOWeight.objects.filter(learning_outcome__offering=offering).values_list(
            "learning_outcome_id", "program_outcome_id", "weight"
        )
    else:
        raise ValueError(f"unknown grid kind {kind!r}")
    return version_of(rows)


# ---------- what the template renders ----------

#: LOPOWeight.source -> the cell's colour class. Manual and cloned cells are plain.
SOURCE_TO_ORIGIN = {"syllabus": "document", "ai_suggested": "ai_suggested"}


@dataclass
class GridCol:
    label: str  # "LO 2", "PO 3"
    tooltip: str = ""  # full description, shown on hover and keyboard focus


@dataclass
class GridCell:
    name: str  # the <input name>, unique in the form
    value: str  # what the input shows ("" = no link)
    label: str  # accessible name, e.g. "Midterm I to LO 2"
    error: str = ""
    origin: str = (
        ""  # "", "document", "derived", "ai_suggested" (colour + text mark); "manual" = plain
    )
    rationale: str = ""  # one sentence, shown on hover for AI-suggested cells


@dataclass
class GridRow:
    label: str
    cells: list[GridCell]
    tooltip: str = ""


@dataclass
class WeightGrid:
    kind: str  # A_LO or LO_PO
    caption: str
    cols: list[GridCol]
    rows: list[GridRow]
    footer: list[str] | None = None  # per-column totals
    footer_label: str = "Total"
    version: str = ""  # posted back as the hidden "version" field
    validate_url: str = ""  # set -> cells validate live over HTMX
    empty_message: str = ""
    form_errors: list[str] = field(default_factory=list)

    def all_cells(self):
        for row in self.rows:
            yield from row.cells

    @property
    def has_errors(self) -> bool:
        return bool(self.form_errors) or any(cell.error for cell in self.all_cells())

    @property
    def has_origins(self) -> bool:
        return any(cell.origin for cell in self.all_cells())


def column_totals(grid: WeightGrid) -> list[str]:
    """Sum of the valid values in each column. Invalid or blank cells count as nothing."""
    totals = [Decimal("0")] * len(grid.cols)
    validator = VALIDATORS[grid.kind]
    for row in grid.rows:
        for i, cell in enumerate(row.cells):
            try:
                value = validator(cell.value)
            except ValidationError:
                continue
            if value is not None:
                totals[i] += Decimal(value)
    return [fmt_weight(t) for t in totals]


def overlay_submitted(
    grid: WeightGrid, cells: list[Cell], errors: dict[str, str] | None = None
) -> WeightGrid:
    """Show what the user typed (and the errors) instead of the saved values, so a refused
    save never throws their work away. Mutates and returns `grid`. Errors for cells that
    aren't on the page, and the "__all__" key, go to grid.form_errors."""
    remaining = dict(errors or {})
    typed = {cell_name(grid.kind, c.row_id, c.col_id): c.raw for c in cells}
    for cell in grid.all_cells():
        if cell.name in typed and typed[cell.name] != cell.value:
            cell.value = typed[cell.name]
            cell.origin = ""  # a human changed it: no longer "from the document" / "AI"
            cell.rationale = ""
        cell.error = remaining.pop(cell.name, "")
    grid.form_errors.extend(remaining.values())
    grid.footer = column_totals(grid)
    return grid
