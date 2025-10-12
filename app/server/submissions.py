"""Helpers for validating and storing submission records."""

from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, List, Mapping, MutableMapping, Sequence

from fastapi import HTTPException

if __package__:
    from .score import initialise_weights, score_total
    from .score_math import SCORE_WEIGHTS
    from .state import Atom, Residue, State
else:  # pragma: no cover - allows running ``uvicorn main:app`` from this directory
    from score import initialise_weights, score_total
    from score_math import SCORE_WEIGHTS
    from state import Atom, Residue, State

Coords = List[tuple[float, float, float]]

SUBMISSIONS_DIR_ENV = "FOLDIT_SUBMISSIONS_DIR"
DEFAULT_SUBMISSIONS_DIR = Path(__file__).resolve().parents[1] / "data" / "submissions"

BOND_LIMITS: Mapping[tuple[str, str], tuple[float, float]] = {
    ("N", "CA"): (1.20, 1.60),
    ("CA", "C"): (1.20, 1.70),
    ("C", "N_next"): (0.80, 2.00),
}

MIN_INTRA_RES_DISTANCE = 0.6

_LEVEL_LOCKS: MutableMapping[str, threading.Lock] = {}
_LOCK_GUARD = threading.Lock()


class SubmissionStorageError(RuntimeError):
    """Raised when submission persistence fails."""


def _get_base_dir() -> Path:
    override = os.getenv(SUBMISSIONS_DIR_ENV)
    return Path(override) if override else DEFAULT_SUBMISSIONS_DIR


def path_for_level(level_id: str) -> Path:
    base = _get_base_dir()
    return base / f"{level_id}.jsonl"


def _ensure_dir(path: Path) -> None:
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)


def _get_lock(level_id: str) -> threading.Lock:
    with _LOCK_GUARD:
        lock = _LEVEL_LOCKS.get(level_id)
        if lock is None:
            lock = threading.Lock()
            _LEVEL_LOCKS[level_id] = lock
        return lock


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def normalise_coords(coords: Sequence[Sequence[float]]) -> Coords:
    """Convert an iterable of triplets to finite float tuples."""

    normalised: Coords = []
    for index, point in enumerate(coords):
        if len(point) != 3:
            raise ValueError(f"coordinate {index} must contain exactly 3 values")
        triple = []
        for component in point:
            try:
                value = float(component)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                raise ValueError(f"coordinate {index} component {component!r} is not numeric") from exc
            if not math.isfinite(value):
                raise ValueError(f"coordinate {index} contains a non-finite value")
            triple.append(value)
        normalised.append((triple[0], triple[1], triple[2]))
    return normalised


def ensure_payload_shapes(sequence: str, coords: Sequence[Sequence[float]]) -> Coords:
    """Validate that the sequence and coordinate array lengths match."""

    if not sequence:
        raise ValueError("sequence must not be empty")

    expected = len(sequence) * 3
    coords_list = list(coords)
    if len(coords_list) != expected:
        raise ValueError(
            f"coords length mismatch: expected {expected} points for {len(sequence)} residues"
        )
    return normalise_coords(coords_list)


def _atom_index(res_idx: int, atom_name: str) -> int | None:
    mapping = {"N": 0, "CA": 1, "C": 2}
    offset = mapping.get(atom_name)
    if offset is None:
        return None
    return res_idx * 3 + offset


def _dist(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def validate_backbone_bonds(sequence: str, coords: Coords) -> List[str]:
    errors: List[str] = []
    for res_idx in range(len(sequence)):
        n_idx = _atom_index(res_idx, "N")
        ca_idx = _atom_index(res_idx, "CA")
        c_idx = _atom_index(res_idx, "C")
        if n_idx is None or ca_idx is None or c_idx is None:
            errors.append(f"missing backbone at residue {res_idx}")
            continue
        n = coords[n_idx]
        ca = coords[ca_idx]
        c = coords[c_idx]
        d_n_ca = _dist(n, ca)
        d_ca_c = _dist(ca, c)
        low, high = BOND_LIMITS[("N", "CA")]
        if not (low <= d_n_ca <= high):
            errors.append(f"N-CA out of range @ {res_idx}: {d_n_ca:.2f}")
        low, high = BOND_LIMITS[("CA", "C")]
        if not (low <= d_ca_c <= high):
            errors.append(f"CA-C out of range @ {res_idx}: {d_ca_c:.2f}")
        if res_idx + 1 < len(sequence):
            n_next_idx = _atom_index(res_idx + 1, "N")
            if n_next_idx is not None:
                d_c_n = _dist(c, coords[n_next_idx])
                low, high = BOND_LIMITS[("C", "N_next")]
                if not (low <= d_c_n <= high):
                    errors.append(f"C-N(next) out of range @ {res_idx}->{res_idx + 1}: {d_c_n:.2f}")
    return errors


def validate_min_distance(sequence: str, coords: Coords) -> List[str]:
    errors: List[str] = []
    for res_idx in range(len(sequence)):
        start = res_idx * 3
        atoms = coords[start : start + 3]
        if len(atoms) < 3:
            errors.append(f"missing backbone at residue {res_idx}")
            continue
        for i in range(3):
            for j in range(i + 1, 3):
                dist = _dist(atoms[i], atoms[j])
                if dist < MIN_INTRA_RES_DISTANCE:
                    errors.append(
                        f"intra-residue distance too small @ {res_idx}: {dist:.2f}"
                    )
    return errors


def validate_geometry(sequence: str, coords: Coords) -> List[str]:
    errors = validate_backbone_bonds(sequence, coords)
    errors.extend(validate_min_distance(sequence, coords))
    return errors


_ONE_LETTER_TO_THREE = {
    "A": "ALA",
    "R": "ARG",
    "N": "ASN",
    "D": "ASP",
    "C": "CYS",
    "Q": "GLN",
    "E": "GLU",
    "G": "GLY",
    "H": "HIS",
    "I": "ILE",
    "L": "LEU",
    "K": "LYS",
    "M": "MET",
    "F": "PHE",
    "P": "PRO",
    "S": "SER",
    "T": "THR",
    "W": "TRP",
    "Y": "TYR",
    "V": "VAL",
}


def build_state(sequence: str, coords: Coords) -> State:
    residues: List[Residue] = []
    for res_idx, code in enumerate(sequence):
        start = res_idx * 3
        n_xyz, ca_xyz, c_xyz = coords[start : start + 3]
        atoms = [
            Atom((res_idx, "N"), n_xyz),
            Atom((res_idx, "CA"), ca_xyz),
            Atom((res_idx, "C"), c_xyz),
        ]
        name = _ONE_LETTER_TO_THREE.get(code.upper(), "UNK")
        residues.append(Residue(id=res_idx, name=name, atoms=atoms))
    state = State.from_residues(residues, weights=dict(SCORE_WEIGHTS))
    initialise_weights(state)
    return state


def compute_checksum(coords: Coords) -> str:
    hasher = hashlib.sha256()
    for point in coords:
        for value in point:
            hasher.update(struct.pack("!d", value))
    return f"sha256:{hasher.hexdigest()}"


def append_jsonl(path: Path, entry: Mapping[str, object]) -> None:
    _ensure_dir(path)
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, separators=(",", ":"), sort_keys=True))
            handle.write("\n")
    except OSError as exc:  # pragma: no cover - exercised in error handling tests
        raise SubmissionStorageError(str(exc)) from exc


def read_entries(path: Path) -> List[dict]:
    if not path.exists():
        return []
    entries: List[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:  # pragma: no cover - ignore corrupt lines
                continue
    return entries


def sort_entries(entries: Iterable[Mapping[str, object]]) -> List[Mapping[str, object]]:
    def sort_key(item: Mapping[str, object]):
        score = float(item.get("score", 0.0))
        elapsed = item.get("elapsed_ms")
        elapsed_val = float("inf") if elapsed is None else float(elapsed)
        ts = str(item.get("ts", ""))
        return (score, elapsed_val, ts)

    return sorted(entries, key=sort_key)


def compute_rank(entries: List[Mapping[str, object]], target: Mapping[str, object]) -> int:
    checksum = target.get("checksum")
    timestamp = target.get("ts")
    player_name = target.get("player_name")
    score_value = target.get("score")
    for index, item in enumerate(sort_entries(entries), start=1):
        if (
            item.get("checksum") == checksum
            and item.get("ts") == timestamp
            and item.get("player_name") == player_name
            and item.get("score") == score_value
        ):
            return index
    raise ValueError("submitted entry not found in ranking list")


def persist_submission(level_id: str, entry: Mapping[str, object]) -> tuple[int, int]:
    path = path_for_level(level_id)
    lock = _get_lock(level_id)
    with lock:
        entries = read_entries(path)
        append_jsonl(path, entry)
        entries.append(dict(entry))
        rank = compute_rank(entries, entry)
        total = len(entries)
    return rank, total


def make_submission_entry(
    *,
    level_id: str,
    player_name: str,
    score_value: float,
    terms: Mapping[str, float],
    elapsed_ms: int | None,
    client_version: str | None,
    coords: Coords,
    ip_hash: str | None = None,
) -> dict:
    timestamp = _isoformat(_utcnow())
    entry = {
        "ts": timestamp,
        "level_id": level_id,
        "player_name": player_name,
        "score": float(score_value),
        "terms": dict(terms),
        "elapsed_ms": elapsed_ms,
        "client_version": client_version,
        "checksum": compute_checksum(coords),
    }
    if ip_hash:
        entry["ip_hash"] = ip_hash
    return entry


def rescore(sequence: str, coords: Coords) -> dict:
    state = build_state(sequence, coords)
    return score_total(state)


def sanitise_player_name(name: str | None) -> str:
    if not name:
        return "Anonymous"
    candidate = name.strip()
    if not candidate:
        return "Anonymous"
    return candidate[:64]


def sanitise_client_version(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    return candidate[:64] if candidate else None


def validate_elapsed_ms(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 0:
        raise HTTPException(status_code=400, detail={"code": "invalid_elapsed", "message": "elapsed_ms must be non-negative"})
    return value


__all__ = [
    "SubmissionStorageError",
    "build_state",
    "compute_rank",
    "ensure_payload_shapes",
    "make_submission_entry",
    "normalise_coords",
    "path_for_level",
    "persist_submission",
    "read_entries",
    "rescore",
    "sort_entries",
    "sanitise_client_version",
    "sanitise_player_name",
    "validate_geometry",
    "validate_elapsed_ms",
]
