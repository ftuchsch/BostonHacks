"""Tests for the clash scoring term."""
from fastapi.testclient import TestClient

from app.server.main import app


client = TestClient(app)


def _score(atoms: list[dict[str, float | str]]) -> dict:
    response = client.post("/api/score", json={"atoms": atoms})
    assert response.status_code == 200
    return response.json()


def test_clash_decreases_with_distance():
    """Reducing overlap should lower clash energy and increase total score."""

    overlapping = [
        {"element": "C", "x": 0.0, "y": 0.0, "z": 0.0},
        {"element": "C", "x": 0.1, "y": 0.0, "z": 0.0},
    ]
    spaced = [
        {"element": "C", "x": 0.0, "y": 0.0, "z": 0.0},
        {"element": "C", "x": 3.0, "y": 0.0, "z": 0.0},
    ]

    overlapping_score = _score(overlapping)
    spaced_score = _score(spaced)

    assert overlapping_score["terms"]["clash"] > spaced_score["terms"]["clash"]
    assert spaced_score["score"] > overlapping_score["score"]
