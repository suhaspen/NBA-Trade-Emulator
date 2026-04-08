"""Integration-style tests for trade resolution and analysis (deterministic fixture pool)."""

import pandas as pd
import pytest

from cba_rules import get_band, side_is_legal
from picks import PICK_FUTURE_DECAY, resolve_pick
from trade_logic import analyze_trade, find_player_row


def test_find_player_by_player_id(minimal_pool_df: pd.DataFrame):
    row = find_player_row(minimal_pool_df, "", None, 202)
    assert row["player_name"] == "Bob Ball"
    assert row["team"] == "BBB"


def test_find_player_unknown_raises(minimal_pool_df: pd.DataFrame):
    with pytest.raises(ValueError, match="not found"):
        find_player_row(minimal_pool_df, "Nobody Here", None, None)


def test_find_player_duplicate_name_prefers_team_hint(minimal_pool_df: pd.DataFrame):
    row = find_player_row(minimal_pool_df, "Carl Clone", "BBB", None)
    assert int(row["player_id"]) == 404
    row_a = find_player_row(minimal_pool_df, "Carl Clone", "AAA", None)
    assert int(row_a["player_id"]) == 303


def test_find_player_duplicate_name_first_match_without_team(minimal_pool_df: pd.DataFrame):
    """Documented behavior: ambiguous name resolves to first dataframe match."""
    row = find_player_row(minimal_pool_df, "Carl Clone", None, None)
    assert int(row["player_id"]) == 303


def test_unknown_pick_raises(minimal_pool_df: pd.DataFrame):
    body = {
        "label": "A",
        "salary_bracket": "below_first_apron",
        "players": [{"player_id": 101, "query": ""}],
        "picks": ["not_a_real_pick"],
    }
    with pytest.raises(ValueError, match="Unknown pick"):
        analyze_trade(
            minimal_pool_df,
            body,
            {
                "label": "B",
                "salary_bracket": "below_first_apron",
                "players": [{"player_id": 202, "query": ""}],
                "picks": [],
            },
            league_year=2026,
        )


def test_resolve_pick_future_discount():
    r_same = resolve_pick("2027_1st_unprotected", league_year=2027)
    r_ahead = resolve_pick("2027_1st_unprotected", league_year=2026)
    assert r_ahead["trade_value"] == pytest.approx(r_same["trade_value"] * PICK_FUTURE_DECAY)


def test_analyze_trade_balanced_salary_legal(minimal_pool_df: pd.DataFrame, minimal_trade_request_balanced: dict):
    out = analyze_trade(
        minimal_pool_df,
        minimal_trade_request_balanced["team_a"],
        minimal_trade_request_balanced["team_b"],
        league_year=minimal_trade_request_balanced["league_year"],
    )
    assert out["salary"]["trade_legal"] is True
    assert out["salary"]["team_a_ok"] is True
    assert out["salary"]["team_b_ok"] is True
    assert out["team_a_label"] == "AAA"
    assert "profiles" in out and len(out["profiles"]) == 2
    assert "trade_value" in out and "team_a_total" in out["trade_value"]
    assert "charts" in out and "bar" in out["charts"] and "radar" in out["charts"]
    assert "verdict" in out
    assert "balance_suggestions" in out


def test_analyze_trade_second_apron_fails(minimal_pool_df: pd.DataFrame, minimal_trade_request_salary_fail: dict):
    out = analyze_trade(
        minimal_pool_df,
        minimal_trade_request_salary_fail["team_a"],
        minimal_trade_request_salary_fail["team_b"],
        league_year=minimal_trade_request_salary_fail["league_year"],
    )
    assert out["salary"]["trade_legal"] is False
    assert out["verdict"]["salary_cap_note"]  # non-empty failure note


def test_unknown_bracket_defaults_to_lenient_multiplier():
    ok_loose, _, b = side_is_legal(50.0, 40.0, "totally_fake_bracket")
    assert b.multiplier == get_band("below_first_apron").multiplier
    assert ok_loose is True


def test_match_salary_override_for_aggregation(minimal_pool_df: pd.DataFrame):
    """Optional match_salary_mm replaces cap hit for aggregation only."""
    team_a = {
        "label": "A",
        "salary_bracket": "below_first_apron",
        "players": [{"player_id": 101, "query": "", "match_salary_mm": 60.0}],
        "picks": [],
    }
    team_b = {
        "label": "B",
        "salary_bracket": "below_first_apron",
        "players": [{"player_id": 202, "query": ""}],
        "picks": [],
    }
    out = analyze_trade(minimal_pool_df, team_a, team_b, league_year=2026)
    prof = {p["player_name"]: p for p in out["profiles"]}
    assert prof["Alice Ace"]["salary_mm"] == pytest.approx(40.0)
    assert prof["Alice Ace"]["aggregation_salary_mm"] == pytest.approx(60.0)
    # 60M outgoing vs 35M incoming should break loose band on side A
    assert out["salary"]["team_a_ok"] is False
