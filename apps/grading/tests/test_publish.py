from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Enrollment, Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import (
    AssessmentFactory, EnrollmentFactory, GradeFactory, OfferingFactory, UserFactory,
)
from apps.core.tests.scenarios import elif_scenario
from apps.grading.models import Grade
from apps.grading.selectors import publish_preview
from apps.grading.services import publish_assessment, save_grade, unpublish_assessment
from apps.scoring.engine import compute_student_profile, display
from apps.scoring.loaders import load_student_inputs

pytestmark = pytest.mark.django_db


@pytest.fixture
def midterm():
    """4 enrolled students: two scores, one excused, one missing. Plus a dropped student."""
    offering = OfferingFactory(term__status=Term.Status.OPEN)
    a = AssessmentFactory(offering=offering, name="Midterm I", max_score=Decimal("100"))
    e1, e2, e3, _e4 = (EnrollmentFactory(offering=offering) for _ in range(4))
    GradeFactory(assessment=a, enrollment=e1, score=Decimal("90"))
    GradeFactory(assessment=a, enrollment=e2, score=Decimal("80"))
    GradeFactory(assessment=a, enrollment=e3, score=None, is_excused=True)
    dropped = EnrollmentFactory(offering=offering, status=Enrollment.Status.DROPPED)
    GradeFactory(assessment=a, enrollment=dropped, score=Decimal("10"))
    return a


def test_preview_counts_only_enrolled_students(midterm):
    p = publish_preview(midterm)
    assert (p.enrolled, p.graded, p.excused, p.missing, p.changes) == (4, 2, 1, 1, 3)
    assert p.is_first_publish and p.can_publish


def test_publish_copies_drafts_and_audits(midterm):
    user = UserFactory()
    result = publish_assessment(user, midterm, expected_changes=3)

    assert (result.published, result.excused, result.skipped_missing, result.changed) == (2, 1, 1, 3)
    for g in Grade.objects.filter(assessment=midterm):
        assert g.published_score == g.score
        assert g.published_is_excused == g.is_excused
        assert g.published_at is not None
        assert not g.has_unpublished_change
    midterm.refresh_from_db()
    assert midterm.published_at is not None and midterm.published_by == user

    event = AuditEvent.objects.get(action="assessment.publish")
    assert event.actor == user and event.entity_id == midterm.pk
    assert event.before["published_at"] is None
    assert event.after["published"] == 2 and event.after["skipped_missing"] == 1


def test_crash_after_update_publishes_nothing(midterm, monkeypatch):
    """B7 AC 2: a failure half-way leaves zero grades published."""
    def boom(*args, **kwargs):
        raise RuntimeError("audit table is on fire")

    monkeypatch.setattr("apps.core.audit.record", boom)    # runs AFTER the UPDATE in the service
    with pytest.raises(RuntimeError):
        publish_assessment(UserFactory(), midterm)

    assert not Grade.objects.filter(assessment=midterm, published_score__isnull=False).exists()
    assert not Grade.objects.filter(assessment=midterm, published_at__isnull=False).exists()
    midterm.refresh_from_db()
    assert midterm.published_at is None


def test_publish_locks_assessment_and_term_rows(midterm):
    with CaptureQueriesContext(connection) as ctx:
        publish_assessment(UserFactory(), midterm)
    sql = "\n".join(q["sql"] for q in ctx.captured_queries)
    assert 'FOR UPDATE OF "outcomes_assessment"' in sql
    assert "FOR NO KEY UPDATE" in sql


def test_edit_after_publish_is_a_draft_again(midterm):
    """B7 AC 3: editing a published grade changes nothing students see until re-publish."""
    user = UserFactory()
    publish_assessment(user, midterm)
    grade = Grade.objects.get(assessment=midterm, score=Decimal("90"))
    save_grade(user, midterm, grade.enrollment, "95")

    grade.refresh_from_db()
    assert grade.score == Decimal("95") and grade.published_score == Decimal("90")
    assert publish_preview(midterm).changes == 1

    publish_assessment(user, midterm, expected_changes=1)
    grade.refresh_from_db()
    assert grade.published_score == Decimal("95")


def test_nothing_new_to_publish(midterm):
    user = UserFactory()
    publish_assessment(user, midterm)
    with pytest.raises(ValidationError, match="Nothing new to publish"):
        publish_assessment(user, midterm)


def test_assessment_without_grades_cannot_be_published():
    offering = OfferingFactory(term__status=Term.Status.OPEN)
    a = AssessmentFactory(offering=offering)
    EnrollmentFactory(offering=offering)
    with pytest.raises(ValidationError, match="no grades to publish"):
        publish_assessment(UserFactory(), a)


def test_stale_confirmation_is_refused(midterm):
    """The modal showed 3 changes; someone typed another grade before Confirm."""
    user = UserFactory()
    missing = Enrollment.objects.filter(offering=midterm.offering, status=Enrollment.Status.ENROLLED,
                                        grades__isnull=True).get()
    save_grade(user, midterm, missing, "70")
    with pytest.raises(ValidationError, match="changed while the confirmation was open"):
        publish_assessment(user, midterm, expected_changes=3)
    assert not Grade.objects.filter(published_score__isnull=False).exists()


def test_closed_term_cannot_publish(midterm):
    Term.objects.filter(pk=midterm.offering.term_id).update(status=Term.Status.CLOSED)
    with pytest.raises(ValidationError):
        publish_assessment(UserFactory(), midterm)


def test_unpublish_hides_grades_keeps_drafts_and_records_reason(midterm):
    user = UserFactory()
    publish_assessment(user, midterm)
    hidden = unpublish_assessment(user, midterm, reason="Uploaded the wrong section's file")

    assert hidden == 4                         # every published row, including the dropped student
    for g in Grade.objects.filter(assessment=midterm):
        assert g.published_score is None and g.published_at is None
    assert Grade.objects.filter(assessment=midterm, score=Decimal("90")).exists()   # drafts kept
    event = AuditEvent.objects.get(action="assessment.unpublish")
    assert event.after["reason"] == "Uploaded the wrong section's file"
    midterm.refresh_from_db()
    assert midterm.published_at is None


@pytest.mark.parametrize("reason", ["", "   ", "oops"])
def test_unpublish_needs_a_reason(midterm, reason):
    user = UserFactory()
    publish_assessment(user, midterm)
    with pytest.raises(ValidationError):
        unpublish_assessment(user, midterm, reason=reason)


def test_unpublish_of_draft_assessment_is_refused(midterm):
    with pytest.raises(ValidationError, match="not published"):
        unpublish_assessment(UserFactory(), midterm, reason="Testing the guard")


# ---- what students and the engine see (policy P4) ----

def _po(profile, po):
    return display(profile.po_scores[po.id].score) if po.id in profile.po_scores else "—"


def test_scores_follow_publish_not_drafts():
    s = elif_scenario(published=False)
    user = UserFactory()

    before = compute_student_profile(load_student_inputs(s.student))
    assert (_po(before, s.po1), _po(before, s.po2)) == ("—", "—")        # B7 AC 1

    publish_assessment(user, s.midterm)
    publish_assessment(user, s.project)
    after = compute_student_profile(load_student_inputs(s.student))
    assert (_po(after, s.po1), _po(after, s.po2)) == ("85.0", "82.9")

    enrollment = Enrollment.objects.get(offering=s.offering, student=s.student)
    save_grade(user, s.midterm, enrollment, "50")                      # draft only
    unchanged = compute_student_profile(load_student_inputs(s.student))
    assert (_po(unchanged, s.po1), _po(unchanged, s.po2)) == ("85.0", "82.9")

    publish_assessment(user, s.midterm)
    # LO1 = (50·60 + 80·40)/100 = 62; LO2 = (50·40 + 80·100)/140 = 71.43
    # PO1 = (62·4 + 71.43·2)/6 = 65.14; PO2 = 71.43
    republished = compute_student_profile(load_student_inputs(s.student))
    assert (_po(republished, s.po1), _po(republished, s.po2)) == ("65.1", "71.4")


def test_unpublished_midterm_drops_out_of_scores():
    s = elif_scenario(published=False)
    user = UserFactory()
    publish_assessment(user, s.midterm)
    publish_assessment(user, s.project)
    unpublish_assessment(user, s.midterm, reason="Wrong answer key used")
    # Only the project (80) remains: LO1 = 80, LO2 = 80, so PO1 = PO2 = 80.0
    profile = compute_student_profile(load_student_inputs(s.student))
    assert (_po(profile, s.po1), _po(profile, s.po2)) == ("80.0", "80.0")