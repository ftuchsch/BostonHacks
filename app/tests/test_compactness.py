"""Tests for the compactness (radius of gyration) penalty."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.server.main import app


client = TestClient(app)


def _score(atoms: list[dict[str, float | str]]) -> dict:
    response = client.post("/api/score", json={"atoms": atoms})
    assert response.status_code == 200
    return response.json()


def test_compactness_penalty_tracks_radius_of_gyration():
    """Spreading atoms out should increase the compactness penalty."""

    atom_count = 4
    target = 2.2 * (atom_count ** (1.0 / 3.0))
    base_positions = [
        (target, 0.0, 0.0),
        (-target, 0.0, 0.0),
        (0.0, target, 0.0),
        (0.0, -target, 0.0),
    ]

    def _atoms(scale: float) -> list[dict[str, float | str]]:
        return [
            {
                "element": "C",
                "x": scale * x,
                "y": scale * y,
                "z": scale * z,
            }
            for x, y, z in base_positions
        ]

    balanced = _score(_atoms(1.0))
    compressed = _score(_atoms(0.8))
    spread = _score(_atoms(1.5))

    assert balanced["terms"]["compact"] < compressed["terms"]["compact"]
    assert compressed["terms"]["compact"] < spread["terms"]["compact"]

    assert balanced["score"] > compressed["score"]
    assert compressed["score"] > spread["score"]
