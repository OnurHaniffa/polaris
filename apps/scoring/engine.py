"""Pure scoring engine. No Django imports. Every score in POlaris comes from here."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class Edge:
    source: Hashable
    target: Hashable
    weight: Decimal


@dataclass(frozen=True)
class NodeScore:
    score: Decimal | None
    coverage: Decimal


def weighted_average(pairs: Iterable[tuple[Decimal, Decimal]]) -> Decimal | None:
    num = ZERO
    den = ZERO
    for score, weight in pairs:
        num += score * weight
        den += weight
    return None if den == ZERO else num / den


def propagate(
    source_scores: Mapping[Hashable, Decimal], edges: Iterable[Edge]
) -> dict[Hashable, NodeScore]:
    inbound: dict[Hashable, list[Edge]] = defaultdict(list)
    for e in edges:
        if e.weight <= ZERO:
            raise ValueError(f"weight must be positive: {e}")
        inbound[e.target].append(e)

    result: dict[Hashable, NodeScore] = {}
    for target, es in inbound.items():
        total = sum((e.weight for e in es), ZERO)
        present = [(source_scores[e.source], e.weight) for e in es if e.source in source_scores]
        covered = sum((w for _, w in present), ZERO)
        result[target] = NodeScore(score=weighted_average(present), coverage=covered / total)
    return result


def normalise(raw: Decimal, max_score: Decimal) -> Decimal:
    if max_score <= ZERO:
        raise ValueError("max_score must be positive")
    return raw / max_score * HUNDRED


def display(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return str(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class OfferingInputs:
    offering_id: int
    grades: Mapping[int, Decimal]
    max_scores: Mapping[int, Decimal]
    assessment_lo_edges: tuple[Edge, ...]
    lo_po_edges: tuple[Edge, ...]
    # P6: assessments this student is excused from. They drop out of the LO entirely, weight
    # included, so an excused piece of work never leaves the LO looking incomplete.
    excused: frozenset = frozenset()


@dataclass(frozen=True)
class StudentProfile:
    lo_scores: dict[tuple[int, int], NodeScore]
    po_scores: dict[int, NodeScore]
    po_contributors: dict[int, list[tuple[int, int, Decimal]]] = field(default_factory=dict)


def compute_student_profile(offerings: Iterable[OfferingInputs]) -> StudentProfile:
    lo_scores: dict[tuple[int, int], NodeScore] = {}
    lo_values: dict[tuple[int, int], Decimal] = {}
    po_edges: list[Edge] = []
    contributors: dict[int, list[tuple[int, int, Decimal]]] = defaultdict(list)

    for off in offerings:
        normalised = {a: normalise(raw, off.max_scores[a]) for a, raw in off.grades.items()}
        a_lo_edges = [e for e in off.assessment_lo_edges if e.source not in off.excused]
        for lo_id, ns in propagate(normalised, a_lo_edges).items():
            key = (off.offering_id, lo_id)
            lo_scores[key] = ns
            if ns.score is not None:
                lo_values[key] = ns.score
        for e in off.lo_po_edges:
            key = (off.offering_id, e.source)
            po_edges.append(Edge(source=key, target=e.target, weight=e.weight))
            contributors[e.target].append((off.offering_id, e.source, e.weight))

    return StudentProfile(
        lo_scores=lo_scores,
        po_scores=propagate(lo_values, po_edges),
        po_contributors=dict(contributors),
    )
