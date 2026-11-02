"""The demo department (spec Appendix B), as plain data. Edit here to change the demo story."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class LOSpec:
    text: str
    po: dict[int, int]  # PO number -> weight 1..5


@dataclass(frozen=True)
class AssessmentSpec:
    name: str
    kind: str  # Assessment.Kind value
    max_score: int
    course_weight: int  # % of the course grade
    lo: dict[int, int]  # LO number (1-based) -> weight %


@dataclass(frozen=True)
class CourseSpec:
    code: str
    title: str
    credits: str
    ects: str
    los: tuple[LOSpec, ...]
    assessments: tuple[AssessmentSpec, ...]


@dataclass(frozen=True)
class OfferingSpec:
    course: str
    term: str
    teacher: str  # key in PEOPLE
    cohorts: tuple[str, ...]  # "2023", "2024", "2025", or "retake"
    published: str | tuple[str, ...] = "all"  # "all", "none", or assessment names
    mapped: bool = True
    unpublished_change: bool = False
    elif_here: bool = False


TERMS = (
    ("2025F", "Fall 2025", date(2025, 9, 15), date(2026, 1, 23), "closed"),
    ("2026S", "Spring 2026", date(2026, 2, 9), date(2026, 6, 19), "closed"),
    ("2026F", "Fall 2026", date(2026, 9, 14), date(2027, 1, 22), "open"),
)

# key: (first name, last name, email local part, roles)
PEOPLE = {
    "head": ("Deniz", "Kara", "deniz.kara", ("head", "instructor")),
    "can": ("Can", "Aydın", "can.aydin", ("instructor",)),
    "ayse": ("Ayşe", "Demir", "ayse.demir", ("instructor",)),
    "mehmet": ("Mehmet", "Şahin", "mehmet.sahin", ("instructor",)),
}

ELIF = {
    "first_name": "Elif",
    "last_name": "Yıldız",
    "email": "elif.yildiz@polaris.test",
    "student_number": "2024-0041",
    "cohort_year": 2024,
    "grades": {"Midterm I": 90, "Project": 80},
}

COHORTS = (2023, 2024, 2025)

FIRST_NAMES = (
    "Ahmet",
    "Ayşe",
    "Mehmet",
    "Zeynep",
    "Mustafa",
    "Elif",
    "Ali",
    "Merve",
    "Hüseyin",
    "Esra",
    "Emre",
    "Büşra",
    "Burak",
    "Selin",
    "Can",
    "Ceren",
    "Kerem",
    "Damla",
    "Oğuz",
    "İrem",
    "Yusuf",
    "Gizem",
    "Barış",
    "Defne",
    "Serkan",
    "Ebru",
    "Tolga",
    "Nazlı",
    "Onur",
    "Şeyma",
    "Berk",
    "Ece",
    "Umut",
    "Dilara",
    "Kaan",
    "Melis",
    "Furkan",
    "Gamze",
    "Arda",
    "Özge",
)
LAST_NAMES = (
    "Yılmaz",
    "Kaya",
    "Demir",
    "Çelik",
    "Şahin",
    "Yıldız",
    "Yıldırım",
    "Öztürk",
    "Aydın",
    "Özdemir",
    "Arslan",
    "Doğan",
    "Kılıç",
    "Aslan",
    "Çetin",
    "Kara",
    "Koç",
    "Kurt",
    "Özkan",
    "Şimşek",
    "Polat",
    "Korkmaz",
    "Erdoğan",
    "Güneş",
    "Aktaş",
    "Bulut",
    "Tekin",
    "Uçar",
    "Karaca",
    "Ateş",
)

A = AssessmentSpec
L = LOSpec

COURSES: dict[str, CourseSpec] = {
    c.code: c
    for c in (
        CourseSpec(
            "CSE 101",
            "Introduction to Programming",
            "4",
            "6",
            (
                L(
                    "Write, test and debug small Python programs using variables, conditionals, loops and functions.",
                    {1: 2, 2: 4, 4: 3},
                ),
                L(
                    "Decompose a problem into functions and choose suitable built-in data structures.",
                    {2: 4, 3: 3},
                ),
                L(
                    "Use an editor, the terminal and version control to manage their own code.",
                    {4: 4, 8: 2},
                ),
            ),
            (
                A("Quiz", "quiz", 20, 10, {1: 100}),
                A("Midterm", "midterm", 100, 30, {1: 60, 2: 40}),
                A("Lab assignments", "lab", 100, 20, {1: 40, 3: 100}),
                A("Final", "final", 100, 40, {1: 50, 2: 60}),
            ),
        ),
        CourseSpec(
            "CSE 102",
            "Object-Oriented Programming",
            "4",
            "6",
            (
                L(
                    "Model a problem domain with classes, objects, inheritance and interfaces.",
                    {2: 3, 3: 4},
                ),
                L(
                    "Apply exception handling, unit testing and simple design patterns in Java.",
                    {3: 3, 4: 4},
                ),
                L("Develop a small team project with a shared repository.", {6: 4, 4: 2, 7: 2}),
            ),
            (
                A("Quiz", "quiz", 20, 10, {1: 100}),
                A("Midterm", "midterm", 100, 30, {1: 70, 2: 30}),
                A("Project", "project", 100, 30, {1: 30, 2: 40, 3: 100}),
                A("Final", "final", 100, 30, {1: 50, 2: 50}),
            ),
        ),
        CourseSpec(
            "CSE 211",
            "Data Structures",
            "4",
            "6",
            (
                L("Implement lists, stacks, queues, trees, heaps and hash tables.", {1: 3, 2: 4}),
                L(
                    "Analyse the time and space complexity of algorithms with asymptotic notation.",
                    {1: 5, 2: 3},
                ),
                L(
                    "Choose an appropriate data structure for a given problem and justify the choice.",
                    {2: 4, 3: 3},
                ),
                L("Write programs that process large inputs efficiently.", {4: 3, 5: 2}),
            ),
            (
                A("Midterm", "midterm", 100, 30, {1: 50, 2: 50}),
                A("Homework", "homework", 100, 20, {1: 60, 4: 100}),
                A("Final", "final", 100, 50, {1: 40, 2: 50, 3: 100}),
            ),
        ),
        CourseSpec(
            "CSE 221",
            "Digital Logic Design",
            "3",
            "5",
            (
                L("Simplify Boolean functions with Boolean algebra and Karnaugh maps.", {1: 5}),
                L("Design and analyse combinational circuits.", {1: 3, 3: 4}),
                L(
                    "Design sequential circuits with flip-flops and finite state machines.",
                    {3: 4, 5: 3},
                ),
                L(
                    "Build and test circuits in the laboratory and report the results.",
                    {5: 4, 7: 2, 6: 2},
                ),
            ),
            (
                A("Midterm", "midterm", 100, 30, {1: 60, 2: 40}),
                A("Lab assignments", "lab", 100, 25, {4: 100, 2: 30}),
                A("Final", "final", 100, 45, {1: 40, 2: 40, 3: 100}),
            ),
        ),
        CourseSpec(
            "CSE 231",
            "Algorithms",
            "4",
            "6",
            (
                L(
                    "Design algorithms with divide and conquer, greedy and dynamic programming strategies.",
                    {2: 5, 3: 3},
                ),
                L(
                    "Prove the correctness of algorithms and analyse their running time.",
                    {1: 4, 2: 3},
                ),
                L(
                    "Apply graph algorithms (BFS, DFS, shortest paths, spanning trees) to practical problems.",
                    {2: 3, 4: 2},
                ),
            ),
            (
                A("Quiz", "quiz", 20, 10, {2: 100}),
                A("Midterm", "midterm", 100, 35, {1: 60, 2: 60}),
                A("Homework", "homework", 100, 15, {1: 50, 3: 50}),
                A("Final", "final", 100, 40, {1: 40, 2: 40, 3: 100}),
            ),
        ),
        # CSE 311 is the professor's slide example. Do not change its LOs, weights or assessment names.
        CourseSpec(
            "CSE 311",
            "Software Engineering",
            "3",
            "5",
            (
                L(
                    "Learn the design choices and philosophy behind building software products.",
                    {1: 4},
                ),
                L("Learn agile software development methodology and best practices.", {1: 2, 2: 5}),
            ),
            (
                A("Midterm I", "midterm", 100, 25, {1: 60, 2: 40}),
                A("Project", "project", 100, 40, {1: 40, 2: 100}),
                A("Final exam", "final", 100, 35, {1: 50, 2: 50}),
            ),
        ),
        CourseSpec(
            "CSE 321",
            "Data Systems",
            "3",
            "5",
            (
                L(
                    "Design relational schemas and normalise them to third normal form.",
                    {3: 4, 2: 2},
                ),
                L(
                    "Write SQL queries with joins, aggregation, subqueries and window functions.",
                    {4: 4, 2: 3},
                ),
                L(
                    "Explain transactions, isolation levels and indexing, and their effect on performance.",
                    {1: 3, 5: 2},
                ),
                L("Present the data architecture of a team project.", {7: 4, 6: 3, 10: 2}),
            ),
            (
                A("Midterm", "midterm", 100, 30, {1: 50, 2: 50, 3: 40}),
                A("Project", "project", 100, 40, {1: 50, 4: 100, 2: 30}),
                A("Final", "final", 100, 30, {2: 20, 3: 60}),
            ),
        ),
        CourseSpec(
            "CSE 331",
            "Operating Systems",
            "4",
            "6",
            (
                L("Explain processes, threads, scheduling and synchronisation.", {1: 3, 2: 3}),
                L(
                    "Write concurrent programs that avoid race conditions and deadlocks.",
                    {2: 4, 4: 3},
                ),
                L("Describe memory management, virtual memory and file systems.", {1: 4}),
            ),
            (
                A("Midterm", "midterm", 100, 30, {1: 60, 3: 40}),
                A("Lab assignments", "lab", 100, 30, {2: 100}),
                A("Final", "final", 100, 40, {1: 40, 3: 60, 2: 20}),
            ),
        ),
        # The only course linked to PO 9 (Appendix B: "PO 9 covered by only one course").
        CourseSpec(
            "CSE 341",
            "Professional Practice and Ethics in Computing",
            "2",
            "3",
            (
                L(
                    "Analyse ethical dilemmas in computing using professional codes of conduct.",
                    {9: 5, 7: 2},
                ),
                L(
                    "Discuss the legal, social and economic impact of software systems.",
                    {8: 3, 10: 3},
                ),
                L("Write and present a technical report as a team.", {7: 4, 6: 3}),
            ),
            (
                A("Case study essays", "homework", 100, 30, {1: 100, 2: 50}),
                A("Presentation", "presentation", 100, 30, {3: 100}),
                A("Final", "final", 100, 40, {1: 50, 2: 50}),
            ),
        ),
        CourseSpec(
            "MAT 141",
            "Calculus I",
            "4",
            "6",
            (
                L("Compute limits and derivatives and use them to analyse functions.", {1: 5}),
                L("Evaluate definite and indefinite integrals with standard techniques.", {1: 5}),
                L(
                    "Model rates of change and optimisation problems from science and engineering.",
                    {1: 3, 2: 3},
                ),
            ),
            (
                A("Quiz", "quiz", 20, 15, {1: 100}),
                A("Midterm", "midterm", 100, 35, {1: 60, 2: 30}),
                A("Final", "final", 100, 50, {1: 40, 2: 70, 3: 100}),
            ),
        ),
        CourseSpec(
            "MAT 241",
            "Linear Algebra",
            "3",
            "5",
            (
                L(
                    "Solve systems of linear equations with Gaussian elimination and matrix methods.",
                    {1: 5},
                ),
                L("Work with vector spaces, bases, eigenvalues and eigenvectors.", {1: 4, 2: 2}),
                L(
                    "Apply linear algebra to problems in computer graphics and data analysis.",
                    {2: 3, 4: 2},
                ),
            ),
            (
                A("Midterm", "midterm", 100, 40, {1: 60, 2: 40}),
                A("Homework", "homework", 100, 20, {2: 50, 3: 100}),
                A("Final", "final", 100, 40, {1: 40, 2: 60, 3: 50}),
            ),
        ),
        CourseSpec(
            "PHY 101",
            "Physics I",
            "4",
            "6",
            (
                L(
                    "Apply Newton's laws and conservation principles to mechanical systems.",
                    {1: 5, 2: 2},
                ),
                L(
                    "Carry out laboratory experiments, analyse measurement uncertainty and report results.",
                    {5: 5, 7: 2},
                ),
                L("Solve kinematics and dynamics problems with calculus.", {1: 4, 2: 3}),
            ),
            (
                A("Midterm", "midterm", 100, 30, {1: 60, 3: 50}),
                A("Lab assignments", "lab", 100, 20, {2: 100}),
                A("Final", "final", 100, 50, {1: 40, 3: 50}),
            ),
        ),
    )
}

OFFERINGS: tuple[OfferingSpec, ...] = (
    OfferingSpec("CSE 101", "2025F", "can", ("2025",)),
    OfferingSpec("MAT 141", "2025F", "ayse", ("2025",)),
    OfferingSpec("PHY 101", "2025F", "mehmet", ("2025",)),
    OfferingSpec("CSE 211", "2025F", "can", ("2024",)),
    OfferingSpec("CSE 221", "2025F", "mehmet", ("2024",)),
    OfferingSpec("CSE 331", "2025F", "head", ("2023",)),
    OfferingSpec("CSE 102", "2026S", "can", ("2025",)),
    OfferingSpec("MAT 241", "2026S", "ayse", ("2025",)),
    OfferingSpec("CSE 231", "2026S", "head", ("2024",)),
    OfferingSpec("CSE 341", "2026S", "ayse", ("2023",)),
    OfferingSpec("CSE 311", "2026F", "head", ("2024",), published=("Midterm I", "Project"), elif_here=True),
    OfferingSpec("CSE 321", "2026F", "can", ("2024",), published=("Midterm",), unpublished_change=True),
    OfferingSpec("CSE 211", "2026F", "can", ("2025",), published=("Midterm",)),
    OfferingSpec("CSE 221", "2026F", "mehmet", ("2025",), published="none", mapped=False),
    OfferingSpec("CSE 101", "2026F", "can", ("retake",), published=("Quiz", "Midterm")),
)

RETAKERS = 3  # weakest students of cohort 2025 retake CSE 101
