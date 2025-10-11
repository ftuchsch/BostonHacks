"""Routes handling submission recording and leaderboard queries."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.server.levels import LevelNotFoundError, LevelValidationError, load_level
from app.server.submissions import (
    SubmissionStorageError,
    ensure_payload_shapes,
    make_submission_entry,
    persist_submission,
    rescore,
    sanitise_client_version,
    sanitise_player_name,
    sort_entries,
    validate_elapsed_ms,
    validate_geometry,
)

router = APIRouter(prefix="/api", tags=["submit"])


class SubmitRequest(BaseModel):
    level_id: str = Field(..., min_length=1)
    sequence: str = Field(..., min_length=1)
    coords: List[List[float]]
    elapsed_ms: int | None = Field(default=None, ge=0)
    player_name: str | None = None
    client_version: str | None = None


class SubmitResponse(BaseModel):
    score: float
    terms: dict[str, float]
    rank: int
    entries: int


class LeaderboardItem(BaseModel):
    rank: int
    player_name: str
    score: float
    elapsed_ms: int | None = None
    ts: str


class LeaderboardResponse(BaseModel):
    level_id: str
    items: List[LeaderboardItem]
    total_entries: int


@router.post("/submit", response_model=SubmitResponse, status_code=201)
async def submit_structure(request: SubmitRequest, http_request: Request) -> SubmitResponse:
    try:
        level, _ = load_level(request.level_id)
    except LevelNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "level_not_found", "id": request.level_id},
        )
    except LevelValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "level_invalid", "details": exc.details},
        ) from exc

    if request.sequence != level.sequence:
        raise HTTPException(
            status_code=400,
            detail={"code": "sequence_mismatch", "message": "sequence does not match level"},
        )

    try:
        coords = ensure_payload_shapes(request.sequence, request.coords)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_payload", "message": str(exc)}) from exc

    geometry_errors = validate_geometry(request.sequence, coords)
    if geometry_errors:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_geometry", "errors": geometry_errors[:5]},
        )

    elapsed_ms = validate_elapsed_ms(request.elapsed_ms)

    score_result = rescore(request.sequence, coords)

    player_name = sanitise_player_name(request.player_name)
    client_version = sanitise_client_version(request.client_version)

    entry = make_submission_entry(
        level_id=request.level_id,
        player_name=player_name,
        score_value=score_result["score"],
        terms=score_result["terms"],
        elapsed_ms=elapsed_ms,
        client_version=client_version,
        coords=coords,
    )

    try:
        rank, total = persist_submission(request.level_id, entry)
    except SubmissionStorageError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "submission_persist_failed", "message": str(exc)},
        ) from exc

    return SubmitResponse(
        score=score_result["score"],
        terms=score_result["terms"],
        rank=rank,
        entries=total,
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def leaderboard(
    level_id: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> LeaderboardResponse:
    try:
        load_level(level_id)
    except LevelNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "level_not_found", "id": level_id},
        )
    except LevelValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "level_invalid", "details": exc.details},
        ) from exc

    from app.server.submissions import path_for_level, read_entries  # local import to avoid cycle

    path = path_for_level(level_id)
    entries = read_entries(path)
    sorted_entries = sort_entries(entries)
    sliced = sorted_entries[offset : offset + limit]

    items: List[LeaderboardItem] = []
    for idx, entry in enumerate(sliced, start=offset + 1):
        items.append(
            LeaderboardItem(
                rank=idx,
                player_name=str(entry.get("player_name", "Anonymous")),
                score=float(entry.get("score", 0.0)),
                elapsed_ms=int(entry["elapsed_ms"]) if entry.get("elapsed_ms") is not None else None,
                ts=str(entry.get("ts", "")),
            )
        )

    return LeaderboardResponse(level_id=level_id, items=items, total_entries=len(entries))


__all__ = [
    "LeaderboardItem",
    "LeaderboardResponse",
    "SubmitRequest",
    "SubmitResponse",
    "router",
]

