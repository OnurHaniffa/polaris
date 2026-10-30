from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from hypothesis import given
from hypothesis import strategies as st

from apps.grading.services import parse_score_input

MAX = Decimal("100")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("85", (Decimal("85"), False)),
        ("85,5", (Decimal("85.5"), False)),  # Turkish decimal comma
        (" 85.50 ", (Decimal("85.50"), False)),
        ("0", (Decimal("0"), False)),  # a real zero is a grade, not "missing"
        ("100", (Decimal("100"), False)),  # exactly max is fine
        ("", (None, False)),
        ("   ", (None, False)),
        (None, (None, False)),
        ("EX", (None, True)),
        ("ex", (None, True)),
        ("M", (None, True)),
        ("excused", (None, True)),
    ],
)
def test_accepted_inputs(raw, expected):
    assert parse_score_input(raw, MAX) == expected


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("105", "over_max"),
        ("100.01", "over_max"),
        ("-1", "negative"),
        ("abc", "invalid"),
        ("NaN", "invalid"),
        ("Infinity", "invalid"),
        ("1e2", "invalid"),
        ("85.555", "invalid"),  # 3 decimals don't fit decimal_places=2
        ("8 5", "invalid"),
        ("85,5,1", "invalid"),
    ],
)
def test_rejected_inputs(raw, code):
    with pytest.raises(ValidationError) as exc:
        parse_score_input(raw, MAX)
    assert exc.value.code == code


def test_over_max_message_names_the_assessment():
    with pytest.raises(ValidationError) as exc:
        parse_score_input("105", Decimal("100.00"), label="Midterm I")
    assert exc.value.messages == ["Max for Midterm I is 100"]


@given(st.integers(min_value=0, max_value=10_000).map(lambda cents: Decimal(cents) / 100))
def test_round_trip_any_valid_score(value):
    """Whatever Decimal we print with a dot or a comma comes back unchanged."""
    text = format(value, "f")
    assert parse_score_input(text, MAX) == (value, False)
    assert parse_score_input(text.replace(".", ","), MAX) == (value, False)
