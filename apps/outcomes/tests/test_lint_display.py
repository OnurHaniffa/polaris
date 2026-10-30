from decimal import Decimal

from django.urls import reverse

from apps.core.tests.factories import OfferingFactory
from apps.outcomes.lint import LOPOLink
from apps.outcomes.models import AssessmentLOWeight, LOPOWeight, Source
from apps.outcomes.selectors import lint_counts, snapshot_mapping, snapshot_mappings


def test_snapshot_reads_the_saved_mapping(course):
    AssessmentLOWeight.objects.create(
        assessment=course.midterm, learning_outcome=course.lo1, weight=Decimal("60")
    )
    LOPOWeight.objects.create(
        learning_outcome=course.lo1,
        program_outcome=course.po2,
        weight=4,
        source=Source.AI_SUGGESTED,
    )
    snap = snapshot_mapping(course.offering)
    assert [a.name for a in snap.assessments] == ["Midterm I", "Project"]
    assert [lo.number for lo in snap.los] == [1, 2]
    assert snap.assessment_lo == frozenset({(course.midterm.pk, course.lo1.pk)})
    assert snap.lo_po == (LOPOLink(course.lo1.pk, 1, course.po2.pk, 2, 4, "ai_suggested"),)


def test_many_snapshots_cost_four_queries(course, django_assert_num_queries):
    others = [OfferingFactory(course__program=course.program, term=course.term) for _ in range(4)]
    ids = [course.offering.pk] + [o.pk for o in others]
    with django_assert_num_queries(4):
        snaps = snapshot_mappings(ids)
    assert set(snaps) == set(ids)
    assert snaps[others[0].pk].los == ()


def test_counts_mark_empty_courses(course):
    empty = OfferingFactory(course__program=course.program, term=course.term)
    counts = lint_counts([course.offering.pk, empty.pk])
    assert counts[empty.pk].empty and counts[empty.pk].errors == 0
    assert counts[course.offering.pk].errors == 4  # 2 LOs × (L001 + L002)


def test_mapping_tab_shows_the_checks(teacher_client, course):
    """B11 AC2 (Mapping tab) and B5 AC4 (checks reflect the saved mapping)."""
    html = teacher_client.get(
        reverse("outcomes:mapping", kwargs={"offering_id": course.offering.pk})
    ).content.decode()
    assert "Mapping checks" in html
    assert "L001" in html and "L002" in html and "L003" in html
    assert "measured by any assessment" in html


def test_course_list_shows_a_lint_badge(teacher_client, course):
    """B11 AC2 (badge on the course list)."""
    html = teacher_client.get(reverse("catalog:teaching")).content.decode()
    assert "4 errors" in html
