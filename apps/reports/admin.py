from django.contrib import admin

from .models import ExportJob


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "fmt", "status", "created_by", "created_at", "finished_at")
    list_filter = ("kind", "fmt", "status")
