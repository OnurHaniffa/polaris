# Build guide · Sprints 8–10: Tier 2, reports, freeze

This chapter covers the last three sprints, from Mon 7 Dec to Sun 27 Dec. By the time you open it, Baseline and Tier 1 are on production. That was the target for Sun 6 Dec. These three sprints do three things:

1. **Sprint 8 (7–13 Dec):** first absorb anything left over from Sprints 6–7 and the bugs found in the Sprint 7 demo run. Then build the Tier 2 features that make the product feel finished: cloning last term's setup, precomputed scores, reminder emails and the PO transcript.
2. **Sprint 9 (14–20 Dec):** first drafts of both final reports, plus the Tier 2 features that widen the product: Turkish, error monitoring, the TA role, OBS import and a second program.
3. **Sprint 10 (21–27 Dec):** feature freeze from Monday. Bug bash, demo data, backup video, printed reports and the `v1.0.0` release.

**How to read a story section.** Every story has the same parts: Goal, Files, Steps (why, then complete code), Tests, Check it works, Done when, and Commits and PR. Code uses the exact names from the spec's [§4.8 Code map](../../POLARIS-PROJECT-SPEC.md#48-code-map-every-module-public-name-and-url). Names this chapter adds are listed under [Code map additions](#code-map-additions) at the end. Copy them into §4.8 in the same PR that adds the code.

**The Tier 2 rule.** Tier 2 is committed scope, but it comes after the buffer. If Sprint 8 opens with more than 8 points of carry-over, drop stories from the bottom of each sprint table, never from the top. Write the drop into `docs/process/velocity.md` with the reason. A dropped story is evidence of good Scrum, not a failure.

---

# Sprint 8 — Buffer, then Tier 2 (Mon 7 – Sun 13 Dec)

**Sprint goal:** *"An instructor can set up next term in one click, the department dashboard loads instantly, late instructors get reminded automatically, and a student can download a verifiable PO transcript."*

| Order | ID | Story | Pts | Owner |
|---|---|---|---|---|
| 0 | — | Carry-overs from Sprints 6–7, then bugs from the Sprint 7 demo run | — | whoever owns them |
| 1 | S8-02 | T2.3 Precomputed score tables, materialized views, `refresh_scores` | 5 | A |
| 2 | S8-01 | T2.1 Clone last term's setup | 2 | B |
| 3 | S8-04 | T2.4 PO transcript PDF | 3 | B |
| 4 | S8-03 | T2.2 Completion tracker and reminder emails (Celery beat) | 5 | C |

**Merge order.** S8-02 first: it adds `scoring` migrations, and every later migration in the sprint depends on them in the graph. S8-01 and S8-04 don't touch each other and can merge in either order. S8-03 last, because it adds a new container (`beat`) to `compose.prod.yml`. That's the riskiest deploy change of the sprint, so it should land on a quiet staging.

**What must work on staging by Sunday:**
- Head dashboard renders from snapshot tables, and `rebuild_scores --check` reports `0 mismatches`.
- A new 2027S offering of CSE 311 gets last term's setup in one click.
- `beat` is running. A head-set deadline in the past triggers exactly one reminder email per instructor per day, visible in the console log on staging.
- Elif downloads her transcript. Its verification link opens a public page with the same numbers.

---

## S8-02 · Precomputed scores and materialized views (T2.3)

**Points:** 5 · **Owner:** Person A · **Branch:** `feature/S8-02-score-snapshots` · **Depends on:** S1-06, S1-07, S3-04, S6-05, S7-01

### Goal

Today every dashboard request runs the engine for every student in the program. This story writes the engine's results into two tables after anything changes. It also adds two PostgreSQL **materialized views** that aggregate those tables. The department dashboard then reads a few hundred precomputed rows instead of recomputing tens of thousands of grades. This is the story that gives the CSE 321 report Section 4 its "materialized views" content, with real `EXPLAIN ANALYZE` numbers before and after. It delivers spec T2.3 AC 1–4 (see the Tier 2 spec in Part 6).

The rule that keeps this safe: **the snapshot tables are written by Python, using the same engine.** SQL never computes a score. The views only count and sum numbers the engine already produced. If a snapshot and a live calculation ever disagree, `rebuild_scores --check` finds it and the test suite fails.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/scoring/models.py` | modify (was empty) | `StudentLOScore`, `StudentPOScore` |
| `apps/scoring/migrations/0001_initial.py` | create (generated) | The two tables |
| `apps/scoring/migrations/0002_materialized_views.py` | create (hand-written) | Both materialized views and their unique indexes |
| `apps/scoring/snapshots.py` | create | `snapshot_offering`, `snapshot_student`, `refresh_views`, `read_coverage`, `read_attainment` |
| `apps/scoring/tasks.py` | create | `refresh_scores`, `refresh_materialized_views`, `schedule_refresh` |
| `apps/scoring/management/commands/rebuild_scores.py` | create | Full rebuild and `--check` mode |
| `apps/scoring/aggregates.py` | modify | `attainment_matrix` and `coverage_matrix` read from the views when `settings.USE_SCORE_SNAPSHOTS` is on |
| `apps/grading/services.py`, `apps/outcomes/services.py`, `apps/ingestion/services.py` | modify | Call `schedule_refresh(offering)` after each write that changes scores |
| `config/settings/base.py`, `test.py` | modify | `USE_SCORE_SNAPSHOTS` flag |
| `apps/scoring/tests/test_snapshots.py` | create | Snapshot equals engine, views aggregate correctly, idempotency |

### Steps

**1. The two snapshot models.**

`StudentLOScore` has one row per (enrollment, LO): the LO score the engine gives that student in that offering. `StudentPOScore` has one row per (student, PO, scope). Scope `cumulative` is "everything up to now", which is what the profile shows. Scope `term` with a `term` set is "everything up to and including that term". That is the series the T1.5 trend chart draws and what the attainment view groups by.

The cumulative row has `term = NULL`. Normally PostgreSQL treats two NULLs as different, so a plain unique constraint would let duplicate cumulative rows in. `nulls_distinct=False` (PostgreSQL 15+, Django 5.0+) makes NULL count as one value for this constraint. That's exactly the rule we want, and it's worth one sentence in the CSE 321 report.

```python
# apps/scoring/models.py
"""Precomputed engine results (T2.3). Written only by apps/scoring/snapshots.py."""
from django.conf import settings
from django.db import models
from django.db.models import Q


class StudentLOScore(models.Model):
    enrollment = models.ForeignKey("catalog.Enrollment", on_delete=models.CASCADE,
                                   related_name="lo_snapshots")
    learning_outcome = models.ForeignKey("outcomes.LearningOutcome", on_delete=models.CASCADE,
                                         related_name="snapshots")
    score = models.DecimalField(max_digits=30, decimal_places=20, null=True)
    coverage = models.DecimalField(max_digits=21, decimal_places=20)
    computed_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "learning_outcome"], name="uniq_lo_snapshot"),
        ]


class StudentPOScore(models.Model):
    class Scope(models.TextChoices):
        CUMULATIVE = "cumulative", "Cumulative (now)"
        TERM = "term", "Up to and including a term"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="po_snapshots")
    program_outcome = models.ForeignKey("catalog.ProgramOutcome", on_delete=models.CASCADE,
                                        related_name="snapshots")
    scope = models.CharField(max_length=10, choices=Scope.choices)
    term = models.ForeignKey("catalog.Term", null=True, blank=True, on_delete=models.CASCADE,
                             related_name="+")
    score = models.DecimalField(max_digits=30, decimal_places=20, null=True)
    coverage = models.DecimalField(max_digits=21, decimal_places=20)
    computed_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "program_outcome", "scope", "term"],
                                    nulls_distinct=False, name="uniq_po_snapshot"),
            models.CheckConstraint(
                condition=(Q(scope="cumulative") & Q(term__isnull=True))
                | (Q(scope="term") & Q(term__isnull=False)),
                name="po_snapshot_scope_term",
            ),
        ]
        indexes = [models.Index(fields=["program_outcome", "scope", "term"], name="po_snapshot_po_idx")]
```

Why `max_digits=30, decimal_places=20`: P7 says no intermediate rounding. The engine produces `Decimal` values like `82.857142857142857142857…`. If we stored them rounded to two places, the dashboard average of stored values would differ from the live average in the last digit, and the snapshot-equals-engine test could never pass exactly. Twenty decimal places is far beyond what any display needs, and the test compares at that precision. It's the same tolerance the engine tests use (1e-20).

```bash
uv run python manage.py makemigrations scoring
```

**2. The materialized views, as a hand-written migration.**

Django has no model type for a materialized view, so we write the SQL ourselves with `migrations.RunSQL`. Each `RunSQL` gets a `reverse_sql` so `migrate scoring 0001` can undo it (rule 7 of the review checklist: migrations must be reversible).

`REFRESH MATERIALIZED VIEW CONCURRENTLY` lets the dashboard keep reading the old rows while the refresh runs, so nobody waits. PostgreSQL only allows it when the view has a **unique index** that covers every row. That's why each view gets one.

Table names are Django's defaults: `<app_label>_<model_name>`, all lower case.

```python
# apps/scoring/migrations/0002_materialized_views.py
from django.db import migrations

COVERAGE_SQL = """
CREATE MATERIALIZED VIEW mv_course_po_coverage AS
SELECT lo.offering_id,
       w.program_outcome_id,
       SUM(w.weight)                        AS total_weight,
       COUNT(DISTINCT w.learning_outcome_id) AS lo_count
FROM outcomes_lopoweight w
JOIN outcomes_learningoutcome lo ON lo.id = w.learning_outcome_id
GROUP BY lo.offering_id, w.program_outcome_id
WITH DATA;

CREATE UNIQUE INDEX mv_course_po_coverage_key
    ON mv_course_po_coverage (offering_id, program_outcome_id);
"""

ATTAINMENT_SQL = """
CREATE MATERIALIZED VIEW mv_po_attainment AS
SELECT p.id                     AS program_id,
       m.cohort_year,
       s.term_id,
       s.program_outcome_id,
       COUNT(*) FILTER (WHERE s.score IS NOT NULL)                       AS students_scored,
       COUNT(*) FILTER (WHERE s.score >= p.attainment_threshold)         AS students_attaining,
       AVG(s.score)                                                      AS mean_score
FROM scoring_studentposcore s
JOIN catalog_programoutcome     po ON po.id = s.program_outcome_id
JOIN catalog_programoutcomeset  ps ON ps.id = po.po_set_id
JOIN catalog_program            p  ON p.id  = ps.program_id
JOIN accounts_programmembership m  ON m.user_id = s.student_id
                                  AND m.program_id = p.id
                                  AND m.role = 'student'
WHERE s.scope = 'term'
GROUP BY p.id, m.cohort_year, s.term_id, s.program_outcome_id
WITH DATA;

CREATE UNIQUE INDEX mv_po_attainment_key
    ON mv_po_attainment (program_id, cohort_year, term_id, program_outcome_id);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("scoring", "0001_initial"),
        ("outcomes", "0001_initial"),
        ("catalog", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(COVERAGE_SQL, reverse_sql="DROP MATERIALIZED VIEW mv_course_po_coverage;"),
        migrations.RunSQL(ATTAINMENT_SQL, reverse_sql="DROP MATERIALIZED VIEW mv_po_attainment;"),
    ]
```

The dependencies only need the tables to *exist*, and they do from each app's `0001_initial`. Pointing at `0001` instead of the latest migration keeps this file stable when someone adds a column later.

Note what the attainment view does **not** store: the rate. It stores the two counts, and the rate (`attaining ÷ scored`) is computed when read. Storing counts lets the dashboard combine several terms or cohorts correctly: add the counts, then divide. Averaging rates would be wrong whenever groups have different sizes. Say this in the CSE 321 report too. It is the classic "additive vs non-additive measure" point from star-schema design.

`mean_score` is an `AVG` of already-computed engine scores. That's an aggregation, not scoring logic, so it doesn't break the "one engine" rule. The department overview's "average per PO" (B10) is defined as exactly this mean (§2.5: class and cohort numbers are means of per-student results).

**3. The snapshot writer.**

`snapshot_offering` does two things for one offering: it rewrites the LO rows of every enrolled student, then rewrites the PO rows of those same students. A student's PO scores depend on all their courses, so the PO step recomputes the whole student, not just this offering's share.

Upserts use `bulk_create(update_conflicts=True, …)`, which compiles to PostgreSQL `INSERT … ON CONFLICT DO UPDATE`. A refresh is then **idempotent**: running it twice gives the same rows, so a Celery retry or two refreshes racing each other can't create duplicates. Stale PO rows (for example a term the student no longer has) are deleted in the same transaction.

```python
# apps/scoring/snapshots.py
"""Write engine results into the snapshot tables and read the materialized views (T2.3).

Scores are computed ONLY by apps.scoring.engine. This module stores them and reads
SQL aggregates of what was stored. It never computes a score itself."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import connection, transaction
from django.utils import timezone

from apps.catalog.models import CourseOffering, Enrollment, Term
from apps.catalog.selectors import po_set_for_student
from apps.scoring.engine import compute_student_profile
from apps.scoring.loaders import load_offering_inputs, load_student_inputs
from apps.scoring.models import StudentLOScore, StudentPOScore


def snapshot_offering(offering: CourseOffering) -> int:
    """Recompute LO rows for every enrolled student of `offering`, then their PO rows.
    Returns the number of students refreshed."""
    now = timezone.now()
    lo_rows: list[StudentLOScore] = []
    for enrollment_id, inputs in load_offering_inputs(offering).items():
        profile = compute_student_profile([inputs])
        for (_offering_id, lo_id), node in profile.lo_scores.items():
            lo_rows.append(StudentLOScore(
                enrollment_id=enrollment_id, learning_outcome_id=lo_id,
                score=node.score, coverage=node.coverage, computed_at=now,
            ))
    student_ids = list(
        Enrollment.objects.filter(offering=offering, status=Enrollment.Status.ENROLLED)
        .values_list("student_id", flat=True)
    )
    with transaction.atomic():
        existing = StudentLOScore.objects.filter(enrollment__offering=offering)
        if not lo_rows:
            existing.delete()
        else:
            StudentLOScore.objects.bulk_create(
                lo_rows, update_conflicts=True,
                unique_fields=["enrollment", "learning_outcome"],
                update_fields=["score", "coverage", "computed_at"],
            )
            kept = {(r.enrollment_id, r.learning_outcome_id) for r in lo_rows}
            stale = [pk for pk, e_id, lo_id
                     in existing.values_list("pk", "enrollment_id", "learning_outcome_id")
                     if (e_id, lo_id) not in kept]
            StudentLOScore.objects.filter(pk__in=stale).delete()
        for student_id in student_ids:
            _snapshot_student_id(student_id, offering.course.program, now)
    return len(student_ids)


def snapshot_student(student, program) -> None:
    with transaction.atomic():
        _snapshot_student_id(student.pk, program, timezone.now())


def _snapshot_student_id(student_id: int, program, now) -> None:
    from apps.accounts.models import User

    student = User.objects.get(pk=student_id)
    po_ids = set(po_set_for_student(student, program).outcomes.values_list("id", flat=True))

    rows: list[StudentPOScore] = []
    cumulative = compute_student_profile(load_student_inputs(student))
    for po_id, node in cumulative.po_scores.items():
        if po_id in po_ids:
            rows.append(StudentPOScore(student_id=student_id, program_outcome_id=po_id,
                                       scope=StudentPOScore.Scope.CUMULATIVE, term=None,
                                       score=node.score, coverage=node.coverage, computed_at=now))

    terms = Term.objects.filter(offerings__enrollments__student_id=student_id).distinct()
    for term in terms:
        profile = compute_student_profile(load_student_inputs(student, up_to_term=term))
        for po_id, node in profile.po_scores.items():
            if po_id in po_ids:
                rows.append(StudentPOScore(student_id=student_id, program_outcome_id=po_id,
                                           scope=StudentPOScore.Scope.TERM, term=term,
                                           score=node.score, coverage=node.coverage,
                                           computed_at=now))

    # Replace this student's rows as a whole: simpler than diffing, and the
    # surrounding transaction means readers never see a half-written student.
    StudentPOScore.objects.filter(student_id=student_id).delete()
    StudentPOScore.objects.bulk_create(rows)


def refresh_views() -> None:
    """Refresh both materialized views without blocking readers."""
    with connection.cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_course_po_coverage")
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_po_attainment")


@dataclass(frozen=True)
class AttainmentCell:
    students_scored: int
    students_attaining: int
    mean_score: Decimal | None

    @property
    def rate(self) -> Decimal | None:
        if self.students_scored == 0:
            return None
        return Decimal(self.students_attaining) / Decimal(self.students_scored)


def read_attainment(program_id: int, *, term_ids: list[int], cohort: int | None = None,
                    by: str = "cohort") -> dict[tuple[int, int], AttainmentCell]:
    """(po_id, cohort_year or term_id) -> AttainmentCell, summing counts across the
    selected terms. `by` is "cohort" or "term"."""
    if by not in {"cohort", "term"}:
        raise ValueError("by must be 'cohort' or 'term'")
    group_col = "cohort_year" if by == "cohort" else "term_id"
    sql = f"""
        SELECT program_outcome_id, {group_col},
               SUM(students_scored), SUM(students_attaining),
               SUM(mean_score * students_scored) / NULLIF(SUM(students_scored), 0)
        FROM mv_po_attainment
        WHERE program_id = %s AND term_id = ANY(%s)
          AND (%s::int IS NULL OR cohort_year = %s::int)
        GROUP BY program_outcome_id, {group_col}
    """
    with connection.cursor() as cur:
        cur.execute(sql, [program_id, term_ids, cohort, cohort])
        return {
            (po_id, key): AttainmentCell(int(scored or 0), int(attaining or 0), mean)
            for po_id, key, scored, attaining, mean in cur.fetchall()
        }


def read_coverage(program_id: int, *, term_ids: list[int]) -> dict[tuple[int, int], Decimal]:
    """(offering_id, po_id) -> sum of LO->PO weights, for offerings in the given terms."""
    sql = """
        SELECT v.offering_id, v.program_outcome_id, v.total_weight
        FROM mv_course_po_coverage v
        JOIN catalog_courseoffering o ON o.id = v.offering_id
        JOIN catalog_course c         ON c.id = o.course_id
        WHERE c.program_id = %s AND o.term_id = ANY(%s)
    """
    with connection.cursor() as cur:
        cur.execute(sql, [program_id, term_ids])
        return {(off, po): Decimal(total) for off, po, total in cur.fetchall()}
```

`group_col` is inserted with an f-string, but only from a fixed allow-list, which we check first. Every value that comes from a user goes through `%s` parameters. Never format user input into SQL (ruff's `S608` rule would flag it anyway).

If the offering now has no LO scores at all (every LO was deleted), the old rows are deleted outright. Otherwise new rows are upserted, then any row whose (enrollment, LO) pair is no longer produced is deleted as stale.

**4. The Celery tasks and the one-line trigger.**

Services must not call the task directly. A task that starts before the service's transaction commits would read the *old* data. `transaction.on_commit` runs the callback only after a successful commit, and never after a rollback (§4.4 rule 2). `schedule_refresh` wraps that so each service adds one line.

```python
# apps/scoring/tasks.py
from celery import shared_task
from django.conf import settings
from django.db import transaction

from apps.catalog.models import CourseOffering

from .snapshots import refresh_views, snapshot_offering


@shared_task(acks_late=True, autoretry_for=(Exception,), retry_backoff=10, max_retries=3)
def refresh_scores(offering_id: int) -> int:
    """Rewrite snapshots for one offering's students, then refresh both views."""
    offering = CourseOffering.objects.select_related("course__program").filter(pk=offering_id).first()
    if offering is None:            # deleted meanwhile: nothing to do
        return 0
    count = snapshot_offering(offering)
    refresh_views()
    return count


@shared_task
def refresh_materialized_views() -> None:
    """Nightly safety net (Celery beat) and used after mapping-only changes."""
    refresh_views()


def schedule_refresh(offering) -> None:
    """Call from inside a service's atomic() block. Runs after commit, never on rollback."""
    if not getattr(settings, "USE_SCORE_SNAPSHOTS", True):
        return
    offering_id = offering.pk
    transaction.on_commit(lambda: refresh_scores.delay(offering_id))
```

`autoretry_for=(Exception,)` is broader than our usual rule. It's acceptable here because the task is idempotent and only reads and writes our own database. A transient deadlock or connection blip should just be retried.

**5. Call `schedule_refresh` from every write that changes a score.**

Add one line inside the `atomic()` block of each of these services, after the writes and the `audit.record` call:

| Service | Why it changes scores |
|---|---|
| `grading.services.publish_assessment` | Published grades are the engine's input (P4) |
| `grading.services.unpublish_assessment` | Same, in reverse |
| `outcomes.services.save_assessment_lo_matrix` | Changes the edges assessment → LO |
| `outcomes.services.save_lo_po_matrix` | Changes the edges LO → PO |
| `outcomes.services.update_assessment` | `max_score` change renormalises every grade (P3) |
| `outcomes.services.delete_assessment`, `delete_lo` | Removes sources or nodes |
| `outcomes.services.accept_suggestions` | Changes LO→PO weights' source only, but run it anyway: cheap and keeps the rule simple |
| `ingestion.services.apply_syllabus_job` | Creates the whole mapping |
| `catalog.services.enroll`, `drop` | Adds/removes a student from the offering |

Drafts (`grading.services.save_grade`, `apply_grade_upload`) don't change any visible score, because only published grades count. They must **not** schedule a refresh. If they did, 480 HTMX cell saves would queue 480 tasks.

Example, inside `publish_assessment` (the rest of the function is unchanged from S3-01):

```python
from apps.scoring.tasks import schedule_refresh

    # inside `with transaction.atomic():`, as the last line, after audit.record(...)
    schedule_refresh(assessment.offering)
```

**6. Settings flag.**

```python
# config/settings/base.py  (add near the CELERY_ settings)
USE_SCORE_SNAPSHOTS = env.bool("USE_SCORE_SNAPSHOTS", default=True)
```

```python
# config/settings/test.py  (add)
USE_SCORE_SNAPSHOTS = False   # tests opt in explicitly with the `settings` fixture
```

Why off in tests: almost every service test would otherwise run the whole snapshot pipeline eagerly (`CELERY_TASK_ALWAYS_EAGER`), which slows the suite and couples unrelated tests to this feature. The snapshot tests turn it on themselves.

**7. Make the dashboard read the views.**

`attainment_matrix` and `coverage_matrix` were written in S6-05 and S7-01 to compute live. Add a fast path at the top of each, keyed on the same flag. The live code stays as the fallback, and it's what the `--check` command compares against.

```python
# apps/scoring/aggregates.py  (top of attainment_matrix, before the live computation)
from django.conf import settings

from . import snapshots


def attainment_matrix(program, *, by, terms, threshold):
    if getattr(settings, "USE_SCORE_SNAPSHOTS", True) and threshold == program.attainment_threshold:
        cells = snapshots.read_attainment(program.pk, term_ids=[t.pk for t in terms], by=by)
        return AttainmentMatrix.from_cells(program, cells, by=by, terms=terms)
    # The live computation written in S6-05 continues here, unchanged.
```

The fast path is only valid for the program's own threshold, because the view counts "attaining" against `program.attainment_threshold`. If the head types a different threshold into the dashboard's what-if box (T1.6), the live path runs. Add `AttainmentMatrix.from_cells(program, cells, *, by, terms)` as a `classmethod` next to the dataclass S6-05 defined. It must return exactly the structure the live path returns, so the template doesn't know which path ran. `cells` maps `(po_id, key)` → `AttainmentCell`, where `key` is a cohort year or a term id. A missing key means no student has a score there: its rate is `None` and the template shows "—". Likewise `CoverageMatrix.from_totals(program, totals, *, terms)` fills S7-01's structure from `(offering_id, po_id) → total`. The "not covered by any course" flag is computed from these totals exactly as the live path does it. Write one test per classmethod that builds both paths on `small_department()` and asserts the two matrices are equal.

```python
# apps/scoring/aggregates.py  (top of coverage_matrix)
def coverage_matrix(program, *, terms):
    if getattr(settings, "USE_SCORE_SNAPSHOTS", True):
        totals = snapshots.read_coverage(program.pk, term_ids=[t.pk for t in terms])
        return CoverageMatrix.from_totals(program, totals, terms=terms)
    # The live computation written in S7-01 continues here, unchanged.
```

**8. The rebuild command.**

Used three times: once after deploying this story (to fill the empty tables), after every `seed_demo --reset`, and as a correctness check. `--check` recomputes everything live and compares it with what's stored, without writing anything.

```python
# apps/scoring/management/commands/rebuild_scores.py
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import ProgramMembership, User
from apps.catalog.models import CourseOffering
from apps.catalog.selectors import po_set_for_student
from apps.scoring.engine import compute_student_profile
from apps.scoring.loaders import load_student_inputs
from apps.scoring.models import StudentPOScore
from apps.scoring.snapshots import refresh_views, snapshot_offering


class Command(BaseCommand):
    help = "Rebuild score snapshots and materialized views, or verify them with --check."

    def add_arguments(self, parser):
        parser.add_argument("--offering", type=int, help="Only this offering id")
        parser.add_argument("--check", action="store_true",
                            help="Compare stored cumulative PO scores with a live engine run; write nothing")

    def handle(self, *args, offering=None, check=False, **opts):
        if check:
            mismatches = self._check()
            self.stdout.write(f"{mismatches} mismatches")
            if mismatches:
                raise CommandError("Snapshots differ from the engine. Run rebuild_scores without --check.")
            return
        qs = CourseOffering.objects.select_related("course__program")
        if offering:
            qs = qs.filter(pk=offering)
        total = 0
        for off in qs.iterator():
            total += snapshot_offering(off)
        refresh_views()
        self.stdout.write(self.style.SUCCESS(f"Rebuilt snapshots for {qs.count()} offerings "
                                             f"({total} student refreshes)."))

    def _check(self) -> int:
        mismatches = 0
        memberships = ProgramMembership.objects.filter(role=ProgramMembership.Role.STUDENT) \
            .select_related("user", "program")
        for m in memberships.iterator():
            student: User = m.user
            po_ids = set(po_set_for_student(student, m.program).outcomes.values_list("id", flat=True))
            live = {po: ns.score for po, ns in compute_student_profile(
                load_student_inputs(student)).po_scores.items() if po in po_ids}
            stored = dict(StudentPOScore.objects.filter(
                student=student, scope=StudentPOScore.Scope.CUMULATIVE,
            ).values_list("program_outcome_id", "score"))
            for po_id in live.keys() | stored.keys():
                a, b = live.get(po_id), stored.get(po_id)
                if (a is None) != (b is None) or (a is not None and abs(a - b) > 1e-15):
                    mismatches += 1
                    self.stderr.write(f"{student.email} PO id {po_id}: live={a} stored={b}")
        return mismatches
```

The tolerance in `--check` is `1e-15`, not `1e-20`. The engine produces up to 28 significant digits (Python's default `Decimal` context). The database column keeps 20 decimal places, so a value like `82.857142857142857142857142…` loses digits beyond the 20th place when stored. `1e-15` is still a million times smaller than anything the display can show (0.05).

**9. Add the nightly safety net to Celery beat** (beat itself arrives in S8-03; if S8-03 merges first, add this entry to its schedule, otherwise S8-03 adds it):

```python
# config/settings/base.py, inside CELERY_BEAT_SCHEDULE
    "refresh-materialized-views": {
        "task": "apps.scoring.tasks.refresh_materialized_views",
        "schedule": crontab(hour=3, minute=0),
    },
```

**10. Capture before/after evidence for CSE 321.**

On staging, after `seed_demo --reset` and `rebuild_scores`:

```bash
docker compose -f compose.prod.yml exec db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

```sql
-- Before: what the live dashboard effectively asks for (one PO, one cohort)
EXPLAIN (ANALYZE, BUFFERS)
SELECT s.program_outcome_id, count(*) FILTER (WHERE s.score >= 60)
FROM scoring_studentposcore s WHERE s.scope = 'term' GROUP BY 1;

-- After: the dashboard query
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM mv_po_attainment WHERE program_id = 1 AND term_id = ANY('{1,2,3}');
```

Also time the dashboard page itself with and without the flag:

```bash
time curl -s -o /dev/null -b "sessionid=<head session cookie>" https://staging-polaris-cse.duckdns.org/department/
```

Paste both plans and both timings into `docs/reports/cse321/section4-evidence.md`.

### Tests

```python
# apps/scoring/tests/test_snapshots.py
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import connection

from apps.catalog.selectors import po_set_for_student
from apps.core.tests.scenarios import elif_scenario, small_department
from apps.scoring.engine import compute_student_profile
from apps.scoring.loaders import load_student_inputs
from apps.scoring.models import StudentLOScore, StudentPOScore
from apps.scoring.snapshots import read_attainment, read_coverage, refresh_views, snapshot_offering

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def snapshots_on(settings):
    settings.USE_SCORE_SNAPSHOTS = True


def test_elif_snapshot_matches_slide():
    s = elif_scenario()
    snapshot_offering(s.offering)
    po = dict(StudentPOScore.objects.filter(student=s.student, scope="cumulative")
              .values_list("program_outcome_id", "score"))
    assert round(po[s.po1.id], 1) == Decimal("85.0")
    assert round(po[s.po2.id], 1) == Decimal("82.9")
    lo = dict(StudentLOScore.objects.filter(enrollment__student=s.student)
              .values_list("learning_outcome_id", "score"))
    assert round(lo[s.lo1.id], 1) == Decimal("86.0")
    assert round(lo[s.lo2.id], 1) == Decimal("82.9")


def test_snapshot_equals_live_engine_for_every_student():
    data = small_department()
    for offering in data.offerings:
        snapshot_offering(offering)
    for student in data.students:
        program = data.offerings[0].course.program
        po_ids = set(po_set_for_student(student, program).outcomes.values_list("id", flat=True))
        live = compute_student_profile(load_student_inputs(student)).po_scores
        stored = {r.program_outcome_id: r for r in
                  StudentPOScore.objects.filter(student=student, scope="cumulative")}
        assert set(stored) == {p for p in live if p in po_ids}
        for po_id, row in stored.items():
            expected = live[po_id]
            if expected.score is None:
                assert row.score is None
            else:
                assert abs(row.score - expected.score) < Decimal("1e-15")
            assert abs(row.coverage - expected.coverage) < Decimal("1e-15")


def test_refresh_is_idempotent():
    s = elif_scenario()
    snapshot_offering(s.offering)
    first = list(StudentPOScore.objects.order_by("pk").values_list("program_outcome_id", "scope", "score"))
    snapshot_offering(s.offering)
    second = list(StudentPOScore.objects.order_by("pk").values_list("program_outcome_id", "scope", "score"))
    assert sorted(first) == sorted(second)
    assert StudentLOScore.objects.count() == 2


def test_term_scope_rows_exist_for_each_term_with_enrollment():
    s = elif_scenario()
    snapshot_offering(s.offering)
    term_rows = StudentPOScore.objects.filter(student=s.student, scope="term")
    assert set(term_rows.values_list("term_id", flat=True)) == {s.offering.term_id}


def test_coverage_view_sums_lo_po_weights():
    s = elif_scenario()
    refresh_views()
    cov = read_coverage(s.offering.course.program_id, term_ids=[s.offering.term_id])
    # Elif's slide: LO1→PO1 weight 4, LO2→PO1 weight 2, LO2→PO2 weight 5
    assert cov[(s.offering.id, s.po1.id)] == Decimal("6")
    assert cov[(s.offering.id, s.po2.id)] == Decimal("5")


def test_attainment_view_counts_against_threshold():
    s = elif_scenario()
    snapshot_offering(s.offering)
    refresh_views()
    cells = read_attainment(s.offering.course.program_id, term_ids=[s.offering.term_id], by="term")
    cell = cells[(s.po1.id, s.offering.term_id)]
    assert cell.students_scored == 1
    assert cell.students_attaining == 1          # 85.0 >= 60
    assert cell.rate == Decimal("1")


def test_both_views_have_unique_index_for_concurrent_refresh():
    with connection.cursor() as cur:
        cur.execute("SELECT indexname FROM pg_indexes WHERE tablename IN "
                    "('mv_course_po_coverage', 'mv_po_attainment')")
        names = {row[0] for row in cur.fetchall()}
    assert {"mv_course_po_coverage_key", "mv_po_attainment_key"} <= names


def test_publish_schedules_refresh_after_commit(django_capture_on_commit_callbacks):
    from apps.grading.services import publish_assessment
    s = elif_scenario(published=False)
    instructor = s.offering.instructors.first()
    with django_capture_on_commit_callbacks(execute=True):
        publish_assessment(instructor, s.midterm)
        publish_assessment(instructor, s.project)
    assert StudentPOScore.objects.filter(student=s.student, scope="cumulative").exists()


def test_rebuild_check_reports_zero_after_rebuild(capsys):
    elif_scenario()
    call_command("rebuild_scores")
    call_command("rebuild_scores", "--check")
    assert "0 mismatches" in capsys.readouterr().out
```

Why `transaction=True`: `REFRESH MATERIALIZED VIEW CONCURRENTLY` and `on_commit` callbacks both need real commits. pytest-django's default wraps each test in a transaction that is rolled back, so nothing ever commits. `transaction=True` truncates the tables after each test instead. It's slower, so use it only in this file.

`test_publish_schedules_refresh_after_commit` assumes `elif_scenario(published=False)` leaves the grades as drafts and the offering has an instructor (S1-08). If your `elif_scenario` returns `instructor` directly, use `s.instructor`.

### Check it works

1. `uv run python manage.py migrate` then `uv run python manage.py seed_demo --reset` then `uv run python manage.py rebuild_scores` should print `Rebuilt snapshots for … offerings`.
2. `uv run python manage.py rebuild_scores --check` should print `0 mismatches`.
3. Log in as the head and open `/department/`. The debug toolbar's SQL panel should show the two `mv_` queries and no per-student queries.
4. As Dr. Can Aydın, change one of Elif's draft grades and publish. With the worker running (`uv run celery -A config worker -l info`), the log shows `refresh_scores` succeeding. Refresh the dashboard and the number has changed.
5. `uv run python manage.py migrate scoring 0001` drops both views without errors. Then `migrate` again.

### Done when

| AC (T2.3) | Proved by |
|---|---|
| 1. Snapshot equals live engine for the seed data | `test_snapshot_equals_live_engine_for_every_student`, `rebuild_scores --check` on staging |
| 2. Publishing or saving a mapping refreshes snapshots after commit, never on rollback | `test_publish_schedules_refresh_after_commit`; the on_commit design |
| 3. Dashboard reads from the views; loads in under 300 ms on seed data | Debug toolbar check, `curl` timing in `section4-evidence.md` |
| 4. A command rebuilds everything from scratch | `test_rebuild_check_reports_zero_after_rebuild` |
| Views refresh without blocking readers | `test_both_views_have_unique_index_for_concurrent_refresh` |

### Commits and PR

```
Add StudentLOScore and StudentPOScore snapshot tables (#81)
Add coverage and attainment materialized views with unique keys (#81)
Write engine results into snapshots after publish and mapping saves (#81)
Read dashboard aggregates from materialized views (#81)
Add rebuild_scores command with --check mode (#81)
```

PR title: `S8-02 Precomputed scores and materialized views (T2.3)`. In the description, paste the `EXPLAIN ANALYZE` before/after timings. A reviewer can't judge a performance change without numbers.

---

## S8-01 · Clone last term's setup (T2.1)

**Points:** 2 · **Owner:** Person B · **Branch:** `feature/S8-01-clone-setup` · **Depends on:** S2-04, S2-05

### Goal

Most courses change little between terms. Without this story, an instructor retypes six LOs, five assessments and two grids every term. With it, the empty setup page of a new offering offers "Copy setup from Fall 2026 (CSE 311)", and one click copies LOs, assessments (without dates or published state), both weight grids and their sources. No grades are copied. It delivers T2.1 AC 1–4.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/outcomes/services.py` | modify | `clone_setup(user, target, source) -> CloneResult` |
| `apps/outcomes/selectors.py` | modify | `clone_candidates(user, offering) -> QuerySet` |
| `apps/outcomes/views.py` | modify | `clone_setup_view` |
| `apps/outcomes/urls.py` | modify | `outcomes:clone` → `…/setup/clone/` (POST) |
| `apps/outcomes/templates/outcomes/setup.html` | modify | Clone card in the empty state |
| `apps/outcomes/tests/test_clone.py` | create | Service and view tests |
| `apps/accounts/tests/test_permission_matrix.py` | modify | New URL row |

### Steps

**1. Which offerings can be cloned from.** Same catalog course, a different offering, at least one LO, and visible to the user. Newest term first. We use `offerings_for_user` from S2-02 to scope by permission, so an instructor never sees another instructor's course offered as a source unless they're allowed to view it. The head can view everything in their program.

```python
# apps/outcomes/selectors.py  (add)
from django.db.models import Count

from apps.catalog.selectors import offerings_for_user


def clone_candidates(user, offering):
    """Earlier or parallel offerings of the same course that have a setup worth copying."""
    return (
        offerings_for_user(user)
        .filter(course=offering.course)
        .exclude(pk=offering.pk)
        .annotate(lo_count=Count("learning_outcomes", distinct=True),
                  assessment_count=Count("assessments", distinct=True))
        .filter(lo_count__gt=0)
        .select_related("term", "course")
        .order_by("-term__starts_on", "section")
    )
```

**2. The service.** Rules, in the order the code checks them:

- The target's term must be open (`ensure_term_open`).
- The target must be empty: no LOs and no assessments. Cloning on top of an existing setup would create confusing half-merges. If the instructor wants to start over, they delete first, which is a deliberate act.
- The source must be the same course. This is a defensive check: the view already only offers such sources.
- LO→PO links are copied only when the PO belongs to the target program's **active** PO set (§5.3). If the head activated a new PO set between terms, old links to the previous set are dropped and counted, and the UI says so.

Everything happens in one transaction with **one** audit event (`offering.clone`), whose `after` lists counts and the source id. One event is what a reader of the history wants ("Can cloned from Fall 2026"), not forty individual creates.

```python
# apps/outcomes/services.py  (add)
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.catalog.models import CourseOffering
from apps.catalog.selectors import active_po_set
from apps.catalog.services import ensure_term_open
from apps.core import audit

from .models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight, Source


@dataclass(frozen=True)
class CloneResult:
    los: int
    assessments: int
    assessment_lo_weights: int
    lo_po_weights: int
    dropped_lo_po_weights: int     # links to POs outside the target's active set


def clone_setup(user, target: CourseOffering, source: CourseOffering) -> CloneResult:
    ensure_term_open(target)
    if source.course_id != target.course_id:
        raise ValidationError("You can only copy the setup of the same course.")
    if source.pk == target.pk:
        raise ValidationError("Choose a different offering to copy from.")

    with transaction.atomic():
        # Lock the target so two clicks can't clone twice.
        target = CourseOffering.objects.select_for_update().get(pk=target.pk)
        if target.learning_outcomes.exists() or target.assessments.exists():
            raise ValidationError(
                "This course already has learning outcomes or assessments. "
                "Delete them first if you want to copy another term's setup."
            )

        lo_map: dict[int, LearningOutcome] = {}
        for lo in source.learning_outcomes.order_by("number"):
            lo_map[lo.pk] = LearningOutcome.objects.create(
                offering=target, number=lo.number, description=lo.description, source=Source.CLONED,
            )

        a_map: dict[int, Assessment] = {}
        for a in source.assessments.order_by("position", "id"):
            a_map[a.pk] = Assessment.objects.create(
                offering=target, name=a.name, kind=a.kind, max_score=a.max_score,
                course_weight=a.course_weight, position=a.position,
                due_date=None, published_at=None, published_by=None,
            )

        a_lo = [
            AssessmentLOWeight(assessment=a_map[w.assessment_id],
                               learning_outcome=lo_map[w.learning_outcome_id], weight=w.weight)
            for w in AssessmentLOWeight.objects.filter(assessment__offering=source)
        ]
        AssessmentLOWeight.objects.bulk_create(a_lo)

        allowed_pos = set(active_po_set(target.course.program).outcomes.values_list("id", flat=True))
        lo_po, dropped = [], 0
        for w in LOPOWeight.objects.filter(learning_outcome__offering=source):
            if w.program_outcome_id not in allowed_pos:
                dropped += 1
                continue
            lo_po.append(LOPOWeight(
                learning_outcome=lo_map[w.learning_outcome_id], program_outcome_id=w.program_outcome_id,
                weight=w.weight, rationale=w.rationale,
                # Keep unconfirmed AI suggestions flagged so lint L007 still catches them.
                source=Source.AI_SUGGESTED if w.source == Source.AI_SUGGESTED else Source.CLONED,
            ))
        LOPOWeight.objects.bulk_create(lo_po)

        target.cloned_from = source
        target.save(update_fields=["cloned_from"])

        result = CloneResult(len(lo_map), len(a_map), len(a_lo), len(lo_po), dropped)
        audit.record(user, "offering.clone", target, offering=target,
                     after={"source_offering": source.pk, **result.__dict__})
    return result
```

Why `Source.CLONED` on LOs and LO→PO weights, even though the instructor wrote the originals: lint L007 only looks at `ai_suggested`, so cloned weights don't trigger it. But the history and the review screen can now say "copied from last term", and we can measure how many offerings were cloned in the CSE 311 report's punchline section.

One exception: a weight that is still `ai_suggested` (never confirmed by a human) stays `ai_suggested` in the copy. Otherwise cloning would silently launder an unreviewed AI guess into a "cloned" one and lint L007 would stop warning about it.

**3. The view.** POST only. The source id comes from the form, and we re-check it against `clone_candidates`, so a crafted POST can't copy from an offering the user can't see. If it's not in the list, it's a 404 (§3.4 rule 3).

```python
# apps/outcomes/views.py  (add)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.accounts.decorators import require_offering_access

from .selectors import clone_candidates
from .services import clone_setup


@login_required
@require_POST
@require_offering_access(edit=True)
def clone_setup_view(request, offering_id, *, offering, perms_for):
    source = get_object_or_404(clone_candidates(request.user, offering),
                               pk=request.POST.get("source_id") or 0)
    try:
        r = clone_setup(request.user, offering, source)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
        return redirect("outcomes:setup", offering_id=offering.pk)
    msg = (f"Copied {r.los} learning outcomes, {r.assessments} assessments and both weight grids "
           f"from {source.term.name}. Check the due dates: they were not copied.")
    if r.dropped_lo_po_weights:
        msg += (f" {r.dropped_lo_po_weights} PO links were skipped because they point at an older "
                f"PO set. Review the Mapping tab.")
    messages.success(request, msg)
    return redirect("outcomes:mapping", offering_id=offering.pk)
```

```python
# apps/outcomes/urls.py  (add to urlpatterns)
    path("offerings/<int:offering_id>/setup/clone/", views.clone_setup_view, name="clone"),
```

**4. The template.** In the empty state of `setup.html` (the `{% if not los and not assessments %}` branch from S2-04), add a card above "Upload syllabus instead". The view for `outcomes:setup` passes `clone_candidates`. Add this line to `setup`'s context: `"clone_candidates": clone_candidates(request.user, offering)[:5]`.

```django
{% if clone_candidates %}
  <div class="card mb-3">
    <div class="card-body">
      <h2 class="h5">Copy last term's setup</h2>
      <p class="text-body-secondary mb-3">
        Copies learning outcomes, assessments (without dates) and both weight grids. Grades are never copied.
      </p>
      <form method="post" action="{% url 'outcomes:clone' offering_id=offering.pk %}" class="d-flex gap-2 flex-wrap">
        {% csrf_token %}
        <label class="visually-hidden" for="clone-source">Copy from</label>
        <select id="clone-source" name="source_id" class="form-select w-auto">
          {% for c in clone_candidates %}
            <option value="{{ c.pk }}">{{ c.term.name }} · section {{ c.section }} · {{ c.lo_count }} LOs, {{ c.assessment_count }} assessments</option>
          {% endfor %}
        </select>
        <button class="btn btn-primary" type="submit">Copy setup</button>
      </form>
    </div>
  </div>
{% endif %}
```

### Tests

```python
# apps/outcomes/tests/test_clone.py
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.catalog.models import Term
from apps.core.models import AuditEvent
from apps.core.tests.factories import OfferingFactory, ProgramOutcomeFactory, ProgramOutcomeSetFactory, TermFactory
from apps.core.tests.scenarios import elif_scenario
from apps.grading.models import Grade
from apps.outcomes.models import Assessment, LOPOWeight, Source
from apps.outcomes.services import clone_setup

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    s = elif_scenario()
    new_term = TermFactory(code="2027S", name="Spring 2027", status=Term.Status.OPEN,
                           starts_on="2027-02-01", ends_on="2027-06-15")
    target = OfferingFactory(course=s.offering.course, term=new_term)
    instructor = s.offering.instructors.first()
    target.instructors.add(instructor)
    return s, target, instructor


def test_clone_copies_structure_not_grades(setup):
    s, target, instructor = setup
    r = clone_setup(instructor, target, s.offering)
    assert (r.los, r.assessments) == (2, 2)
    assert r.assessment_lo_weights == 4       # slide: midterm→LO1 60, midterm→LO2 40, project→LO1 40, project→LO2 100
    assert r.lo_po_weights == 3               # LO1→PO1, LO2→PO1, LO2→PO2
    assert target.learning_outcomes.filter(source=Source.CLONED).count() == 2
    assert not Grade.objects.filter(assessment__offering=target).exists()
    assert all(a.published_at is None and a.due_date is None
               for a in Assessment.objects.filter(offering=target))
    target.refresh_from_db()
    assert target.cloned_from_id == s.offering.id


def test_clone_refuses_non_empty_target(setup):
    s, target, instructor = setup
    clone_setup(instructor, target, s.offering)
    with pytest.raises(ValidationError):
        clone_setup(instructor, target, s.offering)


def test_clone_refuses_closed_term(setup):
    s, target, instructor = setup
    target.term.status = Term.Status.CLOSED
    target.term.save()
    with pytest.raises(ValidationError):
        clone_setup(instructor, target, s.offering)


def test_links_to_inactive_po_set_are_dropped(setup):
    s, target, instructor = setup
    program = s.offering.course.program
    program.po_sets.update(is_active=False)
    new_set = ProgramOutcomeSetFactory(program=program, label="2027 curriculum",
                                       effective_from_year=2027, is_active=True)
    ProgramOutcomeFactory(po_set=new_set, number=1)
    r = clone_setup(instructor, target, s.offering)
    assert r.lo_po_weights == 0 and r.dropped_lo_po_weights == 3
    assert not LOPOWeight.objects.filter(learning_outcome__offering=target).exists()


def test_clone_writes_one_audit_event(setup):
    s, target, instructor = setup
    clone_setup(instructor, target, s.offering)
    events = AuditEvent.objects.filter(offering=target, action="offering.clone")
    assert events.count() == 1
    assert events.get().after["source_offering"] == s.offering.id


def test_view_404s_for_source_user_cannot_see(client, setup):
    s, target, instructor = setup
    stranger_offering = OfferingFactory()          # different course, not visible to instructor
    client.force_login(instructor)
    url = reverse("outcomes:clone", kwargs={"offering_id": target.pk})
    assert client.post(url, {"source_id": stranger_offering.pk}).status_code == 404


def test_view_clones_and_redirects_to_mapping(client, setup):
    s, target, instructor = setup
    client.force_login(instructor)
    url = reverse("outcomes:clone", kwargs={"offering_id": target.pk})
    resp = client.post(url, {"source_id": s.offering.pk})
    assert resp.status_code == 302
    assert resp.url == reverse("outcomes:mapping", kwargs={"offering_id": target.pk})
```

The comments in the first test spell out the slide's arrows so a reader sees where 4 and 3 come from. They are the same arrows that produce LO1 86.0 and PO1 85.0.

Add the URL to the permission matrix with POST expectations: student 404, other instructor 404, own instructor 302, head 302, anonymous 302 to login.

### Check it works

1. As the head, create a 2027S term (open) and an offering of CSE 311 in it, with Dr. Can Aydın as instructor.
2. Log in as Dr. Can Aydın and open the new offering's setup page. The "Copy last term's setup" card lists Fall 2026.
3. Click **Copy setup**. You land on Mapping with both grids filled and a green message. Assessments have no due dates.
4. Open `/offerings/<id>/history/` (T1.4). One event: "offering.clone".
5. Try again. The card is gone because the setup is no longer empty.

### Done when

| AC (T2.1) | Proved by |
|---|---|
| 1. LOs, assessments without dates and both weight sets are copied; `cloned_from` set | `test_clone_copies_structure_not_grades` |
| 2. No grades are copied; nothing is published | same test |
| 3. Refused on a non-empty target or closed term | `test_clone_refuses_non_empty_target`, `test_clone_refuses_closed_term` |
| 4. Links to POs outside the active set are dropped and reported | `test_links_to_inactive_po_set_are_dropped`, success message |
| Audited as one event | `test_clone_writes_one_audit_event` |

### Commits and PR

```
Add clone_setup service for copying an offering's setup (#80)
Offer last term's setup in the empty state of course setup (#80)
Keep AI-suggested PO links flagged when cloning (#80)
```

PR title: `S8-01 Clone last term's setup (T2.1)`.


---

## S8-04 · PO transcript PDF with a verification code (T2.4)

**Points:** 3 · **Owner:** Person B · **Branch:** `feature/S8-04-po-transcript` · **Depends on:** S3-02, S7-03 (WeasyPrint pipeline), S7-04

### Goal

A student downloads a one-page PDF of their PO profile to attach to an internship or Erasmus application. It shows the PO table, a radar chart, the courses that contributed to each PO, the generation date and a **verification code**. Anyone who gets the PDF can open `/verify/<code>/` and see the same numbers on our site, so a doctored PDF is easy to catch. It delivers T2.4 AC 1–5.

Two design choices to defend:

- **Synchronous rendering, not an `ExportJob`.** A one-page WeasyPrint render takes about a second, and the URL `/me/transcript.pdf` is nicer when it simply returns the file. Department reports use the background pipeline because they can take ten seconds or more. A transcript doesn't.
- **The chart is a server-side SVG, not Chart.js.** WeasyPrint does not run JavaScript, so a Chart.js canvas would be blank in the PDF. A radar chart is 40 lines of trigonometry, so we draw it ourselves as SVG, which WeasyPrint renders sharply at any zoom. The same function could later replace the screenshot in the report.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/reports/models.py` | modify | `TranscriptIssue` |
| `apps/reports/svg.py` | create | `radar_svg(labels, values, threshold) -> str` (pure) |
| `apps/reports/exports.py` | modify | `render_transcript_pdf(student) -> tuple[bytes, TranscriptIssue]` |
| `apps/reports/views_student.py` | modify | `transcript` |
| `apps/reports/views.py` | modify | `verify_transcript` (public) |
| `config/urls.py` / `apps/reports/urls.py` | modify | `reports:verify_transcript` → `/verify/<code>/` |
| `apps/reports/templates/reports/pdf/transcript.html` | create | Print template |
| `apps/reports/templates/reports/verify.html` | create | Public verification page |
| `apps/reports/templates/reports/student/profile.html` | modify | "Download transcript (PDF)" button |
| `apps/reports/tests/test_transcript.py` | create | Tests |

### Steps

**1. The issue record.** Each download creates a `TranscriptIssue` row holding a frozen copy of what was printed (`payload`). Verification shows that stored copy, not today's live numbers. If Elif's scores change next term, an old PDF still verifies as "this is what she had on 20 Dec". The code is random, not derived from the data: 12 characters from a 32-character alphabet give 60 bits, which can't be guessed by trying.

```python
# apps/reports/models.py  (add)
import secrets

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O, 1/I: people retype these codes


def new_verification_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(12))


class TranscriptIssue(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="transcripts")
    code = models.CharField(max_length=12, unique=True, default=new_verification_code)
    payload = models.JSONField()          # exactly what the PDF shows: names, PO rows, courses
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]

    @property
    def display_code(self) -> str:
        return f"{self.code[:4]}-{self.code[4:8]}-{self.code[8:]}"
```

`settings` and `models` are already imported at the top of `apps/reports/models.py` from the `ExportJob` model. Run `uv run python manage.py makemigrations reports`.

**2. The radar SVG.** This is a pure function with no Django, so it's easy to test. Each PO is a spoke. A score of 100 reaches the outer ring, and the threshold is drawn as a dashed ring. `None` scores are drawn at the centre with a hollow marker, never as 0 pretending to be data (P12). In the table next to it they show "—".

```python
# apps/reports/svg.py
"""Server-side SVG charts for PDFs (WeasyPrint runs no JavaScript)."""
from __future__ import annotations

import math
from decimal import Decimal
from html import escape

SIZE = 320
CENTER = SIZE / 2
RADIUS = 120


def _point(i: int, n: int, fraction: float) -> tuple[float, float]:
    angle = -math.pi / 2 + 2 * math.pi * i / n          # first spoke points up
    return (CENTER + RADIUS * fraction * math.cos(angle),
            CENTER + RADIUS * fraction * math.sin(angle))


def _polygon(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def radar_svg(labels: list[str], values: list[Decimal | None], threshold: Decimal) -> str:
    if len(labels) != len(values) or len(labels) < 3:
        raise ValueError("radar needs at least 3 spokes and one value per label")
    n = len(labels)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
             f'width="{SIZE}" height="{SIZE}" role="img" aria-label="PO radar chart">']
    for ring in (0.25, 0.5, 0.75, 1.0):                  # grid rings
        pts = [_point(i, n, ring) for i in range(n)]
        parts.append(f'<polygon points="{_polygon(pts)}" fill="none" stroke="#ccc" stroke-width="0.5"/>')
    for i in range(n):                                   # spokes + labels
        x, y = _point(i, n, 1.0)
        lx, ly = _point(i, n, 1.13)
        parts.append(f'<line x1="{CENTER}" y1="{CENTER}" x2="{x:.1f}" y2="{y:.1f}" stroke="#ccc" stroke-width="0.5"/>')
        parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="9" text-anchor="middle" '
                     f'dominant-baseline="middle">{escape(labels[i])}</text>')
    t = float(threshold) / 100
    parts.append(f'<polygon points="{_polygon([_point(i, n, t) for i in range(n)])}" '
                 f'fill="none" stroke="#b02a37" stroke-width="1" stroke-dasharray="4 3"/>')
    data = [_point(i, n, 0 if v is None else min(float(v), 100) / 100) for i, v in enumerate(values)]
    parts.append(f'<polygon points="{_polygon(data)}" fill="rgba(31,58,147,0.25)" '
                 f'stroke="#1f3a93" stroke-width="1.5"/>')
    for (x, y), v in zip(data, values, strict=True):
        fill = "none" if v is None else "#1f3a93"
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{fill}" stroke="#1f3a93"/>')
    parts.append("</svg>")
    return "".join(parts)
```

`float` appears here only to compute **pixel positions**, after the scores are final. That's allowed: the "never float" rule is about scores and weights in calculations. Write that sentence in the PR description, because a reviewer following the checklist will ask.

**3. Building the payload and the PDF.**

```python
# apps/reports/exports.py  (add)
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.safestring import mark_safe
from weasyprint import HTML

from apps.accounts.models import ProgramMembership
from apps.catalog.models import CourseOffering
from apps.catalog.selectors import po_set_for_student
from apps.scoring.engine import compute_student_profile, display
from apps.scoring.loaders import load_student_inputs

from .models import TranscriptIssue
from .svg import radar_svg


def transcript_payload(student) -> dict:
    """Everything the transcript prints, as JSON-safe data (stored on TranscriptIssue)."""
    membership = (ProgramMembership.objects.select_related("program")
                  .get(user=student, role=ProgramMembership.Role.STUDENT))
    program = membership.program
    pos = list(po_set_for_student(student, program).outcomes.all())
    profile = compute_student_profile(load_student_inputs(student))
    offering_ids = {off_id for rows in profile.po_contributors.values() for off_id, _lo, _w in rows}
    course_codes = dict(CourseOffering.objects.filter(pk__in=offering_ids)
                        .values_list("pk", "course__code"))
    rows = []
    for po in pos:
        node = profile.po_scores.get(po.pk)
        score = node.score if node else None
        contributors = sorted({course_codes[o] for o, _lo, _w in profile.po_contributors.get(po.pk, [])})
        rows.append({
            "number": po.number, "short_name": po.short_name,
            "score": None if score is None else str(score),
            "display": display(score),
            "coverage": None if node is None else str(node.coverage),
            "attained": score is not None and score >= program.attainment_threshold,
            "courses": contributors,
        })
    return {
        "student_name": student.get_full_name(), "student_number": student.student_number,
        "program": f"{program.code} · {program.name}", "cohort_year": membership.cohort_year,
        "threshold": str(program.attainment_threshold),
        "po_set": pos[0].po_set.label if pos else "",
        "rows": rows, "generated_at": timezone.now().isoformat(),
    }


def render_transcript_pdf(student, *, base_url: str) -> tuple[bytes, TranscriptIssue]:
    payload = transcript_payload(student)
    issue = TranscriptIssue.objects.create(student=student, payload=payload)
    chart = radar_svg(
        labels=[f"PO {r['number']}" for r in payload["rows"]],
        values=[None if r["score"] is None else Decimal(r["score"]) for r in payload["rows"]],
        threshold=Decimal(payload["threshold"]),
    ) if len(payload["rows"]) >= 3 else ""
    html = render_to_string("reports/pdf/transcript.html", {
        "p": payload, "issue": issue, "radar": mark_safe(chart),  # noqa: S308 - built by our own code, labels escaped
        "verify_url": f"{base_url}/verify/{issue.code}/",
    })
    return HTML(string=html, base_url=base_url).write_pdf(), issue
```

`Decimal` is already imported at the top of `exports.py`. If not, add `from decimal import Decimal`. `mark_safe` is acceptable only because `radar_svg` escapes every label itself. That's the `# noqa` reason, written next to it so a reviewer doesn't have to guess.

`render_transcript_pdf(student) -> bytes` in §4.8 becomes `render_transcript_pdf(student, *, base_url) -> tuple[bytes, TranscriptIssue]`. The view needs the issue (for the filename) and the base URL (for the verification link). Update §4.8 in this PR.

**4. The print template.** It's one A4 page, so keep the CSS in the file. Bootstrap would add 200 KB and a dozen rules WeasyPrint ignores.

```django
{# apps/reports/templates/reports/pdf/transcript.html #}
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PO transcript · {{ p.student_name }}</title>
<style>
  @page { size: A4; margin: 16mm 14mm; @bottom-center { content: "Verify at {{ verify_url }}"; font-size: 8pt; color: #666; } }
  body { font-family: "DejaVu Sans", sans-serif; font-size: 9.5pt; color: #111; }
  h1 { font-size: 15pt; margin: 0 0 2mm; }
  .meta { color: #444; margin-bottom: 5mm; }
  .grid { display: flex; gap: 6mm; align-items: flex-start; }
  table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
  th, td { border-bottom: 0.4pt solid #bbb; padding: 1.6mm 1.2mm; text-align: left; vertical-align: top; }
  th { background: #f1f3f8; font-weight: 600; }
  td.num { text-align: right; white-space: nowrap; }
  .ok { color: #146c43; } .below { color: #b02a37; } .none { color: #666; }
  .code { font-family: "DejaVu Sans Mono", monospace; font-size: 11pt; letter-spacing: 0.5pt; }
  .foot { margin-top: 5mm; font-size: 8pt; color: #444; }
</style>
</head>
<body>
  <h1>Program Outcome transcript</h1>
  <div class="meta">
    {{ p.student_name }} · {{ p.student_number }} · cohort {{ p.cohort_year }}<br>
    {{ p.program }} · {{ p.po_set }} · attainment threshold {{ p.threshold }}
  </div>
  <div class="grid">
    <div style="flex: 0 0 82mm">{{ radar }}</div>
    <table>
      <thead><tr><th>PO</th><th>Outcome</th><th class="num">Score</th><th>Status</th><th>Evidence from</th></tr></thead>
      <tbody>
      {% for r in p.rows %}
        <tr>
          <td>PO {{ r.number }}</td>
          <td>{{ r.short_name }}</td>
          <td class="num">{{ r.display }}</td>
          <td>{% if r.score is None %}<span class="none">No evidence yet</span>{% elif r.attained %}<span class="ok">✓ Attained</span>{% else %}<span class="below">Below threshold</span>{% endif %}</td>
          <td>{{ r.courses|join:", "|default:"—" }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  <p class="foot">
    Scores are weighted averages of published grades, rounded to one decimal for display only.
    Generated {{ issue.issued_at|date:"j F Y, H:i" }}.
    Verification code: <span class="code">{{ issue.display_code }}</span> · {{ verify_url }}
  </p>
</body>
</html>
```

The Dockerfile already installs Pango for WeasyPrint (§10.5). Add `fonts-dejavu-core` to its `apt-get install` line so the ✓ glyph and Turkish characters (ş, ğ, İ) render. Without a font that has them, WeasyPrint prints empty boxes. Check this on staging, not just your laptop: macOS has more fonts than the slim container.

**5. The two views.**

```python
# apps/reports/views_student.py  (add)
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from apps.accounts.decorators import require_role

from .exports import render_transcript_pdf


@login_required
@require_role("student")
def transcript(request):
    pdf, issue = render_transcript_pdf(request.user, base_url=request.build_absolute_uri("/").rstrip("/"))
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="po-transcript-{issue.code}.pdf"'
    return response
```

```python
# apps/reports/views.py  (add)
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from .models import TranscriptIssue


@never_cache
def verify_transcript(request, code):
    """Public on purpose: the student shares the code so a third party can check the PDF."""
    issue = get_object_or_404(TranscriptIssue, code=code.replace("-", "").upper())
    return render(request, "reports/verify.html", {"issue": issue, "p": issue.payload})
```

```python
# apps/reports/urls.py  (add to urlpatterns)
    path("verify/<str:code>/", views.verify_transcript, name="verify_transcript"),
```

The verification page is the only page besides `/login/` and `/healthz` that needs no login. It shows the frozen payload: name, student number, PO table, issue date. That *is* personal data, but the student chooses to share the code, the same way they choose to share the PDF. Say so on the profile page next to the button: "Anyone with this PDF can verify it at polaris…/verify. It shows the same scores as the PDF." Add the URL to the permission matrix as **public** (200 for every role, including anonymous, for a valid code; 404 for an invalid one).

```django
{# apps/reports/templates/reports/verify.html #}
{% extends "base.html" %}
{% block title %}Verify transcript{% endblock %}
{% block content %}
<div class="container py-4" style="max-width: 760px">
  <div class="alert alert-success" role="status">
    <strong>✓ Genuine POlaris transcript</strong> issued {{ issue.issued_at|date:"j F Y, H:i" }}
    (code <code>{{ issue.display_code }}</code>). Compare the numbers below with the PDF you received.
  </div>
  <h1 class="h4">{{ p.student_name }} · {{ p.student_number }}</h1>
  <p class="text-body-secondary">{{ p.program }} · {{ p.po_set }} · threshold {{ p.threshold }}</p>
  <table class="table table-sm">
    <thead><tr><th>PO</th><th>Outcome</th><th class="text-end">Score</th></tr></thead>
    <tbody>
      {% for r in p.rows %}
        <tr><td>PO {{ r.number }}</td><td>{{ r.short_name }}</td><td class="text-end font-monospace">{{ r.display }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
  <p class="small text-body-secondary">This page shows the scores as they were when the transcript was issued. Later grades do not change it.</p>
</div>
{% endblock %}
```

Then add the button to the student profile page header: `<a class="btn btn-outline-primary" href="{% url 'student:transcript' %}">Download transcript (PDF)</a>`.

### Tests

```python
# apps/reports/tests/test_transcript.py
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.core.tests.scenarios import elif_scenario
from apps.reports.exports import transcript_payload
from apps.reports.models import TranscriptIssue
from apps.reports.svg import radar_svg

pytestmark = pytest.mark.django_db


def test_payload_has_slide_numbers():
    s = elif_scenario()
    p = transcript_payload(s.student)
    by_number = {r["number"]: r for r in p["rows"]}
    assert by_number[s.po1.number]["display"] == "85.0"
    assert by_number[s.po2.number]["display"] == "82.9"
    assert "CSE 311" in by_number[s.po1.number]["courses"][0]


def test_po_without_evidence_shows_dash_not_zero():
    s = elif_scenario()
    p = transcript_payload(s.student)
    empty = [r for r in p["rows"] if r["number"] not in (s.po1.number, s.po2.number)]
    assert empty and all(r["display"] == "—" and r["score"] is None for r in empty)


def test_student_downloads_pdf_and_issue_is_stored(client):
    s = elif_scenario()
    client.force_login(s.student)
    resp = client.get(reverse("student:transcript"))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    issue = TranscriptIssue.objects.get(student=s.student)
    assert issue.code in resp["Content-Disposition"]


def test_verify_page_is_public_and_shows_frozen_payload(client):
    s = elif_scenario()
    issue = TranscriptIssue.objects.create(student=s.student, payload=transcript_payload(s.student))
    resp = client.get(reverse("reports:verify_transcript", kwargs={"code": issue.display_code}))
    assert resp.status_code == 200
    assert "85.0" in resp.content.decode()


def test_verify_unknown_code_404(client):
    resp = client.get(reverse("reports:verify_transcript", kwargs={"code": "AAAA-BBBB-CCCC"}))
    assert resp.status_code == 404


def test_instructor_cannot_download_a_transcript(client):
    s = elif_scenario()
    client.force_login(s.offering.instructors.first())
    assert client.get(reverse("student:transcript")).status_code in (302, 404)


def test_radar_svg_escapes_labels_and_marks_missing_values():
    svg = radar_svg(["<b>PO 1</b>", "PO 2", "PO 3"], [Decimal("85"), None, Decimal("40")], Decimal("60"))
    assert "<b>" not in svg and "&lt;b&gt;" in svg
    assert 'fill="none" stroke="#1f3a93"' in svg       # hollow marker for the None value


def test_radar_requires_three_spokes():
    with pytest.raises(ValueError):
        radar_svg(["a", "b"], [None, None], Decimal("60"))
```

`test_instructor_cannot_download_a_transcript` accepts 302 or 404 because `require_role` from S2-02 decides the exact code. Replace it with the one value that decorator returns (the permission matrix test already pins it), so the test doesn't hide a regression.

### Check it works

1. Log in as Elif (seed data) and open `/me/`. Click **Download transcript (PDF)**.
2. Open the PDF. It's one A4 page, PO 1 shows 85.0 and PO 2 shows 82.9, the radar is visible, and ş/ğ/İ in names render.
3. Copy the verification URL from the footer into a private window (logged out). The green "Genuine" banner appears with the same numbers.
4. Change a URL letter. You get a 404 page.

### Done when

| AC (T2.4) | Proved by |
|---|---|
| 1. One-page PDF with PO table, radar, contributing courses, date, code | `test_student_downloads_pdf_and_issue_is_stored`, manual check 2 |
| 2. Numbers equal the profile page | `test_payload_has_slide_numbers` (same engine and `display`) |
| 3. Verification page shows the frozen copy, publicly | `test_verify_page_is_public_and_shows_frozen_payload` |
| 4. No evidence shows "—", never 0 | `test_po_without_evidence_shows_dash_not_zero` |
| 5. Only the student themself can generate their transcript | `test_instructor_cannot_download_a_transcript`, matrix row |

### Commits and PR

```
Add TranscriptIssue with random verification codes (#83)
Draw PO radar charts as server-side SVG for PDFs (#83)
Render one-page PO transcript with WeasyPrint (#83)
Add public transcript verification page (#83)
```

PR title: `S8-04 PO transcript PDF with verification (T2.4)`.

---

## S8-03 · Completion tracker and reminder emails (T2.2)

**Points:** 5 · **Owner:** Person C · **Branch:** `feature/S8-03-reminders` · **Depends on:** S5-02 (Celery), S6-05/S7-02 (completion panel), S3-06 (production email)

### Goal

The head sets a deadline for a term ("all mappings complete and midterms published by 20 Nov"). From the day after, every morning at 08:00, each instructor who still has unfinished offerings gets **one** email listing what's missing in each course, with direct links. Instructors can opt out with one click. Every email sent is logged, and the head sees the log on the dashboard's completion panel. It delivers T2.2 AC 1–6.

This story introduces the **Celery beat** process. Beat is a scheduler: it doesn't run tasks, it only puts them on the queue at the right time, and the normal worker runs them. There must be exactly one beat process per environment, or every email goes out twice.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/reports/models.py` | modify | `CompletionDeadline`, `ReminderPreference`, `ReminderLog` |
| `apps/reports/reminders.py` | create | `pending_items(offering)`, `build_reminders(term, today)` (pure-ish selection) |
| `apps/reports/tasks.py` | modify | `send_completion_reminders()` |
| `apps/reports/views.py` | modify | `term_deadline`, `reminders_unsubscribe` |
| `apps/reports/forms.py` | modify | `CompletionDeadlineForm` |
| `apps/reports/urls.py` | modify | `reports:term_deadline`, `reports:reminders_unsubscribe` |
| `apps/reports/templates/reports/email/reminder.{txt,html}` | create | Email bodies |
| `apps/reports/templates/reports/term_deadline.html`, `unsubscribe.html` | create | Pages |
| `apps/reports/templates/reports/department.html` | modify | Deadline and reminder log in the completion panel |
| `config/settings/base.py` | modify | `CELERY_BEAT_SCHEDULE`, `CELERY_TIMEZONE` |
| `compose.prod.yml` | modify | `beat` service |
| `apps/reports/tests/test_reminders.py` | create | Tests |

### Steps

**1. Three small models.**

```python
# apps/reports/models.py  (add)
class CompletionDeadline(models.Model):
    """The head's deadline for a term. One per term."""
    term = models.OneToOneField("catalog.Term", on_delete=models.CASCADE, related_name="completion_deadline")
    due_on = models.DateField()
    require_all_published = models.BooleanField(
        default=False, help_text="Off: only mappings must be complete. On: every assessment must also be published.")
    set_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)


class ReminderPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="reminder_preference")
    enabled = models.BooleanField(default=True)
    changed_at = models.DateTimeField(auto_now=True)


class ReminderLog(models.Model):
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    term = models.ForeignKey("catalog.Term", on_delete=models.CASCADE, related_name="+")
    sent_on = models.DateField()
    items = models.JSONField()              # [{"offering": id, "course": "CSE 311", "missing": [...]}]
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # The idempotency guarantee: one email per instructor per term per day,
            # even if beat fires twice or the task is retried.
            models.UniqueConstraint(fields=["instructor", "term", "sent_on"], name="one_reminder_per_day"),
        ]
```

Why a unique constraint instead of "check, then send": two task runs at the same moment would both pass a Python check. The database constraint can't be raced. The task inserts the log row **first**, inside a transaction. If the insert fails with `IntegrityError`, someone already sent today and we skip. The email goes out only after the row exists.

**2. What counts as "missing".** This uses `setup_status` from the catalog selectors, so the dashboard's completion panel and the email can never disagree about what's incomplete.

```python
# apps/reports/reminders.py
"""Decide who gets a completion reminder and what it lists (T2.2)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from apps.catalog.models import CourseOffering, Term
from apps.catalog.selectors import setup_status


def pending_items(offering: CourseOffering, *, require_all_published: bool) -> list[str]:
    st = setup_status(offering)
    missing = []
    if not st.has_los:
        missing.append("Add learning outcomes")
    if not st.has_assessments:
        missing.append("Add assessments")
    if st.has_los and st.has_assessments and not st.has_assessment_lo:
        missing.append("Fill the assessment → LO weights")
    if st.has_los and not st.has_lo_po:
        missing.append("Fill the LO → PO weights")
    if require_all_published and st.assessment_count > st.published_count:
        unpublished = st.assessment_count - st.published_count
        missing.append(f"Publish {unpublished} assessment{'s' if unpublished != 1 else ''}")
    return missing


@dataclass
class Reminder:
    instructor_id: int
    items: list[dict] = field(default_factory=list)


def build_reminders(term: Term, today: date) -> list[Reminder]:
    """One Reminder per instructor with at least one incomplete offering in `term`.
    Empty when there's no deadline, it hasn't passed, or the term isn't open."""
    deadline = getattr(term, "completion_deadline", None)
    if deadline is None or today <= deadline.due_on or term.status != Term.Status.OPEN:
        return []
    by_instructor: dict[int, Reminder] = defaultdict(lambda: Reminder(0))
    offerings = (CourseOffering.objects.filter(term=term)
                 .select_related("course").prefetch_related("instructors"))
    for off in offerings:
        missing = pending_items(off, require_all_published=deadline.require_all_published)
        if not missing:
            continue
        for instructor in off.instructors.all():
            r = by_instructor[instructor.pk]
            r.instructor_id = instructor.pk
            r.items.append({"offering": off.pk, "course": f"{off.course.code} ({off.section})",
                            "missing": missing})
    return list(by_instructor.values())
```

"Today is *after* the deadline" (`today <= due_on` means no email). The deadline day itself is the last day to finish, so the first reminder arrives the next morning.

**3. The task.**

```python
# apps/reports/tasks.py  (add)
import logging

from celery import shared_task
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Term

from .models import ReminderLog, ReminderPreference
from .reminders import build_reminders

log = logging.getLogger(__name__)
UNSUBSCRIBE_SALT = "polaris.reminders.unsubscribe"


def unsubscribe_token(user) -> str:
    return signing.dumps(user.pk, salt=UNSUBSCRIBE_SALT)


@shared_task
def send_completion_reminders(site_url: str | None = None) -> int:
    from django.conf import settings

    site = (site_url or settings.SITE_URL).rstrip("/")
    today = timezone.localdate()
    opted_out = set(ReminderPreference.objects.filter(enabled=False).values_list("user_id", flat=True))
    sent = 0
    for term in Term.objects.filter(status=Term.Status.OPEN).select_related("completion_deadline"):
        for reminder in build_reminders(term, today):
            if reminder.instructor_id in opted_out:
                continue
            instructor = User.objects.get(pk=reminder.instructor_id)
            try:
                with transaction.atomic():
                    ReminderLog.objects.create(instructor=instructor, term=term, sent_on=today,
                                               items=reminder.items)
            except IntegrityError:
                continue                      # already sent today
            ctx = {
                "instructor": instructor, "term": term, "items": reminder.items, "site": site,
                "deadline": term.completion_deadline.due_on,
                "unsubscribe_url": site + reverse("reports:reminders_unsubscribe",
                                                  kwargs={"token": unsubscribe_token(instructor)}),
            }
            msg = EmailMultiAlternatives(
                subject=f"POlaris: {len(reminder.items)} course(s) still incomplete for {term.name}",
                body=render_to_string("reports/email/reminder.txt", ctx),
                to=[instructor.email],
            )
            msg.attach_alternative(render_to_string("reports/email/reminder.html", ctx), "text/html")
            msg.send()
            sent += 1
            log.info("reminder sent to %s for %s (%d offerings)", instructor.email, term.code, len(reminder.items))
    return sent
```

`SITE_URL` is a new setting. An email link needs an absolute URL, and a Celery task has no request to build one from. Add it:

```python
# config/settings/base.py
SITE_URL = env("SITE_URL", default="http://localhost:8000")
```

Add `SITE_URL=https://polaris-cse.duckdns.org` (and the staging host) to each server `.env` and to `.env.example`.

If sending fails after the log row is committed, that day's email is lost (the row says "sent"). We accept that: a missed reminder is harmless, and tomorrow's goes out. The opposite order (send, then log) risks **duplicate** emails, which annoy instructors and undermine the feature. Say this trade-off out loud in review.

**4. The schedule and the beat container.**

```python
# config/settings/base.py  (add)
from celery.schedules import crontab

CELERY_TIMEZONE = TIME_ZONE              # "Europe/Istanbul": 08:00 means 08:00 in Istanbul
CELERY_BEAT_SCHEDULE = {
    "completion-reminders": {
        "task": "apps.reports.tasks.send_completion_reminders",
        "schedule": crontab(hour=8, minute=0),
    },
    "refresh-materialized-views": {
        "task": "apps.scoring.tasks.refresh_materialized_views",
        "schedule": crontab(hour=3, minute=0),
    },
}
```

If S7-03 already added an export-cleanup entry to this dict, keep it. Merge the dicts, don't replace them.

```yaml
# compose.prod.yml  (add under services:)
  beat:
    image: ${IMAGE}:${IMAGE_TAG}
    command: celery -A config beat -l info --schedule /tmp/celerybeat-schedule
    env_file: .env
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.prod
    depends_on:
      redis: {condition: service_healthy}
    restart: unless-stopped
```

The `--schedule` file records when each job last ran. In `/tmp` it's thrown away on restart, which at worst repeats a job. Our daily-unique constraint makes that harmless. Also add `beat` to the deploy script's `pull` line in `cd.yml`: `docker compose -f compose.prod.yml pull web worker beat`.

Locally, run beat in a third terminal only when you're testing this feature: `uv run celery -A config beat -l info`. To trigger the task without waiting for 08:00:

```bash
uv run python manage.py shell -c "from apps.reports.tasks import send_completion_reminders; print(send_completion_reminders())"
```

**5. The email templates.** Plain text first: many university mail clients show it, and spam filters like a text part.

```django
{# apps/reports/templates/reports/email/reminder.txt #}
Hello {{ instructor.first_name }},

The department's deadline for {{ term.name }} was {{ deadline|date:"j F Y" }}. These courses are still incomplete in POlaris:
{% for item in items %}
{{ item.course }}
{% for m in item.missing %}  - {{ m }}
{% endfor %}  Open: {{ site }}{% url 'catalog:offering' offering_id=item.offering %}
{% endfor %}
You get this email once a day until everything above is done.
Stop these reminders: {{ unsubscribe_url }}

POlaris
```

```django
{# apps/reports/templates/reports/email/reminder.html #}
<!doctype html>
<html><body style="font-family: Arial, sans-serif; font-size: 14px; color: #111;">
<p>Hello {{ instructor.first_name }},</p>
<p>The department's deadline for <strong>{{ term.name }}</strong> was {{ deadline|date:"j F Y" }}. These courses are still incomplete in POlaris:</p>
{% for item in items %}
  <p style="margin-bottom: 4px;"><a href="{{ site }}{% url 'catalog:offering' offering_id=item.offering %}"><strong>{{ item.course }}</strong></a></p>
  <ul style="margin-top: 0;">{% for m in item.missing %}<li>{{ m }}</li>{% endfor %}</ul>
{% endfor %}
<p style="color: #555; font-size: 12px;">You get this email once a day until everything above is done.
<a href="{{ unsubscribe_url }}">Stop these reminders</a>.</p>
</body></html>
```

**6. The head's deadline form.** Reached from the completion panel ("Set deadline" next to the term name).

```python
# apps/reports/forms.py  (add)
from django import forms

from .models import CompletionDeadline


class CompletionDeadlineForm(forms.ModelForm):
    class Meta:
        model = CompletionDeadline
        fields = ["due_on", "require_all_published"]
        widgets = {"due_on": forms.DateInput(attrs={"type": "date"})}
        labels = {"due_on": "Deadline", "require_all_published": "Also require every assessment to be published"}
```

```python
# apps/reports/views.py  (add)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.decorators import require_role
from apps.accounts.models import User
from apps.accounts.permissions import is_head
from apps.catalog.models import Term
from apps.core import audit

from .forms import CompletionDeadlineForm
from .models import CompletionDeadline, ReminderLog, ReminderPreference
from .tasks import UNSUBSCRIBE_SALT


@login_required
@require_role("head")
@require_http_methods(["GET", "POST"])
def term_deadline(request, term_id):
    term = get_object_or_404(Term, pk=term_id)
    instance = CompletionDeadline.objects.filter(term=term).first()
    form = CompletionDeadlineForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        deadline = form.save(commit=False)
        deadline.term, deadline.set_by = term, request.user
        deadline.save()
        audit.record(request.user, "term.deadline", deadline,
                     after={"due_on": deadline.due_on.isoformat(),
                            "require_all_published": deadline.require_all_published})
        messages.success(request, f"Deadline for {term.name} set to {deadline.due_on:%d %b %Y}.")
        return redirect("reports:department")
    logs = ReminderLog.objects.filter(term=term).select_related("instructor")[:50]
    return render(request, "reports/term_deadline.html", {"term": term, "form": form, "logs": logs})


@require_http_methods(["GET", "POST"])
def reminders_unsubscribe(request, token):
    """No login: the link comes from an email. GET shows a button, POST changes the setting,
    because mail scanners follow GET links automatically and would unsubscribe everyone."""
    try:
        user_id = signing.loads(token, salt=UNSUBSCRIBE_SALT, max_age=60 * 60 * 24 * 90)
    except signing.BadSignature:
        return render(request, "reports/unsubscribe.html", {"invalid": True}, status=400)
    user = get_object_or_404(User, pk=user_id)
    pref, _ = ReminderPreference.objects.get_or_create(user=user)
    if request.method == "POST":
        pref.enabled = request.POST.get("enabled") == "1"
        pref.save()
    return render(request, "reports/unsubscribe.html", {"pref": pref, "token": token})
```

`Term` belongs to no program in our model, so any head may set a term's deadline. That matches §3.3, where heads manage terms. If T2.6 (two programs) is pulled in, terms stay shared, which is fine: a university has one academic calendar.

```python
# apps/reports/urls.py  (add)
    path("department/terms/<int:term_id>/deadline/", views.term_deadline, name="term_deadline"),
    path("reminders/unsubscribe/<str:token>/", views.reminders_unsubscribe, name="reminders_unsubscribe"),
```

```django
{# apps/reports/templates/reports/unsubscribe.html #}
{% extends "base.html" %}
{% block title %}Reminder emails{% endblock %}
{% block content %}
<div class="container py-5" style="max-width: 560px">
  {% if invalid %}
    <h1 class="h4">This link has expired</h1>
    <p>Open any reminder email from the last 90 days and use its link, or ask the department head.</p>
  {% else %}
    <h1 class="h4">Completion reminders</h1>
    <p>Reminders are currently <strong>{{ pref.enabled|yesno:"on,off" }}</strong> for {{ pref.user.email }}.</p>
    <form method="post">
      {% csrf_token %}
      {% if pref.enabled %}
        <input type="hidden" name="enabled" value="0">
        <button class="btn btn-outline-danger" type="submit">Stop reminder emails</button>
      {% else %}
        <input type="hidden" name="enabled" value="1">
        <button class="btn btn-primary" type="submit">Turn reminders back on</button>
      {% endif %}
    </form>
  {% endif %}
</div>
{% endblock %}
```

```django
{# apps/reports/templates/reports/term_deadline.html #}
{% extends "base.html" %}
{% block title %}Deadline · {{ term.name }}{% endblock %}
{% block content %}
<div class="container py-4" style="max-width: 760px">
  <h1 class="h4">Completion deadline for {{ term.name }}</h1>
  <form method="post" class="card card-body mb-4">
    {% csrf_token %}
    {{ form.as_div }}
    <p class="small text-body-secondary mb-3">From the day after the deadline, instructors with incomplete courses get one email each morning at 08:00.</p>
    <div><button class="btn btn-primary" type="submit">Save deadline</button></div>
  </form>
  <h2 class="h5">Reminders sent</h2>
  {% include "includes/empty_state.html" with title="Nothing sent yet" message="No reminders sent yet." only %}
  {% if logs %}
  <table class="table table-sm">
    <thead><tr><th>Date</th><th>Instructor</th><th>Courses</th></tr></thead>
    <tbody>{% for l in logs %}<tr><td>{{ l.sent_on|date:"j M" }}</td><td>{{ l.instructor.get_full_name }}</td><td>{% for i in l.items %}{{ i.course }}{% if not forloop.last %}, {% endif %}{% endfor %}</td></tr>{% endfor %}</tbody>
  </table>
  {% endif %}
</div>
{% endblock %}
```

Wrap the `empty_state` include in `{% if not logs %}` if your S1-09 component doesn't hide itself. Add both URLs to the permission matrix: `term_deadline` is head-only, while `reminders_unsubscribe` is public and returns 400 with a bad token.

### Tests

```python
# apps/reports/tests/test_reminders.py
from datetime import date, timedelta

import pytest
from django.core import mail
from django.urls import reverse

from apps.catalog.models import Term
from apps.core.tests.factories import OfferingFactory, TermFactory, UserFactory
from apps.core.tests.scenarios import elif_scenario
from apps.reports.models import CompletionDeadline, ReminderLog, ReminderPreference
from apps.reports.reminders import build_reminders, pending_items
from apps.reports.tasks import send_completion_reminders, unsubscribe_token

pytestmark = pytest.mark.django_db
TODAY = date(2026, 11, 21)


@pytest.fixture
def term_with_gap():
    term = TermFactory(status=Term.Status.OPEN, starts_on=date(2026, 9, 21), ends_on=date(2027, 1, 20))
    head = UserFactory()
    CompletionDeadline.objects.create(term=term, due_on=date(2026, 11, 20), set_by=head)
    empty = OfferingFactory(term=term)
    instructor = UserFactory()
    empty.instructors.add(instructor)
    return term, empty, instructor


def test_empty_offering_lists_every_missing_step(term_with_gap):
    _, empty, _ = term_with_gap
    assert pending_items(empty, require_all_published=False) == ["Add learning outcomes", "Add assessments"]


def test_complete_offering_is_not_reminded():
    s = elif_scenario()
    assert pending_items(s.offering, require_all_published=True) == []


def test_no_reminders_on_or_before_deadline(term_with_gap):
    term, _, _ = term_with_gap
    assert build_reminders(term, date(2026, 11, 20)) == []
    assert len(build_reminders(term, TODAY)) == 1


def test_one_email_per_instructor_per_day(term_with_gap, settings, monkeypatch):
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: TODAY)
    settings.SITE_URL = "https://polaris.test"
    assert send_completion_reminders() == 1
    assert send_completion_reminders() == 0          # second run the same day: skipped
    assert len(mail.outbox) == 1
    assert "Add learning outcomes" in mail.outbox[0].body
    assert "https://polaris.test/offerings/" in mail.outbox[0].body
    assert ReminderLog.objects.count() == 1


def test_instructor_with_two_courses_gets_one_email(term_with_gap, monkeypatch):
    term, _, instructor = term_with_gap
    OfferingFactory(term=term).instructors.add(instructor)
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: TODAY)
    send_completion_reminders()
    assert len(mail.outbox) == 1
    assert len(ReminderLog.objects.get().items) == 2


def test_opted_out_instructor_gets_nothing(term_with_gap, monkeypatch):
    _, _, instructor = term_with_gap
    ReminderPreference.objects.create(user=instructor, enabled=False)
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: TODAY)
    assert send_completion_reminders() == 0


def test_closed_term_sends_nothing(term_with_gap, monkeypatch):
    term, _, _ = term_with_gap
    term.status = Term.Status.CLOSED
    term.save()
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: TODAY)
    assert send_completion_reminders() == 0


def test_unsubscribe_get_does_not_change_anything(client, term_with_gap):
    _, _, instructor = term_with_gap
    url = reverse("reports:reminders_unsubscribe", kwargs={"token": unsubscribe_token(instructor)})
    client.get(url)
    assert ReminderPreference.objects.get(user=instructor).enabled is True
    client.post(url, {"enabled": "0"})
    assert ReminderPreference.objects.get(user=instructor).enabled is False


def test_tampered_token_is_rejected(client):
    url = reverse("reports:reminders_unsubscribe", kwargs={"token": "1:forged"})
    assert client.get(url).status_code == 400


def test_deadline_passes_to_next_day_only(term_with_gap):
    term, _, _ = term_with_gap
    due = term.completion_deadline.due_on
    assert build_reminders(term, due + timedelta(days=1))
```

`monkeypatch.setattr("django.utils.timezone.localdate", …)` works because the task calls `timezone.localdate()` through the module, not through a name imported at module load. Keep the call written as `timezone.localdate()` in the task, or this test stops patching anything.

### Check it works

1. As the head, open the dashboard's completion panel and click **Set deadline** for 2026F. Choose yesterday's date and save.
2. Run the task from the shell (step 4). In dev the email prints in the `runserver` console. Check that it lists the seeded offering with no mapping.
3. Run it again. It prints `0`, and no second email appears.
4. Open the unsubscribe link from the console email in a private window, click **Stop reminder emails**, and run the task again. That instructor gets nothing.
5. After deploy: `docker compose -f compose.prod.yml logs beat` on staging shows `Scheduler: Sending due task completion-reminders` at 08:00.

### Done when

| AC (T2.2) | Proved by |
|---|---|
| 1. Head sets a deadline per term | `term_deadline` view, manual check 1 |
| 2. Daily email after the deadline to instructors with incomplete offerings, one per instructor | `test_one_email_per_instructor_per_day`, `test_instructor_with_two_courses_gets_one_email` |
| 3. Nothing on or before the deadline, or for closed terms | `test_no_reminders_on_or_before_deadline`, `test_closed_term_sends_nothing` |
| 4. One-click opt-out that mail scanners can't trigger | `test_unsubscribe_get_does_not_change_anything`, `test_tampered_token_is_rejected` |
| 5. Every email logged and visible to the head | `ReminderLog`, deadline page table |
| 6. Never two emails a day, even with retries | `one_reminder_per_day` constraint, second-run test |

### Commits and PR

```
Add completion deadlines and reminder log models (#82)
Send daily completion reminders from Celery beat (#82)
Add signed one-click unsubscribe for reminder emails (#82)
Run a beat container in staging and production (#82)
```

PR title: `S8-03 Completion reminders with Celery beat (T2.2)`. Mention in the description that the **deploy adds a container**, so whoever merges watches the first CD run.

---

# Sprint 9 — Tier 2 continued, reports drafted (Mon 14 – Sun 20 Dec)

**Sprint goal:** *"Both final reports exist as complete first drafts with real evidence, and POlaris speaks Turkish, reports its own errors, supports TAs, imports OBS pages and runs a second program."*

| Order | ID | Story | Pts | Owner |
|---|---|---|---|---|
| 1 | S9-01 | Final CSE 311 report first draft | 3 | C + all |
| 2 | S9-02 | Final CSE 321 report first draft | 3 | A + all |
| 3 | S9-04 | T2.10 Sentry + uptime check | 1 | C |
| 4 | S9-05 | T2.8 TA role | 3 | A |
| 5 | S9-03 | T2.5 Turkish / English | 5 | B |
| 6 | S9-07 | T2.6 Multi-program UI + second seeded program | 3 | C |
| 7 | S9-06 | T2.9 OBS course page import | 3 | A |

The reports are first because they are graded and the features are not. Monday 21 Dec is the freeze, and the CSE 311 midterm is the next day. Nothing that isn't merged by Sunday night ships.

**Merge order.** S9-04 any time (settings only). S9-05 before S9-03: i18n touches every template, so it's much easier to translate the TA templates once they exist than to merge two big template diffs. S9-07 after S9-03 for the same reason. S9-06 last: it's the most likely to be dropped (it depends on an external site we don't control).

**What must work on staging by Sunday:**
- `docs/reports/cse311/report.md` and `docs/reports/cse321/report.md` have every section filled with real figures, and each has been read by one other person.
- The language switcher flips the whole UI to Turkish. PO names come in Turkish, and scores print as `85,0`.
- A deliberately raised test error appears in Sentry within a minute. The uptime workflow is green.
- A TA account enters draft grades on its one course and gets 404 for publish, mapping and every other course.
- The head of the second program (BME) sees only BME. CSE's head sees only CSE.
- An OBS URL import produces a reviewable extraction, or the story is dropped and the drop is recorded.

---

## S9-01 · Final CSE 311 report, first draft

**Points:** 3 · **Owner:** Person C (editor) + everyone writes their part · **Branch:** `docs/S9-01-cse311-report` · **Depends on:** evidence collected every sprint (§9.5, §9.9, §9.10)

### Goal

A complete draft of the six-section CSE 311 report, with every figure and table generated from real data, by Sunday 20 Dec. The final edit and printing are S10-03. A draft with all the evidence in place is worth far more than polished prose with holes. The report format: printed, **no title page**, figures and code at **125%** zoom, six sections (§13.4).

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `docs/reports/cse311/report.md` | create | The report source (Markdown → PDF with the same WeasyPrint we already run, or paste into Google Docs: team's choice, decide on Monday) |
| `docs/reports/cse311/figures/` | create | Every figure as PNG/SVG, named `s<section>-<what>.png` |
| `docs/process/scripts/issues_by_assignee.sh` | create | Section 2 data |
| `docs/process/scripts/velocity_chart.py` | create | Section 2 chart |
| `docs/process/scripts/ci_runs.sh` | create | Section 5 run summaries |

### Steps

**1. Monday stand-up: assign sections.** Use the owners from §13.4. Each owner writes a draft of their section by **Thursday 17 Dec**. Person C merges, makes the voice consistent, and checks every claim against evidence on Friday–Saturday. Everyone reads the whole draft on Sunday.

| Section | Owner | Draft due |
|---|---|---|
| 1 Punchline, key ingredient, backlog tool | C | Wed |
| 2 Work split, difficulty, sprint length, sprints, velocity | C (with numbers from A) | Thu |
| 3 Contributors and code frequency charts | A | Wed |
| 4 Branching model | A | Wed |
| 5 CI/CD YAML and run summaries | C | Thu |
| 6 Getting Real principles with chapters | B | Thu |

**2. Section 1 — punchline.** Use §1.2 word for word as the starting point and shorten it to three sentences. The **key ingredient** is the syllabus wizard: "an instructor uploads a syllabus and gets a reviewed, complete course setup in about two minutes". Back it with the numbers from `docs/process/eval/` (§7.9): "found 34 of 35 learning outcomes and every assessment weight in 5 real syllabi". Describe the backlog tool: GitHub Projects, with one screenshot of the board (Sprint view) and one of the backlog table with the Points/Sprint/Tier fields visible. Take the screenshots on staging-era data, at 125% browser zoom so the text survives printing.

**3. Section 2 — who did what.** The section must say "who carried out what explicitly". The issue list *is* that evidence:

```bash
#!/usr/bin/env bash
# docs/process/scripts/issues_by_assignee.sh: closed stories per person, as a Markdown table
set -euo pipefail
gh issue list --state closed --limit 500 \
  --json number,title,assignees,labels,closedAt \
  --jq '.[] | [(.assignees | map(.login) | join(", ")), "#\(.number)", .title,
               ((.labels | map(.name) | map(select(startswith("pts:"))) | first) // "")] | @tsv' \
| sort \
| awk -F'\t' 'BEGIN { print "| Who | Issue | Story | Points |"; print "|---|---|---|---|" }
              { printf "| %s | %s | %s | %s |\n", $1, $2, $3, $4 }'
```

If points live in a Projects custom field rather than a `pts:` label (§9.3 uses a Points field), export the project view instead: Projects → table view → `…` → **Export view data** (CSV), then sum by assignee in a spreadsheet. Either way the numbers in the report must equal the numbers in `velocity.md`.

**Difficulty assessment.** Explain planning poker with Fibonacci points (§9.4) in one paragraph. Then give one concrete example where we disagreed: show the cards (e.g. "S6-02 review screen: 5, 8, 13 → discussed the two grids → 8"), and say how the real effort compared afterwards.

**Sprint length and count.** "One-week sprints (Mon–Sun). Sprint 0 (setup, 3 days) plus Sprints 1–10." State how many were completed by the report date.

**Velocity.** Generate the chart from `docs/process/velocity.md`. The table there has columns `Sprint | Planned | Completed`. Run the script with matplotlib pulled in only for this run (`--with`), so it doesn't become a project dependency:

```python
# docs/process/scripts/velocity_chart.py
"""Bar chart of planned vs completed points per sprint, from docs/process/velocity.md.
Run:  uv run --with matplotlib python docs/process/scripts/velocity_chart.py"""
import re
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
rows = []
for line in (ROOT / "docs/process/velocity.md").read_text().splitlines():
    m = re.match(r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", line)
    if m:
        rows.append(tuple(int(x) for x in m.groups()))

sprints = [f"S{r[0]}" for r in rows]
planned = [r[1] for r in rows]
done = [r[2] for r in rows]
x = range(len(rows))

fig, ax = plt.subplots(figsize=(8, 3.6), dpi=200)
ax.bar([i - 0.2 for i in x], planned, width=0.4, label="Planned", color="#9aa8c7")
ax.bar([i + 0.2 for i in x], done, width=0.4, label="Completed", color="#1f3a93")
avg = sum(done) / len(done)
ax.axhline(avg, color="#b02a37", linestyle="--", linewidth=1, label=f"Average velocity {avg:.1f}")
ax.set_xticks(list(x), sprints)
ax.set_ylabel("Story points")
ax.spines[["top", "right"]].set_visible(False)
ax.legend(frameon=False, fontsize=8)
fig.tight_layout()
out = ROOT / "docs/reports/cse311/figures/s2-velocity.png"
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out)
print(f"wrote {out}")
```

Comment on the dip in Sprints 4–5 (checkpoints and midterms), because it was planned (Part 11). A planned dip shows the team forecasts honestly, and that's worth saying.

**4. Section 3 — contributor charts.** On Sunday 20 Dec, and again on 27 Dec for the final version: GitHub → Insights → **Contributors** (default branch `develop`), and **Code frequency**. Screenshot both at 125% zoom. Under each, add one sentence that explains anything odd. For example: "Person A's large addition in week 2 is the generated initial migrations (≈ 1,400 lines)". Graders notice spikes, and an unexplained one looks like copy-paste.

If someone's commits are missing from the chart, their commit email isn't linked to their GitHub account (§9.6 trap). Fix it now by adding that email under GitHub → Settings → Emails. GitHub then re-attributes past commits within a few hours. Don't rewrite history.

**5. Section 4 — branching model.** Use the Mermaid diagram from §9.6, exported as SVG (`npx -y @mermaid-js/mermaid-cli -i branching.mmd -o s4-branching.svg`), plus **real** examples pulled from history:

```bash
git log --oneline --merges origin/main            # release merges develop → main
git tag -l 'v*' --sort=creatordate                # every release
git log --oneline --grep 'hotfix' --all           # any hotfix branches
gh pr list --state merged --base main --limit 20 --json number,title,headRefName
```

Name one release PR and one hotfix PR (if we had one) by number. If we never needed a hotfix, say so honestly, and point to the rule in §9.6 that says what we would have done.

**6. Section 5 — CI/CD.** Paste `.github/workflows/ci.yml` and `cd.yml` in full, in a monospace font at 125%. Then summarise runs. The sprint `runs.md` files already hold one example per sprint. For the totals:

```bash
#!/usr/bin/env bash
# docs/process/scripts/ci_runs.sh: run counts and durations per workflow
set -euo pipefail
for wf in CI CD; do
  gh run list --workflow "$wf" --limit 300 --json conclusion,createdAt,updatedAt \
  | python3 -c '
import json, sys
from datetime import datetime
runs = json.load(sys.stdin)
fmt = "%Y-%m-%dT%H:%M:%SZ"
dur = [(datetime.strptime(r["updatedAt"], fmt) - datetime.strptime(r["createdAt"], fmt)).total_seconds() / 60 for r in runs]
ok = sum(r["conclusion"] == "success" for r in runs)
print(f"'"$wf"': {len(runs)} runs, {ok} succeeded, {len(runs) - ok} failed/cancelled, median {sorted(dur)[len(dur)//2]:.1f} min")
'
done
```

Include **one failed run and its fix** (from `runs.md`): the red check, the log line that explains it, the fixing commit, and the green re-run. This is the best evidence that CI works, so give it a full half page.

**7. Section 6 — Getting Real.** Start from the §13.6 table. Each principle gets a chapter citation and **one concrete example from our project with a link or figure**, never a generic restatement. Include the critical note from "How to use this document" (Ch. 11 says specs are bad, here's what we did about it). Graders reward critical reading over agreement. Aim for 8–10 principles done well rather than all 19 thinly.

**8. Assemble and render.** If the team chooses Markdown → PDF, render it with the WeasyPrint we already have (Pandoc would be one more tool to install):

```bash
uv run --with markdown python - <<'PY'
from pathlib import Path
import markdown
from weasyprint import HTML
src = Path("docs/reports/cse311/report.md").read_text()
body = markdown.markdown(src, extensions=["tables", "fenced_code"])
css = """@page { size: A4; margin: 18mm 16mm; }
body { font-family: 'DejaVu Sans', sans-serif; font-size: 10.5pt; line-height: 1.4; }
pre, code { font-family: 'DejaVu Sans Mono', monospace; font-size: 9pt; }
pre { white-space: pre-wrap; background: #f6f8fa; padding: 3mm; }
img { max-width: 100%; } table { border-collapse: collapse; } td, th { border: 0.4pt solid #bbb; padding: 1mm 2mm; }"""
HTML(string=f"<style>{css}</style>{body}", base_url="docs/reports/cse311/").write_pdf("docs/reports/cse311/report.pdf")
print("wrote docs/reports/cse311/report.pdf")
PY
```

"Code at 125%" means 125% of the body text size. Body 10.5pt × 1.25 ≈ 13pt, so if graders read it literally, raise `pre` to 13pt. Ask the TA which reading they mean on Monday, and record the answer in `docs/process/`.

### Tests

None: documentation. The checks are the review checklist in "Done when".

### Check it works

Open `report.pdf`. There's no title page, sections 1–6 are in order, every figure is readable when printed at 100% on A4 (print one page to check), the code is large enough, and every number in Section 2 matches `velocity.md`.

### Done when

- [ ] All six sections have content, figures and the evidence named in §13.4.
- [ ] Every member has read the whole draft and left comments on the PR.
- [ ] The issue list, velocity chart, contributor charts and run summary are generated from real data, with commands recorded in `docs/process/scripts/`.
- [ ] Open questions for the TA (125% meaning, page limit if any) were sent on Monday.

### Commits and PR

```
Draft CSE 311 report sections 1-6 with process evidence
Add scripts that regenerate report tables and charts
```

PR title: `S9-01 CSE 311 final report, first draft`. Target `develop`. Docs-only PRs still go through review.

---

## S9-02 · Final CSE 321 report, first draft

**Points:** 3 · **Owner:** Person A (editor) + everyone · **Branch:** `docs/S9-02-cse321-report` · **Depends on:** S4-01 diagrams, S8-02 snapshots

### Goal

A complete draft of the six-section CSE 321 report (§13.5). Its heart is Sections 3–5: the data model, real table sizes, indexes with `EXPLAIN ANALYZE` proof, materialized views, and transactions with isolation levels. Every claim is backed by a query run on the seeded database.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `docs/reports/cse321/report.md` | create | Report source |
| `docs/reports/cse321/figures/` | create | Architecture, class and ER diagrams (exported), plan screenshots |
| `docs/reports/cse321/sql/*.sql` | create | Every query the report quotes, runnable as-is |
| `docs/reports/cse321/section4-evidence.md` | modify (from S8-02) | Plans and timings |

### Steps

**1. Section owners and dates.** From §13.5: Section 1 (B, Wed), 2 (A, Wed), 3 (A, Thu), 4 (A, Thu), 5 (B, Thu), 6 (C, Wed: reuse CSE 311 Section 2 data). A is the editor.

**2. Section 2 — architecture and class diagrams.** Re-export the §4.2 Mermaid diagram so it includes everything that exists now: Celery beat (S8-03), Sentry (S9-04), the Claude API, SMTP and OBS (S9-06). The brief names "databases, web apps, cache, notification services, 3rd-party integrations" explicitly, so label each box with one of those words. Generate the class diagram from the real models instead of drawing it by hand. It's then guaranteed correct:

```bash
uv run --with django-extensions --with pydot python manage.py graph_models \
  accounts catalog outcomes grading scoring ingestion reports core \
  --settings=config.settings.dev -g -o docs/reports/cse321/figures/s2-class-diagram.png
```

`graph_models` needs `django_extensions` in `INSTALLED_APPS`. Add it temporarily to `dev.py` for this one command (`INSTALLED_APPS += ["django_extensions"]`), and don't commit that line. It also needs Graphviz installed (`brew install graphviz` / `apt install graphviz`).

**3. Section 3 — data model and sizes.** The ER diagram is §5.1, updated with `StudentLOScore`, `StudentPOScore`, `ExportJob`, `TranscriptIssue`, the reminder models and `OfferingAssistant`. For "each table's final rows, columns and raw size", run on **production after the final reseed** (S10-02). The draft uses staging numbers, labelled as such.

```sql
-- docs/reports/cse321/sql/table_sizes.sql
-- Exact counts (n_live_tup is an estimate; the report needs real numbers)
SELECT format('SELECT %L AS table_name, count(*) AS rows FROM %I', relname, relname)
FROM pg_stat_user_tables ORDER BY relname \gexec

SELECT c.relname AS table_name,
       (SELECT count(*) FROM information_schema.columns col WHERE col.table_name = c.relname) AS columns,
       pg_size_pretty(pg_relation_size(c.oid))       AS data_size,
       pg_size_pretty(pg_indexes_size(c.oid))        AS index_size,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'm')     -- tables and materialized views
ORDER BY pg_total_relation_size(c.oid) DESC;
```

Run it with `psql -f table_sizes.sql` (the `\gexec` line only works in psql). **Star or snowflake; normalised or not:** the operational tables are 3NF. The reporting side (snapshot tables plus materialized views) is a star schema with fact = a student's score on an outcome, and dimensions student/cohort, term, offering/course, LO and PO (§5.5). Draw the star separately: it's a small, clear figure and it answers the question directly.

**4. Section 4 — indexes, views, partitioning, replication, fault tolerance.** For each index in §5.6, one query, its plan, and one sentence. Example:

```sql
-- docs/reports/cse321/sql/idx_grade_enrollment.sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT g.* FROM grading_grade g
JOIN catalog_enrollment e ON e.id = g.enrollment_id
WHERE e.student_id = (SELECT id FROM accounts_user WHERE email = 'elif.yildiz@demo.polaris');
```

Show the plan **with** the index (`Index Scan using grade_enrollment_idx`) and **without** it, inside a transaction you roll back. PostgreSQL DDL is transactional, so dropping an index inside `BEGIN … ROLLBACK` is safe on staging:

```sql
BEGIN;
DROP INDEX grade_enrollment_idx;
EXPLAIN (ANALYZE, BUFFERS) SELECT ... ;      -- same query: now a Seq Scan
ROLLBACK;                                     -- the index is back
```

Materialized views: use the before/after evidence from S8-02. Partitioning: the arithmetic from §5.6 (≈ 19,000 grades per term), plus the exact DDL we *would* run, so the discussion is concrete:

```sql
-- docs/reports/cse321/sql/partitioning_sketch.sql  (NOT applied: discussion only)
CREATE TABLE grading_grade_p (LIKE grading_grade INCLUDING ALL, term_id bigint NOT NULL)
    PARTITION BY LIST (term_id);
CREATE TABLE grading_grade_2026f PARTITION OF grading_grade_p FOR VALUES IN (3);
```

Fault tolerance: Celery retry configuration (quote the decorators), Docker health checks, the `acks_late` setting, the nightly `pg_dump`, and a **restore drill**: restore last night's dump into a scratch database, run `rebuild_scores --check` against it, and paste the output.

**5. Section 5 — transactions.** The §5.6 table, plus for each row the test that proves rollback (e.g. B7 AC2's "crash halfway through publish leaves zero grades published"). Paste the test code. Explain why READ COMMITTED plus `SELECT … FOR UPDATE` is enough for writes, and why the department export uses REPEATABLE READ. Show the export code's first statement.

**6. Render** with the same snippet as S9-01, paths changed to `cse321`.

### Tests

None. The SQL files are the reproducibility evidence: any grader-facing number must be produced by a file in `docs/reports/cse321/sql/`.

### Check it works

Each SQL file runs with no errors against staging (`psql -f`), and every number in the report matches its output.

### Done when

- [ ] Six sections drafted; Sections 3–5 backed by SQL files and pasted plans.
- [ ] Class diagram generated from code, not drawn.
- [ ] Restore drill done and recorded.
- [ ] Everyone has read the draft.

### Commits and PR

```
Draft CSE 321 report with data model, index and transaction evidence
Add runnable SQL for every number quoted in the CSE 321 report
```

PR title: `S9-02 CSE 321 final report, first draft`.

---

## S9-04 · Error monitoring with Sentry and an uptime check (T2.10)

**Points:** 1 · **Owner:** Person C · **Branch:** `feature/S9-04-monitoring` · **Depends on:** S3-06

### Goal

When something breaks on production, we hear about it before a user (or a grader) does. Unhandled exceptions in the web app and the Celery worker are sent to Sentry with a stack trace. A scheduled GitHub Actions workflow calls `/healthz` every 15 minutes and fails, which emails the repo owner, if the site is down. Delivers T2.10 AC 1–4.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `pyproject.toml` / `uv.lock` | modify | `sentry-sdk` |
| `config/settings/prod.py` | modify | `sentry_sdk.init` when `SENTRY_DSN` is set |
| `apps/core/views.py`, `config/urls.py` | modify | `sentry_check` view (superuser only) |
| `apps/core/tasks.py` | create | `sentry_check_task` (raises on purpose) |
| `.github/workflows/uptime.yml` | create | Scheduled health check |
| `.env.example` | modify | `SENTRY_DSN`, `SENTRY_ENVIRONMENT` |

### Steps

**1. Create the Sentry project.** sentry.io → free Developer plan → New project → platform **Django** → name `polaris`. Copy the DSN. Put it in each server's `.env` as `SENTRY_DSN=…` and `SENTRY_ENVIRONMENT=staging` or `production`. The DSN is not a password (it can only *send* events), but keep it out of Git anyway, because anyone with it can flood our quota.

**2. Install and initialise.**

```bash
uv add "sentry-sdk[django,celery]"
```

```python
# config/settings/prod.py  (add at the end)
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=env("SENTRY_ENVIRONMENT", default="production"),  # noqa: F405
        release=env("IMAGE_TAG", default=None),  # noqa: F405  the commit SHA the CD pipeline deployed
        integrations=[DjangoIntegration(), CeleryIntegration()],
        send_default_pii=False,          # no emails, IPs or cookies leave our server
        traces_sample_rate=0.05,         # 5% of requests get performance traces: free-plan friendly
    )
```

`send_default_pii=False` matters here. Our users' data is student grades. By default the SDK doesn't send request bodies or cookies with this setting off, and we keep it off. `release=IMAGE_TAG` means every error in Sentry shows which commit was running, which links an error directly to a CD run (good Section 5 material).

The worker runs with the same settings module (`config.settings.prod`), so the Celery integration is active there too.

**3. A safe way to prove it works.** Testing by breaking production would be silly, so add a superuser-only URL that raises on purpose:

```python
# apps/core/views.py  (add)
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404


@staff_member_required
def sentry_check(request):
    if not request.user.is_superuser:
        raise Http404
    raise RuntimeError("Sentry check: this error was raised on purpose from /ops/sentry-check/")
```

```python
# config/urls.py  (add to urlpatterns)
    path("ops/sentry-check/", core_views.sentry_check, name="sentry_check"),
```

And the worker twin, so the Celery integration can be checked the same way:

```python
# apps/core/tasks.py
from celery import shared_task


@shared_task
def sentry_check_task():
    raise RuntimeError("Sentry check: this error was raised on purpose in the Celery worker")
```

Add the URL to the permission matrix: every role 404 or a redirect to login, and superuser 500. In the matrix test, assert the superuser case with `client.raise_request_exception = False`.

**4. The uptime workflow.** GitHub runs scheduled workflows from the default branch (`develop`). Its schedule uses UTC, and the minimum interval is 5 minutes. We use 15 minutes, which is plenty for a student project and stays well inside the free minutes. A failed scheduled run emails whoever last edited the workflow's cron, so Person C commits this file.

```yaml
# .github/workflows/uptime.yml
name: Uptime

on:
  schedule:
    - cron: "*/15 * * * *"
  workflow_dispatch:

jobs:
  ping:
    runs-on: ubuntu-latest
    timeout-minutes: 3
    strategy:
      fail-fast: false
      matrix:
        host: [polaris-cse.duckdns.org, staging-polaris-cse.duckdns.org]
    steps:
      - name: GET /healthz
        run: |
          for i in 1 2 3; do
            if curl -fsS --max-time 10 "https://${{ matrix.host }}/healthz"; then exit 0; fi
            sleep 10
          done
          echo "::error::${{ matrix.host }} failed its health check 3 times"
          exit 1
```

Three tries with 10 seconds between them prevents a false alarm from a single slow response during a deploy.

### Tests

```python
# apps/core/tests/test_sentry_check.py
import pytest
from django.urls import reverse

from apps.core.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_sentry_check_raises_for_superuser(client):
    client.force_login(UserFactory(is_staff=True, is_superuser=True))
    client.raise_request_exception = False
    assert client.get(reverse("sentry_check")).status_code == 500


def test_sentry_check_hidden_from_normal_users(client):
    client.force_login(UserFactory())
    assert client.get(reverse("sentry_check")).status_code == 302   # staff_member_required → admin login
```

### Check it works

1. Deploy to staging, log in as the superuser, open `/ops/sentry-check/`. You see a 500 page, and within a minute the Sentry issue appears with `environment: staging` and the commit SHA as release.
2. Prove the worker side the same way: `docker compose -f compose.prod.yml exec web python manage.py shell -c "from apps.core.tasks import sentry_check_task; sentry_check_task.delay()"`. The worker log shows the exception, and Sentry shows a second issue tagged `celery.task: apps.core.tasks.sentry_check_task`.
3. Actions → Uptime → **Run workflow**. Both matrix jobs are green.

### Done when

| AC (T2.10) | Proved by |
|---|---|
| 1. Web errors reach Sentry with release and environment | Check 1 |
| 2. Worker errors reach Sentry | Check 2 |
| 3. No personal data sent | `send_default_pii=False`; inspect one event's "Request" section: no cookies, no body |
| 4. Downtime alerts within 15 minutes | `uptime.yml`, check 3 |

### Commits and PR

```
Report web and worker errors to Sentry in staging and production
Add superuser-only route that raises to verify error reporting
Ping both environments' health checks every 15 minutes
```

PR title: `S9-04 Sentry and uptime monitoring (T2.10)`.

---

## S9-05 · Teaching assistant role (T2.8)

**Points:** 3 · **Owner:** Person A · **Branch:** `feature/S9-05-ta-role` · **Depends on:** S2-02, S2-06, S3-01

### Goal

Large courses have TAs who type in quiz and lab grades. Today the instructor has to share their password or type everything themselves. This story adds a per-offering **assistant** assignment. A TA can open the grade sheet of the courses they assist and enter **draft** grades. They cannot publish, change weights or setup, see results, or see any other course. Delivers T2.8 AC 1–5.

Why not a fourth `ProgramMembership` role? Being a TA is a fact about **one offering**, not about the program. The same person is a student in CSE 321 and a TA in CSE 101 in the same term. That's the same reasoning as decision D6, one level down. So it's an assignment table like `CourseOffering.instructors`, but kept separate so that "instructor" keeps meaning "full control".

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/catalog/models.py` | modify | `OfferingAssistant` |
| `apps/catalog/services.py` | modify | `add_assistant`, `remove_assistant` |
| `apps/catalog/selectors.py` | modify | `assisted_offerings(user)` |
| `apps/accounts/permissions.py` | modify | `is_assistant`, `can_grade_offering`; `OfferingPerms.can_grade`, `OfferingPerms.is_assistant` |
| `apps/accounts/decorators.py` | modify | `require_offering_access(*, edit=False, allow_assistants=False)` |
| `apps/grading/views.py` | modify | `sheet` and `cell` accept assistants |
| `apps/grading/services.py` | modify | `save_grade` re-checks `can_grade_offering` |
| `apps/grading/templates/grading/sheet.html` | modify | Inputs use `perms_for.can_grade`; publish buttons use `perms_for.can_publish` |
| `apps/catalog/views.py`, `urls.py` | modify | `offering_assistants`, `assisting` |
| `apps/catalog/templates/catalog/{offering_assistants,assisting}.html` | create | Pages |
| `apps/core/context_processors.py` | modify | "Courses I assist" nav item |
| `apps/accounts/tests/test_assistant_permissions.py` | create | Matrix rows for the assistant role |
| `apps/catalog/tests/test_assistants.py` | create | Service tests |

### Steps

**1. The model.**

```python
# apps/catalog/models.py  (add)
class OfferingAssistant(models.Model):
    """A TA on one offering: may enter draft grades there, nothing else (T2.8)."""
    offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name="assistants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assisting")
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["offering", "user"], name="uniq_assistant")]
```

**2. Permissions.** Two new helpers, and two new fields on `OfferingPerms`. `can_grade_offering` is the single place that says who may write a draft grade. The closed-term rule applies to TAs exactly as it does to instructors.

```python
# apps/accounts/permissions.py  (add)
def is_assistant(user, offering) -> bool:
    if not user.is_authenticated:
        return False
    return offering.assistants.filter(user=user).exists()


def can_grade_offering(user, offering) -> bool:
    """Draft grade entry: anyone who can edit the offering, or one of its TAs while the term is open."""
    if can_edit_offering(user, offering):
        return True
    return is_assistant(user, offering) and offering.term.status != offering.term.Status.CLOSED
```

Then in `OfferingPerms` (the frozen dataclass from S2-02) add two fields, `can_grade: bool` and `is_assistant: bool`, and fill them in `offering_perms`:

```python
# apps/accounts/permissions.py  (inside offering_perms, where the dataclass is built)
    assistant = is_assistant(user, offering)
    return OfferingPerms(
        can_view=can_view,
        can_edit=can_edit,
        can_publish=can_edit,                    # TAs never publish
        is_closed=is_closed,
        can_grade=can_edit or (assistant and not is_closed),
        is_assistant=assistant,
    )
```

Keep whatever local variable names S2-02 used for `can_view`, `can_edit` and `is_closed`. The two new lines are what matters. **`can_view_offering` stays false for TAs.** A TA has no business on the results page, which shows every student's LO scores. They only see the grade sheet they are entering.

**3. The decorator gains one opt-in flag.** Existing callers don't pass `allow_assistants`, so their behaviour is unchanged. Only the two grade-entry views opt in. Here's the complete decorator. Replace S2-02's version with it, which keeps the same signature plus one keyword:

```python
# apps/accounts/decorators.py
from functools import wraps

from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.catalog.models import CourseOffering

from .permissions import can_edit_offering, can_view_offering, is_assistant, offering_perms


def require_offering_access(*, edit=False, allow_assistants=False):
    """Load the offering from the `offering_id` URL kwarg and 404 unless allowed.
    edit=True needs edit rights. allow_assistants=True also admits the offering's TAs
    (for edit=True only while the term is open). Passes offering= and perms_for= to the view."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, offering_id, **kwargs):
            offering = get_object_or_404(
                CourseOffering.objects.select_related("course__program", "term"), pk=offering_id)
            user = request.user
            allowed = can_edit_offering(user, offering) if edit else can_view_offering(user, offering)
            if not allowed and allow_assistants and is_assistant(user, offering):
                allowed = (not edit) or offering.term.status != offering.term.Status.CLOSED
            if not allowed:
                raise Http404
            perms = offering_perms(user, offering)
            return view(request, *args, offering_id=offering_id, offering=offering, perms_for=perms, **kwargs)
        return wrapper
    return decorator
```

If S2-02's version did more (for example caching perms on `request`), keep that and add only the `allow_assistants` branch.

**4. Open the two grade-entry views to TAs.**

```python
# apps/grading/views.py  (change only the decorators)
@login_required
@require_offering_access(allow_assistants=True)
def sheet(request, offering_id, *, offering, perms_for):
    ...  # body unchanged from S2-06

@login_required
@require_POST
@require_offering_access(edit=True, allow_assistants=True)
def cell(request, offering_id, assessment_id, enrollment_id, *, offering, perms_for):
    ...  # body unchanged from S2-06
```

(The `...` stands for the existing function bodies. Don't retype them, only change the decorator lines.)

`publish`, `unpublish`, `upload*`, `cell_history` and every `outcomes:*` view keep their decorators without the flag, so a TA gets 404 there. Bulk upload stays instructor-only on purpose. One wrong file overwrites 480 drafts, and that's a call for the person responsible for the course.

**5. Defence in depth in the service.** The decorator is the real check (§3.4 rule 1), but `save_grade` is also called by tests and could be called by future code, so it re-checks:

```python
# apps/grading/services.py  (first lines of save_grade)
from django.core.exceptions import PermissionDenied

from apps.accounts.permissions import can_grade_offering


def save_grade(user, assessment, enrollment, raw):
    if not can_grade_offering(user, assessment.offering):
        raise PermissionDenied
    # the rest of save_grade from S2-06 continues unchanged
```

**6. Template changes in the grade sheet.** Where S2-06 rendered an `<input>` when `perms_for.can_edit`, use `perms_for.can_grade`. Where it rendered **Publish** and **Unpublish**, use `perms_for.can_publish`. Add a banner for TAs:

```django
{% if perms_for.is_assistant and not perms_for.can_edit %}
  <div class="alert alert-info py-2">You are a teaching assistant on this course. You can enter draft grades; the instructor publishes them.</div>
{% endif %}
```

**7. Managing assistants.** The instructor (or head) adds a TA by email on `/offerings/<id>/assistants/`. Rules:
- The person must already have an account. We don't create accounts here. Students are created by the enrollment import, staff by the admin.
- A student enrolled in the offering can't be its TA (they would grade themselves).
- One audit event per add or remove.

```python
# apps/catalog/services.py  (add)
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.core import audit

from .models import Enrollment, OfferingAssistant


def add_assistant(user, offering, email: str) -> OfferingAssistant:
    ensure_term_open(offering)
    assistant = User.objects.filter(email__iexact=email.strip()).first()
    if assistant is None:
        raise ValidationError("No POlaris account uses that email. Ask the admin to create one first.")
    if Enrollment.objects.filter(offering=offering, student=assistant,
                                 status=Enrollment.Status.ENROLLED).exists():
        raise ValidationError(f"{assistant.get_full_name()} is enrolled in this course and can't be its assistant.")
    if offering.instructors.filter(pk=assistant.pk).exists():
        raise ValidationError(f"{assistant.get_full_name()} already teaches this course.")
    with transaction.atomic():
        row, created = OfferingAssistant.objects.get_or_create(
            offering=offering, user=assistant, defaults={"added_by": user})
        if created:
            audit.record(user, "offering.assistant_add", row, offering=offering,
                         after={"user": assistant.email})
    return row


def remove_assistant(user, row: OfferingAssistant) -> None:
    with transaction.atomic():
        audit.record(user, "offering.assistant_remove", row, offering=row.offering,
                     before={"user": row.user.email})
        row.delete()
```

`audit.record` reads `entity.pk`, so in `remove_assistant` it's called **before** `delete()`, while the row still has a primary key.

```python
# apps/catalog/selectors.py  (add)
def assisted_offerings(user):
    return (CourseOffering.objects.filter(assistants__user=user)
            .select_related("course", "term").order_by("-term__starts_on", "course__code"))
```

```python
# apps/catalog/views.py  (add)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import require_offering_access

from .models import OfferingAssistant
from .selectors import assisted_offerings
from .services import add_assistant, remove_assistant


@login_required
@require_offering_access(edit=True)
def offering_assistants(request, offering_id, *, offering, perms_for):
    if request.method == "POST":
        try:
            if "remove" in request.POST:
                row = get_object_or_404(OfferingAssistant, pk=request.POST["remove"], offering=offering)
                remove_assistant(request.user, row)
                messages.success(request, f"{row.user.get_full_name()} is no longer an assistant.")
            else:
                row = add_assistant(request.user, offering, request.POST.get("email", ""))
                messages.success(request, f"{row.user.get_full_name()} can now enter draft grades.")
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
        return redirect("catalog:offering_assistants", offering_id=offering.pk)
    rows = offering.assistants.select_related("user").order_by("user__last_name")
    return render(request, "catalog/offering_assistants.html",
                  {"offering": offering, "perms_for": perms_for, "rows": rows})


@login_required
def assisting(request):
    """Every logged-in user may open this; the list is scoped to their own assignments."""
    return render(request, "catalog/assisting.html", {"offerings": assisted_offerings(request.user)})
```

```python
# apps/catalog/urls.py  (add)
    path("offerings/<int:offering_id>/assistants/", views.offering_assistants, name="offering_assistants"),
    path("assisting/", views.assisting, name="assisting"),
```

```django
{# apps/catalog/templates/catalog/offering_assistants.html #}
{% extends "base.html" %}
{% block title %}Assistants · {{ offering.course.code }}{% endblock %}
{% block content %}
<div class="container py-4" style="max-width: 720px">
  <h1 class="h4">Teaching assistants · {{ offering.course.code }} ({{ offering.term.name }})</h1>
  <p class="text-body-secondary">Assistants can enter draft grades on this course's grade sheet. They can't publish, change the setup or weights, or see results.</p>
  <form method="post" class="d-flex gap-2 mb-4">
    {% csrf_token %}
    <label class="visually-hidden" for="ta-email">Assistant's email</label>
    <input id="ta-email" class="form-control" type="email" name="email" placeholder="name@live.acibadem.edu.tr" required>
    <button class="btn btn-primary" type="submit">Add</button>
  </form>
  {% if rows %}
    <ul class="list-group">
      {% for r in rows %}
        <li class="list-group-item d-flex justify-content-between align-items-center">
          {{ r.user.get_full_name }} <span class="text-body-secondary small">{{ r.user.email }}</span>
          <form method="post">{% csrf_token %}<button class="btn btn-sm btn-outline-danger" name="remove" value="{{ r.pk }}">Remove</button></form>
        </li>
      {% endfor %}
    </ul>
  {% else %}
    {% include "includes/empty_state.html" with title="No assistants yet" message="No assistants yet." only %}
  {% endif %}
</div>
{% endblock %}
```

```django
{# apps/catalog/templates/catalog/assisting.html #}
{% extends "base.html" %}
{% block title %}Courses I assist{% endblock %}
{% block content %}
<div class="container py-4">
  <h1 class="h4">Courses I assist</h1>
  {% for o in offerings %}
    <a class="d-block mb-2" href="{% url 'grading:sheet' offering_id=o.pk %}">{{ o.course.code }} · {{ o.course.title }} ({{ o.term.name }})</a>
  {% empty %}
    {% include "includes/empty_state.html" with title="No courses" message="You are not an assistant on any course." only %}
  {% endfor %}
</div>
{% endblock %}
```

**8. Navigation.** In `core.context_processors.navigation`, append a "Courses I assist" item linking to `catalog:assisting` when `request.user.assisting.exists()`. Add a link to `catalog:offering_assistants` on the offering home for users with `perms_for.can_edit`.

### Tests

```python
# apps/accounts/tests/test_assistant_permissions.py
"""Permission matrix rows for the assistant role (§3.4). Kept in its own file so the
main matrix test from S2-02 doesn't need restructuring; the URL list here must stay
in sync with §8.3 for every offering-scoped URL."""
import pytest
from django.urls import reverse

from apps.catalog.models import OfferingAssistant
from apps.core.tests.factories import UserFactory
from apps.core.tests.scenarios import elif_scenario

pytestmark = pytest.mark.django_db


@pytest.fixture
def ta_client(client):
    s = elif_scenario(published=False)
    ta = UserFactory()
    OfferingAssistant.objects.create(offering=s.offering, user=ta, added_by=s.offering.instructors.first())
    client.force_login(ta)
    return client, s


def url(name, s, **extra):
    return reverse(name, kwargs={"offering_id": s.offering.pk, **extra})


@pytest.mark.parametrize("name,extra,method,expected", [
    ("grading:sheet", {}, "get", 200),
    ("catalog:offering", {}, "get", 404),
    ("outcomes:setup", {}, "get", 404),
    ("outcomes:mapping", {}, "get", 404),
    ("reports:results", {}, "get", 404),
    ("reports:history", {}, "get", 404),
    ("grading:upload", {}, "get", 404),
    ("catalog:offering_assistants", {}, "get", 404),
])
def test_assistant_matrix_simple(ta_client, name, extra, method, expected):
    client, s = ta_client
    assert getattr(client, method)(url(name, s, **extra)).status_code == expected


def test_assistant_can_save_draft_but_not_publish(ta_client):
    client, s = ta_client
    cell = reverse("grading:cell", kwargs={"offering_id": s.offering.pk, "assessment_id": s.midterm.pk,
                                           "enrollment_id": s.student.enrollments.get(offering=s.offering).pk})
    assert client.post(cell, {"value": "77"}, HTTP_HX_REQUEST="true").status_code == 200
    publish = reverse("grading:publish", kwargs={"offering_id": s.offering.pk, "assessment_id": s.midterm.pk})
    assert client.post(publish).status_code == 404


def test_assistant_sees_no_other_course(ta_client):
    client, s = ta_client
    from apps.core.tests.factories import OfferingFactory
    other = OfferingFactory()
    assert client.get(reverse("grading:sheet", kwargs={"offering_id": other.pk})).status_code == 404


def test_assistant_blocked_in_closed_term(ta_client):
    client, s = ta_client
    s.offering.term.status = "closed"
    s.offering.term.save()
    cell = reverse("grading:cell", kwargs={"offering_id": s.offering.pk, "assessment_id": s.midterm.pk,
                                           "enrollment_id": s.student.enrollments.get(offering=s.offering).pk})
    assert client.post(cell, {"value": "77"}, HTTP_HX_REQUEST="true").status_code == 404
```

The cell POST field name (`value`) must match what S2-06's `cell` view reads. Use the same name the S2-06 tests use.

```python
# apps/catalog/tests/test_assistants.py
import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.catalog.models import OfferingAssistant
from apps.catalog.services import add_assistant, remove_assistant
from apps.core.models import AuditEvent
from apps.core.tests.factories import UserFactory
from apps.core.tests.scenarios import elif_scenario
from apps.grading.services import save_grade

pytestmark = pytest.mark.django_db


def test_add_and_remove_are_audited():
    s = elif_scenario()
    instructor = s.offering.instructors.first()
    ta = UserFactory(email="ta@example.com")
    row = add_assistant(instructor, s.offering, "TA@example.com ")
    assert row.user == ta
    remove_assistant(instructor, row)
    actions = list(AuditEvent.objects.filter(offering=s.offering).values_list("action", flat=True))
    assert "offering.assistant_add" in actions and "offering.assistant_remove" in actions
    assert not OfferingAssistant.objects.exists()


def test_enrolled_student_cannot_be_assistant_of_own_course():
    s = elif_scenario()
    with pytest.raises(ValidationError):
        add_assistant(s.offering.instructors.first(), s.offering, s.student.email)


def test_unknown_email_is_rejected():
    s = elif_scenario()
    with pytest.raises(ValidationError):
        add_assistant(s.offering.instructors.first(), s.offering, "nobody@example.com")


def test_service_rejects_grade_from_stranger():
    s = elif_scenario()
    enrollment = s.student.enrollments.get(offering=s.offering)
    with pytest.raises(PermissionDenied):
        save_grade(UserFactory(), s.midterm, enrollment, "50")
```

### Check it works

1. As Dr. Can Aydın, open CSE 311 → Assistants and add a seeded student from another cohort who is not enrolled in CSE 311.
2. Log in as that student. The navbar shows "Courses I assist". Open it, enter a draft grade, and see the green tick.
3. Try `/offerings/<id>/mapping/` and `/offerings/<id>/results/` by URL: both are 404. The sheet shows no Publish buttons.
4. As the head, close the term. The TA's sheet becomes read-only.

### Done when

| AC (T2.8) | Proved by |
|---|---|
| 1. Instructor or head assigns TAs per offering; audited | `test_add_and_remove_are_audited` |
| 2. TAs enter drafts on their offerings only | `test_assistant_can_save_draft_but_not_publish`, `test_assistant_sees_no_other_course` |
| 3. TAs can't publish, change setup or weights, upload, or see results | `test_assistant_matrix_simple` |
| 4. Closed term blocks TAs | `test_assistant_blocked_in_closed_term` |
| 5. A student can't TA their own course | `test_enrolled_student_cannot_be_assistant_of_own_course` |

### Commits and PR

```
Add OfferingAssistant and grade-entry permission for TAs (#88)
Let assistants into the grade sheet only, never publish (#88)
Add assistant management page and Courses I assist list (#88)
Extend permission matrix with assistant role (#88)
```

PR title: `S9-05 Teaching assistant role (T2.8)`.

---

## S9-03 · Turkish and English (T2.5)

**Points:** 5 · **Owner:** Person B · **Branch:** `feature/S9-03-i18n` · **Depends on:** every UI story (it touches them all), S9-05 merged first

### Goal

Every page, email and PDF works in Turkish and English. A switcher in the navbar changes the language, which is remembered in a cookie. Program outcomes show their **official Turkish wording** when the language is Turkish. Numbers print the Turkish way in Turkish (`85,0`) and the English way in English (`85.0`). Delivers T2.5 AC 1–6.

**Method, before the code.** Django's i18n works in four steps:

1. **Mark** every user-visible string in code and templates (`gettext` / `{% translate %}`).
2. `makemessages` **extracts** them into `locale/tr/LC_MESSAGES/django.po`, a text file of `msgid "Publish"` → `msgstr ""` pairs.
3. A human **translates** the `msgstr` lines.
4. `compilemessages` **compiles** the `.po` file into a binary `.mo` file that Django reads at runtime.

`LocaleMiddleware` picks the language for each request: the `django_language` cookie set by the switcher, then the browser's `Accept-Language`, then `LANGUAGE_CODE`.

We **commit both `.po` and `.mo`** files. Committing the `.mo` means teammates and the Docker build don't need the `gettext` tools unless they change translations. CI recompiles them and fails if the committed `.mo` is stale, so it can't drift.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `config/settings/base.py` | modify | `LANGUAGES`, `LOCALE_PATHS`, `LocaleMiddleware`, i18n context processor |
| `config/urls.py` | modify | `path("i18n/", include("django.conf.urls.i18n"))` |
| `apps/catalog/models.py` | modify | `ProgramOutcome.short_name_tr`, `description_tr` |
| `apps/catalog/management/commands/load_po_translations.py` | create | Loads `seed/po_tr.json` |
| `seed/po_tr.json` | create | Official Turkish PO texts copied from OBS |
| `apps/core/templatetags/polaris.py` | modify | `score` localises the decimal mark; `po_short`, `po_description` filters |
| every `templates/**/*.html`, `forms.py`, `models.py` choices, `views.py` messages, email templates | modify | Mark strings |
| `templates/includes/language_switcher.html` | create | Switcher form |
| `locale/tr/LC_MESSAGES/django.po`, `django.mo` | create | Translations |
| `.github/workflows/ci.yml` | modify | Stale `.mo` check |
| `apps/core/tests/test_i18n.py` | create | Tests |

### Steps

**1. Install gettext locally** (only the person running `makemessages` needs it): `brew install gettext` on macOS, or `sudo apt install gettext` on Ubuntu.

**2. Settings.**

```python
# config/settings/base.py
from django.utils.translation import gettext_lazy as _

LANGUAGE_CODE = "en"
LANGUAGES = [("en", _("English")), ("tr", _("Türkçe"))]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_I18N = True

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",          # after sessions, before common
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]
```

Keep any middleware other stories added (`ActiveRoleMiddleware` etc.) in its current position relative to these. Add `"django.template.context_processors.i18n"` to the template context processors. It gives templates `LANGUAGE_CODE` and `LANGUAGES` for the switcher.

`LANGUAGE_CODE = "en"`, not `"en-us"`. With `"en-us"` Django looks for an `en_US` catalog first, and the switcher has to list `en-us`. One code per language keeps the cookie values and the `LANGUAGES` list identical.

**3. The switcher.** Django ships a `set_language` view. It takes a POST with `language` and `next`, sets the cookie and redirects. We don't use `i18n_patterns` (language prefixes in URLs like `/tr/me/`). That would change every URL, break the permission matrix and bookmarked links, and it's only needed for public SEO pages, which we don't have.

```python
# config/urls.py  (add to urlpatterns)
    path("i18n/", include("django.conf.urls.i18n")),     # provides the name "set_language"
```

```django
{# templates/includes/language_switcher.html #}
{% load i18n %}
<form action="{% url 'set_language' %}" method="post" class="d-flex align-items-center">
  {% csrf_token %}
  <input name="next" type="hidden" value="{{ request.get_full_path }}">
  <label class="visually-hidden" for="lang">{% translate "Language" %}</label>
  <select id="lang" name="language" class="form-select form-select-sm" onchange="this.form.submit()">
    {% get_available_languages as langs %}
    {% for code, name in langs %}
      <option value="{{ code }}" {% if code == LANGUAGE_CODE %}selected{% endif %}>{{ name }}</option>
    {% endfor %}
  </select>
</form>
```

Include it in the navbar of `base.html`, and on the login page so a logged-out user can switch too. Add `set_language` to the permission matrix as public (POST → 302 for every role).

**4. Mark strings.** This is the bulk of the 5 points. Work app by app, one commit per app, so the PR is reviewable.

| Where | How |
|---|---|
| Templates | `{% load i18n %}` at the top, then `{% translate "Publish" %}`. For sentences with variables: `{% blocktranslate with name=a.name count=n %}Publish {{ name }} to {{ count }} students?{% endblocktranslate %}` |
| Plural sentences | `{% blocktranslate count counter=n %}{{ counter }} student{% plural %}{{ counter }} students{% endblocktranslate %}`. Turkish doesn't change the noun after a number ("3 öğrenci"), but the English side needs it |
| Python (views, services' `ValidationError` messages) | `from django.utils.translation import gettext as _`, then `_("Max for %(name)s is %(max)s") % {"name": …, "max": …}`. Named placeholders let the Turkish sentence reorder them |
| Models, forms, choices (evaluated at import time) | `from django.utils.translation import gettext_lazy as _`. Lazy, because the language is only known per request |
| Emails and PDFs (rendered in Celery, no request) | Wrap rendering in `with translation.override(lang):`. For reminders, use the instructor's last language. We don't store it, so use `settings.LANGUAGE_CODE` and say so. Transcripts use the requesting student's language: `translation.get_language()` in the view, passed to `render_transcript_pdf` |

Two examples, so everyone marks the same way:

```django
{# apps/grading/templates/grading/sheet.html (fragment) #}
{% load i18n polaris %}
<th scope="col">
  {{ a.name }}
  <span class="small text-body-secondary">/ {{ a.max_score|weight }}</span>
  {% if a.unpublished_changes %}
    <span class="badge text-bg-warning">
      {% blocktranslate count counter=a.unpublished_changes %}{{ counter }} unpublished change{% plural %}{{ counter }} unpublished changes{% endblocktranslate %}
    </span>
  {% endif %}
</th>
```

```python
# apps/grading/services.py (fragment of parse_score_input)
from django.utils.translation import gettext as _

        raise ValidationError(_("Max for %(name)s is %(max)s") % {"name": name, "max": max_score})
```

Choices need `gettext_lazy` labels: `MIDTERM = "midterm", _("Midterm")`. Changing choice **labels** makes `makemigrations` produce a migration (Django stores choices in migrations). That's harmless. Generate it and commit it.

**Never translate:** model field *values* the user typed (LO descriptions, assessment names), course codes, the em dash "—", or log messages.

**5. Official Turkish PO texts.** The OBS page we took the English text from (Appendix A) has a Turkish version: the same URL with `lang=tr`. Copy the 11 short names and descriptions **verbatim** into `seed/po_tr.json`. They are official wording, so don't let anyone, human or AI, paraphrase them. Have a second person compare them against the page in the PR review.

```json
[
  {"number": 1, "short_name_tr": "<from OBS, PO 1 Turkish title>", "description_tr": "<from OBS, PO 1 Turkish text>"}
]
```

That's the file's shape. It has 11 objects, numbers 1–11, filled from the OBS page during this story. The angle-bracket text above marks *where* each copied string goes. It is not content to commit.

Add the fields with `blank=True` (other programs' PO sets may have no Turkish yet):

```python
# apps/catalog/models.py  (ProgramOutcome, add)
    short_name_tr = models.CharField(max_length=80, blank=True)
    description_tr = models.TextField(blank=True)
```

```python
# apps/catalog/management/commands/load_po_translations.py
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Program, ProgramOutcome


class Command(BaseCommand):
    help = "Load official Turkish PO wording from seed/po_tr.json into the program's active PO set."

    def add_arguments(self, parser):
        parser.add_argument("--program", default="CSE")
        parser.add_argument("--file", default=str(Path(settings.BASE_DIR) / "seed" / "po_tr.json"))

    def handle(self, *args, program, file, **opts):
        rows = json.loads(Path(file).read_text(encoding="utf-8"))
        prog = Program.objects.get(code=program)
        po_set = prog.po_sets.get(is_active=True)
        with transaction.atomic():
            for row in rows:
                updated = ProgramOutcome.objects.filter(po_set=po_set, number=row["number"]).update(
                    short_name_tr=row["short_name_tr"], description_tr=row["description_tr"])
                if not updated:
                    raise CommandError(f"PO {row['number']} not found in {po_set.label}")
        self.stdout.write(self.style.SUCCESS(f"Loaded Turkish text for {len(rows)} POs of {program}."))
```

Call it at the end of `seed_demo` so demo data is always bilingual. Add both fields to `POForm` so the head can edit them on `/department/outcomes/`.

**6. Template filters for PO text and numbers.**

```python
# apps/core/templatetags/polaris.py  (replace `score`; add the two PO filters)
from django import template
from django.utils.translation import get_language

from apps.scoring.engine import display

register = template.Library()


def _turkish() -> bool:
    return (get_language() or "en").startswith("tr")


@register.filter
def score(value):
    """1 decimal, half-up, '—' for None (P7, P12). Decimal comma in Turkish."""
    text = display(value)
    return text.replace(".", ",") if _turkish() else text


@register.filter
def po_short(po):
    return po.short_name_tr if _turkish() and po.short_name_tr else po.short_name


@register.filter
def po_description(po):
    return po.description_tr if _turkish() and po.description_tr else po.description
```

Keep the existing `pct`, `weight` and `query_transform` definitions in the file. Apply the same comma rule in `pct` and `weight` if they print decimals. Then replace `{{ po.short_name }}` with `{{ po|po_short }}`, and `{{ po.description }}` with `{{ po|po_description }}`, everywhere: `grep -rn "po.short_name\|po.description\|\.short_name }}" apps templates`.

Charts: Chart.js labels come from the view's JSON. Build them with the same helpers in Python (`po_short(po)`), and set Chart.js's `locale` option to `document.documentElement.lang` so tooltips use the right decimal mark. Set `<html lang="{{ LANGUAGE_CODE }}">` in `base.html`.

Excel exports keep numeric cells as **numbers** (T1.7 AC2), so Excel formats them for the reader's own locale. Don't format them as text.

**7. Extract, translate, compile.**

```bash
uv run python manage.py makemessages -l tr --ignore ".venv/*" --ignore "staticfiles/*"
# translate locale/tr/LC_MESSAGES/django.po (Poedit is a free GUI; any editor works)
uv run python manage.py compilemessages -l tr
```

A few entries, to set the terminology everyone uses (put this table in the PR description so translations stay consistent):

| English | Turkish |
|---|---|
| Program Outcome (PO) | Program Çıktısı (PÇ) |
| Learning Outcome (LO) | Öğrenme Çıktısı (ÖÇ) |
| Assessment | Değerlendirme |
| Publish | Yayınla |
| Draft | Taslak |
| Coverage | Kapsam |
| Attainment | Başarı / Ulaşma |
| Weight | Ağırlık |
| Grade sheet | Not çizelgesi |
| Syllabus | Ders izlencesi |

The UI labels `PO 1` / `LO 2` become `PÇ 1` / `ÖÇ 2` in Turkish. Mark them as `{% blocktranslate %}PO {{ n }}{% endblocktranslate %}` so they translate as a pattern.

Example `.po` entries:

```po
msgid "Publish"
msgstr "Yayınla"

#, python-format
msgid "Max for %(name)s is %(max)s"
msgstr "%(name)s için en yüksek not %(max)s"

msgid "%(counter)s unpublished change"
msgid_plural "%(counter)s unpublished changes"
msgstr[0] "%(counter)s yayınlanmamış değişiklik"
msgstr[1] "%(counter)s yayınlanmamış değişiklik"
```

**8. CI guard against a stale `.mo`.** Add to the `lint` job in `ci.yml`, after checkout and uv setup:

```yaml
      - name: Translations compiled
        run: |
          sudo apt-get update && sudo apt-get install -y gettext
          uv run python manage.py compilemessages -l tr
          git diff --exit-code -- locale/ || (echo "::error::Run compilemessages and commit the .mo file" && exit 1)
```

`.mo` files are deterministic for the same `.po` input, so an unchanged `.po` produces a byte-identical `.mo`, and `git diff` stays empty.

**9. Turkish text gotchas.**
- `"İ".lower()` in Python is `"i̇"` (i plus a combining dot), not `"i"`. Never lowercase for matching. The bulk-upload header matcher (T1.1) already uses `casefold()` on both sides, so keep it that way.
- Sorting Turkish names with `order_by("last_name")` uses PostgreSQL's collation. The Docker image's default `en_US.utf8` puts "Ç" after "Z". It's acceptable for us. If the head complains, sort in Python with a `tr` collator later. Note it as a known limitation.
- WeasyPrint needs a font with Turkish glyphs (`fonts-dejavu-core`, added in S8-04).

### Tests

```python
# apps/core/tests/test_i18n.py
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import translation

from apps.core.templatetags.polaris import po_short, score
from apps.core.tests.scenarios import elif_scenario

pytestmark = pytest.mark.django_db


def test_score_uses_decimal_comma_in_turkish():
    with translation.override("tr"):
        assert score(Decimal("84.95")) == "85,0"
    with translation.override("en"):
        assert score(Decimal("84.95")) == "85.0"
    with translation.override("tr"):
        assert score(None) == "—"


def test_po_falls_back_to_english_when_no_turkish():
    s = elif_scenario()
    s.po1.short_name, s.po1.short_name_tr = "Teamwork", ""
    with translation.override("tr"):
        assert po_short(s.po1) == "Teamwork"
    s.po1.short_name_tr = "Takım çalışması"
    with translation.override("tr"):
        assert po_short(s.po1) == "Takım çalışması"


def test_language_switch_sets_cookie_and_translates_page(client):
    s = elif_scenario()
    client.force_login(s.student)
    resp = client.post(reverse("set_language"), {"language": "tr", "next": "/me/"})
    assert resp.status_code == 302
    assert resp.cookies["django_language"].value == "tr"
    page = client.get(reverse("student:profile")).content.decode()
    assert 'lang="tr"' in page
    assert "85,0" in page


def test_every_po_string_has_a_turkish_translation():
    """Fails if someone marks a new string and forgets to translate it."""
    import polib  # dev dependency: uv add --dev polib
    from django.conf import settings
    po = polib.pofile(str(settings.BASE_DIR / "locale" / "tr" / "LC_MESSAGES" / "django.po"))
    missing = [e.msgid for e in po.untranslated_entries() if not e.obsolete]
    fuzzy = [e.msgid for e in po.fuzzy_entries()]
    assert not missing, f"Untranslated: {missing[:10]}"
    assert not fuzzy, f"Fuzzy (check and clear the flag): {fuzzy[:10]}"
```

`polib` is a small pure-Python `.po` reader: `uv add --dev polib`. The last test makes "every string translated" a CI rule rather than a hope.

### Check it works

1. `uv run python manage.py seed_demo --reset`, then log in as Elif. Pick **Türkçe** in the navbar.
2. Every label is Turkish. PO names are the official Turkish ones, and PO 1 reads `85,0`.
3. Hover a PO column in the instructor mapping grid: the tooltip shows the Turkish description.
4. Download the transcript in Turkish. The headings and decimal commas are Turkish, and ş/ğ/İ render.
5. Switch back to English. Everything flips back, including the decimal point.

### Done when

| AC (T2.5) | Proved by |
|---|---|
| 1. Every UI string translatable and translated | `test_every_po_string_has_a_turkish_translation` |
| 2. Switcher on every page incl. login; choice remembered | `test_language_switch_sets_cookie_and_translates_page` |
| 3. Official Turkish PO wording, English fallback | `test_po_falls_back_to_english_when_no_turkish`, `seed/po_tr.json` reviewed against OBS |
| 4. Numbers formatted per language; exports stay numeric | `test_score_uses_decimal_comma_in_turkish`, Excel check |
| 5. Emails and PDFs in the right language | manual check 4 |
| 6. Translations can't go stale | CI `compilemessages` + `git diff` step |

### Commits and PR

```
Enable LocaleMiddleware and a language switcher
Mark grading and outcomes templates for translation
Mark reports, catalog and account strings for translation
Add official Turkish PO wording and bilingual PO filters
Add Turkish translations and a CI check for stale catalogs
```

PR title: `S9-03 Turkish / English (T2.5)`. It touches many files, so ask reviewers to review **one commit at a time** (GitHub's commit-by-commit view).

---

## S9-07 · Second program, side by side (T2.6)

**Points:** 3 · **Owner:** Person C · **Branch:** `feature/S9-07-multi-program` · **Depends on:** S2-02, S3-04, S6-05, S9-03

### Goal

Prove that POlaris isn't hard-wired to CSE. A second program (Biomedical Engineering, BME, with its own POs) runs in the same database. Its head sees only BME, CSE's head sees only CSE, and a person with roles in both switches programs from the navbar. Delivers T2.6 AC 1–4. The data model has supported this since Sprint 1 (`ProgramMembership.program`, `Course.program`, `ProgramOutcomeSet.program`). This story fixes the **UI assumption** that there's only one program, and **proves isolation with tests**.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/core/programs.py` | create | `programs_for(user, role=None)`, `active_program(request)`, `SESSION_KEY` |
| `apps/core/middleware.py` | modify | `ActiveRoleMiddleware` also sets `request.active_program` |
| `apps/core/views.py`, `config/urls.py` | modify | `switch_program` (POST) |
| `apps/core/context_processors.py` | modify | `available_programs`, `active_program` |
| `templates/base.html` | modify | Program switcher when there's more than one |
| `apps/reports/views.py`, `apps/catalog/views.py` | modify | Every head view uses `request.active_program` |
| `apps/catalog/selectors.py` | modify | Scope catalog lists by program |
| `apps/core/management/commands/seed_demo.py` | modify | `--with-bme` |
| `apps/core/tests/test_multi_program.py` | create | Isolation tests |

### Steps

**1. One helper decides "which program am I looking at".** Every head-facing view must use it. A view that picks "the first program" or `Program.objects.get(code="CSE")` is exactly the bug this story exists to remove. Find those first:

```bash
grep -rn 'Program.objects.first()\|code="CSE"\|programs.first()\|memberships.first()' apps
```

```python
# apps/core/programs.py
"""Which program the current request is about (T2.6)."""
from __future__ import annotations

from apps.accounts.models import ProgramMembership
from apps.catalog.models import Program

SESSION_KEY = "active_program_id"


def programs_for(user, role: str | None = None):
    if user.is_superuser:
        return Program.objects.order_by("code")
    qs = ProgramMembership.objects.filter(user=user)
    if role:
        qs = qs.filter(role=role)
    return Program.objects.filter(pk__in=qs.values("program_id")).order_by("code")


def active_program(request) -> Program | None:
    """The program chosen in the session, if the user still belongs to it; else their first one."""
    if not request.user.is_authenticated:
        return None
    allowed = programs_for(request.user)
    chosen = request.session.get(SESSION_KEY)
    if chosen and allowed.filter(pk=chosen).exists():
        return allowed.get(pk=chosen)
    return allowed.first()
```

```python
# apps/core/middleware.py  (inside ActiveRoleMiddleware.__call__, before calling get_response)
from django.utils.functional import SimpleLazyObject

from .programs import active_program

        request.active_program = SimpleLazyObject(lambda: active_program(request))
```

`SimpleLazyObject` means the query only runs if a view actually uses `request.active_program`. Static files and `/healthz` pay nothing.

**2. Switching.** POST, re-validated against `programs_for`, so a crafted POST can't select a program you don't belong to.

```python
# apps/core/views.py  (add)
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .programs import SESSION_KEY, programs_for


@login_required
@require_POST
def switch_program(request):
    program = programs_for(request.user).filter(pk=request.POST.get("program") or 0).first()
    if program is None:
        raise Http404
    request.session[SESSION_KEY] = program.pk
    nxt = request.POST.get("next") or "/"
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = "/"
    return redirect(nxt)
```

```python
# config/urls.py  (add)
    path("program/", core_views.switch_program, name="switch_program"),
```

The `url_has_allowed_host_and_scheme` check stops an **open redirect**: without it, a link could send someone to `https://polaris…/program/?next=https://evil.example`, and after the POST they'd land on a lookalike site.

**3. Use it in head views.** For every view under `/department/`, the program is `request.active_program`, and the permission check is `is_head(request.user, program)`. Example, the dashboard:

```python
# apps/reports/views.py  (department view, first lines)
@login_required
@require_role("head")
def department(request):
    program = request.active_program
    if program is None or not is_head(request.user, program):
        raise Http404
    # the rest of the view from S3-04 / S6-05 / S7-02 continues, using `program`
```

Apply the same two lines to `department_student`, `department_history`, `department_export`, every `catalog:*` department view (`po_sets`, `terms`, `courses`, `offerings`, `enrollments`, `enrollment_import*`), and `term_deadline`. Pass `program` into every selector that lists data: `Course.objects.filter(program=program)`, offerings via `course__program=program`, and memberships via `program=program`.

`department_student` gets one more check: the student must have a student membership in `program`. Otherwise it's a 404, even if the user exists. This is the rule that keeps CSE's head from opening a BME student's profile by guessing the user id.

```python
    student = get_object_or_404(User, pk=user_id, memberships__program=program,
                                memberships__role=ProgramMembership.Role.STUDENT)
```

`require_role("head")` checks "head of *some* program". The `is_head(user, program)` check makes it "head of *this* program". Both are needed.

**4. The switcher in the navbar.** It's shown only when the user has more than one program, so CSE-only users never see it.

```python
# apps/core/context_processors.py  (inside navigation(), add to the returned dict)
        "available_programs": programs_for(request.user) if request.user.is_authenticated else [],
        "active_program": getattr(request, "active_program", None),
```

```django
{# templates/base.html, inside the navbar, next to the role switcher #}
{% if available_programs|length > 1 %}
  <form action="{% url 'switch_program' %}" method="post" class="d-flex">
    {% csrf_token %}
    <input type="hidden" name="next" value="{{ request.get_full_path }}">
    <label class="visually-hidden" for="program-switch">{% translate "Program" %}</label>
    <select id="program-switch" name="program" class="form-select form-select-sm" onchange="this.form.submit()">
      {% for p in available_programs %}
        <option value="{{ p.pk }}" {% if p.pk == active_program.pk %}selected{% endif %}>{{ p.code }}</option>
      {% endfor %}
    </select>
  </form>
{% endif %}
```

**5. Seed a second program.** `seed_demo --with-bme` adds BME: a program, a 6-PO set clearly labelled **"Demo POs (fictional)"** (not real BME outcomes, so nobody mistakes them for official text), 2 courses in 2026F, 1 instructor, a head (Dr. Selin Arslan), 20 students, and setup and grades generated by the same helpers the CSE seed uses. Also make **Prof. Deniz Kara head of both programs**, so the demo can show the switcher.

```python
# apps/core/management/commands/seed_demo.py  (add)
BME_POS = [
    (1, "Biology fundamentals", "Apply knowledge of biology and physiology to engineering problems."),
    (2, "Medical devices", "Design and evaluate devices that interact with the human body."),
    (3, "Signals", "Acquire and process biomedical signals and images."),
    (4, "Safety and ethics", "Apply patient safety, regulatory and ethical principles."),
    (5, "Experimentation", "Plan experiments and analyse biological and clinical data."),
    (6, "Communication", "Communicate with clinicians and engineers in writing and speech."),
]


def seed_bme(self, *, rng, term, head_of_cse):
    bme = Program.objects.create(code="BME", name="Biomedical Engineering (demo)")
    po_set = ProgramOutcomeSet.objects.create(program=bme, label="Demo POs (fictional)",
                                              effective_from_year=2023, is_active=True)
    for number, short, desc in BME_POS:
        ProgramOutcome.objects.create(po_set=po_set, number=number, short_name=short, description=desc)
    head = self.make_user("selin.arslan@demo.polaris", "Selin", "Arslan")
    ProgramMembership.objects.create(user=head, program=bme, role=ProgramMembership.Role.HEAD)
    ProgramMembership.objects.create(user=head_of_cse, program=bme, role=ProgramMembership.Role.HEAD)
    instructor = self.make_user("burak.celik@demo.polaris", "Burak", "Çelik")
    ProgramMembership.objects.create(user=instructor, program=bme, role=ProgramMembership.Role.INSTRUCTOR)
    students = [self.make_student(bme, cohort_year=2024, index=i, prefix="BME") for i in range(20)]
    for code, title in [("BME 201", "Biomedical Signals"), ("BME 301", "Medical Device Design")]:
        course = Course.objects.create(program=bme, code=code, title=title, credits=3, ects=6)
        offering = CourseOffering.objects.create(course=course, term=term)
        offering.instructors.add(instructor)
        self.build_setup_and_grades(offering, students, po_set=po_set, rng=rng)
    return bme
```

`make_user`, `make_student` and `build_setup_and_grades` are the helper methods S1-10/S3-07 wrote for the CSE seed. If they're named differently in your `seed_demo`, use those names. The point is that BME reuses them, so BME data has the same realism and the same fixed random seed. Call `seed_bme` at the end of `handle()` when `--with-bme` is passed. Make `--with-bme` the default for staging and production reseeds in the S10-02 runbook.

### Tests

```python
# apps/core/tests/test_multi_program.py
import pytest
from django.urls import reverse

from apps.accounts.models import ProgramMembership
from apps.core.programs import SESSION_KEY
from apps.core.tests.factories import (
    CourseFactory, EnrollmentFactory, MembershipFactory, OfferingFactory, ProgramFactory, UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_programs():
    cse, bme = ProgramFactory(code="CSE"), ProgramFactory(code="BME")
    cse_head, bme_head, both = UserFactory(), UserFactory(), UserFactory()
    MembershipFactory(user=cse_head, program=cse, role="head")
    MembershipFactory(user=bme_head, program=bme, role="head")
    MembershipFactory(user=both, program=cse, role="head")
    MembershipFactory(user=both, program=bme, role="head")
    bme_student = UserFactory()
    MembershipFactory(user=bme_student, program=bme, role="student", cohort_year=2024)
    bme_offering = OfferingFactory(course=CourseFactory(program=bme, code="BME 201"))
    EnrollmentFactory(offering=bme_offering, student=bme_student)
    return cse, bme, cse_head, bme_head, both, bme_student, bme_offering


def test_cse_head_cannot_open_bme_student(client, two_programs):
    cse, bme, cse_head, *_rest, bme_student, _off = two_programs
    client.force_login(cse_head)
    url = reverse("reports:department_student", kwargs={"user_id": bme_student.pk})
    assert client.get(url).status_code == 404


def test_cse_head_cannot_open_bme_offering(client, two_programs):
    cse, bme, cse_head, bme_head, both, bme_student, bme_offering = two_programs
    client.force_login(cse_head)
    for name in ("catalog:offering", "outcomes:mapping", "grading:sheet", "reports:results"):
        assert client.get(reverse(name, kwargs={"offering_id": bme_offering.pk})).status_code == 404


def test_bme_course_not_listed_for_cse_head(client, two_programs):
    cse, bme, cse_head, *_ = two_programs
    client.force_login(cse_head)
    assert "BME 201" not in client.get(reverse("catalog:courses")).content.decode()


def test_switcher_changes_dashboard_program(client, two_programs):
    cse, bme, _c, _b, both, *_ = two_programs
    client.force_login(both)
    client.post(reverse("switch_program"), {"program": bme.pk, "next": "/department/"})
    assert client.session[SESSION_KEY] == bme.pk
    assert "BME 201" in client.get(reverse("catalog:courses")).content.decode()


def test_cannot_switch_to_foreign_program(client, two_programs):
    cse, bme, cse_head, *_ = two_programs
    client.force_login(cse_head)
    assert client.post(reverse("switch_program"), {"program": bme.pk}).status_code == 404


def test_switch_rejects_open_redirect(client, two_programs):
    cse, _bme, cse_head, *_ = two_programs
    client.force_login(cse_head)
    resp = client.post(reverse("switch_program"), {"program": cse.pk, "next": "https://evil.example/"})
    assert resp.url == "/"
```

### Check it works

1. `seed_demo --reset --with-bme`. Log in as Prof. Deniz Kara: the navbar has a CSE/BME switcher.
2. Choose BME. The dashboard shows 6 fictional POs and 2 courses. Choose CSE, and it's back to 11 POs.
3. Log in as Dr. Selin Arslan. There's no switcher (she has one program). Paste a CSE student's `/department/students/<id>/` URL and get a 404.

### Done when

| AC (T2.6) | Proved by |
|---|---|
| 1. A second program with its own POs runs side by side | `seed_demo --with-bme`, manual check 2 |
| 2. A head of one program can't see another's students, courses or offerings | first three tests |
| 3. Multi-program users switch from the navbar; choice validated | `test_switcher_changes_dashboard_program`, `test_cannot_switch_to_foreign_program` |
| 4. No open redirect through the switcher | `test_switch_rejects_open_redirect` |

### Commits and PR

```
Resolve the active program per request instead of assuming CSE
Scope every department view to the active program
Add program switcher for users in several programs
Seed a fictional BME program to prove program isolation
```

PR title: `S9-07 Second program side by side (T2.6)`.

---

## S9-06 · Import a course from its OBS page (T2.9)

**Points:** 3 · **Owner:** Person A · **Branch:** `feature/S9-06-obs-import` · **Depends on:** S5-03, S5-04, S6-01, S6-02

### Goal

Every Acıbadem course has a public Bologna page on OBS with its learning outcomes, assessment breakdown and course-to-PO contribution table. Instead of uploading a file, the instructor pastes that page's URL. The worker downloads the page, turns the HTML into clean text, and sends it through **the same extraction and review pipeline** as a syllabus upload. The review screen, validation and Apply are unchanged. Delivers T2.9 AC 1–5.

**Day 1, first hour: the reachability spike.** OBS is an external site we don't control. Before writing any code, from the **production server** (not your laptop, since the university may block data-centre IPs):

```bash
ssh deploy@<server>
curl -sS -o /tmp/obs.html -w "%{http_code} %{size_download} bytes\n" \
  "https://obs.acibadem.edu.tr/oibs/bologna/progLearnOutcomes.aspx?lang=en&curSunit=6246"
grep -c "Learning Outcomes\|Öğrenme Çıktıları" /tmp/obs.html
```

Then do the same for one real **course** page (open a course from the program page in your browser and copy its URL). Record the HTTP status, the size, and whether the LO text appears in the raw HTML, in the PR description.

- **200 and the text is in the HTML:** build the story as below.
- **Blocked, or the content is loaded by JavaScript** (the text isn't in the raw HTML): **drop the story.** Record it in `velocity.md` with the evidence, and move on. Don't build a headless browser in the last sprint before the freeze. A spike that kills a story early is exactly what spikes are for, and it's a good paragraph for the CSE 311 report.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/ingestion/models.py` | modify | `IngestionJob.source_url` |
| `apps/ingestion/obs.py` | create | `validate_obs_url`, `fetch_obs_page`, `html_to_text` |
| `apps/ingestion/services.py` | modify | `create_obs_job(user, offering, url)` |
| `apps/ingestion/tasks.py` | modify | `run_obs_import(job_id)` |
| `apps/ingestion/forms.py` | modify | `ObsImportForm` |
| `apps/ingestion/views.py`, `urls.py` | modify | `start_obs` → `ingestion:start_obs` |
| `apps/ingestion/templates/ingestion/start.html` | modify | Second tab "From OBS page" |
| `apps/ingestion/tests/test_obs.py` | create | Tests with a recorded HTML fixture |
| `apps/ingestion/tests/fixtures/obs_cse311.html` | create | One real OBS page, saved during the spike |

### Steps

**1. Store where the job came from.**

```python
# apps/ingestion/models.py  (IngestionJob, add)
    source_url = models.URLField(max_length=500, blank=True)
```

**2. Fetch safely.** Making our server download a URL a user typed is a classic **SSRF** risk (server-side request forgery): someone could paste `http://localhost:6379/` or `http://169.254.169.254/` (cloud metadata) and make our server talk to internal services. Three rules make it safe:

- **HTTPS only, and only the exact host `obs.acibadem.edu.tr`.** Not a suffix match: `obs.acibadem.edu.tr.evil.com` must fail.
- **No redirects followed automatically.** A redirect could point anywhere. If OBS answers with a redirect, we refuse.
- **Size and time limits:** 2 MB and 20 seconds.

`httpx` is already installed (the Anthropic SDK depends on it), so this adds no dependency.

```python
# apps/ingestion/obs.py
"""Fetch a public OBS Bologna course page and turn it into plain text (T2.9)."""
from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx
from django.core.exceptions import ValidationError

OBS_HOST = "obs.acibadem.edu.tr"
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = httpx.Timeout(20.0)


def validate_obs_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or parts.hostname != OBS_HOST or parts.port not in (None, 443):
        raise ValidationError(f"Paste a link that starts with https://{OBS_HOST}/")
    if parts.username or parts.password:
        raise ValidationError("That link contains a username or password. Copy the address from the browser bar.")
    return parts.geturl()


def fetch_obs_page(url: str) -> str:
    url = validate_obs_url(url)
    with httpx.Client(timeout=TIMEOUT, follow_redirects=False,
                      headers={"User-Agent": "POlaris course import (student project)"}) as client:
        with client.stream("GET", url) as resp:
            if resp.is_redirect:
                raise ValidationError("OBS redirected the request. Open the page in a browser and copy the final address.")
            resp.raise_for_status()
            chunks, size = [], 0
            for chunk in resp.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValidationError("That page is unexpectedly large. Upload the syllabus file instead.")
                chunks.append(chunk)
            encoding = resp.encoding or "utf-8"
    return b"".join(chunks).decode(encoding, errors="replace")


class _TextExtractor(HTMLParser):
    """Keeps visible text; turns table cells into ' | ' and rows/blocks into newlines,
    so the LO table and the PO contribution table survive as readable rows."""
    SKIP = {"script", "style", "noscript", "head"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "section"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth and data.strip():
            self.parts.append(" ".join(data.split()))


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    lines = [" ".join(line.split()).strip(" |") for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)
```

Why not BeautifulSoup: one more dependency for a job the standard library's `HTMLParser` does in 30 lines. We don't need CSS selectors because Claude reads the text. We only need tables to stay readable.

**3. The service and the task.** The OBS task's only job is to produce the same input a DOCX upload would: a `.txt` file of the syllabus text. It saves that on `job.file`, then hands over to the existing `run_syllabus_extraction`. One pipeline, one set of validation rules, one review screen.

```python
# apps/ingestion/services.py  (add)
from django.db import transaction

from apps.catalog.services import ensure_term_open

from .models import IngestionJob
from .obs import validate_obs_url


def create_obs_job(user, offering, url: str) -> IngestionJob:
    ensure_term_open(offering)
    clean = validate_obs_url(url)
    with transaction.atomic():
        job = IngestionJob.objects.create(
            offering=offering, kind=IngestionJob.Kind.SYLLABUS, source_url=clean,
            original_filename="obs-page.txt", created_by=user,
        )
        from .tasks import run_obs_import
        transaction.on_commit(lambda: run_obs_import.delay(job.pk))
    return job
```

`IngestionJob.file` is a required `FileField`, but a model can be saved with it empty. Django stores `""`. The task fills it before extraction starts. The progress page only reads `status`, so an empty file in the first second doesn't matter.

```python
# apps/ingestion/tasks.py  (add)
import httpx
from celery import shared_task
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from .models import IngestionJob
from .obs import fetch_obs_page, html_to_text


@shared_task(bind=True, autoretry_for=(httpx.TransportError,), retry_backoff=15, max_retries=3)
def run_obs_import(self, job_id: int):
    job = IngestionJob.objects.get(pk=job_id)
    if job.status != IngestionJob.Status.PENDING:
        return
    try:
        text = html_to_text(fetch_obs_page(job.source_url))
    except ValidationError as e:
        job.status, job.error = IngestionJob.Status.FAILED, " ".join(e.messages)
        job.save(update_fields=["status", "error", "updated_at"])
        return
    except httpx.HTTPStatusError as e:
        job.status = IngestionJob.Status.FAILED
        job.error = f"OBS answered with error {e.response.status_code}. Check the link or upload the syllabus file."
        job.save(update_fields=["status", "error", "updated_at"])
        return
    if len(text) < 300:
        job.status = IngestionJob.Status.FAILED
        job.error = "That OBS page has almost no text. Is it the course's detail page?"
        job.save(update_fields=["status", "error", "updated_at"])
        return
    job.file.save(f"obs-{job.pk}.txt", ContentFile(text.encode("utf-8")), save=False)
    job.save(update_fields=["file", "updated_at"])
    run_syllabus_extraction.run(job.pk)    # same pipeline as an upload, in this worker process
```

`run_syllabus_extraction.run(job.pk)` calls the task's function directly instead of queueing a second task. It's already inside a worker, so queueing would add delay for nothing. `.run()` on a bound task supplies `self` automatically. `run_syllabus_extraction` is defined above this function in the same `tasks.py` (S5-03).

**Teach the extraction about plain text.** S5-03's task decides the media type from the stored file and converts DOCX to text before calling `extract_syllabus`. The text branch of `_content_blocks` (§7.5) already handles `text/plain`. Where S5-03 chooses the media type, add this as the first check:

```python
    if job.file.name.endswith(".txt"):
        media_type = "text/plain"            # OBS import (S9-06): already plain text
```

**4. Form, view, URL.**

```python
# apps/ingestion/forms.py  (add)
from django import forms
from django.utils.translation import gettext_lazy as _

from .obs import OBS_HOST, validate_obs_url


class ObsImportForm(forms.Form):
    url = forms.URLField(label=_("OBS course page address"), max_length=500,
                         widget=forms.URLInput(attrs={"placeholder": f"https://{OBS_HOST}/oibs/bologna/…"}))

    def clean_url(self):
        return validate_obs_url(self.cleaned_data["url"])
```

```python
# apps/ingestion/views.py  (add)
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import require_offering_access

from .forms import ObsImportForm, SyllabusUploadForm
from .services import create_obs_job


@login_required
@require_POST
@require_offering_access(edit=True)
def start_obs(request, offering_id, *, offering, perms_for):
    form = ObsImportForm(request.POST)
    if not form.is_valid():
        return render(request, "ingestion/start.html", {
            "offering": offering, "perms_for": perms_for,
            "form": SyllabusUploadForm(), "obs_form": form, "active_tab": "obs",
        }, status=400)
    job = create_obs_job(request.user, offering, form.cleaned_data["url"])
    return redirect("ingestion:job", job_id=job.pk)
```

```python
# apps/ingestion/urls.py  (add)
    path("offerings/<int:offering_id>/syllabus/obs/", views.start_obs, name="start_obs"),
```

In `start.html`, add a second Bootstrap tab next to "Upload a file": "From the OBS page", containing `obs_form` posted to `ingestion:start_obs`. Add `"obs_form": ObsImportForm()` to the existing `start` view's context.

**5. Save a fixture during the spike.** Store the course page you fetched as `apps/ingestion/tests/fixtures/obs_cse311.html`. It's public course information, so committing it is fine. Tests must never hit the network.

### Tests

```python
# apps/ingestion/tests/test_obs.py
from pathlib import Path

import httpx
import pytest
from django.core.exceptions import ValidationError

from apps.core.tests.scenarios import elif_scenario
from apps.ingestion.models import IngestionJob
from apps.ingestion.obs import fetch_obs_page, html_to_text, validate_obs_url
from apps.ingestion.services import create_obs_job

FIXTURE = Path(__file__).parent / "fixtures" / "obs_cse311.html"


@pytest.mark.parametrize("url", [
    "http://obs.acibadem.edu.tr/oibs/x",                 # not https
    "https://obs.acibadem.edu.tr.evil.com/oibs/x",       # suffix trick
    "https://evil.com/?obs.acibadem.edu.tr",             # host only in query
    "https://user:pw@obs.acibadem.edu.tr/oibs/x",        # credentials
    "https://obs.acibadem.edu.tr:8443/oibs/x",           # other port
    "https://localhost/",
])
def test_rejects_unsafe_urls(url):
    with pytest.raises(ValidationError):
        validate_obs_url(url)


def test_accepts_obs_course_url():
    url = "https://obs.acibadem.edu.tr/oibs/bologna/progCourseDetails.aspx?lang=en"
    assert validate_obs_url(url) == url


def test_html_to_text_keeps_table_rows():
    html = "<table><tr><th>LO</th><th>Text</th></tr><tr><td>1</td><td>Design &amp; test</td></tr></table><script>x()</script>"
    assert html_to_text(html) == "LO | Text\n1 | Design & test"


def test_fixture_contains_learning_outcomes():
    text = html_to_text(FIXTURE.read_text(encoding="utf-8"))
    assert "Learning Outcome" in text or "Öğrenme Çıktı" in text
    assert len(text) > 300


def test_fetch_refuses_redirect(monkeypatch):
    def handler(request):
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/"})
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=transport, **kw))
    with pytest.raises(ValidationError):
        fetch_obs_page("https://obs.acibadem.edu.tr/oibs/x")


def test_fetch_refuses_oversized_page(monkeypatch):
    big = b"a" * (2 * 1024 * 1024 + 1)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=big))
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=transport, **kw))
    with pytest.raises(ValidationError):
        fetch_obs_page("https://obs.acibadem.edu.tr/oibs/x")


@pytest.mark.django_db
def test_failed_fetch_marks_job_failed(monkeypatch, django_capture_on_commit_callbacks):
    s = elif_scenario()
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=transport, **kw))
    with django_capture_on_commit_callbacks(execute=True):
        job = create_obs_job(s.offering.instructors.first(), s.offering,
                             "https://obs.acibadem.edu.tr/oibs/bologna/x.aspx")
    job.refresh_from_db()
    assert job.status == IngestionJob.Status.FAILED
    assert "404" in job.error
```

The success path (fixture → extraction → READY) is covered by S5-04's recorded-extraction tests. Mock `extract_syllabus` exactly the way those tests do, and add one test here that runs `run_obs_import` with the fixture served by `MockTransport` and asserts the job reaches `READY`. Copy the mock setup from S5-04's test module, so both use one way of faking Claude.

### Check it works

1. As Dr. Can Aydın, open a new empty offering → **Upload syllabus instead** → tab **From the OBS page**. Paste the CSE 311 OBS URL.
2. The progress page appears. Within a minute, the review screen shows the LOs, assessments and PO contributions read from OBS.
3. Paste `https://example.com`. The form refuses it with "Paste a link that starts with https://obs.acibadem.edu.tr/".
4. The job in Django admin shows `source_url` and a stored `obs-<id>.txt` file you can open and read.

### Done when

| AC (T2.9) | Proved by |
|---|---|
| 1. Instructor pastes an OBS URL; same review/apply flow as uploads | manual checks 1–2, success-path test |
| 2. Only https OBS URLs accepted; no redirects; size/time capped | `test_rejects_unsafe_urls`, `test_fetch_refuses_redirect`, `test_fetch_refuses_oversized_page` |
| 3. Unreachable or empty page fails with a human message | `test_failed_fetch_marks_job_failed`, short-text branch |
| 4. Job records its source URL and the text that was sent | `source_url`, stored `.txt` |
| 5. Reachability verified from the server before building | spike notes in the PR |

### Commits and PR

```
Record OBS reachability spike results
Fetch OBS course pages with an https-only, no-redirect client
Convert OBS HTML to plain text that keeps table rows
Route OBS imports through the syllabus extraction pipeline
```

PR title: `S9-06 Import a course from its OBS page (T2.9)`.

---

# Sprint 10 — Freeze (Mon 21 – Sun 27 Dec)

**Sprint goal:** *"The demo paths have no known bugs, production holds the final demo data with a backup video, both reports are printed, and `v1.0.0` is tagged."*

**Monday 21 Dec, 09:00: feature freeze.** From now on, `develop` only accepts `fix/` branches for bugs found in this sprint, plus docs. No `feature/` branches, no refactors, no dependency upgrades (Dependabot PRs wait until January). The CSE 311 midterm is on 22 Dec and the CSE 321 midterm on 24 Dec. Plan around them: Monday is the bug bash, Wednesday and Friday–Saturday are fix days, and Sunday is the release.

| Day | What | Who |
|---|---|---|
| Mon 21 | Bug bash (S10-01), triage at 17:00 | all |
| Tue 22 | CSE 311 midterm. No meetings | — |
| Wed 23 | Fix P1/P2 bugs; print test of both reports (S10-03) | all |
| Thu 24 | CSE 321 midterm. No meetings | — |
| Fri 25 | Last fixes merged by 18:00; staging reseeded and checked | all |
| Sat 26 | Production reseed, backup video recorded (S10-02); release PR opened (S10-04) | B, C |
| Sun 27 | Release `v1.0.0`; GitHub charts and table sizes captured; reports printed | A, C |
| Mon 28 | Full rehearsal with a timer (§13.3) | all |

| ID | Story | Pts | Owner |
|---|---|---|---|
| S10-01 | Bug bash and final fixes | 3 | all |
| S10-02 | Final demo data on production + backup video | 2 | B |
| S10-03 | Final reports: edit, figures, print test, print | 2 | A + C |
| S10-04 | Release `v1.0.0`, README with screenshots | 1 | C |

---

## S10-01 · Bug bash and final fixes

**Points:** 3 · **Owner:** everyone · **Branch:** one `fix/<issue>-<slug>` per bug

### Goal

Every person tests an area they did **not** build. That way the demo paths are exercised by fresh eyes, and the bugs get found by us, not by the graders. Fixes follow strict severity rules, because a "small fix" during a freeze is how demos break.

### Steps

**1. Rotation (2 hours, Monday morning, on staging).**

| Tester | Tests the area of | Script |
|---|---|---|
| A | C's: login and roles, student profile, dashboard, exports, transcript | Demo minutes 5:30–7:30, plus everything in §8.3 a student and a head can open |
| B | A's: seed data, extraction, OBS import, snapshots, TA role | Upload 2 syllabi (one Turkish), 1 OBS URL, run `rebuild_scores --check` |
| C | B's: setup, both grids, grade sheet, publish, bulk upload, clone | Demo minutes 1:00–5:30 end to end, then the messy gradebook |

Everyone also does these, whatever their area:
- Turkish once through the whole demo path.
- A phone (real device, not just DevTools) for the student pages.
- Keyboard only for the grade sheet.
- Two tabs editing the same mapping (B5 AC3).

**2. Report every bug as an issue** with the `bug` template (§9.3), labelled `freeze` and one severity:

| Severity | Meaning | Rule this week |
|---|---|---|
| **P1** | Breaks a demo path, shows a wrong number, or leaks data across roles | Fix now. Pair on it. Test first: write the failing test, then fix |
| **P2** | Visible on a demo path but there's a workaround, or a wrong message/label | Fix by Friday if the fix is under ~30 lines |
| **P3** | Off the demo path, cosmetic | Don't fix. Leave it in the backlog with label `after-v1` |

A **wrong number is always P1**, however small, because the whole product is about trusting numbers.

**3. Triage at 17:00 Monday (30 minutes).** The Scrum Master reads each issue out loud, and the team agrees the severity. Fixes are assigned to the area owner **unless** they're the one who found it. Then someone else fixes it, which spreads knowledge before the demo Q&A.

**4. Fix discipline.**
- Every P1 fix starts with a test that fails without the fix. This is the same red → green rule as the engine.
- One bug per PR. Title: `Fix <what> (#<issue>)`. Review within 4 hours: during the freeze, reviews come before your own work.
- After each merge, the person who **found** the bug re-tests it on staging and closes the issue. Merging doesn't close it.
- If a fix looks bigger than expected (touches a migration, more than 3 files, or needs a design decision): stop and talk. Often the right call this week is a clear error message or hiding the button, not a redesign.

**5. Friday 18:00 is the last merge.** Anything not merged becomes a P3 with `after-v1`.

### Done when

- [ ] Every person ran their rotation script; every bug filed with a severity.
- [ ] Zero open P1. Every P2 fixed or explicitly downgraded at triage.
- [ ] `rebuild_scores --check` reports 0 mismatches on staging after the last merge.
- [ ] CI green on the last `develop` commit; coverage at or above the gate.

### Commits and PR

```
Fix rounding of class average on results page (#131)
Fix Turkish label overflow in grade sheet header (#134)
```

PR titles follow the commit. Link the bug issue with `Closes #…`.

---

## S10-02 · Final demo data and the backup video

**Points:** 2 · **Owner:** Person B · **Depends on:** S10-01 fixes merged and deployed

### Goal

Production holds exactly the data the demo script needs, and nobody touches it afterwards. A recorded video of the whole demo exists on two devices, in case the network, the server or the Claude API fails on the day.

### Steps

**1. Reseed production (Saturday 26 Dec, morning).** Seeding refuses to run with `DEBUG=False` unless explicitly allowed (Appendix B), and that's the point: you have to mean it.

```bash
ssh deploy@<server>
cd /srv/polaris/production
# 1. Safety backup of whatever is there now
docker compose -f compose.prod.yml exec -T db pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" \
  > /srv/backups/before-final-seed-$(date +%F).dump
# 2. Reseed with both programs, then rebuild snapshots and load Turkish PO text
docker compose -f compose.prod.yml exec web python manage.py seed_demo --reset --with-bme --allow-production
docker compose -f compose.prod.yml exec web python manage.py rebuild_scores
docker compose -f compose.prod.yml exec web python manage.py rebuild_scores --check
```

The last command must print `0 mismatches`. Copy the persona passwords that `seed_demo` prints onto the **persona cards** (§13.3), one card per persona: head, instructor, student, TA, BME head.

**2. Prepare the live parts.**
- Run **one syllabus extraction now** for an offering the script doesn't use, and leave it APPLIED. That's the fallback ("here's one we ran earlier").
- Prepare the live one: a new empty CSE 311 offering in 2026F with Dr. Can Aydın, and the syllabus PDF on the presenting laptop's desktop.
- Put the messy gradebook (`seed/grades/messy.xlsx`) next to it.
- Click through the whole script once **as a dry run on production**, then undo what it changed. The simplest undo is to restore the dump you take right after the seed:

```bash
docker compose -f compose.prod.yml exec -T db pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" \
  > /srv/backups/final-demo-$(date +%F).dump          # the golden demo state
# … dry run the script …
docker compose -f compose.prod.yml exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
  < /srv/backups/final-demo-$(date +%F).dump
```

Keep `final-demo-*.dump`. Restoring it on Monday after the rehearsal resets production to the exact demo start state in under a minute.

**3. Record the backup video.**
- **Tool:** QuickTime (macOS: File → New Screen Recording) or OBS Studio. 1920×1080, browser zoom 125% so text is readable on a projector.
- **Content:** the full §13.3 script, with each presenter narrating their part. Ten minutes; one take per part is fine, then cut them together.
- **No real personal data:** everything on screen is seed data. Close other tabs, and turn off notifications (macOS Focus mode).
- **Store it** in three places: the presenting laptop, a USB stick, and the team's Google Drive. Name it `polaris-demo-backup-2026-12-26.mp4`. Test-play it from the USB stick on a **different** computer.

**4. Freeze production.** After the video, post in the team chat: "Production is frozen. No deploys to `main`, no shell commands on production until after the demo, except restoring `final-demo-*.dump`." Pause CD for `main`: Settings → Environments → production → add a required reviewer, or disable the workflow (Actions → CD → ⋯ → Disable workflow). Re-enable it after the demo.

### Done when

- [ ] Production reseeded; `rebuild_scores --check` = 0 mismatches.
- [ ] `final-demo-*.dump` exists and a restore was tested.
- [ ] Persona cards written.
- [ ] Video recorded and stored in three places; played back from USB on another machine.
- [ ] CD to production paused.

### Commits and PR

```
Add final demo runbook and persona card template
```

Commit the runbook as `docs/process/demo-runbook.md` (the commands above, with real hostnames). **Never commit the passwords.** The cards are paper.

---

## S10-03 · Final reports: edit, figures, print

**Points:** 2 · **Owner:** Person A (CSE 321) + Person C (CSE 311) · **Depends on:** S9-01, S9-02

### Goal

Both reports are final, every figure is current (charts captured on 27 Dec, table sizes from production after the reseed), and one printed copy per course is in hand on Monday. The format: **no title page, figures and code at 125%**, printed.

### Steps

**1. Refresh the evidence on Sunday 27 Dec**, after the release:
- GitHub Insights → Contributors and Code frequency screenshots (CSE 311 §3).
- `docs/process/scripts/issues_by_assignee.sh`, `velocity_chart.py` and `ci_runs.sh` re-run (CSE 311 §2 and §5).
- `table_sizes.sql` on **production** (CSE 321 §3).

**2. Edit pass (one person per report, then a swap).**
- Every claim has evidence next to it.
- Every number matches its source.
- Every figure has a caption that says what to notice ("Velocity dips in Sprints 4–5 as planned for checkpoints and midterms").
- Remove anything a grader would skim: no restating the brief, no marketing.
- Then **swap**: A reads the CSE 311 report and C reads the CSE 321 report, looking for anything unclear to someone who wasn't there.

**3. Print checklist (do the print test on Wednesday 23 Dec, the real print on Sunday 27).**

- [ ] **No title page.** Page 1 starts with Section 1. Team name, members and repo URL go in a small header on page 1 only.
- [ ] **Figures at 125%.** Every screenshot was taken at 125% browser zoom, *and* is placed at 100% width of the text column, not shrunk. Check with a ruler: body-text-sized labels in figures should be at least as tall as the body text.
- [ ] **Code at 125%.** Code blocks use 125% of the body font size (13pt for 10.5pt body), or whatever the TA confirmed in S9-01.
- [ ] **Long YAML.** `ci.yml` and `cd.yml` may run onto a second page. Allow page breaks *between* steps, never inside one (`pre { break-inside: auto }` with one `pre` per job if needed).
- [ ] **Colour.** Charts must read in black-and-white too: the lab printer may be greyscale. Velocity uses a dashed average line (it already does), and the heat map uses a legend with numbers.
- [ ] **Page numbers** in the footer (`@page { @bottom-right { content: counter(page); } }` in the render CSS).
- [ ] **Section headings** exactly match the six sections in each report format, in order.
- [ ] **Print test** of 2 pages per report (one figure page, one code page) on the actual printer you'll use, checked by someone who didn't make it.
- [ ] **Final print:** one copy per course, single-sided unless the instructions say otherwise, stapled top-left. Plus a PDF of each in `docs/reports/` and on the team Drive.

### Done when

- [ ] Both PDFs final and committed; both printed copies in Person A's bag on Monday.
- [ ] Every figure regenerated on 27 Dec.

### Commits and PR

```
Finalise CSE 311 report with 27 Dec evidence
Finalise CSE 321 report with production table sizes
```

PR title: `S10-03 Final reports`.

---

## S10-04 · Release v1.0.0

**Points:** 1 · **Owner:** Person C · **Depends on:** S10-01

### Goal

`main` holds exactly what we demo, tagged `v1.0.0`, with a GitHub Release whose notes summarise the product. The README is the front page a grader sees first: what POlaris is, screenshots, how to run it, and links to the spec and reports.

### Steps

**1. README** (on a `docs/S10-04-readme` branch into `develop`, Saturday). Sections:
1. One-paragraph punchline (§1.2) and the scoring chain in one line.
2. Four screenshots at 125%: grade sheet, syllabus review screen, student profile radar, department heat map. Store them in `docs/screenshots/`.
3. Live demo link (production) and "logins on request". Never paste the demo passwords publicly.
4. Feature list by tier (Baseline, Tier 1, Tier 2 shipped), each with a one-line description.
5. Quick start: the §10.4 commands.
6. Architecture image (§4.2 export) and links to `POLARIS-PROJECT-SPEC.md` and `docs/reports/`.
7. Team: names, GitHub handles, areas (§0.3).

**2. Release PR (Saturday evening).** `develop` → `main`, merge commit (§9.6). Title: `Release v1.0.0`. In the description, list every story merged since the last release:

```bash
git log --oneline origin/main..origin/develop --no-merges
```

It needs one approval and green CI. After merging, CD deploys `main` to production. Make sure S10-02's production freeze is lifted **only** for this deploy, and restore `final-demo-*.dump` afterwards **only if** the deploy ran migrations that changed data (it shouldn't: freeze rules).

Order matters: if S10-02's reseed ran *before* this release deploy, re-check `/healthz` and `rebuild_scores --check` after the deploy. If the release came first, there's nothing to re-check.

**3. Tag and release.**

```bash
git switch main && git pull
git tag -a v1.0.0 -m "POlaris 1.0.0: final demo release (CSE 311 / CSE 321, Fall 2026)"
git push origin v1.0.0
gh release create v1.0.0 --title "POlaris 1.0.0" --notes-file docs/process/release-notes-1.0.0.md \
  docs/reports/cse311/report.pdf docs/reports/cse321/report.pdf
```

`release-notes-1.0.0.md` contains: highlights (syllabus wizard, bulk upload, dashboards, transcript, TR/EN), numbers (tests, coverage %, CI runs, sprints, total points), known limitations (the P3 list), and thanks.

**4. Merge `main` back into `develop`** if a hotfix landed directly on `main` during the freeze (§9.6), so the two don't diverge.

### Done when

- [ ] `v1.0.0` tag and GitHub Release exist, with both report PDFs attached.
- [ ] README renders with screenshots on the repo front page.
- [ ] Production `/healthz` green, showing the release commit (Sentry release = tag commit).

### Commits and PR

```
Write README with screenshots, quick start and feature overview
Add release notes for 1.0.0
```

PR titles: `S10-04 README for v1.0.0`, then `Release v1.0.0`.

**Mon 28 Dec:** full rehearsal with a timer, then restore `final-demo-*.dump`. **Tue 29 – Wed 30 Dec:** demo.

---

# Optional · T2.7 Head approval of mapping changes

**Points:** 8 · **Owner:** pulled by whoever has capacity (default Person B with Person A reviewing) · **Branch:** `feature/T2.7-mapping-approval` · **Depends on:** S2-05, S3-01, S8-02

This story is in no sprint. It's here, fully designed, so it can be pulled the moment velocity allows. That will most likely be **after** the course if the department actually adopts POlaris. Decision D13 says that in the baseline the head can view and override any mapping and every change is audited, but there's no approval step. T2.7 adds one, for the situation where it matters: **changing a mapping on a course whose grades students can already see**. That change silently moves published PO scores, which is something an accreditation reviewer would ask about.

### Goal

When an instructor saves either weight grid on an offering that has **at least one published assessment**, the change isn't applied. It becomes a **pending change request**. Scores keep using the current (last approved) mapping. The head sees a list of pending requests, opens a side-by-side diff of old and new cells with the instructor's reason, and approves or rejects with a note. Approval applies the change in one transaction. If the live mapping changed after the request was made, approval is refused as stale. Changes on offerings with nothing published, and changes the head makes themselves, apply immediately as today. Delivers T2.7 AC 1–7.

### Design choices

**Why requests, not a versioned copy of the whole mapping.** One option is a `MappingVersion` table where every edge row carries a version number and the engine reads "the latest approved version". That touches the loaders, the engine inputs, both grid editors, lint and the snapshots, so every part of the scoring path would learn about versions. The design here leaves all of that untouched. The live tables `AssessmentLOWeight` and `LOPOWeight` **are** the approved mapping, always. A pending change lives only as JSON inside a `MappingChangeRequest` until it's approved, at which point the existing write path applies it. The loaders, engine, lint and snapshots don't change at all.

**The cost** of this choice: we can't ask "what was the approved mapping on 3 Nov?" from the weight tables alone. We *can* answer it from the audit trail, because every applied matrix save records the whole before/after matrix as one event (§5.4). That's enough for accreditation questions, and the CSE 321 report can discuss it as a deliberate trade-off between normalised history tables and an event log.

**Staleness.** Each request stores `base_version`, the `matrix_version(offering, kind)` hash of the live grid when the instructor opened it (already sent with the form for B5 AC3). Approval recomputes it. If it differs, the head is approving a diff against a grid that no longer exists, so we refuse and ask the instructor to resubmit. It's the same optimistic-concurrency idea as B5, one level up.

**One pending request per grid per offering.** A partial unique index (`WHERE status = 'pending'`) enforces it. A new save on a grid with a pending request **replaces** the proposal (the old one becomes `superseded`), so the head always reviews the instructor's latest intent.

### Files

| Path | Create / modify | What goes in it |
|---|---|---|
| `apps/outcomes/models.py` | modify | `MappingChangeRequest` |
| `apps/outcomes/services.py` | modify | Split each `save_*_matrix` into a gate + `_apply_*`; `request_change`, `approve_change`, `reject_change`, `withdraw_change` |
| `apps/outcomes/selectors.py` | modify | `needs_approval(user, offering)`, `pending_requests(user, program)`, `request_diff(req)` |
| `apps/outcomes/views.py`, `urls.py` | modify | `approvals`, `approval_detail`, `withdraw_request`; mapping view shows pending banner |
| `apps/outcomes/templates/outcomes/{approvals,approval_detail}.html` | create | Inbox and diff |
| `apps/outcomes/templates/outcomes/mapping.html` | modify | "Pending approval" banner, reason field |
| `apps/outcomes/tests/test_mapping_approval.py` | create | Tests |

### Steps

**1. The model.**

```python
# apps/outcomes/models.py  (add)
from django.conf import settings


class MappingChangeRequest(models.Model):
    class Kind(models.TextChoices):
        ASSESSMENT_LO = "assessment_lo", "Assessment → LO weights"
        LO_PO = "lo_po", "LO → PO weights"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"
        SUPERSEDED = "superseded", "Replaced by a newer request"
        STALE = "stale", "Refused: mapping changed meanwhile"

    offering = models.ForeignKey("catalog.CourseOffering", on_delete=models.CASCADE,
                                 related_name="mapping_requests")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    proposed = models.JSONField()              # [{"row": id, "col": id, "raw": "40"}, …] full grid
    base_version = models.CharField(max_length=64)
    reason = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            models.UniqueConstraint(fields=["offering", "kind"], condition=Q(status="pending"),
                                    name="one_pending_request_per_grid"),
        ]
```

The proposal stores the **whole grid** (every non-blank cell), not a list of edits. Applying it is then exactly what a normal save does: replace the grid. That reuses the existing, tested code path.

**2. Split the save services into a gate and an apply step.** Rename the body of S2-05's `save_assessment_lo_matrix` (everything after its version check) into a private `_apply_assessment_lo_matrix(user, offering, cells)`, and the same for LO→PO. Then the public functions become gates:

```python
# apps/outcomes/services.py  (replace the two public functions; keep the renamed bodies)
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import CourseOffering
from apps.catalog.services import ensure_term_open
from apps.core import audit

from .matrix import matrix_version, validate_assessment_lo_cell, validate_lo_po_cell
from .models import MappingChangeRequest
from .selectors import needs_approval

_APPLY = {}        # filled at the bottom of the module: kind -> apply function
_VALIDATE = {
    MappingChangeRequest.Kind.ASSESSMENT_LO: validate_assessment_lo_cell,
    MappingChangeRequest.Kind.LO_PO: validate_lo_po_cell,
}


@dataclass(frozen=True)
class SaveOutcome:
    applied: bool
    request: MappingChangeRequest | None = None


def _save(user, offering, cells, *, kind, expected_version, reason) -> SaveOutcome:
    ensure_term_open(offering)
    for c in cells:                       # validate before anything else: bad cells never become requests
        _VALIDATE[kind](c.raw)
    with transaction.atomic():
        offering = CourseOffering.objects.select_for_update().get(pk=offering.pk)
        if matrix_version(offering, kind) != expected_version:
            raise ValidationError("This mapping changed since you opened it. Reload to see the latest version.")
        if not needs_approval(user, offering):
            _APPLY[kind](user, offering, cells)
            return SaveOutcome(applied=True)
        if not reason.strip():
            raise ValidationError("Students can already see grades for this course, so the head must approve "
                                  "this change. Please say why you are changing the mapping.")
        MappingChangeRequest.objects.filter(offering=offering, kind=kind, status="pending") \
            .update(status=MappingChangeRequest.Status.SUPERSEDED, decided_at=timezone.now())
        req = MappingChangeRequest.objects.create(
            offering=offering, kind=kind, base_version=expected_version, reason=reason.strip(),
            proposed=[{"row": c.row_id, "col": c.col_id, "raw": c.raw} for c in cells],
            requested_by=user,
        )
        audit.record(user, "mapping.request", req, offering=offering,
                     after={"kind": kind, "cells": req.proposed, "reason": req.reason})
        return SaveOutcome(applied=False, request=req)


def save_assessment_lo_matrix(user, offering, cells, *, expected_version, reason="") -> SaveOutcome:
    return _save(user, offering, cells, kind=MappingChangeRequest.Kind.ASSESSMENT_LO,
                 expected_version=expected_version, reason=reason)


def save_lo_po_matrix(user, offering, cells, *, expected_version, reason="") -> SaveOutcome:
    return _save(user, offering, cells, kind=MappingChangeRequest.Kind.LO_PO,
                 expected_version=expected_version, reason=reason)
```

At the very bottom of `services.py`, after `_apply_assessment_lo_matrix` and `_apply_lo_po_matrix` are defined:

```python
_APPLY.update({
    MappingChangeRequest.Kind.ASSESSMENT_LO: _apply_assessment_lo_matrix,
    MappingChangeRequest.Kind.LO_PO: _apply_lo_po_matrix,
})
```

The return type changes from "the rows written" to `SaveOutcome`. The two mapping views (S2-05) must check `outcome.applied`: show "Saved" when it's true, and "Sent to the head for approval" when it's false. The syllabus wizard's `apply_syllabus_job` and `clone_setup` call the `_apply_*` functions directly. They only run on offerings with no grades at all (T1.2 rule, T2.1 rule), so approval never applies to them.

**3. Who needs approval.**

```python
# apps/outcomes/selectors.py  (add)
from apps.accounts.permissions import is_head
from apps.outcomes.models import Assessment


def needs_approval(user, offering) -> bool:
    """A mapping save waits for the head when students can already see grades for this
    offering and the person saving is not the program's head (or a superuser)."""
    if user.is_superuser or is_head(user, offering.course.program):
        return False
    return Assessment.objects.filter(offering=offering, published_at__isnull=False).exists()
```

**4. Approve, reject, withdraw.**

```python
# apps/outcomes/services.py  (add, above the _APPLY.update line)
from django.core.exceptions import PermissionDenied

from apps.accounts.permissions import is_head

from .matrix import Cell


def approve_change(head, req: MappingChangeRequest, *, note="") -> MappingChangeRequest:
    if not is_head(head, req.offering.course.program) and not head.is_superuser:
        raise PermissionDenied
    ensure_term_open(req.offering)
    with transaction.atomic():
        req = MappingChangeRequest.objects.select_for_update().get(pk=req.pk)
        if req.status != MappingChangeRequest.Status.PENDING:
            raise ValidationError("This request was already decided.")
        offering = CourseOffering.objects.select_for_update().get(pk=req.offering_id)
        if matrix_version(offering, req.kind) != req.base_version:
            req.status, req.decided_by, req.decided_at = (MappingChangeRequest.Status.STALE, head,
                                                           timezone.now())
            req.decision_note = "The mapping changed after this request was made."
            req.save()
            audit.record(head, "mapping.stale", req, offering=offering)
            return req
        cells = [Cell(row_id=c["row"], col_id=c["col"], raw=c["raw"]) for c in req.proposed]
        _APPLY[req.kind](req.requested_by, offering, cells)   # authored by the instructor
        req.status, req.decided_by, req.decided_at, req.decision_note = (
            MappingChangeRequest.Status.APPROVED, head, timezone.now(), note)
        req.save()
        audit.record(head, "mapping.approve", req, offering=offering, after={"note": note})
    return req


def reject_change(head, req: MappingChangeRequest, *, note: str) -> MappingChangeRequest:
    if not is_head(head, req.offering.course.program) and not head.is_superuser:
        raise PermissionDenied
    if not note.strip():
        raise ValidationError("Tell the instructor why the change was rejected.")
    with transaction.atomic():
        req = MappingChangeRequest.objects.select_for_update().get(pk=req.pk)
        if req.status != MappingChangeRequest.Status.PENDING:
            raise ValidationError("This request was already decided.")
        req.status, req.decided_by, req.decided_at, req.decision_note = (
            MappingChangeRequest.Status.REJECTED, head, timezone.now(), note.strip())
        req.save()
        audit.record(head, "mapping.reject", req, offering=req.offering, after={"note": req.decision_note})
    return req


def withdraw_change(user, req: MappingChangeRequest) -> None:
    if req.requested_by_id != user.pk:
        raise PermissionDenied
    with transaction.atomic():
        updated = MappingChangeRequest.objects.filter(pk=req.pk, status="pending").update(
            status=MappingChangeRequest.Status.WITHDRAWN, decided_at=timezone.now())
        if updated:
            audit.record(user, "mapping.withdraw", req, offering=req.offering)
```

`_apply_*` is called with `req.requested_by` as the actor, so the matrix's own audit event says the instructor authored the mapping. The separate `mapping.approve` event records who approved it. Both facts are true, and the history viewer shows them as two lines. A stale request is **saved** with status `stale` (not raised as an error) so the instructor sees why nothing changed. Its `return` exits the `atomic()` block normally, so the status change commits.

`_apply_*` from S2-05 calls `schedule_refresh` (S8-02), so approval refreshes scores after commit. That's the moment published PO scores actually move.

**5. The diff for the head.**

```python
# apps/outcomes/selectors.py  (add)
from dataclasses import dataclass
from decimal import Decimal

from apps.core.templatetags.polaris import weight as format_weight

from .models import AssessmentLOWeight, LOPOWeight, MappingChangeRequest


@dataclass(frozen=True)
class CellChange:
    row_id: int
    col_id: int
    before: str | None
    after: str | None

    @property
    def kind(self) -> str:
        if self.before is None:
            return "added"
        if self.after is None:
            return "removed"
        return "changed"


def _current_cells(req) -> dict[tuple[int, int], str]:
    if req.kind == MappingChangeRequest.Kind.ASSESSMENT_LO:
        rows = AssessmentLOWeight.objects.filter(assessment__offering=req.offering) \
            .values_list("assessment_id", "learning_outcome_id", "weight")
    else:
        rows = LOPOWeight.objects.filter(learning_outcome__offering=req.offering) \
            .values_list("learning_outcome_id", "program_outcome_id", "weight")
    return {(r, c): _canon(w) for r, c, w in rows}


def _canon(value) -> str:
    """One spelling per number so '40', '40.00' and Decimal('40.00') compare equal."""
    return format_weight(Decimal(str(value).replace(",", ".")))


def request_diff(req) -> list[CellChange]:
    before = _current_cells(req)
    after = {(c["row"], c["col"]): _canon(c["raw"]) for c in req.proposed if str(c["raw"]).strip()}
    keys = sorted(before.keys() | after.keys())
    return [CellChange(r, c, before.get((r, c)), after.get((r, c)))
            for r, c in keys if before.get((r, c)) != after.get((r, c))]


def pending_requests(user, program):
    if not (user.is_superuser or is_head(user, program)):
        return MappingChangeRequest.objects.none()
    return (MappingChangeRequest.objects.filter(status="pending", offering__course__program=program)
            .select_related("offering__course", "offering__term", "requested_by"))
```

Both sides go through `_canon`, which formats numbers exactly as the grid displays them (the `weight` filter drops trailing zeros), so `40`, `40.00` and `"40,0"` all compare equal. Don't use `Decimal.normalize()` for this: it turns `40` into `4E+1`.

**6. Views and URLs.**

```python
# apps/outcomes/views.py  (add)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import require_role
from apps.accounts.permissions import is_head

from .models import MappingChangeRequest
from .selectors import pending_requests, request_diff
from .services import approve_change, reject_change, withdraw_change


@login_required
@require_role("head")
def approvals(request):
    program = request.active_program
    return render(request, "outcomes/approvals.html",
                  {"requests": pending_requests(request.user, program), "program": program})


@login_required
@require_role("head")
def approval_detail(request, request_id):
    req = get_object_or_404(MappingChangeRequest.objects.select_related("offering__course"), pk=request_id)
    if not is_head(request.user, req.offering.course.program):
        raise Http404
    if request.method == "POST":
        try:
            if request.POST.get("decision") == "approve":
                req = approve_change(request.user, req, note=request.POST.get("note", ""))
                messages.success(request, "Approved and applied." if req.status == "approved"
                                 else "Not applied: the mapping changed after this request.")
            else:
                reject_change(request.user, req, note=request.POST.get("note", ""))
                messages.info(request, "Rejected. The instructor will see your note.")
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
        return redirect("outcomes:approvals")
    return render(request, "outcomes/approval_detail.html", {"req": req, "changes": request_diff(req)})


@login_required
@require_POST
def withdraw_request(request, request_id):
    req = get_object_or_404(MappingChangeRequest, pk=request_id, requested_by=request.user)
    withdraw_change(request.user, req)
    return redirect("outcomes:mapping", offering_id=req.offering_id)
```

```python
# apps/outcomes/urls.py  (add)
    path("department/approvals/", views.approvals, name="approvals"),
    path("department/approvals/<int:request_id>/", views.approval_detail, name="approval_detail"),
    path("mapping-requests/<int:request_id>/withdraw/", views.withdraw_request, name="withdraw_request"),
```

The diff template shows a table of changes. Each row shows the row label (assessment name or LO number), the column label (LO number or PO number with its short name), before → after, and a badge (added, removed or changed). Above it is the instructor's reason, and below it an Approve/Reject form with a note box. On the mapping page, when the offering has a pending request, show a banner: "A change to this grid is waiting for the head's approval (sent 12 Dec). Students still see scores from the current mapping. [Withdraw]". The grid also gets a **Reason** textarea that appears only when `needs_approval(user, offering)` is true. Add a "Approvals (n)" item to the head's navbar.

### Tests

```python
# apps/outcomes/tests/test_mapping_approval.py
import pytest
from django.core.exceptions import ValidationError

from apps.core.tests.factories import MembershipFactory, UserFactory
from apps.core.tests.scenarios import elif_scenario
from apps.outcomes.matrix import Cell, matrix_version
from apps.outcomes.models import LOPOWeight, MappingChangeRequest
from apps.outcomes.services import approve_change, reject_change, save_lo_po_matrix

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx():
    s = elif_scenario()                       # published grades exist
    instructor = s.offering.instructors.first()
    head = UserFactory()
    MembershipFactory(user=head, program=s.offering.course.program, role="head")
    cells = [Cell(s.lo1.pk, s.po1.pk, "5"), Cell(s.lo2.pk, s.po1.pk, "2"), Cell(s.lo2.pk, s.po2.pk, "5")]
    return s, instructor, head, cells


def test_instructor_change_on_published_course_becomes_request(ctx):
    s, instructor, _head, cells = ctx
    v = matrix_version(s.offering, "lo_po")
    out = save_lo_po_matrix(instructor, s.offering, cells, expected_version=v, reason="LO1 is central to PO1")
    assert not out.applied and out.request.status == "pending"
    assert LOPOWeight.objects.get(learning_outcome=s.lo1, program_outcome=s.po1).weight == 4   # unchanged


def test_reason_is_required(ctx):
    s, instructor, _head, cells = ctx
    with pytest.raises(ValidationError):
        save_lo_po_matrix(instructor, s.offering, cells,
                          expected_version=matrix_version(s.offering, "lo_po"), reason=" ")


def test_head_saves_apply_immediately(ctx):
    s, _i, head, cells = ctx
    out = save_lo_po_matrix(head, s.offering, cells, expected_version=matrix_version(s.offering, "lo_po"))
    assert out.applied
    assert LOPOWeight.objects.get(learning_outcome=s.lo1, program_outcome=s.po1).weight == 5


def test_approve_applies_and_records_author(ctx):
    s, instructor, head, cells = ctx
    out = save_lo_po_matrix(instructor, s.offering, cells,
                            expected_version=matrix_version(s.offering, "lo_po"), reason="r")
    req = approve_change(head, out.request, note="ok")
    assert req.status == "approved"
    assert LOPOWeight.objects.get(learning_outcome=s.lo1, program_outcome=s.po1).weight == 5


def test_stale_request_is_refused(ctx):
    s, instructor, head, cells = ctx
    out = save_lo_po_matrix(instructor, s.offering, cells,
                            expected_version=matrix_version(s.offering, "lo_po"), reason="r")
    LOPOWeight.objects.filter(learning_outcome=s.lo2, program_outcome=s.po2).update(weight=3)  # head edits meanwhile
    req = approve_change(head, out.request)
    assert req.status == "stale"
    assert LOPOWeight.objects.get(learning_outcome=s.lo1, program_outcome=s.po1).weight == 4


def test_new_save_supersedes_pending(ctx):
    s, instructor, _h, cells = ctx
    v = matrix_version(s.offering, "lo_po")
    first = save_lo_po_matrix(instructor, s.offering, cells, expected_version=v, reason="a").request
    save_lo_po_matrix(instructor, s.offering, cells, expected_version=v, reason="b")
    first.refresh_from_db()
    assert first.status == "superseded"
    assert MappingChangeRequest.objects.filter(status="pending").count() == 1


def test_reject_needs_note_and_changes_nothing(ctx):
    s, instructor, head, cells = ctx
    req = save_lo_po_matrix(instructor, s.offering, cells,
                            expected_version=matrix_version(s.offering, "lo_po"), reason="r").request
    with pytest.raises(ValidationError):
        reject_change(head, req, note="")
    reject_change(head, req, note="PO1 already over-claimed (L005)")
    assert LOPOWeight.objects.get(learning_outcome=s.lo1, program_outcome=s.po1).weight == 4


def test_course_without_published_grades_applies_directly():
    s = elif_scenario(published=False)
    instructor = s.offering.instructors.first()
    cells = [Cell(s.lo1.pk, s.po1.pk, "3")]
    out = save_lo_po_matrix(instructor, s.offering, cells, expected_version=matrix_version(s.offering, "lo_po"))
    assert out.applied
```

`test_stale_request_is_refused` edits the table directly to simulate "someone changed it meanwhile", which bypasses services on purpose. The existing S2-05 tests for `save_*_matrix` must be updated to read `SaveOutcome` instead of the old return value. That's part of this story's points.

### Check it works

1. As Dr. Can Aydın on CSE 311 (published midterm), change one LO→PO cell. The Reason box appears, and saving shows "Sent to the head for approval". Elif's profile is unchanged.
2. As Prof. Deniz Kara, Approvals (1) → open it. The diff shows one changed cell with the reason. Approve.
3. Wait for the worker. Elif's PO score has moved, and the history shows "mapping.request", the matrix save by Dr. Aydın, and "mapping.approve" by Prof. Kara.

### Done when

| AC (T2.7) | Proved by |
|---|---|
| 1. Instructor changes on offerings with published grades wait for approval | `test_instructor_change_on_published_course_becomes_request` |
| 2. Scores use the last approved mapping until approval | same test (weights unchanged) |
| 3. Head sees a diff with the reason and approves or rejects with a note | `approval_detail`, `test_reject_needs_note_and_changes_nothing` |
| 4. Approval applies in one transaction and refreshes scores | `test_approve_applies_and_records_author`, S8-02 refresh |
| 5. Stale requests are refused, not applied | `test_stale_request_is_refused` |
| 6. One pending request per grid; newer replaces older | `test_new_save_supersedes_pending` |
| 7. Head's own changes and unpublished courses skip approval | `test_head_saves_apply_immediately`, `test_course_without_published_grades_applies_directly` |

### Commits and PR

```
Add MappingChangeRequest with one pending request per grid
Route instructor mapping saves on published courses through approval
Add approval inbox and cell diff for the head
Refuse stale approvals using the matrix version hash
```

PR title: `T2.7 Head approval of mapping changes`.

---

## Code map additions

Copy these into spec §4.8 in the PR that adds each one.

| Module | Name | Signature | Purpose |
|---|---|---|---|
| `scoring/models.py` | `StudentLOScore`, `StudentPOScore` | models (S8-02) | Snapshot tables; `StudentPOScore.Scope` = `cumulative` / `term` |
| `scoring/snapshots.py` | `snapshot_offering` | `(offering) -> int` | Rewrite LO and PO snapshots for an offering's students |
| `scoring/snapshots.py` | `snapshot_student` | `(student, program) -> None` | Rewrite one student's PO snapshots |
| `scoring/snapshots.py` | `refresh_views` | `() -> None` | `REFRESH MATERIALIZED VIEW CONCURRENTLY` both views |
| `scoring/snapshots.py` | `AttainmentCell`, `read_attainment` | `(program_id, *, term_ids, cohort=None, by="cohort") -> dict[(po_id, key), AttainmentCell]` | Read `mv_po_attainment` |
| `scoring/snapshots.py` | `read_coverage` | `(program_id, *, term_ids) -> dict[(offering_id, po_id), Decimal]` | Read `mv_course_po_coverage` |
| `scoring/tasks.py` | `schedule_refresh` | `(offering) -> None` | `on_commit` → `refresh_scores.delay` |
| `scoring/aggregates.py` | `AttainmentMatrix.from_cells`, `CoverageMatrix.from_totals` | classmethods | Build dashboard matrices from the views |
| `scoring/management/commands/rebuild_scores.py` | `rebuild_scores` | `[--offering ID] [--check]` | Full rebuild / verification |
| `outcomes/services.py` | `clone_setup`, `CloneResult` | `(user, target, source) -> CloneResult` | T2.1 |
| `outcomes/selectors.py` | `clone_candidates` | `(user, offering) -> QuerySet` | T2.1 |
| `outcomes/views.py` | `clone_setup_view` | URL `outcomes:clone` `…/setup/clone/` POST | T2.1 |
| `reports/models.py` | `TranscriptIssue`, `new_verification_code` | model (S8-04) | Frozen transcript payload + code |
| `reports/svg.py` | `radar_svg` | `(labels, values, threshold) -> str` | Server-side radar for PDFs |
| `reports/exports.py` | `transcript_payload`; `render_transcript_pdf` | `(student) -> dict`; **changed** to `(student, *, base_url) -> tuple[bytes, TranscriptIssue]` | T2.4 |
| `reports/views.py` | `verify_transcript` | URL `reports:verify_transcript` `/verify/<code>/` GET, public | T2.4 |
| `reports/models.py` | `CompletionDeadline`, `ReminderPreference`, `ReminderLog` | models (S8-03) | T2.2 |
| `reports/reminders.py` | `pending_items`, `Reminder`, `build_reminders` | `(offering, *, require_all_published) -> list[str]`; `(term, today) -> list[Reminder]` | T2.2 |
| `reports/tasks.py` | `send_completion_reminders`, `unsubscribe_token`, `UNSUBSCRIBE_SALT` | `(site_url=None) -> int` | T2.2 |
| `reports/views.py` | `term_deadline`, `reminders_unsubscribe` | URLs `reports:term_deadline` `/department/terms/<term_id>/deadline/`, `reports:reminders_unsubscribe` `/reminders/unsubscribe/<token>/` (public) | T2.2 |
| `reports/forms.py` | `CompletionDeadlineForm` | form | T2.2 |
| settings | `SITE_URL`, `USE_SCORE_SNAPSHOTS`, `CELERY_BEAT_SCHEDULE`, `CELERY_TIMEZONE`, `SENTRY_DSN` | env-driven | S8-02, S8-03, S9-04 |
| `core/views.py` | `sentry_check` | URL `sentry_check` `/ops/sentry-check/` (superuser) | S9-04 |
| `core/tasks.py` | `sentry_check_task` | task | S9-04 |
| `core/programs.py` | `programs_for`, `active_program`, `SESSION_KEY` | `(user, role=None)`, `(request) -> Program \| None` | T2.6 |
| `core/views.py` | `switch_program` | URL `switch_program` `/program/` POST | T2.6 |
| `core/templatetags/polaris.py` | `po_short`, `po_description`; `score` localises the decimal mark | filters | T2.5 |
| `catalog/models.py` | `ProgramOutcome.short_name_tr`, `description_tr` | fields | T2.5 |
| `catalog/management/commands/load_po_translations.py` | `load_po_translations` | `[--program CSE] [--file path]` | T2.5 |
| `config/urls.py` | `set_language` (Django) | `/i18n/setlang/` POST, public | T2.5 |
| `catalog/models.py` | `OfferingAssistant` | model | T2.8 |
| `catalog/services.py` | `add_assistant`, `remove_assistant` | `(user, offering, email)`, `(user, row)` | T2.8 |
| `catalog/selectors.py` | `assisted_offerings` | `(user) -> QuerySet` | T2.8 |
| `catalog/views.py` | `offering_assistants`, `assisting` | URLs `catalog:offering_assistants` `/offerings/<offering_id>/assistants/`, `catalog:assisting` `/assisting/` | T2.8 |
| `accounts/permissions.py` | `is_assistant`, `can_grade_offering`; `OfferingPerms.can_grade`, `OfferingPerms.is_assistant` | `(user, offering) -> bool` | T2.8 |
| `accounts/decorators.py` | `require_offering_access(..., allow_assistants=False)` | new keyword | T2.8 |
| `ingestion/models.py` | `IngestionJob.source_url` | field | T2.9 |
| `ingestion/obs.py` | `validate_obs_url`, `fetch_obs_page`, `html_to_text`, `OBS_HOST` | `(url) -> str` each | T2.9 |
| `ingestion/services.py` | `create_obs_job` | `(user, offering, url) -> IngestionJob` | T2.9 |
| `ingestion/tasks.py` | `run_obs_import` | `(job_id)` | T2.9 |
| `ingestion/forms.py` | `ObsImportForm` | form | T2.9 |
| `ingestion/views.py` | `start_obs` | URL `ingestion:start_obs` `/offerings/<offering_id>/syllabus/obs/` POST | T2.9 |
| `outcomes/models.py` | `MappingChangeRequest` | model (T2.7) | Pending mapping changes |
| `outcomes/services.py` | `SaveOutcome`; `save_*_matrix` **changed** to take `reason=""` and return `SaveOutcome`; `_apply_*_matrix`; `approve_change`, `reject_change`, `withdraw_change` | — | T2.7 |
| `outcomes/selectors.py` | `needs_approval`, `pending_requests`, `request_diff`, `CellChange` | — | T2.7 |
| `outcomes/views.py` | `approvals`, `approval_detail`, `withdraw_request` | URLs `outcomes:approvals` `/department/approvals/`, `outcomes:approval_detail` `/department/approvals/<request_id>/`, `outcomes:withdraw_request` `/mapping-requests/<request_id>/withdraw/` | T2.7 |
| `.github/workflows/uptime.yml` | Uptime | schedule every 15 min | T2.10 |
| `compose.prod.yml` | `beat` service | — | T2.2 |
