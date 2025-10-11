"""Module providing a process-wide scoring state."""

from __future__ import annotations

import os
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


def _generate_backbone(sequence: str) -> List[Tuple[float, float, float]]:
    """Return a simple linear backbone for the provided sequence length."""

    coords: List[Tuple[float, float, float]] = []
    step = 4.31
    n_ca = 1.45
    ca_c = 1.53
    for index in range(len(sequence)):
        origin = index * step
        coords.append((origin, 0.0, 0.0))
        coords.append((origin + n_ca, 0.0, 0.0))
        coords.append((origin + n_ca + ca_c, 0.0, 0.0))
    return coords


def _load_default_state() -> State:
    """Initialise the global state with a default level footprint."""

    try:
        level, _ = load_level(_DEFAULT_LEVEL_ID)
        sequence = level.sequence
    except Exception:
        sequence = "ACDEFGHIKLMNPQRSTVWY"
    coords = _generate_backbone(sequence)
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
