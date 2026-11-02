from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.db.models import F

from apps.accounts.models import User
from apps.catalog.models import Course, CourseOffering, Enrollment, Program, Term
from apps.catalog.selectors import active_po_set
from apps.grading.models import Grade
from apps.outcomes.models import AssessmentLOWeight, LearningOutcome, LOPOWeight
from apps.scoring.engine import compute_student_profile, display
from apps.scoring.loaders import load_student_inputs

pytestmark = pytest.mark.django_db


def seed(*flags):
    out = StringIO()
    call_command("seed_demo", "--small", *flags, stdout=out)
    return out.getvalue()


@pytest.fixture
def seeded(settings):
    settings.DEBUG = True
    return seed()


def test_elif_reproduces_the_slide(seeded):
    elif_user = User.objects.get(email="elif.yildiz@polaris.test")
    profile = compute_student_profile(load_student_inputs(elif_user))
    pos = {po.number: po for po in active_po_set(Program.objects.get(code="CSE")).outcomes.all()}
    assert display(profile.po_scores[pos[1].id].score) == "85.0"
    assert display(profile.po_scores[pos[2].id].score) == "82.9"


def test_shape_of_the_department(seeded):
    assert Term.objects.count() == 3
    assert Course.objects.count() == 12
    assert CourseOffering.objects.count() == 15
    students = User.objects.filter(memberships__role="student").distinct()
    assert students.count() == 31  # 3 cohorts × 10 + Elif
    assert "Elif Yıldız" in seeded and "student-demo-311" in seeded


def test_deliberate_flaws_are_present(seeded):
    active = active_po_set(Program.objects.get(code="CSE"))
    # PO 11 linked by no course
    assert not LOPOWeight.objects.filter(program_outcome__po_set=active, program_outcome__number=11).exists()
    # PO 9 covered by exactly one course
    po9_courses = set(
        LOPOWeight.objects.filter(program_outcome__number=9).values_list("learning_outcome__offering__course__code", flat=True)
    )
    assert po9_courses == {"CSE 341"}
    # one Fall 2026 offering with LOs and assessments but no mapping
    unmapped = CourseOffering.objects.get(course__code="CSE 221", term__code="2026F")
    assert LearningOutcome.objects.filter(offering=unmapped).exists()
    assert unmapped.assessments.exists()
    assert not AssessmentLOWeight.objects.filter(assessment__offering=unmapped).exists()
    assert not LOPOWeight.objects.filter(learning_outcome__offering=unmapped).exists()
    # exactly one grade with an unpublished change
    changed = Grade.objects.filter(assessment__published_at__isnull=False, score__isnull=False).exclude(
        score=F("published_score")
    )
    assert changed.count() == 1


def test_retakers_are_in_both_cse101_offerings(seeded):
    old = CourseOffering.objects.get(course__code="CSE 101", term__code="2025F")
    retake = CourseOffering.objects.get(course__code="CSE 101", term__code="2026F")
    retakers = set(Enrollment.objects.filter(offering=retake).values_list("student_id", flat=True))
    assert len(retakers) == 3
    assert retakers <= set(Enrollment.objects.filter(offering=old).values_list("student_id", flat=True))


def test_grades_are_valid(seeded):
    assert not Grade.objects.filter(score__gt=F("assessment__max_score")).exists()
    assert not Grade.objects.filter(score__lt=0).exists()
    assert not Grade.objects.exclude(assessment__offering=F("enrollment__offering")).exists()
    total = Grade.objects.count()
    excused = Grade.objects.filter(is_excused=True).count()
    assert 0 < excused < total * 0.06  # about 2%


def _fingerprint():
    return list(
        Grade.objects.order_by(
            "enrollment__student__student_number",
            "assessment__offering__term__code",
            "assessment__offering__course__code",
            "assessment__position",
        ).values_list(
            "enrollment__student__student_number",
            "assessment__offering__course__code",
            "assessment__name",
            "score",
            "is_excused",
        )
    )


def test_same_seed_same_data(seeded):
    first = _fingerprint()
    seed("--reset")
    assert _fingerprint() == first


def test_second_run_without_reset_is_refused(seeded):
    with pytest.raises(CommandError, match="already exists"):
        seed()


def test_refuses_when_debug_is_false(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG is False"):
        seed()


def test_production_mode_uses_random_passwords(settings):
    settings.DEBUG = False
    out = seed("--allow-production")
    assert "student-demo-311" not in out
    assert "shown once" in out
