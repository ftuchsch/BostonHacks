"""Tests covering leaderboard sorting, ties, and pagination."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server.main import app


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("FOLDIT_SUBMISSIONS_DIR", str(tmp_path))
    return TestClient(app)


def _write_entries(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, separators=(",", ":"), sort_keys=True))
            handle.write("\n")


def test_leaderboard_sorting_and_pagination(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "level_0001.jsonl"
    base_entry = {
        "terms": {"clash": 1.0},
        "level_id": "level_0001",
        "checksum": "sha256:abc",
    }
    entries = [
        {
            **base_entry,
            "player_name": "Carol",
            "score": 205.0,
            "elapsed_ms": 2000,
            "ts": "2025-10-11T10:00:00Z",
            "checksum": "sha256:carol",
        },
        {
            **base_entry,
            "player_name": "Bob",
            "score": 200.0,
            "elapsed_ms": 1500,
            "ts": "2025-10-11T09:00:00Z",
            "checksum": "sha256:bob",
        },
        {
            **base_entry,
            "player_name": "Alice",
            "score": 200.0,
            "elapsed_ms": 2500,
            "ts": "2025-10-11T08:00:00Z",
            "checksum": "sha256:alice",
        },
        {
            **base_entry,
            "player_name": "Dave",
            "score": 190.0,
            "elapsed_ms": None,
            "ts": "2025-10-11T07:00:00Z",
            "checksum": "sha256:dave",
        },
    ]
    _write_entries(path, entries)

    response = client.get("/api/leaderboard", params={"level_id": "level_0001", "limit": 3})
    assert response.status_code == 200
    payload = response.json()

    assert payload["total_entries"] == 4
    ranks = [item["player_name"] for item in payload["items"]]
    assert ranks == ["Dave", "Bob", "Alice"]
    assert payload["items"][1]["rank"] == 2

    response_offset = client.get(
        "/api/leaderboard",
        params={"level_id": "level_0001", "limit": 2, "offset": 1},
    )
    assert response_offset.status_code == 200
    payload_offset = response_offset.json()
    assert [item["player_name"] for item in payload_offset["items"]] == ["Bob", "Alice"]


def test_leaderboard_unknown_level(client: TestClient) -> None:
    response = client.get("/api/leaderboard", params={"level_id": "missing"})
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "level_not_found"
