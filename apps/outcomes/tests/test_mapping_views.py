from django.urls import reverse

from apps.catalog.models import Term
from apps.outcomes.matrix import A_LO, LO_PO, Cell, matrix_version
from apps.outcomes.models import AssessmentLOWeight, LOPOWeight
from apps.outcomes.services import save_lo_po_matrix


def url(name, course):
    return reverse(f"outcomes:{name}", kwargs={"offering_id": course.offering.pk})


def test_mapping_page_shows_both_grids_with_saved_values(
    teacher_client, course, django_assert_max_num_queries
):
    AssessmentLOWeight.objects.create(
        assessment=course.midterm, learning_outcome=course.lo1, weight="60.00"
    )
    with django_assert_max_num_queries(20):
        response = teacher_client.get(url("mapping", course))
    html = response.content.decode()
    assert response.status_code == 200
    assert f'name="a_lo-{course.midterm.pk}-{course.lo1.pk}" value="60"' in html
    assert f'name="lo_po-{course.lo1.pk}-{course.po1.pk}" value=""' in html
    assert "PO 3 · Design" in html  # header tooltip carries the PO wording
    assert 'hx-post="' + url("validate_cell", course) in html


def test_valid_save_redirects_to_the_grid(teacher_client, course):
    response = teacher_client.post(
        url("save_lo_po", course),
        {
            "version": matrix_version(course.offering, LO_PO),
            f"lo_po-{course.lo1.pk}-{course.po1.pk}": "4",
        },
    )
    assert response.status_code == 302
    assert response["Location"].endswith("#lo-po")
    assert LOPOWeight.objects.get().weight == 4


def test_invalid_cells_answer_422_and_keep_what_was_typed(teacher_client, course):
    """B5 AC2."""
    name = f"lo_po-{course.lo1.pk}-{course.po1.pk}"
    response = teacher_client.post(
        url("save_lo_po", course), {"version": matrix_version(course.offering, LO_PO), name: "6"}
    )
    html = response.content.decode()
    assert response.status_code == 422
    assert f'name="{name}" value="6"' in html
    assert "Use a whole number from 1 to 5." in html and "Nothing was saved" in html
    assert not LOPOWeight.objects.exists()


def test_stale_save_answers_409_with_the_warning(teacher_client, course, head_user):
    """B5 AC3."""
    opened_with = matrix_version(course.offering, LO_PO)
    save_lo_po_matrix(
        head_user,
        course.offering,
        [Cell(course.lo1.pk, course.po1.pk, "5")],
        expected_version=opened_with,
    )
    response = teacher_client.post(
        url("save_lo_po", course),
        {"version": opened_with, f"lo_po-{course.lo1.pk}-{course.po1.pk}": "2"},
    )
    assert response.status_code == 409
    assert "This mapping changed since you opened it" in response.content.decode()
    assert LOPOWeight.objects.get().weight == 5


def test_post_without_version_is_400(teacher_client, course):
    assert teacher_client.post(url("save_assessment_lo", course), {}).status_code == 400


def test_validate_cell_returns_a_red_cell(teacher_client, course):
    name = f"lo_po-{course.lo1.pk}-{course.po1.pk}"
    response = teacher_client.post(
        url("validate_cell", course),
        {"kind": LO_PO, "name": name, name: "7", "label": "LO 1 to PO 1"},
        headers={"HX-Request": "true"},
    )
    html = response.content.decode().strip()
    assert response.status_code == 200
    assert html.startswith("<td") and "is-invalid" in html
    assert "Use a whole number from 1 to 5." in html
    assert 'aria-label="LO 1 to PO 1"' in html


def test_validate_cell_accepts_a_good_value(teacher_client, course):
    name = f"a_lo-{course.midterm.pk}-{course.lo1.pk}"
    html = teacher_client.post(
        url("validate_cell", course),
        {"kind": A_LO, "name": name, name: "12,5"},
        headers={"HX-Request": "true"},
    ).content.decode()
    assert "is-invalid" not in html


def test_validate_cell_refuses_a_mismatched_kind(teacher_client, course):
    name = f"a_lo-{course.midterm.pk}-{course.lo1.pk}"
    response = teacher_client.post(
        url("validate_cell", course), {"kind": LO_PO, "name": name, name: "3"}
    )
    assert response.status_code == 400


def test_head_can_edit_any_course_mapping(client, course, head_user):
    """Decision D13: the head sees and can override every mapping."""
    client.force_login(head_user)
    response = client.post(
        url("save_assessment_lo", course),
        {
            "version": matrix_version(course.offering, A_LO),
            f"a_lo-{course.midterm.pk}-{course.lo1.pk}": "50",
        },
    )
    assert response.status_code == 302


def test_closed_term_shows_a_read_only_grid(teacher_client, course):
    Term.objects.filter(pk=course.term.pk).update(status=Term.Status.CLOSED)
    html = teacher_client.get(url("mapping", course)).content.decode()
    assert "disabled" in html
    assert "data-pl-save" not in html
    assert url("validate_cell", course) not in html
