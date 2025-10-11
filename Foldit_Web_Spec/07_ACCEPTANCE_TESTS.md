# Acceptance Tests (Given/When/Then)

## Scoring
- **Given** a 60 aa level and valid coordinates, **when** no residues are selected and no moves applied, **then** `POST /score` returns in ≤50 ms with `score` and `per_residue` arrays of length 60.
- **Given** an edit that reduces two atomic overlaps by ≥0.5 Å each, **when** I rescore, **then** the `clash` term decreases and `score` increases.
- **Given** a residue with out‑of‑range φ/ψ, **when** I rotate into a high‑probability Rama bin, **then** `rama` penalty drops (≥1.0).

## AI Nudge
- **Given** a conformation with a single severe clash, **when** I call `POST /nudge`, **then** a move is suggested on a nearby residue and `expected_delta_score > 0`.
- **Given** ΔScore model present, **when** `/nudge` is called, **then** heuristic fallback is not used (flag present) and latency ≤200 ms.

## Performance
- **Given** a 100 aa structure, **when** I adjust φ by 10° on one residue, **then** edit→score roundtrip is ≤30 ms on sample machine (local mode).

## Submit/Leaderboard
- **Given** a final state, **when** I call `POST /submit`, **then** the server recomputes score, validates geometry, stores replay, and `GET /leaderboard` shows the new entry.

## Geometry Validations
- **Given** a state with stretched bond (>2× typical length), **when** scoring, **then** server returns `400 invalid geometry`.
