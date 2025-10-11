"""Incremental scoring surface with per-residue caching."""

from __future__ import annotations

from typing import Dict, Set, List, Any
import math

if __package__:
    from .score_math import SCORE_WEIGHTS
    from .state import State, Residue, PerResScore
else:  # pragma: no cover - allows running ``uvicorn main:app`` from this directory
    from score_math import SCORE_WEIGHTS
    from state import State, Residue, PerResScore

PAIR_TERMS = {"clash", "compact", "hbond"}
SINGLE_TERMS = {"rama", "rotamer", "ss"}
ALL_TERMS = ["clash", "rama", "rotamer", "ss", "compact", "hbond"]


def _dist(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _pair_term_stub(state: State, term: str, a: Residue, b: Residue) -> float:
    """Symmetric placeholder pair term using first atom distances."""

    state.stats.bump(term)
    pa = a.atoms[0].xyz
    pb = b.atoms[0].xyz
    d = max(_dist(pa, pb), 1.0e-3)
    if term == "clash":
        return 1.0 / (d * d)
    if term == "compact":
        return 1.0 / d
    if term == "hbond":
        return 0.5 / d
    return 0.0


def _single_term_stub(state: State, term: str, residue: Residue) -> float:
    """Deterministic single-residue placeholder term."""

    state.stats.bump(term)
    rid = residue.id
    if term == "rama":
        return 0.01 * ((rid % 10) - 5)
    if term == "rotamer":
        return 0.02 * ((rid % 7) - 3)
    if term == "ss":
        return 0.015 * ((rid % 5) - 2)
    return 0.0


def compute_per_residue_terms(state: State, res_id: int, neighbor_ids: Set[int]) -> Dict[str, float]:
    """Return per-term contributions assigned to ``res_id``."""

    residue = state.residues[res_id]
    terms: Dict[str, float] = {name: 0.0 for name in ALL_TERMS}
    for term in SINGLE_TERMS:
        terms[term] = _single_term_stub(state, term, residue)
    for term in PAIR_TERMS:
        value = 0.0
        for nid in neighbor_ids:
            if nid == res_id:
                continue
            other = state.residues[nid]
            contrib = _pair_term_stub(state, term, residue, other)
            value += 0.5 * contrib
        terms[term] = value
    return terms


def compose_weighted_total(terms: Dict[str, float], weights: Dict[str, float]) -> float:
    return sum(terms[name] * weights.get(name, 1.0) for name in terms)


def _ensure_cache_for_all(state: State) -> None:
    state.stats.full_passes += 1
    residue_ids = list(state.residues.keys())
    for rid in residue_ids:
        center = [state.residues[rid].atoms[0].xyz]
        neighbours = state.grid.nearby_residues(center, radius=8.0)
        terms = compute_per_residue_terms(state, rid, neighbours)
        total = compose_weighted_total(terms, state.weights)
        state.per_res_cache[rid] = PerResScore(terms=terms, total=total, version=1)


def score_total(state: State) -> Dict[str, Any]:
    if not state.per_res_cache:
        _ensure_cache_for_all(state)
    total = 0.0
    term_totals = {name: 0.0 for name in ALL_TERMS}
    per_res: Dict[int, Dict[str, Any]] = {}
    for rid, cache_entry in state.per_res_cache.items():
        total += cache_entry.total
        per_res[rid] = {
            "total": cache_entry.total,
            "terms": dict(cache_entry.terms),
        }
        for term, value in cache_entry.terms.items():
            term_totals[term] += value * state.weights.get(term, 1.0)
    return {"score": total, "terms": term_totals, "per_residue": per_res}


def local_rescore(state: State, affected_res_ids: Set[int]) -> Dict[str, Any]:
    state.stats.incremental_passes += 1
    moved_points: List[tuple[float, float, float]] = []
    for rid in affected_res_ids:
        moved_points.extend([atom.xyz for atom in state.residues[rid].atoms])
    neighbour_ids = state.grid.nearby_residues(moved_points, radius=8.0)
    todo = set(neighbour_ids) | set(affected_res_ids)
    for rid in todo:
        centre = [state.residues[rid].atoms[0].xyz]
        neighbours = state.grid.nearby_residues(centre, radius=8.0)
        terms = compute_per_residue_terms(state, rid, neighbours)
        total = compose_weighted_total(terms, state.weights)
        previous = state.per_res_cache.get(rid)
        version = (previous.version + 1) if previous else 1
        state.per_res_cache[rid] = PerResScore(terms=terms, total=total, version=version)
    return score_total(state)


def initialise_weights(state: State) -> None:
    """Ensure the state's weights default to ``SCORE_WEIGHTS`` if missing."""

    if not state.weights:
        state.weights.update(SCORE_WEIGHTS)


__all__ = [
    "compute_per_residue_terms",
    "compose_weighted_total",
    "score_total",
    "local_rescore",
    "initialise_weights",
]
