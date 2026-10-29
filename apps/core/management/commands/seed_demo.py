"""Fill a fresh database with a believable department (spec Appendix B, v1 = Sprint 1).

    uv run python manage.py seed_demo             # once, on an empty database
    uv run python manage.py seed_demo --reset     # wipe demo data and rebuild
    uv run python manage.py seed_demo --small     # 12 students instead of 30 (fast, for tests)

v1 builds: 3 terms, 4 instructors (the head also teaches), 30 students in cohorts
2023-2025, 4 offerings with LOs, assessments, both weight sets and grades, and Elif Yıldız
with exactly the professor's slide example (PO 1 = 85.0, PO 2 = 82.9).
"""

import datetime
import random
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import ProgramMembership, User
from apps.catalog.models import (
    Course,
    CourseOffering,
    Enrollment,
    Program,
    ProgramOutcome,
    Term,
)
from apps.catalog.selectors import active_po_set
from apps.core.seed.names import FIRST_NAMES, LAST_NAMES
from apps.grading.models import Grade
from apps.outcomes.models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight

SEED = 311
DEMO_PASSWORD = "polaris-demo-2026"  # noqa: S105

TERMS = [
    ("2025F", "Fall 2025", datetime.date(2025, 9, 29), datetime.date(2026, 1, 23), "closed"),
    ("2026S", "Spring 2026", datetime.date(2026, 2, 9), datetime.date(2026, 6, 12), "closed"),
    ("2026F", "Fall 2026", datetime.date(2026, 9, 28), datetime.date(2027, 1, 22), "open"),
]

STAFF = [
    ("Deniz", "Kara", "deniz.kara", ["head", "instructor"]),
    ("Can", "Aydın", "can.aydin", ["instructor"]),
    ("Ayşe", "Demir", "ayse.demir", ["instructor"]),
    ("Mehmet", "Şahin", "mehmet.sahin", ["instructor"]),
]

COURSES = [
    {
        "code": "CSE 211",
        "title": "Data Structures",
        "credits": "4.0",
        "ects": "6.0",
        "term": "2025F",
        "instructor": "can.aydin",
        "cohorts": [2023, 2024],
        "los": [
            "Analyse the time and space complexity of algorithms using asymptotic notation.",
            "Implement lists, stacks, queues, trees and hash tables and choose between them.",
            "Design and test programs that use appropriate data structures for a problem.",
        ],
        "assessments": [
            ("Quiz 1", "quiz", "20", "10", True),
            ("Midterm", "midterm", "100", "30", True),
            ("Lab assignments", "lab", "100", "20", True),
            ("Final", "final", "100", "40", True),
        ],
        "a_lo": {
            "Quiz 1": {1: 100},
            "Midterm": {1: 50, 2: 50},
            "Lab assignments": {2: 50, 3: 100},
            "Final": {1: 40, 2: 30, 3: 30},
        },
        "lo_po": {1: {1: 5, 2: 3}, 2: {1: 3, 4: 4}, 3: {2: 4, 3: 3, 4: 3}},
    },
    {
        "code": "MAT 241",
        "title": "Linear Algebra",
        "credits": "3.0",
        "ects": "5.0",
        "term": "2026S",
        "instructor": "mehmet.sahin",
        "cohorts": [2023, 2024, 2025],
        "los": [
            "Solve systems of linear equations with Gaussian elimination and matrix methods.",
            "Compute and interpret eigenvalues, eigenvectors and matrix decompositions.",
        ],
        "assessments": [
            ("Midterm", "midterm", "100", "40", True),
            ("Homework", "homework", "50", "20", True),
            ("Final", "final", "100", "40", True),
        ],
        "a_lo": {"Midterm": {1: 100}, "Homework": {1: 50, 2: 50}, "Final": {1: 40, 2: 60}},
        "lo_po": {1: {1: 5}, 2: {1: 4, 2: 3}},
    },
    {
        "code": "CSE 311",
        "title": "Software Engineering",
        "credits": "3.0",
        "ects": "6.0",
        "term": "2026F",
        "instructor": "deniz.kara",
        "cohorts": [2023, 2024],
        "los": [
            "Plan and run a software project with Scrum: backlog, sprints, reviews.",
            "Use version control, code review and continuous integration in a team.",
            "Write automated tests and apply test-driven development.",
        ],
        "assessments": [
            ("Midterm I", "midterm", "100", "30", True),
            ("Project", "project", "100", "40", True),
            ("Final", "final", "100", "30", False),
        ],
        "a_lo": {"Midterm I": {1: 60, 2: 40}, "Project": {1: 40, 2: 100}, "Final": {3: 100}},
        "lo_po": {1: {1: 4}, 2: {1: 2, 2: 5}, 3: {3: 4}},
    },
    {
        "code": "CSE 321",
        "title": "Data Systems",
        "credits": "3.0",
        "ects": "6.0",
        "term": "2026F",
        "instructor": "ayse.demir",
        "cohorts": [2023],
        "los": [
            "Design normalised relational schemas from requirements.",
            "Write SQL queries, including joins, aggregation and window functions.",
            "Explain transactions, isolation levels and indexing trade-offs.",
        ],
        "assessments": [
            ("Midterm", "midterm", "100", "35", True),
            ("Team project", "project", "100", "35", False),
            ("Final", "final", "100", "30", False),
        ],
        "a_lo": {
            "Midterm": {1: 50, 2: 50},
            "Team project": {1: 50, 2: 50, 3: 30},
            "Final": {2: 40, 3: 100},
        },
        "lo_po": {1: {3: 4, 4: 3}, 2: {2: 4, 4: 5}, 3: {1: 3, 2: 3}},
    },
]

ELIF = {
    "first_name": "Elif",
    "last_name": "Yıldız",
    "email": "elif.yildiz@live.acibadem.edu.tr",
    "student_number": "2024-0041",
    "cohort_year": 2024,
    "marks": {"Midterm I": Decimal("90"), "Project": Decimal("80")},
}

ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


class Command(BaseCommand):
    help = "Fill the database with demo data (spec Appendix B)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="wipe demo data first")
        parser.add_argument("--small", action="store_true", help="12 students instead of 30")
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help="run even when DEBUG=False",
        )

    def handle(self, *args, reset, small, allow_production, **options):
        if not settings.DEBUG and not allow_production:
            raise CommandError(
                "Refusing to seed with DEBUG=False: demo accounts have a known password. "
                "Pass --allow-production if you really mean it."
            )
        self.rng = random.Random(SEED)  # noqa: S311

        with transaction.atomic():
            if reset:
                self.wipe()
            elif Term.objects.filter(code="2026F").exists():
                self.stdout.write("Demo data already exists. Use --reset to rebuild it.")
                return
            self.build(students_per_cohort=4 if small else 10)
        self.report()

    def wipe(self):
        CourseOffering.objects.all().delete()
        Course.objects.all().delete()
        Term.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write("Wiped demo data.")

    def build(self, *, students_per_cohort):
        self.program = Program.objects.get(code="CSE")
        self.pos = {
            po.number: po
            for po in ProgramOutcome.objects.filter(po_set=active_po_set(self.program))
        }
        self.terms = {
            code: Term.objects.create(code=code, name=name, starts_on=s, ends_on=e, status=st)
            for code, name, s, e, st in TERMS
        }
        self.staff = self.create_staff()
        self.elif_ = self.create_user(**{k: v for k, v in ELIF.items() if k != "marks"})
        self.students = [self.elif_] + self.create_students(students_per_cohort)
        for spec in COURSES:
            self.create_offering(spec)

    def create_user(self, *, first_name, last_name, email, student_number=None, cohort_year=None):
        user = User.objects.create_user(
            email,
            DEMO_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            student_number=student_number,
        )
        if cohort_year is not None:
            ProgramMembership.objects.create(
                user=user, program=self.program, role="student", cohort_year=cohort_year
            )
        return user

    def create_staff(self):
        staff = {}
        for first, last, local, roles in STAFF:
            user = self.create_user(
                first_name=first, last_name=last, email=f"{local}@acibadem.edu.tr"
            )
            for role in roles:
                ProgramMembership.objects.create(user=user, program=self.program, role=role)
            staff[local] = user
        return staff

    def create_students(self, per_cohort):
        students = []
        for cohort in (2023, 2024, 2025):
            count = per_cohort - 1 if cohort == ELIF["cohort_year"] else per_cohort
            for i in range(1, count + 1):
                first, last = self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)
                local = f"{first}.{last}".lower().translate(ASCII).replace(" ", "")
                students.append(
                    self.create_user(
                        first_name=first,
                        last_name=last,
                        email=f"{local}.{cohort}{i:02d}@live.acibadem.edu.tr",
                        student_number=f"{cohort}-{i:04d}",
                        cohort_year=cohort,
                    )
                )
        self.ability = {s.id: self.rng.gauss(72, 11) for s in students}
        return students

    def create_offering(self, spec):
        term = self.terms[spec["term"]]
        course = Course.objects.create(
            program=self.program,
            code=spec["code"],
            title=spec["title"],
            credits=Decimal(spec["credits"]),
            ects=Decimal(spec["ects"]),
        )
        offering = CourseOffering.objects.create(course=course, term=term)
        offering.instructors.add(self.staff[spec["instructor"]])

        los = {
            n: LearningOutcome.objects.create(offering=offering, number=n, description=text)
            for n, text in enumerate(spec["los"], start=1)
        }
        published_at = timezone.make_aware(
            datetime.datetime.combine(
                min(term.ends_on, datetime.date(2026, 11, 6)), datetime.time(12)
            )
        )
        assessments = {}
        for position, (name, kind, max_score, weight, published) in enumerate(spec["assessments"]):
            assessments[name] = Assessment.objects.create(
                offering=offering,
                name=name,
                kind=kind,
                max_score=Decimal(max_score),
                course_weight=Decimal(weight),
                position=position,
                published_at=published_at if published else None,
            )
        for name, targets in spec["a_lo"].items():
            for lo_number, weight in targets.items():
                AssessmentLOWeight.objects.create(
                    assessment=assessments[name],
                    learning_outcome=los[lo_number],
                    weight=Decimal(weight),
                )
        for lo_number, targets in spec["lo_po"].items():
            for po_number, weight in targets.items():
                LOPOWeight.objects.create(
                    learning_outcome=los[lo_number],
                    program_outcome=self.pos[po_number],
                    weight=weight,
                )

        is_elifs_course = spec["code"] == "CSE 311"
        takers = [
            s
            for s in self.students[1:]
            if s.memberships.get(role="student").cohort_year in spec["cohorts"]
        ]
        if is_elifs_course:
            takers = [self.elif_, *takers]

        grades = []
        for student in takers:
            enrollment = Enrollment.objects.create(offering=offering, student=student)
            for name, assessment in assessments.items():
                if student is self.elif_:
                    mark, excused = ELIF["marks"].get(name), False
                    if mark is None:
                        continue
                else:
                    mark, excused = self.random_mark(student, assessment)
                    if mark is None and not excused:
                        continue
                if assessment.published_at is None and self.rng.random() < 0.5:
                    continue
                grade = Grade(
                    assessment=assessment,
                    enrollment=enrollment,
                    score=mark,
                    is_excused=excused,
                    updated_by=self.staff[spec["instructor"]],
                )
                if assessment.published_at is not None:
                    grade.published_score = mark
                    grade.published_is_excused = excused
                    grade.published_at = assessment.published_at
                grades.append(grade)
        Grade.objects.bulk_create(grades)

    def random_mark(self, student, assessment):
        roll = self.rng.random()
        if roll < 0.02:
            return None, True
        if roll < 0.07:
            return None, False
        percent = min(100.0, max(0.0, self.ability[student.id] + self.rng.gauss(0, 9)))
        mark = assessment.max_score * Decimal(str(percent)) / 100
        return (mark * 2).quantize(Decimal("1")) / 2, False

    def report(self):
        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(f"Every demo account's password: {DEMO_PASSWORD}")
        self.stdout.write("  Head (also teaches CSE 311): deniz.kara@acibadem.edu.tr")
        self.stdout.write("  Instructors: can.aydin@, ayse.demir@, mehmet.sahin@acibadem.edu.tr")
        self.stdout.write(f"  Student Elif (slide example): {ELIF['email']}")
        self.stdout.write(
            f"  {User.objects.filter(memberships__role='student').count()} students, "
            f"{CourseOffering.objects.count()} offerings, {Grade.objects.count()} grades"
        )
