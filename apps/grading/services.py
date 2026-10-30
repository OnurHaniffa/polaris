"""Writes for the grading app: draft grades (S2-06), publish and unpublish (S3-01)."""

from __future__ import annotations

import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.catalog.models import Enrollment, Term
from apps.catalog.services import ensure_term_open
from apps.core import audit

from .models import Grade

EXCUSED_WORDS = frozenset({"EX", "EXC", "EXCUSED", "M", "MUAF"})
_NUMBER = re.compile(r"^\d{1,5}(?:[.,]\d{1,2})?$")
GRADE_AUDIT_FIELDS = ("score", "is_excused")
CENT = Decimal("0.01")


def _plain(value: Decimal) -> str:
    """100.00 -> '100', 85.50 -> '85.5'. For messages only."""
    return format(value.normalize(), "f")


def parse_score_input(
    raw: str | None, max_score: Decimal, *, label: str = "this assessment"
) -> tuple[Decimal | None, bool]:
    """Turn what an instructor typed into (score, is_excused).

    ""          -> (None, False)   no grade
    "EX", "m"   -> (None, True)    excused (P6)
    "85,5"      -> (Decimal("85.5"), False)
    Raises ValidationError with a message a person can act on.
    """
    text = (raw or "").strip()
    if not text:
        return None, False
    if text.upper() in EXCUSED_WORDS:
        return None, True
    if text.startswith("-"):
        raise ValidationError("Scores can't be negative.", code="negative")
    if not _NUMBER.match(text):
        raise ValidationError(
            "Enter a number like 85 or 85,5 (at most 2 decimals), or EX for excused.",
            code="invalid",
        )
    value = Decimal(text.replace(",", "."))
    if value > max_score:
        raise ValidationError(f"Max for {label} is {_plain(max_score)}", code="over_max")
    return value, False


def _lock_open_term(offering) -> None:
    """Lock the offering's term row and refuse if it is closed.
    Must be called inside transaction.atomic()."""
    term = Term.objects.select_for_update(no_key=True).get(pk=offering.term_id)
    offering.term = term  # ensure_term_open reads offering.term.status
    ensure_term_open(offering)


def save_grade(user, assessment, enrollment, raw: str | None) -> Grade | None:
    """Save one draft grade from the grade sheet (B6).

    Writes Grade.score / Grade.is_excused only. Never touches published_score: students
    and every score calculation keep seeing the published value until the next publish (D2).
    Returns the grade, or None when the cell was blank and no grade existed (nothing to do).
    """
    if enrollment.offering_id != assessment.offering_id:
        raise ValidationError("This student is not enrolled in this course.", code="wrong_offering")
    if enrollment.status != Enrollment.Status.ENROLLED:
        raise ValidationError("This student has dropped the course.", code="dropped")
    score, is_excused = parse_score_input(raw, assessment.max_score, label=assessment.name)
    offering = assessment.offering

    with transaction.atomic():
        _lock_open_term(offering)
        grade = (
            Grade.objects.select_for_update()
            .filter(assessment=assessment, enrollment=enrollment)
            .first()
        )
        if grade is None:
            if score is None and not is_excused:
                return None  # blank cell, no grade: nothing to write
            grade = Grade(assessment=assessment, enrollment=enrollment)
            before = None
        else:
            if (grade.score, grade.is_excused) == (score, is_excused):
                return grade  # unchanged: no write, no audit noise
            before = audit.snapshot(grade, GRADE_AUDIT_FIELDS)

        # Same form as the column (decimal_places=2), so audit before/after read "75.00" alike.
        grade.score = None if score is None else score.quantize(CENT)
        grade.is_excused = is_excused
        grade.updated_by = user
        grade.save()
        audit.record(
            user,
            "grade.update",
            grade,
            before=before,
            after=audit.snapshot(grade, GRADE_AUDIT_FIELDS),
            offering=offering,
        )
    return grade
