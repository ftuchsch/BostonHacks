# Task Board

## Epics
1. **3D & Controls (Front‑End)**
2. **Scoring Engine (Back‑End)**
3. **AI Nudge (Heuristic → Model)**
4. **Levels + Leaderboard**
5. **Polish (Tutorial, Replays, Deploy)**

---

## Stories & Tasks

### 1) 3D & Controls
- **S1.1** Three.js scene + load PDB (Acceptance: renders sample in 60 FPS).
- **S1.2** Residue selection & highlight (Acceptance: click selects; index shown).
- **S1.3** φ/ψ rotation UI + Web Worker bridge (Acceptance: moving slider updates coords and invokes `/score`).
- **S1.4** Rotamer dropdown (Acceptance: switch top‑2/3 rotamers visually).
- **S1.5** Heatmap overlay (Acceptance: per‑res colors reflect penalties).

### 2) Scoring Engine
- **S2.1** Spatial grid (cells 4–5 Å) (Acceptance: neighbor queries <1 ms on 100 aa).
- **S2.2** Clash term (Acceptance: unit tests with simple overlaps).
- **S2.3** Rama penalty (Acceptance: lookups + interpolation + tests).
- **S2.4** Rotamer penalty (Acceptance: per‑type thresholds + tests).
- **S2.5** SS mismatch + DSSP‑lite (Acceptance: detect helix/strand in mini examples).
- **S2.6** Compactness (Rg or contacts) (Acceptance: tests pass).
- **S2.7** H‑bond bonus (Acceptance: geometry thresholds tested).
- **S2.8** Final score aggregator + cache (Acceptance: per‑res arrays match length N).

### 3) AI Nudge
- **S3.1** Heuristic move sampler (±5/±10 φ/ψ; top‑2 rotamers).
- **S3.2** Local rescore + argmax (Acceptance: returns a move with ΔScore>0 on fixture).
- **S3.3** Feature extractor (per **03_FEATURE_DICT.md**).
- **S3.4** Train LightGBM (synthetic data) (Acceptance: MAE < 1.0 on val).
- **S3.5** Model inference in `/nudge` + SHAP tooltip (optional).

### 4) Levels + Leaderboard
- **S4.1** Level JSON loader (Acceptance: schema validated).
- **S4.2** Server re‑score on submit (Acceptance: diff between client and server ≤ 1e‑6).
- **S4.3** Supabase tables + `GET /leaderboard` (Acceptance: entries sorted and paginated).
- **S4.4** Replays (store coord history as gzip JSON).

### 5) Polish & Deploy
- **S5.1** Tutorial popovers.
- **S5.2** Landing & Level Select pages.
- **S5.3** Vercel (front) + Render/Fly (FastAPI).
- **S5.4** README + demo script.

---

## Definition of Done
- All acceptance tests in `07_ACCEPTANCE_TESTS.md` pass.
- Lighthouse perf > 80 on main pages.
- Demo script runs in < 2 minutes end‑to‑end.
