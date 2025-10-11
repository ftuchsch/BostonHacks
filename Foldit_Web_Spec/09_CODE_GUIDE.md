# Code Guide

## Directory Layout
```
/app
  /frontend (Next.js, TypeScript)
  /server   (FastAPI, Python)
  /infra    (deploy, Dockerfile optional)
  /levels   (JSON + PDB assets)
  /tests    (unit + integration)
```

## Rules
- **Diff‑only edits** for AI assistants: PRs must show unified diffs for changed files only.
- **No new dependencies** without approval in PR.
- **Keep constants** in a single module; reference, don’t copy.
- **Web Worker** for heavy UI computations; never block main thread.
- **Cache per‑residue** terms; recompute only local neighborhoods.

## Style
- **Python:** black, isort, mypy lite; docstrings for public funcs.
- **TS:** strict mode, functional components, hooks only.
- **Commits:** imperative mood, short scope tags (`feat(frontend): residue inspector`).

## Testing
- **Unit:** scoring terms on tiny fixtures.
- **Integration:** end‑to‑end score after a move; API contract tests.
- **Perf:** time budget checks (<30 ms per edit; <200 ms nudge).

## Security/Validation
- Validate geometry: bond lengths, atom counts, element set.
- Re‑score on server for any submitted leaderboard entry.
