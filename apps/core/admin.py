from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Read-only: an audit trail you can edit is not an audit trail."""

    list_display = ("created_at", "actor", "action", "entity_type", "entity_id", "offering")
    list_filter = ("action", "entity_type")
    search_fields = ("actor__email", "action")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
