from django.urls import path

from apps.catalog import views

app_name = "catalog"

urlpatterns = [
    path("teaching/", views.teaching, name="teaching"),
    path("offerings/<int:offering_id>/", views.offering_home, name="offering"),
]
