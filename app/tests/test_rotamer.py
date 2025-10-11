"""Tests for the rotamer penalty implementation."""

from fastapi.testclient import TestClient

from app.server.main import app


client = TestClient(app)


def _score(chi_angle: float) -> dict:
    response = client.post(
        "/api/score",
        json={
            "atoms": [],
            "residues": [
                {"index": 0, "type": "SER", "chi_angles": [chi_angle]},
            ],
        },
    )
    assert response.status_code == 200
    return response.json()


def test_rotamer_within_top_bin_has_negligible_penalty() -> None:
    result = _score(60.0)
    assert result["terms"]["rotamer"] < 1.0e-3
    assert result["per_residue"][0]["rotamer"] < 1.0e-3


def test_rotamer_far_from_bins_penalised_and_reduces_score() -> None:
    valid = _score(60.0)
    off_rotamer = _score(140.0)

    assert off_rotamer["terms"]["rotamer"] > valid["terms"]["rotamer"]
    assert off_rotamer["per_residue"][0]["rotamer"] == off_rotamer["terms"]["rotamer"]
    assert off_rotamer["score"] < valid["score"]
