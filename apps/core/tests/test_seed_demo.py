import pytest
from django.core.management import CommandError, call_command

from apps.accounts.models import User
from apps.catalog.models import CourseOffering, Program
from apps.grading.models import Grade
from apps.scoring.engine import compute_student_profile, display
from apps.scoring.loaders import load_student_inputs

pytestmark = pytest.mark.django_db


def seed(settings, *args):
    settings.DEBUG = True
    call_command("seed_demo", "--small", *args)


def elif_profile():
    elif_ = User.objects.get(student_number="2024-0041")
    profile = compute_student_profile(load_student_inputs(elif_))
    numbers = {po.number: po for po in Program.objects.get(code="CSE").po_sets.get().outcomes.all()}
    return {
        n: display(profile.po_scores[po.id].score)
        for n, po in numbers.items()
        if po.id in profile.po_scores
    }


def test_elif_matches_the_slide(settings):
    seed(settings)
    assert elif_profile() == {1: "85.0", 2: "82.9", 3: "—"}


def test_second_run_is_a_no_op(settings, capsys):
    seed(settings)
    grades = Grade.objects.count()
    seed(settings)
    assert Grade.objects.count() == grades
    assert "already exists" in capsys.readouterr().out


def grade_rows():
    # excused and missing grades have score None, so sort by the text form
    rows = Grade.objects.values_list(
        "enrollment__student__student_number", "assessment__name", "score", "is_excused"
    )
    return sorted(rows, key=repr)


def test_reset_rebuilds_identical_data(settings):
    seed(settings)
    before = grade_rows()
    seed(settings, "--reset")
    assert grade_rows() == before  # fixed random seed: same data every time
    assert CourseOffering.objects.count() == 4


def test_refuses_without_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="Refusing to seed"):
        call_command("seed_demo")


def test_drafts_are_never_published(settings):
    seed(settings)
    drafts = Grade.objects.filter(assessment__published_at__isnull=True)
    assert drafts.exists()
    assert not drafts.filter(published_score__isnull=False).exists()
