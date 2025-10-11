"""Tests for incremental scoring and cache maintenance."""

from __future__ import annotations

import copy
import math

from fastapi.testclient import TestClient

from app.server.main import app
from app.server.score import score_total
from app.server.score_math import SCORE_WEIGHTS
from app.server.state import Atom, Residue, State
from app.server.stateful import set_state


def _mk_mock_state(n_res: int = 30) -> State:
    residues = []
    for i in range(n_res):
        x = (i % 5) * 6.0
        y = ((i // 5) % 3) * 6.0
        z = (i // 15) * 6.0
        atoms = [
            Atom((i, "N"), (x, y, z)),
            Atom((i, "CA"), (x + 1.2, y, z)),
            Atom((i, "C"), (x + 2.2, y, z)),
            Atom((i, "O"), (x + 2.2, y + 1.2, z)),
        ]
        residues.append(Residue(id=i, name="GLY", atoms=atoms))
    return State.from_residues(residues, weights=dict(SCORE_WEIGHTS))


def test_incremental_scoring_via_api():
    state = _mk_mock_state()
    set_state(state)
    client = TestClient(app)

    response = client.post("/api/score", json={"payload": {}})
    assert response.status_code == 200
    data_full = response.json()
    assert isinstance(data_full["score"], float)
    assert len(data_full["per_residue"]) == len(state.residues)
    full_calls = sum(state.stats.term_eval_calls.values())
    assert state.stats.full_passes == 1

    pre_calls = copy.deepcopy(state.stats.term_eval_calls)
    res_idx = 7
    residue = state.residues[res_idx]
    move = {
        "CA": [
            residue.atoms[1].xyz[0] + 0.5,
            residue.atoms[1].xyz[1],
            residue.atoms[1].xyz[2],
        ]
    }

    response_inc = client.post(
        "/api/score",
        json={"payload": {"diff": {"res_idx": res_idx, "move": move}}},
    )
    assert response_inc.status_code == 200
    data_inc = response_inc.json()
    stats_inc = data_inc["stats"]
    assert stats_inc["incremental_passes"] == 1
    added_calls = sum(state.stats.term_eval_calls[key] - pre_calls[key] for key in pre_calls)
    assert added_calls < full_calls

    cloned_residues = []
    for res in state.residues.values():
        atoms = [
            Atom(atom.id, (atom.xyz[0], atom.xyz[1], atom.xyz[2]))
            for atom in res.atoms
        ]
        cloned_residues.append(Residue(id=res.id, name=res.name, atoms=atoms))
    fresh_state = State.from_residues(cloned_residues, weights=dict(SCORE_WEIGHTS))
    full_again = score_total(fresh_state)
    assert math.isclose(data_inc["score"], full_again["score"], abs_tol=1e-6)

