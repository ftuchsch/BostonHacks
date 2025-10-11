"""Scoring utilities for the FoldIt prototype server."""
from __future__ import annotations

from collections.abc import Iterable
from math import acos, degrees, exp, floor, log, sqrt
from typing import Any, Mapping, Sequence

# Van der Waals radii in Ångström pulled from the score spec (02_SCORE_MATH.md §1).
VAN_DER_WAALS_RADII: Mapping[str, float] = {
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "S": 1.80,
    "H": 1.10,
}

RAMA_BIN_SIZE = 10.0
RAMA_BIN_COUNT = 36
RAMA_MAX_PENALTY = 10.0
RAMA_MIN_PROBABILITY = 1.0e-6

# Bin centres for the coarse Ramachandran histograms (10° bins spanning [-180, 180)).
RAMA_BIN_CENTERS: tuple[float, ...] = tuple(
    -180.0 + (index + 0.5) * RAMA_BIN_SIZE for index in range(RAMA_BIN_COUNT)
)

# Synthetic Ramachandran histograms approximating the common α/β basins.
# Values are probabilities capped to [RAMA_MIN_PROBABILITY, 1.0]. The precise
# shapes are less important than having realistic hotspots for interpolation
# during unit tests.
_RAMA_COMPONENTS: Mapping[str, tuple[tuple[float, float, float, float, float], ...]] = {
    "general": (
        (-60.0, -40.0, 22.0, 18.0, 0.55),  # right-handed α-helix basin
        (-120.0, 130.0, 25.0, 22.0, 0.35),  # β-sheet basin
        (60.0, 40.0, 18.0, 20.0, 0.20),  # left-handed α region
    ),
    "gly": (
        (-80.0, 0.0, 25.0, 22.0, 0.45),
        (80.0, 0.0, 25.0, 20.0, 0.45),
        (-150.0, 150.0, 28.0, 24.0, 0.30),
    ),
    "pro": (
        (-65.0, 140.0, 18.0, 18.0, 0.60),
        (-80.0, -35.0, 16.0, 20.0, 0.25),
    ),
}


def _build_ramachandran_table(
    components: tuple[tuple[float, float, float, float, float], ...]
) -> tuple[tuple[float, ...], ...]:
    table: list[tuple[float, ...]] = []
    for phi_center in RAMA_BIN_CENTERS:
        row: list[float] = []
        for psi_center in RAMA_BIN_CENTERS:
            probability = RAMA_MIN_PROBABILITY
            for phi0, psi0, sigma_phi, sigma_psi, weight in components:
                d_phi = (phi_center - phi0) / sigma_phi
                d_psi = (psi_center - psi0) / sigma_psi
                exponent = -0.5 * (d_phi * d_phi + d_psi * d_psi)
                probability += weight * exp(exponent)
            row.append(min(probability, 1.0))
        table.append(tuple(row))
    return tuple(table)


RAMACHANDRAN_TABLES: Mapping[str, tuple[tuple[float, ...], ...]] = {
    key: _build_ramachandran_table(components)
    for key, components in _RAMA_COMPONENTS.items()
}

ALPHA_ROT = 0.02
ALPHA_RG = 0.3


def _generate_rotamer_bins(chi_count: int) -> tuple[tuple[tuple[float, ...], tuple[float, ...]], ...]:
    """Return coarse top-rotamer bins for a residue with ``chi_count`` torsions."""

    if chi_count <= 0:
        return ((),)

    centres = (-60.0, 60.0, 180.0)
    width = 35.0

    bins: list[tuple[tuple[float, ...], tuple[float, ...]]] = []
    # The MVP uses a simple tensor product of three canonical centres for each χ
    # angle. This yields 3^n bins which is still tractable for the small n (≤ 4)
    # encountered in protein side chains and matches the "top-k" guidance in the
    # scoring spec. Each bin stores its centres together with a uniform half width
    # (±35°) used to determine whether a χ angle is considered "inside" the bin.
    def _build(current: tuple[float, ...]) -> None:
        if len(current) == chi_count:
            bins.append((current, tuple(width for _ in current)))
            return
        for centre in centres:
            _build((*current, centre))

    _build(())
    return tuple(bins)


def _normalise_residue_key(residue: str) -> str:
    residue = residue.strip().upper()
    if len(residue) == 1:
        return residue
    return residue[:3]


RESIDUE_CHI_COUNT: Mapping[str, int] = {
    "ALA": 0,
    "GLY": 0,
    "SER": 1,
    "CYS": 1,
    "VAL": 1,
    "THR": 1,
    "ASN": 2,
    "ASP": 2,
    "LEU": 2,
    "ILE": 2,
    "HIS": 2,
    "PHE": 2,
    "TYR": 2,
    "TRP": 2,
    "GLN": 3,
    "GLU": 3,
    "MET": 3,
    "LYS": 4,
    "ARG": 4,
    "PRO": 0,
}


ROTAMER_LIBRARY: Mapping[str, tuple[tuple[tuple[float, ...], tuple[float, ...]], ...]] = {
    key: _generate_rotamer_bins(count) for key, count in RESIDUE_CHI_COUNT.items()
}
ROTAMER_LIBRARY = {
    **ROTAMER_LIBRARY,
    "DEFAULT": _generate_rotamer_bins(1),
}


HBOND_MAX_DISTANCE = 3.0
HBOND_MIN_ANGLE = 120.0
HBOND_GAMMA = 1.0
HBOND_RESIDUE_CAP = 2

HELIX_PHI_RANGE = (-90.0, -30.0)
HELIX_PSI_RANGE = (-80.0, -10.0)
HELIX_HBOND_RANGE = (3, 5)

STRAND_PHI_RANGE = (-160.0, -90.0)
STRAND_PSI_RANGE = (90.0, 180.0)

SS_WEIGHTS: Mapping[str, float] = {"H": 1.0, "E": 1.0, "C": 0.0}


__all__ = [
    "clash_energy",
    "compactness_penalty",
    "detect_ss_labels",
    "hbond_bonus",
    "ramachandran_penalty",
    "rotamer_penalty",
]


def _wrap_angle(angle: float) -> float:
    """Wrap an angle into the [-180°, 180°) domain."""

    return ((angle + 180.0) % 360.0) - 180.0


def _interpolation_indices(angle: float) -> tuple[int, int, float]:
    """Return lower/upper bin indices and interpolation weight for an angle."""

    coord = ((angle + 180.0) / RAMA_BIN_SIZE) - 0.5
    lower = floor(coord)
    fraction = coord - lower
    lower_index = lower % RAMA_BIN_COUNT
    upper_index = (lower_index + 1) % RAMA_BIN_COUNT
    return lower_index, upper_index, fraction


def ramachandran_penalty(
    phi: float,
    psi: float,
    *,
    residue_type: str = "general",
) -> float:
    """Compute the Ramachandran penalty for a residue.

    The implementation follows 02_SCORE_MATH.md §2. For the appropriate residue
    type (general, glycine, or proline) a coarse 10°×10° histogram is used and
    bilinear interpolation between bin centres estimates the probability at the
    requested `(φ, ψ)` pair. The penalty is the negative natural logarithm of
    that probability, clipped to ``[0, RAMA_MAX_PENALTY]``.
    """

    key = residue_type.lower()
    try:
        table = RAMACHANDRAN_TABLES[key]
    except KeyError as exc:
        valid = ", ".join(sorted(RAMACHANDRAN_TABLES))
        raise ValueError(
            f"Unknown residue type '{residue_type}' for Ramachandran lookup; "
            f"expected one of {valid}"
        ) from exc

    wrapped_phi = _wrap_angle(float(phi))
    wrapped_psi = _wrap_angle(float(psi))

    phi_lower, phi_upper, phi_weight = _interpolation_indices(wrapped_phi)
    psi_lower, psi_upper, psi_weight = _interpolation_indices(wrapped_psi)

    v00 = table[phi_lower][psi_lower]
    v10 = table[phi_upper][psi_lower]
    v01 = table[phi_lower][psi_upper]
    v11 = table[phi_upper][psi_upper]

    prob = (
        (1.0 - phi_weight) * (1.0 - psi_weight) * v00
        + phi_weight * (1.0 - psi_weight) * v10
        + (1.0 - phi_weight) * psi_weight * v01
        + phi_weight * psi_weight * v11
    )

    prob = max(min(prob, 1.0), RAMA_MIN_PROBABILITY)
    penalty = -log(prob)
    if penalty < 0.0:
        penalty = 0.0
    return min(penalty, RAMA_MAX_PENALTY)


def _get_residue_type(res_idx: int, residue_types: Mapping[int, str] | Iterable[str]) -> str:
    if isinstance(residue_types, Mapping):
        try:
            residue = residue_types[res_idx]
        except KeyError as exc:
            raise ValueError(f"Unknown residue index {res_idx} for rotamer lookup") from exc
    else:
        residue_list = list(residue_types)
        try:
            residue = residue_list[res_idx]
        except IndexError as exc:
            raise ValueError(f"Unknown residue index {res_idx} for rotamer lookup") from exc
    return _normalise_residue_key(residue)


def _get_residue_chis(
    res_idx: int,
    coords: Mapping[int, Iterable[float]] | Iterable[Iterable[float]],
) -> tuple[float, ...]:
    if isinstance(coords, Mapping):
        try:
            chis = coords[res_idx]
        except KeyError as exc:
            raise ValueError(f"Missing χ angles for residue {res_idx}") from exc
    else:
        coord_list = list(coords)
        try:
            chis = coord_list[res_idx]
        except IndexError as exc:
            raise ValueError(f"Missing χ angles for residue {res_idx}") from exc
    return tuple(float(angle) for angle in chis)


def _angle_distance(a: float, b: float) -> float:
    return abs(_wrap_angle(a - b))


def rotamer_penalty(
    res_idx: int,
    coords: Mapping[int, Iterable[float]] | Iterable[Iterable[float]],
    residue_types: Mapping[int, str] | Iterable[str],
) -> float:
    """Return the coarse rotamer penalty for ``res_idx``.

    The function implements the MVP outlined in 02_SCORE_MATH.md §3. It checks the
    χ angles of the provided residue against a small library of "top" rotamer bins
    (tensor-product combinations of gauche+/− and trans states). If all χ angles
    lie within any bin's window the penalty is zero. Otherwise the squared excess
    (beyond the bin widths) is accumulated and scaled by ``ALPHA_ROT``.
    """

    residue_type = _get_residue_type(res_idx, residue_types)
    chi_angles = _get_residue_chis(res_idx, coords)

    chi_count = RESIDUE_CHI_COUNT.get(residue_type, len(chi_angles))
    if chi_count == 0 or not chi_angles:
        return 0.0

    if len(chi_angles) < chi_count:
        raise ValueError(
            f"Residue {res_idx} ({residue_type}) expected {chi_count} χ angles, "
            f"received {len(chi_angles)}"
        )

    bins = ROTAMER_LIBRARY.get(residue_type)
    if not bins:
        bins = ROTAMER_LIBRARY["DEFAULT"]
        chi_count = min(chi_count, len(chi_angles), 1)

    best_excess = float("inf")
    # Use only the number of χ angles that the bin was generated for. Extra angles
    # are ignored for the MVP implementation to keep computation local.
    relevant_angles = chi_angles[:chi_count]
    for centres, widths in bins:
        if len(centres) != len(relevant_angles):
            continue
        excess_sq = 0.0
        for angle, centre, width in zip(relevant_angles, centres, widths):
            delta = _angle_distance(angle, centre)
            if delta <= width:
                continue
            extra = delta - width
            excess_sq += extra * extra
        if excess_sq < best_excess:
            best_excess = excess_sq
            if best_excess == 0.0:
                break

    if best_excess == float("inf"):
        return 0.0
    return ALPHA_ROT * best_excess


def _clamp(value: float, lower: float, upper: float) -> float:
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return sqrt(dx * dx + dy * dy + dz * dz)


def _angle(donor: Sequence[float], hydrogen: Sequence[float], acceptor: Sequence[float]) -> float:
    """Return the D–H–A angle in degrees for three points."""

    # Build vectors pointing from hydrogen towards the donor and acceptor atoms.
    v_d = (donor[0] - hydrogen[0], donor[1] - hydrogen[1], donor[2] - hydrogen[2])
    v_a = (acceptor[0] - hydrogen[0], acceptor[1] - hydrogen[1], acceptor[2] - hydrogen[2])

    dot = v_d[0] * v_a[0] + v_d[1] * v_a[1] + v_d[2] * v_a[2]
    norm_d = sqrt(v_d[0] * v_d[0] + v_d[1] * v_d[1] + v_d[2] * v_d[2])
    norm_a = sqrt(v_a[0] * v_a[0] + v_a[1] * v_a[1] + v_a[2] * v_a[2])

    if norm_d == 0.0 or norm_a == 0.0:
        return 0.0

    cosine = _clamp(dot / (norm_d * norm_a), -1.0, 1.0)
    return degrees(acos(cosine))


def _in_range(value: float, bounds: tuple[float, float]) -> bool:
    lower, upper = bounds
    if lower <= upper:
        return lower <= value <= upper
    return lower <= value or value <= upper


def _coerce_point(point: Any) -> tuple[float, float, float]:
    """Return a ``(x, y, z)`` tuple for various point representations."""

    if isinstance(point, Mapping):
        try:
            return (float(point["x"]), float(point["y"]), float(point["z"]))
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError("Point mapping must contain 'x', 'y' and 'z'") from exc

    if hasattr(point, "x") and hasattr(point, "y") and hasattr(point, "z"):
        return (float(getattr(point, "x")), float(getattr(point, "y")), float(getattr(point, "z")))

    try:
        coords = tuple(float(value) for value in point)
    except TypeError as exc:  # pragma: no cover - defensive guard
        raise ValueError("Point must be an iterable of coordinates") from exc

    if len(coords) != 3:
        raise ValueError("Point coordinate must contain exactly three values")
    return coords


def _prepare_hbond_geometry(
    coords: Iterable[Mapping[str, Any]]
) -> tuple[
    list[dict[str, Any]],
    list[tuple[int, tuple[float, float, float], tuple[float, float, float]]],
    list[tuple[int, tuple[float, float, float]]],
]:
    entries: list[dict[str, Any]] = []
    donors: list[tuple[int, tuple[float, float, float], tuple[float, float, float]]] = []
    acceptors: list[tuple[int, tuple[float, float, float]]] = []

    for item in coords:
        if "index" not in item:
            raise ValueError("Secondary structure entries require an 'index' field")
        index = int(item["index"])
        n = item.get("n")
        h = item.get("h")
        o = item.get("o")
        entry = {
            "index": index,
            "phi": item.get("phi"),
            "psi": item.get("psi"),
            "n": n,
            "h": h,
            "o": o,
        }
        entries.append(entry)

        if n is not None and h is not None:
            donor_point = _coerce_point(n)
            hydrogen_point = _coerce_point(h)
            donors.append((index, donor_point, hydrogen_point))
        if o is not None:
            acceptor_point = _coerce_point(o)
            acceptors.append((index, acceptor_point))

    entries.sort(key=lambda e: e["index"])
    return entries, donors, acceptors


def detect_ss_labels(coords: Iterable[Mapping[str, Any]]) -> str:
    """Return DSSP-lite secondary structure labels for the provided residues."""

    entries, donors, acceptors = _prepare_hbond_geometry(coords)

    if not entries:
        return ""

    hbond_map: dict[int, set[int]] = {entry["index"]: set() for entry in entries}

    for donor_idx, donor_pos, hydrogen_pos in donors:
        for acceptor_idx, acceptor_pos in acceptors:
            if donor_idx == acceptor_idx:
                continue
            distance = _distance(hydrogen_pos, acceptor_pos)
            if distance > HBOND_MAX_DISTANCE:
                continue
            angle = _angle(donor_pos, hydrogen_pos, acceptor_pos)
            if angle < HBOND_MIN_ANGLE:
                continue
            hbond_map.setdefault(donor_idx, set()).add(acceptor_idx)
            hbond_map.setdefault(acceptor_idx, set()).add(donor_idx)

    labels: list[str] = []
    for entry in entries:
        idx = entry["index"]
        phi = entry.get("phi")
        psi = entry.get("psi")
        label = "C"

        if phi is not None and psi is not None:
            phi_f = float(phi)
            psi_f = float(psi)
            partners = hbond_map.get(idx, set())

            if _in_range(phi_f, HELIX_PHI_RANGE) and _in_range(psi_f, HELIX_PSI_RANGE):
                if any(
                    HELIX_HBOND_RANGE[0] <= abs(partner - idx) <= HELIX_HBOND_RANGE[1]
                    for partner in partners
                ):
                    label = "H"
            elif _in_range(phi_f, STRAND_PHI_RANGE) and _in_range(psi_f, STRAND_PSI_RANGE):
                if any(abs(partner - idx) >= 2 for partner in partners):
                    label = "E"

        labels.append(label)

    return "".join(labels)


def hbond_bonus(
    coords: Iterable[Mapping[str, Any]],
    *,
    gamma: float = HBOND_GAMMA,
    per_residue_cap: int = HBOND_RESIDUE_CAP,
) -> tuple[float, dict[int, float]]:
    """Return the hydrogen bond bonus and per-residue contributions."""

    if gamma <= 0.0 or per_residue_cap <= 0:
        return 0.0, {}

    entries, donors, acceptors = _prepare_hbond_geometry(coords)
    if not donors or not acceptors:
        return 0.0, {}

    counts: dict[int, int] = {entry["index"]: 0 for entry in entries}
    contributions: dict[int, float] = {}
    total_bonus = 0.0
    seen_pairs: set[tuple[int, int]] = set()

    for donor_idx, donor_pos, hydrogen_pos in donors:
        for acceptor_idx, acceptor_pos in acceptors:
            if donor_idx == acceptor_idx:
                continue
            key = (min(donor_idx, acceptor_idx), max(donor_idx, acceptor_idx))
            if key in seen_pairs:
                continue
            if counts.get(donor_idx, 0) >= per_residue_cap:
                continue
            if counts.get(acceptor_idx, 0) >= per_residue_cap:
                continue

            distance = _distance(hydrogen_pos, acceptor_pos)
            if distance > HBOND_MAX_DISTANCE:
                continue
            angle = _angle(donor_pos, hydrogen_pos, acceptor_pos)
            if angle < HBOND_MIN_ANGLE:
                continue

            seen_pairs.add(key)
            counts[donor_idx] = counts.get(donor_idx, 0) + 1
            counts[acceptor_idx] = counts.get(acceptor_idx, 0) + 1

            bonus_share = 0.5 * gamma
            contributions[donor_idx] = contributions.get(donor_idx, 0.0) + bonus_share
            contributions[acceptor_idx] = (
                contributions.get(acceptor_idx, 0.0) + bonus_share
            )
            total_bonus += gamma

    if total_bonus == 0.0:
        return 0.0, {}

    return total_bonus, contributions


def _get_atom_attribute(atom: Any, name: str) -> float:
    """Return an atom attribute from either a mapping or attribute-based object."""
    if isinstance(atom, Mapping):
        try:
            value = atom[name]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Atom is missing required field '{name}'") from exc
    else:
        try:
            value = getattr(atom, name)
        except AttributeError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Atom is missing required attribute '{name}'") from exc
    return float(value)


def _get_element(atom: Any) -> str:
    if isinstance(atom, Mapping):
        try:
            element = atom["element"]
        except KeyError as exc:
            raise ValueError("Atom is missing required field 'element'") from exc
    else:
        try:
            element = getattr(atom, "element")
        except AttributeError as exc:
            raise ValueError("Atom is missing required attribute 'element'") from exc
    if not isinstance(element, str):
        raise ValueError("Atom element must be a string")
    return element.upper()


def clash_energy(
    atoms: Iterable[Any],
    *,
    softness: float = 0.2,
    cutoff: float = 8.0,
) -> float:
    """Compute the steric clash penalty for a collection of atoms.

    The implementation follows the specification in 02_SCORE_MATH.md §1. For each
    unique atom pair `(i, j)` within the cutoff, the overlap is computed as
    `(r_i + r_j + softness) - d_ij`, where `r_k` is the van der Waals radius and
    `d_ij` is the inter-atomic distance. Positive overlaps are squared and
    accumulated; non-overlapping pairs contribute zero.

    Args:
        atoms: Iterable of atom records. Each atom must provide ``element``, ``x``,
            ``y`` and ``z`` either as dictionary keys or object attributes.
        softness: Softness margin (τ) to add to each radius sum.
        cutoff: Distance cutoff in Å beyond which pairs are ignored.

    Returns:
        The total clash penalty as a non-negative float.
    """

    atom_list = list(atoms)
    positions: list[tuple[float, float, float]] = []
    radii: list[float] = []

    for atom in atom_list:
        element = _get_element(atom)
        try:
            radius = VAN_DER_WAALS_RADII[element]
        except KeyError as exc:
            raise ValueError(f"Unsupported element '{element}' for clash calculation") from exc

        x = _get_atom_attribute(atom, "x")
        y = _get_atom_attribute(atom, "y")
        z = _get_atom_attribute(atom, "z")

        radii.append(radius)
        positions.append((x, y, z))

    total = 0.0
    cutoff_sq = cutoff * cutoff

    for i in range(len(atom_list)):
        x_i, y_i, z_i = positions[i]
        r_i = radii[i]
        for j in range(i + 1, len(atom_list)):
            x_j, y_j, z_j = positions[j]
            dx = x_j - x_i
            dy = y_j - y_i
            dz = z_j - z_i
            dist_sq = dx * dx + dy * dy + dz * dz

            if dist_sq >= cutoff_sq:
                continue

            distance = sqrt(dist_sq)
            target = r_i + radii[j] + softness
            overlap = target - distance
            if overlap > 0:
                total += overlap * overlap

    return total


def compactness_penalty(
    coords: Iterable[Sequence[float]], *, alpha: float = ALPHA_RG
) -> float:
    """Return the compactness penalty based on the radius of gyration."""

    positions = [tuple(float(value) for value in point) for point in coords]
    count = len(positions)
    if count == 0:
        return 0.0

    if count == 1:
        rg = 0.0
    else:
        sum_x = sum(point[0] for point in positions)
        sum_y = sum(point[1] for point in positions)
        sum_z = sum(point[2] for point in positions)
        centre = (sum_x / count, sum_y / count, sum_z / count)

        moment = 0.0
        for point in positions:
            dx = point[0] - centre[0]
            dy = point[1] - centre[1]
            dz = point[2] - centre[2]
            moment += dx * dx + dy * dy + dz * dz
        rg = sqrt(moment / count)

    target = 2.2 * (count ** (1.0 / 3.0))
    delta = rg - target
    return alpha * (delta * delta)
