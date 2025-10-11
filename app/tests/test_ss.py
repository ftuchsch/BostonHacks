"""Tests for the secondary structure mismatch term."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.server.main import app


client = TestClient(app)


def _helix_residues(phi_values: list[float]) -> list[dict[str, object]]:
    residues: list[dict[str, object]] = []
    for idx, phi in enumerate(phi_values):
        residue = {
            "index": idx,
            "type": "ALA",
            "chi_angles": [],
            "phi": phi,
            "psi": -45.0,
            "n": {"x": float(idx), "y": -1.0, "z": 0.0},
            "h": {"x": float(idx), "y": 0.0, "z": 0.0},
        }
        if idx >= 4:
            residue["o"] = {"x": float(idx - 4), "y": 1.0, "z": 0.0}
        else:
            residue["o"] = {"x": float(idx + 4), "y": 1.0, "z": 0.0}
        residues.append(residue)
    return residues


def _score_for_phi(phi_values: list[float]) -> dict:
    payload = {
        "atoms": [],
        "residues": _helix_residues(phi_values),
        "target_ss": "H" * len(phi_values),
    }
    response = client.post("/api/score", json=payload)
    assert response.status_code == 200
    return response.json()


def test_helix_break_increases_mismatch_penalty() -> None:
    """Perturbing a helix residue should increase the SS mismatch penalty."""

    intact = _score_for_phi([-60.0] * 8)
    broken = _score_for_phi([-60.0, -60.0, -60.0, 20.0, -60.0, -60.0, -60.0, -60.0])

    assert intact["terms"]["ss"] == 0.0
    assert broken["terms"]["ss"] > intact["terms"]["ss"]
    assert broken["score"] < intact["score"]

    per_residue = {entry["i"]: entry for entry in broken["per_residue"]}
    assert per_residue[3]["ss"] > 0.0
