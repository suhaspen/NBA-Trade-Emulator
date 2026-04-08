"""Draft pick option list respects season-end year."""

import pytest

from picks import list_pick_options, resolve_pick


def test_resolve_pick_unknown_id():
    with pytest.raises(ValueError, match="Unknown pick"):
        resolve_pick("not_in_catalog", league_year=2026)


def test_list_pick_options_drops_past_draft_years():
    opts_2025 = list_pick_options(league_year=2025)
    ids_2025 = {r["id"] for r in opts_2025}
    assert "2025_1st_unprotected" in ids_2025

    opts_2027 = list_pick_options(league_year=2027)
    ids_2027 = {r["id"] for r in opts_2027}
    assert "2025_1st_unprotected" not in ids_2027
    assert "2026_1st_unprotected" not in ids_2027
    assert "2027_1st_unprotected" in ids_2027

