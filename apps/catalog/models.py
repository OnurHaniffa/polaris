from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Program(models.Model):
    code = models.CharField(max_length=16, unique=True)  # "CSE"
    name = models.CharField(max_length=200)
    attainment_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("60"))

    def __str__(self):
        return self.code


class ProgramOutcomeSet(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="po_sets")
    label = models.CharField(max_length=100)  # "2023 curriculum"
    effective_from_year = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["program", "label"], name="uniq_po_set_label"),
            models.UniqueConstraint(
                fields=["program"],
                condition=Q(is_active=True),
                name="one_active_po_set_per_program",
            ),
        ]

    def __str__(self):
        return f"{self.program} · {self.label}"


class ProgramOutcome(models.Model):
    po_set = models.ForeignKey(ProgramOutcomeSet, on_delete=models.CASCADE, related_name="outcomes")
    number = models.PositiveSmallIntegerField()  # 1..11
    short_name = models.CharField(max_length=80)
    description = models.TextField()

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["po_set", "number"], name="uniq_po_number"),
            models.CheckConstraint(condition=Q(number__gte=1) & Q(number__lte=30), name="po_number_range"),
        ]

    def __str__(self):
        return f"PO {self.number}"


class Term(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    code = models.CharField(max_length=10, unique=True)  # "2026F"
    name = models.CharField(max_length=40)  # "Fall 2026"
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)

    class Meta:
        ordering = ["-starts_on"]
        constraints = [
            models.CheckConstraint(condition=Q(ends_on__gt=F("starts_on")), name="term_dates_ordered"),
        ]

    def __str__(self):
        return self.name


class Course(models.Model):
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="courses")
    code = models.CharField(max_length=16)  # "CSE 311"
    title = models.CharField(max_length=200)
    credits = models.DecimalField(max_digits=4, decimal_places=1)
    ects = models.DecimalField(max_digits=4, decimal_places=1)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["program", "code"], name="uniq_course_code")]

    def __str__(self):
        return f"{self.code} {self.title}"


class CourseOffering(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="offerings")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="offerings")
    section = models.CharField(max_length=8, default="1")
    instructors = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="teaching", blank=True)
    syllabus = models.FileField(upload_to="syllabi/%Y/", null=True, blank=True)
    cloned_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["course", "term", "section"], name="uniq_offering"),
        ]

    def __str__(self):
        suffix = "" if self.section == "1" else f" (section {self.section})"
        return f"{self.course.code} · {self.term.name}{suffix}"


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ENROLLED = "enrolled", "Enrolled"
        DROPPED = "dropped", "Dropped"

    offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name="enrollments")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="enrollments")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ENROLLED)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["offering", "student"], name="uniq_enrollment"),
        ]
        indexes = [models.Index(fields=["student"], name="enrollment_student_idx")]

    def __str__(self):
        return f"{self.student} in {self.offering}"
