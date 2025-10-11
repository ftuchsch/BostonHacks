"""FastAPI router providing scoring endpoints."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.server.score import initialise_weights, local_rescore, score_total
from app.server.scoring import (
    SS_WEIGHTS,
    clash_energy,
    compactness_penalty,
    detect_ss_labels,
    hbond_bonus,
    rotamer_penalty,
)
from app.server.stateful import get_state

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
        diff = payload.get("diff")
        if diff:
            try:
                res_idx = int(diff["res_idx"])
                move: Dict[str, List[float]] = diff["move"]
            except Exception as exc:  # pragma: no cover - defensive programming
                raise HTTPException(status_code=400, detail=f"Invalid diff payload: {exc}")
            new_xyz = {
                name: (float(coords[0]), float(coords[1]), float(coords[2]))
                for name, coords in move.items()
            }
            state.update_residue_coords(res_idx, new_xyz)
            result = local_rescore(state, {res_idx})
        else:
            result = score_total(state)
    result["stats"] = {
        "term_eval_calls": state.stats.term_eval_calls,
        "full_passes": state.stats.full_passes,
        "incremental_passes": state.stats.incremental_passes,
    }
    return result


__all__ = ["router"]

