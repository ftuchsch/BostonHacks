"""FastAPI router providing scoring endpoints."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple, Set

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

if __package__:
    from .score import initialise_weights, local_rescore, score_total
    from .scoring import (
        SS_WEIGHTS,
        clash_energy,
        compactness_penalty,
        detect_ss_labels,
        hbond_bonus,
        rotamer_penalty,
    )
    from .stateful import get_state
else:  # pragma: no cover - allows running ``uvicorn main:app`` locally
    from score import initialise_weights, local_rescore, score_total
    from scoring import (
        SS_WEIGHTS,
        clash_energy,
        compactness_penalty,
        detect_ss_labels,
        hbond_bonus,
        rotamer_penalty,
    )
    from stateful import get_state

router = APIRouter()


class AtomPayload(BaseModel):
    element: str
    x: float
    y: float
    z: float


class Point3DModel(BaseModel):
    x: float
    y: float
    z: float

    def as_tuple(self) -> tuple[float, float, float]:  # pragma: no cover - trivial
        return (self.x, self.y, self.z)


class ResidueState(BaseModel):
    index: int
    type: str
    chi_angles: List[float] = []
    phi: float | None = None
    psi: float | None = None
    n: Point3DModel | None = None
    h: Point3DModel | None = None
    o: Point3DModel | None = None


class ScoreRequest(BaseModel):
    payload: dict = {}
    diff: dict | None = None
    atoms: List[AtomPayload] | None = None
    residues: List[ResidueState] | None = None
    target_ss: str | None = None


def _legacy_score(request: ScoreRequest) -> Dict[str, object]:
    atoms = request.atoms or []
    clash = clash_energy(atoms)
    positions = [(atom.x, atom.y, atom.z) for atom in atoms]
    compact = compactness_penalty(positions)

    rotamer_total = 0.0
    ss_entries: List[Dict[str, object]] = []
    per_residue_map: Dict[int, Dict[str, float | int]] = {}
    hbond_total = 0.0

    def _ensure_entry(res_idx: int) -> Dict[str, float | int]:
        entry = per_residue_map.get(res_idx)
        if entry is None:
            entry = {
                "i": res_idx,
                "clash": 0.0,
                "rama": 0.0,
                "rotamer": 0.0,
                "ss": 0.0,
                "compact": 0.0,
                "hbond": 0.0,
            }
            per_residue_map[res_idx] = entry
        return entry

    if request.residues:
        chi_map = {res.index: tuple(res.chi_angles) for res in request.residues}
        residue_types = {res.index: res.type for res in request.residues}
        for residue in request.residues:
            penalty = rotamer_penalty(residue.index, chi_map, residue_types)
            rotamer_total += penalty
            entry = _ensure_entry(residue.index)
            entry["rotamer"] = penalty

            ss_entry: Dict[str, object] = {
                "index": residue.index,
                "phi": residue.phi,
                "psi": residue.psi,
            }
            if residue.n and residue.h:
                ss_entry["n"] = residue.n.as_tuple()
                ss_entry["h"] = residue.h.as_tuple()
            if residue.o:
                ss_entry["o"] = residue.o.as_tuple()
            ss_entries.append(ss_entry)

        if ss_entries:
            hbond_total, hbond_contribs = hbond_bonus(ss_entries)
            for res_idx, value in hbond_contribs.items():
                entry = _ensure_entry(res_idx)
                entry["hbond"] = value

    ss_total = 0.0
    if request.target_ss:
        labels = detect_ss_labels(ss_entries) if ss_entries else ""
        for idx, target in enumerate(request.target_ss):
            actual = labels[idx] if idx < len(labels) else "C"
            weight = SS_WEIGHTS.get(target, 0.0)
            penalty = weight if actual != target else 0.0
            entry = _ensure_entry(idx)
            entry["ss"] = penalty
            ss_total += penalty

    per_residue = [per_residue_map[key] for key in sorted(per_residue_map)]

    total_score = 1000.0 - clash - rotamer_total - ss_total - compact + hbond_total
    return {
        "score": total_score,
        "terms": {
            "clash": clash,
            "rama": 0.0,
            "rotamer": rotamer_total,
            "ss": ss_total,
            "compact": compact,
            "hbond": hbond_total,
        },
        "per_residue": per_residue,
    }


def _capture_coords(residue) -> Dict[str, Tuple[float, float, float]]:
    return {atom.id[1]: atom.xyz for atom in residue.atoms}


def _vec_sub(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec_add(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vec_scale(
    v: Tuple[float, float, float], factor: float
) -> Tuple[float, float, float]:
    return (v[0] * factor, v[1] * factor, v[2] * factor)


def _vec_dot(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vec_cross(
    a: Tuple[float, float, float], b: Tuple[float, float, float]
) -> Tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vec_norm(a: Tuple[float, float, float]) -> float:
    return math.sqrt(_vec_dot(a, a))


def _vec_normalise(
    a: Tuple[float, float, float]
) -> Tuple[float, float, float] | None:
    length = _vec_norm(a)
    if length < 1.0e-6:
        return None
    scale = 1.0 / length
    return (a[0] * scale, a[1] * scale, a[2] * scale)


def _rotate_point_around_axis(
    point: Tuple[float, float, float],
    origin: Tuple[float, float, float],
    axis_unit: Tuple[float, float, float],
    radians: float,
) -> Tuple[float, float, float]:
    """
    Rotate ``point`` around an axis passing through ``origin`` with direction ``axis_unit``.
    """

    rel = _vec_sub(point, origin)
    cos_t = math.cos(radians)
    sin_t = math.sin(radians)
    term1 = _vec_scale(rel, cos_t)
    term2 = _vec_scale(_vec_cross(axis_unit, rel), sin_t)
    term3 = _vec_scale(axis_unit, _vec_dot(axis_unit, rel) * (1 - cos_t))
    rotated = _vec_add(_vec_add(term1, term2), term3)
    return _vec_add(rotated, origin)


def _apply_rotation_to_residues(
    state,
    axis_origin: Tuple[float, float, float],
    axis_direction: Tuple[float, float, float],
    radians: float,
    residues: Iterable[int],
    skip_atoms: Dict[int, Set[str]] | None = None,
) -> Dict[int, Dict[str, Tuple[float, float, float]]]:
    unit = _vec_normalise(axis_direction)
    if unit is None or abs(radians) < 1.0e-6:
        return {}

    updates: Dict[int, Dict[str, Tuple[float, float, float]]] = {}
    for rid in residues:
        residue = state.residues.get(rid)
        if residue is None:
            continue
        excluded = skip_atoms.get(rid) if skip_atoms else None
        if not excluded:
            excluded = set()
        atom_updates: Dict[str, Tuple[float, float, float]] = {}
        for atom in residue.atoms:
            name = atom.id[1]
            if name in excluded:
                continue
            rotated = _rotate_point_around_axis(atom.xyz, axis_origin, unit, radians)
            atom_updates[name] = (
                float(rotated[0]),
                float(rotated[1]),
                float(rotated[2]),
            )
        if atom_updates:
            updates[rid] = atom_updates
    return updates


def _apply_phi(state, res_idx: int, delta: float) -> Dict[int, Dict[str, Tuple[float, float, float]]]:
    residue = state.residues.get(res_idx)
    if residue is None:
        return {}
    coords = _capture_coords(residue)
    n = coords.get("N")
    ca = coords.get("CA")
    if n is None or ca is None:
        return {}
    axis = _vec_sub(ca, n)
    radians = math.radians(delta)
    target_residues = [rid for rid in state.residues if rid >= res_idx]
    skip_atoms = {
        res_idx: {"N", "CA"},
    }
    return _apply_rotation_to_residues(
        state,
        axis_origin=n,
        axis_direction=axis,
        radians=radians,
        residues=target_residues,
        skip_atoms=skip_atoms,
    )


def _apply_psi(state, res_idx: int, delta: float) -> Dict[int, Dict[str, Tuple[float, float, float]]]:
    residue = state.residues.get(res_idx)
    if residue is None:
        return {}
    coords = _capture_coords(residue)
    ca = coords.get("CA")
    c = coords.get("C")
    if ca is None or c is None:
        return {}
    axis = _vec_sub(c, ca)
    radians = math.radians(delta)
    target_residues = [rid for rid in state.residues if rid > res_idx]
    if not target_residues:
        return {}
    return _apply_rotation_to_residues(
        state,
        axis_origin=ca,
        axis_direction=axis,
        radians=radians,
        residues=target_residues,
    )


def _apply_rotamer(coords: Dict[str, Tuple[float, float, float]], rotamer_id: int) -> Dict[str, Tuple[float, float, float]]:
    origin = coords.get("N")
    ca = coords.get("CA")
    if origin is None:
        return {}
    direction = -0.4 if rotamer_id == 0 else 0.4
    updates = {"N": (origin[0] + direction, origin[1], origin[2] + 0.5 * direction)}
    if ca is not None:
        updates["CA"] = (ca[0] - 0.25 * direction, ca[1] + 0.25 * direction, ca[2])
    return updates


def _coerce_vector(value) -> Tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("coordinate must be an array of three numbers")
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        raise ValueError("coordinate components must be numeric")


def _merge_residue_updates(
    target: Dict[int, Dict[str, Tuple[float, float, float]]],
    source: Dict[int, Dict[str, Tuple[float, float, float]]],
) -> None:
    for rid, atoms in source.items():
        bucket = target.setdefault(rid, {})
        bucket.update(atoms)


def _diff_updates(state, diff: Dict[str, object]) -> Tuple[Set[int], Dict[int, Dict[str, Tuple[float, float, float]]]]:
    try:
        res_idx = int(diff["res_idx"])
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail=f"Invalid diff payload: {exc}")

    residue = state.residues.get(res_idx)
    if residue is None:
        raise HTTPException(status_code=404, detail=f"Residue {res_idx} not found")

    move = diff.get("move")
    if not isinstance(move, dict):
        raise HTTPException(status_code=400, detail="diff.move must be an object")

    coords = _capture_coords(residue)
    updates: Dict[int, Dict[str, Tuple[float, float, float]]] = {}
    affected: Set[int] = {res_idx}

    move_type = move.get("type")
    if isinstance(move_type, str):
        move_type = move_type.lower()

    if move_type == "torsion":
        delta = move.get("delta")
        if isinstance(delta, dict):
            phi = delta.get("phi")
            psi = delta.get("psi")
            if phi is not None:
                try:
                    phi_updates = _apply_phi(state, res_idx, float(phi))
                    if phi_updates:
                        _merge_residue_updates(updates, phi_updates)
                        affected |= set(phi_updates)
                except (TypeError, ValueError) as exc:
                    raise HTTPException(status_code=400, detail=f"Invalid phi delta: {exc}") from exc
            if psi is not None:
                try:
                    psi_updates = _apply_psi(state, res_idx, float(psi))
                    if psi_updates:
                        _merge_residue_updates(updates, psi_updates)
                        affected |= set(psi_updates)
                except (TypeError, ValueError) as exc:
                    raise HTTPException(status_code=400, detail=f"Invalid psi delta: {exc}") from exc
    elif move_type == "rotamer":
        rotamer_id = move.get("rotamer_id", 0)
        try:
            rotamer_updates = _apply_rotamer(coords, int(rotamer_id))
            if rotamer_updates:
                updates.setdefault(res_idx, {}).update(rotamer_updates)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid rotamer id: {exc}") from exc
    else:
        for name, value in move.items():
            if not isinstance(name, str):
                continue
            if name == "type":
                continue
            try:
                updates.setdefault(res_idx, {})[name] = _coerce_vector(value)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid atom update for {name}: {exc}") from exc

    return affected, updates


def _serialise_structure(state) -> List[Dict[str, object]]:
    residues_payload: List[Dict[str, object]] = []
    for rid in sorted(state.residues):
        residue = state.residues[rid]
        atoms_payload: List[Dict[str, object]] = []
        ca_coords: Tuple[float, float, float] | None = None
        for atom in residue.atoms:
            name = atom.id[1]
            coords_tuple = (
                float(atom.xyz[0]),
                float(atom.xyz[1]),
                float(atom.xyz[2]),
            )
            if name.upper() == "CA":
                ca_coords = coords_tuple
            atoms_payload.append(
                {
                    "name": name,
                    "element": name[0].upper(),
                    "coords": [coords_tuple[0], coords_tuple[1], coords_tuple[2]],
                }
            )
        centroid = ca_coords or (
            float(residue.atoms[0].xyz[0]),
            float(residue.atoms[0].xyz[1]),
            float(residue.atoms[0].xyz[2]),
        )
        residues_payload.append(
            {
                "index": rid,
                "name": residue.name,
                "coords": [centroid[0], centroid[1], centroid[2]],
                "atoms": atoms_payload,
            }
        )
    return residues_payload


@router.post("/api/score")
async def api_score(req: ScoreRequest):
    state = get_state()
    initialise_weights(state)
    if (
        req.atoms is not None
        or req.residues is not None
        or req.target_ss is not None
    ):
        result = _legacy_score(req)
    else:
        payload = req.payload or {}
        diff = payload.get("diff") or req.diff
        if diff:
            affected_residues, updates = _diff_updates(state, diff)
            if updates:
                for rid, atom_updates in updates.items():
                    state.update_residue_coords(rid, atom_updates)
                result = local_rescore(state, affected_residues)
            else:
                result = score_total(state)
        else:
            result = score_total(state)
    result["structure"] = _serialise_structure(state)
    result["stats"] = {
        "term_eval_calls": state.stats.term_eval_calls,
        "full_passes": state.stats.full_passes,
        "incremental_passes": state.stats.incremental_passes,
    }
    return result


__all__ = ["router"]
