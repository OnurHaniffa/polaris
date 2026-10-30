from django.urls import path

from . import views

app_name = "outcomes"

OFFERING = "offerings/<int:offering_id>/"

urlpatterns = [
    path(OFFERING + "setup/", views.setup, name="setup"),
    path(OFFERING + "setup/los/new/", views.lo_create, name="lo_create"),
    path(OFFERING + "setup/los/<int:lo_id>/edit/", views.lo_edit, name="lo_edit"),
    path(OFFERING + "setup/los/<int:lo_id>/delete/", views.lo_delete, name="lo_delete"),
    path(OFFERING + "setup/los/reorder/", views.lo_reorder, name="lo_reorder"),
    path(OFFERING + "setup/assessments/new/", views.assessment_create, name="assessment_create"),
    path(
        OFFERING + "setup/assessments/<int:assessment_id>/edit/",
        views.assessment_edit,
        name="assessment_edit",
    ),
    path(
        OFFERING + "setup/assessments/<int:assessment_id>/delete/",
        views.assessment_delete,
        name="assessment_delete",
    ),
    path(OFFERING + "mapping/", views.mapping, name="mapping"),
    path(OFFERING + "mapping/assessment-lo/", views.save_assessment_lo, name="save_assessment_lo"),
    path(OFFERING + "mapping/lo-po/", views.save_lo_po, name="save_lo_po"),
    path(OFFERING + "mapping/validate/", views.validate_cell, name="validate_cell"),
]
