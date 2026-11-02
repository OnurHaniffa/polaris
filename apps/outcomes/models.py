from django.db import models
from django.db.models import Q


class Source(models.TextChoices):
    MANUAL = "manual", "Entered by hand"
    SYLLABUS = "syllabus", "Read from syllabus"
    AI_SUGGESTED = "ai_suggested", "Suggested by AI"
    CLONED = "cloned", "Cloned from a previous term"


class LearningOutcome(models.Model):
    offering = models.ForeignKey("catalog.CourseOffering", on_delete=models.CASCADE, related_name="learning_outcomes")
    number = models.PositiveSmallIntegerField()
    description = models.TextField()
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["offering", "number"], name="uniq_lo_number")]

    def __str__(self):
        return f"LO {self.number}"


class Assessment(models.Model):
    class Kind(models.TextChoices):
        MIDTERM = "midterm", "Midterm"
        FINAL = "final", "Final exam"
        PROJECT = "project", "Project"
        QUIZ = "quiz", "Quiz"
        HOMEWORK = "homework", "Homework"
        LAB = "lab", "Lab"
        PRESENTATION = "presentation", "Presentation"
        PARTICIPATION = "participation", "Attendance / participation"
        OTHER = "other", "Other"

    offering = models.ForeignKey("catalog.CourseOffering", on_delete=models.CASCADE, related_name="assessments")
    name = models.CharField(max_length=100)  # "Midterm I"
    kind = models.CharField(max_length=16, choices=Kind.choices)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, default=100)
    course_weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["offering", "name"], name="uniq_assessment_name"),
            models.CheckConstraint(condition=Q(max_score__gt=0), name="max_score_positive"),
        ]

    def __str__(self):
        return self.name


class AssessmentLOWeight(models.Model):
    """Arrow from an assessment to an LO. Weight in percent, 0 < w ≤ 100 (policy P1)."""

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="lo_weights")
    learning_outcome = models.ForeignKey(LearningOutcome, on_delete=models.CASCADE, related_name="assessment_weights")
    weight = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["assessment", "learning_outcome"], name="uniq_a_lo"),
            models.CheckConstraint(condition=Q(weight__gt=0) & Q(weight__lte=100), name="a_lo_weight_range"),
        ]

    def __str__(self):
        return f"{self.assessment} → {self.learning_outcome}: {self.weight}%"


class LOPOWeight(models.Model):
    """Arrow from an LO to a PO. Integer 1..5 (policy P2). No row = no contribution."""

    learning_outcome = models.ForeignKey(LearningOutcome, on_delete=models.CASCADE, related_name="po_weights")
    program_outcome = models.ForeignKey("catalog.ProgramOutcome", on_delete=models.PROTECT, related_name="lo_weights")
    weight = models.PositiveSmallIntegerField()
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)
    rationale = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["learning_outcome", "program_outcome"], name="uniq_lo_po"),
            models.CheckConstraint(condition=Q(weight__gte=1) & Q(weight__lte=5), name="lo_po_weight_range"),
        ]

    def __str__(self):
        return f"{self.learning_outcome} → {self.program_outcome}: {self.weight}"
