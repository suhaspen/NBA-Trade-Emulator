import datetime

from season_utils import nba_season_end_calendar_year, nba_season_id


def test_mid_season_march():
    d = datetime.date(2026, 3, 30)
    assert nba_season_id(d) == "2025-26"
    assert nba_season_end_calendar_year(d) == 2026


def test_early_season_october():
    d = datetime.date(2025, 11, 1)
    assert nba_season_id(d) == "2025-26"
    assert nba_season_end_calendar_year(d) == 2026


def test_off_season_july():
    d = datetime.date(2025, 7, 1)
    assert nba_season_id(d) == "2024-25"
    assert nba_season_end_calendar_year(d) == 2025
