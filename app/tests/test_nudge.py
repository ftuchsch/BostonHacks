"""Tests for the S3.1 heuristic nudge implementation."""

from __future__ import annotations

from app.server.nudge import suggest_nudge
from app.server.score_math import SCORE_WEIGHTS
from app.server.state import Atom, Residue, State
from app.server.stateful import set_state


def _build_clashing_state() -> State:
    residues = []
    # Two residues positioned very close to each other to induce a clash.
    residues.append(
        Residue(
            id=0,
            name="GLY",
            atoms=[
                Atom((0, "N"), (0.0, 0.0, 0.0)),
                Atom((0, "CA"), (1.2, 0.0, 0.0)),
                Atom((0, "C"), (2.4, 0.0, 0.0)),
            ],
        )
    )
    residues.append(
        Residue(
            id=1,
            name="GLY",
            atoms=[
                Atom((1, "N"), (0.4, 0.0, 0.0)),
                Atom((1, "CA"), (1.6, 0.0, 0.0)),
                Atom((1, "C"), (2.8, 0.0, 0.0)),
            ],
        )
    )
    return State.from_residues(residues, weights=dict(SCORE_WEIGHTS))


def test_nudge_reduces_clash_energy():
    state = _build_clashing_state()
    set_state(state)

    result = suggest_nudge(state)

    assert result["res_idx"] in {0, 1}
    assert result["expected_delta_score"] > 0
    clash_delta = result["term_deltas"].get("clash")
    assert clash_delta is not None and clash_delta < 0
