"""State containers and neighbour indexing for incremental scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set
import math

Vec3 = Tuple[float, float, float]
AtomID = Tuple[int, str]


@dataclass
class Atom:
    """Minimal atom representation tracked in the global state."""

    id: AtomID
    xyz: Vec3


@dataclass
class Residue:
    """Residue record storing atoms and identifiers."""

    id: int
    name: str
    atoms: List[Atom]


@dataclass
class PerResScore:
    """Cached per-residue score contributions."""

    terms: Dict[str, float]
    total: float
    version: int = 0


@dataclass
class NeighborGrid:
    """Voxel grid used to find nearby residues quickly."""

    voxel: float = 4.0
    vox2res: Dict[Tuple[int, int, int], Set[int]] = field(default_factory=dict)
    res2vox: Dict[int, Set[Tuple[int, int, int]]] = field(default_factory=dict)

    def _to_key(self, p: Vec3) -> Tuple[int, int, int]:
        v = self.voxel
        return (
            int(math.floor(p[0] / v)),
            int(math.floor(p[1] / v)),
            int(math.floor(p[2] / v)),
        )

    def index_residue(self, res: Residue) -> None:
        voxset = self.res2vox.setdefault(res.id, set())
        for atom in res.atoms:
            key = self._to_key(atom.xyz)
            voxset.add(key)
            self.vox2res.setdefault(key, set()).add(res.id)

    def clear_residue(self, res_id: int) -> None:
        for key in self.res2vox.get(res_id, set()):
            bucket = self.vox2res.get(key)
            if bucket:
                bucket.discard(res_id)
                if not bucket:
                    self.vox2res.pop(key, None)
        self.res2vox.pop(res_id, None)

    def nearby_residues(self, xyzs: List[Vec3], radius: float) -> Set[int]:
        v = self.voxel
        out: Set[int] = set()
        rng = int(math.ceil(radius / v))
        for point in xyzs:
            cx, cy, cz = self._to_key(point)
            for dx in range(-rng, rng + 1):
                for dy in range(-rng, rng + 1):
                    for dz in range(-rng, rng + 1):
                        ids = self.vox2res.get((cx + dx, cy + dy, cz + dz))
                        if ids:
                            out |= ids
        return out


@dataclass
class ScoreStats:
    """Instrumentation counters to validate incremental recomputation."""

    term_eval_calls: Dict[str, int] = field(
        default_factory=lambda: {
            "clash": 0,
            "rama": 0,
            "rotamer": 0,
            "ss": 0,
            "compact": 0,
            "hbond": 0,
        }
    )
    full_passes: int = 0
    incremental_passes: int = 0

    def bump(self, term: str, n: int = 1) -> None:
        self.term_eval_calls[term] = self.term_eval_calls.get(term, 0) + n


@dataclass
class State:
    """Container for residues, neighbour grid, and score cache."""

    residues: Dict[int, Residue]
    atom_index: Dict[AtomID, Vec3]
    grid: NeighborGrid
    per_res_cache: Dict[int, PerResScore]
    weights: Dict[str, float]
    stats: ScoreStats = field(default_factory=ScoreStats)

    @classmethod
    def from_residues(cls, residues: List[Residue], weights: Dict[str, float]) -> "State":
        atom_index: Dict[AtomID, Vec3] = {}
        grid = NeighborGrid()
        resmap: Dict[int, Residue] = {}
        for residue in residues:
            resmap[residue.id] = residue
            for atom in residue.atoms:
                atom_index[atom.id] = atom.xyz
            grid.index_residue(residue)
        return cls(
            residues=resmap,
            atom_index=atom_index,
            grid=grid,
            per_res_cache={},
            weights=weights,
        )

    def update_residue_coords(self, res_id: int, new_xyz: Dict[str, Vec3]) -> None:
        """Update atom coordinates for a residue and refresh the neighbour grid."""

        residue = self.residues[res_id]
        self.grid.clear_residue(res_id)
        for atom in residue.atoms:
            name = atom.id[1]
            if name in new_xyz:
                atom.xyz = new_xyz[name]
                self.atom_index[atom.id] = atom.xyz
        self.grid.index_residue(residue)

