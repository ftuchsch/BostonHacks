# FoldIt Reimagined — Web (MVP + AI Coach)

**Purpose:** Revive the “folding puzzle” experience in a browser with fast, explainable scoring and an AI-assisted “Nudge” that proposes small geometry edits. Optimized for hackathon demoability and recruiter appeal.

## 1) Problem & Goals
- **Problem:** Full Rosetta/OpenMM scoring is too heavy for real-time, and older citizen‑science apps require downloads and long feedback loops.
- **Goal:** A **web game** for short proteins (40–120 aa) where users adjust backbone (φ/ψ) and side‑chain rotamers and see a **live score**. An **AI coach** highlights problematic residues and suggests micro‑moves that improve score.
- **Non‑negotiables:** 
  - Live score updated per edit with **<20–30 ms** latency for ~100 aa.
  - **Local recomputation** (only neighborhood around edited residue).
  - “**AI Nudge**” that returns in **<200 ms** (heuristic or ΔScore model).
  - Server **re‑scores** on submit for anti‑cheat.

## 2) Core Gameplay Loop
1. Load a level (sequence + start coords + target SS/contacts).
2. Player selects a residue and rotates **φ** or **ψ** (±5°/±10°) or flips a **rotamer**.
3. **Score** updates instantly; **heatmap** shows worst residues.
4. Click **AI Nudge** → best local micro‑move applied; UI shows term deltas.
5. Submit solution → leaderboard.

## 3) Scoring (physics‑lite, explainable)
- **Clash:** soft overlap penalty on nearby atoms.
- **Ramachandran:** −log p(φ,ψ) (separate tables: Gly/Pro/general).
- **Rotamer:** penalty outside top‑k bins for residue type.
- **Secondary Structure (SS):** mismatch vs level’s target SS (DSSP‑lite).
- **Compactness:** radius of gyration target or target contact preservation.
- **H‑bond bonus:** donor–acceptor geometry threshold.

**Final:** `Score = 1000 - [w1*Clash + w2*Rama + w3*Rotamer + w4*SS + w5*Compact] + w6*HBond`

## 4) AI Components
- **Heatmap:** per‑residue penalties normalized to 0–1.
- **AI Nudge (Day 1):** Try a capped set of micro‑moves around worst residues; pick best ΔScore.
- **AI Nudge (Day 2):** Train **LightGBM** ΔScore regressor on synthetic perturbations; rank moves without evaluating them all. Optional **SHAP** to show feature drivers.

## 5) Architecture
- **Frontend (Next.js/React + Three.js):** 3D view, controls, heatmap, HUD, hotkeys. Heavy math runs in a **Web Worker**.
- **Backend (FastAPI + NumPy + scikit‑learn/LightGBM):** scoring, nudge selection, optional OpenMM minimization; server re‑score on submit.
- **DB (Supabase/Postgres):** users, levels, submissions, replays.

## 6) Latency/Perf Targets
- Edit → score: **<30 ms** on 100 aa.
- AI Nudge: **<200 ms** (evaluate ≤200 candidates or use ΔScore model).
- Minimize button: 0.5–3 s (server, optional).

## 7) Deliverables for Hackathon
- 3–5 levels, leaderboard, replays (JSON of coord history), tutorial popovers, landing page.
- Clean demo script with 90‑second flow.

## 8) Success Criteria
- Judges can play with zero install (web link), see live score, observe “AI Nudge” improvement + explanation, and submit to leaderboard with server verification.
