# ΔScore Model — Feature Dictionary

Each sample corresponds to evaluating a **candidate micro‑move** around residue *i*.

| Name | Type/Shape | Range/Encoding | How computed |
|---|---|---|---|
| res_idx | int | [0..N-1] | Residue index |
| aa_type | one‑hot(20) | {0,1} | Residue type |
| is_gly, is_pro | bool | 0/1 | Flags for Rama table |
| phi_sin, phi_cos | float | [-1,1] | sin/cos of current φ |
| psi_sin, psi_cos | float | [-1,1] | sin/cos of current ψ |
| chi_k_sin/cos | float×(≤4×2) | [-1,1] | For up to 4 χ angles |
| local_clash_count | float | ≥0 | # pairs with overlap >0 within 8 Å (pre‑move) |
| local_clash_energy | float | ≥0 | Clash energy over neighborhood |
| rama_pen | float | ≥0 | Current Rama penalty at (φ,ψ) |
| rotamer_pen | float | ≥0 | Current rotamer penalty |
| ss_state | one‑hot(3) | H/E/C | Current DSSP‑lite |
| target_ss | one‑hot(3) | H/E/C | Level mask at i |
| ss_mismatch | bool | 0/1 | (ss_state != target_ss) |
| neighbor_density | float | ≥0 | Atoms within 6 Å of CA_i |
| contact_kept_ratio | float | [0,1] | Fraction of target contacts for i still ≤8 Å |
| hbond_count | int | ≥0 | # H‑bonds involving residue i |
| move_type | one‑hot(5) | φ+5, φ−5, ψ+5, ψ−5, rotamer_k | Candidate move category |
| delta_phi, delta_psi | float | degrees | 0 if not used |
| rotamer_id | int | {0,1,2} | Proposed rotamer index |
| predicted_deltas_hint | float×4 | any | Optional heuristic deltas for terms |
| **label: delta_score** | float | any | (True post‑move Score − pre‑move Score) |

**Note:** When using model inference to *rank* candidates, verify the winner by recomputing the true local score once.
