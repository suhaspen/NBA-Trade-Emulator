import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trade_logic import enrich_player_pool  # noqa: E402

from tests.minimal_pool_data import MINIMAL_PLAYER_ROWS  # noqa: E402


@pytest.fixture
def minimal_pool_df() -> pd.DataFrame:
    return enrich_player_pool(pd.DataFrame(MINIMAL_PLAYER_ROWS))


@pytest.fixture
def minimal_trade_request_balanced() -> dict:
    """Alice (40M AAA) for Bob (35M BBB) — loose band should pass."""
    return {
        "league_year": 2026,
        "team_a": {
            "label": "AAA",
            "salary_bracket": "below_first_apron",
            "players": [{"player_id": 101, "query": ""}],
            "picks": [],
        },
        "team_b": {
            "label": "BBB",
            "salary_bracket": "below_first_apron",
            "players": [{"player_id": 202, "query": ""}],
            "picks": [],
        },
    }


@pytest.fixture
def minimal_trade_request_salary_fail() -> dict:
    """50M vs 30M under second apron — both sides use strict band."""
    return {
        "league_year": 2026,
        "team_a": {
            "label": "AAA",
            "salary_bracket": "second_apron",
            "players": [{"player_id": 505, "query": ""}],
            "picks": [],
        },
        "team_b": {
            "label": "BBB",
            "salary_bracket": "second_apron",
            "players": [{"player_id": 606, "query": ""}],
            "picks": [],
        },
    }
