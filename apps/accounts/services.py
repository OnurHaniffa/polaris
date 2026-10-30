from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import ProgramMembership, User
from apps.core import audit


@transaction.atomic
def get_or_create_student(
    *, student_number, email, first_name, last_name, program, cohort_year, actor=None
) -> tuple[User, bool]:
    """Find a student by student number, or create the account. Ensures a student membership
    in `program`. Returns (user, created). Raises ValidationError on conflicting data."""
    student_number = (student_number or "").strip()
    email = User.objects.normalize_email((email or "").strip())
    if not student_number:
        raise ValidationError({"student_number": "Student number is required."})

    user = User.objects.filter(student_number=student_number).first()
    created = False
    if user is None:
        if not email or not first_name or not last_name or not cohort_year:
            raise ValidationError(
                "New students need a student number, email, first name, last name and cohort year."
            )
        clash = User.objects.filter(email__iexact=email).first()
        if clash is not None:
            raise ValidationError(
                {
                    "email": f"{email} already belongs to another account "
                    f"(student number {clash.student_number or 'none'})."
                }
            )
        user = User(
            email=email,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            student_number=student_number,
        )
        user.set_unusable_password()
        user.full_clean(exclude=["password"])
        user.save()
        created = True
        audit.record(
            actor, "user.create", user, after={"student_number": student_number, "email": email}
        )
    elif email and user.email.lower() != email.lower():
        raise ValidationError(
            {"email": f"Student {student_number} is registered as {user.email}, not {email}."}
        )

    membership = ProgramMembership.objects.filter(
        user=user, program=program, role=ProgramMembership.Role.STUDENT
    ).first()
    if membership is None:
        if not cohort_year:
            raise ValidationError({"cohort_year": "Cohort year is required for a new student."})
        membership = ProgramMembership.objects.create(
            user=user, program=program, role=ProgramMembership.Role.STUDENT, cohort_year=cohort_year
        )
        audit.record(
            actor,
            "membership.create",
            membership,
            after={"role": "student", "program": program.code, "cohort_year": cohort_year},
        )
    return user, created
