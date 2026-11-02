from django.db import models


class IngestionJob(models.Model):
    class Kind(models.TextChoices):
        SYLLABUS = "syllabus", "Syllabus"
        GRADES = "grades", "Grade file"
        ENROLLMENTS = "enrollments", "Enrollment list"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting"
        PROCESSING = "processing", "Reading"
        READY = "ready", "Ready for review"
        APPLIED = "applied", "Applied"
        FAILED = "failed", "Failed"
        DISCARDED = "discarded", "Discarded"

    offering = models.ForeignKey("catalog.CourseOffering", on_delete=models.CASCADE, related_name="ingestion_jobs")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    file = models.FileField(upload_to="uploads/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    result = models.JSONField(null=True, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)
    model = models.CharField(max_length=40, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} job #{self.pk} ({self.status})"
