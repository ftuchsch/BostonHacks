"""Feature extraction utilities for the ΔScore regression model.

This module translates a ``(state, residue_idx, candidate_move)`` triple into a
fixed-length numeric feature vector described in ``03_FEATURE_DICT.md``. The
returned payload provides both the structured fields (useful for debugging) and
an ``np.ndarray`` representation ready for model consumption.

The implementation focuses on robustness: missing optional inputs fall back to
reasonable defaults so unit tests and downstream consumers can exercise the
behaviour without depending on a fully fledged FoldIt geometry pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence

try:  # pragma: no cover - exercised implicitly in environments with NumPy
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - fallback for stripped-down envs
    class _Array(list):
        @property
        def shape(self) -> tuple[int, ...]:
            return (len(self),)

    class _NPModule:
        float32 = float

        @staticmethod
        def array(seq: Iterable[float], dtype: object | None = None) -> _Array:
            return _Array(float(value) for value in seq)

    np = _NPModule()  # type: ignore[assignment]

if __package__:
    from .score import compute_per_residue_terms
    from .state import Residue, State
else:  # pragma: no cover - allows running ``uvicorn main:app`` from this directory
    from score import compute_per_residue_terms
    from state import Residue, State

AA_ORDER: tuple[str, ...] = (
    "ALA",
    "ARG",
    "ASN",
    "ASP",
    "CYS",
    "GLN",
    "GLU",
    "GLY",
    "HIS",
    "ILE",
    "LEU",
    "LYS",
    "MET",
    "PHE",
    "PRO",
    "SER",
    "THR",
    "TRP",
    "TYR",
    "VAL",
)

SS_STATES = ("H", "E", "C")
MOVE_TYPES = ("phi_pos", "phi_neg", "psi_pos", "psi_neg", "rotamer")


@dataclass(slots=True)
class FeatureBundle:
    """Container for structured features and their vectorised representation."""

    fields: Dict[str, object]
    vector: np.ndarray


def _one_hot(value: str, vocabulary: Sequence[str]) -> List[float]:
    mapping = {token: idx for idx, token in enumerate(vocabulary)}
    result = [0.0] * len(vocabulary)
    index = mapping.get(value, None)
    if index is not None:
        result[index] = 1.0
    return result


def _angle_to_sin_cos(angle: float | None) -> tuple[float, float]:
    if angle is None:
        return 0.0, 1.0
    radians = math.radians(float(angle))
    return math.sin(radians), math.cos(radians)


def _safe_float(value: float | int | None, default: float = 0.0) -> float:
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _residue_for(state: State, res_idx: int) -> Residue:
    try:
        return state.residues[res_idx]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Residue index {res_idx} not found in state") from exc


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _local_clash_count(residue: Residue, neighbours: Iterable[Residue]) -> float:
    threshold = 1.5
    count = 0
    for atom in residue.atoms:
        ax, ay, az = atom.xyz
        for other_res in neighbours:
            if other_res.id == residue.id:
                continue
            for other_atom in other_res.atoms:
                if _distance((ax, ay, az), other_atom.xyz) < threshold:
                    count += 1
    return float(count)


def _neighbour_residues(state: State, residue: Residue) -> List[Residue]:
    points = [atom.xyz for atom in residue.atoms]
    neighbour_ids = state.grid.nearby_residues(points, radius=8.0)
    return [state.residues[nid] for nid in neighbour_ids if nid in state.residues]


def _neighbour_density(residue: Residue, neighbours: Iterable[Residue]) -> float:
    ca = next((atom.xyz for atom in residue.atoms if atom.id[1] == "CA"), None)
    if ca is None:
        ca = residue.atoms[0].xyz if residue.atoms else (0.0, 0.0, 0.0)
    radius = 6.0
    total = 0
    for other in neighbours:
        for atom in other.atoms:
            if _distance(ca, atom.xyz) <= radius:
                total += 1
    return float(total)


def _contact_kept_ratio(
    residue: Residue,
    neighbours: Mapping[int, Residue],
    target_contacts: Sequence[int] | None,
) -> float:
    if not target_contacts:
        return 1.0
    kept = 0
    total = 0
    ca = next((atom.xyz for atom in residue.atoms if atom.id[1] == "CA"), None)
    if ca is None:
        ca = residue.atoms[0].xyz if residue.atoms else (0.0, 0.0, 0.0)
    for contact_idx in target_contacts:
        total += 1
        neighbour = neighbours.get(contact_idx)
        if neighbour is None:
            continue
        other_ca = next((atom.xyz for atom in neighbour.atoms if atom.id[1] == "CA"), None)
        if other_ca is None and neighbour.atoms:
            other_ca = neighbour.atoms[0].xyz
        if other_ca is None:
            continue
        if _distance(ca, other_ca) <= 8.0:
            kept += 1
    if total == 0:
        return 1.0
    ratio = kept / total
    if ratio < 0.0:
        ratio = 0.0
    if ratio > 1.0:
        ratio = 1.0
    return float(ratio)


def _move_type_one_hot(candidate_move: Mapping[str, object]) -> tuple[list[float], float, float, int]:
    move_type = [0.0] * len(MOVE_TYPES)
    move = candidate_move.get("type", "").lower()
    delta = _safe_float(candidate_move.get("delta"))
    delta_phi = _safe_float(candidate_move.get("delta_phi"))
    delta_psi = _safe_float(candidate_move.get("delta_psi"))

    if move == "phi":
        if delta == 0.0:
            delta = delta_phi
        index = 0 if delta >= 0 else 1
        move_type[index] = 1.0
        delta_phi = delta
        delta_psi = 0.0
        rotamer_id = 0
    elif move == "psi":
        if delta == 0.0:
            delta = delta_psi
        index = 2 if delta >= 0 else 3
        move_type[index] = 1.0
        delta_phi = 0.0
        delta_psi = delta
        rotamer_id = 0
    elif move == "rotamer":
        move_type[4] = 1.0
        rotamer_id = int(candidate_move.get("rotamer_id", 0))
        delta_phi = 0.0
        delta_psi = 0.0
    else:
        move_type[4] = 1.0
        rotamer_id = int(candidate_move.get("rotamer_id", 0))
    rotamer_id = max(0, min(2, rotamer_id))
    return move_type, delta_phi, delta_psi, rotamer_id


def _extract_ss_label(candidate_move: Mapping[str, object], key: str) -> str:
    label = str(candidate_move.get(key, "C")) if candidate_move.get(key) is not None else "C"
    label = label.strip().upper() if label else "C"
    if label not in SS_STATES:
        return "C"
    return label


def build_features(
    state: State,
    res_idx: int,
    candidate_move: Mapping[str, object] | MutableMapping[str, object],
) -> FeatureBundle:
    """Return structured ΔScore features for the provided candidate move.

    Parameters
    ----------
    state:
        The current FoldIt server state containing residues, grids and caches.
    res_idx:
        Residue index around which the candidate move is evaluated.
    candidate_move:
        Mapping describing the proposed move. The dictionary is expected to
        contain at least ``{"type": "phi"|"psi"|"rotamer"}`` and may optionally
        provide ``delta``, ``current_phi``, ``current_psi``, ``chi_angles``,
        secondary structure hints, and other auxiliary metadata.
    """

    residue = _residue_for(state, res_idx)
    neighbours = _neighbour_residues(state, residue)
    neighbour_map = {res.id: res for res in neighbours}

    # Use the scoring surface to obtain local penalties (clash/rama/rotamer/etc.).
    neighbour_ids = {res.id for res in neighbours}
    terms = compute_per_residue_terms(state, res_idx, neighbour_ids)

    residue_name = residue.name.strip().upper() if residue.name else "UNK"
    aa_one_hot = _one_hot(residue_name, AA_ORDER)

    current_phi = candidate_move.get("current_phi")
    current_psi = candidate_move.get("current_psi")

    phi_sin, phi_cos = _angle_to_sin_cos(current_phi)
    psi_sin, psi_cos = _angle_to_sin_cos(current_psi)

    chi_angles = candidate_move.get("chi_angles")
    chi_values: Sequence[float] = tuple(float(angle) for angle in chi_angles) if chi_angles else ()
    chi_sin_cos: List[float] = []
    for idx in range(4):
        angle = chi_values[idx] if idx < len(chi_values) else None
        sin_val, cos_val = _angle_to_sin_cos(angle)
        chi_sin_cos.extend([sin_val, cos_val])

    local_clash_count = _local_clash_count(residue, neighbours)
    local_clash_energy = float(max(0.0, terms.get("clash", 0.0)))
    rama_pen = float(max(0.0, terms.get("rama", 0.0)))
    rotamer_pen = float(max(0.0, terms.get("rotamer", 0.0)))

    ss_state_label = _extract_ss_label(candidate_move, "ss_state")
    target_ss_label = _extract_ss_label(candidate_move, "target_ss")
    ss_state_one_hot = _one_hot(ss_state_label, SS_STATES)
    target_ss_one_hot = _one_hot(target_ss_label, SS_STATES)
    ss_mismatch = 1.0 if ss_state_label != target_ss_label else 0.0

    density = _neighbour_density(residue, neighbours)
    contact_ratio = _contact_kept_ratio(residue, neighbour_map, candidate_move.get("target_contacts"))

    hbond_count = candidate_move.get("hbond_count")
    if hbond_count is None:
        hbond_term = terms.get("hbond", 0.0)
        hbond_count = int(round(hbond_term)) if hbond_term > 0.0 else 0
    hbond_count = int(max(0, hbond_count))

    move_type_one_hot, delta_phi, delta_psi, rotamer_id = _move_type_one_hot(candidate_move)

    predicted_deltas = candidate_move.get("predicted_deltas_hint") or ()
    predicted: List[float] = []
    for idx in range(4):
        predicted.append(_safe_float(predicted_deltas[idx] if idx < len(predicted_deltas) else 0.0))

    fields: Dict[str, object] = {
        "res_idx": int(res_idx),
        "aa_one_hot": aa_one_hot,
        "is_gly": 1.0 if residue_name == "GLY" else 0.0,
        "is_pro": 1.0 if residue_name == "PRO" else 0.0,
        "phi_sin": phi_sin,
        "phi_cos": phi_cos,
        "psi_sin": psi_sin,
        "psi_cos": psi_cos,
        "chi_sin_cos": chi_sin_cos,
        "local_clash_count": local_clash_count,
        "local_clash_energy": local_clash_energy,
        "rama_pen": rama_pen,
        "rotamer_pen": rotamer_pen,
        "ss_state_one_hot": ss_state_one_hot,
        "target_ss_one_hot": target_ss_one_hot,
        "ss_mismatch": ss_mismatch,
        "neighbor_density": density,
        "contact_kept_ratio": contact_ratio,
        "hbond_count": hbond_count,
        "move_type_one_hot": move_type_one_hot,
        "delta_phi": delta_phi,
        "delta_psi": delta_psi,
        "rotamer_id": rotamer_id,
        "predicted_deltas_hint": predicted,
    }

    vector = np.array(
        [
            float(fields["res_idx"]),
            *fields["aa_one_hot"],
            float(fields["is_gly"]),
            float(fields["is_pro"]),
            float(fields["phi_sin"]),
            float(fields["phi_cos"]),
            float(fields["psi_sin"]),
            float(fields["psi_cos"]),
            *fields["chi_sin_cos"],
            float(fields["local_clash_count"]),
            float(fields["local_clash_energy"]),
            float(fields["rama_pen"]),
            float(fields["rotamer_pen"]),
            *fields["ss_state_one_hot"],
            *fields["target_ss_one_hot"],
            float(fields["ss_mismatch"]),
            float(fields["neighbor_density"]),
            float(fields["contact_kept_ratio"]),
            float(fields["hbond_count"]),
            *fields["move_type_one_hot"],
            float(fields["delta_phi"]),
            float(fields["delta_psi"]),
            float(fields["rotamer_id"]),
            *fields["predicted_deltas_hint"],
        ],
        dtype=np.float32,
    )

    return FeatureBundle(fields=fields, vector=vector)


__all__ = ["FeatureBundle", "build_features"]
