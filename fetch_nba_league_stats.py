"""
Build data/players.csv from stats.nba.com via the ``nba_api`` package.

Use this when Basketball-Reference blocks you with HTTP 403. The league stats
endpoint is official NBA data and is usually reachable from the same machine.

Limitations vs the BRef pipeline:
  - No salary or contract length: ``salary_2023_24`` / years are left blank (0 in the app).
    Merge salaries later from a spreadsheet or another allowed source if you need cap math.

Run (from project root):

  pip install nba_api pandas
  python fetch_nba_league_stats.py

Optional env:
  NBA_STATS_SEASON=2025-26   (defaults to **current** season from calendar if unset)
  NBA_STATS_OUT=data/players.csv
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats

from season_utils import nba_season_id

# NBA.com uses a few abbreviations that differ from Basketball-Reference.
NBA_TO_BREF_TEAM = {
    "BKN": "BRK",
    "CHA": "CHO",
    "PHX": "PHO",
}

DEFAULT_SEASON = os.environ.get("NBA_STATS_SEASON") or nba_season_id()
OUT_CSV = Path(os.environ.get("NBA_STATS_OUT", "data/players.csv"))


def _fetch_measure(measure: str, season: str) -> pd.DataFrame:
    time.sleep(0.65)
    raw = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
        measure_type_detailed_defense=measure,
        league_id_nullable="00",
    )
    return raw.get_data_frames()[0]


def build_player_table(season: str = DEFAULT_SEASON) -> pd.DataFrame:
    print(f"Fetching NBA.com LeagueDashPlayerStats ({season}) …")
    base = _fetch_measure("Base", season)
    adv = _fetch_measure("Advanced", season)

    adv_only = adv.drop(
        columns=[c for c in adv.columns if c in base.columns and c != "PLAYER_ID"]
    )
    merged = base.merge(adv_only, on="PLAYER_ID", how="left")

    def bref_team(abbr: str) -> str:
        if pd.isna(abbr):
            return ""
        a = str(abbr).strip().upper()
        return NBA_TO_BREF_TEAM.get(a, a)

    pts = pd.to_numeric(merged.get("PTS"), errors="coerce").fillna(0.0)
    pie = pd.to_numeric(merged.get("PIE"), errors="coerce").fillna(0.0)
    gp = pd.to_numeric(merged.get("GP"), errors="coerce").fillna(0.0)
    net = pd.to_numeric(merged.get("NET_RATING"), errors="coerce").fillna(0.0)
    offr = pd.to_numeric(merged.get("OFF_RATING"), errors="coerce").fillna(110.0)
    defr = pd.to_numeric(merged.get("DEF_RATING"), errors="coerce").fillna(110.0)

    # Align with trade_logic / radar-ish columns (NBA does not publish BPM/VORP/WS).
    bpm = net
    vorp = pie * 40.0
    ws = (pie * gp * 0.18).clip(lower=0.0)
    obpm = (offr - 110.0) / 2.0
    dbpm = (110.0 - defr) / 2.0

    out = pd.DataFrame(
        {
            "player_id": pd.to_numeric(merged["PLAYER_ID"], errors="coerce").astype("Int64"),
            "player_name": merged["PLAYER_NAME"],
            "team": merged["TEAM_ABBREVIATION"].map(bref_team),
            "age": pd.to_numeric(merged.get("AGE"), errors="coerce"),
            "pts": pts,
            "ast": pd.to_numeric(merged.get("AST"), errors="coerce").fillna(0.0),
            "reb": pd.to_numeric(merged.get("REB"), errors="coerce").fillna(0.0),
            "bpm": bpm,
            "vorp": vorp,
            "salary_2023_24": pd.NA,
            "contract_years_remaining": 0,
            "games_played": gp,
            "ts_pct": pd.to_numeric(merged.get("TS_PCT"), errors="coerce").fillna(0.0),
            "obpm": obpm,
            "dbpm": dbpm,
            "stl": pd.to_numeric(merged.get("STL"), errors="coerce").fillna(0.0),
            "blk": pd.to_numeric(merged.get("BLK"), errors="coerce").fillna(0.0),
            "ws": ws,
            "per": 0.0,
        }
    )
    if "MIN" in merged.columns:
        out["min_per_game"] = pd.to_numeric(merged["MIN"], errors="coerce").fillna(0.0)
    else:
        out["min_per_game"] = 0.0
    # Keep a stable column order similar to BRef export
    cols = [
        "player_id",
        "player_name",
        "team",
        "age",
        "pts",
        "ast",
        "reb",
        "bpm",
        "vorp",
        "salary_2023_24",
        "contract_years_remaining",
        "games_played",
        "ts_pct",
        "obpm",
        "dbpm",
        "stl",
        "blk",
        "ws",
        "per",
    ]
    if "min_per_game" in out.columns:
        cols.append("min_per_game")
    out = out[cols]
    out.sort_values(["team", "pts"], ascending=[True, False], inplace=True)
    out.reset_index(drop=True, inplace=True)
    return out


def main() -> None:
    season = DEFAULT_SEASON
    print(f"Using season id: {season}" + (" (from NBA_STATS_SEASON)" if os.environ.get("NBA_STATS_SEASON") else " (calendar default)"))
    df = build_player_table(season)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV.resolve()}  ({len(df)} players)")
    print("Note: salaries are blank — trade salary checks will be 0 until you merge contract data.")


if __name__ == "__main__":
    main()
