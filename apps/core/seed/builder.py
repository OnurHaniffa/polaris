"""Builds the demo department (spec Appendix B). Deterministic: same seed, same data."""
from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from decimal import Decimal

from django.contrib.auth.hashers import make_password

from apps.accounts.models import ProgramMembership, User
from apps.catalog.models import Course, CourseOffering, Enrollment, Program, Term
from apps.catalog.selectors import active_po_set
from apps.core.models import AuditEvent
from apps.grading.models import Grade
from apps.ingestion.models import IngestionJob
from apps.outcomes.models import (
    Assessment,
    AssessmentLOWeight,
    LearningOutcome,
    LOPOWeight,
    Source,
)

from . import data

SEED = 311
DOMAIN = "polaris.test"
MISSING_RATE = 0.05
EXCUSED_RATE = 0.02
FALL_2026_PUBLISHED_AT = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)

TRANSLIT = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def slug(name: str) -> str:
    return name.translate(TRANSLIT).lower().replace(" ", "")


def half(value: float) -> Decimal:
    """Round to the nearest 0.5, the way instructors write marks."""
    return Decimal(round(value * 2)) / Decimal(2)


@dataclass
class Persona:
    role: str
    name: str
    email: str
    password: str


@dataclass
class SeedSummary:
    personas: list[Persona] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


class DemoBuilder:
    def __init__(self, *, students_per_cohort: int = 40, random_passwords: bool = False):
        self.n = students_per_cohort
        self.random_passwords = random_passwords
        self.rng = random.Random(SEED)
        self.summary = SeedSummary()
        self.abilities: dict[int, dict[int, float]] = {}     # user id -> PO number -> ability
        self.base: dict[int, float] = {}                     # user id -> μ
        self.cohort_students: dict[str, list[User]] = {}

    # ---------- housekeeping ----------

    @staticmethod
    def already_seeded() -> bool:
        return Term.objects.filter(code="2026F").exists()

    @staticmethod
    def wipe() -> None:
        """Delete all teaching data and every demo account. Keeps programs, PO sets and
        superusers. Order matters because of PROTECT foreign keys."""
        AuditEvent.objects.all().delete()
        IngestionJob.objects.all().delete()           # created_by is PROTECT
        CourseOffering.objects.all().delete()         # cascades LOs, assessments, weights, enrollments, grades
        Course.objects.all().delete()
        Term.objects.all().delete()
        User.objects.filter(email__endswith=DOMAIN, is_superuser=False).delete()

    def _password(self, fixed: str) -> str:
        return secrets.token_urlsafe(9) if self.random_passwords else fixed

    # ---------- build ----------

    def build(self) -> SeedSummary:
        self.program = Program.objects.get(code="CSE")
        self.pos = {po.number: po for po in active_po_set(self.program).outcomes.all()}
        if len(self.pos) != 11:
            raise RuntimeError("Expected the 11 official POs from the S1-05 data migration.")

        self.terms = {
            code: Term.objects.create(code=code, name=name, starts_on=start, ends_on=end, status=status)
            for code, name, start, end, status in data.TERMS
        }
        self._staff()
        self._students()
        self.courses = {
            code: Course.objects.create(program=self.program, code=code, title=spec.title,
                                        credits=Decimal(spec.credits), ects=Decimal(spec.ects))
            for code, spec in data.COURSES.items()
        }
        for spec in data.OFFERINGS:
            self._offering(spec)

        self.summary.counts = {
            "terms": Term.objects.count(),
            "courses": Course.objects.count(),
            "offerings": CourseOffering.objects.count(),
            "students": User.objects.filter(memberships__role="student").distinct().count(),
            "enrollments": Enrollment.objects.count(),
            "grades": Grade.objects.count(),
        }
        return self.summary

    def _staff(self) -> None:
        password = self._password("teach-demo-311")
        head_password = self._password("head-demo-311")
        self.staff: dict[str, User] = {}
        for key, (first, last, local, roles) in data.PEOPLE.items():
            pw = head_password if key == "head" else password
            user = User.objects.create_user(email=f"{local}@{DOMAIN}", password=pw,
                                            first_name=first, last_name=last)
            for role in roles:
                ProgramMembership.objects.create(user=user, program=self.program, role=role)
            self.staff[key] = user
            self.summary.personas.append(Persona(
                role="Head + instructor" if key == "head" else "Instructor",
                name=f"{first} {last}", email=user.email, password=pw,
            ))

    def _students(self) -> None:
        student_password = self._password("student-demo-311")
        hashed = make_password(student_password)
        users = []
        for cohort in data.COHORTS:
            for i in range(1, self.n + 1):
                first = self.rng.choice(data.FIRST_NAMES)
                last = self.rng.choice(data.LAST_NAMES)
                number = f"{cohort}-{i:04d}"
                users.append(User(
                    email=f"{slug(first)}.{slug(last)}.{cohort % 100}{i:03d}@students.{DOMAIN}",
                    first_name=first, last_name=last, student_number=number, password=hashed,
                ))
        users = User.objects.bulk_create(users)          # PostgreSQL returns primary keys

        memberships = []
        for user in users:
            cohort = int(user.student_number[:4])
            memberships.append(ProgramMembership(user=user, program=self.program,
                                                 role=ProgramMembership.Role.STUDENT, cohort_year=cohort))
            self.cohort_students.setdefault(str(cohort), []).append(user)
            mu = self.rng.gauss(70, 9)
            self.base[user.pk] = mu
            self.abilities[user.pk] = {n: min(99.0, max(30.0, self.rng.gauss(mu, 7))) for n in range(1, 12)}
        ProgramMembership.objects.bulk_create(memberships)

        weakest = sorted(self.cohort_students["2025"], key=lambda u: self.base[u.pk])[:data.RETAKERS]
        self.cohort_students["retake"] = sorted(weakest, key=lambda u: u.student_number)

        self.elif_user = User.objects.create_user(
            email=data.ELIF["email"], password=student_password,
            first_name=data.ELIF["first_name"], last_name=data.ELIF["last_name"],
            student_number=data.ELIF["student_number"],
        )
        ProgramMembership.objects.create(user=self.elif_user, program=self.program,
                                         role=ProgramMembership.Role.STUDENT,
                                         cohort_year=data.ELIF["cohort_year"])
        self.summary.personas.append(Persona("Student (slide example)", "Elif Yıldız",
                                             self.elif_user.email, student_password))
        self.summary.personas.append(Persona("Any other student", f"{len(users)} students",
                                             f"…@students.{DOMAIN} (see admin)", student_password))

    def _offering(self, spec: data.OfferingSpec) -> None:
        course_spec = data.COURSES[spec.course]
        term = self.terms[spec.term]
        teacher = self.staff[spec.teacher]
        offering = CourseOffering.objects.create(course=self.courses[spec.course], term=term)
        offering.instructors.set([teacher])

        los = [
            LearningOutcome.objects.create(offering=offering, number=i, description=lo.text)
            for i, lo in enumerate(course_spec.los, start=1)
        ]
        if term.status == Term.Status.CLOSED:
            published_at = datetime.combine(term.ends_on, time(12, 0), tzinfo=UTC)
        else:
            published_at = FALL_2026_PUBLISHED_AT

        assessments = []
        for position, a in enumerate(course_spec.assessments):
            is_published = spec.published == "all" or (
                isinstance(spec.published, tuple) and a.name in spec.published)
            assessments.append((a, Assessment.objects.create(
                offering=offering, name=a.name, kind=a.kind, max_score=Decimal(a.max_score),
                course_weight=Decimal(a.course_weight), position=position,
                published_at=published_at if is_published else None,
                published_by=teacher if is_published else None,
            )))

        if spec.mapped:
            AssessmentLOWeight.objects.bulk_create([
                AssessmentLOWeight(assessment=obj, learning_outcome=los[lo_no - 1], weight=Decimal(w))
                for a, obj in assessments for lo_no, w in a.lo.items()
            ])
            LOPOWeight.objects.bulk_create([
                LOPOWeight(learning_outcome=los[i], program_outcome=self.pos[po_no], weight=w,
                           source=Source.MANUAL)
                for i, lo in enumerate(course_spec.los) for po_no, w in lo.po.items()
            ])

        students = sorted(
            (u for cohort in spec.cohorts for u in self.cohort_students[cohort]),
            key=lambda u: u.student_number,
        )
        enrollments = Enrollment.objects.bulk_create(
            [Enrollment(offering=offering, student=u) for u in students])

        grades = []
        for enrollment, student in zip(enrollments, students, strict=True):
            for a, obj in assessments:
                if obj.published_at is None:
                    continue                          # not held yet (open term) or not published
                grade = self._grade(student, a, course_spec, obj, enrollment, teacher)
                if grade is not None:
                    grades.append(grade)

        if spec.elif_here:
            elif_enrollment = Enrollment.objects.create(offering=offering, student=self.elif_user)
            for a, obj in assessments:
                if a.name in data.ELIF["grades"]:
                    value = Decimal(data.ELIF["grades"][a.name])
                    grades.append(Grade(assessment=obj, enrollment=elif_enrollment, score=value,
                                        published_score=value, published_at=obj.published_at,
                                        updated_by=teacher))
        Grade.objects.bulk_create(grades)

        if spec.unpublished_change:
            first_published = next(obj for _a, obj in assessments if obj.published_at is not None)
            grade = (Grade.objects.filter(assessment=first_published, score__isnull=False)
                     .order_by("enrollment__student__student_number").first())
            grade.score = min(first_published.max_score, grade.score + Decimal(5))
            if grade.score == grade.published_score:          # was already at max: go down instead
                grade.score -= Decimal(5)
            grade.save(update_fields=["score"])

    def _grade(self, student, a: data.AssessmentSpec, course: data.CourseSpec, obj, enrollment, teacher):
        draw = self.rng.random()
        noise = self.rng.gauss(0, 8)
        if draw < MISSING_RATE:
            return None
        if draw < MISSING_RATE + EXCUSED_RATE:
            return Grade(assessment=obj, enrollment=enrollment, is_excused=True,
                         published_is_excused=True, published_at=obj.published_at, updated_by=teacher)
        num = den = 0.0
        abilities = self.abilities[student.pk]
        for lo_no, w in a.lo.items():
            for po_no, pw in course.los[lo_no - 1].po.items():
                num += abilities[po_no] * w * pw
                den += w * pw
        percent = min(100.0, max(0.0, num / den + noise))
        score = min(Decimal(a.max_score), half(percent / 100 * a.max_score))
        return Grade(assessment=obj, enrollment=enrollment, score=score, published_score=score,
                     published_at=obj.published_at, updated_by=teacher)