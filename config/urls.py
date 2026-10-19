from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

urlpatterns = [
    path("healthz", core_views.healthz, name="healthz"),
    path("admin/", admin.site.urls),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
