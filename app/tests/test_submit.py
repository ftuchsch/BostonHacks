"""Tests covering the submission endpoint and geometry validation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import json
import math

import pytest
from fastapi.testclient import TestClient

from app.server.main import app
from app.server.submissions import ensure_payload_shapes, rescore


def _linear_backbone(sequence: str) -> list[list[float]]:
    coords: list[list[float]] = []
    step = 4.31
    n_ca = 1.45
    ca_c = 1.53
    for idx in range(len(sequence)):
        origin = idx * step
        n = [origin, 0.0, 0.0]
        ca = [origin + n_ca, 0.0, 0.0]
        c = [origin + n_ca + ca_c, 0.0, 0.0]
        coords.extend([n, ca, c])
    return coords


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("FOLDIT_SUBMISSIONS_DIR", str(tmp_path))
    from app.server import submissions

    monkeypatch.setattr(
        submissions,
        "_utcnow",
        lambda: datetime(2025, 10, 11, 18, 5, 23, tzinfo=timezone.utc),
    )
    return TestClient(app)


def test_submit_success_persists_and_rescores(client: TestClient, tmp_path: Path) -> None:
    level_sequence = "MKVIFQLAAERDKYKQLVEMAEQL"
    coords = _linear_backbone(level_sequence)

    response = client.post(
        "/api/submit",
        json={
            "level_id": "level_0001",
            "sequence": level_sequence,
            "coords": coords,
            "elapsed_ms": 51842,
            "player_name": "Felix",
            "client_version": "web-0.1.0",
        },
    )
    assert response.status_code == 201
    payload = response.json()

    normalised = ensure_payload_shapes(level_sequence, coords)
    expected = rescore(level_sequence, normalised)
    assert math.isclose(payload["score"], expected["score"], rel_tol=1e-9)
    assert payload["rank"] == 1
    assert payload["entries"] == 1

    storage = tmp_path / "level_0001.jsonl"
    assert storage.exists()
    lines = storage.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    stored = json.loads(lines[0])
    assert stored["player_name"] == "Felix"
    assert stored["score"] == pytest.approx(expected["score"])
    assert stored["checksum"].startswith("sha256:")


def test_submit_invalid_geometry_returns_400(client: TestClient) -> None:
    sequence = "MKVIFQLAAERDKYKQLVEMAEQL"
    coords = _linear_backbone(sequence)
    coords[1][0] += 1.2  # make N-CA distance too large

    response = client.post(
        "/api/submit",
        json={"level_id": "level_0001", "sequence": sequence, "coords": coords},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_geometry"
    assert any("N-CA" in message for message in detail["errors"])


def test_submit_unknown_level(client: TestClient) -> None:
    sequence = "MKVIFQLAAERDKYKQLVEMAEQL"
    coords = _linear_backbone(sequence)

    response = client.post(
        "/api/submit",
        json={"level_id": "missing", "sequence": sequence, "coords": coords},
    )
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "level_not_found"

