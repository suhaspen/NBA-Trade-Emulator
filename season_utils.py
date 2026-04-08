"""Infer current NBA season id for stats.nba.com (e.g. '2025-26') from the calendar."""

from __future__ import annotations

from datetime import date


def nba_season_id(today: date | None = None) -> str:
    """
    Season runs Oct → Jun. October–December use (Y)-(Y+1); Jan–Sep use (Y-1)-(Y).
    """
    d = today or date.today()
    y, m = d.year, d.month
    if m >= 10:
        return f"{y}-{str(y + 1)[-2:]}"
    return f"{y - 1}-{str(y)[-2:]}"


def nba_season_end_calendar_year(today: date | None = None) -> int:
    """Year in which the season ends (used for pick discounting in the app)."""
    d = today or date.today()
    y, m = d.year, d.month
    if m >= 10:
        return y + 1
    return y
