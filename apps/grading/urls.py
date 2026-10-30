from django.urls import path

from . import views

app_name = "grading"

urlpatterns = [
    path("offerings/<int:offering_id>/grades/", views.sheet, name="sheet"),
    path(
        "offerings/<int:offering_id>/grades/cell/<int:assessment_id>/<int:enrollment_id>/",
        views.cell,
        name="cell",
    ),
]
