"""Unit tests for the ΔScore feature extractor."""

from __future__ import annotations

import math

from app.server.features import build_features
from app.server.score_math import SCORE_WEIGHTS
from app.server.state import Atom, Residue, State


def _mk_state() -> State:
    residues = []
    for idx in range(3):
        base = float(idx) * 4.0
        atoms = [
            Atom((idx, "N"), (base, 0.0, 0.0)),
            Atom((idx, "CA"), (base + 1.2, 0.5, 0.0)),
            Atom((idx, "C"), (base + 2.2, 1.0, 0.0)),
            Atom((idx, "O"), (base + 2.2, 1.0, 1.0)),
        ]
        name = "GLY" if idx == 1 else "SER"
        residues.append(Residue(id=idx, name=name, atoms=atoms))
    return State.from_residues(residues, weights=dict(SCORE_WEIGHTS))


def test_feature_shapes_and_ranges() -> None:
    state = _mk_state()
    candidate = {
        "type": "phi",
        "delta": 5.0,
        "current_phi": -60.0,
        "current_psi": 135.0,
        "chi_angles": [60.0, -60.0],
        "ss_state": "H",
        "target_ss": "E",
        "target_contacts": [1, 2],
        "predicted_deltas_hint": [0.25, -0.5, 1.0, 0.0],
        "hbond_count": 2,
    }

    bundle = build_features(state, 1, candidate)
    fields = bundle.fields
    vector = bundle.vector

    assert fields["res_idx"] == 1
    assert len(fields["aa_one_hot"]) == 20
    assert math.isclose(sum(fields["aa_one_hot"]), 1.0, abs_tol=1e-6)
    assert fields["is_gly"] == 1.0
    assert fields["is_pro"] == 0.0
    assert abs(fields["phi_sin"]) <= 1.0 and abs(fields["phi_cos"]) <= 1.0
    assert abs(fields["psi_sin"]) <= 1.0 and abs(fields["psi_cos"]) <= 1.0
    assert len(fields["chi_sin_cos"]) == 8
    assert all(-1.0 <= value <= 1.0 for value in fields["chi_sin_cos"])
    assert fields["local_clash_count"] >= 0.0
    assert fields["local_clash_energy"] >= 0.0
    assert fields["rama_pen"] >= 0.0
    assert fields["rotamer_pen"] >= 0.0
    assert len(fields["ss_state_one_hot"]) == 3
    assert len(fields["target_ss_one_hot"]) == 3
    assert fields["ss_mismatch"] == 1.0
    assert fields["neighbor_density"] >= 0.0
    assert 0.0 <= fields["contact_kept_ratio"] <= 1.0
    assert fields["hbond_count"] >= 0
    assert len(fields["move_type_one_hot"]) == 5
    assert math.isclose(sum(fields["move_type_one_hot"]), 1.0, abs_tol=1e-6)
    assert fields["delta_phi"] == 5.0
    assert fields["delta_psi"] == 0.0
    assert fields["rotamer_id"] == 0
    assert len(fields["predicted_deltas_hint"]) == 4
    assert getattr(bundle.vector, "shape", (len(vector),)) == (61,)
    assert not any(math.isnan(value) for value in vector)


def test_rotamer_move_one_hot_encoding() -> None:
    state = _mk_state()
    candidate = {
        "type": "rotamer",
        "rotamer_id": 2,
        "current_phi": 10.0,
        "current_psi": -30.0,
        "chi_angles": [180.0, 60.0, -60.0, 45.0],
        "ss_state": "C",
        "target_ss": "C",
    }

    bundle = build_features(state, 0, candidate)
    fields = bundle.fields

    assert fields["is_gly"] == 0.0
    assert fields["is_pro"] == 0.0
    assert fields["move_type_one_hot"] == [0.0, 0.0, 0.0, 0.0, 1.0]
    assert fields["delta_phi"] == 0.0
    assert fields["delta_psi"] == 0.0
    assert fields["rotamer_id"] == 2
    assert fields["ss_mismatch"] == 0.0
    assert all(-1.0 <= value <= 1.0 for value in fields["chi_sin_cos"])
