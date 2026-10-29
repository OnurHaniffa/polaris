from django.contrib import admin

from .models import IngestionJob


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "kind",
        "offering",
        "status",
        "original_filename",
        "cost_usd",
        "created_at",
    )
    list_filter = ("kind", "status")
    readonly_fields = ("input_tokens", "output_tokens", "cost_usd", "request_id", "model")
