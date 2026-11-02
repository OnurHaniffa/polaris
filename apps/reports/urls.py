# apps/reports/urls.py
from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("department/students/<int:user_id>/", views.department_student, name="department_student"),
    path(
        "department/students/<int:user_id>/po/<int:po_id>/",
        views.department_student_po,
        name="department_student_po",
    ),
    path("offerings/<int:offering_id>/results/", views.course_results, name="results"),
    path("department/", views.department, name="department"),
]

