from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models import Q


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """Identity only. What someone *is* lives in ProgramMembership (decision D6)."""

    username = None
    email = models.EmailField(unique=True)
    student_number = models.CharField(max_length=20, unique=True, null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]
    objects = UserManager()

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}>"


class ProgramMembership(models.Model):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        INSTRUCTOR = "instructor", "Instructor"
        HEAD = "head", "Department Head"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    program = models.ForeignKey(
        "catalog.Program", on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    cohort_year = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "program", "role"], name="uniq_membership"),
            models.CheckConstraint(
                condition=~Q(role="student") | Q(cohort_year__isnull=False),
                name="student_has_cohort",
            ),
        ]

    def __str__(self):
        return f"{self.user} · {self.get_role_display()} · {self.program}"
