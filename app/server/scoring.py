"""Scoring utilities for the FoldIt prototype server."""
from __future__ import annotations

from collections.abc import Iterable
from math import sqrt
from typing import Any, Mapping

# Van der Waals radii in Ångström pulled from the score spec (02_SCORE_MATH.md §1).
VAN_DER_WAALS_RADII: Mapping[str, float] = {
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "S": 1.80,
    "H": 1.10,
}

__all__ = ["clash_energy"]


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
