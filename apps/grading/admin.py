from django.contrib import admin

from .models import Grade


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "assessment", "score", "published_score", "is_excused")
    list_filter = ("assessment__offering__term", "is_excused")
    search_fields = ("enrollment__student__email", "enrollment__student__student_number")
    list_select_related = ("enrollment__student", "assessment")
    raw_id_fields = ("enrollment", "assessment")
