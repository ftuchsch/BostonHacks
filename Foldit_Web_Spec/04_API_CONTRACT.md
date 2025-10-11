# API Contract (FastAPI)

Base URL: `/api`

## POST /score
Compute score for the given state (diff or full coords).

**Request (example)**
```json
{
  "sequence": "ACDEFGHIK",
  "atoms": [{ "id":1, "res":0, "name":"N", "x":0.0, "y":1.2, "z":0.0, "elem":"N" }, ...],
  "target_ss": "CCHHHHHHC",
  "target_contacts": [[5,28],[6,27]]
}
```
**Response**
```json
{
  "score": 942.3,
  "terms": {"clash": 22.4, "rama": 8.6, "rotamer": 3.0, "ss": 4.0, "compact": 2.1, "hbond": 1.0},
  "per_residue": [
    {"i":0, "clash":1.0,"rama":0.5,"rotamer":0.0,"ss":0.0,"compact":0.1,"hbond":0.0},
    {"i":1, "clash":3.4, ...}
  ]
}
```

## POST /nudge
Return the best micro‑move suggestion for the current state.

**Response**
```json
{
  "res_idx": 27,
  "move": {"type": "phi", "delta": -10},
  "expected_delta_score": 4.2,
  "explanation": {"clash": -3.8, "rama": -1.2, "rotamer": 0.0, "ss": 0.0, "hbond": +1.0}
}
```

## POST /minimize (optional)
Runs short OpenMM minimization (server).

**Response**
```json
{"new_atoms": [...], "energy": -123.4}
```

## GET /levels
List levels (id, name, length).

## GET /levels/{id}
Fetch level spec: sequence, start coords, target_ss, target_contacts, tips.

## POST /submit
Submit final coordinates for re‑score and leaderboard write.
- Server recomputes score, validates geometry, and stores replay.

## GET /leaderboard?level_id=...
Top scores, fastest times, fewest moves.

## Errors
- `400` invalid geometry (bond lengths, impossible angles)
- `422` schema errors
- `429` rate limited
- `500` server error

## Auth
- Hackathon: none or simple API key. Production: JWT or Supabase auth.
