"""Sanity checks for aggregation presets (not a CBA compliance suite)."""

from cba_rules import get_band, side_is_legal


def test_below_first_more_lenient_than_second():
    lo, _, b_lo = side_is_legal(50.0, 40.0, "below_first_apron")
    hi, _, b_hi = side_is_legal(50.0, 40.0, "second_apron")
    assert b_lo.multiplier > b_hi.multiplier
    assert lo is True
    assert hi is False


def test_max_outgoing_scales_with_incoming():
    # 40 * 1.25 + 0.1 = 50.1
    ok50, mx50, _ = side_is_legal(50.0, 40.0, "below_first_apron")
    ok51, mx51, _ = side_is_legal(51.0, 40.0, "below_first_apron")
    assert mx50 == mx51
    assert ok50 is True
    assert ok51 is False


def test_unknown_bracket_defaults():
    b = get_band("not_a_real_key")
    assert b.multiplier == get_band("below_first_apron").multiplier
