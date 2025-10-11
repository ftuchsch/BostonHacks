"""Heuristic "nudge" suggestions for the FoldIt prototype."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple

from app.server.score import initialise_weights, local_rescore, score_total
from app.server.state import Residue, State


NUDGE_TERMS = ("clash", "rama", "rotamer", "ss")


def _capture_coords(residue: Residue) -> Dict[str, Tuple[float, float, float]]:
    return {atom.id[1]: atom.xyz for atom in residue.atoms}


def _apply_phi(coords: Dict[str, Tuple[float, float, float]], delta: float) -> Dict[str, Tuple[float, float, float]]:
    origin = coords.get("N")
    if origin is None:
        return {}
    radians = math.radians(delta)
    amplitude = 0.35
    dx = amplitude * math.cos(radians)
    dy = amplitude * math.sin(radians)
    return {"N": (origin[0] + dx, origin[1] + dy, origin[2])}


def _apply_psi(coords: Dict[str, Tuple[float, float, float]], delta: float) -> Dict[str, Tuple[float, float, float]]:
    origin = coords.get("N")
    if origin is None:
        return {}
    radians = math.radians(delta)
    amplitude = 0.35
    dy = amplitude * math.cos(radians)
    dz = amplitude * math.sin(radians)
    return {"N": (origin[0], origin[1] + dy, origin[2] + dz)}


def _apply_rotamer(
    coords: Dict[str, Tuple[float, float, float]], rotamer_id: int
) -> Dict[str, Tuple[float, float, float]]:
    origin = coords.get("N")
    ca = coords.get("CA")
    if origin is None:
        return {}
    direction = -0.4 if rotamer_id == 0 else 0.4
    updates = {"N": (origin[0] + direction, origin[1], origin[2] + 0.5 * direction)}
    if ca is not None:
        updates["CA"] = (ca[0] - 0.25 * direction, ca[1] + 0.25 * direction, ca[2])
    return updates


def _generate_moves(coords: Dict[str, Tuple[float, float, float]]) -> Iterable[Dict[str, object]]:
    for delta in (-10.0, -5.0, 5.0, 10.0):
        yield {"type": "phi", "delta": delta, "updates": _apply_phi(coords, delta)}
    for delta in (-10.0, -5.0, 5.0, 10.0):
        yield {"type": "psi", "delta": delta, "updates": _apply_psi(coords, delta)}
    for rotamer_id in (0, 1):
        yield {
            "type": "rotamer",
            "rotamer_id": rotamer_id,
            "updates": _apply_rotamer(coords, rotamer_id),
        }


def _pick_centres(per_residue: Dict[int, Dict[str, object]], limit: int) -> List[int]:
    scored: List[Tuple[float, int]] = []
    for rid, payload in per_residue.items():
        terms = payload.get("terms", {})
        severity = sum(float(terms.get(name, 0.0)) for name in NUDGE_TERMS)
        scored.append((severity, rid))
    scored.sort(reverse=True)
    return [rid for _, rid in scored[:limit]]


def suggest_nudge(state: State, max_candidates: int = 200) -> Dict[str, object]:
    """Return the best heuristic nudge suggestion for the provided state."""

    initialise_weights(state)
    if not state.residues:
        return {
            "res_idx": -1,
            "move": {"type": "phi", "delta": 0.0},
            "expected_delta_score": 0.0,
            "term_deltas": {name: 0.0 for name in ("clash", "rama", "rotamer", "ss", "compact", "hbond")},
        }

    baseline = score_total(state)
    baseline_score = float(baseline["score"])
    baseline_terms = dict(baseline["terms"])
    per_residue = baseline["per_residue"]

    centres = _pick_centres(per_residue, limit=min(10, len(per_residue)))

    best_delta = float("-inf")
    best_payload: Dict[str, object] | None = None
    evaluated = 0

    for centre in centres:
        residue = state.residues.get(centre)
        if residue is None:
            continue
        original = _capture_coords(residue)
        for move in _generate_moves(original):
            if evaluated >= max_candidates:
                break
            updates = move.get("updates")
            if not updates:
                evaluated += 1
                continue

            state.update_residue_coords(centre, updates)
            result = local_rescore(state, {centre})
            candidate_score = float(result["score"])
            delta_score = baseline_score - candidate_score
            term_deltas = {
                term: float(result["terms"].get(term, 0.0)) - float(baseline_terms.get(term, 0.0))
                for term in baseline_terms
            }
            if delta_score > best_delta:
                move_payload = {k: v for k, v in move.items() if k != "updates"}
                best_payload = {
                    "res_idx": centre,
                    "move": move_payload,
                    "expected_delta_score": delta_score,
                    "term_deltas": term_deltas,
                }
                best_delta = delta_score

            state.update_residue_coords(centre, {name: original[name] for name in updates})
            baseline = local_rescore(state, {centre})
            baseline_score = float(baseline["score"])
            baseline_terms = dict(baseline["terms"])
            evaluated += 1
        if evaluated >= max_candidates:
            break

    if best_payload is None:
        # Fallback if nothing improved – return neutral move on first residue.
        first_idx = next(iter(state.residues))
        best_payload = {
            "res_idx": first_idx,
            "move": {"type": "phi", "delta": 0.0},
            "expected_delta_score": 0.0,
            "term_deltas": {term: 0.0 for term in baseline_terms},
        }

    return best_payload


__all__ = ["suggest_nudge"]

