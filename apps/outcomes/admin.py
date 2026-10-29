from django.contrib import admin

from .models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight


class AssessmentLOWeightInline(admin.TabularInline):
    model = AssessmentLOWeight
    extra = 0


class LOPOWeightInline(admin.TabularInline):
    model = LOPOWeight
    extra = 0


@admin.register(LearningOutcome)
class LearningOutcomeAdmin(admin.ModelAdmin):
    list_display = ("__str__", "offering", "source")
    list_filter = ("source", "offering__term")
    search_fields = ("description", "offering__course__code")
    inlines = [LOPOWeightInline]


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("name", "offering", "kind", "max_score", "course_weight", "published_at")
    list_filter = ("kind", "offering__term")
    search_fields = ("name", "offering__course__code")
    inlines = [AssessmentLOWeightInline]


@admin.register(AssessmentLOWeight)
class AssessmentLOWeightAdmin(admin.ModelAdmin):
    list_display = ("assessment", "learning_outcome", "weight")
    list_filter = ("assessment__offering__term",)


@admin.register(LOPOWeight)
class LOPOWeightAdmin(admin.ModelAdmin):
    list_display = ("learning_outcome", "program_outcome", "weight", "source")
    list_filter = ("source", "program_outcome")
