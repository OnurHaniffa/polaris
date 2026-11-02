from django.conf import settings
from django.db import models
from django.db.models import Q


class Grade(models.Model):
    assessment = models.ForeignKey("outcomes.Assessment", on_delete=models.CASCADE, related_name="grades")
    enrollment = models.ForeignKey("catalog.Enrollment", on_delete=models.CASCADE, related_name="grades")
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    is_excused = models.BooleanField(default=False)
    published_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    published_is_excused = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["assessment", "enrollment"], name="uniq_grade"),
            models.CheckConstraint(condition=Q(score__isnull=True) | Q(score__gte=0), name="score_non_negative"),
        ]
        indexes = [models.Index(fields=["enrollment"], name="grade_enrollment_idx")]

    def __str__(self):
        return f"{self.enrollment} · {self.assessment}: {self.score}"

    @property
    def has_unpublished_change(self) -> bool:
        return (self.score, self.is_excused) != (self.published_score, self.published_is_excused)
