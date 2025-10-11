"""FastAPI entry point for the FoldIt prototype server."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

if __package__:
    from .scoring import (
        SS_WEIGHTS,
        clash_energy,
        compactness_penalty,
        detect_ss_labels,
        hbond_bonus,
        rotamer_penalty,
    )
else:  # pragma: no cover - allows running ``uvicorn main:app`` from this directory
    from scoring import (
        SS_WEIGHTS,
        clash_energy,
        compactness_penalty,
        detect_ss_labels,
        hbond_bonus,
        rotamer_penalty,
    )

app = FastAPI(title="FoldIt API", openapi_url="/api/openapi.json")

BASE_PREFIX = "/api"


class Atom(BaseModel):
    """Minimal atom representation for scoring."""

    element: str
    x: float
    y: float
    z: float


class Point3D(BaseModel):
    """Simple 3D point container for backbone atoms."""

    x: float
    y: float
    z: float

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


class ResidueState(BaseModel):
    """Minimal residue representation for rotamer and SS scoring."""

    index: int
    type: str
    chi_angles: list[float] = []
    phi: float | None = None
    psi: float | None = None
    n: Point3D | None = None
    h: Point3D | None = None
    o: Point3D | None = None


class ScoreRequest(BaseModel):
    """Request payload for scoring computations."""

    atoms: list[Atom]
    residues: list[ResidueState] | None = None
    target_ss: str | None = None


@app.post(f"{BASE_PREFIX}/score")
async def score(request: ScoreRequest) -> JSONResponse:
    """Compute score terms for the provided atoms."""

    clash = clash_energy(request.atoms)
    positions = [(atom.x, atom.y, atom.z) for atom in request.atoms]
    compact = compactness_penalty(positions)

    rotamer_total = 0.0
    ss_entries: list[dict[str, object]] = []
    per_residue_map: dict[int, dict[str, float | int]] = {}

    def _ensure_entry(res_idx: int) -> dict[str, float | int]:
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

    hbond_total = 0.0

    if request.residues:
        chi_map = {res.index: tuple(res.chi_angles) for res in request.residues}
        residue_types = {res.index: res.type for res in request.residues}
        for residue in request.residues:
            penalty = rotamer_penalty(residue.index, chi_map, residue_types)
            rotamer_total += penalty
            entry = _ensure_entry(residue.index)
            entry["rotamer"] = penalty

            ss_entry: dict[str, object] = {
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
    payload = {
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
    return JSONResponse(payload)


@app.post(f"{BASE_PREFIX}/nudge")
async def nudge() -> JSONResponse:
    """Return a placeholder nudge suggestion."""
    payload = {
        "res_idx": 0,
        "move": {"type": "phi", "delta": 0},
        "expected_delta_score": 0.0,
        "explanation": {
            "clash": 0.0,
            "rama": 0.0,
            "rotamer": 0.0,
            "ss": 0.0,
            "hbond": 0.0,
        },
    }
    return JSONResponse(payload)


@app.post(f"{BASE_PREFIX}/minimize")
async def minimize() -> JSONResponse:
    """Return a placeholder minimization response."""
    payload = {"new_atoms": [], "energy": 0.0}
    return JSONResponse(payload)


@app.get(f"{BASE_PREFIX}/levels")
async def list_levels() -> JSONResponse:
    """Return a placeholder list of levels."""
    payload = {"levels": []}
    return JSONResponse(payload)


@app.get(f"{BASE_PREFIX}/levels/{{level_id}}")
async def get_level(level_id: str) -> JSONResponse:
    """Return a placeholder level specification."""
    payload = {
        "id": level_id,
        "sequence": "",
        "start_atoms": [],
        "target_ss": "",
        "target_contacts": [],
        "tips": [],
    }
    return JSONResponse(payload)


@app.post(f"{BASE_PREFIX}/submit")
async def submit() -> JSONResponse:
    """Return a placeholder submission acknowledgement."""
    payload = {"status": "received", "score": 0.0}
    return JSONResponse(payload)


@app.get(f"{BASE_PREFIX}/leaderboard")
async def leaderboard(level_id: str | None = None) -> JSONResponse:
    """Return a placeholder leaderboard."""
    payload = {"level_id": level_id, "entries": []}
    return JSONResponse(payload)
