"""FastAPI entry point for the FoldIt prototype server."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="FoldIt API", openapi_url="/api/openapi.json")

BASE_PREFIX = "/api"


@app.post(f"{BASE_PREFIX}/score")
async def score() -> JSONResponse:
    """Return a placeholder score response."""
    payload = {
        "score": 0.0,
        "terms": {
            "clash": 0.0,
            "rama": 0.0,
            "rotamer": 0.0,
            "ss": 0.0,
            "compact": 0.0,
            "hbond": 0.0,
        },
        "per_residue": [],
    }
    return JSONResponse(payload)


@app.post(f"{BASE_PREFIX}/nudge")
async def nudge() -> JSONResponse:
    """Return a placeholder nudge suggestion."""
    payload = {
        "res_idx": 0,
        "move": {"type": "phi", "delta": 0},
        "expected_delta_score": 0.0,
        "explanation": {
            "clash": 0.0,
            "rama": 0.0,
            "rotamer": 0.0,
            "ss": 0.0,
            "hbond": 0.0,
        },
    }
    return JSONResponse(payload)


@app.post(f"{BASE_PREFIX}/minimize")
async def minimize() -> JSONResponse:
    """Return a placeholder minimization response."""
    payload = {"new_atoms": [], "energy": 0.0}
    return JSONResponse(payload)


@app.get(f"{BASE_PREFIX}/levels")
async def list_levels() -> JSONResponse:
    """Return a placeholder list of levels."""
    payload = {"levels": []}
    return JSONResponse(payload)


@app.get(f"{BASE_PREFIX}/levels/{{level_id}}")
async def get_level(level_id: str) -> JSONResponse:
    """Return a placeholder level specification."""
    payload = {
        "id": level_id,
        "sequence": "",
        "start_atoms": [],
        "target_ss": "",
        "target_contacts": [],
        "tips": [],
    }
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
