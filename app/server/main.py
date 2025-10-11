"""FastAPI entry point for the FoldIt prototype server."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

if __package__:
    from .api import router as api_router
    from .routes_levels import router as levels_router
else:  # pragma: no cover - allows running ``uvicorn main:app`` from this directory
    from api import router as api_router
    from routes_levels import router as levels_router

from app.server.nudge import suggest_nudge
from app.server.score import initialise_weights
from app.server.stateful import get_state

app = FastAPI(title="FoldIt API", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(levels_router)
app.include_router(api_router)

BASE_PREFIX = "/api"


@app.post(f"{BASE_PREFIX}/nudge")
async def nudge() -> JSONResponse:
    """Return a heuristic nudge suggestion based on the current state."""
    state = get_state()
    initialise_weights(state)
    payload = suggest_nudge(state)
    return JSONResponse(payload)


@app.post(f"{BASE_PREFIX}/minimize")
async def minimize() -> JSONResponse:
    """Return a placeholder minimization response."""
    payload = {"new_atoms": [], "energy": 0.0}
    return JSONResponse(payload)


@app.post(f"{BASE_PREFIX}/submit")
async def submit() -> JSONResponse:
    """Return a placeholder submission acknowledgement."""
    payload = {"status": "received", "score": 0.0}
    return JSONResponse(payload)


@app.get(f"{BASE_PREFIX}/leaderboard")
async def leaderboard(level_id: str | None = None) -> JSONResponse:
    """Return a placeholder leaderboard."""
    payload = {"level_id": level_id, "entries": []}
    return JSONResponse(payload)
