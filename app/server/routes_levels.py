"""FastAPI routes exposing the levels catalogue."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from .levels import (
    LevelDataError,
    LevelNotFoundError,
    LevelValidationError,
    load_level,
    load_level_summaries,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/api/levels", tags=["levels"])


@router.get("", response_model=None)
async def list_levels(request: Request) -> Response:
    """Return the catalogue of level summaries."""

    try:
        summaries, etag = load_level_summaries()
    except LevelValidationError as exc:  # pragma: no cover - defensive logging
        LOGGER.exception("Level index failed validation: %s", exc.details)
        return JSONResponse(
            status_code=500,
            content={"error": "levels_index_unavailable"},
        )
    except LevelDataError:
        LOGGER.exception("Level index could not be loaded")
        return JSONResponse(
            status_code=500,
            content={"error": "levels_index_unavailable"},
        )

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    payload: List[dict] = [summary.model_dump(exclude_none=True) for summary in summaries]
    response = JSONResponse(content=payload)
    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["ETag"] = etag
    return response


@router.get("/{level_id}", response_model=None)
async def get_level(level_id: str, request: Request) -> Response:
    """Return the full level definition for a specific level."""

    try:
        level, etag = load_level(level_id)
    except LevelNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"error": "level_not_found", "id": level_id},
        )
    except LevelValidationError as exc:
        LOGGER.exception("Level %s failed schema validation", level_id)
        return JSONResponse(
            status_code=422,
            content={"error": "schema_validation_failed", "details": exc.details},
        )
    except LevelDataError:  # pragma: no cover - defensive logging
        LOGGER.exception("Unexpected error while loading level %s", level_id)
        return JSONResponse(
            status_code=500,
            content={"error": "level_load_failed", "id": level_id},
        )

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    response = JSONResponse(content=level.model_dump(exclude_none=True))
    response.headers["Cache-Control"] = "public, max-age=0"
    response.headers["ETag"] = etag
    return response


__all__ = ["router"]
