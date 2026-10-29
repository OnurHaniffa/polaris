import datetime
from decimal import Decimal as D

import pytest
from django.db import transaction

from apps.core.audit import record, snapshot
from apps.core.models import AuditEvent
from apps.core.tests.factories import GradeFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_snapshot_is_json_safe():
    grade = GradeFactory(score=D("85.5"))
    snap = snapshot(grade, ["score", "is_excused", "assessment", "updated_at"])
    assert snap["score"] == "85.50" or snap["score"] == "85.5"
    assert snap["is_excused"] is False
    assert snap["assessment"] == grade.assessment_id
    datetime.datetime.fromisoformat(snap["updated_at"])  # parses: it's an ISO string


def test_record_stores_who_what_and_where():
    actor = UserFactory()
    grade = GradeFactory(score=D(75))
    event = record(
        actor,
        "grade.update",
        grade,
        before={"score": "75"},
        after={"score": "78"},
        offering=grade.assessment.offering,
    )
    assert event.entity_type == "grade"
    assert event.entity_id == grade.pk
    assert event.offering == grade.assessment.offering
    assert str(event) == f"grade.update grade#{grade.pk}"


def test_event_rolls_back_with_the_write():
    """Audit events are written in the caller's transaction (§5.3)."""
    grade = GradeFactory()
    with pytest.raises(RuntimeError), transaction.atomic():
        record(None, "grade.update", grade)
        raise RuntimeError("the service failed after recording")
    assert AuditEvent.objects.count() == 0
