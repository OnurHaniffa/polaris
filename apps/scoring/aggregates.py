"""Class- and program-level numbers. Always averages of per-student engine results,
never a separate formula on pooled grades (spec §2.5)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from apps.accounts.models import ProgramMembership, User
from apps.catalog.models import Enrollment, ProgramOutcome, ProgramOutcomeSet
from apps.catalog.selectors import active_po_set

from .engine import ZERO, NodeScore, compute_student_profile
from .loaders import load_offering_inputs, load_student_inputs

BUCKETS = 10
NO_EVIDENCE = NodeScore(score=None, coverage=ZERO)


def mean(values: list[Decimal]) -> Decimal | None:
    return None if not values else sum(values, ZERO) / Decimal(len(values))


def bucket_of(score: Decimal) -> int:
    """0..9. 100 belongs to the top bucket."""
    return min(int(score // 10), BUCKETS - 1)


@dataclass(frozen=True)
class StudentLORow:
    enrollment_id: int
    student_id: int
    student_number: str | None
    name: str
    scores: dict[int, NodeScore]  # lo_id -> NodeScore


@dataclass(frozen=True)
class LOStats:
    lo_id: int
    number: int
    description: str
    mean: Decimal | None
    n: int
    histogram: tuple[int, ...] = field(default=(0,) * BUCKETS)

    @property
    def histogram_heights(self) -> list[int]:
        top = max(self.histogram) or 1
        return [round(100 * c / top) for c in self.histogram]


@dataclass(frozen=True)
class POContribution:
    po_id: int
    number: int
    short_name: str
    mean: Decimal | None
    n: int


@dataclass(frozen=True)
class ClassLOSummary:
    los: list[LOStats]
    rows: list[StudentLORow]
    po_contribution: list[POContribution]
    enrolled: int


def class_lo_summary(offering) -> ClassLOSummary:
    los = list(offering.learning_outcomes.order_by("number"))
    enrollments = list(
        offering.enrollments.filter(status=Enrollment.Status.ENROLLED)
        .select_related("student")
        .order_by("student__student_number", "student__last_name", "student__first_name")
    )
    inputs = load_offering_inputs(offering)

    rows: list[StudentLORow] = []
    lo_values: dict[int, list[Decimal]] = {lo.id: [] for lo in los}
    po_values: dict[int, list[Decimal]] = defaultdict(list)

    for enr in enrollments:
        off_inputs = inputs.get(enr.id)
        profile = compute_student_profile([off_inputs]) if off_inputs else None
        scores: dict[int, NodeScore] = {}
        for lo in los:
            ns = (
                profile.lo_scores.get((offering.id, lo.id), NO_EVIDENCE) if profile else NO_EVIDENCE
            )
            scores[lo.id] = ns
            if ns.score is not None:
                lo_values[lo.id].append(ns.score)
        if profile:
            for po_id, ns in profile.po_scores.items():
                if ns.score is not None:
                    po_values[po_id].append(ns.score)
        rows.append(
            StudentLORow(
                enrollment_id=enr.id,
                student_id=enr.student_id,
                student_number=enr.student.student_number,
                name=enr.student.get_full_name(),
                scores=scores,
            )
        )

    stats = []
    for lo in los:
        values = lo_values[lo.id]
        counts = [0] * BUCKETS
        for v in values:
            counts[bucket_of(v)] += 1
        stats.append(
            LOStats(
                lo_id=lo.id,
                number=lo.number,
                description=lo.description,
                mean=mean(values),
                n=len(values),
                histogram=tuple(counts),
            )
        )

    pos = (
        ProgramOutcome.objects.filter(lo_weights__learning_outcome__offering=offering)
        .distinct()
        .order_by("number")
    )
    contribution = [
        POContribution(
            po_id=po.id,
            number=po.number,
            short_name=po.short_name,
            mean=mean(po_values.get(po.id, [])),
            n=len(po_values.get(po.id, [])),
        )
        for po in pos
    ]
    return ClassLOSummary(
        los=stats, rows=rows, po_contribution=contribution, enrolled=len(enrollments)
    )


@dataclass(frozen=True)
class POSummary:
    po: ProgramOutcome
    mean: Decimal | None
    n_evidence: int  # bu PO için herhangi bir puanı olan öğrenci sayısı
    n_attaining: int  # bunlardan puanı >= eşik olanlar

    @property
    def rate(self) -> Decimal | None:
        """Başarı oranı (P11), 0..1. Kimsenin kanıtı yoksa None."""
        if self.n_evidence == 0:
            return None
        return Decimal(self.n_attaining) / Decimal(self.n_evidence)


def program_po_summary(program, *, terms, include_open_terms, cohort=None) -> list[POSummary]:
    """Programın aktif PO setindeki her PO için, `terms` içindeki en son döneme kadar
    öğrencilerin kümülatif PO puanlarının ortalaması."""
    terms = list(terms)
    try:
        pos = list(active_po_set(program).outcomes.all())
    except ProgramOutcomeSet.DoesNotExist:
        return []
    if not terms:
        return [POSummary(po=po, mean=None, n_evidence=0, n_attaining=0) for po in pos]
    up_to_term = max(terms, key=lambda t: t.starts_on)
    threshold = program.attainment_threshold

    # Tek filter çağrısı: rol ve kohort aynı membership satırına bağlanır.
    membership = {
        "memberships__program": program,
        "memberships__role": ProgramMembership.Role.STUDENT,
    }
    if cohort is not None:
        membership["memberships__cohort_year"] = cohort
    students = User.objects.filter(**membership)

    values: dict[int, list[Decimal]] = {po.id: [] for po in pos}
    for student in students.distinct().order_by("pk").iterator():
        inputs = load_student_inputs(
            student, include_open_terms=include_open_terms, up_to_term=up_to_term
        )
        if not inputs:
            continue
        profile = compute_student_profile(inputs)
        for po in pos:
            ns = profile.po_scores.get(po.id)
            if ns is not None and ns.score is not None:
                values[po.id].append(ns.score)

    return [
        POSummary(
            po=po,
            mean=mean(values[po.id]),
            n_evidence=len(values[po.id]),
            n_attaining=sum(1 for v in values[po.id] if v >= threshold),
        )
        for po in pos
    ]
