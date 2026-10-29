from django.contrib import admin

from apps.outcomes.models import Assessment, LearningOutcome

from .models import (
    Course,
    CourseOffering,
    Enrollment,
    Program,
    ProgramOutcome,
    ProgramOutcomeSet,
    Term,
)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "attainment_threshold")
    search_fields = ("code", "name")


class ProgramOutcomeInline(admin.TabularInline):
    model = ProgramOutcome
    extra = 0


@admin.register(ProgramOutcomeSet)
class ProgramOutcomeSetAdmin(admin.ModelAdmin):
    list_display = ("label", "program", "effective_from_year", "is_active")
    list_filter = ("program", "is_active")
    inlines = [ProgramOutcomeInline]


@admin.register(ProgramOutcome)
class ProgramOutcomeAdmin(admin.ModelAdmin):
    list_display = ("number", "short_name", "po_set")
    list_filter = ("po_set",)
    search_fields = ("short_name", "description")


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "starts_on", "ends_on", "status")
    list_filter = ("status",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "program", "credits", "ects")
    list_filter = ("program",)
    search_fields = ("code", "title")


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    raw_id_fields = ("student",)  # a search popup; a dropdown of 400 students would be unusable


class LearningOutcomeInline(admin.TabularInline):
    model = LearningOutcome
    extra = 0
    fields = ("number", "description", "source")


class AssessmentInline(admin.TabularInline):
    model = Assessment
    extra = 0
    fields = ("position", "name", "kind", "max_score", "course_weight", "due_date", "published_at")
    readonly_fields = ("published_at",)


@admin.register(CourseOffering)
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ("course", "term", "section", "created_at")
    list_filter = ("term", "course__program")
    search_fields = ("course__code", "course__title")
    filter_horizontal = ("instructors",)
    inlines = [LearningOutcomeInline, AssessmentInline, EnrollmentInline]
    list_select_related = ("course", "term")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "offering", "status", "enrolled_at")
    list_filter = ("status", "offering__term")
    search_fields = ("student__email", "student__student_number", "offering__course__code")
    raw_id_fields = ("student",)  # a search popup; a dropdown of 400 students would be unusable
    list_select_related = ("student", "offering__course", "offering__term")
