"""Pure tests: no database."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.http import QueryDict

from apps.outcomes.matrix import (
    A_LO,
    LO_PO,
    Cell,
    GridCell,
    GridCol,
    GridRow,
    WeightGrid,
    column_totals,
    fmt_weight,
    overlay_submitted,
    parse_cell_name,
    parse_matrix_post,
    validate_assessment_lo_cell,
    validate_lo_po_cell,
    version_of,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("60", Decimal("60")),
        (" 40 ", Decimal("40")),
        ("12,5", Decimal("12.5")),
        ("1", Decimal("1")),
        ("100", Decimal("100")),
        ("33.33", Decimal("33.33")),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_assessment_lo_accepts(raw, expected):
    assert validate_assessment_lo_cell(raw) == expected


@pytest.mark.parametrize(
    "raw, message",
    [
        ("0", "Leave the cell blank"),
        ("-0", "Leave the cell blank"),
        ("0.5", "between 1 and 100"),
        ("101", "between 1 and 100"),
        ("-5", "between 1 and 100"),
        ("1e400", "between 1 and 100"),
        ("abc", "Enter a number"),
        ("NaN", "Enter a number"),
        ("Infinity", "Enter a number"),
        ("12.345", "2 decimal places"),
    ],
)
def test_assessment_lo_rejects(raw, message):
    with pytest.raises(ValidationError) as exc:
        validate_assessment_lo_cell(raw)
    assert message in exc.value.messages[0]


@pytest.mark.parametrize(
    "raw, expected", [("1", 1), ("5", 5), (" 3 ", 3), ("", None), (None, None)]
)
def test_lo_po_accepts(raw, expected):
    assert validate_lo_po_cell(raw) == expected


@pytest.mark.parametrize(
    "raw, message",
    [
        ("0", "Leave the cell blank"),  # B5 AC2
        ("6", "whole number from 1 to 5"),  # B5 AC2
        ("2.5", "whole number from 1 to 5"),  # B5 AC2
        ("abc", "whole number from 1 to 5"),  # B5 AC2
        ("-1", "whole number from 1 to 5"),
        ("٣", "whole number from 1 to 5"),  # non-ASCII digit
    ],
)
def test_lo_po_rejects(raw, message):
    with pytest.raises(ValidationError) as exc:
        validate_lo_po_cell(raw)
    assert message in exc.value.messages[0]


def test_cell_names_round_trip():
    assert parse_cell_name("a_lo-12-34") == (A_LO, 12, 34)
    assert parse_cell_name("lo_po-3-11") == (LO_PO, 3, 11)
    for bad in ["a_lo-12", "a_lo-x-1", "zz-1-2", "a_lo-1-2-3", "lo_po--1-2", ""]:
        assert parse_cell_name(bad) is None


def test_parse_matrix_post_takes_only_its_grid():
    post = QueryDict(
        "a_lo-1-2=60&a_lo-1-3=&lo_po-2-9=4&version=abc&csrfmiddlewaretoken=t&a_lo-x-1=5"
    )
    cells = sorted(parse_matrix_post(post, A_LO), key=lambda c: (c.row_id, c.col_id))
    assert cells == [Cell(1, 2, "60"), Cell(1, 3, "")]
    assert parse_matrix_post(post, LO_PO) == [Cell(2, 9, "4")]


def test_fmt_weight():
    assert [fmt_weight(Decimal(x)) for x in ("60.00", "12.50", "100", "0.25")] == [
        "60",
        "12.5",
        "100",
        "0.25",
    ]
    assert fmt_weight(4) == "4"


def test_version_ignores_order_and_number_format():
    a = version_of([(1, 2, Decimal("60.00")), (1, 3, Decimal("40"))])
    b = version_of([(1, 3, Decimal("40.0")), (1, 2, Decimal("60"))])
    assert a == b
    assert a != version_of([(1, 2, Decimal("61")), (1, 3, Decimal("40"))])
    assert version_of([]) == version_of([])


def _grid():
    return WeightGrid(
        kind=LO_PO,
        caption="",
        cols=[GridCol("PO 1"), GridCol("PO 2")],
        rows=[
            GridRow(
                "LO 1",
                [
                    GridCell(
                        "lo_po-1-1", "4", "LO 1 to PO 1", origin="ai_suggested", rationale="r"
                    ),
                    GridCell("lo_po-1-2", "", "LO 1 to PO 2"),
                ],
            ),
            GridRow(
                "LO 2",
                [
                    GridCell("lo_po-2-1", "2", "LO 2 to PO 1"),
                    GridCell("lo_po-2-2", "5", "LO 2 to PO 2"),
                ],
            ),
        ],
    )


def test_column_totals_skip_blank_and_invalid():
    grid = _grid()
    grid.rows[1].cells[1].value = "abc"
    assert column_totals(grid) == ["6", "0"]


def test_overlay_shows_typed_values_and_errors():
    grid = overlay_submitted(
        _grid(),
        [Cell(1, 1, "4"), Cell(1, 2, "9")],
        {"lo_po-1-2": "Use a whole number from 1 to 5.", "lo_po-7-7": "Not in this course"},
    )
    first, second = grid.rows[0].cells
    assert (first.value, first.origin) == ("4", "ai_suggested")  # unchanged keeps its origin
    assert (second.value, second.error) == ("9", "Use a whole number from 1 to 5.")
    assert grid.form_errors == ["Not in this course"]  # cell not on the page
    assert grid.has_errors


def test_overlay_drops_origin_when_a_human_changes_the_value():
    grid = overlay_submitted(_grid(), [Cell(1, 1, "3")])
    cell = grid.rows[0].cells[0]
    assert (cell.value, cell.origin, cell.rationale) == ("3", "", "")
