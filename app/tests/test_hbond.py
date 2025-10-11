"""Tests for the hydrogen bond bonus term."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.server.main import app
from app.server.scoring import HBOND_GAMMA


client = TestClient(app)


def _residues(acceptor_y: float) -> list[dict[str, object]]:
    return [
        {
            "index": 0,
            "type": "ALA",
            "chi_angles": [],
            "n": {"x": 0.0, "y": 0.0, "z": 0.0},
            "h": {"x": 0.0, "y": 1.0, "z": 0.0},
        },
        {
            "index": 1,
            "type": "ALA",
            "chi_angles": [],
            "o": {"x": 0.0, "y": acceptor_y, "z": 0.0},
        },
    ]


def _score(acceptor_y: float) -> dict:
    payload = {
        "atoms": [],
        "residues": _residues(acceptor_y),
    }
    response = client.post("/api/score", json=payload)
    assert response.status_code == 200
    return response.json()


def test_hbond_bonus_applied_when_geometry_matches() -> None:
    """Moving the acceptor into range should grant the hydrogen bond bonus."""

    broken = _score(4.5)
    formed = _score(2.8)

    assert broken["terms"]["hbond"] == 0.0
    assert formed["terms"]["hbond"] == pytest.approx(HBOND_GAMMA)
    assert formed["score"] == pytest.approx(
        broken["score"] + HBOND_GAMMA
    )

    per_residue = {entry["i"]: entry for entry in formed["per_residue"]}
    assert per_residue[0]["hbond"] == pytest.approx(HBOND_GAMMA / 2)
    assert per_residue[1]["hbond"] == pytest.approx(HBOND_GAMMA / 2)
