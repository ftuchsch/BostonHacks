"""Module providing a process-wide scoring state."""

from __future__ import annotations

from typing import Optional

from app.server.score_math import SCORE_WEIGHTS
from app.server.state import State

_STATE: Optional[State] = None


def set_state(state: State) -> None:
    """Replace the global scoring state (used primarily in tests)."""

    global _STATE
    _STATE = state


def get_state() -> State:
    """Return the active global scoring state, initialising if necessary."""

    global _STATE
    if _STATE is None:
        _STATE = State.from_residues([], weights=dict(SCORE_WEIGHTS))
    return _STATE


__all__ = ["get_state", "set_state"]

