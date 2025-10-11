"""API tests for the levels catalogue endpoints."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.server.main import app
from app.server import routes_levels
from app.server.levels import LevelDataError, LevelValidationError

client = TestClient(app)


def test_list_levels_success() -> None:
    response = client.get("/api/levels")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload, "expected at least one level summary"
    entry = payload[0]
    for key in ("id", "name", "difficulty", "length"):
        assert key in entry
    assert "sequence" not in entry
    assert response.headers.get("Cache-Control") == "public, max-age=300"
    assert "ETag" in response.headers


def test_get_level_success() -> None:
    index = client.get("/api/levels").json()
    level_id = index[0]["id"]

    response = client.get(f"/api/levels/{level_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == level_id
    assert len(payload["sequence"]) == payload["length"]
    assert len(payload["target_ss"]) == payload["length"]
    assert set(payload["target_ss"]) <= {"H", "E", "C"}
    assert response.headers.get("Cache-Control") == "public, max-age=0"
    assert "ETag" in response.headers


def test_get_level_not_found() -> None:
    response = client.get("/api/levels/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"error": "level_not_found", "id": "does-not-exist"}


def test_get_level_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_validation(level_id: str) -> Any:  # pragma: no cover - patched
        raise LevelValidationError([{ "msg": "boom" }])

    monkeypatch.setattr(routes_levels, "load_level", _raise_validation)
    response = client.get("/api/levels/level_0001")
    assert response.status_code == 422
    assert response.json() == {
        "error": "schema_validation_failed",
        "details": [{"msg": "boom"}],
    }


def test_list_levels_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_data_error() -> Any:  # pragma: no cover - patched
        raise LevelDataError("oops")

    monkeypatch.setattr(routes_levels, "load_level_summaries", _raise_data_error)
    response = client.get("/api/levels")
    assert response.status_code == 500
    assert response.json() == {"error": "levels_index_unavailable"}
