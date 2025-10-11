"""Scoring utilities for the FoldIt prototype server."""
from __future__ import annotations

from collections.abc import Iterable
from math import exp, floor, log, sqrt
from typing import Any, Mapping

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

__all__ = ["clash_energy", "ramachandran_penalty"]


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
