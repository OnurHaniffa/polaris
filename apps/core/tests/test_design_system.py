from decimal import Decimal as D

import pytest
from django.template import Context, Template
from django.test import RequestFactory

from apps.core.templatetags.polaris import pct, score, weight


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (D("86"), "86.0"),
        (D("84.95"), "85.0"),  # half-up, not banker's rounding
        (D("84.94"), "84.9"),
        (D("11600") / D("140"), "82.9"),
        (None, "—"),
        ("", "—"),
        ("not a number", "—"),
        (90, "90.0"),
    ],
)
def test_score_filter(value, expected):
    assert score(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(D("0.2857"), "29%"), (D("1"), "100%"), (D("0.005"), "1%"), (None, "—")]
)
def test_pct_filter(value, expected):
    assert pct(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(D("40.00"), "40"), (D("12.50"), "12.5"), (5, "5"), (None, "")]
)
def test_weight_filter(value, expected):
    assert weight(value) == expected


def test_query_transform_changes_one_key():
    request = RequestFactory().get("/department/", {"term": "2025F", "cohort": "2023"})
    out = Template("{% load polaris %}{% query_transform term='2026F' cohort=None %}").render(
        Context({"request": request})
    )
    assert out == "term=2026F"


@pytest.mark.parametrize(
    ("value", "css", "text"),
    [
        (D("86"), "pl-badge-ok", "86.0"),
        (D("59.94"), "pl-badge-low", "59.9"),
        (None, "pl-badge-none", "—"),
    ],
)
def test_score_badge_include(value, css, text):
    html = Template(
        '{% include "includes/score_badge.html" with value=v threshold=t only %}'
    ).render(Context({"v": value, "t": D("60")}))
    assert css in html
    assert text in html


def test_threshold_boundary_counts_as_attained():
    """P11: attains when score >= threshold."""
    html = Template(
        '{% include "includes/score_badge.html" with value=v threshold=t only %}'
    ).render(Context({"v": D("60"), "t": D("60")}))
    assert "pl-badge-ok" in html


def test_styleguide_only_in_debug(client, db, settings):
    settings.DEBUG = False
    assert client.get("/styleguide/").status_code == 404
    settings.DEBUG = True
    response = client.get("/styleguide/")
    assert response.status_code == 200
    assert b"85.0" in response.content
