from django.urls import path

from apps.catalog import views

app_name = "catalog"

urlpatterns = [
    path("teaching/", views.teaching, name="teaching"),
    path("offerings/<int:offering_id>/", views.offering_home, name="offering"),
    # department: outcomes
    path("department/outcomes/", views.po_sets, name="outcomes"),
    path("department/outcomes/sets/<int:set_id>/", views.po_set_detail, name="po_set"),
    path("department/outcomes/sets/<int:set_id>/copy/", views.po_set_copy, name="po_set_copy"),
    path(
        "department/outcomes/sets/<int:set_id>/activate/",
        views.po_set_activate,
        name="po_set_activate",
    ),
    path("department/outcomes/<int:po_id>/edit/", views.po_edit, name="po_edit"),
    path("department/outcomes/<int:po_id>/delete/", views.po_delete, name="po_delete"),
    # department: terms, courses, offerings, enrollments
    path("department/terms/", views.terms, name="terms"),
    path("department/terms/<int:term_id>/edit/", views.term_edit, name="term_edit"),
    path("department/terms/<int:term_id>/status/", views.term_status, name="term_status"),
    path("department/courses/", views.courses, name="courses"),
    path("department/courses/<int:course_id>/edit/", views.course_edit, name="course_edit"),
    path("department/offerings/", views.offerings, name="offerings"),
    path("department/offerings/<int:offering_id>/edit/", views.offering_edit, name="offering_edit"),
    path(
        "department/offerings/<int:offering_id>/enrollments/", views.enrollments, name="enrollments"
    ),
    # S3-05 adds: enrollment_import, enrollment_import_preview, enrollment_import_confirm
]
