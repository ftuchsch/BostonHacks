"""Module providing a process-wide scoring state."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, List, Tuple

if __package__:
    from .levels import load_level
    from .score_math import SCORE_WEIGHTS
    from .state import State
    from .submissions import build_state
else:  # pragma: no cover - allows running ``uvicorn main:app`` from this directory
    from levels import load_level
    from score_math import SCORE_WEIGHTS
    from state import State
    from submissions import build_state

_STATE: Optional[State] = None
_DEFAULT_LEVEL_ID = os.getenv("FOLDIT_DEFAULT_LEVEL", "level_0001")


def _resolve_start_coords(url: str) -> Optional[Path]:
    clean = url.lstrip("/")
    root = Path(__file__).resolve().parents[2]
    public_dir = root / "app" / "frontend" / "public"
    path = (public_dir / clean).resolve()
    try:
        path.relative_to(public_dir)
    except ValueError:
        return None
    return path if path.exists() else None


def _load_coords_from_file(path: Path, expected_residues: int) -> Optional[List[Tuple[float, float, float]]]:
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    residues = payload.get("residues") if isinstance(payload, dict) else None
    if not isinstance(residues, list):
        return None

    coords: List[Tuple[float, float, float]] = []
    for entry in residues:
        if not isinstance(entry, dict):
            return None
        atoms = entry.get("atoms")
        ca = entry.get("coords")
        def _get_atom(name: str):
            if isinstance(atoms, list):
                for atom in atoms:
                    if isinstance(atom, dict) and atom.get("name", "").upper() == name:
                        coord = atom.get("coords")
                        if isinstance(coord, list) and len(coord) >= 3:
                            return float(coord[0]), float(coord[1]), float(coord[2])
            return None

        xyz_n = _get_atom("N")
        xyz_ca = _get_atom("CA")
        xyz_c = _get_atom("C")

        if xyz_ca is None and isinstance(ca, list) and len(ca) >= 3:
            xyz_ca = float(ca[0]), float(ca[1]), float(ca[2])

        if xyz_n is None or xyz_ca is None or xyz_c is None:
            return None

        coords.extend([xyz_n, xyz_ca, xyz_c])

    if expected_residues and len(coords) != expected_residues * 3:
        return None
    return coords


def _load_default_state() -> State:
    """Initialise the global state with a default level footprint."""

    sequence = "ACDEFGHIKLMNPQRSTVWY"
    coords: Optional[List[Tuple[float, float, float]]] = None

    try:
        level, _ = load_level(_DEFAULT_LEVEL_ID)
        sequence = level.sequence
        path = _resolve_start_coords(level.start_coords_url)
        if path is not None:
            coords = _load_coords_from_file(path, len(sequence))
    except Exception:
        coords = None

    if coords is None:
        # Fallback to a simple linear backbone if assets are unavailable.
        step = 4.31
        n_ca = 1.45
        ca_c = 1.53
        coords = []
        for index in range(len(sequence)):
            origin = index * step
            coords.append((origin, 0.0, 0.0))
            coords.append((origin + n_ca, 0.0, 0.0))
            coords.append((origin + n_ca + ca_c, 0.0, 0.0))

    return build_state(sequence, coords)


def set_state(state: State) -> None:
    """Replace the global scoring state (used primarily in tests)."""

    global _STATE
    _STATE = state


def get_state() -> State:
    """Return the active global scoring state, initialising if necessary."""

    global _STATE
    if _STATE is None:
        try:
            _STATE = _load_default_state()
        except Exception:
            _STATE = State.from_residues([], weights=dict(SCORE_WEIGHTS))
    return _STATE


__all__ = ["get_state", "set_state"]
