# apps/reports/urls_student.py
from django.urls import path

from . import views_student

app_name = "student"

urlpatterns = [
    path("", views_student.profile, name="profile"),
    path("po/<int:po_id>/", views_student.po_detail, name="po_detail"),
    path("courses/<int:offering_id>/", views_student.course, name="course"),
    path("transcript.pdf", views_student.transcript, name="transcript"),
]
