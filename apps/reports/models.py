from django.conf import settings
from django.db import models


class ExportJob(models.Model):
    class Kind(models.TextChoices):
        COURSE = "course", "Course report"
        DEPARTMENT = "department", "Department report"
        TRANSCRIPT = "transcript", "PO transcript"

    class Format(models.TextChoices):
        PDF = "pdf", "PDF"
        XLSX = "xlsx", "Excel"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting"
        RUNNING = "running", "Building"
        DONE = "done", "Ready"
        FAILED = "failed", "Failed"

    kind = models.CharField(max_length=12, choices=Kind.choices)
    fmt = models.CharField(max_length=4, choices=Format.choices)
    offering = models.ForeignKey("catalog.CourseOffering", null=True, blank=True, on_delete=models.CASCADE)
    program = models.ForeignKey("catalog.Program", null=True, blank=True, on_delete=models.CASCADE)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    file = models.FileField(upload_to="exports/%Y/%m/", null=True, blank=True)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} ({self.fmt}) #{self.pk}"
