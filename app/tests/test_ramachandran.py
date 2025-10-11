"""Tests for the Ramachandran penalty implementation."""

from app.server.scoring import ramachandran_penalty


def test_general_rama_allowed_vs_out_of_range() -> None:
    allowed = ramachandran_penalty(-60.0, -40.0, residue_type="general")
    disfavoured = ramachandran_penalty(50.0, 150.0, residue_type="general")
    assert allowed < disfavoured


def test_glycine_rama_allowed_vs_out_of_range() -> None:
    allowed = ramachandran_penalty(80.0, 0.0, residue_type="gly")
    disfavoured = ramachandran_penalty(10.0, -150.0, residue_type="gly")
    assert allowed < disfavoured


def test_proline_rama_allowed_vs_out_of_range() -> None:
    allowed = ramachandran_penalty(-65.0, 140.0, residue_type="pro")
    disfavoured = ramachandran_penalty(40.0, -130.0, residue_type="pro")
    assert allowed < disfavoured
