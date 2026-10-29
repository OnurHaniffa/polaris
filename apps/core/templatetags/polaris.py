"""Template filters every page uses. Load with {% load polaris %}.

The |score filter is the ONLY way a score is printed (spec §8.2, policy P7): one decimal,
half-up, and an em dash for "no evidence". It reuses engine.display so the rounding rule
lives in exactly one place."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

from apps.scoring.engine import display

register = template.Library()


def _to_decimal(value):
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


@register.filter
def score(value):
    """86 → "86.0", Decimal("84.95") → "85.0", None → "—"."""
    return display(_to_decimal(value))


@register.filter
def pct(value):
    """A 0..1 share as a whole percentage: Decimal("0.2857") → "29%", None → "—"."""
    value = _to_decimal(value)
    if value is None:
        return "—"
    return f"{(value * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)}%"


@register.filter
def weight(value):
    """A weight without trailing zeros: Decimal("40.00") → "40", Decimal("12.50") → "12.5"."""
    value = _to_decimal(value)
    if value is None:
        return ""
    text = format(value.normalize(), "f")
    return text


@register.simple_tag(takes_context=True)
def query_transform(context, **changes):
    """Rebuild the current query string with some keys changed, for filter links:
    <a href="?{% query_transform term='2026F' %}">. A value of None removes the key."""
    params = context["request"].GET.copy()
    for key, value in changes.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()
