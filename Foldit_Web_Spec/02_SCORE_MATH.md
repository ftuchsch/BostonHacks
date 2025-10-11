# Score Math — Terms, Formulas, Constants

All terms are computed **locally** for residues within an **8 Å** neighborhood of edited atoms, using a spatial grid (cell size ≈ 4–5 Å). Distances in Å, angles in degrees.

## 1) Steric Clash (dominant term)
Let `r_i` be VdW radius of atom i, `d_ij` distance between atoms i and j, and `τ` a softness margin (e.g., 0.2 Å). Exclude bonded (1–2) and optionally 1–3 pairs.
\[
\text{Clash}=\sum_{i<j} \max\!\big(0,\; (r_i+r_j+\tau) - d_{ij}\big)^2
\]
- **Cutoff:** only pairs with `d_ij < 8 Å`.
- **Constants:** VdW (Å): C=1.7, N=1.55, O=1.52, S=1.8, H=1.1 (tunable).

## 2) Ramachandran Penalty
\[
\text{Rama} = -\log \big(p(\phi,\psi)\big) \;\; \text{(clipped to } [0, R_{\max}] \text{)}
\]
- Separate 2D histograms for **Gly**, **Pro**, and **General** residues (coarse 10° bins).
- Use bilinear interpolation between bin centers; `R_max` ≈ 10.

## 3) Rotamer Penalty
- Precompute top‑k rotamer bins per residue type.
- Penalty 0 if χ angles within a top bin; otherwise `Rotamer = α_rot * min_Δχ^2`.
- Constants: `α_rot ≈ 0.02` per degree² (tune).

## 4) Secondary Structure (SS) Mismatch
- Each level has a **target SS** mask `SS* ∈ {H,E,C}^N`.
- Current SS via **DSSP‑lite**: φ/ψ ranges + H‑bond geometry.
- Penalty per residue if `SS != SS*`: `SS_pen = w_H` for helix, `w_E` for strand, `w_C` for coil (typically `w_H = w_E = 1`, `w_C = 0`).

## 5) Compactness
Choose one:
- **Radius of gyration target:** `Rg_pen = α_rg * (Rg - Rg_target)^2`, where `Rg_target ≈ 2.2 * N^(1/3)` Å.
- **Contact preservation:** for a set of target contacts `(i,j)`, add `β_contact` if `d_CA(i,j) > 8 Å`.

## 6) H‑bond Bonus
For donor D–H and acceptor A:
- Distance `d( H , A ) < 2.5–3.0 Å` and angle `∠D–H–A > 120°` → bonus `γ_hb`.
- Count distinct bonds; cap per residue.

## 7) Final Score
\[
\boxed{\text{Score} = 1000 - (w_1 \text{Clash} + w_2 \text{Rama} + w_3 \text{Rotamer} + w_4 \text{SS} + w_5 \text{Compact}) + w_6 \text{HBond}}
\]
**Default weights:** `w = [1.0, 0.6, 0.4, 0.5, 0.3]`, `w6 = 0.2`. Tweak quickly by eyeballing feel.

## 8) Incremental Update
- Maintain per‑residue term caches.
- When residue `i` moves, recompute only residues with any atom within **8 Å** of any moved atom.

## 9) Worked Mini‑Example
- Suppose a move reduces two overlaps from 0.8 Å→0.2 Å: ΔClash ≈ (0.8²−0.2²)*2 = 1.2.
- φ/ψ moves into a higher‑probability bin: ΔRama ≈ −2.5.
- Rotamer becomes valid: ΔRotamer ≈ −4.0.
- SS unchanged: ΔSS = 0.
- H‑bond formed: +1 bonus.
**ΔScore ≈ −(1.0*−1.2 + 0.6*−2.5 + 0.4*−4.0) + 0.2*(+1) ≈ +4.0**
