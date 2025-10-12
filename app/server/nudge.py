"""Model-guided "nudge" suggestions for the FoldIt prototype."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple

try:  # pragma: no cover - optional dependency
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - gracefully handle missing NumPy
    np = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    import joblib  # type: ignore
except Exception:  # pragma: no cover - gracefully handle missing joblib
    joblib = None  # type: ignore[assignment]

if __package__:
    from .features import build_features
    from .score import initialise_weights, local_rescore, score_total
    from .state import PerResScore, Residue, State
else:  # pragma: no cover - allows running ``uvicorn main:app`` from this directory
    from features import build_features
    from score import initialise_weights, local_rescore, score_total
    from state import PerResScore, Residue, State


NUDGE_TERMS = ("clash", "rama", "rotamer", "ss")
MOVES_PER_RESIDUE = 10
MODEL_PATH = Path(__file__).resolve().parent / "models" / "delta_score.pkl"
_DELTA_MODEL = None
_DELTA_MODEL_LOADED = False
_TIE_EPS = 1.0e-9


def _capture_coords(residue: Residue) -> Dict[str, Tuple[float, float, float]]:
    return {atom.id[1]: atom.xyz for atom in residue.atoms}


def _apply_phi(coords: Dict[str, Tuple[float, float, float]], delta: float) -> Dict[str, Tuple[float, float, float]]:
    origin = coords.get("N")
    ca = coords.get("CA")
    if origin is None or ca is None:
        return {}
    radians = math.radians(delta)
    axis = (
        ca[0] - origin[0],
        ca[1] - origin[1],
        ca[2] - origin[2],
    )
    length = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
    if length < 1.0e-6:
        return {}
    ux, uy, uz = axis[0] / length, axis[1] / length, axis[2] / length
    cos_t = math.cos(radians)
    sin_t = math.sin(radians)

    def _rotate(point: Tuple[float, float, float]) -> Tuple[float, float, float]:
        rel = (
            point[0] - origin[0],
            point[1] - origin[1],
            point[2] - origin[2],
        )
        dot = rel[0] * ux + rel[1] * uy + rel[2] * uz
        cross = (
            uy * rel[2] - uz * rel[1],
            uz * rel[0] - ux * rel[2],
            ux * rel[1] - uy * rel[0],
        )
        rotated = (
            rel[0] * cos_t + cross[0] * sin_t + ux * dot * (1 - cos_t),
            rel[1] * cos_t + cross[1] * sin_t + uy * dot * (1 - cos_t),
            rel[2] * cos_t + cross[2] * sin_t + uz * dot * (1 - cos_t),
        )
        return (
            rotated[0] + origin[0],
            rotated[1] + origin[1],
            rotated[2] + origin[2],
        )

    rotated_n = _rotate(origin)
    return {"N": rotated_n}


def _apply_psi(coords: Dict[str, Tuple[float, float, float]], delta: float) -> Dict[str, Tuple[float, float, float]]:
    ca = coords.get("CA")
    c = coords.get("C")
    if ca is None or c is None:
        return {}
    radians = math.radians(delta)
    axis = (
        c[0] - ca[0],
        c[1] - ca[1],
        c[2] - ca[2],
    )
    length = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
    if length < 1.0e-6:
        return {}
    ux, uy, uz = axis[0] / length, axis[1] / length, axis[2] / length
    cos_t = math.cos(radians)
    sin_t = math.sin(radians)

    def _rotate(point: Tuple[float, float, float]) -> Tuple[float, float, float]:
        rel = (
            point[0] - ca[0],
            point[1] - ca[1],
            point[2] - ca[2],
        )
        dot = rel[0] * ux + rel[1] * uy + rel[2] * uz
        cross = (
            uy * rel[2] - uz * rel[1],
            uz * rel[0] - ux * rel[2],
            ux * rel[1] - uy * rel[0],
        )
        rotated = (
            rel[0] * cos_t + cross[0] * sin_t + ux * dot * (1 - cos_t),
            rel[1] * cos_t + cross[1] * sin_t + uy * dot * (1 - cos_t),
            rel[2] * cos_t + cross[2] * sin_t + uz * dot * (1 - cos_t),
        )
        return (
            rotated[0] + ca[0],
            rotated[1] + ca[1],
            rotated[2] + ca[2],
        )

    rotated_n = _rotate(coords.get("N", ca))
    return {"N": rotated_n}


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


def _clone_cache(cache: Dict[int, PerResScore]) -> Dict[int, PerResScore]:
    return {
        rid: PerResScore(terms=dict(entry.terms), total=float(entry.total), version=int(entry.version))
        for rid, entry in cache.items()
    }


def _move_abs_delta(move: Mapping[str, object]) -> float:
    move_type = str(move.get("type", "")).lower()
    if move_type in {"phi", "psi"}:
        return abs(float(move.get("delta", 0.0)))
    if move_type == "rotamer":
        return 0.0
    return abs(float(move.get("delta", 0.0)))


def _candidate_key(candidate: Dict[str, object]) -> Tuple[float, int, str, float]:
    move = candidate["move"]
    move_type = str(move.get("type", ""))
    extra = float(move.get("rotamer_id", move.get("delta", 0.0)) or 0.0)
    return (candidate["abs_delta"], int(candidate["res_idx"]), move_type, extra)


def _format_move_output(move: Mapping[str, object]) -> Dict[str, object]:
    move_type = str(move.get("type", ""))
    if move_type.lower() == "phi":
        return {"type": "torsion", "delta": {"phi": float(move.get("delta", 0.0))}}
    if move_type.lower() == "psi":
        return {"type": "torsion", "delta": {"psi": float(move.get("delta", 0.0))}}
    if move_type.lower() == "rotamer":
        return {"type": "rotamer", "rotamer_id": int(move.get("rotamer_id", 0))}
    return {"type": move_type, **{k: v for k, v in move.items() if k != "type"}}


def _snapshot_terms(baseline_terms: Mapping[str, float], result_terms: Mapping[str, float]) -> Dict[str, float]:
    keys = set(baseline_terms) | set(result_terms)
    return {
        term: float(result_terms.get(term, 0.0)) - float(baseline_terms.get(term, 0.0))
        for term in keys
    }


def _generate_candidates(
    state: State,
    centres: Iterable[int],
    max_candidates: int,
) -> List[Dict[str, object]]:
    candidates: List[Dict[str, object]] = []
    for centre in centres:
        residue = state.residues.get(centre)
        if residue is None:
            continue
        coords = _capture_coords(residue)
        for move in _generate_moves(coords):
            if len(candidates) >= max_candidates:
                break
            updates = move.get("updates")
            if not updates:
                continue
            move_payload = {k: v for k, v in move.items() if k != "updates"}
            candidate = {
                "res_idx": centre,
                "move": move_payload,
                "updates": updates,
                "abs_delta": _move_abs_delta(move_payload),
            }
            candidates.append(candidate)
        if len(candidates) >= max_candidates:
            break
    return candidates


def load_delta_model():
    """Load and cache the ΔScore regression model if available."""

    global _DELTA_MODEL
    global _DELTA_MODEL_LOADED

    if _DELTA_MODEL_LOADED:
        return _DELTA_MODEL

    if joblib is None or not MODEL_PATH.exists():
        _DELTA_MODEL_LOADED = True
        _DELTA_MODEL = None
        return None

    try:
        _DELTA_MODEL = joblib.load(MODEL_PATH)
    except Exception:
        _DELTA_MODEL = None
    finally:
        _DELTA_MODEL_LOADED = True

    return _DELTA_MODEL


def _evaluate_candidate(
    state: State,
    candidate: Dict[str, object],
    baseline_score: float,
    baseline_terms: Mapping[str, float],
    baseline_cache: Dict[int, PerResScore],
) -> Tuple[float, Dict[str, float]]:
    res_idx = int(candidate["res_idx"])
    updates: Dict[str, Tuple[float, float, float]] = candidate["updates"]
    residue = state.residues.get(res_idx)
    if residue is None:
        raise ValueError("Residue missing for candidate evaluation")

    original_coords = _capture_coords(residue)
    revert_coords = {name: original_coords[name] for name in updates if name in original_coords}
    cache_restore = _clone_cache(baseline_cache)

    try:
        state.update_residue_coords(res_idx, updates)
        result = local_rescore(state, {res_idx})
        candidate_score = float(result["score"])
        delta_score = baseline_score - candidate_score
        term_deltas = _snapshot_terms(baseline_terms, result["terms"])
    finally:
        if revert_coords:
            state.update_residue_coords(res_idx, revert_coords)
        state.per_res_cache = cache_restore

    return delta_score, term_deltas


def _select_best_predicted(
    candidates: List[Dict[str, object]],
    predictions: Iterable[float],
) -> int:
    best_idx = -1
    best_pred = float("-inf")
    for idx, pred in enumerate(predictions):
        if not math.isfinite(pred):
            return -1
        score = float(pred)
        if best_idx == -1 or score > best_pred + _TIE_EPS:
            best_idx = idx
            best_pred = score
            continue
        if abs(score - best_pred) <= _TIE_EPS:
            current_key = _candidate_key(candidates[idx])
            best_key = _candidate_key(candidates[best_idx])
            if current_key < best_key:
                best_idx = idx
                best_pred = score
    return best_idx


def _improvement_preferred(
    candidate: Dict[str, object],
    delta_score: float,
    best_candidate: Dict[str, object] | None,
    best_delta: float,
) -> bool:
    if best_candidate is None:
        return True
    if delta_score > best_delta + _TIE_EPS:
        return True
    if best_delta > delta_score + _TIE_EPS:
        return False
    return _candidate_key(candidate) < _candidate_key(best_candidate)


def suggest_nudge(state: State, max_candidates: int = 200) -> Dict[str, object]:
    """Return the best nudge suggestion using a model-guided ranking if available."""

    initialise_weights(state)
    if not state.residues:
        empty_terms = {name: 0.0 for name in ("clash", "rama", "rotamer", "ss", "compact", "hbond")}
        return {
            "res_idx": -1,
            "move": {"type": "torsion", "delta": {"phi": 0.0}},
            "expected_delta_score": 0.0,
            "term_deltas": empty_terms,
            "model_used": False,
        }

    baseline = score_total(state)
    baseline_score = float(baseline["score"])
    baseline_terms = {name: float(value) for name, value in baseline["terms"].items()}
    per_residue = baseline["per_residue"]
    baseline_cache = _clone_cache(state.per_res_cache)

    moves_limit = max(1, max_candidates // MOVES_PER_RESIDUE) if max_candidates > 0 else 1
    moves_limit = min(len(per_residue), moves_limit) if per_residue else 0
    if moves_limit == 0 and per_residue:
        moves_limit = 1
    centres = _pick_centres(per_residue, limit=moves_limit or 0)
    candidates = _generate_candidates(state, centres, max_candidates)

    if not candidates:
        first_idx = next(iter(state.residues)) if state.residues else -1
        term_template = {term: 0.0 for term in baseline_terms}
        return {
            "res_idx": first_idx,
            "move": {"type": "torsion", "delta": {"phi": 0.0}},
            "expected_delta_score": 0.0,
            "term_deltas": term_template,
            "model_used": False,
        }

    model = None
    model_used = False
    best_candidate: Dict[str, object] | None = None
    best_delta = float("-inf")
    best_terms: Dict[str, float] = {}

    try:
        model = load_delta_model()
        if model is not None and np is not None:
            feature_vectors: List[np.ndarray] = []
            for candidate in candidates:
                bundle = build_features(state, candidate["res_idx"], candidate["move"])
                vector = np.asarray(bundle.vector, dtype=np.float32)
                if not np.all(np.isfinite(vector)):
                    raise ValueError("Non-finite feature encountered")
                feature_vectors.append(vector)
            if feature_vectors:
                feature_matrix = np.stack(feature_vectors, axis=0)
                predictions = np.asarray(model.predict(feature_matrix), dtype=float).reshape(-1)
                if predictions.shape[0] != len(candidates):
                    raise ValueError("Prediction shape mismatch")
                best_idx = _select_best_predicted(candidates, predictions)
                if best_idx >= 0:
                    chosen = candidates[best_idx]
                    delta_score, term_deltas = _evaluate_candidate(
                        state, chosen, baseline_score, baseline_terms, baseline_cache
                    )
                    best_candidate = chosen
                    best_delta = delta_score
                    best_terms = term_deltas
                    model_used = True
    except Exception:
        model_used = False
        best_candidate = None
        best_delta = float("-inf")
        best_terms = {}

    if not model_used:
        for candidate in candidates:
            try:
                delta_score, term_deltas = _evaluate_candidate(
                    state, candidate, baseline_score, baseline_terms, baseline_cache
                )
            except Exception:
                continue
            if _improvement_preferred(candidate, delta_score, best_candidate, best_delta):
                best_candidate = candidate
                best_delta = delta_score
                best_terms = term_deltas

    if best_candidate is None:
        first_idx = next(iter(state.residues)) if state.residues else -1
        term_template = {term: 0.0 for term in baseline_terms}
        return {
            "res_idx": first_idx,
            "move": {"type": "torsion", "delta": {"phi": 0.0}},
            "expected_delta_score": 0.0,
            "term_deltas": term_template,
            "model_used": False,
        }

    move_output = _format_move_output(best_candidate["move"])
    payload: Dict[str, object] = {
        "res_idx": int(best_candidate["res_idx"]),
        "move": move_output,
        "expected_delta_score": float(best_delta),
        "term_deltas": best_terms,
        "model_used": model_used,
    }
    if best_delta <= 0.0:
        payload["note"] = "no positive improvement"

    # Restore baseline cache to ensure deterministic state for callers.
    state.per_res_cache = _clone_cache(baseline_cache)

    return payload


__all__ = ["load_delta_model", "suggest_nudge"]
